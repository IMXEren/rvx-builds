"""Tests for VersionSorter.sorting_key."""

# ruff: noqa: PT009

from typing import Self
from unittest import TestCase

import semver

from src.apks.version_sorter import VersionSorter


class TestSortingKey(TestCase):
    """Unit tests for VersionSorter.sorting_key."""

    def test_standard_semver(self: Self) -> None:
        """A standard version retains its three numeric components."""
        self.assertEqual(semver.Version(1, 2, 3), VersionSorter.sorting_key("1.2.3"))

    def test_four_part_version(self: Self) -> None:
        """The fourth component is retained as build metadata."""
        result = VersionSorter.sorting_key("1.2.3.4")
        self.assertEqual((1, 2, 3, "4"), (result.major, result.minor, result.patch, result.build))

    def test_prerelease(self: Self) -> None:
        """PEP 440 beta maps to the corresponding SemVer prerelease."""
        result = VersionSorter.sorting_key("1.2.3-beta")
        self.assertEqual((1, 2, 3), (result.major, result.minor, result.patch))
        self.assertEqual("b0", result.prerelease)

    def test_bogus_version(self: Self) -> None:
        """A version with no numeric prefix sorts last."""
        self.assertEqual(semver.Version(0, 0, 0), VersionSorter.sorting_key("bogus"))

    def test_empty_string(self: Self) -> None:
        """An empty version sorts last without raising."""
        self.assertEqual(semver.Version(0, 0, 0), VersionSorter.sorting_key(""))

    def test_sort_integration(self: Self) -> None:
        """Standard versions sort in ascending order."""
        versions = ["1.0.0", "2.0.0", "0.5.0"]
        self.assertEqual(["0.5.0", "1.0.0", "2.0.0"], sorted(versions, key=VersionSorter.sorting_key))

    def test_sort_with_prereleases(self: Self) -> None:
        """Prereleases sort before their final release."""
        versions = ["1.0.0", "1.0.0-rc.1", "1.0.0-beta"]
        self.assertEqual(["1.0.0-beta", "1.0.0-rc.1", "1.0.0"], sorted(versions, key=VersionSorter.sorting_key))

    def test_unknown_suffix_keeps_numeric_release_order(self: Self) -> None:
        """Unknown channel suffixes cannot erase the advertised release numbers."""
        versions = ["12.19.1-release.0", "12.41.0-prod.01", "12.43.0-prod.01"]
        self.assertEqual(
            ["12.43.0-prod.01", "12.41.0-prod.01", "12.19.1-release.0"],
            sorted(versions, key=VersionSorter.sorting_key, reverse=True),
        )
