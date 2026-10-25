#!/usr/bin/env python3
"""Stop and UserPromptSubmit hook: format only the files a turn changed, once, at turn end.

UserPromptSubmit snapshots the dirty set with content hashes. Stop formats files new
to that set or whose hash moved, so untouched hand edits are left alone. Silent and always exits 0.
Stop formats nothing while a merge, squash merge, cherry-pick, revert or rebase is unfinished: the files the other
side brought in are in the dirty set, and reformatting them leaves unstaged edits behind the commit.
A commit or reset deletes the message files git leaves for a squash merge or `cherry-pick -n`, so formatting resumes
then.
CLAUDE_SKIP_HOOKS set to any non-empty value exits 0. Snapshots live in ~/.claude/state/format-changed and
snapshots older than 2 days are deleted on every run.
"""
import contextlib
import locale
import os
import shutil
import subprocess
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils

LINT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".vue")
FORMAT_ONLY_SUFFIXES = (".json", ".css", ".scss", ".md")
OPERATION_MARKERS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply",
                     "SQUASH_MSG", "MERGE_MSG")


def event_field(documents, key):
    """`jq -r '.key // ""'` over every document, as a shell variable holds it. Raises JqError on a non-object."""
    pieces = [hook_input.jq_str(hook_input.index(document, key)) for document in documents]
    return "\n".join(pieces).rstrip("\n")


def collation_key(path):
    try:
        return (locale.strxfrm(path), path)
    except (ValueError, OSError):
        return (path, path)


def dirty_hashes():
    """Lines of "<hash> <path>" for every existing file in the dirty set, sorted like `sort -u`."""
    names = set()
    for arguments in (
        ["diff", "--name-only", "--diff-filter=d", "HEAD"],
        ["ls-files", "--others", "--exclude-standard"],
    ):
        output = script_utils.git_output(".", *arguments) or ""
        for line in output.split("\n"):
            if line != "":
                names.add(line)
    existing = [name for name in sorted(names, key=collation_key) if os.path.isfile(name)]
    if not existing:
        return []

    hash_output = script_utils.git_output(".", "hash-object", "--", *existing)
    hashes = hash_output.split("\n") if hash_output else []
    lines = []
    for position in range(max(len(hashes), len(existing))):
        digest = hashes[position] if position < len(hashes) else ""
        name = existing[position] if position < len(existing) else ""
        lines.append(f"{digest} {name}")
    return lines


def run_quiet(command):
    with contextlib.suppress(OSError):
        subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def tool_available(name):
    if shutil.which(name):
        return True
    local = os.path.join("node_modules", ".bin", name)
    return os.path.exists(local) and os.access(local, os.X_OK)


def operation_in_progress(git_dir):
    """True while the repo's git dir holds a merge, cherry-pick, revert or rebase marker."""
    return any(os.path.lexists(os.path.join(git_dir, marker)) for marker in OPERATION_MARKERS)


def snapshot_difference(snapshot_lines):
    known = set(snapshot_lines)
    paths = []
    for line in dirty_hashes():
        if line in known:
            continue
        paths.append(line.split(" ", 1)[1] if " " in line else line)
    return paths


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    try:
        text = sys.stdin.buffer.read().decode("utf-8", "replace").rstrip("\n")
        documents = hook_input.parse_documents(text)
        event = event_field(documents, "hook_event_name")
        session = event_field(documents, "session_id")
        cwd = event_field(documents, "cwd")
    except (ValueError, hook_input.JqError):
        return 0
    if session == "":
        return 0
    if cwd == "":
        cwd = os.environ.get("PWD") or os.getcwd()

    with contextlib.suppress(locale.Error):
        locale.setlocale(locale.LC_COLLATE, "")

    repo_dirs = script_utils.git_output(".", "-C", cwd, "rev-parse", "--show-toplevel", "--absolute-git-dir")
    if repo_dirs is None:
        return 0
    root, _, git_dir = repo_dirs.rpartition("\n")
    try:
        os.chdir(root)
    except OSError:
        return 0

    state_dir = os.path.join(os.environ.get("HOME", ""), ".claude", "state", "format-changed")
    try:
        os.makedirs(state_dir, exist_ok=True)
    except OSError:
        return 0
    hook_input.prune_old_state_files(state_dir)
    root_checksum = hook_input.cksum(os.fsencode(root))
    snapshot = f"{state_dir}/{session}-{root_checksum}"

    if event == "UserPromptSubmit":
        lines = dirty_hashes()
        try:
            with open(snapshot, "w", encoding="utf-8", errors="surrogateescape") as handle:
                handle.write("".join(line + "\n" for line in lines))
        except OSError:
            pass
        return 0
    if event != "Stop":
        return 0

    if operation_in_progress(git_dir):
        return 0

    if not os.path.isfile(snapshot):
        return 0
    try:
        with open(snapshot, encoding="utf-8", errors="surrogateescape") as handle:
            snapshot_lines = handle.read().split("\n")
    except OSError:
        snapshot_lines = []
    if snapshot_lines and snapshot_lines[-1] == "":
        snapshot_lines.pop()

    format_files = []
    lint_files = []
    for path in snapshot_difference(snapshot_lines):
        if path.endswith(LINT_SUFFIXES):
            format_files.append(path)
            lint_files.append(path)
        elif path.endswith(FORMAT_ONLY_SUFFIXES):
            format_files.append(path)
    if not format_files:
        return 0

    if lint_files:
        if tool_available("oxlint"):
            run_quiet(["npx", "oxlint", "--fix", *lint_files])
        elif os.path.exists("node_modules/.bin/eslint") and os.access("node_modules/.bin/eslint", os.X_OK):
            run_quiet(["npx", "eslint", "--fix", "--no-warn-ignored", "--max-warnings=0", *lint_files])

    if tool_available("oxfmt"):
        run_quiet(["npx", "oxfmt", *format_files])
    else:
        run_quiet(["npx", "--yes", "prettier", "--write", *format_files])
    return 0


if __name__ == "__main__":
    sys.exit(main())
