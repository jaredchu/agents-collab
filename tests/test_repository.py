"""Checks for public repository content, the website sources and the build script.

Run from the repository root:

    python3 -m unittest discover -s tests -v

Privacy guards use generic patterns plus optional maintainer-supplied terms.
To add private identifiers without committing them, point the environment
variable AGENTS_COLLAB_PRIVATE_TERMS_FILE at a UTF-8 file outside this
repository containing one literal term per line (blank lines and lines starting
with '#' are ignored). Matches are reported by file and line, never by term.

Temporary files use the system temporary area (TMPDIR is honoured).
No network, credentials or model calls. Python 3.9+, standard library only.
"""

import html
import importlib.util
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "skills" / "agents-collab"
WEBSITE = REPO / "website"
DOC_EXAMPLE = REPO / "docs" / "examples" / "writer-review.profile.example.json"
PAGES = ("index.html", "guide/index.html", "research/index.html",
         "experiments/index.html", "story/index.html")
REPO_URL = "https://github.com/jaredchu/agents-collab"
LICENSE_URL = REPO_URL + "/blob/main/LICENSE"
# Curated package size: workflow files, the validator and setup scripts, LICENSE.
PACKAGE_FILE_COUNT = 10
TEXT_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".html", ".css", ".js", ".txt"}

_previous_flag = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    def _load(name, path):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    vp = _load("validate_profile", PACKAGE / "scripts" / "validate_profile.py")
    build = _load("build_website", REPO / "scripts" / "build_website.py")
finally:
    sys.dont_write_bytecode = _previous_flag


# --- privacy guards ------------------------------------------------------------

