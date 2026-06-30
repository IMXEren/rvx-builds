"""Unit tests for the VariantSorter APK ranking class with typed Arch/Density primitives."""

# ruff: noqa: PT009

from typing import Self
from unittest import TestCase

import pytest

from src.apks.variant_sorter import Arch, Density, VariantSorter


class ArchTests(TestCase):
    """Verify Arch enum values and membership."""

    def test_arm64_v8a_value(self: Self) -> None:
        self.assertEqual(Arch.ARM64_V8A.value, "arm64-v8a")

    def test_armeabi_v7a_value(self: Self) -> None:
        self.assertEqual(Arch.ARMEABI_V7A.value, "armeabi-v7a")

    def test_x86_64_value(self: Self) -> None:
        self.assertEqual(Arch.X86_64.value, "x86_64")

    def test_x86_value(self: Self) -> None:
        self.assertEqual(Arch.X86.value, "x86")

    def test_universal_value(self: Self) -> None:
        self.assertEqual(Arch.UNIVERSAL.value, "universal")

    def test_noarch_value(self: Self) -> None:
        self.assertEqual(Arch.NOARCH.value, "noarch")

    def test_str_representation(self: Self) -> None:
        self.assertEqual(str(Arch.ARM64_V8A), "arm64-v8a")

    def test_construction_from_value(self: Self) -> None:
        self.assertEqual(Arch("arm64-v8a"), Arch.ARM64_V8A)
        self.assertEqual(Arch("x86_64"), Arch.X86_64)


class DensityTests(TestCase):
    """Verify Density factory methods and span property."""

    def test_universal_infinite_span(self: Self) -> None:
        d = Density.universal()
        self.assertEqual(d.span, float("inf"))

    def test_universal_is_universal_flag(self: Self) -> None:
        d = Density.universal()
        self.assertTrue(d._is_universal)

    def test_exact_dpi_span(self: Self) -> None:
        d = Density.exact(480)
        self.assertEqual(d.span, 480.0)

    def test_exact_dpi_zero_range(self: Self) -> None:
        d = Density.exact(320)
        self.assertEqual(d.span, 320.0)

    def test_exact_dpi_zero_span(self: Self) -> None:
        d = Density.exact(0)
        self.assertEqual(d.span, 0.0)

    def test_range_dpi_span(self: Self) -> None:
        d = Density.range_dpi(160, 640)
        self.assertEqual(d.span, 480.0)

    def test_range_dpi_reversed(self: Self) -> None:
        d = Density.range_dpi(640, 160)
        self.assertEqual(d.span, -480.0)

    def test_range_dpi_zero_span(self: Self) -> None:
        d = Density.range_dpi(480, 480)
        self.assertEqual(d.span, 0.0)

    def test_default_span_zero(self: Self) -> None:
        d = Density()
        self.assertEqual(d.span, 0.0)

    def test_frozen_dataclass(self: Self) -> None:
        d = Density.exact(480)
        with pytest.raises(AttributeError):
            d._min_dpi = 640  # type: ignore[misc]


class ParseArchsTests(TestCase):
    """Verify parse_archs with whitespace and delimiter splitting."""

    def test_whitespace_single_arch(self: Self) -> None:
        result = VariantSorter.parse_archs("arm64-v8a", delimiter=None)
        self.assertEqual(result, [Arch.ARM64_V8A])

    def test_whitespace_multiple_archs(self: Self) -> None:
        result = VariantSorter.parse_archs("arm64-v8a x86_64", delimiter=None)
        self.assertEqual(result, [Arch.ARM64_V8A, Arch.X86_64])

    def test_whitespace_with_other_text(self: Self) -> None:
        result = VariantSorter.parse_archs("Variant 3 APK arm64-v8a 480dpi Android 5.0+", delimiter=None)
        self.assertEqual(result, [Arch.ARM64_V8A])

    def test_delimiter_comma(self: Self) -> None:
        result = VariantSorter.parse_archs("arm64-v8a,armeabi-v7a")
        self.assertEqual(result, [Arch.ARM64_V8A, Arch.ARMEABI_V7A])

    def test_delimiter_comma_with_spaces(self: Self) -> None:
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
        result = VariantSorter.parse_archs("ARM64-V8A", delimiter=None)
        self.assertEqual(result, [Arch.ARM64_V8A])

    def test_no_archs(self: Self) -> None:
        result = VariantSorter.parse_archs("Variant 5 APK", delimiter=None)
        self.assertEqual(result, [])

    def test_empty_string(self: Self) -> None:
        result = VariantSorter.parse_archs("", delimiter=None)
        self.assertEqual(result, [])

    def test_universal_and_noarch(self: Self) -> None:
        result = VariantSorter.parse_archs("universal noarch", delimiter=None)
        self.assertEqual(result, [Arch.UNIVERSAL, Arch.NOARCH])

    def test_bundle_universal_text(self: Self) -> None:
        result = VariantSorter.parse_archs("Variant 2 BUNDLE universal", delimiter=None)
        self.assertEqual(result, [Arch.UNIVERSAL])

    def test_mixed_archs(self: Self) -> None:
        result = VariantSorter.parse_archs("armeabi-v7a x86_64 arm64-v8a", delimiter=None)
        self.assertEqual(result, [Arch.ARMEABI_V7A, Arch.X86_64, Arch.ARM64_V8A])


