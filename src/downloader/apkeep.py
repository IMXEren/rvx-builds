"""Apkeep Downloader Class."""

import zipfile
from subprocess import PIPE, Popen
from time import perf_counter
from typing import Any, Self

from loguru import logger

from src.app import APP
from src.downloader.download import Downloader
from src.exceptions import DownloadError


class Apkeep(Downloader):
    """Apkeep-based Downloader."""

    def _run_apkeep(self: Self, package_name: str, version: str = "", extra_options: list[str] | None = None) -> str:
        """Run apkeep CLI to fetch APK from Google Play."""
        email = self.config.env.str("APKEEP_EMAIL")
        token = self.config.env.str("APKEEP_TOKEN")

        if not email or not token:
            msg = "APKEEP_EMAIL and APKEEP_TOKEN must be set in environment."
            raise DownloadError(msg)

        file_name = f"{package_name}.apk"
        file_path = self.config.temp_folder / file_name
        folder_path = self.config.temp_folder / package_name
        zip_path = self.config.temp_folder / f"{package_name}.zip"

        # If already downloaded, return it
        if file_path.exists():
            logger.debug(f"{file_name} already downloaded.")
            return file_name
        if zip_path.exists():
            logger.debug(f"{zip_path.name} already zipped and exists.")
            return zip_path.name

        options = ["split_apk=true", *(extra_options or [])]

        # Build apkeep command
        cmd = [
            "apkeep",
            "-a",
            f"{package_name}@{version}" if version and version != "latest" else package_name,
            "-d",
            "google-play",
            "-e",
            email,
            "-t",
            token,
            "-o",
            ",".join(options),
            self.config.temp_folder_name,
        ]
        # Keep the exact execution command separate from the log-safe command so credentials never reach CI logs.
        safe_cmd = [*cmd]
        safe_cmd[6] = "<redacted-email>"
        safe_cmd[8] = "<redacted-token>"
        logger.debug(f"Running command: {safe_cmd}")

        start = perf_counter()
        process = Popen(cmd, stdout=PIPE)
        output = process.stdout
        if not output:
            msg = "Failed to send request for patching."
            raise DownloadError(msg)
        for line in output:
            logger.debug(line.decode(), flush=True, end="")
        process.wait()
        if process.returncode != 0:
            msg = f"Command failed with exit code {process.returncode} for app {package_name}"
            raise DownloadError(msg)
        logger.info(f"Downloading completed for app {package_name} in {perf_counter() - start:.2f} seconds.")

        if file_path.exists():
            return file_name
        if folder_path.exists() and folder_path.is_dir():
            # Zip the folder
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file in folder_path.rglob("*"):
                    arcname = file.relative_to(self.config.temp_folder)
                    zipf.write(file, arcname)
            logger.debug(f"Zipped {folder_path} to {zip_path}")
            return zip_path.name
        msg = "APK file or folder not found after apkeep execution."
        raise DownloadError(msg)

    def latest_version(self: Self, app: APP, **kwargs: Any) -> tuple[str, str]:
        """Download latest version from Google Play via Apkeep."""
        extra_options = list(kwargs.get("extra_options") or [])
        device_name: str | None = getattr(app, "apkeep_device_name", None)
        device_file: str | None = getattr(app, "apkeep_device_file", None)
        if device_name or device_file:
            extra_options.append(f"device={device_name or 'default'}")
        if device_file:
            extra_options.append(f"device_properties_file={device_file}")

        file_name = self._run_apkeep(app.package_name, extra_options=extra_options)
        logger.info(f"Got file name as {file_name}")
        return file_name, f"apkeep://google-play/{app.package_name}"
