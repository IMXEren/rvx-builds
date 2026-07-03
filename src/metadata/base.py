"""Base class for source release metadata."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Self

if TYPE_CHECKING:
    from collections.abc import Iterable
    from datetime import datetime


class SourceType(Enum):
    """Known source forges for release metadata."""

    GITHUB = "github"
    """GitHub (github.com)."""
    GITLAB = "gitlab"
    """GitLab (gitlab.com)."""


class SourceMetadata:
    """Base class for release metadata from any source (GitHub, GitLab, etc.).

    Subclasses are dataclasses that override ``from_json`` for their
    respective API response formats.

    """

    name: str
    """Identifier for the source (e.g., ``owner/repo`` or ``group/project``)."""
    tag: str
    """Release tag name."""
    body: str
    """Release description / changelog body."""
    html_url: str
    """Public URL of the release."""
    published_at: datetime
    """When the release was published."""
    source_type: SourceType
    """Which forge this metadata came from."""

    @classmethod
    def from_json(cls, response: dict[str, str]) -> Self:
        """Create an instance from a normalized API JSON response.

        Subclasses must override this to handle their URL format.

        Parameters
        ----------
        response : dict[str, str]
            Normalized JSON response containing ``html_url``, ``tag_name``,
            ``body``, and ``published_at`` keys.

        Returns
        -------
        Self
            A new metadata instance.

        Raises
        ------
        NotImplementedError
            Always — subclasses must implement this method.

        """
        msg = f"{cls.__name__}.from_json() must be implemented by subclass"
        raise NotImplementedError(msg)

    @classmethod
    def for_response(cls, response: dict[str, str]) -> SourceMetadata:
        """Create the correct metadata subclass from a normalized response.

        Dispatches to the appropriate subclass by trying each known
        ``from_json``.  The subclass whose ``source_type`` domain appears
        in the response URL wins.

        Parameters
        ----------
        response : dict[str, str]
            Normalized JSON response with ``html_url``, ``tag_name``,
            ``body``, and ``published_at``.

        Returns
        -------
        SourceMetadata
            A ``GithubSourceMetadata`` or ``GitlabSourceMetadata`` instance.

        Raises
        ------
        KeyError
            If required keys are missing.
        ValueError
            If the URL does not match a known source.

        """
        html_url = response.get("html_url", "")
        for sub in cls.__subclasses__():
            if hasattr(sub, "_domain") and sub._domain in html_url:  # type: ignore[attr-defined]
                return sub.from_json(response)
        msg = f"Unknown source for URL: {html_url}"
        raise ValueError(msg)

    @staticmethod
    def is_valid_source(url: str) -> bool:
        """Check whether *url* points to a known source.

        Parameters
        ----------
        url : str
            A tool download URL to inspect.

        Returns
        -------
        bool
            ``True`` if the URL belongs to a supported forge.

        """
        return any(
            hasattr(sub, "_domain") and sub._domain in url  # type: ignore[attr-defined]
            for sub in SourceMetadata.__subclasses__()
        )

    def get_release_date(self) -> str:
        """Return the release date as a formatted UTC string.

        Returns
        -------
        str
            The published date formatted as ``"Month DD, YYYY, HH:MM:SS UTC"``.

        """
        return self.published_at.strftime("%B %d, %Y, %H:%M:%S UTC")

    def to_dict(self) -> dict[str, object]:
        """Serialize metadata to a JSON-safe dictionary.

        Returns
        -------
        dict[str, object]
            Dictionary with all metadata fields ready for JSON encoding.

        """
        return {
            "name": self.name,
            "tag": self.tag,
            "body": self.body,
            "html_url": self.html_url,
            "published_at": self.published_at.isoformat(),
            "source_type": self.source_type.value,
        }

    @staticmethod
    def sort_by_latest_release(items: Iterable[SourceMetadata]) -> list[SourceMetadata]:
        """Sort metadata items by release date, latest first.

        Parameters
        ----------
        items : Iterable[SourceMetadata]
            The metadata items to sort.

        Returns
        -------
        list[SourceMetadata]
            Items sorted by ``published_at`` descending.

        """
        return sorted(items, key=lambda m: m.published_at, reverse=True)
