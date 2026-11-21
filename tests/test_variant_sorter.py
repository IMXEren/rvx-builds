"""Unit tests for the VariantSorter APK ranking class with typed Arch/Density primitives."""

# Density's private fields are checked directly because they are the dataclass state under test.
# ruff: noqa: PT009, SLF001

from typing import Self
from unittest import TestCase

import pytest

from src.apks.variant_sorter import Arch, Density, VariantSorter


class ArchTests(TestCase):
    """Verify Arch enum values and membership."""

    def test_arm64_v8a_value(self: Self) -> None:
        """ARM64_V8A uses Android's `arm64-v8a` ABI name."""
        self.assertEqual(Arch.ARM64_V8A.value, "arm64-v8a")

    def test_armeabi_v7a_value(self: Self) -> None:
        """ARMEABI_V7A uses Android's `armeabi-v7a` ABI name."""
        self.assertEqual(Arch.ARMEABI_V7A.value, "armeabi-v7a")

    def test_x86_64_value(self: Self) -> None:
        """X86_64 uses Android's `x86_64` ABI name."""
        self.assertEqual(Arch.X86_64.value, "x86_64")

    def test_x86_value(self: Self) -> None:
        """X86 uses Android's `x86` ABI name."""
        self.assertEqual(Arch.X86.value, "x86")

    def test_universal_value(self: Self) -> None:
        """UNIVERSAL uses APKMirror's `universal` label."""
        self.assertEqual(Arch.UNIVERSAL.value, "universal")

    def test_noarch_value(self: Self) -> None:
        """NOARCH uses APKMirror's `noarch` label."""
        self.assertEqual(Arch.NOARCH.value, "noarch")

    def test_str_representation(self: Self) -> None:
        """An Arch renders as its ABI name."""
        self.assertEqual(str(Arch.ARM64_V8A), "arm64-v8a")

    def test_construction_from_value(self: Self) -> None:
        """An Arch can be looked up from its ABI name."""
        self.assertEqual(Arch("arm64-v8a"), Arch.ARM64_V8A)
        self.assertEqual(Arch("x86_64"), Arch.X86_64)


class DensityTests(TestCase):
    """Verify Density factory methods and span property."""

    def test_universal_infinite_span(self: Self) -> None:
        """A universal density covers every DPI."""
        d = Density.universal()
        self.assertEqual(d.span, float("inf"))

    def test_universal_is_universal_flag(self: Self) -> None:
        """The universal factory marks the density as universal."""
        d = Density.universal()
        self.assertTrue(d._is_universal)

    def test_exact_dpi_span(self: Self) -> None:
        """An exact density spans up to its DPI."""
        d = Density.exact(480)
        self.assertEqual(d.span, 480.0)

    def test_exact_dpi_zero_range(self: Self) -> None:
        """An exact density starts its range at zero."""
        d = Density.exact(320)
        self.assertEqual(d.span, 320.0)

    def test_exact_dpi_zero_span(self: Self) -> None:
        """An exact zero DPI has no span."""
        d = Density.exact(0)
        self.assertEqual(d.span, 0.0)

    def test_range_dpi_span(self: Self) -> None:
        """A DPI range spans the distance between its bounds."""
        d = Density.range_dpi(160, 640)
        self.assertEqual(d.span, 480.0)

    def test_range_dpi_reversed(self: Self) -> None:
        """Reversed bounds give a negative span."""
        d = Density.range_dpi(640, 160)
        self.assertEqual(d.span, -480.0)

    def test_range_dpi_zero_span(self: Self) -> None:
        """Equal bounds give no span."""
        d = Density.range_dpi(480, 480)
        self.assertEqual(d.span, 0.0)

    def test_default_span_zero(self: Self) -> None:
        """A default density has no span."""
        d = Density()
        self.assertEqual(d.span, 0.0)

    def test_frozen_dataclass(self: Self) -> None:
        """Densities are immutable."""
        d = Density.exact(480)
        with pytest.raises(AttributeError):
            d._min_dpi = 640  # type: ignore[misc]