# Generic signs of private material: absolute home/volume paths, e-mail
# addresses and credential-shaped tokens. Assembled from pieces so this file
# does not match itself if it is ever scanned.
GENERIC_PRIVATE = re.compile(
    "|".join((
        r"/" + r"Users/[^/\s\"'<>]+",
        r"/" + r"home/[^/\s\"'<>]+",
        r"/" + r"Volumes/",
        r"[A-Za-z]:\\" + r"Users\\",
        r"[A-Za-z0-9._%+-]+@(?!example\.(?:com|org|net)\b)[A-Za-z0-9-]+\.[A-Za-z0-9.-]+",
        r"\bsk-[A-Za-z0-9_-]{16,}",
        r"\bgh[pousr]_[A-Za-z0-9]{20,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    ))
)


def private_terms_pattern(terms_file):
    """Compile literal terms from a maintainer file; None if no usable terms."""
    if not terms_file:
        return None
    lines = Path(terms_file).read_text(encoding="utf-8").splitlines()
    terms = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    if not terms:
        return None
    return re.compile("|".join(re.escape(term) for term in terms), re.IGNORECASE)


def public_files():
    """Files that are or will be public, excluding this tests/ directory."""
    roots = [REPO / name for name in ("README.md", "AGENTS.md", "CONTRIBUTING.md", "LICENSE")]
    roots += [REPO / name for name in ("docs", "website", "skills", "scripts")]
    for root in roots:
        candidates = [root] if root.is_file() else sorted(root.rglob("*")) if root.is_dir() else []
        for path in candidates:
            if (path.is_file() and (path.suffix in TEXT_SUFFIXES or path.name == "LICENSE")
                    and "__pycache__" not in path.parts):
                yield path


def scan(pattern, text):
    """Return 1-based line numbers where pattern matches."""
    return [number for number, line in enumerate(text.splitlines(), 1) if pattern.search(line)]


class PrivacyGuards(unittest.TestCase):
    def test_generic_pattern_with_synthetic_identifiers(self):
        hits = ("/" "Users/alex-example/notes", "/" "home/sample-owner/work",
                "/" "Volumes/Archive/x", "C:\\" "Users\\sample\\x",
                "owner-sample@" "acme-client.test", "sk-" "abcdefghijklmnop1234",
                "ghp_" "abcdefghijklmnopqrstuvwx")
        for text in hits:
            with self.subTest(hit=text):
                self.assertIsNotNone(GENERIC_PRIVATE.search(text))
        misses = ("~/.config/agents-collab/profile.json", "~/.local/state/agents-collab",
                  "/usr/bin/env python3", "/var/tmp/agents-collab-records",
                  "maintainer@example.com", "git stash push -- path", "$agents-collab")
        for text in misses:
            with self.subTest(miss=text):
                self.assertIsNone(GENERIC_PRIVATE.search(text))

    def test_private_terms_file_mechanism(self):
        with tempfile.TemporaryDirectory(prefix="agents-collab-terms-") as tmp:
            terms = Path(tmp) / "terms.txt"
            terms.write_text("# synthetic\nclient-acme\n\nOwner Sample\n", encoding="utf-8")
            pattern = private_terms_pattern(str(terms))
        self.assertEqual(scan(pattern, "fine\nnotes for CLIENT-ACME\nowner sample here"), [2, 3])
        self.assertEqual(scan(pattern, "a generic owner and a sample client"), [])
        self.assertIsNone(private_terms_pattern(None))

    def test_public_files_have_no_private_markers(self):
        extra = private_terms_pattern(os.environ.get("AGENTS_COLLAB_PRIVATE_TERMS_FILE"))
        for path in public_files():
            text = path.read_text(encoding="utf-8")
            rel = path.relative_to(REPO).as_posix()
            with self.subTest(file=rel):
                self.assertEqual(scan(GENERIC_PRIVATE, text), [], "generic private marker")
                if extra is not None:
                    # Report line numbers only, never the matched private term.
                    self.assertEqual(scan(extra, text), [], "maintainer-listed private term")


# --- license ----------------------------------------------------------------------

LICENSE_FILE = REPO / "LICENSE"
PACKAGE_LICENSE = PACKAGE / "LICENSE"
MIT_PERMISSION = (
    "Permission is hereby granted, free of charge, to any person obtaining a copy\n"
    "of this software and associated documentation files (the \"Software\"), to deal\n"
    "in the Software without restriction, including without limitation the rights\n"
    "to use, copy, modify, merge, publish, distribute, sublicense, and/or sell\n"
    "copies of the Software, and to permit persons to whom the Software is\n"
    "furnished to do so, subject to the following conditions:\n"
    "\n"
    "The above copyright notice and this permission notice shall be included in all\n"
    "copies or substantial portions of the Software.\n"
)
MIT_WARRANTY_START = "THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR\n"
# Statements that were true before the owner selected the MIT License.
STALE_LICENSE = re.compile(
    r"(?i)license (?:pending|is not chosen|not decided|not chosen)"
    r"|(?:have|has) not been chosen|not (?:yet )?(?:chosen|decided|selected)\b[^.]*license"
    r"|license[^.]*not (?:yet )?(?:chosen|decided|selected)|no license (?:is granted|has been|file exists)")


class License(unittest.TestCase):
    def test_root_license_is_canonical_mit(self):
        text = LICENSE_FILE.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("MIT License\n\nCopyright (c) 2026 Jared Chu\n\n"))
        self.assertIn(MIT_PERMISSION, text)
        self.assertIn(MIT_WARRANTY_START, text)
        self.assertTrue(text.endswith("DEALINGS IN THE\nSOFTWARE.\n"))
        self.assertNotIn("\r", text)

    def test_package_license_is_identical(self):
        self.assertEqual(PACKAGE_LICENSE.read_bytes(), LICENSE_FILE.read_bytes())

    def test_package_includes_license_and_helper_scripts(self):
        for name in ("LICENSE", "scripts/validate_profile.py", "scripts/setup_profile.py"):
            with self.subTest(file=name):
                self.assertIn(name, build.PACKAGE_FILES)
        self.assertEqual(len(build.PACKAGE_FILES), PACKAGE_FILE_COUNT)
        self.assertEqual(len(set(build.PACKAGE_FILES)), len(build.PACKAGE_FILES))

    def test_documents_state_the_license_and_link_it(self):
        docs = [REPO / "README.md", REPO / "CONTRIBUTING.md", REPO / "docs" / "guide.md",
                REPO / "docs" / "history.md", REPO / "docs" / "project-context.md"]
        for path in docs:
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.relative_to(REPO).as_posix()):
                self.assertIn("MIT", text)
                self.assertIn(REPO_URL, text)
                self.assertIsNone(STALE_LICENSE.search(text))
        readme = (REPO / "README.md").read_text(encoding="utf-8")
        self.assertIn("](LICENSE)", readme)
        self.assertIn("](skills/agents-collab/LICENSE)", readme)

    def test_stale_pattern_with_synthetic_statements(self):
        for text in ("Repository owner and license pending; no license is granted yet.",
                     "No license has been chosen yet.", "The license is not chosen yet.",
                     "Public owner and license are not decided."):
            with self.subTest(hit=text):
                self.assertIsNotNone(STALE_LICENSE.search(text))
        for text in ("Licensed under the MIT License.", "Publication is still pending.",
                     "The skill is MIT-licensed; deployment is not verified."):
            with self.subTest(miss=text):
                self.assertIsNone(STALE_LICENSE.search(text))


