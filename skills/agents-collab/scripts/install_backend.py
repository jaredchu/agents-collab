#!/usr/bin/env python3
"""Install an explicitly supplied, checksummed local macOS arm64 CLI archive.

No downloads, source builds, profile changes or shell/PATH edits. --enable writes
only the separate backend selector. A checksum authenticates bytes only when its
source is trusted; this helper does not establish publisher identity.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import stat
import struct
import sys
import tarfile
import tempfile
from pathlib import Path

DEFAULT_CONFIG = Path.home() / ".config/agents-collab/backend.json"
SUPPORTED = ("darwin", "arm64")
MAX_ARCHIVE = 256 * 1024 * 1024
MAX_BINARY = 200 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def strict_json(data):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def safe_path(path):
    """Reject lexical traversal and symlink ancestry, including dangling links."""
    path = Path(path).expanduser()
    if ".." in path.parts or "." in path.parts:
        raise ValueError("path traversal is not allowed")
    path = path.absolute()
    for part in [*reversed(path.parents), path]:
        if part.is_symlink():
            raise ValueError("symlink path or ancestor is not allowed")
    return path


def read_regular(path, limit=MAX_ARCHIVE):
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("expected bounded regular file")
        with os.fdopen(fd, "rb", closefd=False) as handle:
            result = handle.read(limit + 1)
        if len(result) > limit:
            raise ValueError("file exceeds size limit")
        return result
    finally:
        os.close(fd)


def private_dir(path):
    path = safe_path(path)
    if path.exists():
        if not path.is_dir():
            raise ValueError("directory path is not a directory")
        return path
    if not path.parent.exists():
        private_dir(path.parent)
    path.mkdir(mode=0o700)
    return path


def atomic_write(path, data, mode=0o600, replace=False):
    path = safe_path(path)
    if path.exists() and (not path.is_file() or not replace):
        raise ValueError("existing target requires explicit replacement")
    private_dir(path.parent)
    fd, name = tempfile.mkstemp(prefix=".agents-collab-", dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        safe_path(path)
        if replace:
            os.replace(name, path)
        else:
            os.link(name, path)  # publish without clobbering a competing writer
            os.unlink(name)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def host_platform():
    value = (platform.system().lower(), platform.machine().lower())
    if value != SUPPORTED:
        raise ValueError("only verified macOS arm64 packages are supported")
    return value


def macho_arm64(binary):
    if len(binary) < 32 or binary[:4] != b"\xcf\xfa\xed\xfe":
        raise ValueError("binary must be a thin 64-bit macOS arm64 Mach-O executable")
    cpu, _, filetype = struct.unpack("<III", binary[4:16])
    if cpu != 0x0100000C or filetype != 2:
        raise ValueError("binary architecture/type is not a macOS arm64 executable")


def read_config(path):
    data = strict_json(read_regular(path, 16384))
    if (not isinstance(data, dict) or set(data) != {"version", "mode", "binary"}
            or type(data["version"]) is not int or data["version"] != 1
            or data["mode"] != "cli" or not isinstance(data["binary"], str)
            or not Path(data["binary"]).is_absolute()):
        raise ValueError("invalid separate backend configuration")
    safe_path(data["binary"])
    return data


def inspect_archive(path, expected):
    host_platform()
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected):
        raise ValueError("--sha256 requires exactly 64 hexadecimal characters")
    raw = read_regular(path)
    if digest(raw) != expected.lower():
        raise ValueError("archive SHA-256 mismatch")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as archive:
        members = archive.getmembers()
        if len(members) != 3:
            raise ValueError("archive must contain exactly agents-collab, LICENSE and manifest.json")
        for member in members:
            if (member.name not in {"agents-collab", "LICENSE", "manifest.json"}
                    or member.name in files or not member.isfile()
                    or member.issparse() or member.linkname or member.pax_headers
                    or member.size > (MAX_BINARY if member.name == "agents-collab" else 65536)):
                raise ValueError("unexpected, duplicate or unsafe archive member")
            handle = archive.extractfile(member)
            files[member.name] = handle.read(member.size + 1)
            if len(files[member.name]) != member.size:
                raise ValueError("archive member length mismatch")
    manifest = strict_json(files["manifest.json"])
    if (not isinstance(manifest, dict)
            or set(manifest) != {"schema_version", "version", "platform", "arch", "binary_sha256"}
            or type(manifest["schema_version"]) is not int or manifest["schema_version"] != 1
            or not isinstance(manifest["version"], str)
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?", manifest["version"])
            or (manifest["platform"], manifest["arch"]) != SUPPORTED
            or manifest["binary_sha256"] != digest(files["agents-collab"])):
        raise ValueError("malformed manifest, wrong platform/architecture or binary hash")
    macho_arm64(files["agents-collab"])
    if not files["LICENSE"].startswith(b"MIT License\n"):
        raise ValueError("missing MIT license notice")
    return files, manifest


def install(args):
    files, manifest = inspect_archive(args.archive, args.sha256)
    binary = safe_path(Path(args.bin_dir) / "agents-collab")
    config = safe_path(args.config)
    desired = {"version": 1, "mode": "cli", "binary": str(binary)}
    existing_config = None
    if config.exists():
        try:
            existing_config = read_config(config)
        except (ValueError, OSError):
            if args.enable and not args.replace:
                raise ValueError("unrelated existing backend config; use --replace explicitly")
    same_config = existing_config == desired
    if args.enable and config.exists() and not same_config and not args.replace:
        raise ValueError("unrelated existing backend config; use --replace explicitly")
    if binary.exists():
        if not binary.is_file():
            raise ValueError("binary target is not a regular file")
        same_binary = digest(read_regular(binary, MAX_BINARY)) == manifest["binary_sha256"]
        if not (same_binary or same_config or args.replace):
            raise ValueError("unrelated existing binary; use --replace explicitly")
    atomic_write(binary, files["agents-collab"], 0o755, replace=binary.exists())
    if args.enable:
        try:
            atomic_write(config, (json.dumps(desired, indent=2) + "\n").encode(),
                         replace=config.exists())
        except (OSError, ValueError) as exc:
            raise ValueError(f"binary installed at {binary}, but enabling failed: {exc}") from exc
    return {"binary": str(binary), "version": manifest["version"], "enabled": args.enable,
            "config": str(config) if args.enable else None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="explicit local .tar.gz package")
    parser.add_argument("--sha256", required=True, help="trusted archive SHA-256")
    parser.add_argument("--bin-dir", default=str(Path.home() / ".local/bin"))
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--enable", action="store_true", help="select CLI in separate backend.json")
    parser.add_argument("--replace", action="store_true", help="replace unrelated regular binary/config")
    try:
        print(json.dumps(install(parser.parse_args(argv)), indent=2))
        return 0
    except (ValueError, OSError, tarfile.TarError, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