class ParseArchsTests(TestCase):
    """Verify parse_archs with whitespace and delimiter splitting."""

    def test_whitespace_single_arch(self: Self) -> None:
        """One whitespace-separated arch is parsed."""
        result = VariantSorter.parse_archs("arm64-v8a", delimiter=None)
        self.assertEqual(result, [Arch.ARM64_V8A])

    def test_whitespace_multiple_archs(self: Self) -> None:
        """Several whitespace-separated archs keep their order."""
        result = VariantSorter.parse_archs("arm64-v8a x86_64", delimiter=None)
        self.assertEqual(result, [Arch.ARM64_V8A, Arch.X86_64])

    def test_whitespace_with_other_text(self: Self) -> None:
        """Archs are picked out of surrounding variant text."""
        result = VariantSorter.parse_archs("Variant 3 APK arm64-v8a 480dpi Android 5.0+", delimiter=None)
        self.assertEqual(result, [Arch.ARM64_V8A])

    def test_delimiter_comma(self: Self) -> None:
        """Comma-separated archs are parsed."""
        result = VariantSorter.parse_archs("arm64-v8a,armeabi-v7a")
        self.assertEqual(result, [Arch.ARM64_V8A, Arch.ARMEABI_V7A])

    def test_delimiter_comma_with_spaces(self: Self) -> None:
        """Spaces around commas are ignored."""
        result = VariantSorter.parse_archs("arm64-v8a, x86_64")
        self.assertEqual(result, [Arch.ARM64_V8A, Arch.X86_64])

    def test_default_delimiter_is_comma(self: Self) -> None:
        """Without explicit delimiter, comma is the default splitter."""
        result = VariantSorter.parse_archs("armeabi-v7a,arm64-v8a")
        self.assertEqual(result, [Arch.ARMEABI_V7A, Arch.ARM64_V8A])

    def test_longest_match_first_x86_64(self: Self) -> None:
        """x86_64 must not be split/matched as x86."""
        result = VariantSorter.parse_archs("x86_64", delimiter=None)
        self.assertEqual(result, [Arch.X86_64])

    def test_longest_match_first_armeabi_v7a(self: Self) -> None:
        """armeabi-v7a must match before any prefix."""
        result = VariantSorter.parse_archs("armeabi-v7a", delimiter=None)
        self.assertEqual(result, [Arch.ARMEABI_V7A])

    def test_case_insensitive(self: Self) -> None:
        """Arch names match regardless of case."""
        result = VariantSorter.parse_archs("ARM64-V8A", delimiter=None)
        self.assertEqual(result, [Arch.ARM64_V8A])

    def test_no_archs(self: Self) -> None:
        """Text without arch names gives no archs."""
        result = VariantSorter.parse_archs("Variant 5 APK", delimiter=None)
        self.assertEqual(result, [])

    def test_empty_string(self: Self) -> None:
        """Empty text gives no result."""
        result = VariantSorter.parse_archs("", delimiter=None)
        self.assertEqual(result, [])

    def test_universal_and_noarch(self: Self) -> None:
        """Universal and noarch labels are parsed as archs."""
        result = VariantSorter.parse_archs("universal noarch", delimiter=None)
        self.assertEqual(result, [Arch.UNIVERSAL, Arch.NOARCH])

    def test_bundle_universal_text(self: Self) -> None:
        """A bundle row's universal label is parsed as an arch."""
        result = VariantSorter.parse_archs("Variant 2 BUNDLE universal", delimiter=None)
        self.assertEqual(result, [Arch.UNIVERSAL])

    def test_mixed_archs(self: Self) -> None:
        """Mixed archs keep their order."""
        result = VariantSorter.parse_archs("armeabi-v7a x86_64 arm64-v8a", delimiter=None)
        self.assertEqual(result, [Arch.ARMEABI_V7A, Arch.X86_64, Arch.ARM64_V8A])


