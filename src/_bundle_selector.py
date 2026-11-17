"""Bundle-scoped patch selection by bundle index.

Provides the ``[selector:]patch_name`` syntax where ``selector`` is one of:
  - ``*`` matches all bundles
  - ``N`` matches one bundle (1-indexed)
  - ``N-M`` matches an inclusive range
  - ``^selector`` matches bundles outside the selector
"""

import re
from enum import StrEnum


class PatchBase(StrEnum):
    """Starting sets for app-wide patch selection."""

    ALL = "ALL"
    DEFAULT = "DEFAULT"
    NONE = "NONE"
    APP = "APP"


# Matches bundle selectors: 1, 1-3, ^1, ^1-3
_BUNDLE_SELECTOR_RE = re.compile(r"^(\^)?(\d+)(?:-(\d+))?$")
# Converts any non-alphanumeric sequence to dash for matching
_NORMALIZE_PATTERN = re.compile(r"[^a-z0-9]+")


def normalize_patch_name(name: str) -> str:
    """Lowercase a patch name and replace all non-alphanumeric runs with ``-``.

    E.g. ``"Fix /s/ links"`` → ``"fix-s-links"``.
    """
    return _NORMALIZE_PATTERN.sub("-", name.lower()).strip("-")


def selector_matches(selector: str, bundle_index: int) -> bool:
    """Evaluate a selector against a 1-indexed bundle position.

    Parameters
    ----------
    selector : str
        Selector string (``*``, ``N``, ``N-M``, ``^...``).
    bundle_index : int
        1-indexed bundle position.

    Returns
    -------
    bool
        True if the selector matches this bundle position.
    """
    if selector == "*":
        return True

    negate = False
    s = selector
    if s.startswith("^"):
        negate = True
        s = s[1:]

    if s == "*":
        result = True
    else:
        m = _BUNDLE_SELECTOR_RE.match(s)
        if not m:
            return False
        start = int(m.group(2))
        end = int(m.group(3)) if m.group(3) else start
        result = start <= bundle_index <= end

    return not result if negate else result


def entry_matches(entry: str, patch_name: str, bundle_index: int | None) -> bool:
    """Check if a selector entry matches a given patch and bundle.

    Entry format: ``[selector:]patch_name``
      - ``2:patch_name`` matches only bundle 2
      - ``1-3:patch_name`` matches bundles 1 through 3
      - ``^1-3:patch_name`` matches bundles outside 1-3
      - ``*:patch_name`` matches all bundles
      - ``patch_name`` (no colon) matches all bundles

    Parameters
    ----------
    entry : str
        The selector entry.
    patch_name : str
        The patch name to check.
    bundle_index : int | None
        The 1-indexed bundle position, or None if unknown.

    Returns
    -------
    bool
        True if the entry matches this patch/bundle.
    """
    colon_idx = entry.find(":")
    if colon_idx > 0:
        selector_str = entry[:colon_idx]
        name = entry[colon_idx + 1 :]
        if name != patch_name:
            return False
        if bundle_index is not None:
            return selector_matches(selector_str, bundle_index)
        return selector_str == "*"

    # No selector applies to all bundles
    return entry == patch_name


def parse_patch_selection(value: str) -> tuple[PatchBase, list[tuple[bool, str]]]:
    """Parse an app-wide base followed by ordered patch overrides."""
    if not value.strip():
        return PatchBase.DEFAULT, []
    parts = [part.strip() for part in value.split(",")]
    base = PatchBase.DEFAULT
    if parts[0].upper() in PatchBase.__members__:
        base = PatchBase[parts.pop(0).upper()]
    overrides = []
    for part in parts:
        if not part or part[0] not in "+-" or not part[1:]:
            msg = f"Invalid patch selection clause: {part!r}"
            raise ValueError(msg)
        entry = part[1:]
        selector, separator, name = entry.partition(":")
        valid_selector = selector.removeprefix("^") == "*" or bool(_BUNDLE_SELECTOR_RE.fullmatch(selector))
        if separator and (not name or not valid_selector):
            msg = f"Invalid patch selection clause: {part!r}"
            raise ValueError(msg)
        overrides.append((part[0] == "+", entry))
    return base, overrides
