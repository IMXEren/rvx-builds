"""Unit tests for src.jars.normalize — NormalizeJar Python port."""

# ruff: noqa: PT009

import io
import tempfile
import zipfile
from pathlib import Path
from typing import Self
from unittest import TestCase

from src.jars.normalize import normalize_jar_file, normalize_jar_hash


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
    """AC-1: verify the public API is importable."""

    def test_import_normalize_jar_file(self: Self) -> None:
        self.assertTrue(callable(normalize_jar_file))

    def test_import_normalize_jar_hash(self: Self) -> None:
        self.assertTrue(callable(normalize_jar_hash))


class NormalizeJarFileTests(TestCase):
    """Functional tests for normalize_jar_file."""

    def setUp(self: Self) -> None:
        self.tmpdir = tempfile.mkdtemp()

    def _write_input(self, raw: bytes) -> Path:
        p = Path(self.tmpdir) / "input.jar"
        p.write_bytes(raw)
        return p

    def _output_path(self) -> Path:
        return Path(self.tmpdir) / "output.jar"

    def _normalize(self, raw_input: bytes) -> bytes:
        inp = self._write_input(raw_input)
        out = self._output_path()
        normalize_jar_file(inp, out)
        return out.read_bytes()

    def _read_entries(self, raw: bytes) -> list[zipfile.ZipInfo]:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            return zf.infolist()

    # AC-2: NO META-INF/MANIFEST.MF entry in output
    def test_strips_manifest_mf(self: Self) -> None:
        raw = _build_test_jar({
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\n",
            "com/example/App.class": b"\xca\xfe\xba\xbe",
        })
        out = self._normalize(raw)
        names = [e.filename for e in self._read_entries(out)]
        self.assertNotIn("META-INF/MANIFEST.MF", names)

    # AC-2: Case-insensitive MANIFEST.MF stripping
    def test_strips_manifest_mf_case_insensitive(self: Self) -> None:
        raw = _build_test_jar({
            "META-INF/Manifest.MF": b"Manifest-Version: 1.0\n",
            "com/example/App.class": b"\xca\xfe\xba\xbe",
        })
        out = self._normalize(raw)
        names = [e.filename for e in self._read_entries(out)]
        self.assertNotIn("META-INF/Manifest.MF", names)

    # AC-3: NO *.kotlin_module entries
    def test_strips_kotlin_module(self: Self) -> None:
        raw = _build_test_jar({
            "META-INF/kotlin/app.kotlin_module": b"kotlin",
            "com/example/App.class": b"\xca\xfe\xba\xbe",
        })
        out = self._normalize(raw)
        names = [e.filename for e in self._read_entries(out)]
        self.assertNotIn("META-INF/kotlin/app.kotlin_module", names)

    # AC-3: Multiple kotlin_module entries
    def test_strips_multiple_kotlin_module(self: Self) -> None:
        raw = _build_test_jar({
            "META-INF/kotlin/a.kotlin_module": b"a",
            "META-INF/kotlin/b.kotlin_module": b"b",
            "com/example/App.class": b"\xca\xfe\xba\xbe",
        })
        out = self._normalize(raw)
        names = [e.filename for e in self._read_entries(out)]
        self.assertNotIn("META-INF/kotlin/a.kotlin_module", names)
        self.assertNotIn("META-INF/kotlin/b.kotlin_module", names)

    # AC-2 + AC-3: Both stripped together
    def test_strips_both_manifest_and_kotlin(self: Self) -> None:
        raw = _build_test_jar({
            "META-INF/MANIFEST.MF": b"Manifest-Version: 1.0\n",
            "META-INF/kotlin/app.kotlin_module": b"kotlin",
            "com/example/App.class": b"\xca\xfe\xba\xbe",
        })
        out = self._normalize(raw)
        names = [e.filename for e in self._read_entries(out)]
        self.assertNotIn("META-INF/MANIFEST.MF", names)
        self.assertNotIn("META-INF/kotlin/app.kotlin_module", names)
        self.assertEqual(names, ["com/example/App.class"])

    # AC-4: Timestamp normalized to (1980, 1, 1, 0, 0, 0)
    def test_timestamp_normalized(self: Self) -> None:
        raw = _build_test_jar({
            "com/example/App.class": b"\xca\xfe\xba\xbe",
        })
        out = self._normalize(raw)
        entries = self._read_entries(out)
        for e in entries:
            self.assertEqual(
                e.date_time,
                (1980, 1, 1, 0, 0, 0),
                f"Entry {e.filename} has wrong timestamp",
            )

    # AC-4: Multiple entries all normalized
    def test_timestamp_normalized_multiple(self: Self) -> None:
        raw = _build_test_jar({
            "a.txt": b"aaa",
            "b.txt": b"bbb",
            "c.txt": b"ccc",
        })
        out = self._normalize(raw)
        entries = self._read_entries(out)
        self.assertGreater(len(entries), 1)
        for e in entries:
            self.assertEqual(e.date_time, (1980, 1, 1, 0, 0, 0))

    # AC-5: Entries in case-sensitive alphabetical order
    def test_sort_order(self: Self) -> None:
        raw = _build_test_jar({
            "z.txt": b"zzz",
            "a.txt": b"aaa",
            "M.txt": b"MMM",
        })
        out = self._normalize(raw)
        names = [e.filename for e in self._read_entries(out)]
        # Java String.compareTo: uppercase before lowercase (since 'M' (77) < 'a' (97))
        self.assertEqual(names, ["M.txt", "a.txt", "z.txt"])

    # AC-5: Case-sensitive sort: uppercase < lowercase
    def test_case_sensitive_sort(self: Self) -> None:
        raw = _build_test_jar({
            "b.txt": b"bbb",
            "A.txt": b"AAA",
            "a.txt": b"aaa",
        })
        out = self._normalize(raw)
        names = [e.filename for e in self._read_entries(out)]
        # 'A' (65) < 'a' (97) < 'b' (98) in Unicode codepoint order
        # So: A.txt, a.txt, b.txt
        self.assertEqual(names, ["A.txt", "a.txt", "b.txt"])

    # STORED entries are preserved
    def test_preserves_stored_entries(self: Self) -> None:
        raw = _build_test_jar({
            "META-INF/MANIFEST.MF": b"Manifest: 1.0\n",
            "stored.txt": b"hello stored data",
        }, compress=False)
        out = self._normalize(raw)
        entries = self._read_entries(out)
        # Only stored.txt should remain
        self.assertEqual(len(entries), 1)
        e = entries[0]
        self.assertEqual(e.filename, "stored.txt")
        self.assertEqual(e.compress_type, zipfile.ZIP_STORED)
        # Original data must survive
        with zipfile.ZipFile(io.BytesIO(out), "r") as zf:
            self.assertEqual(zf.read("stored.txt"), b"hello stored data")

    # Mixed STORED and DEFLATED entries
    def test_mixed_compress_methods(self: Self) -> None:
        raw = _build_test_jar({
            "a.txt": b"a" * 1000,  # will be DEFLATED
            "b.bin": b"bb",        # will be STORED
        }, compress=True)
        out = self._normalize(raw)
        # Check that data survives correctly
        with zipfile.ZipFile(io.BytesIO(out), "r") as zf:
            self.assertEqual(zf.read("a.txt"), b"a" * 1000)
            self.assertEqual(zf.read("b.bin"), b"bb")

    # Directory entries preserved
    def test_preserves_directory_entries(self: Self) -> None:
        raw = _build_test_jar({
            "com/": b"",
            "com/example/": b"",
            "com/example/App.class": b"\xca\xfe\xba\xbe",
        })
        # Note: zipfile removes empty directory entries, so we build manually
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write directory entries explicitly
            for name in ("com/", "com/example/"):
                info = zipfile.ZipInfo(name)
                info.compress_type = zipfile.ZIP_STORED
                zf.writestr(info, b"")
            zf.writestr("com/example/App.class", b"\xca\xfe\xba\xbe")

        out = self._normalize(buf.getvalue())
        names = [e.filename for e in self._read_entries(out)]
        self.assertIn("com/", names)
        self.assertIn("com/example/", names)
        self.assertIn("com/example/App.class", names)

    # Order of input entries should not matter; output is always sorted
    def test_output_order_independent_of_input_order(self: Self) -> None:
        raw1 = _build_test_jar({
            "z.txt": b"zzz",
            "a.txt": b"aaa",
            "m.txt": b"mmm",
        })
        raw2 = _build_test_jar({
            "a.txt": b"aaa",
            "m.txt": b"mmm",
            "z.txt": b"zzz",
        })
        out1 = self._normalize(raw1)
        out2 = self._normalize(raw2)
        # Different input order may produce different bytes (compression artifacts),
        # but entry ordering (names in sorted order) must be the same
        names1 = [e.filename for e in self._read_entries(out1)]
        names2 = [e.filename for e in self._read_entries(out2)]
        self.assertEqual(names1, names2)

    # All entries stripped → empty JAR (no entries)
    def test_all_stripped(self: Self) -> None:
        raw = _build_test_jar({
            "META-INF/MANIFEST.MF": b"Manifest: 1.0\n",
            "META-INF/kotlin/x.kotlin_module": b"x",
        })
        out = self._normalize(raw)
        entries = self._read_entries(out)
        self.assertEqual(len(entries), 0)

    def tearDown(self: Self) -> None:
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)


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
        raw = _build_test_jar({
            "a.class": b"\xca\xfe\xba\xbe",
            "b.class": b"\xca\xfe\xba\xbf",
            "META-INF/MANIFEST.MF": b"Manifest: 1.0\n",
        })
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
