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

from src.downloader.apkmirror import ApkMirror
from src.downloader.sources import APK_MIRROR_BASE_URL
from src.exceptions import APKMirrorAPKDownloadError, ScrapingError, VersionNotFoundError
from src.utils import request_header
lazy from src.config import RevancedConfig

if TYPE_CHECKING:
    from src.app import APP
    from src.utils import ResponseType


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

    def setUp(self: Self) -> None:
        """Keep Morphe's resolver offline unless a test answers it."""
        resolver = patch("src.downloader.apkmirror.resolve_download_page", return_value="")
        self.resolver = resolver.start()
        self.addCleanup(resolver.stop)

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

    def test_guess_release_url_strips_ripped_suffix(self: Self) -> None:
        """Piko's `release-ripped` versions map to APKMirror's upstream `release` slug."""
        url = ApkMirror._guess_release_url("https://www.apkmirror.com/apk/x-corp/twitter/x", "11.95.1-release-ripped.0")
        self.assertEqual("https://www.apkmirror.com/apk/x-corp/twitter/x-11-95-1-release-0-release/", url)

    def test_version_matches_title_requires_whole_version(self: Self) -> None:
        """A version must not match a longer version that merely starts with it."""
        self.assertTrue(ApkMirror._version_matches_title("445.0.0.0.37", "Instagram 445.0.0.0.37 alpha by Instagram"))
        self.assertFalse(ApkMirror._version_matches_title("445.0.0.0.3", "Instagram 445.0.0.0.37 alpha by Instagram"))
        self.assertTrue(ApkMirror._version_matches_title("11.95.1-release-ripped.0", "X 11.95.1-release.0"))

    def test_listing_urls_page_older_uploads_by_app_category(self: Self) -> None:
        """Older uploads are paged under `/uploads/` by the listing's category segment."""
        self.assertEqual(
            [
                "https://www.apkmirror.com/apk/instagram/instagram-instagram/instagram",
                "https://www.apkmirror.com/uploads/page/2/?appcategory=instagram-instagram",
                "https://www.apkmirror.com/uploads/page/3/?appcategory=instagram-instagram",
            ],
            ApkMirror._listing_urls("https://www.apkmirror.com/apk/instagram/instagram-instagram/instagram"),
        )

    def test_find_specific_version_searches_older_upload_pages(self: Self) -> None:
        """A version pushed off the app listing is still found on a later uploads page."""

        def listing(version: str, href: str) -> str:
            return f"""
                <div class="listWidget p-relative">
                    <div class="appRow">
                        <span class="appRowTitle">Instagram {version} by Instagram</span>
                        <a class="downloadLink" href="{href}">Download</a>
                    </div>
                </div>
            """

        app = cast(
            "APP",
            SimpleNamespace(
                app_name="INSTAGRAM",
                download_source="https://www.apkmirror.com/apk/instagram/instagram-instagram/instagram",
            ),
        )
        missing = ScrapingError(
            "404 not found",
            response=cast("ResponseType", _APKMirrorResponse(status_code=404, text="<html><h1>404</h1></html>")),
        )

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            pages = [missing, listing("456.0.0.53.78", "/new/"), listing("445.0.0.45.83", "/old/")]
            with patch.object(downloader, "_extract_source", side_effect=pages) as extract:
                result = downloader._find_specific_version_page(app, "445.0.0.45.83")

        self.assertEqual(f"{APK_MIRROR_BASE_URL}/old/", result)
        self.assertEqual(
            "https://www.apkmirror.com/uploads/page/2/?appcategory=instagram-instagram",
            extract.call_args.args[0],
        )

        # Pages past the last upload return 404, which ends the search as not found.
        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            pages = [missing, listing("456.0.0.53.78", "/new/"), missing]
            with (
                patch.object(downloader, "_extract_source", side_effect=pages),
                self.assertRaises(VersionNotFoundError),
            ):
                downloader._find_specific_version_page(app, "445.0.0.45.83")

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
                package_name="com.twitter.android",
                download_source="https://www.apkmirror.com/apk/x-corp/twitter/",
                effective_cli_argsf="morphe-cli",
                compatible_version_codes={"11.95.1-release-ripped.0": {"arm64-v8a": {311950100}, "x86": {311950101}}},
                archs_to_build=["arm64-v8a"],
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
                            response=cast(
                                "ResponseType",
                                _APKMirrorResponse(status_code=404, text="<html><h1>404</h1></html>"),
                            ),
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
            {311950100},
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
                <div class="headerFont table-row">
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

    def test_get_download_page_prefers_targeted_version_code_over_arch_and_density(self: Self) -> None:
        """Patches fingerprint one build, so its version code outranks the arch and density ordering."""

        def row(href: str, code: str, arch: str, dpi: str) -> str:
            # Mirrors APKMirror's variant cell markup, including the split-count badge and the date span.
            return f"""
                <div class="table-row headerFont">
                    <div class="table-cell rowheight addseparator expand pad dowrap-break-all">
                        <a class="accent_color" href="{href}">456.0.0.53.78</a>
                        <span class="apkm-badge success">BUNDLE</span>
                        <span class="apkm-badge success">1 S</span>
                        <br><span class="colorLightBlack">{code}</span>
                        <br><span class="colorLightBlack wrapText">November 18, 2026</span>
                    </div>
                    <div class="table-cell rowheight addseparator expand pad dowrap">{arch}</div>
                    <div class="table-cell rowheight addseparator expand pad dowrap">Android 9.0+</div>
                    <div class="table-cell rowheight addseparator expand pad dowrap">{dpi}</div>
                </div>
            """

        variant_page = f"""
            <div class="tab-pane noPadding">
                {row("/download/640dpi/", "386214528", "arm64-v8a", "640dpi")}
                {row("/download/targeted/", "386214534", "arm64-v8a", "160-480dpi")}
                {row("/download/short-code/", "42", "armeabi-v7a", "160-480dpi")}
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with patch.object(downloader, "_extract_source", return_value=variant_page):
                best = downloader.get_download_page("https://www.apkmirror.com/apk/instagram/")
                targeted = downloader.get_download_page("https://www.apkmirror.com/apk/instagram/", {386214534})
                short_code = downloader.get_download_page("https://www.apkmirror.com/apk/instagram/", {42})
                unmatched = downloader.get_download_page("https://www.apkmirror.com/apk/instagram/", {1, 2026})

        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download/640dpi/", best)
        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download/targeted/", targeted)
        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download/short-code/", short_code)
        self.assertEqual(best, unmatched)

    def test_get_download_page_handles_reversed_multi_class_ordering(self: Self) -> None:
        """CSS conjunction selector matches multi-class elements regardless of token order.

        The CSS selector ``.tab-pane.noPadding`` is an explicit AND predicate:
        it matches elements that have both ``tab-pane`` and ``noPadding``
        classes, independent of attribute ordering or extra class tokens.
        """
        variant_page = """
            <div class="noPadding tab-pane">
                <div class="headerFont table-row">
                    <span class="apkm-badge">APK</span>
                    <a class="accent_color" href="/download/best/">Download</a>
                    Variant 1 APK arm64-v8a nodpi Android 5.0+
                </div>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with patch.object(downloader, "_extract_source", return_value=variant_page):
                result = downloader.get_download_page(
                    "https://www.apkmirror.com/apk/google-inc/youtube/",
                )

        self.assertEqual(f"{APK_MIRROR_BASE_URL}/download/best/", result)
        self.assertEqual(downloader.apk_type, "APK")

    def test_force_download_raises_when_missing_tab_pane(self: Self) -> None:
        """Missing tab-pane container should raise APKMirrorAPKDownloadError instead of crashing on None."""
        page_without_tab_pane = """
            <div class="something-else">
                <a href="/download.php?id=1">Download</a>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with (
                patch.object(downloader, "_extract_source", return_value=page_without_tab_pane),
                self.assertRaisesRegex(APKMirrorAPKDownloadError, "Unable to extract force download for MISSING"),
            ):
                downloader._extract_force_download_link(
                    "https://www.apkmirror.com/apk/example/app/download/",
                    "MISSING",
                )

    def test_extract_download_link_raises_when_missing_center(self: Self) -> None:
        """Missing center container should raise APKMirrorAPKDownloadError instead of crashing on None."""
        page_without_center = """
            <div class="not-center">
                <a href="/download/?key=abc123">Download APK</a>
            </div>
        """

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with (
                patch.object(downloader, "_extract_source", return_value=page_without_center),
                self.assertRaisesRegex(APKMirrorAPKDownloadError, "Unable to extract link from MISSING version list"),
            ):
                downloader._extract_download_link(
                    "https://www.apkmirror.com/apk/example/app/download/",
                    "MISSING",
                    preserve_bundle=False,
                )

    def test_specific_version_leaves_version_unresolved_when_missing_appspec(self: Self) -> None:
        """Missing appspec metadata should preserve the requested selector and leave resolution to the caller."""
        page_with_variants = """
            <div class="tab-pane noPadding">
                <div class="table-row headerFont">
                    <span class="apkm-badge">APK</span>
                    <a class="accent_color" href="/download/best/">Download</a>
                    APK arm64-v8a nodpi Android 5.0+
                </div>
            </div>
        """
        app = cast(
            "APP",
            SimpleNamespace(
                app_name="YOUTUBE",
                app_version="latest",
                resolved_version=None,
                download_source="https://www.apkmirror.com/apk/google-inc/youtube/youtube",
                effective_cli_argsf="revanced-cli",
                compatible_version_codes={},
                archs_to_build=["arm64-v8a"],
            ),
        )

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with (
                patch.object(downloader, "_extract_source", return_value=page_with_variants),
                patch.object(
                    downloader,
                    "extract_download_link_for_app",
                    return_value=("YOUTUBE.apk", "https://example.test/download.php?id=1"),
                ) as extract_link,
            ):
                file_name, download_url = downloader.specific_version(app, "latest")

        self.assertEqual(app.app_version, "latest")
        self.assertIsNone(app.resolved_version)
        extract_link.assert_called_once()
        self.assertEqual("YOUTUBE.apk", file_name)
        self.assertEqual("https://example.test/download.php?id=1", download_url)

    def test_specific_latest_resolves_version_without_overwriting_selector(self: Self) -> None:
        """Source-discovered versions belong in resolved_version while app_version remains the request."""
        release_page = """
            <div class="tab-pane noPadding">
                <div class="table-row headerFont">
                    <span class="apkm-badge">APK</span>
                    <a class="accent_color" href="/download/best/">Download</a>
                    APK arm64-v8a nodpi Android 5.0+
                </div>
            </div>
            <div class="appspec-value">Version: 20.51.39 APK</div>
        """
        app = cast(
            "APP",
            SimpleNamespace(
                app_name="YOUTUBE",
                app_version="latest",
                resolved_version=None,
                download_source="https://www.apkmirror.com/apk/google-inc/youtube/youtube",
                effective_cli_argsf="revanced-cli",
                compatible_version_codes={},
                archs_to_build=["arm64-v8a"],
            ),
        )

        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with (
                patch.object(downloader, "_extract_source", return_value=release_page),
                patch.object(
                    downloader,
                    "extract_download_link_for_app",
                    return_value=("YOUTUBE.apk", "https://example.test/download.php?id=1"),
                ),
            ):
                downloader.specific_version(app, "latest")

        self.assertEqual("latest", app.app_version)
        self.assertEqual("20.51.39", app.resolved_version)

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

    @staticmethod
    def _twitter_app() -> APP:
        """Build the APP fields the resolver and latest-release paths read."""
        return cast(
            "APP",
            SimpleNamespace(
                app_name="TWITTER",
                package_name="com.twitter.android",
                download_source="https://www.apkmirror.com/apk/x-corp/twitter/x",
                compatible_version_codes={"12.43.0-prod.01": {"arm64-v8a": {312430001}}},
                archs_to_build=["arm64-v8a"],
            ),
        )

    def test_resolver_variant_page_resolves_to_its_release_page(self: Self) -> None:
        """A resolver answer on a variant page of the requested version is used as the release page."""
        self.resolver.return_value = (
            "https://www.apkmirror.com/apk/x-corp/twitter/x-12-43-0-prod-01-release/"
            "x-12-43-0-prod-01-3-android-apk-download/"
        )

        page = ApkMirror._resolver_release_page(self._twitter_app(), "12.43.0-prod.01")

        self.assertEqual("https://www.apkmirror.com/apk/x-corp/twitter/x-12-43-0-prod-01-release/", page)
        self.resolver.assert_called_once_with("com.twitter.android", "12.43.0-prod.01", "arm64-v8a", 312430001)

    def test_resolver_answer_for_another_version_or_listing_is_ignored(self: Self) -> None:
        """Only a release of the requested version inside the source listing is trusted."""
        for answer in (
            "https://www.apkmirror.com/apk/x-corp/twitter/x-12-45-1-prod-01-release/",
            "https://www.apkmirror.com/apk/x-corp/twitter-tv/x-12-43-0-prod-01-release/",
            "https://google.com/search?q=com.twitter.android",
        ):
            with self.subTest(answer=answer):
                self.resolver.return_value = answer
                self.assertEqual("", ApkMirror._resolver_release_page(self._twitter_app(), "12.43.0-prod.01"))

    def test_latest_version_uses_app_exists_release_in_source_listing(self: Self) -> None:
        """APKMirror's API names the latest stable release without scraping the listing."""
        entry = {
            "pname": "com.twitter.android",
            "exists": True,
            "release": {"version": "12.45.1-prod.01", "link": "/apk/x-corp/twitter/x-12-45-1-prod-01-release/"},
        }
        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with (
                patch("src.downloader.apkmirror.apkmirror_status_check", return_value={"data": [entry]}),
                patch.object(downloader, "specific_version", return_value=("TWITTER.apkm", "dl")) as specific,
                patch.object(downloader, "_extract_source") as extract_source,
            ):
                downloader.latest_version(self._twitter_app())

        specific.assert_called_once_with(
            self._twitter_app(),
            "latest",
            "https://www.apkmirror.com/apk/x-corp/twitter/x-12-45-1-prod-01-release/",
        )
        extract_source.assert_not_called()

    def test_latest_version_listing_takes_first_stable_row(self: Self) -> None:
        """The listing is newest first, so text order of the URLs must not pick an older release."""
        listing_page = """
            <div class="listWidget p-relative">
                <div class="appRow">
                    <span class="appRowTitle">X 12.46.0-alpha.01</span>
                    <a class="downloadLink" href="/apk/x-corp/twitter/x-12-46-0-alpha-01-release/">Download</a>
                </div>
                <div class="appRow">
                    <span class="appRowTitle">X 12.45.1-SECONDARY</span>
                    <a class="downloadLink" href="/apk/x-corp/twitter/x-12-45-1-secondary-release/">Download</a>
                </div>
                <div class="appRow">
                    <span class="appRowTitle">X 12.45.1-prod.01</span>
                    <a class="downloadLink" href="/apk/x-corp/twitter/x-12-45-1-prod-01-release/">Download</a>
                </div>
                <div class="appRow">
                    <span class="appRowTitle">X 12.9.0-prod.01</span>
                    <a class="downloadLink" href="/apk/x-corp/twitter/x-12-9-0-prod-01-release/">Download</a>
                </div>
            </div>
        """
        with TemporaryDirectory() as tmp_dir:
            downloader = ApkMirror(_config(Path(tmp_dir)))
            with (
                patch("src.downloader.apkmirror.apkmirror_status_check", return_value={"data": []}),
                patch.object(downloader, "_extract_source", return_value=listing_page),
                patch.object(downloader, "specific_version", return_value=("TWITTER.apkm", "dl")) as specific,
            ):
                downloader.latest_version(self._twitter_app())

        self.assertEqual(
            f"{APK_MIRROR_BASE_URL}/apk/x-corp/twitter/x-12-45-1-prod-01-release/",
            specific.call_args.args[2],
        )

    def test_source_for_package_strips_version_from_release_link(self: Self) -> None:
        """An unconfigured app gets the release slug prefix, so release URLs can still be guessed."""
        entry = {
            "pname": "com.twitter.android",
            "exists": True,
            "release": {"version": "12.45.1-prod.01", "link": "/apk/x-corp/twitter/x-12-45-1-prod-01-release/"},
        }
        with patch("src.downloader.apkmirror.apkmirror_status_check", return_value={"data": [entry]}):
            source = ApkMirror.source_for_package("com.twitter.android")

        self.assertEqual("https://www.apkmirror.com/apk/x-corp/twitter/x", source)
