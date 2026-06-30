"""App version sorting and comparison."""

from __future__ import annotations

import packaging.version
import semver


class VersionSorter:
    """Ranks app versions using semver-compatible comparison."""

    @staticmethod
    def sorting_key(version: str) -> semver.Version:
        """Return a semver.Version suitable for sort(key=...).

        Handles standard semver and packaging.version formats. Falls back to
        semver.Version.parse() if the first attempt fails, and finally to
        semver.Version(0, 0, 0) as a last-resort minimum so unparseable
        versions still sort without raising.
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
            return semver.Version(0, 0, 0)
