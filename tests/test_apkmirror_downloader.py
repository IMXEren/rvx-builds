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
                    side_effect=[ScrapingError("404 not found"), listing_page],
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

    def test_force_download_preserves_bundle_as_apkm_when_requested(self: Self) -> None:
        """Morphe patch sources need APKMirror bundles preserved as APKM instead of merged through APKEditor."""
        force_download_page = """
            <span class="apkm-badge">BUNDLE</span>
            <div class="tab-pane">
                <a href="/download.php?id=67890">Download APKM</a>
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
                    "PIKO_TWITTER",
                    preserve_bundle=True,
                )

        self.assertEqual("PIKO_TWITTER.apkm", file_name)
        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download.php?id=67890", download_url)
        download.assert_called_once()
