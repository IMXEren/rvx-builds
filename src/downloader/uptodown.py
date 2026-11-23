"""Upto Down Downloader."""

import base64
import hashlib
import hmac
import json
import re
import secrets
import time
from typing import Any, ClassVar, Self, cast

import turbohtml
from loguru import logger

from src.apks.variant_sorter import VariantSorter
from src.downloader.download import Downloader
from src.downloader.sources import UPTODOWN_API_URL, UPTODOWN_SUFFIX
from src.exceptions import NOT_FOUND_STATUS_CODE, UptoDownAPKDownloadError, VersionNotFoundError
from src.utils import handle_request_response, make_request, request_header, request_timeout, session
lazy from src.app import APP

# The Android client's API is not behind the web pages' Turnstile.
CLIENT_HEADERS = {
    "User-Agent": "Dalvik/2.1.0 (Linux; U; Android 16; Pixel 8 Pro Build/BP4A.260205.001)",
    "Identificador": "Uptodown_Android",
    "Identificador-Version": "739",
    "Accept": "application/json",
}
# Signs the token request timestamp.
CLIENT_HMAC_KEY = b"MDGMXUMdvHJBG/vjdFgmqX6LUdy7ecfwvYNd0gyfOCs="
CLIENT_PLATFORM = "13"
TOKEN_EXPIRY_MARGIN = 60
MAX_VERSION_PAGES = 50


