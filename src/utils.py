"""Utilities."""
from typing import Dict

from loguru import logger
from requests import Response

default_build = [
    "youtube",
    "youtube_music"
]
possible_archs = ["armeabi-v7a", "x86", "x86_64", "arm64-v8a"]


def update_changelog(name: str, response: Dict[str, str]) -> None:
    """Updated Changelog."""
    parent_repo = "https://github.com/nikhilbadyal/docker-py-revanced"
    file1 = open("changelog.md", "a", encoding="utf_8")
    collapse_start = f"\n<details> <summary>👀 {name} </summary>\n\n"
    release_version = (
        f"**Release Version** - [{response['tag_name']}]({response['html_url']})<br>"
    )
    change_log = f"**Changelog** -<br> {response['body']}"
    publish_time = f"**Published at** -<br> {response['published_at']}"
    footer = (
        f"<br><sub>Change logs generated by [Docker Py Revanced]({parent_repo})</sub>\n"
    )
    collapse_end = "</details>"
    change_log = (
        collapse_start
        + release_version
        + change_log
        + publish_time
        + footer
        + collapse_end
    )
    file1.write(change_log)
    file1.close()


class AppNotFound(ValueError):
    """Not a valid Revanced App."""

    pass


class PatcherDownloadFailed(Exception):
    """Not a valid Revanced App."""

    pass


def handle_response(response: Response) -> None:
    """Handle Get Request Response."""
    response_code = response.status_code
    if response_code != 200:
        logger.error(response.text)
        exit(1)