# --- documentation ----------------------------------------------------------------

class Documentation(unittest.TestCase):
    def test_relative_markdown_links_resolve(self):
        link = re.compile(r"\]\(([^)\s]+)\)")
        docs = [REPO / "README.md", REPO / "CONTRIBUTING.md", REPO / "AGENTS.md"]
        docs += sorted((REPO / "docs").rglob("*.md"))
        for path in docs:
            for target in link.findall(path.read_text(encoding="utf-8")):
                if re.match(r"[a-z]+:", target) or target.startswith("#"):
                    continue
                with self.subTest(file=path.name, target=target):
                    self.assertTrue((path.parent / target.split("#")[0]).exists())

    def test_doc_example_needs_real_model_ids(self):
        data = json.loads(DOC_EXAMPLE.read_text(encoding="utf-8"))
        paths = sorted(issue.path for issue in vp.validate_profile(data))
        self.assertEqual(paths, ["agents.reviewer.model", "agents.writer.model"])
        data["agents"]["writer"]["model"] = "vendor-a-model-1"
        data["agents"]["reviewer"]["model"] = "vendor-b-model-2"
        self.assertEqual(vp.validate_profile(data), [])

    def test_setup_wizard_command_is_documented(self):
        command = "python3 ~/.agents/skills/agents-collab/scripts/setup_profile.py"
        for path in (REPO / "README.md", REPO / "docs" / "guide.md",
                     WEBSITE / "index.html", WEBSITE / "guide" / "index.html"):
            with self.subTest(file=path.relative_to(REPO).as_posix()):
                self.assertIn(command, path.read_text(encoding="utf-8"))

    def test_website_guide_embeds_the_same_example(self):
        page = (WEBSITE / "guide" / "index.html").read_text(encoding="utf-8")
        match = re.search(r'<code id="profile-writer-review">(.*?)</code>', page, re.S)
        self.assertIsNotNone(match, "guide example block missing")
        embedded = json.loads(html.unescape(match.group(1)))
        self.assertEqual(embedded, json.loads(DOC_EXAMPLE.read_text(encoding="utf-8")))


# --- website sources --------------------------------------------------------------

