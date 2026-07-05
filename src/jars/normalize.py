"""Normalize JAR files - strip metadata, normalize timestamps, sort entries.

Strip META-INF/MANIFEST.MF and *.kotlin_module entries, normalize timestamps
to 1980-01-01T00:00:00Z, sort entries by name with case-sensitive lexicographic
order, and optionally compute a deterministic SHA256 hash.
"""

import hashlib
import tempfile
import zipfile
from pathlib import Path


def normalize_jar_file(input_path: Path, output_path: Path) -> None:
    """Normalize a JAR/ZIP file, writing the canonical result to *output_path*.

    Raises
    ------
    FileNotFoundError
        If *input_path* does not exist.
    zipfile.BadZipFile
        If *input_path* is not a valid ZIP/JAR.
    """
    with zipfile.ZipFile(input_path, "r") as src_zip:
        entries: list[zipfile.ZipInfo] = []
        data_map: dict[str, bytes] = {}

        for info in src_zip.infolist():
            name: str = info.filename

            # Strip META-INF/MANIFEST.MF - case-insensitive
            if name.lower() == "meta-inf/manifest.mf":
                continue
            # Strip *.kotlin_module
            if name.endswith(".kotlin_module"):
                continue

            entries.append(info)
            data_map[name] = src_zip.read(name)

        entries.sort(key=lambda e: e.filename)

        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as dest_zip:
            for info in entries:
                name = info.filename
                data = data_map[name]

                # Build a fresh ZipInfo with normalized timestamp
                new_info = zipfile.ZipInfo(name)
                new_info.date_time = (1980, 1, 1, 0, 0, 0)  # 315532800000 ms

                # Preserve compression method from the source
                new_info.compress_type = info.compress_type

                # For STORED entries, preserve CRC and sizes so zipfile
                # does not need to re-verify or reject the entry.
                if info.compress_type == zipfile.ZIP_STORED:
                    new_info.CRC = info.CRC
                    new_info.compress_size = info.compress_size
                    new_info.file_size = info.file_size

                dest_zip.writestr(new_info, data)


def normalize_jar_hash(input_path: Path) -> str:
    """Compute the normalized SHA-256 hex digest of a JAR file.

    Deterministic: the same file always produces the same hash.
    """
    with tempfile.NamedTemporaryFile(suffix=".jar", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        normalize_jar_file(input_path, tmp_path)
        return hashlib.sha256(tmp_path.read_bytes()).hexdigest()
    finally:
        # Clean up the temp file
        tmp_path.unlink(missing_ok=True)
