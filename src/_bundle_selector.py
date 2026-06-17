"""Bundle-scoped patch selection for include/exclude by bundle index.

Provides the ``[!][selector:]patch_name`` syntax where ``selector`` is one of:
  - ``*`` — all bundles
  - ``N`` — single bundle (1-indexed)
  - ``N-M`` — inclusive range
  - ``^selector`` — negation (NOT)
"""

import re

# Matches bundle selectors: 1, 1-3, ^1, ^1-3
_BUNDLE_SELECTOR_RE = re.compile(r"^(\^)?(\d+)(?:-(\d+))?$")


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
      - ``2:patch_name`` — matches only bundle 2
      - ``1-3:patch_name`` — matches bundles 1 through 3
      - ``^1-3:patch_name`` — matches bundles NOT 1-3
      - ``*:patch_name`` — matches all bundles
      - ``patch_name`` (no colon) — matches all bundles (legacy)

    The ``!`` allowlist prefix is stripped by the caller before calling this.

    Parameters
    ----------
    entry : str
        The selector entry (without ``!`` prefix).
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

    # No colon — applies to all bundles
    return entry == patch_name
