"""Tests for per-bundle patch tracking in CLI arg generation.

The Morphe CLI scopes -e/-d/-O flags to the preceding -p bundle.
This requires grouping patches by their source bundle in the CLI args
instead of emitting all -p flags first then all patches flatly.
"""

# ruff: noqa: PT009, SLF001, D102

from typing import Self
from unittest import TestCase
from unittest.mock import MagicMock

from src.parser import Parser
from src.structs.patches import PatchInfo


def _make_patch(name: str, bundle_file: str | None = None) -> PatchInfo:
    """Create a minimal PatchInfo for testing include/exclude/bundle tracking."""
    return PatchInfo(
        name=name,
        description="test patch",
        app="com.test.app",
        version="1.0.0",
        options=[],
        bundle_file=bundle_file,
    )


def _make_parser() -> Parser:
    """Create a Parser with minimal mocking and default revanced-cli args."""
    parser = Parser(MagicMock(), MagicMock())
    parser._enable_arg = ["-e"]
    parser._disable_arg = ["-d"]
    parser._options_arg = ["-O"]
    return parser


class BundleTrackingIncludeTests(TestCase):
    """Tests for include() populating _BUNDLE_PATCHES."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()

    def test_include_adds_enable_entry_to_correct_bundle(self: Self) -> None:
        """include() should prepend -e entry to the matching bundle in _BUNDLE_PATCHES."""
        patch = _make_patch("Test patch", bundle_file="bundle1.rvp")

        self.parser.include(patch, [])

        self.assertIn("bundle1.rvp", self.parser._BUNDLE_PATCHES)
        self.assertEqual(
            [["-e"], "Test patch"],
            self.parser._BUNDLE_PATCHES["bundle1.rvp"],
        )

    def test_include_without_bundle_file_does_not_populate_bundle_patches(self: Self) -> None:
        """Patches without bundle_file should not appear in _BUNDLE_PATCHES (single-bundle compat)."""
        patch = _make_patch("No bundle", bundle_file=None)

        self.parser.include(patch, [])

        self.assertFalse(self.parser._BUNDLE_PATCHES)

    def test_multiple_includes_from_same_bundle_accumulate(self: Self) -> None:
        """Multiple include() calls from the same bundle should accumulate in that bundle's list."""
        patch_a = _make_patch("Patch A", bundle_file="patches.rvp")
        patch_b = _make_patch("Patch B", bundle_file="patches.rvp")

        self.parser.include(patch_a, [])
        self.parser.include(patch_b, [])

        # include prepends, so Patch B comes first, then Patch A
        self.assertEqual(
            [["-e"], "Patch B", ["-e"], "Patch A"],
            self.parser._BUNDLE_PATCHES["patches.rvp"],
        )

    def test_patches_from_different_bundles_are_separated(self: Self) -> None:
        """Patches from different bundles should go into separate _BUNDLE_PATCHES entries."""
        p1 = _make_patch("Bundle1 patch", bundle_file="b1.rvp")
        p2 = _make_patch("Bundle2 patch", bundle_file="b2.rvp")

        self.parser.include(p1, [])
        self.parser.include(p2, [])

        self.assertEqual(2, len(self.parser._BUNDLE_PATCHES))
        self.assertIn("b1.rvp", self.parser._BUNDLE_PATCHES)
        self.assertIn("b2.rvp", self.parser._BUNDLE_PATCHES)

    def test_include_also_populates_flat_patches(self: Self) -> None:
        """include() must still populate the flat _PATCHES list alongside _BUNDLE_PATCHES."""
        patch = _make_patch("Consistency", bundle_file="b.rvp")

        self.parser.include(patch, [])

        # _PATCHES has the same entries (prepended)
        self.assertEqual(
            self.parser._PATCHES,
            self.parser._BUNDLE_PATCHES["b.rvp"],
        )


