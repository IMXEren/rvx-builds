"""Github Source Metadata."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self


@dataclass(unsafe_hash=True)
class GithubSourceMetadata:
    """Represents github release tag metadata."""

    name: str
    tag: str
    body: str
    html_url: str
    published_at: datetime

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
        published_at = datetime.strptime(response["published_at"], "%Y-%m-%dT%H:%M:%SZ").astimezone(UTC)
        return cls(name, tag, body, html_url, published_at)

    def get_release_date(self) -> str:
        """Return the release date as a formatted UTC string.

        Returns
        -------
        str
            The published date formatted as "Month DD, YYYY, HH:MM:SS UTC".
        """
        return self.published_at.strftime("%B %d, %Y, %H:%M:%S UTC")

    @staticmethod
    def sort_by_latest_release(items: Iterable["GithubSourceMetadata"]) -> list["GithubSourceMetadata"]:
        """Sort by latest release first."""
        return sorted(items, key=lambda m: m.published_at, reverse=True)
