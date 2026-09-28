"""Regression tests for Obtainium export metadata."""

# Obtainium support is optional but user-facing, so these tests pin URL and update identity behavior.
# unittest keeps this file aligned with the rest of the repository test suite.
# ruff: noqa: PT009

import json
import re
from contextlib import chdir
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import TYPE_CHECKING, Self, cast
from unittest import TestCase
from unittest.mock import patch

from src.app import APP
from src.metadata import GithubSourceMetadata, SourceMetadata  # noqa: F401
from src.utils import (
    generate_obtainium_export,
    generate_per_app_changelog,
    get_build_revision,
    write_per_app_changelogs,
)

if TYPE_CHECKING:
    from src.config import RevancedConfig


class _Env:
    """Small env double for only the config lookup used by Obtainium export."""

    def __init__(self: Self, github_repository: str) -> None:
        """Store the repository value so tests do not depend on real environment variables."""
        self.github_repository = github_repository

    def str(self: Self, key: str, default: str = "") -> str:
        """Return GitHub repository for export URL generation and defaults for unrelated keys."""
        if key == "GITHUB_REPOSITORY":
            return self.github_repository
        return default


def _app_with_patch_bundles(second_bundle_version: str) -> APP:
    """Build the minimum APP-shaped object needed to exercise output filename generation."""
    # APP initialization needs a full RevancedConfig, so allocate an instance and set only fields this method reads.
    app = APP.__new__(APP)
    app.app_name = "youtube"
    app.app_version = "20.47.62"
    app.patch_bundles = [
        {"file_name": "revanced.rvp", "version": "v1.0.0"},
        {"file_name": "extra.mpp", "version": second_bundle_version},
    ]
    # The method under test reads the private cache, so the test seeds it through __dict__ without lint noise.
    app.__dict__["_cached_output_file_name"] = ""
    return app