class ParseDensityTests(TestCase):
    """Verify parse_density handles all density formats."""

    def _span(self: Self, text: str) -> float:
        """Parse a density that must be present and return its span."""
        density = VariantSorter.parse_density(text)
        if density is None:
            self.fail(f"No density parsed from {text!r}")
        return density.span

    def test_single_480dpi(self: Self) -> None:
        """A single DPI value is parsed."""
        self.assertEqual(self._span("480dpi"), 480.0)

    def test_single_320dpi(self: Self) -> None:
        """Another single DPI value is parsed."""
        self.assertEqual(self._span("320dpi"), 320.0)

    def test_range_160_640dpi(self: Self) -> None:
        """A DPI range is parsed."""
        self.assertEqual(self._span("160-640dpi"), 480.0)

    def test_range_120_160dpi(self: Self) -> None:
        """A narrow DPI range is parsed."""
        self.assertEqual(self._span("120-160dpi"), 40.0)

    def test_nodpi_universal(self: Self) -> None:
        """`nodpi` is a universal density."""
        self.assertEqual(self._span("nodpi"), float("inf"))

    def test_anydpi_universal(self: Self) -> None:
        """`anydpi` is a universal density."""
        self.assertEqual(self._span("anydpi"), float("inf"))

    def test_universal_is_arch_not_density(self: Self) -> None:
        """'universal' and 'noarch' are architecture tokens, not density keywords."""
        d = VariantSorter.parse_density("universal")
        self.assertIsNone(d)

    def test_noarch_is_arch_not_density(self: Self) -> None:
        """`noarch` is an arch token, not a density."""
        d = VariantSorter.parse_density("noarch")
        self.assertIsNone(d)

    def test_case_insensitive_universal(self: Self) -> None:
        """Universal density keywords match regardless of case."""
        self.assertEqual(self._span("NoDPI"), float("inf"))

    def test_case_insensitive_range(self: Self) -> None:
        """DPI ranges match regardless of case."""
        self.assertEqual(self._span("160-640DPI"), 480.0)

    def test_no_density_token(self: Self) -> None:
        """Text without a density gives none."""
        d = VariantSorter.parse_density("Variant 5 APK")
        self.assertIsNone(d)

    def test_empty_string(self: Self) -> None:
        """Empty text gives no result."""
        d = VariantSorter.parse_density("")
        self.assertIsNone(d)

    def test_from_variant_text(self: Self) -> None:
        """A density is picked out of surrounding variant text."""
        self.assertEqual(self._span("Variant 3 APK arm64-v8a 480dpi Android 5.0+"), 480.0)

    def test_from_bundle_universal_text(self: Self) -> None:
        """'universal' in variant text is an arch token, not a density catch-all."""
        d = VariantSorter.parse_density("Variant 2 BUNDLE universal")
        self.assertIsNone(d)

    # ── Flexible whitespace ──────────────────────────────────────────

    def test_range_with_spaces_around_dash(self: Self) -> None:
        """Spaces around a range dash are allowed."""
        self.assertEqual(self._span("160 - 640dpi"), 480.0)

    def test_range_with_space_before_dpi(self: Self) -> None:
        """A space before `dpi` is allowed in a range."""
        self.assertEqual(self._span("160-640 dpi"), 480.0)

    def test_range_with_spaces_everywhere(self: Self) -> None:
        """Spaces around the dash and before `dpi` are allowed together."""
        self.assertEqual(self._span("160 - 640 dpi"), 480.0)

    def test_single_with_space_before_dpi(self: Self) -> None:
        """A space before `dpi` is allowed for a single value."""
        self.assertEqual(self._span("480 dpi"), 480.0)

    # ── Qualitative DPI buckets ──────────────────────────────────────

    def test_mdpi(self: Self) -> None:
        """The mdpi bucket is 160 DPI."""
        self.assertEqual(self._span("mdpi"), 160.0)

    def test_hdpi(self: Self) -> None:
        """The hdpi bucket is 240 DPI."""
        self.assertEqual(self._span("hdpi"), 240.0)

    def test_xhdpi(self: Self) -> None:
        """The xhdpi bucket is 320 DPI."""
        self.assertEqual(self._span("xhdpi"), 320.0)

    def test_xxhdpi(self: Self) -> None:
        """The xxhdpi bucket is 480 DPI."""
        self.assertEqual(self._span("xxhdpi"), 480.0)

    def test_xxxhdpi(self: Self) -> None:
        """The xxxhdpi bucket is 640 DPI."""
        self.assertEqual(self._span("xxxhdpi"), 640.0)

    def test_ldpi(self: Self) -> None:
        """The ldpi bucket is 120 DPI."""
        self.assertEqual(self._span("ldpi"), 120.0)

    def test_tvdpi(self: Self) -> None:
        """The tvdpi bucket is 213 DPI."""
        self.assertEqual(self._span("tvdpi"), 213.0)

    def test_qualitative_case_insensitive(self: Self) -> None:
        """DPI bucket names match regardless of case."""
        self.assertEqual(self._span("HDPI"), 240.0)

    # ── Unicode dashes ───────────────────────────────────────────────

    def test_en_dash(self: Self) -> None:
        """An en dash separates a DPI range."""
        self.assertEqual(self._span("160\u2013640dpi"), 480.0)

    def test_em_dash(self: Self) -> None:
        """An em dash separates a DPI range."""
        self.assertEqual(self._span("160\u2014640dpi"), 480.0)

    def test_minus_sign(self: Self) -> None:
        """A minus sign separates a DPI range."""
        self.assertEqual(self._span("160\u2212640dpi"), 480.0)


