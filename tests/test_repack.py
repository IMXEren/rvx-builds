"""Split APK repack selection tests."""

# ruff: noqa: PT009, SLF001

import json
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Self
from unittest import TestCase

from src.apks import repack


class RepackSelectionTests(TestCase):
    """The base may need resources that only exist in a density or arch split, so one must survive."""

    def test_keeps_only_density_split_when_device_bucket_is_missing(self: Self) -> None:
        """A 640dpi bundle on a 450dpi device keeps its xxxhdpi split instead of losing its resources."""
        with TemporaryDirectory() as tmp_dir:
            tmp = Path(tmp_dir)
            bundle = tmp / "instagram.apkm"
            names = ["base.apk", "split_config.xxxhdpi.apk", "split_heliumcore.apk", "split_i18n_zh_TW.apk"]
            with zipfile.ZipFile(bundle, "w") as archive:
                for name in [*names, "info.json"]:
                    archive.writestr(name, name)
            spec = tmp / "device-spec.json"
            spec.write_text(json.dumps({"supportedAbis": ["arm64-v8a"], "screenDensity": 450}))
            output = tmp / "instagram-repack.apkm"

            self.assertTrue(repack.repack_apks(bundle, output, spec))
            with zipfile.ZipFile(output) as archive:
                self.assertEqual(sorted(names), sorted(archive.namelist()))

    def test_keeps_matching_density_and_arch_splits(self: Self) -> None:
        """Bundles carrying the device's buckets still drop the other densities and archs."""
        names = [
            "base.apk",
            "split_config.xhdpi.apk",
            "split_config.xxhdpi.apk",
            "split_config.xxxhdpi.apk",
            "split_config.arm64_v8a.apk",
            "split_config.x86.apk",
            "split_config.en.apk",
        ]
        keep = repack._select_splits(names, {"arm64_v8a"}, {"nodpi", "anydpi", "xxhdpi"})
        expected = {"base.apk", "split_config.xxhdpi.apk", "split_config.arm64_v8a.apk", "split_config.en.apk"}
        self.assertEqual(expected, keep)

    def test_falls_back_to_closest_density_preferring_higher(self: Self) -> None:
        """Without the device bucket, the nearest density wins and ties favor the sharper one."""
        names = ["base.apk", "split_config.mdpi.apk", "split_config.xhdpi.apk", "split_config.xxxhdpi.apk"]
        keep = repack._select_splits(names, {"arm64_v8a"}, {"nodpi", "anydpi", "xxhdpi"})
        self.assertEqual({"base.apk", "split_config.xxxhdpi.apk"}, keep)

    def test_keeps_all_arch_splits_when_none_match(self: Self) -> None:
        """Native libraries must not disappear when the bundle lacks the requested ABI."""
        names = ["base.apk", "split_config.armeabi_v7a.apk", "split_config.x86.apk"]
        self.assertEqual(set(names), repack._select_splits(names, {"arm64_v8a"}, {"xxhdpi"}))