class ObtainiumExportTests(TestCase):
    """Verify Obtainium export data changes when app or patch metadata changes."""

    def test_output_file_name_includes_all_patch_bundle_versions(self: Self) -> None:
        """Patch-only updates in any bundle should change the release asset link Obtainium hashes."""
        first_name = _app_with_patch_bundles("v2.0.0").get_output_file_name()
        second_name = _app_with_patch_bundles("v3.0.0").get_output_file_name()

        self.assertIn("PatchVersionv1.0.0.v2.0.0", first_name)
        self.assertIn("PatchVersionv1.0.0.v3.0.0", second_name)
        self.assertNotEqual(first_name, second_name)
        self.assertIn("-BuildRevision0-BuildHash", first_name)

    def test_output_file_name_collapses_repeated_dots(self: Self) -> None:
        """Generated release asset names should match GitHub's uploaded asset names."""
        app = _app_with_patch_bundles("v2.0.0")
        app.app_version = "50.1.1..5001014"

        self.assertIn("Version50.1.1.5001014", app.get_output_file_name())

    def test_output_file_name_uses_resolved_version_without_changing_latest_selector(self: Self) -> None:
        """Release metadata should name the concrete download while retaining the requested selector."""
        app = _app_with_patch_bundles("v2.0.0")
        app.app_version = "latest"
        app.resolved_version = "20.51.39"

        self.assertIn("Version20.51.39", app.get_output_file_name())
        self.assertEqual("latest", app.app_version)

    def test_build_revision_resets_and_advances_only_for_changed_hash(self: Self) -> None:
        """The counter is scoped to the resolved upstream version, not the app lifetime."""
        self.assertEqual(get_build_revision(None, "20.1", "abc123"), 0)
        previous = {"app_version": "20.1", "build_revision": 3, "app_dump": {"build_hash": "abc123"}}
        self.assertEqual(get_build_revision(previous, "20.1", "abc123"), 3)
        self.assertEqual(get_build_revision(previous, "20.1", "def456"), 4)
        self.assertEqual(get_build_revision(previous, "20.2", "def456"), 0)
        legacy = {"app_version": "20.1", "app_dump": {"build_hash": "abc123"}}
        self.assertEqual(get_build_revision(legacy, "20.1", "abc123"), 0)
        self.assertEqual(get_build_revision(legacy, "20.1", "def456"), 1)

    def test_private_obtainium_version_extracts_separate_revision_and_hash(self: Self) -> None:
        """GitHub asset versions retain upstream version and add a per-version revision."""
        with TemporaryDirectory() as temp_dir, chdir(temp_dir):
            config = cast(
                "RevancedConfig",
                SimpleNamespace(
                    obtainium_export=True,
                    obtainium_gh_private_export="owner/index",
                    obtainium_github_tag="latest",
                    env=_Env("owner/repo"),
                ),
            )
            app = _app_with_patch_bundles("v2.0.0")
            app.build_revision = 2
            name = app.get_output_file_name()
            updates = {
                "youtube": {
                    "app_version": "20.47.62",
                    "output_file_name": name,
                    "app_dump": {"package_name": "com.google.android.youtube"},
                },
            }
            generate_obtainium_export(updates, config)
            app_config = json.loads(Path("obtainium_sources/json/youtube.json").read_text(encoding="utf_8"))
            settings = json.loads(app_config["apps"][0]["additionalSettings"])
            match = re.search(settings["versionExtractionRegEx"], name)
            self.assertIsNotNone(match)
            version = settings["matchGroupToUse"]
            for index, group in enumerate(cast("re.Match[str]", match).groups(), 1):
                version = version.replace(f"${index}", group)
            self.assertEqual(version, f"20.47.62-2+{app.build_hash[:6]}")

    def test_generate_obtainium_export_encodes_url_and_slugifies_html_name(self: Self) -> None:
        """Generated HTML should be safe to serve and should link to the exact encoded release asset."""
        with TemporaryDirectory() as temp_dir, chdir(temp_dir):
            # This config mirrors the runtime fields used by generate_obtainium_export without booting Env.
            config = cast(
                "RevancedConfig",
                SimpleNamespace(
                    obtainium_export=True,
                    obtainium_github_tag="release tag",
                    env=_Env("owner/repo"),
                ),
            )
            updates_info = {
                "YouTube Music": {
                    "app_version": "1<2",
                    "output_file_name": "My APK #1.apk",
                },
            }

            generate_obtainium_export(updates_info, config)
            html_path = Path(temp_dir, "obtainium_sources", "youtube.music.html")
            html_content = html_path.read_text(encoding="utf_8")

        self.assertIn(
            "https://github.com/owner/repo/releases/download/release%20tag/My%20APK%20%231.apk",
            html_content,
        )
        self.assertIn("1&lt;2", html_content)