class SortingKeyTests(TestCase):
    """Verify sorting_key produces correct tuple values from typed inputs."""

    def test_arm64_nodpi_has_primary(self: Self) -> None:
        """An arm64 universal-density variant gets the best key."""
        archs = [Arch.ARM64_V8A]
        density = Density.universal()
        key = VariantSorter.sorting_key(archs, density)
        self.assertEqual(key, (True, float("inf"), 1))

    def test_no_density_fallback_to_zero(self: Self) -> None:
        """A missing density counts as no span."""
        archs = [Arch.ARM64_V8A, Arch.X86_64]
        key = VariantSorter.sorting_key(archs, None)
        self.assertEqual(key, (True, 0.0, 2))

    def test_no_density_default(self: Self) -> None:
        """The density argument defaults to none."""
        archs = [Arch.ARM64_V8A]
        key = VariantSorter.sorting_key(archs)
        self.assertEqual(key, (True, 0.0, 1))

    def test_armeabi_no_primary(self: Self) -> None:
        """armeabi-v7a is not a preferred arch."""
        archs = [Arch.ARMEABI_V7A]
        density = Density.exact(480)
        key = VariantSorter.sorting_key(archs, density)
        self.assertEqual(key, (False, 480.0, 1))

    def test_more_archs_better(self: Self) -> None:
        """Supporting more archs ranks higher."""
        density = Density.exact(480)
        key_a = VariantSorter.sorting_key([Arch.ARM64_V8A], density)
        key_b = VariantSorter.sorting_key([Arch.ARM64_V8A, Arch.X86_64], density)
        self.assertGreater(key_b, key_a)

    def test_primary_arch_trumps_everything(self: Self) -> None:
        """A preferred arch outranks any density."""
        density = Density.universal()
        key_a = VariantSorter.sorting_key([Arch.ARM64_V8A], density)
        key_b = VariantSorter.sorting_key([Arch.ARMEABI_V7A], density)
        self.assertGreater(key_a, key_b)

    def test_infinite_density_trumps_exact(self: Self) -> None:
        """A universal density outranks an exact one."""
        archs = [Arch.ARM64_V8A]
        key_a = VariantSorter.sorting_key(archs, Density.universal())
        key_b = VariantSorter.sorting_key(archs, Density.exact(480))
        self.assertGreater(key_a, key_b)

    def test_equal_range_and_exact_density(self: Self) -> None:
        """A range and an exact density with equal spans rank equally."""
        archs = [Arch.ARM64_V8A]
        key_a = VariantSorter.sorting_key(archs, Density.range_dpi(160, 640))
        key_b = VariantSorter.sorting_key(archs, Density.exact(480))
        self.assertEqual(key_a, key_b)

    def test_noarch_is_primary(self: Self) -> None:
        """The noarch label is a preferred arch."""
        archs = [Arch.NOARCH]
        key = VariantSorter.sorting_key(archs, Density.universal())
        self.assertEqual(key, (True, float("inf"), 1))

    def test_x86_is_not_primary(self: Self) -> None:
        """x86 is not a preferred arch."""
        archs = [Arch.X86]
        key = VariantSorter.sorting_key(archs)
        self.assertEqual(key, (False, 0.0, 1))

    def test_x86_64_is_not_primary(self: Self) -> None:
        """x86_64 is not a preferred arch."""
        archs = [Arch.X86_64]
        key = VariantSorter.sorting_key(archs)
        self.assertEqual(key, (False, 0.0, 1))

    def test_empty_arch_list(self: Self) -> None:
        """A variant without archs gets the lowest key."""
        key = VariantSorter.sorting_key([])
        self.assertEqual(key, (False, 0.0, 0))

    def test_unknown_archs_not_primary(self: Self) -> None:
        """Arch values not in PREFERRED_ARCHS yield has_primary=False."""
        archs = [Arch.X86, Arch.ARMEABI_V7A]
        key = VariantSorter.sorting_key(archs)
        self.assertEqual(key, (False, 0.0, 2))

    def test_mixed_known_and_preferred(self: Self) -> None:
        """A list containing at least one preferred arch yields has_primary=True."""
        archs = [Arch.ARM64_V8A, Arch.X86]
        key = VariantSorter.sorting_key(archs)
        self.assertEqual(key, (True, 0.0, 2))


