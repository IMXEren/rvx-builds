"""App version sorting and comparison."""

from __future__ import annotations

import re

import packaging.version
import semver


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
    def candidate_key(version: str, version_codes: dict[str, int]) -> tuple[bool, int, semver.Version]:
        """Prefer an advertised Android version code, then the version name."""
        code = version_codes.get(version)
        return code is not None, code if code is not None else 0, VersionSorter.sorting_key(version)
