"""Regression tests for APKCube build selection and the reserved-tab download handoff."""

# ruff: noqa: PT009, PT027, SLF001

from contextlib import nullcontext
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Self, cast
from unittest import TestCase
from unittest.mock import MagicMock, patch

from pydoll.sync import Key

from src.downloader.apkcube import LATEST_BUTTON, PAGE_TIMEOUT, ApkCube
from src.exceptions import APKCubeAPKDownloadError, VersionNotFoundError

if TYPE_CHECKING:
    from src.app import APP
    from src.config import RevancedConfig

SOURCE = "https://apkcube.com/instagram/com.instagram.android"
OLD_VERSIONS = r"""
<script>self.__next_f.push([1,"[\"$\",\"$L61\",null,{\"packageName\":\"com.instagram.android\",
\"initial\":{\"apks\":[{\"apkId\":\"1\",\"versionName\":\"457.0.0.6.73\",\"versionCode\":386307610,\"arch\":\"arm64-v8a\"},
{\"apkId\":\"2\",\"versionName\":\"456.0.0.53.78\",\"versionCode\":386214574,\"arch\":\"arm64-v8a\"},
{\"apkId\":\"3\",\"versionName\":\"456.0.0.53.78\",\"versionCode\":386214534,\"arch\":\"armeabi-v7a\"}]}}]"])</script>
"""
FILE_URL = (
    "https://files.apkcf.com/f/abc?e=1&d=attachment%3B+filename%3D%22Instagram_456.0.0.53.78_apkcube.apks%22"
    "&t=application%2Foctet-stream"
)


class _Response(SimpleNamespace):
    """Response double with the fields read by `handle_request_response`."""

    status_code: int = 200
    text: str = ""


def _app(archs: list[str], codes: dict[str, Any] | None = None) -> APP:
    """Build the APP fields the APKCube downloader reads."""
    return cast(
        "APP",
        SimpleNamespace(
            app_name="INSTAGRAM",
            package_name="com.instagram.android",
            download_source=SOURCE,
            archs_to_build=archs,
            compatible_version_codes=codes or {},
        ),
    )


class ApkCubeDownloaderTests(TestCase):
    """Verify which APKCube build is requested and how its file is named."""

    def _downloader(self: Self) -> ApkCube:
        """Build a downloader without the full env config."""
        return ApkCube(cast("RevancedConfig", SimpleNamespace()))

    def test_targeted_version_code_is_requested_without_the_build_list(self: Self) -> None:
        """The build the patches target is requested directly for a single built arch."""
        app = _app(["arm64-v8a"], {"456.0.0.53.78": {"arm64-v8a": {386214534}}})
        downloader = self._downloader()
        with (
            patch("src.downloader.apkcube.make_request") as request,
            patch.object(ApkCube, "_file_url", return_value=FILE_URL) as file_url,
            patch.object(downloader, "_download") as download,
        ):
            file_name, url = downloader.specific_version(app, "456.0.0.53.78")

        request.assert_not_called()
        file_url.assert_called_once_with(
            f"{SOURCE}/download?target=version&vc=386214534&arch=arm64-v8a&langs=standard&dpi=all",
            targeted=True,
        )
        self.assertEqual(("INSTAGRAM.apks", FILE_URL), (file_name, url))
        download.assert_called_once_with(FILE_URL, "INSTAGRAM.apks")

    def test_build_list_picks_the_version_for_the_requested_arch(self: Self) -> None:
        """Without a targeted code, the old versions page names the build of the version."""
        with patch("src.downloader.apkcube.make_request", return_value=_Response(text=OLD_VERSIONS)):
            code = self._downloader()._version_code(_app(["armeabi-v7a"]), "456.0.0.53.78", "armeabi-v7a")

        self.assertEqual(386214534, code)

    def test_every_arch_requests_the_universal_build(self: Self) -> None:
        """An app built for several archs asks APKCube for its universal build."""
        self.assertEqual("universal", ApkCube._arch(_app(["arm64-v8a", "armeabi-v7a"])))
        self.assertEqual("arm64-v8a", ApkCube._arch(_app(["arm64-v8a"])))

    def test_missing_version_lets_the_fallback_try_another(self: Self) -> None:
        """A version APKCube does not hold raises the error the version fallback handles."""
        with (
            patch("src.downloader.apkcube.make_request", return_value=_Response(text=OLD_VERSIONS)),
            self.assertRaises(VersionNotFoundError),
        ):
            self._downloader().specific_version(_app(["arm64-v8a"]), "1.0")

    def test_a_different_version_handed_out_is_rejected(self: Self) -> None:
        """The file name names the version, so another build is never patched as the requested one."""
        app = _app(["arm64-v8a"], {"456.0.0.53.70": {"arm64-v8a": {386214000}}})
        with (
            patch.object(ApkCube, "_file_url", return_value=FILE_URL),
            self.assertRaises(VersionNotFoundError),
        ):
            self._downloader().specific_version(app, "456.0.0.53.70")

    def test_refused_download_names_the_reason(self: Self) -> None:
        """A refusal from the download request is reported instead of a missing-key error."""
        answers = iter([{"hold": {"requiredMs": 0}}, {"error": {"code": "FIREWALL_BLOCKED"}}])
        tab = MagicMock()
        tab.expect_response.side_effect = lambda *_, **__: nullcontext(SimpleNamespace(json=lambda: next(answers)))
        with (
            patch("src.downloader.apkcube.cdp_token", return_value="token"),
            patch("src.downloader.apkcube.reserved_tab", return_value=nullcontext(tab)),
            patch("src.downloader.apkcube._linger"),
            self.assertRaisesRegex(APKCubeAPKDownloadError, "FIREWALL_BLOCKED"),
        ):
            ApkCube._file_url(f"{SOURCE}/download?arch=universal", targeted=False)

        tab.go_to.assert_called_once_with(SOURCE, timeout=PAGE_TIMEOUT)
        tab.query.assert_any_call(LATEST_BUTTON, timeout=PAGE_TIMEOUT)
        tab.keyboard.down.assert_called_once_with(Key.SPACE)
        tab.keyboard.up.assert_called_once_with(Key.SPACE)

    def test_source_for_package_reads_the_app_slug(self: Self) -> None:
        """Discovery takes the app slug from the downloader page and needs a reserved-tab token."""
        page = r'<script>self.__next_f.push([1,"{\"href\":\"/instagram/com.instagram.android/download\"}"])</script>'
        with (
            patch("src.downloader.apkcube.cdp_token", return_value="token"),
            patch("src.downloader.apkcube.make_request", return_value=_Response(text=page)),
        ):
            self.assertEqual(SOURCE, ApkCube.source_for_package("com.instagram.android"))
        with patch("src.downloader.apkcube.cdp_token", return_value=""):
            self.assertEqual("", ApkCube.source_for_package("com.instagram.android"))