class SortingIntegrationTests(TestCase):
    """End-to-end sort order verification using sorted(..., reverse=True)."""

    def test_arm64_nodpi_ranks_first(self: Self) -> None:
        """The arm64 universal-density variant sorts first."""
        variants = [
            ([Arch.ARMEABI_V7A], Density.exact(480)),
            ([Arch.ARM64_V8A], Density.universal()),
            ([Arch.ARM64_V8A], Density.exact(480)),
        ]
        result = sorted(variants, key=lambda v: VariantSorter.sorting_key(*v), reverse=True)
        self.assertEqual(result[0], ([Arch.ARM64_V8A], Density.universal()))

    def test_more_archs_ranks_above_fewer(self: Self) -> None:
        """The variant with more archs sorts first."""
        variants = [
            ([Arch.ARM64_V8A], Density.exact(480)),
            ([Arch.ARM64_V8A, Arch.X86_64], Density.exact(480)),
        ]
        result = sorted(variants, key=lambda v: VariantSorter.sorting_key(*v), reverse=True)
        self.assertEqual(result[0], ([Arch.ARM64_V8A, Arch.X86_64], Density.exact(480)))

    def test_noarch_fallback_ranks_low(self: Self) -> None:
        """A non-preferred arch sorts after a preferred one."""
        variants = [
            ([Arch.ARM64_V8A], Density.universal()),
            ([Arch.X86], Density.universal()),
        ]
        result = sorted(variants, key=lambda v: VariantSorter.sorting_key(*v), reverse=True)
        self.assertEqual(result[0], ([Arch.ARM64_V8A], Density.universal()))

    def test_density_none_causes_arch_only_sorting(self: Self) -> None:
        """Without densities, variants sort by arch alone."""
        variants = [
            ([Arch.X86], None),
            ([Arch.ARM64_V8A, Arch.ARMEABI_V7A], None),
            ([Arch.ARM64_V8A], None),
        ]
        result = sorted(variants, key=lambda v: VariantSorter.sorting_key(*v), reverse=True)
        self.assertEqual(result[0], ([Arch.ARM64_V8A, Arch.ARMEABI_V7A], None))
        self.assertEqual(result[1], ([Arch.ARM64_V8A], None))
        self.assertEqual(result[2], ([Arch.X86], None))