class BundleTrackingExcludeTests(TestCase):
    """Tests for exclude() populating _BUNDLE_PATCHES."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()

    def test_exclude_adds_disable_entry_to_correct_bundle(self: Self) -> None:
        """exclude() should append -d entry to the matching bundle."""
        patch = _make_patch("Bad patch", bundle_file="bundle1.rvp")

        self.parser.exclude(patch)

        self.assertIn("bundle1.rvp", self.parser._BUNDLE_PATCHES)
        self.assertEqual(
            [["-d"], "Bad patch"],
            self.parser._BUNDLE_PATCHES["bundle1.rvp"],
        )

    def test_exclude_without_bundle_file_leaves_bundle_patches_empty(self: Self) -> None:
        """exclude() without bundle_file should not populate _BUNDLE_PATCHES."""
        patch = _make_patch("Legacy exclude", bundle_file=None)

        self.parser.exclude(patch)

        self.assertFalse(self.parser._BUNDLE_PATCHES)

    def test_exclude_appends_not_prepends(self: Self) -> None:
        """exclude() should append (not prepend) to preserve disable-after-enable ordering."""
        inc = _make_patch("Enabled", bundle_file="b.rvp")
        exc = _make_patch("Disabled", bundle_file="b.rvp")

        self.parser.include(inc, [])
        self.parser.exclude(exc)

        self.assertEqual(
            [["-e"], "Enabled", ["-d"], "Disabled"],
            self.parser._BUNDLE_PATCHES["b.rvp"],
        )


class ExclusiveModeBundleSyncTests(TestCase):
    """Tests for enable_exclusive_mode() correctly syncing _BUNDLE_PATCHES."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()
        self.parser._PATCHES = [["-e"], "Keep", ["-e"], "Drop"]
        self.parser._BUNDLE_PATCHES = {
            "b1.rvp": [["-e"], "Keep"],
            "b2.rvp": [["-e"], "Drop"],
        }

    def test_exclusive_mode_keeps_only_surviving_patch_bundle(self: Self) -> None:
        """After enable_exclusive_mode, only the bundle with the surviving patch should remain."""
        self.parser.enable_exclusive_mode()

        self.assertEqual(1, len(self.parser._BUNDLE_PATCHES))
        self.assertIn("b1.rvp", self.parser._BUNDLE_PATCHES)

    def test_exclusive_mode_preserves_surviving_patch_entry(self: Self) -> None:
        """The surviving bundle's entry should contain only the kept patch enable pair."""
        self.parser.enable_exclusive_mode()

        self.assertEqual(
            [["-e"], "Keep"],
            self.parser._BUNDLE_PATCHES["b1.rvp"],
        )

    def test_exclusive_mode_removes_other_bundles(self: Self) -> None:
        """Bundles that did not contain the surviving patch should be deleted."""
        self.parser.enable_exclusive_mode()

        self.assertNotIn("b2.rvp", self.parser._BUNDLE_PATCHES)

    def test_exclusive_mode_with_empty_bundle_patches(self: Self) -> None:
        """enable_exclusive_mode should not crash when _BUNDLE_PATCHES is empty."""
        self.parser._BUNDLE_PATCHES.clear()
        self.parser._PATCHES = [["-e"], "Only"]

        # Should not raise
        self.parser.enable_exclusive_mode()

        self.assertFalse(self.parser._BUNDLE_PATCHES)


class EmitPatchesTests(TestCase):
    """Tests for _emit_patches() helper."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()

    def test_emit_patches_flattens_enable_disable_pairs(self: Self) -> None:
        """_emit_patches should flatten [flag_list, name] pairs into the args list."""
        items: list[str | list[str]] = [
            ["-e"],
            "Patch A",
            ["-d"],
            "Patch B",
        ]
        args: list[str] = []

        self.parser._emit_patches(args, items)

        self.assertEqual(["-e", "Patch A", "-d", "Patch B"], args)

    def test_emit_patches_handles_empty_items(self: Self) -> None:
        """_emit_patches with an empty items list should produce no args."""
        args: list[str] = ["existing"]

        self.parser._emit_patches(args, [])

        self.assertEqual(["existing"], args)

    def test_emit_patches_handles_options(self: Self) -> None:
        """_emit_patches should handle -O option pairs mixed with -e entries."""
        items: list[str | list[str]] = [
            ["-e"],
            "WithOpts",
            ["-O"],
            "key=value",
        ]
        args: list[str] = []

        self.parser._emit_patches(args, items)

        self.assertEqual(["-e", "WithOpts", "-O", "key=value"], args)