class ParseDensityTests(TestCase):
    """Verify parse_density handles all density formats."""

    def test_single_480dpi(self: Self) -> None:
        d = VariantSorter.parse_density("480dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_single_320dpi(self: Self) -> None:
        d = VariantSorter.parse_density("320dpi")
        assert d is not None
        self.assertEqual(d.span, 320.0)

    def test_range_160_640dpi(self: Self) -> None:
        d = VariantSorter.parse_density("160-640dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_range_120_160dpi(self: Self) -> None:
        d = VariantSorter.parse_density("120-160dpi")
        assert d is not None
        self.assertEqual(d.span, 40.0)

    def test_nodpi_universal(self: Self) -> None:
        d = VariantSorter.parse_density("nodpi")
        assert d is not None
        self.assertEqual(d.span, float("inf"))

    def test_anydpi_universal(self: Self) -> None:
        d = VariantSorter.parse_density("anydpi")
        assert d is not None
        self.assertEqual(d.span, float("inf"))

    def test_universal_is_arch_not_density(self: Self) -> None:
        """'universal' and 'noarch' are architecture tokens, not density keywords."""
        d = VariantSorter.parse_density("universal")
        self.assertIsNone(d)

    def test_noarch_is_arch_not_density(self: Self) -> None:
        d = VariantSorter.parse_density("noarch")
        self.assertIsNone(d)

    def test_case_insensitive_universal(self: Self) -> None:
        d = VariantSorter.parse_density("NoDPI")
        assert d is not None
        self.assertEqual(d.span, float("inf"))

    def test_case_insensitive_range(self: Self) -> None:
        d = VariantSorter.parse_density("160-640DPI")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_no_density_token(self: Self) -> None:
        d = VariantSorter.parse_density("Variant 5 APK")
        self.assertIsNone(d)

    def test_empty_string(self: Self) -> None:
        d = VariantSorter.parse_density("")
        self.assertIsNone(d)

    def test_from_variant_text(self: Self) -> None:
        d = VariantSorter.parse_density("Variant 3 APK arm64-v8a 480dpi Android 5.0+")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_from_bundle_universal_text(self: Self) -> None:
        """'universal' in variant text is an arch token, not a density catch-all."""
        d = VariantSorter.parse_density("Variant 2 BUNDLE universal")
        self.assertIsNone(d)

    # ── Flexible whitespace ──────────────────────────────────────────

    def test_range_with_spaces_around_dash(self: Self) -> None:
        d = VariantSorter.parse_density("160 - 640dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_range_with_space_before_dpi(self: Self) -> None:
        d = VariantSorter.parse_density("160-640 dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_range_with_spaces_everywhere(self: Self) -> None:
        d = VariantSorter.parse_density("160 - 640 dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_single_with_space_before_dpi(self: Self) -> None:
        d = VariantSorter.parse_density("480 dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    # ── Qualitative DPI buckets ──────────────────────────────────────

    def test_mdpi(self: Self) -> None:
        d = VariantSorter.parse_density("mdpi")
        assert d is not None
        self.assertEqual(d.span, 160.0)

    def test_hdpi(self: Self) -> None:
        d = VariantSorter.parse_density("hdpi")
        assert d is not None
        self.assertEqual(d.span, 240.0)

    def test_xhdpi(self: Self) -> None:
        d = VariantSorter.parse_density("xhdpi")
        assert d is not None
        self.assertEqual(d.span, 320.0)

    def test_xxhdpi(self: Self) -> None:
        d = VariantSorter.parse_density("xxhdpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_xxxhdpi(self: Self) -> None:
        d = VariantSorter.parse_density("xxxhdpi")
        assert d is not None
        self.assertEqual(d.span, 640.0)

    def test_ldpi(self: Self) -> None:
        d = VariantSorter.parse_density("ldpi")
        assert d is not None
        self.assertEqual(d.span, 120.0)

    def test_tvdpi(self: Self) -> None:
        d = VariantSorter.parse_density("tvdpi")
        assert d is not None
        self.assertEqual(d.span, 213.0)

    def test_qualitative_case_insensitive(self: Self) -> None:
        d = VariantSorter.parse_density("HDPI")
        assert d is not None
        self.assertEqual(d.span, 240.0)

    # ── Unicode dashes ───────────────────────────────────────────────

    def test_en_dash(self: Self) -> None:
        d = VariantSorter.parse_density("160\u2013640dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_em_dash(self: Self) -> None:
        d = VariantSorter.parse_density("160\u2014640dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)

    def test_minus_sign(self: Self) -> None:
        d = VariantSorter.parse_density("160\u2212640dpi")
        assert d is not None
        self.assertEqual(d.span, 480.0)


class SortingKeyTests(TestCase):
    """Verify sorting_key produces correct tuple values from typed inputs."""

    def test_arm64_nodpi_has_primary(self: Self) -> None:
        archs = [Arch.ARM64_V8A]
        density = Density.universal()
        key = VariantSorter.sorting_key(archs, density)
        self.assertEqual(key, (True, float("inf"), 1))

    def test_no_density_fallback_to_zero(self: Self) -> None:
        archs = [Arch.ARM64_V8A, Arch.X86_64]
        key = VariantSorter.sorting_key(archs, None)
        self.assertEqual(key, (True, 0.0, 2))

    def test_no_density_default(self: Self) -> None:
        archs = [Arch.ARM64_V8A]
        key = VariantSorter.sorting_key(archs)
        self.assertEqual(key, (True, 0.0, 1))

    def test_armeabi_no_primary(self: Self) -> None:
        archs = [Arch.ARMEABI_V7A]
        density = Density.exact(480)
        key = VariantSorter.sorting_key(archs, density)
        self.assertEqual(key, (False, 480.0, 1))

    def test_more_archs_better(self: Self) -> None:
        density = Density.exact(480)
        key_a = VariantSorter.sorting_key([Arch.ARM64_V8A], density)
        key_b = VariantSorter.sorting_key([Arch.ARM64_V8A, Arch.X86_64], density)
        self.assertGreater(key_b, key_a)

    def test_primary_arch_trumps_everything(self: Self) -> None:
        density = Density.universal()
        key_a = VariantSorter.sorting_key([Arch.ARM64_V8A], density)
        key_b = VariantSorter.sorting_key([Arch.ARMEABI_V7A], density)
        self.assertGreater(key_a, key_b)

    def test_infinite_density_trumps_exact(self: Self) -> None:
        archs = [Arch.ARM64_V8A]
        key_a = VariantSorter.sorting_key(archs, Density.universal())
        key_b = VariantSorter.sorting_key(archs, Density.exact(480))
        self.assertGreater(key_a, key_b)

    def test_equal_range_and_exact_density(self: Self) -> None:
        archs = [Arch.ARM64_V8A]
        key_a = VariantSorter.sorting_key(archs, Density.range_dpi(160, 640))
        key_b = VariantSorter.sorting_key(archs, Density.exact(480))
        self.assertEqual(key_a, key_b)

    def test_noarch_is_primary(self: Self) -> None:
        archs = [Arch.NOARCH]
        key = VariantSorter.sorting_key(archs, Density.universal())
        self.assertEqual(key, (True, float("inf"), 1))

    def test_x86_is_not_primary(self: Self) -> None:
        archs = [Arch.X86]
        key = VariantSorter.sorting_key(archs)
        self.assertEqual(key, (False, 0.0, 1))

    def test_x86_64_is_not_primary(self: Self) -> None:
        archs = [Arch.X86_64]
        key = VariantSorter.sorting_key(archs)
        self.assertEqual(key, (False, 0.0, 1))

    def test_empty_arch_list(self: Self) -> None:
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
        variants = [
            ([Arch.ARMEABI_V7A], Density.exact(480)),
            ([Arch.ARM64_V8A], Density.universal()),
            ([Arch.ARM64_V8A], Density.exact(480)),
        ]
        result = sorted(variants, key=lambda v: VariantSorter.sorting_key(*v), reverse=True)
        self.assertEqual(result[0], ([Arch.ARM64_V8A], Density.universal()))

    def test_more_archs_ranks_above_fewer(self: Self) -> None:
        variants = [
            ([Arch.ARM64_V8A], Density.exact(480)),
            ([Arch.ARM64_V8A, Arch.X86_64], Density.exact(480)),
        ]
        result = sorted(variants, key=lambda v: VariantSorter.sorting_key(*v), reverse=True)
        self.assertEqual(result[0], ([Arch.ARM64_V8A, Arch.X86_64], Density.exact(480)))

    def test_noarch_fallback_ranks_low(self: Self) -> None:
        variants = [
            ([Arch.ARM64_V8A], Density.universal()),
            ([Arch.X86], Density.universal()),
        ]
        result = sorted(variants, key=lambda v: VariantSorter.sorting_key(*v), reverse=True)
        self.assertEqual(result[0], ([Arch.ARM64_V8A], Density.universal()))

    def test_density_none_causes_arch_only_sorting(self: Self) -> None:
        variants = [
            ([Arch.X86], None),
            ([Arch.ARM64_V8A, Arch.ARMEABI_V7A], None),
            ([Arch.ARM64_V8A], None),
        ]
        result = sorted(variants, key=lambda v: VariantSorter.sorting_key(*v), reverse=True)
        self.assertEqual(result[0], ([Arch.ARM64_V8A, Arch.ARMEABI_V7A], None))
        self.assertEqual(result[1], ([Arch.ARM64_V8A], None))
        self.assertEqual(result[2], ([Arch.X86], None))
