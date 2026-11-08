#!/usr/bin/env python3
"""Build the static Agents Collab website into this repository's dist/ folder.

Copies website/ to dist/, adds curated downloads (a deterministic zip of the
generic skill package, including its MIT LICENSE, and an illustrative profile)
with SHA-256 sums, and
checks that every internal link in the output resolves.

The script manages only <repo>/dist. It refuses to run if dist is a symlink or
not a directory, and it writes nothing outside it. No network, no third-party
packages; Python 3.9+.

Usage:  python3 scripts/build_website.py
Exit status: 0 built and checked; 1 a check failed; 2 a setup error.
"""

from __future__ import annotations

import hashlib
import html.parser
import shutil
import sys
import zipfile
from pathlib import Path
from typing import List, Tuple
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parent.parent
SOURCE = REPO / "website"
PACKAGE = REPO / "skills" / "agents-collab"
DIST = REPO / "dist"
DOWNLOADS = "downloads"
ZIP_NAME = "agents-collab-skill.zip"
EXAMPLE_PROFILE = REPO / "docs" / "examples" / "writer-review.profile.example.json"

# The curated distributable package: the workflow files, the two
# dependency-free helper scripts (profile validator and setup wizard) and the
# MIT LICENSE. Only these files are zipped, under the top-level folder name
# users install. Nothing else from the repository ships.
PACKAGE_FILES = (
    "LICENSE",
    "SKILL.md",
    "agents/openai.yaml",
    "assets/review-packet.md",
    "assets/task-state.json",
    "examples/profile.example.json",
    "references/configuration.md",
    "references/review-protocol.md",
    "scripts/setup_profile.py",
    "scripts/validate_profile.py",
)
ZIP_TIMESTAMP = (2026, 11, 8, 0, 0, 0)


class BuildError(Exception):
    pass


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_package_zip(dest: Path) -> str:
    """Write a byte-reproducible zip of the package to dest; return its SHA-256."""
    missing = [name for name in PACKAGE_FILES if not (PACKAGE / name).is_file()]
    if missing:
        raise BuildError("package file missing: " + ", ".join(missing))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in PACKAGE_FILES:
            info = zipfile.ZipInfo("agents-collab/" + name, date_time=ZIP_TIMESTAMP)
            mode = 0o755 if name.endswith(".py") else 0o644
            info.external_attr = (0o100000 | mode) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # Unix, so the mode bits are honoured
            archive.writestr(info, (PACKAGE / name).read_bytes())
    return sha256(dest)


def copy_site(dest: Path) -> None:
    """Copy website sources, skipping dotfiles and editor/OS clutter."""
    for path in sorted(SOURCE.rglob("*")):
        rel = path.relative_to(SOURCE)
        if any(part.startswith(".") for part in rel.parts):
            continue
        if path.is_symlink():
            raise BuildError(f"symlink in website sources is not copied: {rel}")
        target = dest / rel
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)


class _Links(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.refs: List[str] = []
        self.ids: List[str] = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ("href", "src") and value:
                self.refs.append(value)
            elif key == "id" and value:
                self.ids.append(value)


def _parse(path: Path) -> _Links:
    parser = _Links()
    parser.feed(path.read_text(encoding="utf-8"))
    return parser


def resolve_internal(root: Path, page: Path, ref: str) -> Tuple[Path, str]:
    """Map an internal href to (file, fragment). Directory links mean index.html."""
    parts = urlsplit(ref)
    rel = unquote(parts.path)
    if not rel:
        return page, parts.fragment
    target = (root / rel.lstrip("/")) if rel.startswith("/") else (page.parent / rel)
    if rel.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target, parts.fragment


def check_links(root: Path, skip_prefixes: Tuple[str, ...] = ()) -> List[str]:
    """Return problems for internal links/anchors in every HTML file under root."""
    problems: List[str] = []
    root = root.resolve()
    ids_cache = {}
    for page in sorted(root.rglob("*.html")):
        for ref in _parse(page).refs:
            scheme = urlsplit(ref).scheme
            if scheme or ref.startswith("//"):
                continue  # external links are outside this offline check
            target, fragment = resolve_internal(root, page, ref)
            label = f"{page.relative_to(root)} -> {ref}"
            try:
                rel_target = target.resolve().relative_to(root).as_posix()
            except ValueError:
                problems.append(label + " (leaves the site root)")
                continue
            if any(rel_target.startswith(prefix) for prefix in skip_prefixes):
                continue
            if not target.is_file():
                problems.append(label + " (missing)")
                continue
            if fragment and target.suffix == ".html":
                if target not in ids_cache:
                    ids_cache[target] = set(_parse(target).ids)
                if fragment not in ids_cache[target]:
                    problems.append(label + " (missing anchor)")
    return problems


def main() -> int:
    if not SOURCE.is_dir():
        print("error: website/ sources not found", file=sys.stderr)
        return 2
    if DIST.is_symlink() or (DIST.exists() and not DIST.is_dir()):
        print("error: dist exists but is not a plain directory; refusing to touch it",
              file=sys.stderr)
        return 2
    if DIST.resolve().parent != REPO:
        print("error: dist does not resolve inside the repository", file=sys.stderr)
        return 2
    try:
        if DIST.exists():
            shutil.rmtree(DIST)
        DIST.mkdir()
        copy_site(DIST)
        downloads = DIST / DOWNLOADS
        downloads.mkdir(exist_ok=True)
        sums = [(build_package_zip(downloads / ZIP_NAME), ZIP_NAME)]
        if EXAMPLE_PROFILE.is_file():
            shutil.copyfile(EXAMPLE_PROFILE, downloads / EXAMPLE_PROFILE.name)
            sums.append((sha256(downloads / EXAMPLE_PROFILE.name), EXAMPLE_PROFILE.name))
        (downloads / "SHA256SUMS").write_text(
            "".join(f"{digest}  {name}\n" for digest, name in sums), encoding="utf-8")
    except (BuildError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    problems = check_links(DIST)
    if problems:
        print(f"link check failed: {len(problems)} problem(s)", file=sys.stderr)
        for problem in problems:
            print("  " + problem, file=sys.stderr)
        return 1
    for digest, name in sums:
        print(f"{digest}  {DOWNLOADS}/{name}")
    print("built dist/ and checked internal links")
    return 0


if __name__ == "__main__":
    sys.exit(main())
