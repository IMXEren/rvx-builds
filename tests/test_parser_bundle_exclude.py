"""Tests for bundle-aware exclude with [selector:]patch_name syntax.

The exclude_request list supports:
  - ``2:patch_name`` — exclude from bundle N only (1-indexed)
  - ``1-3:patch_name`` — exclude from bundles N through M
  - ``^1-3:patch_name`` — exclude from bundles NOT matching selector
  - ``*:patch_name`` — exclude from all bundles
  - ``patch_name`` (bare) — exclude from all bundles (legacy)
  - ``EXCEPT::`` prefix — allowlist mode
  - ``EXCEPT::2:patch_name`` — allowlist, keep from bundle 2 only

Core matching logic lives in :mod:`src._exclude_matcher` (lightweight, no parser imports).
"""

# ruff: noqa: SLF001, D102, S101

from typing import Self
from unittest import TestCase
from unittest.mock import MagicMock

from src._bundle_selector import entry_matches as matches_exclude
from src._bundle_selector import selector_matches
from src.parser import Parser
from src.structs.patches import PatchInfo

BUNDLE_2_IDX = 2


def _make_patch(name: str, bundle_file: str | None = None) -> PatchInfo:
    return PatchInfo(
        name=name,
        description="test patch",
        app="com.test.app",
        version="1.0.0",
        options=[],
        bundle_file=bundle_file,
    )


def _make_parser() -> Parser:
    parser = Parser(MagicMock(), MagicMock())
    parser._enable_arg = ["-e"]
    parser._disable_arg = ["-d"]
    parser._options_arg = ["-O"]
    return parser


# ---------------------------------------------------------------------------
# selector_matches() — standalone, no Parser needed
# ---------------------------------------------------------------------------


class SelectorMatchesTests(TestCase):
    """Tests for :func:`src._exclude_matcher.selector_matches`."""

    def test_asterisk_matches_any(self: Self) -> None:
        assert selector_matches("*", 1)
        assert selector_matches("*", 5)

    def test_single_index(self: Self) -> None:
        assert selector_matches("2", 2)
        assert not selector_matches("2", 1)
        assert not selector_matches("2", 3)

    def test_range(self: Self) -> None:
        assert selector_matches("1-3", 1)
        assert selector_matches("1-3", 2)
        assert selector_matches("1-3", 3)
        assert not selector_matches("1-3", 4)
        assert not selector_matches("1-3", 0)

    def test_negate_single(self: Self) -> None:
        assert selector_matches("^2", 1)
        assert not selector_matches("^2", 2)
        assert selector_matches("^2", 3)

    def test_negate_range(self: Self) -> None:
        assert selector_matches("^1-3", 4)
        assert selector_matches("^1-3", 5)
        assert not selector_matches("^1-3", 1)
        assert not selector_matches("^1-3", 2)
        assert not selector_matches("^1-3", 3)

    def test_negate_asterisk(self: Self) -> None:
        assert not selector_matches("^*", 1)
        assert not selector_matches("^*", 99)

    def test_invalid_selector(self: Self) -> None:
        assert not selector_matches("abc", 1)
        assert not selector_matches("", 1)
        assert not selector_matches("^-", 1)


# ---------------------------------------------------------------------------
# matches_exclude() — standalone, no Parser needed
# ---------------------------------------------------------------------------


