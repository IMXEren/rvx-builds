"""Repack split apks."""

import json
import re
import zipfile
from pathlib import Path

from loguru import logger
from pyaxmlparser import APK

from src.apks.silence import silence_pyaxmlparser

# All standard Android architectures and screen densities
STANDARD_ARCHS = {"armeabi", "armeabi_v7a", "arm64_v8a", "x86", "x86_64", "mips", "mips64"}
STANDARD_DPIS = {"ldpi", "mdpi", "tvdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi", "anydpi", "nodpi"}
DPI_BUCKETS = {"ldpi": 120, "mdpi": 160, "tvdpi": 213, "hdpi": 240, "xhdpi": 320, "xxhdpi": 480, "xxxhdpi": 640}
MODIFIER_PATTERN = re.compile(r"(?:config\.|base-)([^.]+)\.apk$")


def get_dpi_modifier(density: int) -> str:
    """Maps a raw density integer from device.json to the standard Android DPI modifier."""
    return min(DPI_BUCKETS, key=lambda bucket: abs(DPI_BUCKETS[bucket] - density))


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


def _select_splits(names: list[str], allowed_arch: set[str], allowed_dpi: set[str]) -> set[str]:
    """Pick the split APKs to keep, never dropping every split of one kind.

    Bundletool makes each density or arch split complete for its bucket, and the base may reference
    resources that only exist in them. So when no split matches the device, the closest density split
    or all arch splits are kept instead of none.
    """
    archs: dict[str, str] = {}
    dpis: dict[str, str] = {}
    keep: set[str] = set()
    for name in names:
        match = MODIFIER_PATTERN.search(name)
        modifier = match.group(1).replace("-", "_") if match else ""
        if modifier in STANDARD_ARCHS:
            archs[name] = modifier
        elif modifier in DPI_BUCKETS:
            dpis[name] = modifier
        else:
            # Base, nodpi/anydpi, language, feature and unrecognized APKs are always kept.
            keep.add(name)

    matched_archs = {name for name, arch in archs.items() if arch in allowed_arch}
    keep |= matched_archs or set(archs)

    matched_dpis = {name for name, dpi in dpis.items() if dpi in allowed_dpi}
    if not matched_dpis and dpis:
        targets = [DPI_BUCKETS[dpi] for dpi in allowed_dpi if dpi in DPI_BUCKETS]
        if targets:
            # Ties go to the higher density because downscaling keeps bitmaps sharp.
            closest = min(dpis, key=lambda name: (abs(DPI_BUCKETS[dpis[name]] - targets[0]), -DPI_BUCKETS[dpis[name]]))
            matched_dpis = {closest}
        else:
            matched_dpis = set(dpis)
    keep |= matched_dpis
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


def repack_apks(input_zip: Path, output_zip: Path, device_spec_path: Path) -> bool:
    """Repack apks to include only necessary archs, density (dpi) and languages (ALL) from the `device-spec.json`."""
    allowed_arch, allowed_dpi = get_filters(device_spec_path)

    if any([len(allowed_arch) == 0, len(allowed_dpi) == 0]):
        # Repack definitely needs all of them to be non-zero, for the apk to actually work.
        logger.warning("Any one of the target archs, dpi is empty!")
        return False

    logger.info(f"[*] Target Architecture(s): {', '.join(allowed_arch) or 'None specified'}")
    logger.info(f"[*] Target Density(s)     : {', '.join(allowed_dpi)}")

    with (
        zipfile.ZipFile(input_zip, "r") as zin,
        zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zout,
    ):
        apks = [item for item in zin.infolist() if item.filename.endswith(".apk")]
        keep = _select_splits([Path(item.filename).name for item in apks], allowed_arch, allowed_dpi)
        for item in apks:
            basename = Path(item.filename).name
            if basename in keep:
                logger.debug(f"[+] Packing [{output_zip.name}/]:  {basename}")
                zout.writestr(item.filename, zin.read(item.filename))
            else:
                logger.warning(f"[-] Dropping [{output_zip.name}/]: {basename}")

    in_size = input_zip.stat().st_size
    out_size = output_zip.stat().st_size
    logger.info(f"[*] Packed [{output_zip.name}/]! Repacked Ratio: {in_size / out_size:.2f}")

    return True
