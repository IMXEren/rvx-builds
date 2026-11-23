"""Regression tests for APKPure's client API download path."""

# ruff: noqa: PT009, PT027

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Self, cast
from unittest import TestCase
from unittest.mock import patch

from src.downloader.apkpure import ApkPure
from src.exceptions import VersionNotFoundError

if TYPE_CHECKING:
    from src.app import APP
    from src.config import RevancedConfig


def _build(name: str, code: int, kind: str) -> dict[str, Any]:
    """Build one version list entry with its signed file URL."""
    return {"version_name": name, "version_code": str(code), "asset": {"type": kind, "url": f"https://f/{code}/{kind}"}}


BUILDS = [
    _build("2.0", 21, "XAPK"),
    _build("2.0", 20, "APK"),
    _build("1.0", 11, "XAPK"),
    _build("1.0", 10, "XAPK"),
]


def _app(codes: dict[str, Any] | None = None) -> APP:
    """Build the APP fields the APKPure downloader reads."""
    return cast(
        "APP",
        SimpleNamespace(
            app_name="EXAMPLE",
            package_name="com.example.app",
            download_source="https://apkpure.net/-/com.example.app",
            archs_to_build=["arm64-v8a"],
            compatible_version_codes=codes or {},
            resolved_version=None,
        ),
    )


class ApkPureDownloaderTests(TestCase):
    """Verify build selection from APKPure's version list."""

    def _download(self: Self, app: APP, version: str | None) -> tuple[str, Any]:
        """Run a download with the version list and the file download mocked."""
        downloader = ApkPure(cast("RevancedConfig", SimpleNamespace()))
        with (
            patch.object(ApkPure, "_versions", return_value=BUILDS),
            patch.object(downloader, "_download") as download,
        ):
            file_name = (
                downloader.latest_version(app) if version is None else downloader.specific_version(app, version)
            )[0]
        return file_name, download

    def test_latest_prefers_plain_apk_of_newest_version(self: Self) -> None:
        """Latest takes the newest version, and a plain APK over a split archive."""
        app = _app()
        file_name, download = self._download(app, None)

        self.assertEqual("EXAMPLE.apk", file_name)
        download.assert_called_once_with("https://f/20/APK", "EXAMPLE.apk")
        self.assertEqual("2.0", app.resolved_version)

    def test_specific_version_prefers_targeted_version_code(self: Self) -> None:
        """A version code the patches target wins over the other builds of the version."""
        file_name, download = self._download(_app({"1.0": {"arm64-v8a": {10}}}), "1.0")

        self.assertEqual("EXAMPLE.xapk", file_name)
        download.assert_called_once_with("https://f/10/XAPK", "EXAMPLE.xapk")

    def test_build_older_than_the_list_uses_the_direct_endpoint(self: Self) -> None:
        """A targeted code the 20-build list omits is still fetched from the direct file endpoint."""
        signed = "https://data.winudf.com/APK/x?filename=Example_0.9_APKPure.apk"
        redirect = SimpleNamespace(headers={"location": signed})
        with patch("src.downloader.apkpure.session.get", return_value=redirect) as get:
            file_name, download = self._download(_app({"0.9": {"arm64-v8a": {9}}}), "0.9")

        self.assertEqual("EXAMPLE.apk", file_name)
        download.assert_called_once_with(signed, "EXAMPLE.apk")
        self.assertIn("versionCode=9", get.call_args_list[0].args[0])

    def test_missing_version_lets_the_fallback_try_another(self: Self) -> None:
        """A version APKPure does not list raises the error the version fallback handles."""
        with self.assertRaises(VersionNotFoundError):
            self._download(_app(), "3.0")
