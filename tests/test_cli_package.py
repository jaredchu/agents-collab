"""Offline CLI packaging/installation safety checks with synthetic Mach-O bytes."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
import struct
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "skills/agents-collab/scripts"
sys.path.insert(0, str(SCRIPTS))
import install_backend as installer
spec = importlib.util.spec_from_file_location("package_cli", REPO / "scripts/package_cli.py")
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)


def macho():
    return b"\xcf\xfa\xed\xfe" + struct.pack("<III", 0x0100000C, 0, 2) + b"\0" * 32


def archive_bytes(members=None, manifest_changes=None):
    binary = macho()
    manifest = {"schema_version": 1, "version": "0.1.0", "platform": "darwin", "arch": "arm64",
                "binary_sha256": installer.digest(binary)}
    manifest.update(manifest_changes or {})
    members = members or [("agents-collab", binary, "file"), ("LICENSE", b"MIT License\n", "file"),
                          ("manifest.json", json.dumps(manifest).encode(), "file")]
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as tar:
        for name, raw, kind in members:
            info = tarfile.TarInfo(name)
            info.size = len(raw)
            if kind == "link":
                info.type, info.linkname, info.size = tarfile.SYMTYPE, "outside", 0
            elif kind == "hardlink":
                info.type, info.linkname, info.size = tarfile.LNKTYPE, "outside", 0
            tar.addfile(info, io.BytesIO(raw) if info.isfile() else None)
    return output.getvalue()


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.host = mock.patch.object(installer, "host_platform", return_value=("darwin", "arm64"))
        self.host.start()
        self.addCleanup(self.host.stop)
        self.pkg_host = mock.patch.object(packager.helpers, "host_platform", return_value=("darwin", "arm64"))
        self.pkg_host.start()
        self.addCleanup(self.pkg_host.stop)

    def source(self, raw=None):
        path = self.root / "package.tar.gz"
        path.write_bytes(raw or archive_bytes())
        return path, installer.digest(path.read_bytes())

    def args(self, **changes):
        path, checksum = self.source()
        values = dict(archive=str(path), sha256=checksum, bin_dir=str(self.root / "bin"),
                      config=str(self.root / "backend.json"), enable=True, replace=False)
        values.update(changes)
        return argparse.Namespace(**values)

    def test_deterministic_package_and_manifest(self):
        source = self.root / "release"
        source.write_bytes(macho())
        probe = subprocess.CompletedProcess([], 0, "agents-collab 0.1.0\n", "")
        with mock.patch.object(packager.subprocess, "run", return_value=probe):
            first = packager.package(source, self.root / "one")
            second = packager.package(source, self.root / "two")
        self.assertEqual(Path(first["archive"]).read_bytes(), Path(second["archive"]).read_bytes())
        files, manifest = installer.inspect_archive(first["archive"], first["sha256"])
        self.assertEqual(files["agents-collab"], macho())
        self.assertEqual(manifest["binary_sha256"], installer.digest(macho()))
        self.assertIn(first["sha256"], (self.root / "one/SHA256SUMS").read_text())

    def test_package_rejects_non_macho_before_version_exec(self):
        path = self.root / "fake"
        path.write_text("script")
        with mock.patch.object(packager.subprocess, "run") as run:
            with self.assertRaises(ValueError):
                packager.package(path, self.root / "out")
            run.assert_not_called()
        self.assertFalse((self.root / "out").exists())

    def test_checksum_mismatch_writes_nothing(self):
        args = self.args(sha256="0" * 64)
        with self.assertRaisesRegex(ValueError, "mismatch"):
            installer.install(args)
        self.assertFalse((self.root / "bin").exists())
        self.assertFalse(Path(args.config).exists())

    def test_install_separate_config_and_permissions(self):
        args = self.args()
        profile = self.root / "profile.json"
        profile.write_bytes(b"saved profile unchanged")
        result = installer.install(args)
        self.assertEqual(profile.read_bytes(), b"saved profile unchanged")
        self.assertEqual(Path(result["binary"]).read_bytes(), macho())
        self.assertEqual(Path(result["binary"]).stat().st_mode & 0o777, 0o755)
        config = Path(args.config)
        self.assertEqual(config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(config.read_text()), {"version": 1, "mode": "cli", "binary": result["binary"]})
        installer.install(args)  # same installation may be updated explicitly

    def test_install_without_enable_creates_no_config(self):
        args = self.args(enable=False)
        installer.install(args)
        self.assertFalse(Path(args.config).exists())

    def test_unrelated_binary_and_config_are_preserved(self):
        for target in ("binary", "config"):
            with self.subTest(target=target):
                args = self.args(bin_dir=str(self.root / target / "bin"), config=str(self.root / target / "config"))
                path = Path(args.bin_dir) / "agents-collab" if target == "binary" else Path(args.config)
                path.parent.mkdir(parents=True)
                path.write_bytes(b"unrelated")
                with self.assertRaisesRegex(ValueError, "unrelated"):
                    installer.install(args)
                self.assertEqual(path.read_bytes(), b"unrelated")
                args.replace = True
                installer.install(args)

    def test_symlink_target_or_ancestor_never_followed_even_replace(self):
        outside = self.root / "outside"
        outside.mkdir()
        for at_ancestor in (False, True):
            with self.subTest(ancestor=at_ancestor):
                args = self.args(bin_dir=str(self.root / ("ancestor-bin" if at_ancestor else "file-bin")), replace=True)
                if at_ancestor:
                    Path(args.bin_dir).symlink_to(outside, target_is_directory=True)
                else:
                    Path(args.bin_dir).mkdir()
                    (Path(args.bin_dir) / "agents-collab").symlink_to(outside / "missing")
                with self.assertRaisesRegex(ValueError, "symlink"):
                    installer.install(args)
        self.assertEqual(list(outside.iterdir()), [])

    def test_rejects_unsafe_archive_members(self):
        for name, kind in (("../agents-collab", "file"), ("/agents-collab", "file"),
                           ("agents-collab", "link"), ("agents-collab", "hardlink"),
                           ("surprise", "file"), ("LICENSE", "file")):
            with self.subTest(name=name, kind=kind):
                raw = archive_bytes([(name, macho(), kind), ("LICENSE", b"MIT License\n", "file"),
                                     ("manifest.json", b"{}", "file")])
                path, checksum = self.source(raw)
                with self.assertRaises(ValueError):
                    installer.inspect_archive(path, checksum)

    def test_wrong_platform_arch_hash_schema_or_version(self):
        for changes in ({"platform": "linux"}, {"arch": "x86_64"}, {"schema_version": True},
                        {"version": "shell;command"}, {"binary_sha256": "0" * 64}, {"extra": 1}):
            with self.subTest(changes=changes):
                path, checksum = self.source(archive_bytes(manifest_changes=changes))
                with self.assertRaises(ValueError):
                    installer.inspect_archive(path, checksum)

    def test_duplicate_json_keys_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate"):
            installer.strict_json('{"version":1,"version":1}')

    def test_actual_platform_gate_rejects_unverified_hosts(self):
        self.host.stop()
        with mock.patch.object(installer.platform, "system", return_value="Linux"):
            with self.assertRaisesRegex(ValueError, "verified"):
                installer.host_platform()
        self.host.start()


if __name__ == "__main__":
    unittest.main()
