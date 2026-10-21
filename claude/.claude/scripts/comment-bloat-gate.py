#!/usr/bin/env python3
"""PostToolUse hook on Write|Edit: block workflow-marker leaks and comment bloat in committed code.

Enforces coder-core's density cap and _shared/code-vocabulary.md deterministically. Reads the edited file from
disk. A marker counts only when the edit itself contributed the line (exact whole-line match against the new text).
Exit 2 with the reason on stderr blocks; every other path exits 0. Any error exits 0.
"""
import json
import os
import re
import sys

import hook_input
import script_utils
from hook_input import emit_stderr

GIT_PROBE_TIMEOUT_SECONDS = 2

SPACE = r"\s"
NONBLANK = re.compile(r"\S")
CODE_FILE = re.compile(
    r"\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|rb|java|kt|swift|php|c|h|cc|cpp|hpp|lua|qml|sh|bash|zsh|yml|yaml|json|sql)$",
    re.M)

# JSDoc continuation `*` needs a space or line end after it: `**unpacking` and `*args` are code.
COMMENT_LINE = re.compile(r"^" + SPACE + r"*(//|#|\*(" + SPACE + r"|$)|--|;|/\*|\"\"\"|<!--)")
# A bare docstring/JSDoc delimiter is structure, not prose.
DELIMITER_LINE = re.compile(r"^" + SPACE + r"*(\"\"\"|'''|/\*\*?|\*/)" + SPACE + r"*$")

CASE_INSENSITIVE_MARKERS = [re.compile(pattern, re.I) for pattern in (
    r"\bphases?" + SPACE + r"*[0-9]",
    r"docs/plans/",
    r"\b(PR|issue)" + SPACE + r"*#[0-9]+",
    r"per the (architect|plan|spec|ledger)",
    r"written by the (coder|architect|poller|assistant|agent)",
    r"decision ledger|acceptance criteri|acceptance contract",
    r"plan[ -]?impact",
    r"user ruling",
    r"end-of-branch",
)]
CASE_SENSITIVE_MARKERS = [re.compile(pattern) for pattern in (
    r"\(D[0-9]+[):]",
    r"\bD[0-9]+:",
    r"\bPD[0-9]+\b",
    r"(^|[^#\w])AC[0-9]+\b",
)]
NOT_A_MARKER = re.compile(
    r"utf-8|sha-[0-9]|iso-[0-9]|rfc-[0-9]|aes-[0-9]|http-[0-9]|base-[0-9]|dp-[0-9]|hdmi-[0-9]|dvi-[0-9]|usb-[0-9]",
    re.I)

DENSITY_CAP_PERCENT = 22
MIN_LINES_FOR_DENSITY = 30


def jq_text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return json.dumps(value)


def first_present(tool_input, *keys):
    """jq `.a // .b // empty`: null and false fall through to the next key."""
    for key in keys:
        value = tool_input.get(key)
        if value is not None and value is not False:
            return jq_text(value).rstrip("\n")
    return ""


def read_text(path):
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8", "surrogateescape")
    except OSError:
        return ""


def surface_of(file_path):
    if "/.claude/worktrees/" in file_path or file_path.startswith(".claude/worktrees/"):
        marker = ".claude/worktrees/"
        surface = file_path[file_path.index(marker) + len(marker):]
        slash = surface.find("/")
        if slash >= 0:
            surface = surface[slash + 1:]
        return surface
    return file_path


def marker_rows(file_lines, comments_only=False):
    """Numbered non-blank lines carrying a workflow marker, ordered by line number.

    comments_only limits the scan to comment lines, for formats whose values are data, not prose."""
    rows = []
    for number, line in enumerate(file_lines, 1):
        if not NONBLANK.search(line):
            continue
        if comments_only and not COMMENT_LINE.match(line):
            continue
        row = "%d:%s" % (number, line)
        hit = any(p.search(row) for p in CASE_INSENSITIVE_MARKERS) or any(p.search(row) for p in CASE_SENSITIVE_MARKERS)
        if hit and not NOT_A_MARKER.search(row):
            rows.append((number, line))
    return rows


def block_inside_repo(file_path, reason):
    """Exit 2 with the reason, except for a file outside a git work tree: a scratch probe there is free to name plan
    paths and other workflow strings."""
    if not script_utils.inside_git_work_tree(file_path, GIT_PROBE_TIMEOUT_SECONDS):
        return 0
    emit_stderr(reason)
    return 2


def check(raw):
    payload = json.loads(raw)
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict):
        return 0

    file_path = first_present(tool_input, "file_path")
    if not file_path or not os.path.isfile(file_path):
        return 0
    if not CODE_FILE.search(file_path):
        return 0
    if "/.claude/" in "/" + surface_of(file_path):
        return 0

    new_text = first_present(tool_input, "content", "new_string")
    if not new_text:
        return 0

    file_lines = read_text(file_path).split("\n")
    new_lines = new_text.split("\n")
    name = os.path.basename(file_path)

    added_lines = set(new_lines)
    data_only = file_path.endswith(".json")
    leaks = ["  %d:%s\n" % (number, line) for number, line in marker_rows(file_lines, data_only)
             if line in added_lines]
    if leaks:
        return block_inside_repo(file_path, "comment-bloat-gate: private-workflow marker in an added line (%s). Zero "
                                 "exceptions — keep the reason, drop the pointer (_shared/code-vocabulary.md):\n"
                                 % name + "".join(leaks))

    added_comments = [line for line in new_lines if COMMENT_LINE.match(line)]
    if not any(not DELIMITER_LINE.match(line) for line in added_comments):
        return 0
    total = sum(1 for line in file_lines if NONBLANK.search(line))
    if total < MIN_LINES_FOR_DENSITY:
        return 0
    comments = sum(1 for line in file_lines if COMMENT_LINE.match(line) and not DELIMITER_LINE.match(line))
    percent = comments * 100 // total
    if percent > DENSITY_CAP_PERCENT:
        return block_inside_repo(file_path, "comment-bloat-gate: %s is %d%% comments (%d/%d non-blank lines), cap "
                                 "~20%%. Delete the comments this edit added, or rename/split so they are "
                                 "unnecessary. Never add code to lower the ratio.\n"
                                 % (name, percent, comments, total))
    return 0


def main():
    try:
        code = check(hook_input.read_stdin_text())
    except Exception:
        code = 0
    return code


if __name__ == "__main__":
    hook_input.run_gate(main)
