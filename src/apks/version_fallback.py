"""Version-stepping fallback for the 404 / not-found case."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from src.apks.version_sorter import VersionSorter
from src.exceptions import VersionNotFoundError

if TYPE_CHECKING:
    from src.app import APP
    from src.downloader.download import Downloader


class VersionFallback:
    """Step through compatible versions when the latest version's page 404s.

    Only catches VersionNotFoundError. Network errors, download errors after
    the page was found, and other exceptions propagate immediately so callers
    can decide how to handle them.
    """

    @staticmethod
    def run(
        app: APP,
        downloader: Downloader,
        versions: list[str],
        **kwargs: dict[str, Any],
    ) -> tuple[str, str]:
        """Try downloading each version in descending semver order.

        :param app: The APP instance being downloaded.
        :param downloader: The Downloader instance to use.
        :param versions: Candidate versions in any order. Will be sorted
            descending using ``VersionSorter.sorting_key`` before iteration.
        :param kwargs: Extra kwargs forwarded to ``downloader.download``.
        :returns: The ``(file_name, dl_url)`` tuple from the successful attempt.
        :raises ValueError: If ``versions`` is empty.
        :raises VersionNotFoundError: The last such error if every version 404s.
        """
        if not versions:
            msg = "VersionFallback.run requires a non-empty versions list"
            raise ValueError(msg)
        # Sort descending so the newest is tried first.
        ordered = sorted(versions, key=VersionSorter.sorting_key, reverse=True)
        last_error: VersionNotFoundError | None = None
        for version in ordered:
            try:
                result = downloader.download(version, app, **kwargs)
            except VersionNotFoundError as exc:
                logger.info(
                    f"Version {version} not found for {app.app_name}; stepping down to next candidate",
                )
                last_error = exc
                continue
            app.app_version = version
            logger.info(f"Fell back to version {version} for {app.app_name}")
            return result
        raise cast("VersionNotFoundError", last_error)
