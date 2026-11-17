"""Regression tests for parsing ReVanced-family list-patches output."""

# These samples mirror the three live CLI dialects the builder supports today.
# unittest keeps this parser coverage aligned with the existing project test style.
# ruff: noqa: PT009, SLF001

from contextlib import chdir
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Self, cast
from unittest import TestCase
from unittest.mock import patch

from src.cli_args import merge_cli_arg_maps
from src.patches import Patches
from src.patches_gen import convert_command_output_to_json, parse_text_to_json

if TYPE_CHECKING:
    from src.app import APP

EXPECTED_REVANCED_PATCH_COUNT = 2
EXPECTED_REVANCED_OPTION_COUNT = 2

REVANCED_SAMPLE = """INFO: Name: Spoof build info
Description: Spoofs the device build information.
Enabled: false
Options:
\tName: Board
\tDescription: The name of the underlying board.
\tRequired: false
\t
\tType: kotlin.String
\t
\tName: Bootloader
\tDescription: The system bootloader version.
\tRequired: false
\tDefault: unknown
\tType: kotlin.String
Compatible packages:
\tPackage name: com.google.android.youtube
\tCompatible versions:
\t\t20.47.62

Name: Spoof client
Description: Spoofs the Reddit OAuth client.
Enabled: true
Options:
\tName: Application client ID
\tDescription: The Reddit OAuth application client ID.
\tRequired: true
\tDefault: redreader-client-id
\tPossible values:
\t\tredreader-client-id (RedReader)
\tType: kotlin.String
Compatible packages:
\tPackage name: com.onelouder.baconreader
"""

MORPHE_SAMPLE = """INFO: Name: Custom branding
Description: Adds custom branding.
Enabled: false
Options:
\tTitle: Custom icon
\tDescription: Folder path to a custom icon.
\t
\tThe folder must contain density-specific resources:
\t- mipmap-mdpi
\tRequired: false
\tKey: customIcon
\tType: kotlin.String
Compatible packages:
\tPackage name: com.google.android.youtube
\tCompatible versions:
\t\t20.47.62
"""

ANDDEA_SAMPLE = """INFO: Name: GmsCore support
Description: Adds GmsCore support.
Enabled: true
Options:
\tTitle: GmsCore vendor group ID
\tDescription: The package name of the GmsCore vendor.
\tRequired: true
\tKey: gmsCoreVendorGroupId
\tDefault: app.revanced
\tPossible values:
\t\tapp.revanced
\t\tcom.google
\t\tcom.mgoogle
\tType: kotlin.String
Compatible packages:
\tPackage name: com.google.android.youtube
\tCompatible versions:
\t\t20.47.62
\t\t20.48.46
"""


def _patch_by_name(patches: list[dict[Any, Any]], name: str) -> dict[Any, Any]:
    """Find patches by name so tests stay focused on parser behavior instead of list ordering."""
    return next(patch for patch in patches if patch["name"] == name)


