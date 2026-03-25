"""Repack split apks."""

import json
import re
import zipfile
from pathlib import Path

from loguru import logger

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
    allowed_arch = set()
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
        for item in zin.infolist():
            filename = item.filename

            if not filename.endswith(".apk"):
                continue

            basename = Path(filename).name
            keep = False

            if basename in ["base.apk", "base-master.apk"]:
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
