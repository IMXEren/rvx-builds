"""Check patching resource updates."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import Lock

import requests
from environs import Env
from loguru import logger

from main import get_app
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


class BuildReason(Enum):
    """Reasons why a build might be triggered."""

    FRESH_BUILD = "Fresh build (no previous record)"
    VERSION_UPDATE = "Version update"
    SOURCE_CHANGE = "Patch source changed"
    BUNDLE_COUNT_CHANGE = "Number of patch bundles changed"


@dataclass
class AppBuildInfo:
    """Information about why an app needs to be rebuilt."""

    app_name: str
    reason: BuildReason
    old_versions: list[str] = field(default_factory=list)
    new_versions: list[str] = field(default_factory=list)
    old_sources: list[str] = field(default_factory=list)
    new_sources: list[str] = field(default_factory=list)

    def get_summary(self) -> str:
        """Get a human-readable summary of the build reason."""
        if self.reason == BuildReason.FRESH_BUILD:
            versions = ", ".join(self.new_versions) if self.new_versions else "N/A"
            return f"[FRESH] No previous build -> {versions}"

        if self.reason == BuildReason.VERSION_UPDATE:
            changes = []
            for old, new in zip(self.old_versions, self.new_versions, strict=False):
                if old != new:
                    changes.append(f"{old} -> {new}")
            return f"[UPDATE] {', '.join(changes)}"

        if self.reason == BuildReason.SOURCE_CHANGE:
            return "[SOURCE] Patch source URL changed"

        if self.reason == BuildReason.BUNDLE_COUNT_CHANGE:
            return f"[BUNDLES] {len(self.old_versions)} -> {len(self.new_versions)} patch bundles"

        return f"[UNKNOWN] {self.reason.value}"


def _is_fresh_build(old_versions: list[str], old_sources: list[str]) -> bool:
    """Check if this is a fresh build with no previous record."""
    no_versions = not old_versions or all(v in ("0", "", None) for v in old_versions)
    no_sources = not old_sources or all(s in ("0", "", None) for s in old_sources)
    return no_versions or no_sources


def _detect_build_reason(
    old_versions: list[str],
    old_sources: list[str],
    new_versions: list[str],
    new_sources: list[str],
) -> BuildReason | None:
    """Detect the reason why a build should be triggered."""
    # Check for fresh build first
    if _is_fresh_build(old_versions, old_sources):
        return BuildReason.FRESH_BUILD

    # Check for bundle count change
    if len(old_versions) != len(new_versions) or len(old_sources) != len(new_sources):
        return BuildReason.BUNDLE_COUNT_CHANGE

    # Check for version or source changes
    for old_ver, old_src, new_ver, new_src in zip(
        old_versions,
        old_sources,
        new_versions,
        new_sources,
        strict=True,
    ):
        if old_src != new_src:
            return BuildReason.SOURCE_CHANGE
        if old_ver != new_ver:
            return BuildReason.VERSION_UPDATE

    return None


def _print_build_summary(build_infos: list[AppBuildInfo]) -> None:
    """Print a formatted summary of all apps that need rebuilding."""
    if not build_infos:
        logger.info("No apps need to be repatched.")
        return

    # Group by reason
    by_reason: dict[BuildReason, list[AppBuildInfo]] = {}
    for info in build_infos:
        by_reason.setdefault(info.reason, []).append(info)

    logger.info("=" * 60)
    logger.info("BUILD SUMMARY")
    logger.info("=" * 60)

    for reason in BuildReason:
        if reason not in by_reason:
            continue
        apps = by_reason[reason]
        logger.info(f"\n{reason.value} ({len(apps)} apps):")
        logger.info("-" * 40)
        for info in apps:
            logger.info(f"  {info.app_name}: {info.get_summary()}")

    logger.info("\n" + "=" * 60)
    logger.info(f"TOTAL: {len(build_infos)} apps need to be repatched")
    logger.info("=" * 60)


def check_if_build_is_required() -> bool:
    """Read resource version and determine which apps need rebuilding."""
    env = Env()
    env.read_env()
    config = RevancedConfig(env)
    build_infos: list[AppBuildInfo] = []
    resource_cache: dict[str, tuple[str, str]] = {}
    resource_lock = Lock()
    github_manager = GitHubManager(env)

    for app_name in env.list("PATCH_APPS", default_build):
        logger.info(f"Checking {app_name}")
        app_obj = get_app(config, app_name)
        old_patches_versions = github_manager.get_last_version(app_obj, patches_versions_key)
        old_patches_sources = github_manager.get_last_version_source(app_obj, patches_dl_list_key)

        # Backward compatibility for string version/source
        if isinstance(old_patches_versions, str):
            old_patches_versions = [old_patches_versions]
        if isinstance(old_patches_sources, str):
            old_patches_sources = [old_patches_sources]

        app_obj.download_patch_resources(config, resource_cache, resource_lock)

        new_patches_versions = app_obj.get_patch_bundles_versions()
        new_patches_sources = app_obj.patches_dl_list

        # Detect why build is needed
        reason = _detect_build_reason(
            old_patches_versions,
            old_patches_sources,
            new_patches_versions,
            new_patches_sources,
        )

        if reason:
            build_info = AppBuildInfo(
                app_name=app_name,
                reason=reason,
                old_versions=old_patches_versions,
                new_versions=new_patches_versions,
                old_sources=old_patches_sources,
                new_sources=new_patches_sources,
            )
            build_infos.append(build_info)
            logger.debug(f"{app_name} needs rebuild: {reason.value}")

    # Print detailed summary
    _print_build_summary(build_infos)

    if build_infos:
        app_names = [info.app_name for info in build_infos]
        print(f"PATCH_APPS={','.join(app_names)}")  # noqa: T201
        write_patch_updates_changelog(config, build_infos)
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


def write_patch_updates_changelog(config: RevancedConfig, apps: list[AppBuildInfo]) -> None:
    """Write patch updates changelog."""
    patches_dl_set: set[str] = set()
    for app_obj in apps:
        for dl in app_obj.new_sources:
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
