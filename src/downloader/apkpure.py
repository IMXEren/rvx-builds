"""APK Pure Downloader Class."""

import json
import secrets
from typing import Any, Self, cast
from urllib.parse import urlsplit

from loguru import logger

from src.apks.version_sorter import VersionSorter
from src.downloader.download import Downloader
from src.downloader.sources import APK_PURE_DIRECT_URL, APK_PURE_URL, APK_PURE_VERSIONS_URL
from src.exceptions import APKPureAPKDownloadError, VersionNotFoundError
from src.utils import handle_request_response, request_timeout, session
lazy from src.app import APP

DEVICE_SDK = "34"
DEVICE_RELEASE = "14"
# Any other redirect means APKPure lacks the build.
FILE_HOST = "winudf.com"


class ApkPure(Downloader):
    """Files downloader."""

    @staticmethod
    def _versions(package_name: str, archs: list[str]) -> list[dict[str, Any]]:
        """Return APKPure's 20 newest builds of a package, newest first."""
        device = {
            "abis": archs,
            "android_id": secrets.token_hex(8),
            "os_ver": DEVICE_SDK,
            "os_ver_name": DEVICE_RELEASE,
            "platform": 1,
        }
        response = session.get(
            APK_PURE_VERSIONS_URL,
            params={"package_name": package_name, "hl": "en"},
            headers={
                "ual-access-businessid": "projecta",
                "ual-access-projecta": json.dumps({"device_info": device}),
                "Content-Type": "application/json",
            },
            timeout=request_timeout,
        )
        handle_request_response(response, APK_PURE_VERSIONS_URL)
        return cast("list[dict[str, Any]]", response.json().get("version_list") or [])

    @staticmethod
    def source_for_package(package_name: str) -> str:
        """Return the APKPure app source URL for a package, or an empty string when APKPure lacks it."""
        try:
            found = bool(ApkPure._versions(package_name, ["arm64-v8a"]))
        except Exception as exc:  # noqa: BLE001 - discovery moves on to the next mirror
            logger.debug(f"APKPure lookup failed for {package_name}: {exc}")
            return ""
        return APK_PURE_URL.format(package_name) if found else ""

    @staticmethod
    def _direct_builds(package_name: str, version: str, codes: set[int]) -> list[dict[str, Any]]:
        """Return builds of version codes the history no longer lists, from the direct file endpoint."""
        builds = []
        for code in sorted(codes):
            for kind in ("APK", "XAPK"):
                url = APK_PURE_DIRECT_URL.format(kind=kind, package=package_name, code=code)
                location = session.get(url, allow_redirects=False, timeout=request_timeout).headers.get("location")
                if location and (urlsplit(location).hostname or "").endswith(FILE_HOST):
                    builds.append(
                        {"version_name": version, "version_code": code, "asset": {"type": kind, "url": location}},
                    )
        return builds

    def _download_build(self: Self, app: APP, version: str | None) -> tuple[str, str]:
        """Download a version's build, preferring the targeted version codes, then a plain APK."""
        archs = app.archs_to_build or ["arm64-v8a", "armeabi-v7a", "x86_64", "x86"]
        builds = self._versions(app.package_name, archs)
        wanted = version if version is not None else (builds[0].get("version_name", "") if builds else "")
        builds = [b for b in builds if b.get("version_name") == wanted]
        codes = VersionSorter.target_codes(app.compatible_version_codes, wanted, archs)
        builds = [b for b in builds if int(b.get("version_code") or 0) in codes] or builds
        if not builds and codes:
            builds = self._direct_builds(app.package_name, wanted, codes)
        if not builds:
            msg = f"Unable to find {app.app_name} version {version or 'latest'} on APKPure"
            raise VersionNotFoundError(msg, url=app.download_source)
        build = min(builds, key=lambda b: b.get("asset", {}).get("type") != "APK")
        asset = build.get("asset", {})
        if not asset.get("url"):
            msg = f"APKPure returned no file for {app.app_name}"
            raise APKPureAPKDownloadError(msg, url=app.download_source)
        file_name = f"{app.app_name}.{'apk' if asset.get('type') == 'APK' else 'xapk'}"
        self._download(asset["url"], file_name)
        app.resolved_version = build.get("version_name") or None
        return file_name, cast("str", asset["url"])

    def specific_version(self: Self, app: APP, version: str) -> tuple[str, str]:
        """Download the specified version of an app from APKPure."""
        return self._download_build(app, version)

    def latest_version(self: Self, app: APP, **kwargs: Any) -> tuple[str, str]:
        """Download the latest version of an app from APKPure."""
        return self._download_build(app, None)
