"""Unit tests for src.jars.normalize — NormalizeJar Python port."""

# ruff: noqa: PT009

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Self
from unittest import TestCase

from src.jars.normalize import normalize_jar_hash


def _build_test_jar(
    entries: dict[str, bytes],
    compress: bool = True,
) -> bytes:
    """Build an in-memory ZIP/JAR from *entries* (name → data) and return the
    raw bytes.  *compress* controls whether the archive uses DEFLATED (default)
    or STORED.
    """
    buf = io.BytesIO()
    mode = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
    with zipfile.ZipFile(buf, "w", mode) as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


class NormalizeJarImportTests(TestCase):
    def test_import_normalize_jar_hash(self: Self) -> None:
        self.assertTrue(callable(normalize_jar_hash))


class NormalizeJarHashTests(TestCase):
    """Tests for normalize_jar_hash — AC-6 and AC-7."""

    def setUp(self: Self) -> None:
        self.tmpdir = tempfile.mkdtemp()

    def _write_input(self, raw: bytes) -> Path:
        p = Path(self.tmpdir) / "input.jar"
        p.write_bytes(raw)
        return p

    # AC-6: Returns 64-character lowercase hex string
    def test_hash_length_and_format(self: Self) -> None:
        raw = _build_test_jar({"com/example/App.class": b"\xca\xfe\xba\xbe"})
        inp = self._write_input(raw)
        h = normalize_jar_hash(inp)
        self.assertIsInstance(h, str)
        self.assertEqual(len(h), 64)
        # Verify it's valid hex
        int(h, 16)

    # AC-7: Deterministic — same file → same hash
    def test_deterministic_same_file(self: Self) -> None:
        raw = _build_test_jar({"com/example/App.class": b"\xca\xfe\xba\xbe"})
        inp = self._write_input(raw)
        h1 = normalize_jar_hash(inp)
        h2 = normalize_jar_hash(inp)
        self.assertEqual(h1, h2)

    # AC-7: Deterministic across different temp dirs / runs
    def test_deterministic_repeatable(self: Self) -> None:
        raw = _build_test_jar(
            {
                "a.class": b"\xca\xfe\xba\xbe",
                "b.class": b"\xca\xfe\xba\xbf",
                "META-INF/MANIFEST.MF": b"Manifest: 1.0\n",
            },
        )
        inp = self._write_input(raw)
        h = normalize_jar_hash(inp)
        # Run multiple times
        for _ in range(3):
            self.assertEqual(normalize_jar_hash(inp), h)

    # Hash depends on content, not on path
    def test_hash_content_based(self: Self) -> None:
        raw_a = _build_test_jar({"c.class": b"\x01\x02"})
        raw_b = _build_test_jar({"c.class": b"\x03\x04"})
        inp_a = self._write_input(raw_a)
        inp_b = Path(self.tmpdir) / "other.jar"
        inp_b.write_bytes(raw_b)
        self.assertNotEqual(normalize_jar_hash(inp_a), normalize_jar_hash(inp_b))

    def tearDown(self: Self) -> None:
        import shutil

        shutil.rmtree(self.tmpdir, ignore_errors=True)
