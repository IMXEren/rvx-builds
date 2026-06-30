"""APK variant ranking by architecture preference and density precision."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum
from typing import Self


class Arch(StrEnum):
    """Known Android CPU architectures."""

    ARM64_V8A = "arm64-v8a"
    ARMEABI_V7A = "armeabi-v7a"
    X86_64 = "x86_64"
    X86 = "x86"
    NOARCH = "noarch"
    UNIVERSAL = "universal"


@dataclass(frozen=True, slots=True)
class Density:
    """Screen density specification. Use factory methods to construct."""

    _is_universal: bool = False
    _min_dpi: float = 0.0
    _max_dpi: float = 0.0

    @property
    def span(self) -> float:
        """DPI range width. Universal densities yield infinity."""
        if self._is_universal:
            return float("inf")
        return self._max_dpi - self._min_dpi

    @classmethod
    def universal(cls) -> Self:
        """Catch-all density: nodpi, anydpi."""
        return cls(_is_universal=True)

    @classmethod
    def exact(cls, dpi: float) -> Self:
        """Single DPI target, e.g. 480dpi."""
        return cls(_max_dpi=dpi)

    @classmethod
    def range_dpi(cls, low: float, high: float) -> Self:
        """DPI range, e.g. 160-640dpi."""
        return cls(_min_dpi=low, _max_dpi=high)


# Catch-all densities that work on any screen (NOT architecture keywords).
_DENSITY_UNIVERSAL_KEYWORDS: frozenset[str] = frozenset({"nodpi", "anydpi"})

# Normalise whitespace inside DPI specs and collapse Unicode dashes.
# "160 - 640 dpi" → "160-640dpi", "480 dpi" → "480dpi"
_DENSITY_NORMALISE_RE: re.Pattern[str] = re.compile(
    r"(\d+)\s*[-\u2013\u2014\u2212]\s*(\d+)\s*dpi|(\d+)\s+dpi",
    re.IGNORECASE,
)

# Android density qualifiers → approximate DPI values.
_QUALITATIVE_DPI: dict[str, int] = {
    "ldpi": 120,
    "mdpi": 160,
    "tvdpi": 213,
    "hdpi": 240,
    "xhdpi": 320,
    "xxhdpi": 480,
    "xxxhdpi": 640,
}


class VariantSorter:
    """Ranks APK variants by architecture preference and density precision."""

    # Baseline preferred architectures (presence = top priority)
    PREFERRED_ARCHS: frozenset[Arch] = frozenset({Arch.ARM64_V8A, Arch.NOARCH, Arch.UNIVERSAL})

    @staticmethod
    def parse_archs(source: str, *, delimiter: str | None = ",") -> list[Arch]:
        """
        Parse architecture tokens from text.

        By default splits on commas (``,``). Pass ``delimiter=None`` to split on
        whitespace. Matches tokens against ``Arch`` enum values (case-insensitive),
        longest-match-first to avoid ``x86`` swallowing ``x86_64``.
        """
        tokens = (
            [t.strip() for t in source.split(delimiter) if t.strip()]
            if delimiter is not None
            else source.split()
        )

        # Arch values sorted by length descending for longest-match-first
        arch_values: list[str] = sorted([m.value for m in Arch], key=len, reverse=True)

        archs: list[Arch] = []
        for token in tokens:
            lower = token.lower()
            for val in arch_values:
                if lower == val:
                    archs.append(Arch(val))
                    break
        return archs

    @staticmethod
    def parse_density(source: str) -> Density | None:
        """
        Parse a density specification from text.

        Handles:
          - Universal: ``'nodpi'``, ``'anydpi'`` → ``Density.universal()``
          - Numeric: ``'480dpi'``, ``'480 dpi'``, ``'160-640dpi'``,
            ``'160 -- 640 dpi'`` (Unicode dashes supported)
          - Qualitative: ``'mdpi'``, ``'hdpi'``, ``'xhdpi'``, ``'xxhdpi'``,
            ``'xxxhdpi'``, ``'ldpi'``, ``'tvdpi'``

        Returns ``None`` if no density token is found.
        """
        # Collapse whitespace and Unicode dashes so that "160 -- 640 dpi" -> "160-640dpi"
        source = _DENSITY_NORMALISE_RE.sub(
            lambda m: f"{m.group(1)}-{m.group(2)}dpi" if m.group(1) else f"{m.group(3)}dpi",
            source,
        )

        for token in source.split():
            lower = token.lower()

            # Universal keywords
            if lower in _DENSITY_UNIVERSAL_KEYWORDS:
                return Density.universal()

            # Qualitative DPI buckets
            if lower in _QUALITATIVE_DPI:
                return Density.exact(float(_QUALITATIVE_DPI[lower]))

            # Normalised numeric forms: "160-640dpi" or "480dpi"
            if lower.endswith("dpi"):
                dpi_part = lower[:-3]  # strip "dpi" suffix
                if "-" in dpi_part:
                    low_str, _, high_str = dpi_part.partition("-")
                    try:
                        return Density.range_dpi(float(low_str), float(high_str))
                    except ValueError:
                        pass
                else:
                    try:
                        return Density.exact(float(dpi_part))
                    except ValueError:
                        pass

        return None

    @staticmethod
    def sorting_key(
        archs: list[Arch],
        density: Density | None = None,
    ) -> tuple[bool, float, int]:
        """
        Return descending-sortable tuple.

        Parameters
        ----------
        archs : list[Arch]
            List of ``Arch`` enum values.
        density : Density | None
            ``Density`` spec, or ``None`` (treated as span 0.0).

        Returns
        -------
        tuple[bool, float, int]
            ``(has_primary_arch, density_span, arch_count)`` — designed for use with
            ``sorted(..., key=..., reverse=True)`` so that better matches sort first.
        """
        has_primary = any(a in VariantSorter.PREFERRED_ARCHS for a in archs)
        width = density.span if density else 0.0
        return (has_primary, width, len(archs))
