"""JAR normalization utilities."""

import hashlib
import zipfile
from pathlib import Path


def _should_ignore(name: str) -> bool:
    name_lower = name.lower()

    if name.endswith("/"):
        return True

    if name_lower == "meta-inf/manifest.mf":
        return True
    if name_lower.endswith(".kotlin_module"):
        return True

    if "meta-inf/maven/" in name_lower and name_lower.endswith("pom.properties"):
        return True

    if name_lower.startswith("meta-inf/") and any(name_lower.endswith(ext) for ext in (".sf", ".rsa", ".dsa")):
        return True
    if name_lower.startswith("meta-inf/sig-"):
        return True

    return name_lower.endswith(".ds_store") or "thumbs.db" in name_lower


def normalize_jar_hash(input_path: Path) -> str:
    """Compute a deterministic SHA-256 hash of a JAR's contents."""
    hasher = hashlib.sha256()

    with zipfile.ZipFile(input_path, "r") as src_zip:
        valid_entries: list[str] = []

        for info in src_zip.infolist():
            if _should_ignore(info.filename):
                continue
            valid_entries.append(info.filename)

        valid_entries.sort()

        for name in valid_entries:
            hasher.update(src_zip.read(name))

    return hasher.hexdigest()
