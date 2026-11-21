"""App version sorting and comparison."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

import packaging.version
import semver

if TYPE_CHECKING:
    from collections.abc import Collection

    from src.apks.variant_sorter import Arch

# Version name to arch to the version codes the patches target.
type VersionCodes = dict[str, dict[Arch, set[int]]]


class VersionSorter:
    """Ranks app versions using semver-compatible comparison."""

    _numeric_prefix = re.compile(r"^\d+(?:\.\d+)*")

    @staticmethod
    def sorting_key(version: str) -> semver.Version:
        """Return a semver.Version suitable for sort(key=...).

        Handles standard semver and packaging.version formats. Unknown suffixes
        retain their numeric release components; names without a numeric prefix
        sort at the end.
        """
        min_components = 3
        try:
            ver = packaging.version.parse(version)
            components = list(ver.release[:3])
            while len(components) < min_components:
                components.append(0)
            major, minor, patch = components
            pre = "".join([str(i) for i in ver.pre]) if ver.pre else None
            extra_digits = ".".join(map(str, ver.release[3:])) if len(ver.release) > min_components else None
            build_components = []
            if extra_digits:
                build_components.append(extra_digits)
            if ver.dev:
                build_components.append(str(ver.dev))
            build_meta = ".".join(build_components) if build_components else None
            return semver.Version(major, minor, patch, prerelease=pre, build=build_meta)
        except (packaging.version.InvalidVersion, ValueError):
            pass

        try:
            return semver.Version.parse(version)
        except ValueError:
            match = VersionSorter._numeric_prefix.match(version)
            if match:
                components = [int(part) for part in match[0].split(".")]
                components = [*components, 0, 0, 0][:3]
                return semver.Version(*components)
            return semver.Version(0, 0, 0)

    @staticmethod
    def target_codes(version_codes: VersionCodes, version: str, archs: Collection[str]) -> set[int]:
        """Return the version codes advertised for the archs being built."""
        return {code for arch, codes in version_codes.get(version, {}).items() if arch in archs for code in codes}

    @staticmethod
    def candidate_key(
        version: str,
        version_codes: VersionCodes,
        archs: Collection[str],
    ) -> tuple[bool, int, semver.Version]:
        """Prefer the highest version code advertised for the built archs, then the version name."""
        codes = VersionSorter.target_codes(version_codes, version, archs)
        return bool(codes), max(codes) if codes else 0, VersionSorter.sorting_key(version)
