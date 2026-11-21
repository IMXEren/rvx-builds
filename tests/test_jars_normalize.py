"""Unit tests for src.jars.normalize, the Python port of NormalizeJar."""

# ruff: noqa: PT009

import io
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Self
from unittest import TestCase

from src.jars.normalize import normalize_jar_hash


def _build_test_jar(entries: dict[str, bytes]) -> bytes:
    """Build an in-memory deflated JAR from entry names and contents, and return its bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class NormalizeJarImportTests(TestCase):
    """Verify the module exposes its public hash function."""

    def test_import_normalize_jar_hash(self: Self) -> None:
        """normalize_jar_hash is importable and callable."""
        self.assertTrue(callable(normalize_jar_hash))


class NormalizeJarHashTests(TestCase):
    """Tests for normalize_jar_hash."""

    def setUp(self: Self) -> None:
        """Create a scratch directory for input JARs."""
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self: Self) -> None:
        """Remove the scratch directory."""
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_input(self: Self, raw: bytes) -> Path:
        p = Path(self.tmpdir) / "input.jar"
        p.write_bytes(raw)
        return p

    def test_hash_length_and_format(self: Self) -> None:
        """The hash is a 64-character lowercase hex string."""
        raw = _build_test_jar({"com/example/App.class": b"\xca\xfe\xba\xbe"})
        h = normalize_jar_hash(self._write_input(raw))
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)
        int(h, 16)

    def test_deterministic_same_file(self: Self) -> None:
        """Hashing the same file twice gives the same hash."""
        inp = self._write_input(_build_test_jar({"com/example/App.class": b"\xca\xfe\xba\xbe"}))
        self.assertEqual(normalize_jar_hash(inp), normalize_jar_hash(inp))

    def test_deterministic_repeatable(self: Self) -> None:
        """Repeated runs on a multi-entry JAR keep the same hash."""
        raw = _build_test_jar(
            {
                "a.class": b"\xca\xfe\xba\xbe",
                "b.class": b"\xca\xfe\xba\xbf",
                "META-INF/MANIFEST.MF": b"Manifest: 1.0\n",
            },
        )
        inp = self._write_input(raw)
        h = normalize_jar_hash(inp)
        for _ in range(3):
            self.assertEqual(normalize_jar_hash(inp), h)

    def test_hash_content_based(self: Self) -> None:
        """Different entry contents give different hashes."""
        inp_a = self._write_input(_build_test_jar({"c.class": b"\x01\x02"}))
        inp_b = Path(self.tmpdir) / "other.jar"
        inp_b.write_bytes(_build_test_jar({"c.class": b"\x03\x04"}))
        self.assertNotEqual(normalize_jar_hash(inp_a), normalize_jar_hash(inp_b))
