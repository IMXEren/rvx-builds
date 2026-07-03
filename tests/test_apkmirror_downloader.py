"""Regression tests for APKMirror Cloudflare fallback behavior."""

# APKMirror's challenge shape is external and unstable, so these tests pin the local fallback decisions.
# Private helper coverage is intentional because the public path would perform live APKMirror downloads.
# ruff: noqa: PT009, PT027, SLF001

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import TYPE_CHECKING, Self, cast
from unittest import TestCase
from unittest.mock import patch

from src.config import RevancedConfig
from src.downloader.apkmirror import ApkMirror
from src.downloader.sources import APK_MIRROR_BASE_URL
from src.exceptions import APKMirrorAPKDownloadError, ScrapingError
from src.utils import request_header

if TYPE_CHECKING:
    from src.app import APP


class _APKMirrorResponse(SimpleNamespace):
    """Small response double with only the fields used by the APKMirror source fetcher."""

    status_code: int
    text: str


def _config(temp_folder: Path) -> RevancedConfig:
    """Build the downloader config surface needed before patching out network downloads."""
    return cast(
        "RevancedConfig",
        # The browser download fallback needs these policy fields without constructing the full env config.
        SimpleNamespace(dry_run=False, temp_folder=temp_folder),
    )


class APKMirrorDownloaderTests(TestCase):
    """Verify APKMirror can fall back from HTTP scraping to CloakBrowser."""

    def test_default_user_agent_uses_valid_khtml_token(self: Self) -> None:
        """A typo in the shared UA made requests look like an impossible browser."""
        user_agent = request_header["User-Agent"]

        self.assertIn("(KHTML, like Gecko)", user_agent)
        self.assertNotIn("(HTML, like Gecko)", user_agent)

    def test_guess_release_url_constructs_correct_slug(self: Self) -> None:
        """The guessed URL should combine the app slug with the version in APKMirror's dash-separated format."""
        url = ApkMirror._guess_release_url(
            "https://www.apkmirror.com/apk/google-inc/youtube/youtube",
            "20.51.39",
        )
        self.assertEqual(
            "https://www.apkmirror.com/apk/google-inc/youtube/youtube-20-51-39-release/",
            url,
        )

    def test_guess_release_url_handles_no_trailing_slash(self: Self) -> None:
        """Sources without a trailing slash should still produce a correct release URL."""
        url = ApkMirror._guess_release_url(
            "https://www.apkmirror.com/apk/google-inc/youtube-music/youtube-music",
            "7.32.51",
        )
        self.assertEqual(
            "https://www.apkmirror.com/apk/google-inc/youtube-music/youtube-music-7-32-51-release/",
            url,
        )

    def test_find_specific_version_uses_guessed_url_when_valid(self: Self) -> None:
        """When the guessed release URL returns a valid variants page, skip the listing scrape entirely."""
        # Simulates a valid release page with the variants table marker.
        valid_release_page = """
            <div class="tab-pane noPadding">variants table here</div>
        """
        app = cast(
            "APP",
            SimpleNamespace(
                app_name="YOUTUBE",
                app_version="20.51.39",
                download_source="https://www.apkmirror.com/apk/google-inc/youtube/youtube",
                effective_cli_argsf="revanced-cli",
            ),
        )

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with patch.object(downloader, "_extract_source", return_value=valid_release_page) as extract:
                result = downloader._find_specific_version_page(app, "20.51.39")

        # Should return the guessed URL directly without scraping the listing page.
        self.assertEqual(
            "https://www.apkmirror.com/apk/google-inc/youtube/youtube-20-51-39-release/",
            result,
        )
        # Only one call to _extract_source (for the guessed URL), not two (listing page).
        extract.assert_called_once()

    def test_specific_version_uses_listing_url_for_release_slug(self: Self) -> None:
        """When the guessed URL fails, fall back to scraping the listing to find non-standard release slugs."""
        listing_page = """
            <div class="listWidget p-relative">
                <div class="appRow">
                    <span class="appRowTitle">X 11.95.1-release.0</span>
                    <a class="downloadLink" href="/apk/x-corp/twitter/x-11-95-1-release-0-release/">Download</a>
                </div>
            </div>
        """
        app = cast(
            "APP",
            # Only these APP fields are read while network and download methods are patched in this test.
            SimpleNamespace(
                app_name="TWITTER_PIKO",
                app_version="11.95.1-release-ripped.0",
                download_source="https://www.apkmirror.com/apk/x-corp/twitter/",
                effective_cli_argsf="morphe-cli",
            ),
        )

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            # The guessed URL fails (ScrapingError), then the listing page is scraped successfully.
            with (
                patch.object(
                    downloader,
                    "_extract_source",
                    side_effect=[
                        ScrapingError(
                            "404 not found",
                            response=_APKMirrorResponse(status_code=404, text="<html><h1>404</h1></html>"),
                        ),
                        listing_page,
                    ],
                ),
                patch.object(
                    downloader,
                    "get_download_page",
                    return_value="https://example.test/download/",
                ) as get_page,
                patch.object(
                    downloader,
                    "extract_download_link_for_app",
                    return_value=("TWITTER_PIKO.apkm", "https://example.test/download.php?id=1"),
                ),
            ):
                file_name, download_url = downloader.specific_version(app, "11.95.1-release-ripped.0")

        get_page.assert_called_once_with(
            "https://www.apkmirror.com/apk/x-corp/twitter/x-11-95-1-release-0-release/",
        )
        self.assertEqual("TWITTER_PIKO.apkm", file_name)
        self.assertEqual("https://example.test/download.php?id=1", download_url)

    def test_get_download_page_rejects_missing_release_table(self: Self) -> None:
        """A normal APKMirror 404 page should fail as a download error instead of a NoneType parser crash."""
        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with (
                patch.object(downloader, "_extract_source", return_value="<html><h1>404</h1></html>"),
                self.assertRaisesRegex(APKMirrorAPKDownloadError, "variants table"),
            ):
                downloader.get_download_page("https://www.apkmirror.com/apk/x-corp/twitter/missing/")

    def test_get_download_page_prefers_arm64_nodpi_apk_over_arm64_480dpi_apk(self: Self) -> None:
        """When multiple APK variants exist, the one with arm64-v8a+nodpi sorts higher than arm64-v8a+480dpi."""
        variant_page = """
            <div class="tab-pane noPadding">
                <div class="table-row headerFont">
                    <span class="apkm-badge">APK</span>
                    <a class="accent_color" href="/download/narrow/">Download</a>
                    Variant 1 APK arm64-v8a 480dpi Android 5.0+
                </div>
                <div class="table-row headerFont">
                    <span class="apkm-badge">APK</span>
                    <a class="accent_color" href="/download/best/">Download</a>
                    Variant 2 APK arm64-v8a nodpi Android 5.0+
                </div>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with patch.object(downloader, "_extract_source", return_value=variant_page):
                result = downloader.get_download_page("https://www.apkmirror.com/apk/google-inc/youtube/")

        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download/best/", result)
        self.assertEqual(downloader.apk_type, "APK")

    def test_get_download_page_falls_back_to_best_bundle_when_no_apk_variants(self: Self) -> None:
        """When no APK variants are present, the best BUNDLE variant (noarch) is selected."""
        variant_page = """
            <div class="tab-pane noPadding">
                <div class="table-row headerFont">
                    <span class="apkm-badge">BUNDLE</span>
                    <a class="accent_color" href="/download/bundle-noarch/">Download</a>
                    Variant 1 BUNDLE noarch Android 5.0+
                </div>
                <div class="table-row headerFont">
                    <span class="apkm-badge">BUNDLE</span>
                    <a class="accent_color" href="/download/bundle-x86/">Download</a>
                    Variant 2 BUNDLE x86 Android 5.0+
                </div>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with patch.object(downloader, "_extract_source", return_value=variant_page):
                result = downloader.get_download_page("https://www.apkmirror.com/apk/google-inc/youtube/")

        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download/bundle-noarch/", result)
        self.assertEqual(downloader.apk_type, "BUNDLE")

    def test_force_download_preserves_bundle_as_apkm_when_requested(self: Self) -> None:
        """Morphe patch sources need APKMirror bundles preserved as APKM instead of merged through APKEditor."""
        force_download_page = """
            <span class="apkm-badge">BUNDLE</span>
            <div class="tab-pane">
                <a href="/download.php?id=67890">Download APK Bundle</a>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            downloader.apk_type = "BUNDLE"
            with (
                patch.object(downloader, "_extract_source", return_value=force_download_page),
                patch.object(downloader, "_download") as download,
            ):
                file_name, download_url = downloader._extract_force_download_link(
                    "https://www.apkmirror.com/apk/example/app/download/",
                    "PIKO_TWITTER",
                    preserve_bundle=True,
                )

        self.assertEqual("PIKO_TWITTER.apkm", file_name)
        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download.php?id=67890", download_url)
        download.assert_called_once()

    def test_force_download_uses_link_text_over_badge(self: Self) -> None:
        """When the badge says BUNDLE but the link says 'Download APK', the file extension must be .apk."""
        force_download_page = """
            <span class="apkm-badge">BUNDLE</span>
            <div class="tab-pane">
                <a href="/download.php?id=12345">Download APK</a>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with (
                patch.object(downloader, "_extract_source", return_value=force_download_page),
                patch.object(downloader, "_download") as download,
            ):
                file_name, download_url = downloader._extract_force_download_link(
                    "https://www.apkmirror.com/apk/example/app/download/",
                    "YOUTUBE",
                )

        self.assertEqual("YOUTUBE.apk", file_name)
        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download.php?id=12345", download_url)
        download.assert_called_once()

    def test_extract_download_link_forwards_apkm_for_bundle_text(self: Self) -> None:
        """When listing-page link text says 'Download APK Bundle', extension forwarded must be 'apkm'."""
        listing_page = """
            <div class="center">
                <a href="/download/?key=abc123">Download APK Bundle</a>
                <a href="/other-link">Other</a>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            downloader.apk_type = "BUNDLE"
            with (
                patch.object(downloader, "_extract_source", return_value=listing_page),
                patch.object(
                    downloader,
                    "_extract_force_download_link",
                    return_value=("TEST.apkm", f"{APK_MIRROR_BASE_URL}/download.php?id=1"),
                ) as force_download,
            ):
                file_name, _download_url = downloader._extract_download_link(
                    "https://www.apkmirror.com/apk/example/app/download/",
                    "TEST",
                    preserve_bundle=True,
                )

        force_download.assert_called_once_with(
            f"{APK_MIRROR_BASE_URL}/download/?key=abc123",
            "TEST",
            preserve_bundle=True,
        )
        self.assertEqual(downloader.apk_type, "BUNDLE")
        self.assertEqual("TEST.apkm", file_name)

    def test_extract_download_link_forwards_apk_for_apk_text(self: Self) -> None:
        """When listing-page link text says 'Download APK', extension forwarded must be 'apk'."""
        listing_page = """
            <div class="center">
                <a href="/download/?key=def456">Download APK</a>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            downloader.apk_type = "BUNDLE"
            with (
                patch.object(downloader, "_extract_source", return_value=listing_page),
                patch.object(
                    downloader,
                    "_extract_force_download_link",
                    return_value=("TEST.apk", f"{APK_MIRROR_BASE_URL}/download.php?id=2"),
                ) as force_download,
            ):
                file_name, _download_url = downloader._extract_download_link(
                    "https://www.apkmirror.com/apk/example/app/download/",
                    "TEST",
                    preserve_bundle=False,
                )

        force_download.assert_called_once_with(
            f"{APK_MIRROR_BASE_URL}/download/?key=def456",
            "TEST",
            preserve_bundle=False,
        )
        self.assertEqual(downloader.apk_type, "APK")
        self.assertEqual("TEST.apk", file_name)