class MatchesExcludeTests(TestCase):
    """Tests for :func:`src._exclude_matcher.matches_exclude`."""

    def test_legacy_bare_name(self: Self) -> None:
        assert matches_exclude("disable-ads", "disable-ads", None)
        assert matches_exclude("disable-ads", "disable-ads", 1)
        assert matches_exclude("disable-ads", "disable-ads", 2)
        assert not matches_exclude("disable-ads", "other-patch", 1)

    def test_single_bundle_exclude(self: Self) -> None:
        assert matches_exclude("2:disable-ads", "disable-ads", 2)
        assert not matches_exclude("2:disable-ads", "disable-ads", 1)
        assert not matches_exclude("2:disable-ads", "disable-ads", 3)

    def test_range_bundle_exclude(self: Self) -> None:
        assert matches_exclude("1-3:disable-ads", "disable-ads", 1)
        assert matches_exclude("1-3:disable-ads", "disable-ads", 2)
        assert matches_exclude("1-3:disable-ads", "disable-ads", 3)
        assert not matches_exclude("1-3:disable-ads", "disable-ads", 4)

    def test_negate_bundle_exclude(self: Self) -> None:
        assert not matches_exclude("^1-3:disable-ads", "disable-ads", 1)
        assert not matches_exclude("^1-3:disable-ads", "disable-ads", 2)
        assert matches_exclude("^1-3:disable-ads", "disable-ads", 4)
        assert matches_exclude("^1-3:disable-ads", "disable-ads", 5)

    def test_all_bundles_exclude(self: Self) -> None:
        assert matches_exclude("*:disable-ads", "disable-ads", 1)
        assert matches_exclude("*:disable-ads", "disable-ads", 5)

    def test_patch_name_mismatch(self: Self) -> None:
        assert not matches_exclude("2:disable-ads", "other-patch", 2)

    def test_unknown_bundle_index_fallback(self: Self) -> None:
        assert not matches_exclude("2:disable-ads", "disable-ads", None)
        assert not matches_exclude("1-3:disable-ads", "disable-ads", None)
        assert matches_exclude("*:disable-ads", "disable-ads", None)

    def test_malformed_entry(self: Self) -> None:
        assert not matches_exclude("::nope", "nope", 1)
        assert not matches_exclude("::::", "", 1)


# ---------------------------------------------------------------------------
# Parser integration — _get_bundle_index, _should_include_*
# ---------------------------------------------------------------------------


