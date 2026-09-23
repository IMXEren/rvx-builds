"""Github Downloader."""

import re
from typing import Self
from urllib.parse import urlparse

import requests
from loguru import logger

from src.app import APP
from src.config import RevancedConfig
from src.downloader.download import Downloader
from src.exceptions import DownloadError
from src.utils import handle_request_response, request_timeout, update_changelog


class Github(Downloader):
    """Files downloader."""

    MIN_PATH_SEGMENTS = 2  # Minimum path segments for valid GitHub URL
    RELEASE_PAGE_SIZE = 100  # GitHub's maximum page size, so skipping drafts costs as few requests as possible.

    @staticmethod
    def _get_headers(github_pat: str | None) -> dict[str, str]:
        """Build GitHub API headers, including the personal access token when provided."""
        headers = {
            "Content-Type": "application/vnd.github.v3+json",
        }
        if github_pat:
            logger.debug("Using personal access token")
            headers["Authorization"] = f"Bearer {github_pat}"
        return headers

    def latest_version(self: Self, app: APP, **kwargs: dict[str, str]) -> tuple[str, str]:
        """Function to download files from GitHub repositories.

        :param app: App to download
        """
        logger.debug(f"Trying to download {app.app_name} from github")
        if self.config.dry_run:
            logger.debug(f"Skipping download of {app.app_name}. File already exists or dry running.")
            return app.app_name, f"local://{app.app_name}"
        owner = str(kwargs["owner"])
        repo_name = str(kwargs["name"])
        repo_url = f"https://api.github.com/repos/{owner}/{repo_name}/releases/latest"
        response = requests.get(repo_url, headers=Github._get_headers(self.config.github_pat), timeout=request_timeout)
        handle_request_response(response, repo_url)
        if repo_name == "revanced-patches":
            download_url = response.json()["assets"][1]["browser_download_url"]
        else:
            download_url = response.json()["assets"][0]["browser_download_url"]
        update_changelog(f"{owner}/{repo_name}", response.json())
        self._download(download_url, file_name=app.app_name)
        return app.app_name, download_url

    @staticmethod
    def _get_latest_release_tag(github_repo_owner: str, github_repo_name: str, github_pat: str | None) -> str:
        """Resolve the newest published release tag, including pre-releases.

        GitHub exposes no "latest including pre-releases" endpoint, so the releases
        listing is walked newest-first until a published entry is found.
        """
        first_page_url = (
            f"https://api.github.com/repos/{github_repo_owner}/{github_repo_name}"
            f"/releases?per_page={Github.RELEASE_PAGE_SIZE}"
        )
        api_url: str | None = first_page_url
        while api_url:
            response = requests.get(api_url, headers=Github._get_headers(github_pat), timeout=request_timeout)
            handle_request_response(response, api_url)
            # Draft releases have no published git tag, so they cannot be used as a release reference.
            published_release = next((release for release in response.json() if not release["draft"]), None)
            if published_release is not None:
                return str(published_release["tag_name"])
            # A page made up entirely of drafts must not end the search while older pages remain.
            api_url = response.links.get("next", {}).get("url")
        msg = f"No published releases found for {github_repo_owner}/{github_repo_name}"
        raise DownloadError(msg, url=first_page_url)

    @staticmethod
    def _extract_repo_owner_and_tag(url: str, github_pat: str | None) -> tuple[str, str, str]:
        """Extract repo owner and url from github url."""
        parsed_url = urlparse(url)
        path_segments = parsed_url.path.strip("/").split("/")
        if len(path_segments) < Github.MIN_PATH_SEGMENTS:
            msg = f"Invalid GitHub URL format: {url}"
            raise DownloadError(msg)
        github_repo_owner = path_segments[0]
        github_repo_name = path_segments[1]
        tag_position = 3
        if len(path_segments) > tag_position and path_segments[3] == "latest-prerelease":
            logger.info(f"Including pre-releases/beta for {github_repo_name} selection.")
            release_tag = f"tags/{Github._get_latest_release_tag(github_repo_owner, github_repo_name, github_pat)}"
        else:
            release_tag = next(
                (f"tags/{path_segments[i + 1]}" for i, segment in enumerate(path_segments) if segment == "tag"),
                "latest",
            )
        return github_repo_owner, github_repo_name, release_tag

    @staticmethod
    def _get_release_assets(
        github_repo_owner: str,
        github_repo_name: str,
        release_tag: str,
        asset_filter: str,
        config: RevancedConfig,
    ) -> tuple[str, str]:
        """Get assets from given tag."""
        api_url = f"https://api.github.com/repos/{github_repo_owner}/{github_repo_name}/releases/{release_tag}"
        response = requests.get(api_url, headers=Github._get_headers(config.github_pat), timeout=request_timeout)
        handle_request_response(response, api_url)
        update_changelog(f"{github_repo_owner}/{github_repo_name}", response.json())
        assets = response.json()["assets"]
        try:
            filter_pattern = re.compile(asset_filter)
        except re.error as e:
            msg = f"Invalid regex {asset_filter} pattern provided."
            raise DownloadError(msg) from e
        for asset in assets:
            assets_url = asset["browser_download_url"]
            assets_name = asset["name"]
            if filter_pattern.search(assets_url):
                logger.debug(f"Found {assets_name} to be downloaded from {assets_url}")
                # Return the full asset URL directly rather than the regex match group.
                # This decouples the filter pattern from URL extraction and aligns with GitLab's behavior.
                return response.json()["tag_name"], assets_url
        return "", ""

    @staticmethod
    def patch_resource(repo_url: str, assets_filter: str, config: RevancedConfig) -> tuple[str, str]:
        """Fetch patch resource from repo url."""
        repo_owner, repo_name, latest_tag = Github._extract_repo_owner_and_tag(repo_url, config.github_pat)
        return Github._get_release_assets(repo_owner, repo_name, latest_tag, assets_filter, config)
