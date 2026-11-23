"""APKCube Downloader."""

import json
import random
import re
import time
from typing import Any, Self
from urllib.parse import quote, unquote

from loguru import logger
from pydoll.commands.page_commands import PageCommands
from pydoll.exceptions import PydollException, WaitTimeout
from pydoll.sync import Key, SyncError, Tab, WebElement

from src.apks.version_sorter import VersionSorter
from src.downloader.download import Downloader
from src.downloader.sources import APK_CUBE_BASE_URL
from src.exceptions import APKCubeAPKDownloadError, ScrapingError, VersionNotFoundError
from src.prowl.cdp import ProwlTabError, cdp_token, reserved_tab
from src.utils import handle_request_response, make_request, request_header
lazy from src.app import APP

# Other archs and multi-arch apps get the universal build.
APK_CUBE_ARCHS = ("arm64-v8a", "armeabi-v7a")
UNIVERSAL_ARCH = "universal"
FILE_EXTENSIONS = ("apk", "apks", "xapk", "apkm")
PAGE_TIMEOUT = 60
STEP_TIMEOUT = 60
# Turnstile after the hold can take minutes to clear.
VERIFY_TIMEOUT = 300
# The check fails when released over 600 ms after it fills.
HOLD_MARGIN = 0.25
# Visitor-like pauses in seconds: on the app page, before the click, before the hold.
APP_PAGE_DWELL = (3.0, 6.0)
CLICK_DWELL = (2.0, 5.0)
HOLD_DELAY = (0.4, 1.2)
CLICK_WAIT = 10
CLICK_ATTEMPTS = 3
# Renders after the newest build's button, which a targeted download must not take.
TARGETED_BUTTON = "//button[contains(normalize-space(.), 'Download this build')]"
LATEST_BUTTON = (
    "(//button | //a)[starts-with(normalize-space(.), 'Download APK')"
    " or starts-with(normalize-space(.), 'Download XAPK')]"
)
HOLD_BUTTON = "//button[contains(normalize-space(.), 'Hold to verify')]"


def _linger(bounds: tuple[float, float]) -> None:
    """Pause for a random time within the bounds."""
    time.sleep(random.uniform(*bounds))  # noqa: S311 - pacing, not security


def _click_download(tab: Tab, button: WebElement) -> int:
    """Click the download button until the page asks for a hold token, and return the hold time it needs."""
    attempt = 1
    while True:
        button.scroll_into_view()
        try:
            with tab.expect_response(re.compile("/download-token"), timeout=CLICK_WAIT) as token_response:
                button.click(humanize=True)
            return int(token_response.json()["hold"]["requiredMs"])
        except WaitTimeout:
            if attempt == CLICK_ATTEMPTS:
                raise
            attempt += 1


