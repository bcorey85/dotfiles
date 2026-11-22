"""The mechanical sweep of /refactor branch-prep: added lines that hold a leftover marker or commented-out code.

A marker inside a single-line string literal, or inside a multi-line string held as data, is no hit; comments and
docstrings are still swept. In a .py or .pyi file with a command-line entry point, `print(` is the report
and is no hit either; a TODO-class marker still is.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts" / "lib"))
import source_text

NOTE_MARKERS = r"\b(?:TODO|FIXME|XXX|HACK)s?\b"
DEBUG_MARKERS = r"\bconsole\.(?:log|debug)\b|\bdebugger\b|\bbinding\.pry\b"
PRINT_CALLS = r"(?<![\w.])p?print\(|\bpprint\.pprint\("
NON_PRINT_MARKERS = re.compile(f"{NOTE_MARKERS}|{DEBUG_MARKERS}")
SWEEP_MARKERS = re.compile(f"{NOTE_MARKERS}|{DEBUG_MARKERS}|{PRINT_CALLS}")
COMMENTED_CODE = r"(//|#)\s*(if |for |while |return |const |let |var |def |function |import )"
SWEEP_COMMENTED_CODE = re.compile(rf"^\s*{COMMENTED_CODE}")
SWEEP_COMMENTED_CODE_ANYWHERE = re.compile(COMMENTED_CODE)
CLI_ENTRY_POINT = re.compile(
    r"""^if\s+__name__\s*==\s*["']__main__["']|^(?:async\s+)?def main\(|^(?:import argparse|from argparse import)\b""",
    re.MULTILINE)
PYTHON_SUFFIXES = (".py", ".pyi")


class PostImageMismatchError(Exception):
    """The file read for the sweep is not the text the diff added lines to."""


def has_cli_entry_point(path, code_text):
    """Whether the file is a .py or .pyi file with a command-line entry point: a column-0 line that starts
    `if __name__ == "__main__"`, `def main(`, `async def main(`, `import argparse` or `from argparse import`."""
    if not path.endswith(PYTHON_SUFFIXES):
        return False
    return CLI_ENTRY_POINT.search(code_text) is not None


def has_sweep_candidate(added_lines):
    """Whether any raw added (line, text) pair could be a hit, so the file's post-image is worth reading. The
    commented-out-code search is unanchored: a line that closes a data string is judged on its tail alone."""
    return any(
        SWEEP_MARKERS.search(text) or SWEEP_COMMENTED_CODE_ANYWHERE.search(text) for _line, text in added_lines
    )


def check_post_image(path, added_lines, post_image_lines):
    """Raise PostImageMismatchError when the post-image is not the text the diff added lines to."""
    for line, text in added_lines:
        if line > len(post_image_lines):
            raise PostImageMismatchError(f"{path}:{line} is past the end of the file read for the sweep")
        if post_image_lines[line - 1].rstrip("\r") != text.rstrip("\r"):
            raise PostImageMismatchError(f"{path}:{line} differs between the diff and the file read for the sweep")


def marker_search_text(code_line, style, masks_strings):
    """The text of a line the markers are searched in. String text is masked only in a source file of a known
    comment style, and only when source_text.masks_string_text says so."""
    if style is None or not masks_strings:
        return code_line
    return source_text.without_string_text_keeping_comment(code_line, style)


def sweep_added_lines(path, added_lines, post_image_lines):
    """The sweep matches, as (path, line, kind, text), among one file's added (line, text) pairs, judged against the
    file's post-image lines. With post_image_lines None (the path is a work-tree symlink), each added line stands
    alone."""
    if post_image_lines is None:
        code_by_line = dict(added_lines)
    else:
        check_post_image(path, added_lines, post_image_lines)
        code_by_line = source_text.code_text_by_line(path, post_image_lines)
    code_text = "\n".join(code_by_line.values())
    quiet_prints = has_cli_entry_point(path, code_text)
    marker = NON_PRINT_MARKERS if quiet_prints else SWEEP_MARKERS
    style = source_text.comment_style_of(path)
    comment_numbers = set()
    if style is not None and post_image_lines is not None:
        comment_numbers = set(source_text.comment_line_numbers(post_image_lines, style))
    elif style is not None:
        comment_numbers = {
            line for line, text in added_lines if 1 in source_text.comment_line_numbers([text], style)
        }
    matches = []
    for line, text in added_lines:
        if line not in code_by_line:
            continue
        code_line = code_by_line[line]
        raw_line = text if post_image_lines is None else post_image_lines[line - 1]
        masks_strings = source_text.masks_string_text(raw_line, code_line, line in comment_numbers)
        search_text = marker_search_text(code_line, style, masks_strings)
        if marker.search(search_text):
            matches.append((path, line, "marker", text.strip()))
        if SWEEP_COMMENTED_CODE.search(code_line):
            matches.append((path, line, "commented-out code", text.strip()))
    return matches


def sweep_matches(diff_files, read_post_image):
    """Sweep matches over the added lines of parsed diff files. read_post_image(path) returns the file's lines, or
    None when the path is a work-tree symlink."""
    matches = []
    for diff_file in diff_files:
        added = [pair for hunk in diff_file.hunks for pair in hunk.added]
        if not has_sweep_candidate(added):
            continue
        post_image_lines = read_post_image(diff_file.path)
        matches += sweep_added_lines(diff_file.path, added, post_image_lines)
    return matches


def untracked_matches(untracked):
    """The sweep matches in the untracked files, read as if every line were added."""
    matches = []
    for entry in untracked:
        post_image_lines = [text for _number, text in entry.added_lines]
        matches += sweep_added_lines(entry.path, entry.added_lines, post_image_lines)
    return matches
