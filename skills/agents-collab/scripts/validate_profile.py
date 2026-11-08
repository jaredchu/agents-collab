#!/usr/bin/env python3
"""Check the structure of an agents-collab version 1 collaboration profile.

The profile is read as JSON data and never executed. This script does not
check model availability, credentials, native reasoning controls, permissions
or the resolved storage location, and it writes nothing. A passing result
means only that the file matches the v1 contract structure; the executing
agent still applies the instruction hierarchy, checks the actual dispatch
path and confirms the resolved records directory is outside the project.

Diagnostics name the field path and the rule. Field values are not echoed;
key names appear only when short and simple, otherwise they are redacted.

Exit status: 0 valid structure; 1 invalid profile content, including malformed
JSON, invalid UTF-8, a file over the size limit or an invalid structure; 2 an
OS error, unreadable or nonregular input (directory, FIFO, device) or a
command-line usage error.
Requires Python 3.9+ and no third-party packages.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from typing import Any, Dict, List, NamedTuple, Optional

SUPPORTED_VERSION = 1
MAX_BYTES = 256 * 1024

TOP_KEYS = (
    "version", "name", "agents", "routing", "review",
    "effort_check", "access", "bounds", "records_root",
)
AGENT_KEYS = ("model", "transport", "reasoning")
ROUTING_KEYS = ("small_writer", "substantial_writer")
REVIEW_KEYS = (
    "on_consequential_work", "candidates", "prefer_different_model",
    "recipes", "max_followup_rounds",
)
BOUNDS_KEYS = (
    "enforcement", "writer_minutes", "reviewer_minutes", "review_output_words",
)

TRANSPORTS = ("host", "codex-native", "claude-cli")
REVIEW_MODES = ("single", "none")
EFFORT_CHECKS = ("supported-control", "runtime-attestation")
ACCESS_MODES = ("existing-subscriptions", "existing-authorized-access")
ENFORCEMENT = ("required", "advisory")

CURRENT_SESSION = "current-session"
CURRENT_MODEL = "current"
INHERIT = "inherit"
# Words that look like "inherit" but would be ambiguous as a named level.
AMBIGUOUS_LEVELS = ("default", "current")

NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,39}\Z")
# Exact model identifiers: no whitespace, no leading '-' (cannot become a CLI option).
MODEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+\[\]-]{0,127}\Z")
LEVEL_RE = re.compile(r"[a-z][a-z0-9_-]{0,31}\Z")
LABEL_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}\Z")


class Issue(NamedTuple):
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class ProfileReadError(Exception):
    """The input could not be read at all (exit status 2)."""


class _Object(dict):
    """JSON object that remembers keys repeated in the source text."""

    __slots__ = ("duplicates",)


def _object_pairs(pairs: List[Any]) -> _Object:
    obj = _Object()
    obj.duplicates = []
    for key, value in pairs:
        if key in obj and key not in obj.duplicates:
            obj.duplicates.append(key)
        obj[key] = value
    return obj


def _reject_constant(token: str) -> Any:
    raise ValueError("non-finite numbers (NaN/Infinity) are not valid JSON values here")


def _label(key: Any) -> str:
    if isinstance(key, str) and LABEL_RE.match(key):
        return key
    return "<redacted key>"


def _join(path: str, key: Any) -> str:
    label = _label(key)
    return f"{path}.{label}" if path else label


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def parse_text(text: str) -> Any:
    """Parse profile text; raises ValueError with a content-free message."""
    try:
        return json.loads(
            text, object_pairs_hook=_object_pairs, parse_constant=_reject_constant
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}"
        ) from None
    except RecursionError:
        raise ValueError("invalid JSON: nesting is too deep") from None


def check_text(text: str) -> List[Issue]:
    """Parse and validate profile text, returning all issues found."""
    try:
        data = parse_text(text)
    except ValueError as exc:
        return [Issue("(file)", str(exc))]
    return validate_profile(data)


def read_profile_text(path: str) -> str:
    """Read a regular file as UTF-8. Raises ProfileReadError or ValueError.

    Symlinks are followed. The path is opened nonblocking where the platform
    supports it and checked with fstat before any read, so a FIFO or device
    is rejected instead of blocking. Reads are bounded to MAX_BYTES + 1.
    """
    flags = (os.O_RDONLY | getattr(os, "O_NONBLOCK", 0)
             | getattr(os, "O_NOCTTY", 0) | getattr(os, "O_BINARY", 0))
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise ProfileReadError(
            f"cannot read profile: {exc.strerror or type(exc).__name__}"
        ) from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ProfileReadError("profile path is not a regular file")
        chunks: List[bytes] = []
        remaining = MAX_BYTES + 1
        while remaining > 0:
            chunk = os.read(fd, min(remaining, 65536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
    except OSError as exc:
        raise ProfileReadError(
            f"cannot read profile: {exc.strerror or type(exc).__name__}"
        ) from None
    finally:
        os.close(fd)
    if len(raw) > MAX_BYTES:
        raise ValueError(f"profile exceeds {MAX_BYTES} bytes")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError("profile is not valid UTF-8") from None


def check_file(path: str) -> List[Issue]:
    try:
        text = read_profile_text(path)
    except ValueError as exc:
        return [Issue("(file)", str(exc))]
    return check_text(text)


# --- structural checks -------------------------------------------------------


def _collect_duplicates(value: Any, path: str, issues: List[Issue]) -> None:
    if isinstance(value, dict):
        for key in getattr(value, "duplicates", ()):
            issues.append(Issue(_join(path, key), "duplicate key in the same object"))
        for key, child in value.items():
            _collect_duplicates(child, _join(path, key), issues)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _collect_duplicates(child, f"{path}[{index}]", issues)


def _check_keys(obj: Dict[str, Any], path: str, allowed: tuple, issues: List[Issue]) -> None:
    for key in obj:
        if key not in allowed:
            issues.append(Issue(_join(path, key), "unknown key (not part of the v1 contract)"))
    for key in allowed:
        if key not in obj:
            issues.append(Issue(_join(path, key), "missing required key"))


def _expect_object(value: Any, path: str, issues: List[Issue]) -> Optional[Dict[str, Any]]:
    if isinstance(value, dict):
        return value
    issues.append(Issue(path, f"must be an object, not {_type_name(value)}"))
    return None


def _check_enum(obj: Dict[str, Any], key: str, path: str, allowed: tuple, issues: List[Issue]) -> None:
    if key not in obj:
        return
    value = obj[key]
    where = _join(path, key)
    if not isinstance(value, str):
        issues.append(Issue(where, f"must be a string, not {_type_name(value)}"))
    elif value not in allowed:
        issues.append(Issue(where, "must be one of: " + ", ".join(allowed)))


def _check_int(obj: Dict[str, Any], key: str, path: str, minimum: int, issues: List[Issue]) -> None:
    if key not in obj:
        return
    value = obj[key]
    where = _join(path, key)
    if type(value) is not int:  # bool is a subclass of int; reject it explicitly
        issues.append(Issue(where, f"must be an integer, not {_type_name(value)}"))
    elif value < minimum:
        kind = "positive" if minimum == 1 else "nonnegative"
        issues.append(Issue(where, f"must be a {kind} integer"))


def _check_name_field(data: Dict[str, Any], issues: List[Issue]) -> None:
    if "name" not in data:
        return
    value = data["name"]
    if not isinstance(value, str):
        issues.append(Issue("name", f"must be a string, not {_type_name(value)}"))
    elif not value.strip() or len(value) > 100 or any(ord(c) < 32 or ord(c) == 127 for c in value):
        issues.append(Issue("name", "must be a non-empty label of at most 100 printable characters"))


def _check_agents(data: Dict[str, Any], issues: List[Issue]) -> Dict[str, Optional[str]]:
    """Validate agents; return configured name -> transport (None if invalid)."""
    configured: Dict[str, Optional[str]] = {}
    if "agents" not in data:
        return configured
    agents = _expect_object(data["agents"], "agents", issues)
    if agents is None:
        return configured
    if not agents:
        issues.append(Issue("agents", "must define at least one agent"))
    for name, entry in agents.items():
        path = _join("agents", name)
        configured[name] = None
        if name == CURRENT_SESSION:
            issues.append(Issue(path, f"'{CURRENT_SESSION}' is reserved for routing and cannot name an agent"))
        elif not NAME_RE.match(name):
            issues.append(Issue(path, "agent name must be 1-40 letters, digits, '_' or '-', starting with a letter or digit"))
        entry = _expect_object(entry, path, issues)
        if entry is None:
            continue
        _check_keys(entry, path, AGENT_KEYS, issues)

        model = entry.get("model")
        if "model" in entry:
            if not isinstance(model, str):
                issues.append(Issue(path + ".model", f"must be a string, not {_type_name(model)}"))
                model = None
            elif model != CURRENT_MODEL and not MODEL_RE.match(model):
                issues.append(Issue(path + ".model", "must be 'current' or an exact model identifier (no whitespace, no leading '-', at most 128 characters)"))
                model = None

        transport = entry.get("transport")
        if "transport" in entry:
            if not isinstance(transport, str):
                issues.append(Issue(path + ".transport", f"must be a string, not {_type_name(transport)}"))
                transport = None
            elif transport not in TRANSPORTS:
                issues.append(Issue(path + ".transport", "must be one of: " + ", ".join(TRANSPORTS)))
                transport = None

        if "reasoning" in entry:
            reasoning = entry["reasoning"]
            if not isinstance(reasoning, str):
                issues.append(Issue(path + ".reasoning", f"must be a string, not {_type_name(reasoning)}"))
            elif reasoning in AMBIGUOUS_LEVELS:
                issues.append(Issue(path + ".reasoning", f"ambiguous value; use '{INHERIT}' to keep the current setting or name an exact level"))
            elif reasoning != INHERIT and not LEVEL_RE.match(reasoning):
                issues.append(Issue(path + ".reasoning", f"must be '{INHERIT}' or a lowercase named level such as the interface documents it"))

        if transport == "host" and model is not None and model != CURRENT_MODEL:
            issues.append(Issue(path + ".model", "transport 'host' is the existing lead session and cannot switch models; use 'current' and state any required lead model in task/project instructions"))
        if model == CURRENT_MODEL and transport is not None and transport != "host":
            issues.append(Issue(path + ".model", "'current' is defined only with transport 'host'; a delegated agent needs an exact model identifier"))
        configured[name] = transport

    hosts = [name for name, transport in configured.items() if transport == "host"]
    if len(hosts) > 1:
        issues.append(Issue("agents", "more than one agent uses transport 'host'; they would all denote the same lead session"))
    return configured


def _check_reference(value: Any, path: str, configured: Dict[str, Optional[str]],
                     issues: List[Issue], allow_current_session: bool, reviewer: bool) -> bool:
    if not isinstance(value, str):
        issues.append(Issue(path, f"must be a string agent name, not {_type_name(value)}"))
        return False
    if allow_current_session and value == CURRENT_SESSION:
        return True
    if value not in configured:
        extra = f" or '{CURRENT_SESSION}'" if allow_current_session else ""
        issues.append(Issue(path, f"must name a configured agent{extra}"))
        return False
    if reviewer and configured[value] == "host":
        issues.append(Issue(path, "the current lead (transport 'host') cannot serve as a fresh independent reviewer"))
        return False
    return True


def _check_reviewer_list(value: Any, path: str, configured: Dict[str, Optional[str]],
                         issues: List[Issue], require_nonempty: bool, empty_hint: str) -> Optional[List[Any]]:
    if not isinstance(value, list):
        issues.append(Issue(path, f"must be an array, not {_type_name(value)}"))
        return None
    if require_nonempty and not value:
        issues.append(Issue(path, empty_hint))
    seen = set()
    for index, member in enumerate(value):
        where = f"{path}[{index}]"
        if _check_reference(member, where, configured, issues, False, True):
            if member in seen:
                issues.append(Issue(where, "duplicate agent; repeating an agent does not add an independent reviewer"))
            seen.add(member)
    return value


def _check_routing(data: Dict[str, Any], configured: Dict[str, Optional[str]], issues: List[Issue]) -> None:
    if "routing" not in data:
        return
    routing = _expect_object(data["routing"], "routing", issues)
    if routing is None:
        return
    _check_keys(routing, "routing", ROUTING_KEYS, issues)
    for key in ROUTING_KEYS:
        if key in routing:
            _check_reference(routing[key], "routing." + key, configured, issues, True, False)


def _check_review(data: Dict[str, Any], configured: Dict[str, Optional[str]], issues: List[Issue]) -> None:
    if "review" not in data:
        return
    review = _expect_object(data["review"], "review", issues)
    if review is None:
        return
    _check_keys(review, "review", REVIEW_KEYS, issues)
    _check_enum(review, "on_consequential_work", "review", REVIEW_MODES, issues)

    if "candidates" in review:
        _check_reviewer_list(
            review["candidates"], "review.candidates", configured, issues,
            require_nonempty=review.get("on_consequential_work") == "single",
            empty_hint="must list at least one reviewer when on_consequential_work is 'single'",
        )

    if "prefer_different_model" in review and not isinstance(review["prefer_different_model"], bool):
        issues.append(Issue("review.prefer_different_model",
                            f"must be true or false, not {_type_name(review['prefer_different_model'])}"))

    if "recipes" in review:
        recipes = _expect_object(review["recipes"], "review.recipes", issues)
        for name, members in (recipes or {}).items():
            path = _join("review.recipes", name)
            if not NAME_RE.match(name):
                issues.append(Issue(path, "recipe name must be 1-40 letters, digits, '_' or '-', starting with a letter or digit"))
            _check_reviewer_list(members, path, configured, issues,
                                 require_nonempty=True, empty_hint="recipe must list at least one reviewer")

    _check_int(review, "max_followup_rounds", "review", 0, issues)


def _check_bounds(data: Dict[str, Any], issues: List[Issue]) -> None:
    if "bounds" not in data:
        return
    bounds = _expect_object(data["bounds"], "bounds", issues)
    if bounds is None:
        return
    _check_keys(bounds, "bounds", BOUNDS_KEYS, issues)
    _check_enum(bounds, "enforcement", "bounds", ENFORCEMENT, issues)
    for key in ("writer_minutes", "reviewer_minutes", "review_output_words"):
        _check_int(bounds, key, "bounds", 1, issues)


def _check_records_root(data: Dict[str, Any], issues: List[Issue]) -> None:
    """Lexical checks only; nothing is expanded, resolved or created."""
    if "records_root" not in data:
        return
    value = data["records_root"]
    if not isinstance(value, str):
        issues.append(Issue("records_root", f"must be a string, not {_type_name(value)}"))
        return
    if not value or value.strip() != value:
        issues.append(Issue("records_root", "must be a non-empty path without surrounding whitespace"))
        return
    if any(ord(c) < 32 or ord(c) == 127 for c in value):
        issues.append(Issue("records_root", "must not contain control characters"))
        return
    if value == "~" or value.startswith("~/"):
        rest = value[1:]
    elif value.startswith("~"):
        issues.append(Issue("records_root", "only '~/' (the current owner's home) is supported, not '~user' forms"))
        return
    elif value.startswith("/"):
        rest = value
    else:
        issues.append(Issue("records_root", "must be absolute or start with '~/'; a relative root would resolve inside the working directory, often a project"))
        return
    parts = [part for part in rest.split("/") if part]
    if any(part in (".", "..") for part in parts):
        issues.append(Issue("records_root", "must not contain '.' or '..' components"))
    elif not parts:
        issues.append(Issue("records_root", "must name a dedicated directory, not the filesystem root or home directory itself"))


def validate_profile(data: Any) -> List[Issue]:
    """Validate parsed profile data against the v1 contract. Never mutates data."""
    issues: List[Issue] = []
    _collect_duplicates(data, "", issues)
    if not isinstance(data, dict):
        issues.append(Issue("(root)", f"profile must be a JSON object, not {_type_name(data)}"))
        return issues

    if "version" not in data:
        issues.append(Issue("version", "missing required key; the contract version must be known before other fields are interpreted"))
        return issues
    version = data["version"]
    if type(version) is not int:
        issues.append(Issue("version", f"must be the integer {SUPPORTED_VERSION}, not {_type_name(version)}"))
        return issues
    if version != SUPPORTED_VERSION:
        issues.append(Issue("version", f"unsupported schema version {version}; only {SUPPORTED_VERSION} is supported, other fields were not interpreted"))
        return issues

    _check_keys(data, "", TOP_KEYS, issues)
    _check_name_field(data, issues)
    configured = _check_agents(data, issues)
    _check_routing(data, configured, issues)
    _check_review(data, configured, issues)
    _check_enum(data, "effort_check", "", EFFORT_CHECKS, issues)
    _check_enum(data, "access", "", ACCESS_MODES, issues)
    _check_bounds(data, issues)
    _check_records_root(data, issues)
    return issues


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="validate_profile.py",
        description="Check an agents-collab v1 profile's structure. Reads JSON only; "
                    "does not check model availability, credentials, permissions or storage.",
    )
    parser.add_argument("profile", help="path to the profile JSON file")
    args = parser.parse_args(argv)

    try:
        issues = check_file(args.profile)
    except ProfileReadError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if issues:
        print(f"invalid profile: {len(issues)} issue(s)", file=sys.stderr)
        for issue in issues:
            print(f"  {issue}", file=sys.stderr)
        return 1
    print("valid v1 profile structure (model availability, runtime controls, "
          "permissions and resolved storage were not checked)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