class UptoDown(Downloader):
    """Files downloader."""

    _token: ClassVar[str] = ""
    _token_expiry: ClassVar[float] = 0.0

    @classmethod
    def _authorize(cls: type[Self], *, force: bool = False) -> str:
        """Return a client API token, requesting a new one when the cached token expires."""
        if cls._token and not force and time.time() < cls._token_expiry - TOKEN_EXPIRY_MARGIN:
            return cls._token
        timestamp = str(int(time.time()))
        identifier = secrets.token_hex(8)
        signature = hmac.new(CLIENT_HMAC_KEY, timestamp.encode(), hashlib.sha256).hexdigest()
        response = session.post(
            f"{UPTODOWN_API_URL}/auth/token?identifier={identifier}",
            headers=CLIENT_HEADERS,
            data={
                "identifier": identifier,
                "id_plataforma": CLIENT_PLATFORM,
                "lang": "en",
                "unixtime": timestamp,
                "hmac": signature,
            },
            timeout=request_timeout,
        )
        handle_request_response(response, f"{UPTODOWN_API_URL}/auth/token")
        token = cast("str", response.json().get("token", ""))
        if not token:
            msg = "Uptodown returned no API token"
            raise UptoDownAPKDownloadError(msg, url=UPTODOWN_API_URL)
        # The JWT payload carries the expiry.
        payload = token.split(".")[1]
        expiry = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("exp", 0)
        cls._token, cls._token_expiry = token, float(expiry)
        return token

    @classmethod
    def _api_get(cls: type[Self], path: str) -> dict[str, Any]:
        """Return the `data` object of a client API call, renewing the token once when it is rejected."""
        url = f"{UPTODOWN_API_URL}{path}"
        for force in (False, True):
            headers = CLIENT_HEADERS | {"Authorization": f"Bearer {cls._authorize(force=force)}"}
            response = session.get(url, headers=headers, timeout=request_timeout)
            if response.status_code != 401:  # noqa: PLR2004 - HTTP Unauthorized
                break
        handle_request_response(response, url)
        return cast("dict[str, Any]", response.json().get("data") or {})

    @classmethod
    def _app_id(cls: type[Self], package_name: str) -> str:
        """Return Uptodown's app id for a package, or an empty string when Uptodown lacks it."""
        return str(cls._api_get(f"/apps/byPackagename/{package_name}").get("appID", ""))

    @classmethod
    def source_for_package(cls: type[Self], package_name: str) -> str:
        """Return the Uptodown app source URL for a package, or an empty string when Uptodown lacks it."""
        try:
            app_id = cls._app_id(package_name)
            share_url = cast("str", cls._api_get(f"/v3/apps/{app_id}/device/0").get("urlShare", "")) if app_id else ""
        except Exception as exc:  # noqa: BLE001 - discovery moves on to the next mirror
            logger.debug(f"Uptodown lookup failed for {package_name}: {exc}")
            return ""
        # The factory recognizes the English host.
        match = re.fullmatch(r"https://([^.]+)\.uptodown\.com/android/?", share_url)
        return f"https://{match.group(1)}.{UPTODOWN_SUFFIX}" if match else ""

    @staticmethod
    def _text_or(el: turbohtml.Element | None) -> str:
        """Return stripped text of a tag, or empty string."""
        return el.text.strip() if el is not None else ""

    @staticmethod
    def _parse_variant_arch_text(doc: turbohtml.Document) -> list[Any]:
        """Extract shared arch text from the variants section."""
        arch_text = ""
        section = doc.find("section", class_="variants")
        content_div = section.find("div", class_="content") if section else None
        if content_div:
            p_tag = content_div.find("p")
            if p_tag:
                arch_text = "".join(p_tag.stripped_strings)
        return list(VariantSorter.parse_archs(arch_text)) if arch_text else []

    def _fetch_variants(self: Self, app: APP, app_id: str, version_id: str) -> list[dict[str, Any]]:
        """Fetch variant info from the Uptodown variants endpoint.

        Returns a list of dicts with keys: file_id, archs (list[Arch]), density (Density | None)
        """
        download_page = f"{app.download_source}/download"
        api_url = f"{app.download_source.removesuffix('/android')}/app/{app_id}/version/{version_id}/files"

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
        content = r.json().get("content", "")
        if not content:
            return []

        doc = turbohtml.parse(content)
        parsed_archs = self._parse_variant_arch_text(doc)
        variants: list[dict[str, Any]] = []
        for card in doc.find_all("div", class_="variant"):
            img = card.find("img", attrs={"data-file-id": True})
            if not img:
                continue
            density_text = self._text_or(card.find("div", class_="v-screen"))
            variants.append(
                {
                    "file_id": img.attr("data-file-id", ""),
                    "archs": list(parsed_archs),
                    "density": VariantSorter.parse_density(density_text) if density_text else None,
                },
            )
        return variants

    def _find_release(self: Self, app: APP, app_id: str, version: str | None) -> dict[str, Any]:
        """Return the version list entry of a version, or the newest entry when no version is given."""
        for page in range(1, MAX_VERSION_PAGES + 1):
            url = f"{app.download_source}/apps/{app_id}/versions/{page}"
            response = make_request(url, headers=request_header)
            handle_request_response(response, url)
            items = response.json().get("data") or []
            if not items:
                break
            for item in items:
                if version is None or item.get("version") == version:
                    return cast("dict[str, Any]", item)
        msg = f"Unable to find {app.app_name} version {version} on uptodown"
        raise VersionNotFoundError(msg, url=app.download_source)

    def _download_release(self: Self, app: APP, version: str | None) -> tuple[str, str]:
        """Download the best file of a release through the client API's signed file URL."""
        app_id = self._app_id(app.package_name)
        if not app_id:
            msg = f"Uptodown has no app for {app.package_name}"
            raise UptoDownAPKDownloadError(msg, url=app.download_source)
        release = self._find_release(app, app_id, version)
        file_id = str(release.get("fileID", ""))
        version_id = str((release.get("versionURL") or {}).get("versionID") or file_id)
        if variants := self._fetch_variants(app, app_id, version_id):
            file_id = max(variants, key=lambda v: VariantSorter.sorting_key(v["archs"], v["density"]))["file_id"]
        download = self._api_get(f"/apps/{app_id}/file/{file_id}/downloadUrl?update=0")
        download_url = cast("str", download.get("downloadURL", ""))
        if not download_url:
            msg = f"Uptodown returned no download URL for {app.app_name}"
            raise UptoDownAPKDownloadError(msg, url=app.download_source)
        # A split archive named `.apk` is detected later.
        extension = "xapk" if str(release.get("kindFile", "")).lower() in {"xapk", "apks", "apkm"} else "apk"
        file_name = f"{app.app_name}.{extension}"
        self._download(download_url, file_name)
        if version is None:
            app.resolved_version = release.get("version") or None
        return file_name, download_url

    def specific_version(self: Self, app: APP, version: str) -> tuple[str, str]:
        """Function to download the specified version of app from uptodown.

        :param app: Name of the application
        :param version: Version of the application to download
        :return: Version of downloaded apk
        """
        logger.debug("downloading specified version of app from uptodown.")
        return self._download_release(app, version)

    def latest_version(self: Self, app: APP, **kwargs: Any) -> tuple[str, str]:
        """Function to download the latest version of app from uptodown."""
        logger.debug("downloading latest version of app from uptodown.")
        return self._download_release(app, None)
