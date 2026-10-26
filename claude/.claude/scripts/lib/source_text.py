"""source_text.py: plain-text readers for source files and their diffs, with no rule of any one script.

Toolkit scripts import it after putting scripts/lib on sys.path."""
import re
from dataclasses import dataclass, field

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")
NO_FILE = "/dev/null"
NO_NEWLINE_MARKER = "\\ No newline at end of file"
C_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11, '"': 34, "\\": 92}
C_ESCAPE = re.compile(r'\\([0-7]{3}|[abfnrtv"\\])')
LITERAL = re.compile(r"""(?P<quote>["'`])(?P<text>(?:\\.|(?!(?P=quote)).)*)(?P=quote)"""
                     r"""|(?<![\w$.])(?P<number>\d+(?:\.\d+)?)""")
COMMENT_STYLES = ("slash", "hash", "hash_triple")


@dataclass
class Hunk:
    context: str
    removed: list = field(default_factory=list)
    added: list = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    hunks: list = field(default_factory=list)


def unquote_c_path(quoted):
    """Decode a git C-quoted name (`"..."`): the escapes git writes and octal bytes, read as UTF-8. Raises ValueError
    on an escape git does not write."""
    inner = quoted[1:-1]
    decoded = bytearray()
    position = 0
    for escape in [*C_ESCAPE.finditer(inner), None]:
        end = escape.start() if escape else len(inner)
        plain = inner[position:end]
        if "\\" in plain:
            raise ValueError(f"cannot decode quoted path {quoted!r}: unknown escape")

        decoded += plain.encode("utf-8", errors="surrogateescape")
        if escape is None:
            break

        code = escape.group(1)
        decoded.append(int(code, 8) if code[0] in "01234567" else C_ESCAPES[code])
        position = escape.end()
    return decoded.decode("utf-8", errors="replace")


def _header_path(line, marker):
    """The path of a `--- path` or `+++ path` line of a diff made without prefixes, or None for /dev/null. A name that
    git C-quotes is decoded."""
    path = line[len(marker):].rstrip("\t")
    if len(path) >= 2 and path.startswith('"') and path.endswith('"'):
        path = unquote_c_path(path)
    return None if path == NO_FILE else path


def _read_hunk_body(lines, start, hunk, old_number, new_number, old_count, new_count):
    """Fill hunk from the lines at `start` and return the index after its last line. A hunk body is exactly as long
    as its header says, so a removed line that reads `-- x` is not taken for a file header. Raises ValueError when the
    input ends inside the body or a body line is not `-`, `+`, ` ` or git's no-newline marker."""
    index = start
    while old_count > 0 or new_count > 0:
        if index >= len(lines):
            raise ValueError(f"diff line {index + 1}: the input ends inside a hunk body; expected a line that starts "
                             f"with '-', '+' or ' '")

        line = lines[index]
        index += 1
        if line == NO_NEWLINE_MARKER:
            continue
        if line.startswith("-"):
            hunk.removed.append((old_number, line[1:]))
            old_number += 1
            old_count -= 1
        elif line.startswith("+"):
            hunk.added.append((new_number, line[1:]))
            new_number += 1
            new_count -= 1
        elif line.startswith(" "):
            old_number += 1
            new_number += 1
            old_count -= 1
            new_count -= 1
        else:
            raise ValueError(f"diff line {index}: expected a hunk body line that starts with '-', '+' or ' ', or "
                             f"{NO_NEWLINE_MARKER!r}; got {line!r}")
    return index


def parse_unified_diff(text):
    """The files of `git diff --no-prefix -U0` output as FileDiff objects, in order. Each Hunk holds the text after
    the second `@@` (git's name of the enclosing function), the removed lines as (old line number, text) and the
    added lines as (new line number, text). A deleted file is named by its old path. A binary file or a mode change
    has no hunks and is left out."""
    lines = text.split("\n")
    files = []
    old_path = None
    current = None
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if line.startswith("--- "):
            old_path = _header_path(line, "--- ")
        elif line.startswith("+++ "):
            new_path = _header_path(line, "+++ ")
            current = FileDiff(new_path or old_path)
            files.append(current)
        else:
            header = HUNK_HEADER.match(line)
            if header is None or current is None:
                continue

            old_start, old_count, new_start, new_count, context = header.groups()
            hunk = Hunk(context)
            current.hunks.append(hunk)
            index = _read_hunk_body(lines, index, hunk, int(old_start), int(new_start),
                                    1 if old_count is None else int(old_count),
                                    1 if new_count is None else int(new_count))
    return files


def _slash_comment_numbers(lines):
    numbers = set()
    in_block = False
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if in_block:
            numbers.add(number)
            in_block = "*/" not in stripped
        elif stripped.startswith("//"):
            numbers.add(number)
        elif stripped.startswith("/*"):
            numbers.add(number)
            in_block = "*/" not in stripped[2:]
    return numbers


def _hash_comment_numbers(lines, triple_quotes):
    numbers = set()
    open_quote = None
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if open_quote:
            numbers.add(number)
            if line.count(open_quote) % 2 == 1:
                open_quote = None
        elif stripped.startswith("#"):
            numbers.add(number)
        elif triple_quotes:
            open_quote, is_text_line = _opened_triple_quote(line, stripped)
            if is_text_line:
                numbers.add(number)
    return numbers


def _opened_triple_quote(line, stripped):
    """(the triple quote that the line leaves open or None, whether the line is docstring text). A line that starts
    with a triple quote is docstring text; a string assigned on the line opens a region but is not text."""
    for quote in ('"""', "'''"):
        if quote not in line:
            continue
        return (quote if line.count(quote) % 2 == 1 else None), stripped.startswith(quote)
    return None, False


def literals_of(line):
    """The number and string literals of one line of code, in order. A string literal (single, double or backtick
    quotes) is its text without the quotes; a number is a run of digits with an optional fraction, not part of a
    name."""
    return [found.group("text") if found.group("text") is not None else found.group("number")
            for found in LITERAL.finditer(line)]


def mask_literals(line):
    """The line with every number and string literal replaced by `#`, so two lines that differ only in their literal
    values are equal."""
    return LITERAL.sub("#", line)


def comment_line_numbers(lines, style):
    """The 1-based numbers of the lines of a source file that are comment text. `slash`: a line that starts with `//`,
    and every line of a `/* ... */` block. `hash`: a line that starts with `#`. `hash_triple`: the same, plus every
    line after the opening line of any triple-quoted string (docstring or assigned string alike, up to and including
    the line that closes it), plus the opening line itself when it starts with the quotes. A comment that follows code
    on the same line is not counted."""
    if style == "slash":
        return _slash_comment_numbers(lines)
    if style in ("hash", "hash_triple"):
        return _hash_comment_numbers(lines, style == "hash_triple")
    raise ValueError(f"unknown comment style {style!r}; expected one of {COMMENT_STYLES}")
