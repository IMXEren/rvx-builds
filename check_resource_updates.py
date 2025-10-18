"""Check patching resource updates."""

from pathlib import Path
from threading import Lock

import requests
from environs import Env
from loguru import logger

from main import get_app
from src.app import APP
from src.config import RevancedConfig
from src.downloader.github import Github
from src.manager.github import GitHubManager
from src.metadata.github import GithubSourceMetadata
from src.utils import (
    default_build,
    format_changelog,
    handle_request_response,
    patches_dl_list_key,
    patches_versions_key,
    request_timeout,
)


def check_if_build_is_required() -> bool:
    """Read resource version."""
    env = Env()
    env.read_env()
    config = RevancedConfig(env)
    needs_to_repatched: list[APP] = []
    resource_cache: dict[str, tuple[str, str]] = {}
    resource_lock = Lock()
    for app_name in env.list("PATCH_APPS", default_build):
        logger.info(f"Checking {app_name}")
        app_obj = get_app(config, app_name)
        old_patches_versions = GitHubManager(env).get_last_version(app_obj, patches_versions_key)
        old_patches_sources = GitHubManager(env).get_last_version_source(app_obj, patches_dl_list_key)

        # Backward compatibility for string version/source
        if isinstance(old_patches_versions, str):
            old_patches_versions = [old_patches_versions]
        if isinstance(old_patches_sources, str):
            old_patches_sources = [old_patches_sources]

        app_obj.download_patch_resources(config, resource_cache, resource_lock)

        new_patches_versions = app_obj.get_patch_bundles_versions()
        if len(old_patches_versions) != len(new_patches_versions) or len(old_patches_sources) != len(
            app_obj.patches_dl_list,
        ):
            caused_by = {
                "app_name": app_name,
                "patches": {
                    "old_versions": old_patches_versions,
                    "old_bundles": old_patches_sources,
                    "new_versions": new_patches_versions,
                    "new_bundles": app_obj.patches_dl_list,
                },
            }
            logger.info(
                f"New build can be triggered due to change in number of patch bundles or sources, info: {caused_by}",
            )
            needs_to_repatched.append(app_obj)
            continue

        for old_version, old_source, new_version, new_source in zip(
            old_patches_versions,
            old_patches_sources,
            new_patches_versions,
            app_obj.patches_dl_list,
            strict=True,
        ):
            if GitHubManager(env).should_trigger_build(
                old_version,
                old_source,
                new_version,
                new_source,
            ):
                caused_by = {
                    "app_name": app_name,
                    "patches": {
                        "old": old_version,
                        "new": new_version,
                    },
                }
                logger.info(f"New build can be triggered caused by {caused_by}")
                needs_to_repatched.append(app_obj)
                break
    needs_to_repatched_names = [app.app_name for app in needs_to_repatched]
    logger.info(f"{needs_to_repatched_names} are need to repatched.")
    if needs_to_repatched:
        print(f"PATCH_APPS={','.join(needs_to_repatched_names)}")  # noqa: T201
        write_patch_updates_changelog(config, needs_to_repatched)
        return True
    return False


def _fetch_metadata(url: str, access_token: str | None = None) -> GithubSourceMetadata:
    owner, repo_name, release_tag = Github._extract_repo_owner_and_tag(url)  # noqa: SLF001
    repo_url = f"https://api.github.com/repos/{owner}/{repo_name}/releases/{release_tag}"
    headers = {
        "Content-Type": "application/vnd.github.v3+json",
    }
    if access_token:
        logger.debug("Using personal access token")
        headers["Authorization"] = f"Bearer {access_token}"
    logger.debug(f"Fetching metadata from {repo_url}")
    response = requests.get(repo_url, headers=headers, timeout=request_timeout)
    handle_request_response(response, repo_url)
    return GithubSourceMetadata.from_json(response.json())


def write_patch_updates_changelog(config: RevancedConfig, apps: list[APP]) -> None:
    """Write patch updates changelog."""
    patches_dl_set: set[str] = set()
    for app_obj in apps:
        for dl in app_obj.patches_dl_list:
            if dl.startswith("https://github.com/"):
                patches_dl_set.add(dl)

    metadata_set: set[GithubSourceMetadata] = set()
    for dl in patches_dl_set:
        metadata_set.add(_fetch_metadata(dl, config.personal_access_token))

    changelog_doc = ""
    changelog_doc_file = "patch-updates.md"
    sorted_metadata_list = GithubSourceMetadata.sort_by_latest_release(metadata_set)
    if sorted_metadata_list:
        logger.info(f"Writing patch updates changelog to {changelog_doc_file}.")
    for app_data in sorted_metadata_list:
        changelog_doc += format_changelog(app_data)
    with Path(changelog_doc_file).open("w", encoding="utf_8") as file1:
        file1.write(changelog_doc)


check_if_build_is_required()
