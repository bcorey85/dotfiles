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

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
import source_text
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

# A plan path or provenance in a shipped string still leaks, so these search the whole line, strings included.
RAW_LINE_MARKERS = [re.compile(pattern, re.I) for pattern in (
    r"docs/plans/",
    r"per the (architect|plan|spec|ledger)",
    r"written by the (coder|architect|poller|assistant|agent)",
)]
CASE_INSENSITIVE_MARKERS = [re.compile(pattern, re.I) for pattern in (
    r"\bphases?" + SPACE + r"*[0-9]",
    r"\b(PR|issue)" + SPACE + r"*#[0-9]+",
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

# The first argument of a test-name call is prose, so a marker in it counts. The lookbehind keeps `pattern.test(...)`
# and `obj.it(...)` out; `t.Run`, `self.subTest` and `pytest.param(id=...)` name a test through a method or keyword.
TEST_NAME_CALL = re.compile(
    r"""(?<![.\w$])(?:it|test|describe|context|suite)(?:\.\w+)*(?:\([^()]*\)|`[^`]*`)?\(\s*(?=["'`])"""
    r"""|\b(?:Run|subTest)\(\s*(?=["'`])"""
    r"""|(?<![\w$])ids?\s*=\s*(?:\[|(?=["'`]))"""
    r"""|\bsubTest\(\s*msg\s*=\s*(?=["'`])""")
TEST_ID_LIST_TAIL = re.compile(r"[^\]]*\]")

DENSITY_CAP_PERCENT = 22
MIN_LINES_FOR_DENSITY = 30


def first_present(tool_input, *keys):
    """jq `.a // .b // empty`: null and false fall through to the next key."""
    for key in keys:
        value = tool_input.get(key)
        if value is not None and value is not False:
            return hook_input.raw_text(value).rstrip("\n")
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


def searchable_text(line, style=None):
    """The line with string text removed from the code part, except the name given to each test-name call, plus the raw
    trailing comment. style is the file's comment style (see source_text.comment_style_of)."""
    code, comment = source_text.split_trailing_comment(line, style)
    kept = []
    position = 0
    for call in TEST_NAME_CALL.finditer(code):
        if call.start() < position:
            continue
        opens_list = call.group().endswith("[")
        name = (TEST_ID_LIST_TAIL if opens_list else source_text.STRING_LITERAL).match(code, call.end())
        name_end = name.end() if name else call.end()
        kept.append(source_text.without_string_text(code[position:call.start()]) + code[call.start():name_end])
        position = name_end
    kept.append(source_text.without_string_text(code[position:]))
    return "".join(kept) + comment


def comment_numbers_of(file_lines, style):
    """Numbers of the lines that are comment text, including docstring and block-comment lines COMMENT_LINE misses.
    style is the file's comment style; None gives no lines."""
    if style is None:
        return set()
    return set(source_text.comment_line_numbers(file_lines, style))


def has_marker(row, markers):
    return any(p.search(row) for p in markers) and not NOT_A_MARKER.search(row)


def marker_hit(raw_row, searched_row):
    """Whether a row carries a marker: the raw-line markers search raw_row, the others searched_row, the row with
    string text removed."""
    return (has_marker(raw_row, RAW_LINE_MARKERS)
            or has_marker(searched_row, CASE_INSENSITIVE_MARKERS + CASE_SENSITIVE_MARKERS))


def marker_rows(file_lines, comments_only=False, file_path=""):
    """Numbered non-blank lines carrying a workflow marker, ordered by line number.

    comments_only limits the scan to comment lines, for formats whose values are data, not prose. Lines inside a
    multi-line string held as data are not searched; on the line that opens one, only the text before the opening
    quote is, and on the line that closes one, only the text after the closing quote; on a template-literal line
    that closes one and opens another, only the text between them."""
    style = source_text.comment_style_of(file_path)
    comment_numbers = comment_numbers_of(file_lines, style)
    string_data_numbers, closing_tails, openings = source_text.string_data_regions(file_lines, style)
    rows = []
    for number, line in enumerate(file_lines, 1):
        if not NONBLANK.search(line) or number in string_data_numbers:
            continue
        is_comment = COMMENT_LINE.match(line) or number in comment_numbers
        if comments_only and not is_comment:
            continue
        if number in closing_tails:
            raw = closing_tails[number]
            searched = searchable_text(raw, style)
        elif number in openings:
            raw = openings[number]
            searched = searchable_text(raw, style)
        else:
            raw = line
            searched = line if is_comment else searchable_text(line, style)

        if marker_hit(f"{number}:{raw}", f"{number}:{searched}"):
            rows.append((number, line))
    return rows


def prose_comment_count(lines):
    return sum(1 for line in lines if COMMENT_LINE.match(line) and not DELIMITER_LINE.match(line))


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

    file_text = hook_input.read_file_text(file_path) or ""
    file_lines = file_text.split("\n")
    new_lines = new_text.split("\n")
    name = os.path.basename(file_path)

    added_lines = set(new_lines)
    data_only = file_path.endswith(".json")
    leaks = [f"  {number}:{line}\n" for number, line in marker_rows(file_lines, data_only, file_path)
             if line in added_lines]
    if leaks:
        return block_inside_repo(
            file_path,
            f"comment-bloat-gate: private-workflow marker in an added line ({name}). Zero "
            "exceptions — keep the reason, drop the pointer (_shared/code-vocabulary.md):\n" + "".join(leaks),
        )

    old_lines = first_present(tool_input, "old_string").split("\n")
    net_new_comments = prose_comment_count(new_lines) - prose_comment_count(old_lines)
    if net_new_comments <= 0:
        return 0
    total = sum(1 for line in file_lines if NONBLANK.search(line))
    if total < MIN_LINES_FOR_DENSITY:
        return 0
    comments = prose_comment_count(file_lines)
    percent = comments * 100 // total
    if percent > DENSITY_CAP_PERCENT:
        return block_inside_repo(
            file_path,
            f"comment-bloat-gate: {name} is {percent}% comments ({comments}/{total} non-blank lines), cap "
            f"~20%. Delete the comments this edit added, or rename/split so they are "
            f"unnecessary; a comment the task requires stays, named in the hand-back. Never add code to lower "
            f"the ratio.\n",
        )
    return 0


def main():
    try:
        code = check(hook_input.read_stdin_text())
    except Exception:
        code = 0
    return code


if __name__ == "__main__":
    hook_input.run_gate(main)
