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
import json
import locale
import os
import shutil
import subprocess
import sys
import time

LINT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".vue")
FORMAT_ONLY_SUFFIXES = (".json", ".css", ".scss", ".md")
OPERATION_MARKERS = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "rebase-merge", "rebase-apply",
                     "SQUASH_MSG", "MERGE_MSG")


def build_crc_table():
    table = []
    for byte in range(256):
        value = byte << 24
        for _ in range(8):
            value = (value << 1 ^ 79764919) & 4294967295 if value & 2147483648 else value << 1 & 4294967295
        table.append(value)
    return table


CRC_TABLE = build_crc_table()


def cksum(data):
    """POSIX cksum of bytes, as printed in the first column."""
    crc = 0
    for byte in data:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ CRC_TABLE[((crc >> 24) ^ byte) & 0xFF]
    length = len(data)
    while length:
        crc = ((crc << 8) & 0xFFFFFFFF) ^ CRC_TABLE[((crc >> 24) ^ length) & 0xFF]
        length >>= 8
    return (~crc) & 0xFFFFFFFF


def raw_text(value):
    if isinstance(value, str):
        return value
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "null"
    if isinstance(value, (list, dict)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return json.dumps(value)


def parse_documents(text):
    decoder = json.JSONDecoder()
    documents = []
    position = 0
    length = len(text)
    while True:
        while position < length and text[position] in " \t\r\n":
            position += 1
        if position >= length:
            return documents
        document, position = decoder.raw_decode(text, position)
        documents.append(document)


def field(documents, key):
    """`jq -r '.key // ""'` over every document, as a shell variable holds it."""
    pieces = []
    for document in documents:
        if document is None:
            value = None
        elif isinstance(document, dict):
            value = document.get(key)
        else:
            raise ValueError(key)
        if value is None or value is False:
            value = ""
        pieces.append(raw_text(value))
    return "\n".join(pieces).rstrip("\n")


def run_git(arguments):
    finished = subprocess.run(["git", *arguments], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL)
    return finished.stdout.decode("utf-8", "surrogateescape")


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
        try:
            output = run_git(arguments)
        except OSError:
            continue
        for line in output.split("\n"):
            if line != "":
                names.add(line)
    existing = [name for name in sorted(names, key=collation_key) if os.path.isfile(name)]
    if not existing:
        return []
    try:
        hashes = run_git(["hash-object", "--", *existing]).split("\n")
    except OSError:
        hashes = []
    if hashes and hashes[-1] == "":
        hashes.pop()
    lines = []
    for position in range(max(len(hashes), len(existing))):
        digest = hashes[position] if position < len(hashes) else ""
        name = existing[position] if position < len(existing) else ""
        lines.append(f"{digest} {name}")
    return lines


def remove_old_snapshots(state_dir):
    now = time.time()
    for directory, _, names in os.walk(state_dir):
        for name in names:
            path = os.path.join(directory, name)
            try:
                if os.path.islink(path) or not os.path.isfile(path):
                    continue
                if int((now - os.stat(path).st_mtime) // 86400) > 2:
                    os.unlink(path)
            except OSError:
                pass


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
        documents = parse_documents(text)
        event = field(documents, "hook_event_name")
        session = field(documents, "session_id")
        cwd = field(documents, "cwd")
    except ValueError:
        return 0
    if session == "":
        return 0
    if cwd == "":
        cwd = os.environ.get("PWD") or os.getcwd()

    with contextlib.suppress(locale.Error):
        locale.setlocale(locale.LC_COLLATE, "")

    try:
        finished = subprocess.run(["git", "-C", cwd, "rev-parse", "--show-toplevel", "--absolute-git-dir"],
                                  stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return 0
    if finished.returncode != 0:
        return 0
    root, _, git_dir = finished.stdout.decode("utf-8", "surrogateescape").rstrip("\n").rpartition("\n")
    try:
        os.chdir(root)
    except OSError:
        return 0

    state_dir = os.path.join(os.environ.get("HOME", ""), ".claude", "state", "format-changed")
    try:
        os.makedirs(state_dir, exist_ok=True)
    except OSError:
        return 0
    remove_old_snapshots(state_dir)
    snapshot = f"{state_dir}/{session}-{cksum(os.fsencode(root))}"

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
