#!/usr/bin/env python3
"""Interactively create an agents-collab version 1 collaboration profile.

This is a configuration wizard only. It asks a few questions (writer,
reviewers, per-agent reasoning requests, profile label and private records
root), builds a v1 profile, checks it with the bundled validator
(validate_profile.py, unchanged), previews it and writes it only after an
explicit confirmation. It requests no credentials and contacts no model,
provider or network service.

A generated profile does not establish that a model exists or is accessible,
that a transport works, that a reasoning level is supported or honoured,
any permission or access, or where the records directory actually resolves.
Reasoning levels are requests. The executing lead still checks each dispatch
and confirms the resolved records directory is outside the project.

The current lead always stays the existing session (transport host, model
current, reasoning inherit); the wizard cannot switch its model or effort.

Usage:
  python3 setup_profile.py [--output PATH] [--dry-run] [--replace]

Default output: ~/.config/agents-collab/profile.json. An existing profile is
preserved unless --replace is given and the final confirmation accepts it. A
symbolic link (including a dangling one) or nonregular file at the output path
is never followed or replaced. The file is staged beside the target with mode
0600 and published atomically: a new target is published without clobbering a
file that appeared meanwhile; a replacement is refused if the original changed
after the wizard started (a best-effort check, not OS-level isolation). Missing
parent directories are created with mode 0700; existing ones are not changed.
No backups, transcripts or other files are kept.

Exit status: 0 profile written, or preview completed with --dry-run;
1 cancelled (declined, end of input or repeated invalid answers), nothing
written; 2 usage, output-path or write error, nothing written; 130 interrupted
with Ctrl-C, nothing written.
Requires Python 3.9+ and no third-party packages.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, TextIO, Tuple

_HERE = Path(__file__).resolve().parent


def _load_validator() -> Any:
    """Load the sibling validator without writing bytecode caches."""
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location(
            "agents_collab_validate_profile", _HERE / "validate_profile.py")
        if spec is None or spec.loader is None:
            raise ImportError("validate_profile.py not found beside setup_profile.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.dont_write_bytecode = previous


vp = _load_validator()

DEFAULT_OUTPUT = "~/.config/agents-collab/profile.json"
DEFAULT_RECORDS_ROOT = "~/.local/state/agents-collab"
DEFAULT_LABEL = "personal"
DEFAULT_RECIPE = "all-reviewers"
MAX_REVIEWERS = 8
MAX_ATTEMPTS = 5

TRANSPORT_CHOICES = (
    ("codex-native", "codex-native (native subagent of a Codex lead)"),
    ("claude-cli", "claude-cli (installed, authenticated Claude CLI)"),
)
COMMON_LEVELS = ("low", "medium", "high")

# Neutral values shared with the shipped examples. They add no spending,
# access or runtime authority; edit the saved file by hand to change them.
FIXED_SETTINGS = {
    "prefer_different_model": True,
    "max_followup_rounds": 1,
    "effort_check": "supported-control",
    "access": "existing-authorized-access",
    "bounds": {"enforcement": "advisory", "writer_minutes": 30,
               "reviewer_minutes": 10, "review_output_words": 800},
}

INTRO = """\
agents-collab profile setup (configuration only)
This builds a v1 profile. It asks for no credentials and contacts no model or
service. It cannot check that a model ID exists, that you can use it, that a
transport works or that a reasoning level is supported: levels are requests the
lead checks before dispatch. The lead stays your current session; this does not
switch its model or effort. Press Ctrl-C or end input to cancel without writing.
"""


class Cancelled(Exception):
    """The user declined, input ended or answers stayed invalid."""


class TargetError(Exception):
    """The output path cannot be written safely; nothing was written."""


# --- prompting -----------------------------------------------------------------


class Prompter:
    def __init__(self, stdin: TextIO, stdout: TextIO) -> None:
        self.stdin = stdin
        self.stdout = stdout
        try:
            self.use_input = (stdin is sys.stdin and stdout is sys.stdout
                              and stdin.isatty())
        except (AttributeError, ValueError):
            self.use_input = False

    def say(self, text: str = "") -> None:
        print(text, file=self.stdout)

    def ask(self, prompt: str) -> str:
        if self.use_input:
            try:
                return input(prompt)
            except EOFError:
                raise Cancelled("input ended") from None
        self.stdout.write(prompt)
        self.stdout.flush()
        line = self.stdin.readline()
        if not line:
            raise Cancelled("input ended")
        return line.rstrip("\r\n")


def ask_text(p: Prompter, prompt: str, check: Callable[[str], Optional[str]],
             default: Optional[str] = None, show_default: bool = True) -> str:
    suffix = f" [{default}]" if default is not None and show_default else ""
    for _ in range(MAX_ATTEMPTS):
        answer = p.ask(f"{prompt}{suffix}: ").strip()
        if not answer and default is not None:
            answer = default
        error = check(answer)
        if error is None:
            return answer
        p.say(f"  {error}")
    raise Cancelled("too many invalid answers")


def choose(p: Prompter, title: str, options: Sequence[str],
           default: Optional[int] = None) -> int:
    """Return the zero-based index of the chosen option."""
    p.say(title)
    for number, label in enumerate(options, 1):
        p.say(f"  {number}) {label}")

    def check(answer: str) -> Optional[str]:
        if re.fullmatch(r"[0-9]{1,2}", answer) and 1 <= int(answer) <= len(options):
            return None
        return f"Enter a number from 1 to {len(options)}."

    answer = ask_text(p, "Choice", check, None if default is None else str(default))
    return int(answer) - 1


def ask_yes_no(p: Prompter, prompt: str, default: bool) -> bool:
    def check(answer: str) -> Optional[str]:
        return None if answer.lower() in ("y", "yes", "n", "no") else "Answer y or n."

    answer = ask_text(p, prompt + (" [Y/n]" if default else " [y/N]"), check,
                      "y" if default else "n", show_default=False)
    return answer.lower() in ("y", "yes")


# --- field checks (reusing the validator's rules) ------------------------------


def check_label(value: str) -> Optional[str]:
    issues: List[Any] = []
    vp._check_name_field({"name": value}, issues)
    return "Use 1-100 printable characters." if issues else None


def check_model(value: str) -> Optional[str]:
    if not value:
        return "Enter the exact model ID your interface uses; there is no default."
    if value == vp.CURRENT_MODEL:
        return "'current' means the lead session; a delegate needs an exact model ID."
    if not vp.MODEL_RE.match(value):
        return ("Use the exact ID: letters, digits and . _ : / @ + [ ] -, starting "
                "with a letter or digit, no spaces, at most 128 characters.")
    return None


def check_level(value: str) -> Optional[str]:
    if value in vp.AMBIGUOUS_LEVELS:
        return f"'{value}' is ambiguous; choose inherit from the menu instead."
    if value != vp.INHERIT and not vp.LEVEL_RE.match(value):
        return ("Use a lowercase level as the interface documents it: a letter, "
                "then letters, digits, '_' or '-' (at most 32).")
    return None


def check_recipe_name(value: str) -> Optional[str]:
    if vp.NAME_RE.match(value):
        return None
    return "Use 1-40 letters, digits, '_' or '-', starting with a letter or digit."


def check_records_root(value: str) -> Optional[str]:
    issues: List[Any] = []
    vp._check_records_root({"records_root": value}, issues)
    return f"records_root {issues[0].message}." if issues else None


def check_reviewer_count(value: str) -> Optional[str]:
    if re.fullmatch(r"[0-9]{1,2}", value) and int(value) <= MAX_REVIEWERS:
        return None
    return f"Enter a number from 0 to {MAX_REVIEWERS}."


# --- questions -----------------------------------------------------------------


def ask_reasoning(p: Prompter, role: str) -> str:
    options = ["inherit (keep the interface's current setting; not 'high')"]
    options += list(COMMON_LEVELS)
    options.append("custom lowercase level")
    index = choose(p, f"Reasoning request for {role} (not verified; the lead checks support):",
                   options, default=1)
    if index == 0:
        return vp.INHERIT
    if index <= len(COMMON_LEVELS):
        return COMMON_LEVELS[index - 1]
    return ask_text(p, "Custom level, as the interface documents it", check_level)


def ask_delegate(p: Prompter, role: str) -> Dict[str, str]:
    model = ask_text(p, f"Exact model ID for {role}", check_model)
    index = choose(p, f"Transport for {role}:", [label for _, label in TRANSPORT_CHOICES])
    reasoning = ask_reasoning(p, role)
    return {"model": model, "transport": TRANSPORT_CHOICES[index][0], "reasoning": reasoning}


def collect_answers(p: Prompter) -> Dict[str, Any]:
    label = ask_text(p, "Profile label", check_label, DEFAULT_LABEL)

    p.say()
    writer = None
    if choose(p, "Who writes substantial changes?",
              ["the current lead session (no delegated writer)",
               "a delegated writer model"], default=1) == 1:
        writer = ask_delegate(p, "the writer")

    p.say()
    p.say("Independent reviewers each run in a fresh session; the lead cannot be one.")
    count = int(ask_text(p, f"Reviewers to configure (0-{MAX_REVIEWERS})",
                         check_reviewer_count, "0"))
    reviewers: List[Dict[str, str]] = []
    for number in range(1, count + 1):
        p.say()
        reviewers.append(ask_delegate(p, f"reviewer {number}"))

    review_by_default = False
    recipe = None
    if reviewers:
        p.say()
        review_by_default = ask_yes_no(
            p, "On consequential work, request one reviewer from this pool by default?", True)
    if len(reviewers) > 1:
        p.say("A named recipe lists all reviewers for when you ask for them together.")
        p.say("It is not run automatically: the lead uses it only when you name it")
        p.say("(or a policy calls for it) and still checks each reviewer before dispatch.")
        recipe = ask_text(p, "Recipe name", check_recipe_name, DEFAULT_RECIPE)

    p.say()
    p.say("Private records root: outside every project; the lead confirms the")
    p.say("resolved task directory does not overlap the project before writing records.")
    records_root = ask_text(p, "Records root", check_records_root, DEFAULT_RECORDS_ROOT)
    return {"label": label, "writer": writer, "reviewers": reviewers,
            "review_by_default": review_by_default, "recipe": recipe,
            "records_root": records_root}


def build_profile(answers: Dict[str, Any]) -> Dict[str, Any]:
    agents: Dict[str, Dict[str, str]] = {
        "lead": {"model": vp.CURRENT_MODEL, "transport": "host", "reasoning": vp.INHERIT},
    }
    if answers["writer"]:
        agents["writer"] = dict(answers["writer"])
    names = []
    for number, reviewer in enumerate(answers["reviewers"], 1):
        name = f"reviewer{number}"
        agents[name] = dict(reviewer)
        names.append(name)
    recipes = {answers["recipe"]: list(names)} if answers.get("recipe") else {}
    return {
        "version": vp.SUPPORTED_VERSION,
        "name": answers["label"],
        "agents": agents,
        "routing": {
            "small_writer": vp.CURRENT_SESSION,
            "substantial_writer": "writer" if answers["writer"] else vp.CURRENT_SESSION,
        },
        "review": {
            "on_consequential_work": "single" if answers["review_by_default"] else "none",
            "candidates": names,
            "prefer_different_model": FIXED_SETTINGS["prefer_different_model"],
            "recipes": recipes,
            "max_followup_rounds": FIXED_SETTINGS["max_followup_rounds"],
        },
        "effort_check": FIXED_SETTINGS["effort_check"],
        "access": FIXED_SETTINGS["access"],
        "bounds": dict(FIXED_SETTINGS["bounds"]),
        "records_root": answers["records_root"],
    }


def render(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2) + "\n"


def summary(data: Dict[str, Any], target: Path, existing: bool) -> List[str]:
    agents = data["agents"]

    def delegate(name: str) -> str:
        entry = agents[name]
        return f"{entry['model']} via {entry['transport']}, reasoning {entry['reasoning']}"

    writer = data["routing"]["substantial_writer"]
    review = data["review"]
    bounds = data["bounds"]
    lines = [
        f"Target:    {target} ({'replaces the existing profile' if existing else 'new file'})",
        f"Label:     {data['name']}",
        "Lead:      current session (host, model current, reasoning inherit); not switched",
        "Writer:    " + ("current lead" if writer == vp.CURRENT_SESSION
                         else f"{writer}: {delegate(writer)}; small work stays with the lead"),
    ]
    if review["candidates"]:
        for name in review["candidates"]:
            lines.append(f"Reviewer:  {name}: {delegate(name)}")
    else:
        lines.append("Reviewers: none")
    lines.append("Review:    " + ("one reviewer from the pool on consequential work"
                                  if review["on_consequential_work"] == "single"
                                  else "none by default; project/task requirements still apply"))
    for name, members in review["recipes"].items():
        lines.append(f"Recipe:    {name} = {', '.join(members)} (only when requested)")
    lines.append(f"Records:   {data['records_root']}")
    lines.append(f"Fixed:     effort_check {data['effort_check']}, access {data['access']}, "
                 f"advisory targets {bounds['writer_minutes']}/{bounds['reviewer_minutes']} min "
                 f"and {bounds['review_output_words']} words, "
                 f"{review['max_followup_rounds']} follow-up round")
    return lines


# --- safe publication ----------------------------------------------------------

Identity = Tuple[int, int, int, int, int, int]


def inspect_target(path: Path) -> Optional[Identity]:
    """Identity of an existing regular file, None if absent. Never follows links."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return None
    except NotADirectoryError:
        raise TargetError("a parent of the output path is not a directory") from None
    except OSError as exc:
        raise TargetError(f"cannot inspect the output path: {exc.strerror or type(exc).__name__}") from None
    if stat.S_ISLNK(st.st_mode):
        raise TargetError("the output path is a symbolic link; it was not followed or changed")
    if not stat.S_ISREG(st.st_mode):
        raise TargetError("the output path exists but is not a regular file; it was left unchanged")
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def ensure_parent(parent: Path) -> None:
    """Create missing directories with mode 0700; leave existing ones unchanged."""
    missing: List[Path] = []
    current = parent
    while True:
        try:
            st = os.stat(current)
        except FileNotFoundError:
            missing.append(current)
            if current.parent == current:
                break
            current = current.parent
            continue
        except OSError as exc:
            raise TargetError(f"cannot inspect a parent directory: {exc.strerror or type(exc).__name__}") from None
        if not stat.S_ISDIR(st.st_mode):
            raise TargetError("a parent of the output path is not a directory")
        break
    for directory in reversed(missing):
        try:
            os.mkdir(directory, 0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise TargetError("a parent of the output path is not a directory") from None
            continue  # appeared concurrently; its permissions are not ours to change
        except OSError as exc:
            raise TargetError(f"cannot create a parent directory: {exc.strerror or type(exc).__name__}") from None
        try:
            os.chmod(directory, 0o700)  # in case the umask removed owner bits
        except OSError as exc:
            raise TargetError(f"cannot secure a new parent directory: {exc.strerror or type(exc).__name__}") from None


def _fsync_directory(directory: Path) -> None:
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def publish(target: Path, text: str, original: Optional[Identity]) -> None:
    """Atomically write text to target with mode 0600.

    original None: target must still be absent (no clobber). Otherwise target
    must still be the same regular file observed when the wizard started.
    The staged temporary file is always removed; no backup is kept.
    """
    parent = target.parent
    ensure_parent(parent)
    payload = text.encode("utf-8")
    try:
        fd, tmp_name = tempfile.mkstemp(prefix="." + target.name + ".", suffix=".tmp",
                                        dir=str(parent))
    except OSError as exc:
        raise TargetError(f"cannot stage the profile: {exc.strerror or type(exc).__name__}") from None
    tmp = Path(tmp_name)
    published = False
    try:
        try:
            if hasattr(os, "fchmod"):
                os.fchmod(fd, 0o600)
            view = memoryview(payload)
            while view:
                view = view[os.write(fd, view):]
            os.fsync(fd)
        finally:
            os.close(fd)
        if original is None:
            try:
                os.link(tmp, target)
            except FileExistsError:
                raise TargetError("a file appeared at the output path while the wizard ran; "
                                  "it was left unchanged") from None
            except (OSError, NotImplementedError) as exc:
                raise TargetError("cannot publish without risking an overwrite here "
                                  f"({getattr(exc, 'strerror', None) or type(exc).__name__}); "
                                  "choose another --output location") from None
        else:
            if inspect_target(target) != original:
                raise TargetError("the existing profile changed or disappeared after the wizard "
                                  "started; nothing was replaced")
            os.replace(tmp, target)
            published = True
        _fsync_directory(parent)
    except OSError as exc:
        raise TargetError(f"cannot write the profile: {exc.strerror or type(exc).__name__}") from None
    finally:
        if not published:
            try:
                os.unlink(tmp)
            except FileNotFoundError:
                pass


# --- command line --------------------------------------------------------------


def resolve_output(value: Optional[str]) -> Path:
    raw = os.path.expanduser(value if value else DEFAULT_OUTPUT)
    if raw.startswith("~"):
        raise TargetError("cannot expand '~' in the output path")
    return Path(os.path.abspath(raw))


def main(argv: Optional[List[str]] = None, stdin: Optional[TextIO] = None,
         stdout: Optional[TextIO] = None, stderr: Optional[TextIO] = None) -> int:
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    parser = argparse.ArgumentParser(
        prog="setup_profile.py",
        description="Create an agents-collab v1 profile interactively. Configuration only: "
                    "no credentials, model calls or availability checks.")
    parser.add_argument("--output", metavar="PATH",
                        help=f"profile path to write (default: {DEFAULT_OUTPUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="ask and preview only; write nothing")
    parser.add_argument("--replace", action="store_true",
                        help="allow replacing an existing regular profile after confirmation")
    args = parser.parse_args(argv)

    def fail(message: str) -> int:
        print(f"error: {message}. Nothing was written.", file=stderr)
        return 2

    try:
        target = resolve_output(args.output)
        original = inspect_target(target)
    except TargetError as exc:
        return fail(str(exc))
    if original is not None and not args.replace and not args.dry_run:
        return fail(f"a profile already exists at {target} and was left unchanged; "
                    "use --replace to replace it after confirmation, --output for another "
                    "path or --dry-run to preview")

    p = Prompter(stdin, stdout)
    try:
        p.say(INTRO)
        if original is not None and not args.replace:
            p.say("Note: a profile exists at the target; this dry run leaves it unchanged.\n")
        data = build_profile(collect_answers(p))
        text = render(data)
        issues = vp.validate_profile(data) + vp.check_text(text)
        if issues:  # defensive: every answer was already checked
            print("error: the generated profile failed validation; nothing was written:",
                  file=stderr)
            for issue in issues:
                print(f"  {issue}", file=stderr)
            return 2

        p.say()
        p.say("Preview")
        for line in summary(data, target, original is not None):
            p.say("  " + line)
        p.say()
        p.say(text.rstrip("\n"))
        p.say()
        p.say("Structure validated. Not checked: model availability or access, transports,")
        p.say("reasoning support, permissions or the resolved records location.")
        if args.dry_run:
            p.say("Dry run: nothing was written.")
            return 0
        verb = "Replace the existing profile at" if original is not None else "Write the profile to"
        if not ask_yes_no(p, f"{verb} {target}?", False):
            p.say("Cancelled; nothing was written.")
            return 1
    except Cancelled as exc:
        print(f"\nCancelled ({exc}); nothing was written.", file=stderr)
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted; nothing was written.", file=stderr)
        return 130

    try:
        publish(target, text, original)
    except TargetError as exc:
        return fail(str(exc))
    except KeyboardInterrupt:
        state = "the profile may have been written" if target.exists() else "nothing was written"
        print(f"\nInterrupted; {state}.", file=stderr)
        return 130
    p.say(f"Saved {target} (mode 0600).")
    p.say("Check it again any time with:")
    p.say(f"  python3 {_HERE / 'validate_profile.py'} {target}")
    p.say("Before dispatch the lead still checks model access, effort support and that")
    p.say("the resolved records directory is outside the project.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
