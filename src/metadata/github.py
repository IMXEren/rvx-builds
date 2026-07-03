"""Github Source Metadata."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Self

from src.metadata.base import SourceMetadata, SourceType


@dataclass(unsafe_hash=True)
class GithubSourceMetadata(SourceMetadata):
    """Represents github release tag metadata."""

    _domain: str = field(default="github.com", init=False, repr=False)
    """Domain used by ``SourceMetadata.for_response`` to dispatch."""

    name: str
    tag: str
    body: str
    html_url: str
    published_at: datetime
    source_type: SourceType = field(default=SourceType.GITHUB)

    @classmethod
    def from_json(cls: type[Self], response: dict[str, str]) -> Self:
        """Create a GithubSourceMetadata instance from a GitHub release JSON response.

        Parameters
        ----------
        response : dict[str, str]
            JSON response for a GitHub release as returned by the API; expected to
            contain the keys 'html_url', 'tag_name', 'body' and 'published_at'.

        Returns
        -------
        GithubSourceMetadata
            A new instance populated from the response.

        Raises
        ------
        KeyError
            If required keys are missing in the response.
        """
        name = "/".join(response["html_url"].split("/")[3:5])
        tag = response["tag_name"]
        body = response["body"]
        html_url = response["html_url"]
        published_at = datetime.fromisoformat(response["published_at"]).astimezone(UTC)
        return cls(name, tag, body, html_url, published_at)
