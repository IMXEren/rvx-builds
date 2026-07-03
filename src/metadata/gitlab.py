"""GitLab Source Metadata."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self
from urllib.parse import urlparse

from src.metadata.base import SourceMetadata, SourceType


@dataclass(unsafe_hash=True)
class GitlabSourceMetadata(SourceMetadata):
    """Represents GitLab release tag metadata.

    The ``name`` field is formatted as ``group/project`` (e.g.,
    ``inotia00/revanced-patches``) — the same shape as GitHub's
    ``owner/repo`` so both can be matched uniformly in per-app changelogs.
    """

    _domain: str = field(default="gitlab.com", init=False, repr=False)
    """Domain used by ``SourceMetadata.for_response`` to dispatch."""

    name: str
    tag: str
    body: str
    html_url: str
    published_at: datetime
    source_type: SourceType = field(default=SourceType.GITLAB)

    @classmethod
    def from_json(cls, response: dict[str, str]) -> Self:
        """Create a GitlabSourceMetadata instance from a normalized GitLab release response.

        Parameters
        ----------
        response : dict[str, str]
            Normalized JSON response containing ``html_url``, ``tag_name``,
            ``body``, and ``published_at`` keys (as produced by
            ``Gitlab._normalize_changelog_response``).

        Returns
        -------
        GitlabSourceMetadata
            A new instance populated from the response.

        Raises
        ------
        KeyError
            If required keys are missing.
        """
        html_url = response["html_url"]
        parsed = urlparse(html_url)
        # Extract group/project from paths like /group/project/-/releases/tag
        path_parts = parsed.path.strip("/").split("/")
        _min_path_segments = 2
        name = "/".join(path_parts[:_min_path_segments]) if len(path_parts) >= _min_path_segments else html_url

        tag = response["tag_name"]
        body = response["body"]
        published_at = datetime.fromisoformat(response["published_at"]).astimezone(UTC)
        return cls(name, tag, body, html_url, published_at)