class GetBundleIndexTests(TestCase):
    """Tests for Parser._get_bundle_index()."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()
        self.parser._bundle_index_map = {"bundle1.rvp": 1, "bundle2.rvp": 2, "bundle3.rvp": 3}

    def test_known_bundle(self: Self) -> None:
        assert self.parser._get_bundle_index(_make_patch("p", "bundle2.rvp")) == BUNDLE_2_IDX

    def test_unknown_bundle(self: Self) -> None:
        assert self.parser._get_bundle_index(_make_patch("p", "unknown.rvp")) is None

    def test_no_bundle_file(self: Self) -> None:
        assert self.parser._get_bundle_index(_make_patch("p")) is None


class ShouldIncludeRegularPatchTests(TestCase):
    """Tests for _should_include_regular_patch with bundle-aware excludes."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()
        self.parser._bundle_index_map = {"bundle1.rvp": 1, "bundle2.rvp": 2}

    def _app(self, exclude: list[str] | None = None) -> MagicMock:
        app = MagicMock()
        app.normalize_patch_names = False
        app.exclude_request = exclude or []
        return app

    def test_not_in_exclude_list(self: Self) -> None:
        app = self._app(["other-patch"])
        assert self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle1.rvp"),
            "my-patch",
            app,
        )

    def test_legacy_global_exclude(self: Self) -> None:
        app = self._app(["my-patch"])
        assert not self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle1.rvp"),
            "my-patch",
            app,
        )
        assert not self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle2.rvp"),
            "my-patch",
            app,
        )

    def test_bundle_scoped_exclude_matches(self: Self) -> None:
        app = self._app(["2:my-patch"])
        assert self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle1.rvp"),
            "my-patch",
            app,
        )
        assert not self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle2.rvp"),
            "my-patch",
            app,
        )

    def test_negate_range_exclude(self: Self) -> None:
        app = self._app(["^1:my-patch"])
        assert self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle1.rvp"),
            "my-patch",
            app,
        )
        assert not self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle2.rvp"),
            "my-patch",
            app,
        )

    def test_mixed_bare_and_scoped(self: Self) -> None:
        app = self._app(["2:scoped-patch", "global-patch"])
        assert not self.parser._should_include_regular_patch(
            _make_patch("scoped-patch", "bundle2.rvp"),
            "scoped-patch",
            app,
        )
        assert not self.parser._should_include_regular_patch(
            _make_patch("global-patch", "bundle1.rvp"),
            "global-patch",
            app,
        )

    def test_different_patch_name_not_excluded(self: Self) -> None:
        app = self._app(["2:some-patch"])
        assert self.parser._should_include_regular_patch(
            _make_patch("other-patch", "bundle2.rvp"),
            "other-patch",
            app,
        )

    def test_asterisk_all_bundles(self: Self) -> None:
        app = self._app(["*:my-patch"])
        assert not self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle1.rvp"),
            "my-patch",
            app,
        )
        assert not self.parser._should_include_regular_patch(
            _make_patch("my-patch", "bundle2.rvp"),
            "my-patch",
            app,
        )

    def test_space_formatted(self: Self) -> None:
        app = self._app(["my-patch"])
        app.normalize_patch_names = True
        assert not self.parser._should_include_regular_patch(
            _make_patch("My Patch"),
            "my-patch",
            app,
        )

    # --- Allowlist mode (EXCEPT:: prefix) ---

    def test_allowlist_keeps_matching_patch(self: Self) -> None:
        """EXCEPT:: prefix flips to allowlist mode."""
        app = self._app(["EXCEPT::2:keep-me"])
        assert not self.parser._should_include_regular_patch(
            _make_patch("keep-me", "bundle1.rvp"),
            "keep-me",
            app,
        )
        assert self.parser._should_include_regular_patch(
            _make_patch("keep-me", "bundle2.rvp"),
            "keep-me",
            app,
        )

    def test_allowlist_excludes_unlisted_patches(self: Self) -> None:
        """Patches not in any EXCEPT entry are excluded."""
        app = self._app(["EXCEPT::2:keep-me"])
        assert not self.parser._should_include_regular_patch(
            _make_patch("other-patch", "bundle2.rvp"),
            "other-patch",
            app,
        )

    def test_allowlist_bare_name(self: Self) -> None:
        """EXCEPT:: with bare name keeps from all bundles."""
        app = self._app(["EXCEPT::keep-me"])
        assert self.parser._should_include_regular_patch(
            _make_patch("keep-me", "bundle1.rvp"),
            "keep-me",
            app,
        )
        assert self.parser._should_include_regular_patch(
            _make_patch("keep-me", "bundle2.rvp"),
            "keep-me",
            app,
        )
        assert not self.parser._should_include_regular_patch(
            _make_patch("other", "bundle1.rvp"),
            "other",
            app,
        )

    def test_allowlist_all_bundles(self: Self) -> None:
        """EXCEPT::*:patch keeps from all bundles."""
        app = self._app(["EXCEPT::*:keep-me"])
        assert self.parser._should_include_regular_patch(
            _make_patch("keep-me", "bundle1.rvp"),
            "keep-me",
            app,
        )

    def test_denylist_still_works_without_except(self: Self) -> None:
        """Exclude list without EXCEPT entries still works as deny."""
        app = self._app(["skip-me"])
        assert not self.parser._should_include_regular_patch(
            _make_patch("skip-me", "bundle1.rvp"),
            "skip-me",
            app,
        )
        assert self.parser._should_include_regular_patch(
            _make_patch("other", "bundle1.rvp"),
            "other",
            app,
        )


class ShouldIncludeUniversalPatchTests(TestCase):
    """Tests for _should_include_universal_patch with bundle-aware excludes."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()
        self.parser._bundle_index_map = {"bundle1.rvp": 1, "bundle2.rvp": 2}

    def _app(self, exclude: list[str] | None = None, include: list[str] | None = None) -> MagicMock:
        app = MagicMock()
        app.normalize_patch_names = False
        app.exclude_request = exclude or []
        app.include_request = include or []
        return app

    def test_not_in_include_list(self: Self) -> None:
        app = self._app(include=["other-patch"])
        assert not self.parser._should_include_universal_patch(
            _make_patch("my-patch", "bundle1.rvp"),
            "my-patch",
            app,
        )

    def test_in_include_list_and_not_excluded(self: Self) -> None:
        app = self._app(exclude=["other-patch"], include=["my-patch"])
        assert self.parser._should_include_universal_patch(
            _make_patch("my-patch", "bundle1.rvp"),
            "my-patch",
            app,
        )

    def test_in_include_but_excluded_from_bundle(self: Self) -> None:
        app = self._app(exclude=["2:my-patch"], include=["my-patch"])
        assert self.parser._should_include_universal_patch(
            _make_patch("my-patch", "bundle1.rvp"),
            "my-patch",
            app,
        )
        assert not self.parser._should_include_universal_patch(
            _make_patch("my-patch", "bundle2.rvp"),
            "my-patch",
            app,
        )
