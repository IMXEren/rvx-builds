"""Tests for VersionSorter.sorting_key."""

import semver

from src.apks.version_sorter import VersionSorter


class TestSortingKey:
    """Unit tests for VersionSorter.sorting_key."""

    def test_standard_semver(self) -> None:
        """sorting_key("1.2.3") returns semver.Version(1, 2, 3)."""
        result = VersionSorter.sorting_key("1.2.3")
        assert result == semver.Version(1, 2, 3)

    def test_four_part_version(self) -> None:
        """sorting_key("1.2.3.4") returns a version with build meta."""
        result = VersionSorter.sorting_key("1.2.3.4")
        assert result.major == 1
        assert result.minor == 2
        assert result.patch == 3
        assert result.build == "4"

    def test_prerelease(self) -> None:
        """sorting_key("1.2.3-beta") returns a version with prerelease."""
        result = VersionSorter.sorting_key("1.2.3-beta")
        assert result.major == 1
        assert result.minor == 2
        assert result.patch == 3
        # packaging.version encodes "beta" as pre-release letter 'b' with implicit version 0 → "b0"
        assert result.prerelease == "b0"

    def test_bogus_version(self) -> None:
        """sorting_key("bogus") returns semver.Version(0, 0, 0)."""
        result = VersionSorter.sorting_key("bogus")
        assert result == semver.Version(0, 0, 0)

    def test_empty_string(self) -> None:
        """sorting_key("") returns semver.Version(0, 0, 0) without raising."""
        result = VersionSorter.sorting_key("")
        assert result == semver.Version(0, 0, 0)

    def test_sort_integration(self) -> None:
        """Sorted versions with standard semver strings order correctly."""
        versions = ["1.0.0", "2.0.0", "0.5.0"]
        result = sorted(versions, key=VersionSorter.sorting_key)
        assert result == ["0.5.0", "1.0.0", "2.0.0"]

    def test_sort_with_prereleases(self) -> None:
        """Sorted versions including prereleases order correctly."""
        versions = ["1.0.0", "1.0.0-rc.1", "1.0.0-beta"]
        result = sorted(versions, key=VersionSorter.sorting_key)
        # beta < rc.1 < final release
        assert result == ["1.0.0-beta", "1.0.0-rc.1", "1.0.0"]