class Website(unittest.TestCase):
    def read(self, rel):
        return (WEBSITE / rel).read_text(encoding="utf-8")

    def test_pages_have_accessible_structure(self):
        for rel in PAGES:
            with self.subTest(page=rel):
                text = self.read(rel)
                self.assertRegex(text, r'<html lang="en"')
                self.assertRegex(text, r'<meta name="viewport"')
                self.assertRegex(text, r"<title>[^<]+</title>")
                self.assertEqual(len(re.findall(r"<h1[\s>]", text)), 1)
                self.assertIn('<main id="main"', text)
                self.assertIn('href="#main"', text)
                self.assertIn('aria-current="page"', text)

    def test_every_page_links_to_every_section(self):
        targets = ("guide/", "research/", "experiments/", "story/")
        for rel in PAGES:
            text = self.read(rel)
            for target in targets:
                with self.subTest(page=rel, target=target):
                    self.assertRegex(text, r'href="(\.\./)*' + re.escape(target) + '"')

    def test_no_external_dependencies_forms_or_tracking(self):
        banned = re.compile(r"<form|<iframe|<input|googletagmanager|google-analytics"
                            r"|plausible\.io|gtag\(|fonts\.googleapis|document\.cookie", re.I)
        external_asset = re.compile(r'<(?:script|link|img)[^>]+(?:src|href)="(?:https?:)?//', re.I)
        for path in sorted(WEBSITE.rglob("*")):
            if path.is_file() and path.suffix in {".html", ".css", ".js"}:
                text = path.read_text(encoding="utf-8")
                with self.subTest(file=path.name):
                    self.assertIsNone(banned.search(text))
                    self.assertIsNone(external_asset.search(text))
                    self.assertNotRegex(text, r"@import\s+url\(\s*['\"]?https?:")

    def test_internal_links_resolve_in_sources(self):
        # downloads/ is generated by the build and checked there.
        self.assertEqual(build.check_links(WEBSITE, skip_prefixes=("downloads/",)), [])

    def test_repository_and_license_links(self):
        allowed = {REPO_URL, LICENSE_URL}
        for rel in PAGES:
            with self.subTest(page=rel):
                text = self.read(rel)
                # Every page links the selected repository and its LICENSE, and
                # no other repository location for this project.
                self.assertIn(f'href="{REPO_URL}"', text)
                self.assertIn(f'href="{LICENSE_URL}"', text)
                for ref in re.findall(r'href="(https?://github\.com/[^"]*agents-collab[^"]*)"', text):
                    self.assertIn(ref, allowed)
                self.assertNotRegex(text, r'href="[^"]*(?:OWNER|your-org|example-org)')
                self.assertNotIn('href="#"', text)
                self.assertIn("MIT License", text)
                # The license choice is made; stale "pending" statements must go.
                self.assertIsNone(STALE_LICENSE.search(text))


# --- build script -------------------------------------------------------------------

class BuildScript(unittest.TestCase):
    def test_package_zip_is_exact_and_reproducible(self):
        with tempfile.TemporaryDirectory(prefix="agents-collab-build-") as tmp:
            first = build.build_package_zip(Path(tmp) / "a.zip")
            second = build.build_package_zip(Path(tmp) / "b.zip")
            self.assertEqual(first, second)
            with zipfile.ZipFile(Path(tmp) / "a.zip") as archive:
                names = archive.namelist()
                self.assertEqual(sorted(names),
                                 sorted("agents-collab/" + n for n in build.PACKAGE_FILES))
                for name in build.PACKAGE_FILES:
                    with self.subTest(file=name):
                        self.assertEqual(archive.read("agents-collab/" + name),
                                         (PACKAGE / name).read_bytes())
                # The MIT notice travels with every download.
                self.assertEqual(archive.read("agents-collab/LICENSE"),
                                 (REPO / "LICENSE").read_bytes())

    def test_curated_list_matches_package_folder(self):
        actual = sorted(p.relative_to(PACKAGE).as_posix() for p in PACKAGE.rglob("*")
                        if p.is_file() and "__pycache__" not in p.parts
                        and p.name != ".DS_Store")
        self.assertEqual(actual, sorted(build.PACKAGE_FILES))

    def test_build_only_targets_repository_dist(self):
        self.assertEqual(build.DIST, REPO / "dist")
        self.assertEqual(build.SOURCE, REPO / "website")


if __name__ == "__main__":
    unittest.main()
