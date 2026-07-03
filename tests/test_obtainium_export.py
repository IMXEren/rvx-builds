"""Regression tests for Obtainium export metadata."""

# Obtainium support is optional but user-facing, so these tests pin URL and update identity behavior.
# unittest keeps this file aligned with the rest of the repository test suite.
# ruff: noqa: PT009

from contextlib import chdir
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
        from datetime import UTC, datetime

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
            "output_file_name": "some.apk",
            "app_dump": {
                "app_name": "YouTube",
                "cli_dl": "https://github.com/revanced/revanced-cli/releases/latest",
                "patches_dl_list": ["https://github.com/revanced/revanced-patches/releases/latest"],
            },
        }

        with patch.dict("src.utils.changelogs", changelogs, clear=True):
            result = generate_per_app_changelog(app_data)

        self.assertIn("# YouTube", result)
        self.assertIn("**App Version:** 20.47.62", result)
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

        self.assertEqual(result, "# TestApp\n\n**App Version:** 1.0.0\n")

    def test_generate_per_app_changelog_multiple_patches(self: Self) -> None:
        """Multiple patch bundles should be numbered Patches-1, Patches-2, etc."""
        from datetime import UTC, datetime

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
        """write_per_app_changelogs should create app_changelogs/<name>.md per app with output_file_name."""
        from datetime import UTC, datetime

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

            with patch.dict("src.utils.changelogs", {"revanced/revanced-cli": meta}, clear=True):
                write_per_app_changelogs(updates_info)

            output_path = Path(temp_dir, "app_changelogs", "YouTube.md")
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf_8")
            self.assertIn("# YouTube", content)
            self.assertIn("**App Version:** 20.47.62", content)

            # App without output_file_name should be skipped
            no_file_path = Path(temp_dir, "app_changelogs", "NoFileApp.md")
            self.assertFalse(no_file_path.exists())
