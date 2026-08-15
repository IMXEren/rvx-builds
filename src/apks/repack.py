"""Repack split apks."""

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from loguru import logger
from pyaxmlparser import APK
from pyaxmlparser.axmlprinter import AXMLPrinter

from src.apks.silence import silence_pyaxmlparser

# All standard Android architectures and screen densities
STANDARD_ARCHS = {"armeabi", "armeabi_v7a", "arm64_v8a", "x86", "x86_64", "mips", "mips64"}
STANDARD_DPIS = {"ldpi", "mdpi", "tvdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi", "anydpi", "nodpi"}


def get_dpi_modifier(density: int) -> str:
    """Maps a raw density integer from device.json to the standard Android DPI modifier."""
    dpis = {120: "ldpi", 160: "mdpi", 213: "tvdpi", 240: "hdpi", 320: "xhdpi", 480: "xxhdpi", 640: "xxxhdpi"}
    closest = min(dpis.keys(), key=lambda k: abs(k - density))
    return dpis[closest]


def get_filters(device_spec_path: Path) -> tuple[set[str], set[str]]:
    """Generates the allowlists from either a device-spec.json."""
    allowed_arch: set[str] = set()
    allowed_dpi = {"nodpi", "anydpi"}

    with device_spec_path.open() as f:
        spec = json.load(f)

    allowed_arch.update(abi.replace("-", "_") for abi in spec.get("supportedAbis", []))

    if "screenDensity" in spec:
        dpi: int | str = spec["screenDensity"]
        if isinstance(dpi, int):
            allowed_dpi.add(get_dpi_modifier(dpi))
        elif dpi in STANDARD_DPIS:
            allowed_dpi.add(dpi)

    return allowed_arch, allowed_dpi


def _should_keep(modifier: str, allowed_arch: set[str], allowed_dpi: set[str]) -> bool:
    keep = False
    if modifier in STANDARD_ARCHS:
        if modifier in allowed_arch:
            keep = True
    elif modifier in STANDARD_DPIS:
        if modifier in allowed_dpi:
            keep = True
    else:
        # It is a language or feature module
        keep = True
    return keep


def _normalized_version(version: object) -> str | None:
    """Return a non-empty manifest version as text."""
    normalized = str(version).strip() if version is not None else ""
    return normalized or None


def get_apk_version(file_path: Path) -> str | None:
    """Read the version name from a downloaded APK or an APK inside a split bundle."""
    if not file_path.exists():
        return None

    try:
        with zipfile.ZipFile(file_path) as archive:
            if "AndroidManifest.xml" in archive.namelist():
                with silence_pyaxmlparser():
                    return _normalized_version(APK(file_path).version_name)

            apk_items = [item for item in archive.infolist() if item.filename.lower().endswith(".apk")]
            for item in apk_items:
                try:
                    apk_data = archive.read(item)
                    with silence_pyaxmlparser():
                        version = _normalized_version(APK(apk_data, raw=True).version_name)
                    if version:
                        return version
                except Exception as e:  # noqa: BLE001  # pyaxmlparser raises generic errors
                    logger.debug("Failed to read version from inner APK {}: {}", item.filename, e)
    except Exception as e:  # noqa: BLE001  # downloaded files and pyaxmlparser can fail in several ways
        logger.warning("Failed to inspect downloaded APK version from {}: {}", file_path.name, e)

    return None


def _get_package_name(zin: zipfile.ZipFile) -> str | None:
    """Read the package name from any APK inside a bundle zip."""
    for item in zin.infolist():
        if not item.filename.endswith(".apk"):
            continue
        try:
            with zin.open(item.filename) as apk_file, zipfile.ZipFile(apk_file) as inner_zip:
                manifest_bytes = inner_zip.read("AndroidManifest.xml")
            with silence_pyaxmlparser():
                axml = AXMLPrinter(manifest_bytes)
            manifest_xml = ET.fromstring(axml.get_xml())  # noqa: S314
            package_name = manifest_xml.attrib.get("package")
            if package_name:
                return package_name
        except Exception as e:  # noqa: BLE001  # pyaxmlparser raises generic errors
            logger.warning("Failed to read package name from inner APK: {}, Error: {}", item.filename, e)
            continue
    return None


def repack_apks(input_zip: Path, output_zip: Path, device_spec_path: Path) -> bool:
    """Repack apks to include only necessary archs, density (dpi) and languages (ALL) from the `device-spec.json`."""
    allowed_arch, allowed_dpi = get_filters(device_spec_path)

    if any([len(allowed_arch) == 0, len(allowed_dpi) == 0]):
        # Repack definitely needs all of them to be non-zero, for the apk to actually work.
        logger.warning("Any one of the target archs, dpi is empty!")
        return False

    logger.info(f"[*] Target Architecture(s): {', '.join(allowed_arch) or 'None specified'}")
    logger.info(f"[*] Target Density(s)     : {', '.join(allowed_dpi)}")

    modifier_pattern = re.compile(r"(?:config\.|base-)([^.]+)\.apk$")

    with (
        zipfile.ZipFile(input_zip, "r") as zin,
        zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout,
    ):
        # Discover package-name based APK (e.g. com.example.app.apk)
        base_names = {"base.apk", "base-master.apk"}
        pkg = _get_package_name(zin)
        if pkg:
            base_names.add(f"{pkg}.apk")
            logger.info(f"[*] Identified package: {pkg}")

        for item in zin.infolist():
            filename = item.filename

            if not filename.endswith(".apk"):
                continue

            basename = Path(filename).name
            keep = False

            if basename in base_names:
                keep = True
            else:
                match = modifier_pattern.search(basename)
                if match:
                    modifier = match.group(1).replace("-", "_")

                    # If it's an arch/DPI, check if allowed. Otherwise, keep it.
                    keep = _should_keep(modifier, allowed_arch, allowed_dpi)
                else:
                    # Keep unrecognized APK formats by default
                    keep = True

            if keep:
                logger.debug(f"[+] Packing [{output_zip.name}/]:  {basename}")
                file_data = zin.read(item.filename)
                zout.writestr(item.filename, file_data)
            else:
                logger.warning(f"[-] Dropping [{output_zip.name}/]: {basename}")

    in_size = input_zip.stat().st_size
    out_size = output_zip.stat().st_size
    logger.info(f"[*] Packed [{output_zip.name}/]! Repacked Ratio: {in_size / out_size:.2f}")

    return True
