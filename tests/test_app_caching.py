"""Regression tests for builder cache policy."""

# Cache policy bugs can silently reuse stale artifacts, so these tests exercise the public resource path.
# ruff: noqa: PT009

from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import TYPE_CHECKING, Self, cast
from unittest import TestCase
from unittest.mock import Mock, patch

from src.apks.version_fallback import VersionFallback
from src.app import APP

if TYPE_CHECKING:
    from src.config import RevancedConfig
    from src.downloader.download import Downloader


class AppVersionStateTests(TestCase):
    """Verify requested and resolved app versions remain separate."""

    def test_version_fallback_resolves_candidate_without_overwriting_latest_selector(self: Self) -> None:
        """A successful fallback candidate is concrete download state, not a replacement request selector."""
        app = cast(
            "APP",
            SimpleNamespace(app_name="YOUTUBE", app_version="latest", resolved_version=None),
        )
        downloader = cast(
            "Downloader",
            SimpleNamespace(download=Mock(return_value=("YOUTUBE.apk", "https://example.test/YOUTUBE.apk"))),
        )

        result = VersionFallback.run(app, downloader, ["20.51.39"])

        self.assertEqual(("YOUTUBE.apk", "https://example.test/YOUTUBE.apk"), result)
        self.assertEqual("latest", app.app_version)
        self.assertEqual("20.51.39", app.resolved_version)

    def test_direct_url_uses_downloaded_manifest_to_resolve_latest_selector(self: Self) -> None:
        """Direct APK URLs should get the same manifest fallback as source-backed downloads."""
        app = APP.__new__(APP)
        app.app_name = "YOUTUBE"
        app.app_version = "latest"
        app.resolved_version = None
        app.download_dl = "https://example.test/YOUTUBE.apk"
        config = cast("RevancedConfig", SimpleNamespace(temp_folder=Path("apks")))

        with (
            patch("src.downloader.download.Downloader.direct_download"),
            patch("src.app.get_apk_version", return_value="20.51.39") as apk_version,
        ):
            app.download_apk_for_patching(config, {}, Lock())

        self.assertEqual("latest", app.app_version)
        self.assertEqual("20.51.39", app.resolved_version)
        apk_version.assert_called_once_with(Path("apks/YOUTUBE.apk"))


class AppCachingTests(TestCase):
    """Verify DISABLE_CACHING prevents shared cache reads and writes."""

    def test_cli_temp_path_includes_patch_source_and_app_name(self: Self) -> None:
        """CLI temp directories should identify the patch source so parallel patch families stay isolated."""
        app = APP.__new__(APP)
        # The temp-path helper only needs these fields and should not require full app initialization.
        app.app_name = "YOUTUBE_MORPHE"
        app.effective_cli_argsf = "morphe-cli"
        app.patches_dl_list = ["https://github.com/MorpheApp/morphe-patches/releases/latest-prerelease"]
        config = cast(
            "RevancedConfig",
            SimpleNamespace(cli_temp_folder_name="patch-source-temporary-files", temp_folder=Path("apks")),
        )

        path = app.get_cli_temporary_files_path(config)

        self.assertEqual(
            str(Path("apks", "patch-source-temporary-files", "morpheapp.morphe.patches.youtube_morphe")),
            path,
        )

    def test_apk_cache_restores_resolved_version_for_latest_selector(self: Self) -> None:
        """A cached latest download must carry the concrete version discovered by the original source request."""
        app = APP.__new__(APP)
        app.app_name = "YOUTUBE"
        app.app_version = "latest"
        app.resolved_version = None
        app.download_dl = ""
        app.download_source = "https://example.test/youtube"
        app.package_name = "com.google.android.youtube"
        app.__dict__["_env_version_set"] = True
        app.compatible_versions = set()
        config = cast("RevancedConfig", SimpleNamespace(disable_caching=False))
        cache = {
            (app.download_source, "latest"): (
                "YOUTUBE.apk",
                "https://example.test/YOUTUBE.apk",
                "20.51.39",
            ),
        }

        app.download_apk_for_patching(config, cache, Lock())

        self.assertEqual("latest", app.app_version)
        self.assertEqual("20.51.39", app.resolved_version)
        self.assertEqual("YOUTUBE.apk", app.download_file_name)

    def test_disabled_resource_cache_downloads_and_leaves_shared_cache_unchanged(self: Self) -> None:
        """Disabled cache mode should resolve resources freshly without mutating shared cache state."""
        app = APP.__new__(APP)
        # The public resource downloader only needs these initialized fields for this cache-policy path.
        app.cli_dl = "https://example.test/resource.jar"
        app.patches_dl_list = []
        app.patch_bundles = []
        app.resource = {}
        config = cast(
            "RevancedConfig",
            SimpleNamespace(disable_caching=True, max_resource_workers=1),
        )
        cached_resources = {"https://example.test/resource.jar": ("cached-tag", "cached.jar")}

        with patch("src.app.APP.download", return_value=("v1.0.0", "resource.jar")) as download:
            app.download_patch_resources(config, cached_resources, Lock(), {}, Lock())

        download.assert_called_once_with("https://example.test/resource.jar", config, ".*jar")
        expected_cache = {"https://example.test/resource.jar": ("cached-tag", "cached.jar")}
        self.assertEqual(expected_cache, cached_resources)
        self.assertEqual({"file_name": "resource.jar", "version": "v1.0.0"}, app.resource["cli"])
