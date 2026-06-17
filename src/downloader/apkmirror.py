"""Downloader Class."""

from typing import Any, Self, cast

from bs4 import BeautifulSoup, Tag
from loguru import logger

from src.app import APP
from src.downloader.download import Downloader
from src.downloader.sources import APK_MIRROR_BASE_URL
from src.exceptions import APKMirrorAPKDownloadError, ScrapingError
from src.utils import (
    bs4_parser,
    contains_any_word,
    handle_request_response,
    make_request,
    request_header,
    slugify,
)


class ApkMirror(Downloader):
    """Files downloader."""

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
        link_page_source = self._extract_source(link)
        notes_divs = self._extracted_search_source_div(link_page_source, "tab-pane")
        apk_type = self._extracted_search_source_div(link_page_source, "apkm-badge").get_text()
        extension = self._select_download_extension(apk_type, preserve_bundle=preserve_bundle)
        possible_links = notes_divs.find_all("a")
        for possible_link in possible_links:
            if possible_link.get("href") and "download.php?id=" in cast("str", possible_link.get("href")):
                file_name = f"{app}.{extension}"
                download_url = APK_MIRROR_BASE_URL + cast("str", possible_link["href"])
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
        download_button = self._extracted_search_div(page, "center")
        download_links = download_button.find_all("a")
        if final_download_link := next(
            (
                download_link["href"]
                for download_link in download_links
                if download_link.get("href") and "download/?key=" in cast("str", download_link.get("href"))
            ),
            None,
        ):
            return self._extract_force_download_link(
                APK_MIRROR_BASE_URL + cast("str", final_download_link),
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

    def get_download_page(self: Self, main_page: str) -> str:
        """Function to get the download page in apk_mirror.

        :param main_page: Main Download Page in APK mirror(Index)
        :return:
        """
        list_widget = self._extracted_search_div(main_page, "tab-pane noPadding")
        if list_widget is None:
            # APKMirror can return a normal 404 page for a guessed release URL, so fail before parsing variant rows.
            msg = "Unable to find APKMirror variants table on release page"
            raise APKMirrorAPKDownloadError(msg, url=main_page)
        table_rows = list_widget.find_all(class_="table-row headerFont")
        links: dict[str, str] = {}
        apk_archs = ["arm64-v8a", "universal", "noarch"]
        for row in table_rows:
            if row.find(class_="accent_color"):
                apk_type = row.find(class_="apkm-badge").get_text()
                sub_url = row.find(class_="accent_color")["href"]
                text = row.text.strip()
                if apk_type == "APK" and (not contains_any_word(text, apk_archs)):
                    continue
                links[apk_type] = f"{APK_MIRROR_BASE_URL}{sub_url}"
        if preferred_link := links.get("APK", links.get("BUNDLE")):
            return preferred_link
        msg = "Unable to extract download page"
        raise APKMirrorAPKDownloadError(msg, url=main_page)

    @staticmethod
    def _version_matches_title(version: str, title: str) -> bool:
        """Return whether an APKMirror app-row title refers to the requested version."""
        if version in title:
            return True
        # Piko advertises `release-ripped` versions while APKMirror stores the matching upstream `release` APK.
        apk_mirror_version = version.replace("-ripped", "")
        return apk_mirror_version in title

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
        app_main_page = download_source
        # APKMirror normalizes version separators to dashes inside release slugs.
        version_slug = version.replace(".", "-")
        return f"{app_main_page}-{version_slug}-release/"

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
            if self._extracted_search_source_div(page_source, "tab-pane noPadding") is not None:
                logger.debug(f"Direct URL resolved for {app.app_name} {version}: {guessed_url}")
                return guessed_url
            logger.debug(f"Guessed URL {guessed_url} loaded but has no variants table; falling back to listing.")
        except (APKMirrorAPKDownloadError, ScrapingError):
            # The guessed URL returned a non-200 or challenge page; fall through to listing-based lookup.
            logger.debug(f"Guessed URL {guessed_url} failed; falling back to listing scrape.")

        # Slow path: scrape the first page of the version listing and match by title text.
        versions_div = self._extracted_search_div(app.download_source, "listWidget p-relative")
        if versions_div is None:
            # A missing listing container means the source page is not the expected APKMirror app listing.
            msg = f"Unable to find APKMirror version list for {app.app_name}"
            raise APKMirrorAPKDownloadError(msg, url=app.download_source)

        for app_row in versions_div.find_all(class_="appRow"):
            # APKMirror release slugs can differ from the app source slug, so links must come from the listing row.
            title = app_row.find(class_="appRowTitle")
            download_link = app_row.find(class_="downloadLink")
            if not title or not download_link or not download_link.get("href"):
                continue
            if self._version_matches_title(version, title.get_text(" ", strip=True)):
                return f"{APK_MIRROR_BASE_URL}{download_link['href']}"

        msg = f"Unable to find {app.app_name} version {version} on APKMirror"
        raise APKMirrorAPKDownloadError(msg, url=app.download_source)

    @staticmethod
    def _extract_source(url: str) -> str:
        """Extracts the source from the url incase of reuse."""
        response = make_request(url, headers=request_header)
        handle_request_response(response, url)
        # cloudscraper's .text is typed as Any; cast to str to satisfy mypy
        return cast("str", response.text)

    @staticmethod
    def _extracted_search_source_div(source: str, search_class: str) -> Tag:
        """Extract search div from source."""
        soup = BeautifulSoup(source, bs4_parser)
        return soup.find(class_=search_class)  # type: ignore[return-value]

    def _extracted_search_div(self: Self, url: str, search_class: str) -> Tag:
        """Extract search div from url."""
        return self._extracted_search_source_div(self._extract_source(url), search_class)

    def specific_version(self: Self, app: APP, version: str, main_page: str = "") -> tuple[str, str]:
        """Function to download the specified version of app from  apkmirror.

        :param app: Name of the application
        :param version: Version of the application to download
        :param main_page: Version of the application to download
        :return: Version of downloaded apk
        """
        if not main_page:
            # APKMirror may rename app slugs independently from source paths, so resolve release URLs from listing HTML.
            main_page = self._find_specific_version_page(app, version)
        download_page = self.get_download_page(main_page)
        if app.app_version == "latest":
            try:
                logger.info(f"Trying to guess {app.app_name} version.")
                appsec_val = self._extracted_search_div(download_page, "appspec-value")
                appsec_version = str(appsec_val.find(text=lambda text: "Version" in text))
                appsec_version = appsec_version.rsplit(":", maxsplit=1)[-1].strip()
                appsec_version = appsec_version.split(maxsplit=1)[0]
                app.app_version = slugify(appsec_version)
                logger.info(f"Guessed {app.app_version} for {app.app_name}")
            except ScrapingError:
                pass
        return self.extract_download_link_for_app(download_page, app)

    def latest_version(self: Self, app: APP, **kwargs: Any) -> tuple[str, str]:
        """Function to download whatever the latest version of app from apkmirror.

        :param app: Name of the application
        :return: Version of downloaded apk
        """
        app_main_page = app.download_source
        versions_div = self._extracted_search_div(app_main_page, "listWidget p-relative")
        if versions_div is None:
            # Without the listing widget there is no safe way to infer the latest APKMirror release.
            msg = f"Unable to find APKMirror version list for {app.app_name}"
            raise APKMirrorAPKDownloadError(msg, url=app_main_page)
        app_rows = versions_div.find_all(class_="appRow")
        version_urls = [
            app_row.find(class_="downloadLink")["href"]
            for app_row in app_rows
            if "beta" not in app_row.find(class_="appRowTitle").get_text().lower()
            and "alpha" not in app_row.find(class_="appRowTitle").get_text().lower()
        ]
        return self.specific_version(app, "latest", APK_MIRROR_BASE_URL + max(version_urls))
