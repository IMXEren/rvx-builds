"""Downloader Factory."""

from loguru import logger

from src.downloader.apkcube import ApkCube
from src.downloader.apkeep import Apkeep
from src.downloader.apkmirror import ApkMirror
from src.downloader.apkpure import ApkPure
from src.downloader.github import Github
from src.downloader.gitlab import Gitlab
from src.downloader.sources import (
    APK_CUBE_BASE_URL,
    APK_MIRROR_BASE_URL,
    APK_PURE_BASE_URL,
    APKEEP,
    GITHUB_BASE_URL,
    UPTODOWN_SUFFIX,
)
from src.downloader.uptodown import UptoDown
from src.exceptions import DownloadError
lazy from src.config import RevancedConfig
lazy from src.downloader.download import Downloader


class DownloaderFactory(object):
    """Downloader Factory."""

    @staticmethod
    def create_downloader(config: RevancedConfig, apk_source: str) -> Downloader:
        """Returns appropriate downloader.

        Args:
        ----
            config : Config
            apk_source : Source URL for APK
        """
        if apk_source.startswith(GITHUB_BASE_URL):
            return Github(config)
        # GitLab app sources need release-asset discovery instead of generic HTML scraping.
        if Gitlab.is_gitlab_url(apk_source):
            return Gitlab(config)
        if apk_source.endswith(UPTODOWN_SUFFIX):
            return UptoDown(config)
        if apk_source.startswith(APK_MIRROR_BASE_URL):
            return ApkMirror(config)
        if apk_source.startswith(APK_PURE_BASE_URL):
            return ApkPure(config)
        if apk_source.startswith(APK_CUBE_BASE_URL):
            return ApkCube(config)
        if apk_source.startswith(APKEEP):
            return Apkeep(config)
        msg = "No download factory found."
        raise DownloadError(msg, url=apk_source)

    @staticmethod
    def discover_source(package_name: str) -> str:
        """Return the first mirror source that has the package, for apps without a configured source."""
        lookups = (
            ApkMirror.source_for_package,
            UptoDown.source_for_package,
            ApkCube.source_for_package,
            ApkPure.source_for_package,
        )
        for lookup in lookups:
            if source := lookup(package_name):
                logger.info(f"Found download source {source} for {package_name}")
                return source
        return ""
