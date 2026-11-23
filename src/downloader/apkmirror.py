"""Downloader Class."""

from dataclasses import dataclass
from typing import Any, Self, cast
from urllib.parse import urlsplit
lazy from collections.abc import Collection

import turbohtml
from loguru import logger

from src.apks.variant_sorter import Arch, Density, VariantSorter
from src.apks.version_sorter import VersionSorter
from src.downloader.download import Downloader
from src.downloader.morphe_resolver import resolve_download_page
from src.downloader.sources import APK_MIRROR_BASE_URL
from src.exceptions import APKMirrorAPKDownloadError, ScrapingError, VersionNotFoundError
from src.utils import (
    apkmirror_status_check,
    handle_request_response,
    make_request,
    request_header,
    slugify,
)
lazy from src.app import APP

# Listing and upload pages scraped when the direct release URL guess misses.
LISTING_PAGES = 3
# Index of `<category>` in an `apk/<developer>/<category>/<slug>` source path.
CATEGORY_SEGMENT = 2
# `secondary` builds are alternate packages.
UNSTABLE_RELEASE_MARKERS = ("alpha", "beta", "secondary")
DEFAULT_RESOLVER_ABI = "arm64-v8a"
# A variant page's parent is its release page.
VARIANT_PAGE_MARKER = "-android-apk-download"


@dataclass(frozen=True, slots=True)
class MirrorVariant:
    """One row of an APKMirror release's variants table."""

    type: str  ## APK or BUNDLE badge
    url: str
    archs: list[Arch]
    density: Density | None
    codes: frozenset[int]  ## Android version codes shown in the row


