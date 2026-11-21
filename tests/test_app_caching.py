"""Regression tests for builder cache policy."""

# Cache policy bugs can silently reuse stale artifacts, so these tests exercise the public resource path.
# ruff: noqa: PT009

from pathlib import Path
from threading import Lock
from types import SimpleNamespace
from typing import TYPE_CHECKING, Self, cast
from unittest import TestCase
from unittest.mock import Mock, patch

from src._bundle_selector import PatchBase
from src.apks.version_fallback import VersionFallback
from src.app import APP

if TYPE_CHECKING:
    from src.config import RevancedConfig
    from src.downloader.download import Downloader


class AppVersionStateTests(TestCase):
    """Verify requested and resolved app versions remain separate."""

    def test_legacy_patch_lists_use_app_base_with_warning(self: Self) -> None:
        """Old variables use the same app-only base as explicit selections."""
        config = Mock()
        config.global_patches_dl = "https://example.test/patches"
        config.global_cli_argsf = "revanced-cli"
        config.global_cli_lpargs = ""
        config.global_cli_pargs = ""
        values = {
            "SAMPLE_INCLUDE_PATCH": "universal-patch",
            "SAMPLE_EXCLUDE_PATCH": "2:disabled-patch",
        }
        config.env.str.side_effect = lambda key, default=None: values.get(key, default)
        config.env.list.side_effect = lambda _key, default=None: default
        config.env.bool.side_effect = lambda _key, default=None: default

        with patch("src.app.logger.warning") as warning:
            app = APP("sample", "com.example", cast("RevancedConfig", config))

        self.assertIs(PatchBase.APP, app.selection_base)
        self.assertEqual([(True, "universal-patch"), (False, "2:disabled-patch")], app.selection_overrides)
        warning.assert_called_once_with(
            "SAMPLE_INCLUDE_PATCH and SAMPLE_EXCLUDE_PATCH are deprecated. Use SAMPLE_PATCH_SELECTION.",
        )

        values["SAMPLE_INCLUDE_PATCH"] = ""
        values["SAMPLE_EXCLUDE_PATCH"] = ""
        with patch("src.app.logger.warning") as warning:
            app = APP("sample", "com.example", cast("RevancedConfig", config))
        self.assertIs(PatchBase.APP, app.selection_base)
        self.assertEqual([], app.selection_overrides)
        warning.assert_called_once()

        values["SAMPLE_PATCH_SELECTION"] = "NONE,+other-patch"
        with patch("src.app.logger.warning") as warning:
            app = APP("sample", "com.example", cast("RevancedConfig", config))
        self.assertIs(PatchBase.NONE, app.selection_base)
        self.assertEqual([(True, "other-patch")], app.selection_overrides)
        warning.assert_called_once()

        values.pop("SAMPLE_INCLUDE_PATCH")
        values.pop("SAMPLE_EXCLUDE_PATCH")
        values["SAMPLE_PATCH_SELECTION"] = "APP,+universal-patch"
        with patch("src.app.logger.warning") as warning:
            app = APP("sample", "com.example", cast("RevancedConfig", config))
        self.assertIs(PatchBase.APP, app.selection_base)
        self.assertEqual([(True, "universal-patch")], app.selection_overrides)
        warning.assert_not_called()

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

    def test_version_fallback_prefers_code_and_preserves_requested_version(self: Self) -> None:
        """Download order uses codes even when version names disagree."""
        app = cast(
            "APP",
            SimpleNamespace(
                app_name="twitter",
                app_version="12.41.0-prod.01",
                resolved_version=None,
                # The x86 code would win across all archs, but only the built arm64 codes rank versions.
                compatible_version_codes={
                    "12.41.0-prod.01": {"arm64-v8a": {501}, "x86": {1}},
                    "12.43.0-prod.01": {"arm64-v8a": {401}, "x86": {999}},
                },
                archs_to_build=["arm64-v8a"],
            ),
        )
        download = Mock(return_value=("twitter.apkm", "https://example.test"))
        downloader = cast("Downloader", SimpleNamespace(download=download))

        VersionFallback.run(app, downloader, ["12.43.0-prod.01", "12.41.0-prod.01"])

        download.assert_called_once_with("12.41.0-prod.01", app)
        self.assertEqual("12.41.0-prod.01", app.resolved_version)
        self.assertEqual("12.41.0-prod.01", app.app_version)

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

    def test_app_selection_changes_build_hash(self: Self) -> None:
        """Different base clauses must produce different build identities."""
        hashes = []
        for selection in ("DEFAULT,+universal-patch", "APP,+universal-patch"):
            app = APP.__new__(APP)
            app.app_version = "1.0"
            app.resolved_version = None
            app.patch_selection = selection
            with patch.object(APP, "compute_pb_norm_hashes", return_value=["hash-a"]):
                hashes.append(app.get_build_hash())

        self.assertNotEqual(hashes[0], hashes[1])

    def test_build_hash_preserves_bundle_order(self: Self) -> None:
        """Bundle positions must affect the build identity for scoped patch selection."""
        hashes = []
        for bundle_hashes in (["hash-a", "hash-b"], ["hash-b", "hash-a"]):
            app = APP.__new__(APP)
            app.app_version = "1.0"
            app.resolved_version = None
            app.patch_selection = "DEFAULT,-2:some-patch"
            with patch.object(APP, "compute_pb_norm_hashes", return_value=bundle_hashes):
                hashes.append(app.get_build_hash())

        self.assertNotEqual(hashes[0], hashes[1])

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
