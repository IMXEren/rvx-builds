"""Tests for bundle-aware patch selection and [selector:]patch_name matching.

Selectors support:
  - ``2:patch_name`` matches only bundle N (1-indexed)
  - ``1-3:patch_name`` matches bundles N through M
  - ``^1-3:patch_name`` matches bundles outside the selector
  - ``*:patch_name`` matches all bundles
  - ``patch_name`` (bare) matches all bundles

Core matching logic lives in :mod:`src._bundle_selector`.
"""

# ruff: noqa: SLF001, D102, S101

from typing import Self
from unittest import TestCase
from unittest.mock import MagicMock

import pytest

from src._bundle_selector import PatchBase, entry_matches, parse_patch_selection, selector_matches
from src.parser import Parser
from src.structs.patches import PatchInfo

BUNDLE_2_IDX = 2


def _make_patch(name: str, bundle_file: str | None = None, *, enabled: bool = False) -> PatchInfo:
    return PatchInfo(
        name=name,
        description="test patch",
        app="com.test.app",
        version="1.0.0",
        options=[],
        bundle_file=bundle_file,
        enabled=enabled,
    )


def _make_parser() -> Parser:
    parser = Parser(MagicMock(), MagicMock())
    parser._enable_arg = ["-e"]
    parser._disable_arg = ["-d"]
    parser._options_arg = ["-O"]
    return parser


# ---------------------------------------------------------------------------
# selector_matches() without Parser
# ---------------------------------------------------------------------------


class SelectorMatchesTests(TestCase):
    """Tests for :func:`src._bundle_selector.selector_matches`."""

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
# entry_matches() without Parser
# ---------------------------------------------------------------------------


class EntryMatchesTests(TestCase):
    """Tests for :func:`src._bundle_selector.entry_matches`."""

    def test_legacy_bare_name(self: Self) -> None:
        assert entry_matches("disable-ads", "disable-ads", None)
        assert entry_matches("disable-ads", "disable-ads", 1)
        assert entry_matches("disable-ads", "disable-ads", 2)
        assert not entry_matches("disable-ads", "other-patch", 1)

    def test_single_bundle_exclude(self: Self) -> None:
        assert entry_matches("2:disable-ads", "disable-ads", 2)
        assert not entry_matches("2:disable-ads", "disable-ads", 1)
        assert not entry_matches("2:disable-ads", "disable-ads", 3)

    def test_range_bundle_exclude(self: Self) -> None:
        assert entry_matches("1-3:disable-ads", "disable-ads", 1)
        assert entry_matches("1-3:disable-ads", "disable-ads", 2)
        assert entry_matches("1-3:disable-ads", "disable-ads", 3)
        assert not entry_matches("1-3:disable-ads", "disable-ads", 4)

    def test_negate_bundle_exclude(self: Self) -> None:
        assert not entry_matches("^1-3:disable-ads", "disable-ads", 1)
        assert not entry_matches("^1-3:disable-ads", "disable-ads", 2)
        assert entry_matches("^1-3:disable-ads", "disable-ads", 4)
        assert entry_matches("^1-3:disable-ads", "disable-ads", 5)

    def test_all_bundles_exclude(self: Self) -> None:
        assert entry_matches("*:disable-ads", "disable-ads", 1)
        assert entry_matches("*:disable-ads", "disable-ads", 5)

    def test_patch_name_mismatch(self: Self) -> None:
        assert not entry_matches("2:disable-ads", "other-patch", 2)

    def test_unknown_bundle_index_fallback(self: Self) -> None:
        assert not entry_matches("2:disable-ads", "disable-ads", None)
        assert not entry_matches("1-3:disable-ads", "disable-ads", None)
        assert entry_matches("*:disable-ads", "disable-ads", None)

    def test_malformed_entry(self: Self) -> None:
        assert not entry_matches("::nope", "nope", 1)
        assert not entry_matches("::::", "", 1)


# ---------------------------------------------------------------------------
# Parser integration: selection base, overrides, and bundle scope