class PatchesGenParserTests(TestCase):
    """Verify parser compatibility with current ReVanced, Morphe, and Anddea output shapes."""

    def test_recommended_version_uses_newest_compatible_version(self: Self) -> None:
        """Compatible versions may be listed newest-to-oldest, so the builder must not pick the final entry."""
        selected_version = Patches.select_recommended_version(["8.47.56", "7.29.52"])

        self.assertEqual("8.47.56", selected_version)

    def test_recommended_version_falls_back_to_first_unparseable_version(self: Self) -> None:
        """Non-standard app versions should stay deterministic instead of crashing patch metadata parsing."""
        selected_version = Patches.select_recommended_version(["beta-current", "beta-old"])

        self.assertEqual("beta-current", selected_version)

    def test_recommended_version_handles_piko_suffix_versions(self: Self) -> None:
        """Piko can publish channel-suffixed app versions, so numeric groups should still decide newest support."""
        selected_version = Patches.select_recommended_version(
            [
                "11.80.0-alpha.1",
                "11.82.0-beta.1",
                "11.81.0-release.0",
                "11.95.1-release-ripped.0",
            ],
        )

        self.assertEqual("11.95.1-release-ripped.0", selected_version)

    def test_revanced_indented_option_names_do_not_split_patch_sections(self: Self) -> None:
        """ReVanced v6 option `Name:` fields should not become fake patch sections."""
        patches = parse_text_to_json(REVANCED_SAMPLE)
        patch_names = {patch["name"] for patch in patches}
        build_info = _patch_by_name(patches, "Spoof build info")
        spoof_client = _patch_by_name(patches, "Spoof client")

        self.assertEqual(EXPECTED_REVANCED_PATCH_COUNT, len(patches))
        self.assertNotIn("Board", patch_names)
        self.assertEqual(EXPECTED_REVANCED_OPTION_COUNT, len(build_info["options"]))
        self.assertEqual("Application client ID", spoof_client["options"][0]["key"])
        self.assertEqual(["redreader-client-id (RedReader)"], spoof_client["options"][0]["possible_values"])
        self.assertFalse(build_info["use"])
        self.assertTrue(spoof_client["use"])
        owner = Patches.__new__(Patches)
        self.assertFalse(owner._create_patch_dict(build_info, "com.google.android.youtube", "20.47.62").get("enabled"))
        self.assertTrue(owner._create_patch_dict(spoof_client, "com.onelouder.baconreader", "all").get("enabled"))

    def test_morphe_title_key_options_preserve_multiline_description(self: Self) -> None:
        """Morphe options expose a title plus explicit key and can include multiline descriptions."""
        patches = parse_text_to_json(MORPHE_SAMPLE)
        custom_branding = _patch_by_name(patches, "Custom branding")
        option = custom_branding["options"][0]

        self.assertEqual("Custom icon", option["name"])
        self.assertEqual("customIcon", option["key"])
        self.assertIn("- mipmap-mdpi", option["description"])
        self.assertEqual(["20.47.62"], custom_branding["compatiblePackages"][0]["versions"])

    def test_anddea_keyed_options_preserve_possible_values(self: Self) -> None:
        """Anddea options use Morphe-style keys and line-based possible values."""
        patches = parse_text_to_json(ANDDEA_SAMPLE)
        gms_core = _patch_by_name(patches, "GmsCore support")
        option = gms_core["options"][0]

        self.assertEqual("GmsCore vendor group ID", option["name"])
        self.assertEqual("gmsCoreVendorGroupId", option["key"])
        self.assertEqual(["app.revanced", "com.google", "com.mgoogle"], option["possible_values"])
        self.assertEqual(["20.47.62", "20.48.46"], gms_core["compatiblePackages"][0]["versions"])

    def test_morphe_version_codes_rank_versions_before_names(self: Self) -> None:
        """Collect codes per version and stop parsing versions at the code section."""
        sample = """Name: Example
Compatible packages:
\tPackage name: com.twitter.android
\tCompatible versions:
\t\t12.41.0-prod.01
\t\t12.43.0-prod.01
\tVersion codes:
\t\t12.41.0-prod.01: ARM64_V8A=500 X86=501
\t\t12.43.0-prod.01: ARM64_V8A=400 X86=401
"""
        package = parse_text_to_json(sample)[0]["compatiblePackages"][0]
        self.assertEqual(["12.41.0-prod.01", "12.43.0-prod.01"], package["versions"])
        self.assertEqual({"12.41.0-prod.01": 501, "12.43.0-prod.01": 401}, package["version_codes"])

        app = cast("APP", SimpleNamespace(
            app_name="twitter", package_name="com.twitter.android",
            compatible_versions=set(), compatible_version_codes={},
        ))
        patches = Patches.__new__(Patches)
        patches.patches_dict = {"twitter": []}
        patches._process_app_specific_patch(
            {"name": "Example", "description": "", "options": [], "compatiblePackages": [package]}, app,
        )
        self.assertEqual(["12.41.0-prod.01", "12.43.0-prod.01"], Patches.get_compatible_versions(app))

    def test_mixed_piko_versions_choose_newx(self: Self) -> None:
        """A legacy patch's valid SemVer must not outrank a newer prod.01 version."""
        app = cast("APP", SimpleNamespace(
            app_name="twitter", package_name="com.twitter.android",
            compatible_versions=set(), compatible_version_codes={}, app_version=None,
        ))
        patches = Patches.__new__(Patches)
        patches.patches_dict = {"twitter": []}
        for name, version in (("Legacy", "12.19.1-release.0"), ("NewX", "12.43.0-prod.01")):
            patches._process_app_specific_patch(
                {"name": name, "description": "", "options": [],
                 "compatiblePackages": [{"name": app.package_name, "versions": [version]}]}, app,
            )
        self.assertEqual(["12.43.0-prod.01", "12.19.1-release.0"], Patches.get_compatible_versions(app))
        patches.get_app_configs(app)
        self.assertEqual("12.43.0-prod.01", app.app_version)

    def test_morphe_list_patches_does_not_emit_patch_temp_path(self: Self) -> None:
        """Morphe temp isolation is patch-only; list-patches should not receive patch temp-path flags."""
        list_patch_args, _ = merge_cli_arg_maps("morphe-cli", ("", ""))

        with (
            TemporaryDirectory() as temp_dir,
            chdir(temp_dir),
            patch("src.patches_gen.run_command_and_capture_output", return_value=MORPHE_SAMPLE) as run_command,
        ):
            convert_command_output_to_json("morphe-cli.jar", "patches.mpp", list_patch_args)

        command = run_command.call_args.args[0]
        self.assertNotIn("-t", command)
        self.assertNotIn("tmp/youtube", command)
