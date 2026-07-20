"""Upto Down Downloader."""

import re
from typing import Any, Self, cast

from bs4 import BeautifulSoup, Tag
from loguru import logger

from src.apks.variant_sorter import VariantSorter
from src.app import APP
from src.downloader.download import Downloader
from src.exceptions import NOT_FOUND_STATUS_CODE, ScrapingError, UptoDownAPKDownloadError, VersionNotFoundError
from src.utils import bs4_parser, handle_request_response, make_request, request_header


class UptoDown(Downloader):
    """Files downloader."""

    @staticmethod
    def _is_xapk_variant_page(page: str) -> bool:
        """Detect Uptodown variant URLs that expose the real XAPK file instead of the store bridge."""
        return page.rstrip("/").endswith("-x")

    @staticmethod
    def _is_xapk_store_bridge(detail_download_button: Tag, page: str) -> bool:
        """Detect generic XAPK download pages whose direct token is missing and needs the legacy variant path."""
        button_classes = detail_download_button.get("class") or []
        # Direct variant pages already point at app bytes, so only generic pages are eligible for fallback rewriting.
        return "xapk" in button_classes and not UptoDown._is_xapk_variant_page(page)

    def _resolve_xapk_variant_page(self: Self, detail_download_button: Tag, page: str, app: str) -> str:
        """Build the direct XAPK variant URL from Uptodown's generic app-store bridge button."""
        download_version = detail_download_button.get("data-download-version")
        if not download_version:
            msg = f"Unable to resolve direct XAPK download for {app} from uptodown."
            raise UptoDownAPKDownloadError(msg, url=page)

        # Uptodown encodes the real file endpoint as `/download/<file-id>-x` behind the variants UI.
        return f"{page.rstrip('/')}/{download_version}-x"

    def _get_app_code(self: Self, url: str) -> str:
        """Extract the numeric app code from a Uptodown page."""
        html = make_request(url, headers=request_header).text
        soup = BeautifulSoup(html, bs4_parser)
        el = soup.find("h1", id="detail-app-name")
        if not isinstance(el, Tag):
            msg = f"Could not find app code element on {url}"
            raise UptoDownAPKDownloadError(msg, url=url)
        code = cast("str", el.get("data-code", ""))
        if not code:
            msg = f"App code missing on {url}"
            raise UptoDownAPKDownloadError(msg, url=url)
        return code

    @staticmethod
    def _text_or(tag: Tag | None) -> str:
        """Return stripped text of a tag, or empty string."""
        return tag.text.strip() if tag is not None else ""

    @staticmethod
    def _parse_variant_arch_text(soup: BeautifulSoup) -> list[Any]:
        """Extract shared arch text from the variants section."""
        arch_text = ""
        section = soup.find("section", class_="variants")
        content_div = section.find("div", class_="content") if section else None
        if content_div:
            p_tag = content_div.find("p")
            if p_tag:
                arch_text = p_tag.get_text(strip=True)
        return list(VariantSorter.parse_archs(arch_text)) if arch_text else []

    def _fetch_variants(self: Self, app: APP, app_code: str, version_id: str) -> list[dict[str, Any]]:
        """Fetch variant info from the Uptodown variants API.

        Returns a list of dicts with keys:
            file_id, download_url, archs (list[Arch]), density (Density | None)
        """
        base = app.download_source.rstrip("/")
        if base.endswith("/android"):
            base = base[:-8]
        elif base.endswith("/download"):
            base = base[:-9]

        download_page = f"{app.download_source}/download"
        api_url = f"{base}/app/{app_code}/version/{version_id}/files"

        # Prime cookies by visiting the download page (variant API requires session state).
        make_request(download_page, headers=request_header)

        r = make_request(
            api_url,
            headers=request_header
            | {
                "Accept": "application/json, text/plain, */*",
                "Referer": download_page,
            },
        )

        if r.status_code == NOT_FOUND_STATUS_CODE:
            return []

        data = r.json()
        content = data.get("content", "")
        if not content:
            return []

        soup = BeautifulSoup(content, bs4_parser)
        parsed_archs = self._parse_variant_arch_text(soup)

        variants: list[dict[str, Any]] = []
        for card in soup.find_all("div", class_="variant"):
            img = card.find("img", attrs={"data-file-id": True})
            if not img:
                continue

            file_id = img.get("data-file-id", "")
            name_el = card.find("div", class_="v-version")
            arch_el = card.find("div", class_="v-screen")

            onclick = cast("str", name_el.get("onclick", "")) if name_el else ""
            dl_url = ""
            if "location.href" in onclick:
                m = re.search(r"location\.href='([^']+)'", onclick)
                if m:
                    dl_url = m.group(1)

            density_text = self._text_or(arch_el)
            parsed_density = VariantSorter.parse_density(density_text) if density_text else None

            variants.append(
                {
                    "file_id": file_id,
                    "download_url": dl_url,
                    "archs": list(parsed_archs),
                    "density": parsed_density,
                },
            )

        return variants

    def _select_best_variant(self: Self, app: APP, app_code: str, version_id: str) -> tuple[str, str] | None:
        """Select and download the best variant, or return None if no variants exist."""
        variants = self._fetch_variants(app, app_code, version_id)
        if not variants:
            return None

        # Sort with best match first (reverse=True)
        variants.sort(
            key=lambda v: VariantSorter.sorting_key(v["archs"], v["density"]),
            reverse=True,
        )

        best = variants[0]
        dl_url = best["download_url"]
        if not dl_url:
            return None

        file_name = f"{app.app_name}.apk"
        self._download(dl_url, file_name, extra_headers=request_header)

        return file_name, dl_url

    def extract_download_link(self: Self, page: str, app: str) -> tuple[str, str]:
        """Extract download link from uptodown url."""
        r = make_request(page, headers=request_header)
        handle_request_response(r, page)
        soup = BeautifulSoup(r.text, bs4_parser)
        detail_download_button = soup.find("button", id="detail-download-button")

        if not isinstance(detail_download_button, Tag):
            msg = f"Unable to download {app} from uptodown."
            raise UptoDownAPKDownloadError(msg, url=page)

        data_url = detail_download_button.get("data-url")
        if not isinstance(data_url, str) or not data_url:
            if self._is_xapk_store_bridge(detail_download_button, page):
                # Older Uptodown pages omitted the direct token, so keep the variant-page fallback for that shape.
                return self.extract_download_link(
                    self._resolve_xapk_variant_page(detail_download_button, page, app),
                    app,
                )

            msg = f"Unable to download {app} from uptodown."
            raise UptoDownAPKDownloadError(msg, url=page)

        download_url = f"https://dw.uptodown.com/dwn/{data_url}"
        # Generic pages may be labeled XAPK while redirecting to one APK; archive inspection handles splits later.
        file_name = f"{app}.xapk" if self._is_xapk_variant_page(page) else f"{app}.apk"
        self._download(download_url, file_name, extra_headers=request_header)

        return file_name, download_url

    def specific_version(self: Self, app: APP, version: str) -> tuple[str, str]:  # noqa: C901
        """Function to download the specified version of app from uptodown.

        :param app: Name of the application
        :param version: Version of the application to download
        :return: Version of downloaded apk
        """
        logger.debug("downloading specified version of app from uptodown.")
        url = f"{app.download_source}/versions"
        html = make_request(url, headers=request_header).text
        soup = BeautifulSoup(html, bs4_parser)
        detail_app_name = soup.find("h1", id="detail-app-name")

        if not isinstance(detail_app_name, Tag):
            msg = f"Unable to download {app} from uptodown."
            raise UptoDownAPKDownloadError(msg, url=url)

        app_code = cast("str", detail_app_name.get("data-code"))
        version_page = 1
        download_url = None
        version_found = False

        while not version_found:
            version_url = f"{app.download_source}/apps/{app_code}/versions/{version_page}"
            r = make_request(version_url, headers=request_header)
            handle_request_response(r, version_url)
            json = r.json()

            if "data" not in json:
                break

            for item in json["data"]:
                if item["version"] == version:
                    version_url_data = item["versionURL"]
                    if isinstance(version_url_data, dict):
                        version_id = str(version_url_data.get("versionID", ""))
                        if version_id:
                            variant_result = self._select_best_variant(app, app_code, version_id)
                            if variant_result is not None:
                                return variant_result
                        download_url = f"{version_url_data['url']}/{version_url_data['extraURL']}/{version_id}"
                    else:
                        download_url = f"{version_url_data}-x"
                    version_found = True
                    break

            version_page += 1

        if download_url is None:
            msg = f"Unable to download {app.app_name} from uptodown."
            raise VersionNotFoundError(msg, url=url)

        try:
            return self.extract_download_link(download_url, app.app_name)
        except ScrapingError as exc:
            if not exc.is_not_found():
                raise
            # let the version-fallback system try a different version.
            msg = f"UptoDown version download page not found: {download_url}"
            raise VersionNotFoundError(
                msg,
                url=download_url,
            ) from exc

    def latest_version(self: Self, app: APP, **kwargs: Any) -> tuple[str, str]:
        """Function to download the latest version of app from uptodown."""
        logger.debug("downloading latest version of app from uptodown.")
        page = f"{app.download_source}/download"

        # Try variant selection first: scrape version info from the download page.
        try:
            r = make_request(page, headers=request_header)
            handle_request_response(r, page)
            soup = BeautifulSoup(r.text, bs4_parser)

            app_code = ""
            el = soup.find("h1", id="detail-app-name")
            if isinstance(el, Tag):
                app_code = cast("str", el.get("data-code", ""))

            dl_button = soup.find("button", id="detail-download-button")
            version_id = cast("str", dl_button.get("data-download-version", "")) if isinstance(dl_button, Tag) else ""

            if app_code and version_id:
                variant_result = self._select_best_variant(app, app_code, version_id)
                if variant_result is not None:
                    return variant_result
        except UptoDownAPKDownloadError:
            logger.debug("Variant selection for latest version failed, falling back to default download.")

        return self.extract_download_link(page, app.app_name)