class ApkMirror(Downloader):
    """Files downloader."""

    apk_type: str = "APK"

    @staticmethod
    def _select_download_extension(apk_type: str, *, preserve_bundle: bool) -> str:
        """Choose the local extension that preserves the patcher's expected input shape."""
        if apk_type == "BUNDLE" and preserve_bundle:
            # Morphe can patch APKM bundles directly, so preserving the bundle avoids APKEditor flattening split inputs.
            return "apkm"
        if apk_type == "BUNDLE":
            # ReVanced-style patchers still receive a merged APK, so bundles keep an archive suffix for APKEditor.
            return "zip"
        # Single APK variants are already patcher-ready and should keep the normal APK suffix.
        return "apk"

    def _extract_force_download_link(
        self: Self,
        link: str,
        app: str,
        *,
        preserve_bundle: bool = False,
    ) -> tuple[str, str]:
        """Extract force download link.

        The actual download.php file endpoint is also behind Cloudflare, so we
        must use apkmirror_scraper (instead of the plain requests session) and
        pass the download page URL as a Referer header — exactly what the
        twitter-apk reference implementation does — to satisfy Cloudflare checks.
        """
        link_page_doc = turbohtml.parse(self._extract_source(link))
        download_links_container = link_page_doc.find(class_="tab-pane")
        if download_links_container is None:
            msg = f"Unable to extract force download for {app}"
            raise APKMirrorAPKDownloadError(msg, url=link)
        extension = self._select_download_extension(self.apk_type, preserve_bundle=preserve_bundle)
        possible_links = download_links_container.find_all("a")
        for possible_link in possible_links:
            if possible_link.attr("href") and "download.php?id=" in cast("str", possible_link.attr("href")):
                file_name = f"{app}.{extension}"
                download_url = APK_MIRROR_BASE_URL + cast("str", possible_link.attrs["href"])
                # Use cloudscraper + Referer so Cloudflare allows the binary download
                self._download(
                    download_url,
                    file_name,
                    extra_headers={"Referer": link},
                )
                return file_name, download_url
        msg = f"Unable to extract force download for {app}"
        raise APKMirrorAPKDownloadError(msg, url=link)

    def _extract_download_link(self: Self, page: str, app: str, *, preserve_bundle: bool) -> tuple[str, str]:
        """Extract the APKMirror download link while honoring the selected input-shape policy.

        :param page: Url of the page
        :param app: Name of the app
        """
        logger.debug(f"Extracting download link from\n{page}")
        download_page_doc = turbohtml.parse(self._extract_source(page))
        download_button = download_page_doc.find(class_="center")
        if download_button is None:
            msg = f"Unable to extract link from {app} version list"
            raise APKMirrorAPKDownloadError(msg, url=page)
        download_links = download_button.find_all("a")
        if matched_link := next(
            (
                download_link
                for download_link in download_links
                if download_link.attr("href") and "download/?key=" in cast("str", download_link.attr("href"))
            ),
            None,
        ):
            # When apk_type is BUNDLE, the download links can either be
            # a simple APK or an APKM bundle. The text inside the box (<a> tag)
            # determines which one it is.
            if self.apk_type == "BUNDLE":
                link_text = "".join(matched_link.strings).lower()
                self.apk_type = "BUNDLE" if "apk bundle" in link_text else "APK"

            final_download_link = cast("str", matched_link.attrs["href"])
            return self._extract_force_download_link(
                APK_MIRROR_BASE_URL + final_download_link,
                app,
                preserve_bundle=preserve_bundle,
            )
        msg = f"Unable to extract link from {app} version list"
        raise APKMirrorAPKDownloadError(msg, url=page)

    def extract_download_link(self: Self, page: str, app: str) -> tuple[str, str]:
        """Function to extract the download link from apkmirror html page.

        :param page: Url of the page
        :param app: Name of the app
        """
        # Public callers keep historical merged-bundle behavior unless they pass through the APP-aware path below.
        return self._extract_download_link(page, app, preserve_bundle=False)

    def extract_download_link_for_app(self: Self, page: str, app: APP) -> tuple[str, str]:
        """Extract the APKMirror download link using the app's patcher profile."""
        # Morphe's APKM support is profile-specific, so only Morphe apps preserve APKMirror bundles as `.apkm`.
        preserve_bundle = app.effective_cli_argsf == "morphe-cli"
        return self._extract_download_link(page, app.app_name, preserve_bundle=preserve_bundle)

    def get_download_page(self: Self, main_page: str, version_codes: Collection[int] = ()) -> str:
        """Function to get the download page in apk_mirror.

        :param main_page: Main Download Page in APK mirror(Index)
        :param version_codes: Version codes the patches target, preferred over arch and density
        :return:
        """
        try:
            main_page_doc = turbohtml.parse(self._extract_source(main_page))
            variants_container = main_page_doc.select_one(".tab-pane.noPadding")
        except ScrapingError as exc:
            if not exc.is_not_found():
                # Non-404 scraping errors (5xx, etc.) should propagate, not trigger fallback.
                raise
            # let the version-fallback system try a different version.
            msg = f"APKMirror release page not found: {main_page}"
            raise VersionNotFoundError(
                msg,
                url=main_page,
            ) from exc
        if variants_container is None:
            msg = "Unable to find APKMirror variants table on release page"
            raise APKMirrorAPKDownloadError(msg, url=main_page)
        table_rows = variants_container.select(".table-row.headerFont")
        variants: list[MirrorVariant] = []

        for row in table_rows:
            accent = row.find(class_="accent_color")
            if not accent:
                continue
            badge = row.find(class_="apkm-badge")
            if not badge:
                continue
            text = row.text.strip()
            variants.append(
                MirrorVariant(
                    type="".join(badge.strings),
                    url=f"{APK_MIRROR_BASE_URL}{accent.attr('href')}",
                    archs=VariantSorter.parse_archs(text, delimiter=None),
                    density=VariantSorter.parse_density(text),
                    # The variant cell shows the version code in a plain colorLightBlack span, next to the date span.
                    codes=frozenset(
                        int(code)
                        for span in row.select("span.colorLightBlack")
                        if (code := "".join(span.strings).strip()).isdigit()
                    ),
                ),
            )

        if not variants:
            msg = "Unable to extract download page"
            raise APKMirrorAPKDownloadError(msg, url=main_page)

        # Variants of one version are separate builds, so patch fingerprints only match the targeted codes.
        if version_codes:
            matching = [v for v in variants if v.codes & set(version_codes)]
            if matching:
                variants = matching
            else:
                logger.warning(f"No APKMirror variant matches version codes {sorted(version_codes)} on {main_page}")

        # Prefer APK over BUNDLE, then the best arch and density.
        selected = max(
            variants,
            key=lambda v: (v.type != "BUNDLE", VariantSorter.sorting_key(v.archs, v.density)),
        )
        logger.debug(f"Selected APKMirror variant with version codes {sorted(selected.codes)}: {selected.url}")
        self.apk_type = selected.type
        return selected.url

    @staticmethod
    def _version_matches_title(version: str, title: str) -> bool:
        """Return whether an APKMirror app-row title refers to the requested version.

        The version must be a whole word, so `445.0.0.0.3` does not match `445.0.0.0.37 alpha`.
        """
        words = title.split()
        # Piko advertises `release-ripped` versions while APKMirror stores the matching upstream `release` APK.
        return version in words or version.replace("-ripped", "") in words

    @staticmethod
    def _guess_release_url(download_source: str, version: str) -> str:
        """Construct a direct APKMirror release URL from the app listing URL and version.

        APKMirror follows a predictable slug pattern: the last path segment of the listing URL
        (the app slug) is combined with the version (dots replaced by dashes) and a '-release'
        suffix. For example:
          source: https://www.apkmirror.com/apk/google-inc/youtube/youtube
          version: 20.51.39
          result: https://www.apkmirror.com/apk/google-inc/youtube/youtube-20-51-39-release/
        """
        # Piko advertises `release-ripped` versions while APKMirror stores the matching upstream `release` APK.
        # APKMirror normalizes version separators to dashes inside release slugs.
        version_slug = version.replace("-ripped", "").replace(".", "-")
        return f"{download_source}-{version_slug}-release/"

    @staticmethod
    def _listing_path(download_source: str) -> str:
        """Return the `/apk/<developer>/<category>/` listing path of an app source URL."""
        path = download_source.removeprefix(APK_MIRROR_BASE_URL).strip("/").split("/")
        return "/" + "/".join(path[: CATEGORY_SEGMENT + 1]) + "/"

    @staticmethod
    def _listing_urls(download_source: str) -> list[str]:
        """Return the app listing followed by older APKMirror upload pages for the same app category.

        The listing only shows recent uploads, and older ones are paged under `/uploads/` by the
        category segment of `/apk/<developer>/<category>/<slug>`.
        """
        path = download_source.removeprefix(APK_MIRROR_BASE_URL).strip("/").split("/")
        category = path[CATEGORY_SEGMENT] if len(path) > CATEGORY_SEGMENT else ""
        pages = range(2, LISTING_PAGES + 1) if category else range(0)
        return [download_source, *(f"{APK_MIRROR_BASE_URL}/uploads/page/{n}/?appcategory={category}" for n in pages)]

    def _match_listing_rows(self: Self, versions_container: Any, version: str) -> str | None:
        """Return the release URL of the listing row whose title names the requested version."""
        for app_row in versions_container.find_all(class_="appRow"):
            # APKMirror release slugs can differ from the app source slug, so links must come from the listing row.
            title = app_row.find(class_="appRowTitle")
            download_link = app_row.find(class_="downloadLink")
            if not title or not download_link or not download_link.attr("href"):
                continue
            if self._version_matches_title(version, " ".join(title.stripped_strings)):
                return f"{APK_MIRROR_BASE_URL}{download_link.attrs['href']}"
        return None

    @staticmethod
    def _release_page_of(url: str) -> str:
        """Return the APKMirror release page a resolver answer points into, or an empty string."""
        parts = urlsplit(url)
        if f"{parts.scheme}://{parts.hostname}" != APK_MIRROR_BASE_URL:
            return ""
        path = parts.path.rstrip("/")
        if VARIANT_PAGE_MARKER in path:
            path = path.rsplit("/", 1)[0]
        return f"{APK_MIRROR_BASE_URL}{path}/" if path.endswith("-release") else ""

    @staticmethod
    def _resolver_release_page(app: APP, version: str) -> str:
        """Ask Morphe's resolver for the release page of a version, which also covers renamed release slugs."""
        if version == "latest":
            return ""
        abi = app.archs_to_build[0] if len(app.archs_to_build) == 1 else DEFAULT_RESOLVER_ABI
        codes = VersionSorter.target_codes(app.compatible_version_codes, version, [abi])
        code = next(iter(codes)) if len(codes) == 1 else None
        # APKMirror lists `release-ripped` versions under the upstream `release` name.
        page = resolve_download_page(app.package_name, version.replace("-ripped", ""), abi, code)
        release_page = ApkMirror._release_page_of(page)
        # Trust only a release of this version in the source's listing.
        expected = ApkMirror._guess_release_url("", version)
        listing = APK_MIRROR_BASE_URL + ApkMirror._listing_path(app.download_source)
        if release_page.startswith(listing) and release_page.endswith(expected):
            logger.debug(f"Morphe resolver found {app.app_name} {version}: {release_page}")
            return release_page
        return ""

    @staticmethod
    def app_exists(package_name: str) -> dict[str, Any]:
        """Return APKMirror's latest stable release entry for a package, or an empty dict when it has none."""
        try:
            entries: list[dict[str, Any]] = (
                apkmirror_status_check(package_name, exclude=["alpha", "beta"]).get("data") or []
            )
        except Exception as exc:  # noqa: BLE001 - the listing scrape is the fallback
            logger.debug(f"APKMirror app_exists failed for {package_name}: {exc}")
            return {}
        entry = next((e for e in entries if e.get("pname") == package_name and e.get("exists")), {})
        version = entry.get("release", {}).get("version", "")
        if not entry.get("release", {}).get("link") or any(m in version.lower() for m in UNSTABLE_RELEASE_MARKERS):
            return {}
        return entry

    @staticmethod
    def source_for_package(package_name: str) -> str:
        """Return the APKMirror app source URL for a package, or an empty string when APKMirror lacks it."""
        release = ApkMirror.app_exists(package_name).get("release", {})
        suffix = f"-{release.get('version', '').replace('.', '-')}-release"
        release_path = release.get("link", "").rstrip("/")
        if not release_path.endswith(suffix):
            return ""
        return f"{APK_MIRROR_BASE_URL}{release_path.removesuffix(suffix)}"

    def _find_specific_version_page(self: Self, app: APP, version: str) -> str:
        """Resolve a specific APKMirror release URL, trying a direct URL guess before listing scrape.

        The listing page only shows the most recent versions. Popular apps like YouTube push older
        versions off the first page quickly, so a direct URL construction is attempted first.
        """
        # Fast path: construct the release URL directly and verify that the release page exists.
        guessed_url = self._guess_release_url(app.download_source, version)
        try:
            page_source = self._extract_source(guessed_url)
            # A valid release page contains the variants table; a 404/soft-error page does not.
            release_doc = turbohtml.parse(page_source)
            if release_doc.select_one(".tab-pane.noPadding") is not None:
                logger.debug(f"Direct URL resolved for {app.app_name} {version}: {guessed_url}")
                return guessed_url
            logger.debug(f"Guessed URL {guessed_url} loaded but has no variants table; falling back to listing.")
        except (APKMirrorAPKDownloadError, ScrapingError) as exc:
            # The guessed URL returned a non-200 or challenge page; fall through to listing-based lookup.
            logger.warning(f"Guessed URL {guessed_url} failed ({exc}); falling back to listing scrape.")

        # Slow path: scrape the recent listing pages and match by title text.
        for page, listing_url in enumerate(self._listing_urls(app.download_source), start=1):
            try:
                listing_doc = turbohtml.parse(self._extract_source(listing_url))
            except (APKMirrorAPKDownloadError, ScrapingError) as exc:
                if page == 1:
                    raise
                # Pages past the last upload return 404, which simply ends the listing.
                if isinstance(exc, ScrapingError) and exc.is_not_found():
                    logger.debug(f"APKMirror listing ends before {listing_url}.")
                else:
                    logger.warning(f"APKMirror listing page {listing_url} failed ({exc}); stopping pagination.")
                break
            versions_container = listing_doc.select_one(".listWidget.p-relative")
            if versions_container is None:
                if page == 1:
                    # A missing listing container means the source page is not the expected APKMirror app listing.
                    msg = f"Unable to find APKMirror version list for {app.app_name}"
                    raise APKMirrorAPKDownloadError(msg, url=app.download_source)
                break

            if release_url := self._match_listing_rows(versions_container, version):
                return release_url

        msg = f"Unable to find {app.app_name} version {version} on APKMirror"
        raise VersionNotFoundError(msg, url=app.download_source)

    @staticmethod
    def _extract_source(url: str) -> str:
        """Extracts the source from the url incase of reuse."""
        response = make_request(url, headers=request_header)
        handle_request_response(response, url)
        return response.text

    def specific_version(self: Self, app: APP, version: str, main_page: str = "") -> tuple[str, str]:
        """Function to download the specified version of app from  apkmirror.

        :param app: Name of the application
        :param version: Version of the application to download
        :param main_page: Version of the application to download
        :return: Version of downloaded apk
        """
        if not main_page:
            # Release slugs can differ from the source slug, so resolve before guessing.
            main_page = self._resolver_release_page(app, version) or self._find_specific_version_page(app, version)
        # Only codes for the built archs count, so a missing arm64 build cannot fall through to another arch's build.
        target_codes = VersionSorter.target_codes(app.compatible_version_codes, version, app.archs_to_build)
        download_page = self.get_download_page(main_page, target_codes)
        if version == "latest":
            try:
                logger.info(f"Trying to resolve {app.app_name} version.")
                download_page_doc = turbohtml.parse(self._extract_source(download_page))
                appspec_value = download_page_doc.find(class_="appspec-value")
                if appspec_value is not None:
                    appspec_text = next(
                        (text for text in appspec_value.stripped_strings if "Version" in text),
                        "",
                    )
                    if appspec_text:
                        appspec_version = appspec_text.rsplit(":", maxsplit=1)[-1].strip()
                        appspec_version = appspec_version.split(maxsplit=1)[0]
                        app.resolved_version = slugify(appspec_version)
                        logger.info(f"Resolved {app.resolved_version} for {app.app_name}")
            except ScrapingError:
                pass
        return self.extract_download_link_for_app(download_page, app)

    def latest_version(self: Self, app: APP, **kwargs: Any) -> tuple[str, str]:
        """Function to download whatever the latest version of app from apkmirror.

        :param app: Name of the application
        :return: Version of downloaded apk
        """
        release_link = self.app_exists(app.package_name).get("release", {}).get("link", "")
        # A package can have several listings, such as an Android TV one.
        if release_link and release_link.startswith(self._listing_path(app.download_source)):
            return self.specific_version(app, "latest", APK_MIRROR_BASE_URL + release_link)
        app_main_page = app.download_source
        main_page_doc = turbohtml.parse(self._extract_source(app_main_page))
        versions_container = main_page_doc.select_one(".listWidget.p-relative")
        if versions_container is None:
            # Without the listing widget there is no safe way to infer the latest APKMirror release.
            msg = f"Unable to find APKMirror version list for {app.app_name}"
            raise APKMirrorAPKDownloadError(msg, url=app_main_page)
        # Rows are newest first.
        latest_url = next(
            (
                href
                for app_row in versions_container.find_all(class_="appRow")
                if (dl := app_row.find(class_="downloadLink")) and (href := dl.attr("href"))
                if (title := app_row.find(class_="appRowTitle"))
                and not any(marker in "".join(title.strings).lower() for marker in UNSTABLE_RELEASE_MARKERS)
            ),
            None,
        )
        if not latest_url:
            msg = f"No stable APKMirror release found for {app.app_name}"
            raise APKMirrorAPKDownloadError(msg, url=app_main_page)
        return self.specific_version(app, "latest", APK_MIRROR_BASE_URL + latest_url)
