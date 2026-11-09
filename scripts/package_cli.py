#!/usr/bin/env python3
"""Package an existing release binary for verified macOS arm64 only.

Produces a deterministic tar.gz (agents-collab, LICENSE, manifest.json) and
SHA256SUMS. Does not build, download, install or publish anything.
"""
from __future__ import annotations
import argparse
import gzip
import importlib.util
import io
import json
import re
import subprocess
import sys
import tarfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("install_backend", REPO / "skills/agents-collab/scripts/install_backend.py")
helpers = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(helpers)


def package(binary, output_dir):
    helpers.host_platform()
    path = helpers.safe_path(binary)
    raw = helpers.read_regular(path, helpers.MAX_BINARY)
    helpers.macho_arm64(raw)
    result = subprocess.run([str(path), "--version"], capture_output=True, text=True, timeout=15)
    match = re.fullmatch(r"agents-collab ([0-9]+\.[0-9]+\.[0-9]+(?:[-+][a-zA-Z0-9.-]+)?)\s*", result.stdout)
    if result.returncode != 0 or not match:
        raise ValueError("binary --version did not return an agents-collab version")
    if helpers.read_regular(path, helpers.MAX_BINARY) != raw:
        raise ValueError("binary changed during packaging")
    version = match.group(1)
    manifest = {"schema_version": 1, "version": version, "platform": "darwin", "arch": "arm64",
                "binary_sha256": helpers.digest(raw)}
    files = [("agents-collab", raw, 0o755), ("LICENSE", (REPO / "LICENSE").read_bytes(), 0o644),
             ("manifest.json", (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode(), 0o644)]
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode="wb", filename="", mtime=0) as compressed:
        with tarfile.open(fileobj=compressed, mode="w", format=tarfile.USTAR_FORMAT) as archive:
            for name, data, mode in files:
                info = tarfile.TarInfo(name)
                info.size, info.mode, info.mtime = len(data), mode, 0
                archive.addfile(info, io.BytesIO(data))
    output = helpers.safe_path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    name = f"agents-collab-{version}-darwin-arm64.tar.gz"
    payload = stream.getvalue()
    helpers.atomic_write(output / name, payload, 0o644, replace=True)
    helpers.atomic_write(output / "SHA256SUMS", f"{helpers.digest(payload)}  {name}\n".encode(), 0o644, replace=True)
    return {"archive": str(output / name), "sha256": helpers.digest(payload), "manifest": manifest}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--output-dir", required=True)
    try:
        args = parser.parse_args(argv)
        print(json.dumps(package(args.binary, args.output_dir), indent=2))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