class PatchSelectionTests(TestCase):
    """Evaluate patch selection against individual bundle entries."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()
        self.parser._bundle_index_map = {"bundle1.rvp": 1, "bundle2.rvp": 2}

    def _app(self: Self, selection: str = "DEFAULT", *, normalize: bool = True) -> MagicMock:
        app = MagicMock()
        app.normalize_patch_names = normalize
        app.selection_base, app.selection_overrides = parse_patch_selection(selection)
        return app

    def test_default_uses_maintainer_enabled_state(self: Self) -> None:
        app = self._app()
        assert self.parser._should_select_patch(_make_patch("Enabled", "bundle1.rvp", enabled=True), app)
        assert not self.parser._should_select_patch(_make_patch("Disabled", "bundle2.rvp"), app)

    def test_all_and_none_override_metadata(self: Self) -> None:
        patch = _make_patch("My Patch", "bundle1.rvp")
        assert self.parser._should_select_patch(patch, self._app("ALL"))
        enabled = _make_patch("My Patch", "bundle1.rvp", enabled=True)
        assert not self.parser._should_select_patch(enabled, self._app("NONE"))

    def test_scoped_operations_and_last_wins(self: Self) -> None:
        app = self._app("NONE,+my-patch,-2:my-patch,+2:my-patch,-1:my-patch")
        assert not self.parser._should_select_patch(_make_patch("My Patch", "bundle1.rvp"), app)
        assert self.parser._should_select_patch(_make_patch("My Patch", "bundle2.rvp"), app)

    def test_scope_ranges_and_negation(self: Self) -> None:
        app = self._app("ALL,-^1:my-patch")
        assert self.parser._should_select_patch(_make_patch("My Patch", "bundle1.rvp"), app)
        assert not self.parser._should_select_patch(_make_patch("My Patch", "bundle2.rvp"), app)

    def test_exact_names_when_normalization_disabled(self: Self) -> None:
        app = self._app("NONE,+My Patch", normalize=False)
        assert self.parser._should_select_patch(_make_patch("My Patch"), app)

    def test_default_base_can_be_implicit(self: Self) -> None:
        app = self._app("+my-patch")
        assert self.parser._should_select_patch(_make_patch("My Patch"), app)
        assert not self.parser._should_select_patch(_make_patch("Other"), app)

    def test_all_base_clauses_parse_as_enum(self: Self) -> None:
        for base in PatchBase:
            with self.subTest(base=base):
                assert parse_patch_selection(base.value)[0] is base

    def test_reject_scoped_base_and_malformed_override(self: Self) -> None:
        for value in ("LEGACY", "ALL,2:DEFAULT", "DEFAULT,", "DEFAULT,+", "DEFAULT,-bad:patch"):
            with self.subTest(value=value), pytest.raises(ValueError, match="Invalid patch selection clause"):
                parse_patch_selection(value)

    def test_app_base_selects_app_patches_only(self: Self) -> None:
        app = self._app("APP,+universal-patch,-2:regular-patch")
        regular = _make_patch("Regular Patch", "bundle1.rvp")
        scoped = _make_patch("Regular Patch", "bundle2.rvp")
        universal = _make_patch("Universal Patch", "bundle1.rvp", enabled=True)
        universal["app"] = "universal"
        other = _make_patch("Other Universal", "bundle1.rvp", enabled=True)
        other["app"] = "universal"

        assert self.parser._should_select_patch(regular, app)
        assert not self.parser._should_select_patch(scoped, app)
        assert self.parser._should_select_patch(universal, app)
        assert not self.parser._should_select_patch(other, app)

    def test_universal_patch_uses_same_selection(self: Self) -> None:
        patch = _make_patch("Universal Patch", "bundle1.rvp")
        assert not self.parser._should_select_patch(patch, self._app())
        assert self.parser._should_select_patch(patch, self._app("ALL"))
        assert self.parser._should_select_patch(patch, self._app("NONE,+universal-patch"))

    def test_emits_bundle_specific_flags(self: Self) -> None:
        app = self._app("DEFAULT,-2:my-patch")
        first = _make_patch("My Patch", "bundle1.rvp", enabled=True)
        second = _make_patch("My Patch", "bundle2.rvp", enabled=True)
        self.parser._process_patches([first, second], app, [])
        assert self.parser._BUNDLE_PATCHES["bundle1.rvp"] == [["-e"], "My Patch"]
        assert self.parser._BUNDLE_PATCHES["bundle2.rvp"] == [["-d"], "My Patch"]


class GetBundleIndexTests(TestCase):
    """Tests for Parser._get_bundle_index()."""

    def setUp(self: Self) -> None:
        self.parser = _make_parser()
        self.parser._bundle_index_map = {"bundle1.rvp": 1, "bundle2.rvp": 2}

    def test_known_bundle(self: Self) -> None:
        assert self.parser._get_bundle_index(_make_patch("p", "bundle2.rvp")) == BUNDLE_2_IDX

    def test_unknown_bundle(self: Self) -> None:
        assert self.parser._get_bundle_index(_make_patch("p", "unknown.rvp")) is None

    def test_no_bundle_file(self: Self) -> None:
        assert self.parser._get_bundle_index(_make_patch("p")) is None