class ChangelogGeneratorTests(TestCase):
    """Verify per-app changelog generator and URL helper functions."""

    def test_generate_per_app_changelog_with_changelogs(self: Self) -> None:
        """Changelog with GitHub-sourced tools should render full Markdown."""
        cli_meta = GithubSourceMetadata(
            name="revanced/revanced-cli",
            tag="v6.0.0",
            body="Release notes for CLI",
            html_url="https://github.com/revanced/revanced-cli/releases/tag/v6.0.0",
            published_at=datetime(2025, 1, 1, tzinfo=UTC),
        )
        patches_meta = GithubSourceMetadata(
            name="revanced/revanced-patches",
            tag="v5.0.0",
            body="Patch release notes",
            html_url="https://github.com/revanced/revanced-patches/releases/tag/v5.0.0",
            published_at=datetime(2025, 1, 2, tzinfo=UTC),
        )
        changelogs: dict[str, GithubSourceMetadata] = {
            "revanced/revanced-cli": cli_meta,
            "revanced/revanced-patches": patches_meta,
        }

        app_data = {
            "app_version": "20.47.62",
            "build_revision": 0,
            "output_file_name": "some.apk",
            "app_dump": {
                "build_hash": "abc123def456",
                "app_name": "YouTube",
                "cli_dl": "https://github.com/revanced/revanced-cli/releases/latest",
                "patches_dl_list": ["https://github.com/revanced/revanced-patches/releases/latest"],
            },
        }

        with patch.dict("src.utils.changelogs", changelogs, clear=True):
            result = generate_per_app_changelog(app_data)

        self.assertIn("**App Version:** 20.47.62\n**Build Revision:** 0\n**Build Hash:** abc123def456\n", result)
        self.assertIn("## revanced/revanced-patches", result)
        self.assertIn(
            "***Release Version: [v5.0.0](https://github.com/revanced/revanced-patches/releases/tag/v5.0.0)***",
            result,
        )
        self.assertIn("***Release Date: January 02, 2025, 00:00:00 UTC***", result)
        self.assertIn("Patch release notes", result)
        self.assertIn("## revanced/revanced-cli", result)
        self.assertIn(
            "***Release Version: [v6.0.0](https://github.com/revanced/revanced-cli/releases/tag/v6.0.0)***",
            result,
        )
        self.assertIn("***Release Date: January 01, 2025, 00:00:00 UTC***", result)
        self.assertIn("Release notes for CLI", result)
        # Patches is newer (2025-01-02) → appears first (latest first sort)
        self.assertLess(
            result.index("revanced/revanced-patches"),
            result.index("revanced/revanced-cli"),
        )

    def test_generate_per_app_changelog_missing_tool(self: Self) -> None:
        """Tools without changelog data should show 'Changelog not available'."""
        app_data = {
            "app_version": "1.0.0",
            "output_file_name": "some.apk",
            "app_dump": {
                "app_name": "TestApp",
                "cli_dl": "https://api.revanced.app/v5/patches.rvp",
                "patches_dl_list": [],
            },
        }

        with patch.dict("src.utils.changelogs", {}, clear=True):
            result = generate_per_app_changelog(app_data)

        self.assertEqual(result, "**App Version:** 1.0.0\n")

    def test_generate_per_app_changelog_multiple_patches(self: Self) -> None:
        """Multiple patch bundles should be numbered Patches-1, Patches-2, etc."""
        meta = GithubSourceMetadata(
            name="revanced/revanced-cli",
            tag="v6.0.0",
            body="Notes",
            html_url="https://github.com/revanced/revanced-cli/releases/tag/v6.0.0",
            published_at=datetime(2025, 1, 1, tzinfo=UTC),
        )

        app_data = {
            "app_version": "1.0.0",
            "output_file_name": "some.apk",
            "app_dump": {
                "app_name": "MultiPatch",
                "cli_dl": "https://github.com/revanced/revanced-cli/releases/latest",
                "patches_dl_list": [
                    "https://github.com/owner/patches-one/releases/latest",
                    "https://github.com/owner/patches-two/releases/latest",
                ],
            },
        }

        with patch.dict("src.utils.changelogs", {"revanced/revanced-cli": meta}, clear=True):
            result = generate_per_app_changelog(app_data)

        self.assertIn("## revanced/revanced-cli", result)
        self.assertNotIn("Patches-1", result)
        self.assertNotIn("Patches-2", result)

    def test_write_per_app_changelogs_creates_files(self: Self) -> None:
        """Create per-app changelog files for apps with output filenames."""
        with TemporaryDirectory() as temp_dir, chdir(temp_dir):
            meta = GithubSourceMetadata(
                name="revanced/revanced-cli",
                tag="v6.0.0",
                body="Notes",
                html_url="https://github.com/revanced/revanced-cli/releases/tag/v6.0.0",
                published_at=datetime(2025, 1, 1, tzinfo=UTC),
            )

            updates_info = {
                "YouTube": {
                    "app_version": "20.47.62",
                    "output_file_name": "some.apk",
                    "app_dump": {
                        "app_name": "YouTube",
                        "cli_dl": "https://github.com/revanced/revanced-cli/releases/latest",
                        "patches_dl_list": [],
                    },
                },
                "NoFileApp": {
                    "app_version": "1.0.0",
                    "app_dump": {"app_name": "NoFileApp"},
                },
            }

            # Ensure parent directory exists (mkdir in write_per_app_changelogs uses exist_ok without parents)
            Path(temp_dir, "obtainium_sources").mkdir(exist_ok=True)

            with patch.dict("src.utils.changelogs", {"revanced/revanced-cli": meta}, clear=True):
                write_per_app_changelogs(updates_info)

            output_path = Path(temp_dir, "obtainium_sources", "changelogs", "YouTube.md")
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf_8")
            self.assertIn("**App Version:** 20.47.62", content)

            # App without output_file_name should be skipped
            no_file_path = Path(temp_dir, "obtainium_sources", "changelogs", "NoFileApp.md")
            self.assertFalse(no_file_path.exists())