class ApkCube(Downloader):
    """Files downloader."""

    @staticmethod
    def source_for_package(package_name: str) -> str:
        """Return the APKCube app source URL for a package, or an empty string when APKCube lacks it."""
        if not cdp_token():
            return ""
        url = f"{APK_CUBE_BASE_URL}/apk-downloader?url={quote(package_name)}"
        try:
            response = make_request(url, headers=request_header)
            handle_request_response(response, url)
        except ScrapingError as exc:
            logger.debug(f"APKCube lookup failed for {package_name}: {exc}")
            return ""
        # The flight payload escapes quotes.
        page = response.text.replace('\\"', '"')
        match = re.search(rf'href":"/([a-z0-9-]+)/{re.escape(package_name)}/download', page)
        return f"{APK_CUBE_BASE_URL}/{match.group(1)}/{package_name}" if match else ""

    @staticmethod
    def _builds(app: APP) -> list[dict[str, Any]]:
        """Return the builds APKCube holds for the app, newest first, from its old versions page."""
        url = f"{app.download_source.rstrip('/')}/old-versions"
        response = make_request(url, headers=request_header)
        handle_request_response(response, url)
        page = response.text.replace('\\"', '"')
        start = page.find('"initial":{"apks":')
        if start < 0:
            msg = f"Unable to find the APKCube build list for {app.app_name}"
            raise APKCubeAPKDownloadError(msg, url=url)
        initial, _ = json.JSONDecoder().raw_decode(page, start + len('"initial":'))
        return list(initial.get("apks") or [])

    @staticmethod
    def _arch(app: APP) -> str:
        """Return the build architecture to request from APKCube."""
        archs = app.archs_to_build
        return archs[0] if len(archs) == 1 and archs[0] in APK_CUBE_ARCHS else UNIVERSAL_ARCH

    def _version_code(self: Self, app: APP, version: str, arch: str) -> int:
        """Return the build of a version to request, preferring the code the patches target."""
        codes = VersionSorter.target_codes(app.compatible_version_codes, version, [arch])
        if len(codes) == 1:
            return next(iter(codes))
        builds = [b for b in self._builds(app) if b.get("versionName") == version]
        build = next((b for b in builds if b.get("arch") == arch), builds[0] if builds else None)
        if build is None:
            msg = f"Unable to find {app.app_name} version {version} on APKCube"
            raise VersionNotFoundError(msg, url=app.download_source)
        return int(build["versionCode"])

    @staticmethod
    def _file_url(page_url: str, *, targeted: bool) -> str:
        """Drive the download page in a Prowl reserved tab and return the signed file URL it is given."""
        token = cdp_token()
        if not token:
            msg = "APKCube downloads need a Prowl reserved tab. Set PROWL_CDP_TOKEN_FILE."
            raise APKCubeAPKDownloadError(msg, url=page_url)
        try:
            with reserved_tab(token) as tab:
                # Arrive from the app page like a visitor.
                app_page = page_url.split("/download?", 1)[0]
                tab.go_to(app_page, timeout=PAGE_TIMEOUT)
                _linger(APP_PAGE_DWELL)
                tab.execute_command(PageCommands.navigate(page_url, referrer=app_page))
                button = tab.query(TARGETED_BUTTON if targeted else LATEST_BUTTON, timeout=PAGE_TIMEOUT)
                _linger(CLICK_DWELL)
                required_ms = _click_download(tab, button)
                tab.query(HOLD_BUTTON, timeout=STEP_TIMEOUT).focus()
                _linger(HOLD_DELAY)
                with tab.expect_response(re.compile("/api/downloads/request"), timeout=VERIFY_TIMEOUT) as download:
                    tab.keyboard.down(Key.SPACE)
                    time.sleep(required_ms / 1000 + HOLD_MARGIN)
                    tab.keyboard.up(Key.SPACE)
                answer = download.json()
        except (ProwlTabError, PydollException, SyncError, KeyError, TypeError) as exc:
            msg = f"APKCube download page did not hand out a file: {exc}"
            raise APKCubeAPKDownloadError(msg, url=page_url) from exc
        if not isinstance(answer, dict) or not answer.get("url"):
            # Refusals carry a reason such as `FIREWALL_BLOCKED`.
            msg = f"APKCube refused the download: {answer}"
            raise APKCubeAPKDownloadError(msg, url=page_url)
        return str(answer["url"])

    def _download_build(self: Self, app: APP, version: str | None) -> tuple[str, str]:
        """Download a build through APKCube's download page."""
        arch = self._arch(app)
        target = f"target=version&vc={self._version_code(app, version, arch)}&" if version else ""
        page_url = f"{app.download_source.rstrip('/')}/download?{target}arch={arch}&langs=standard&dpi=all"
        logger.info(f"Downloading {app.app_name} from {page_url}")
        file_url = self._file_url(page_url, targeted=bool(version))
        # The URL names the file, like `Instagram_456.0.0.53.78_apkcube.apks`.
        file_name = unquote(file_url).rsplit('filename="', 1)[-1].split('"', 1)[0]
        if version and f"_{version}_" not in file_name:
            msg = f"APKCube handed out {file_name} instead of {app.app_name} {version}"
            raise VersionNotFoundError(msg, url=page_url)
        extension = file_name.rsplit(".", 1)[-1].lower()
        local_name = f"{app.app_name}.{extension if extension in FILE_EXTENSIONS else 'apk'}"
        self._download(file_url, local_name)
        return local_name, file_url

    def specific_version(self: Self, app: APP, version: str) -> tuple[str, str]:
        """Download the specified version of an app from APKCube."""
        return self._download_build(app, version)

    def latest_version(self: Self, app: APP, **kwargs: Any) -> tuple[str, str]:
        """Download the latest version of an app from APKCube."""
        return self._download_build(app, None)
