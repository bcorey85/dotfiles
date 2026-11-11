"""source_text.py: plain-text readers for source files and their diffs, with no rule of any one script.

Toolkit scripts import it after putting scripts/lib on sys.path."""
import difflib
import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import NamedTuple

HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@ ?(.*)$")
NO_FILE = "/dev/null"
NO_NEWLINE_MARKER = "\\ No newline at end of file"
C_ESCAPES = {"a": 7, "b": 8, "f": 12, "n": 10, "r": 13, "t": 9, "v": 11, '"': 34, "\\": 92}
C_ESCAPE = re.compile(r'\\([0-7]{3}|[abfnrtv"\\])')
LITERAL = re.compile(r"""(?P<quote>["'`])(?P<text>(?:\\.|(?!(?P=quote)).)*)(?P=quote)"""
                     r"""|(?<![\w$.])(?P<number>\d+(?:\.\d+)?)""")
STRING_PATTERN = r"""(?P<quote>["'`])(?:\\.|(?!(?P=quote)).)*(?P=quote)"""
STRING_LITERAL = re.compile(STRING_PATTERN)
STRING_OR_BLOCK_COMMENT_START = re.compile(rf"(?P<string>{STRING_PATTERN})|/\*")
TRIPLE_QUOTE_SCAN = re.compile(r"""\"\"\"|'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#""")
TRIPLE_QUOTE_START = re.compile(r"""[rRuUbBfF]{0,2}(\"\"\"|''')""")
STRING_OPENING_ENDINGS = ("(", "[", "{", ",", "=")
OPEN_BACKTICK_SCAN = re.compile(rf"(?P<string>{STRING_PATTERN})|//|/\*|`")
STRING_OR_COMMENT_START = re.compile(rf"(?P<string>{STRING_PATTERN})|#|//")
STRING_OR_HASH_START = re.compile(rf"(?P<string>{STRING_PATTERN})|#")
STRING_OR_SLASH_START = re.compile(rf"(?P<string>{STRING_PATTERN})|//")
COMMENT_START_OF_STYLE = {"hash": STRING_OR_HASH_START, "hash_triple": STRING_OR_HASH_START,
                          "slash": STRING_OR_SLASH_START}
COMMENT_STYLES = ("slash", "hash", "hash_triple")
COMMENT_STYLE_OF_SUFFIX = {
    ".py": "hash_triple", ".rb": "hash",
    ".sh": "hash", ".bash": "hash", ".zsh": "hash", ".yml": "hash", ".yaml": "hash",
    **dict.fromkeys((
        ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs", ".java", ".kt", ".swift", ".php", ".c", ".h",
        ".cc", ".cpp", ".hpp"), "slash"),
}


class FormattingOnlyLines(NamedTuple):
    old: Counter
    new: Counter


def stripped_lines(text):
    """The nonblank lines of the text, each with surrounding whitespace dropped."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def normalized_block(lines):
    """A block of lines reduced to what a formatter leaves alone: no whitespace, one quote style, and no comma
    right before a closing bracket."""
    squeezed = "".join("".join(lines).split()).replace("'", '"')
    return re.sub(r",(?=[)\]}])", "", squeezed)


def formatting_only_lines(old_text, new_text):
    """The lines of old_text and of new_text, as Counters, that sit in a replaced hunk whose two sides differ only
    in formatting."""
    old_lines = stripped_lines(old_text)
    new_lines = stripped_lines(new_text)
    matcher = difflib.SequenceMatcher(None, old_lines, new_lines, autojunk=False)
    reformatted = FormattingOnlyLines(Counter(), Counter())
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        if tag != "replace":
            continue
        old_block = old_lines[old_start:old_end]
        new_block = new_lines[new_start:new_end]
        if normalized_block(old_block) == normalized_block(new_block):
            reformatted.old.update(old_block)
            reformatted.new.update(new_block)
    return reformatted


def indent_of(line):
    """The number of leading whitespace characters of the line."""
    return len(line) - len(line.lstrip())


def comment_style_of(path):
    """The comment style (one of COMMENT_STYLES) of a source file by its suffix, or None for an unknown suffix."""
    return COMMENT_STYLE_OF_SUFFIX.get(os.path.splitext(path)[1])


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
        byte = int(code, 8) if code[0] in "01234567" else C_ESCAPES[code]
        decoded.append(byte)
        position = escape.end()
    return decoded.decode("utf-8", errors="replace")


def _header_path(line, marker):
    """The path of a `--- path` or `+++ path` line of a diff made without prefixes, or None for /dev/null. A name that
    git C-quotes is decoded."""
    path = line[len(marker):].rstrip("\t")
    if len(path) >= 2 and path.startswith('"') and path.endswith('"'):
        path = unquote_c_path(path)
    return None if path == NO_FILE else path


@dataclass
class _HunkPosition:
    """Where a hunk body read stands: the next line numbers and the lines each side still owes."""
    old_number: int
    new_number: int
    old_count: int
    new_count: int

    def has_lines_left(self):
        return self.old_count > 0 or self.new_count > 0


def _take_body_line(hunk, position, line):
    """Apply one hunk body line to hunk and position; return False when the line is not a body line."""
    if line.startswith("-"):
        hunk.removed.append((position.old_number, line[1:]))
        position.old_number += 1
        position.old_count -= 1
        return True
    if line.startswith("+"):
        hunk.added.append((position.new_number, line[1:]))
        position.new_number += 1
        position.new_count -= 1
        return True
    if line.startswith(" "):
        position.old_number += 1
        position.new_number += 1
        position.old_count -= 1
        position.new_count -= 1
        return True
    return False


def _read_hunk_body(lines, start, hunk, position):
    """Fill hunk from the lines at `start` and return the index after its last line. A hunk body is exactly as long
    as its header says, so a removed line that reads `-- x` is not taken for a file header. Raises ValueError when the
    input ends inside the body or a body line is not `-`, `+`, ` ` or git's no-newline marker."""
    index = start
    while position.has_lines_left():
        if index >= len(lines):
            raise ValueError(f"diff line {index + 1}: the input ends inside a hunk body; expected a line that starts "
                             f"with '-', '+' or ' '")

        line = lines[index]
        index += 1
        if line == NO_NEWLINE_MARKER:
            continue
        if not _take_body_line(hunk, position, line):
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
            continue
        if line.startswith("+++ "):
            new_path = _header_path(line, "+++ ")
            current = FileDiff(new_path or old_path)
            files.append(current)
            continue

        header = HUNK_HEADER.match(line)
        if header is None or current is None:
            continue

        index = _read_hunk(lines, index, header, current)
    return files


def _count_of(text):
    """The line count of a hunk header side; git leaves it out when it is 1."""
    if text is None:
        return 1
    return int(text)


def _read_hunk(lines, start, header, current_file):
    """Add the hunk that `header` opens to current_file and return the index after its body."""
    old_start, old_count, new_start, new_count, context = header.groups()
    hunk = Hunk(context)
    current_file.hunks.append(hunk)
    position = _HunkPosition(int(old_start), int(new_start), _count_of(old_count), _count_of(new_count))
    return _read_hunk_body(lines, start, hunk, position)


def _slash_comment_numbers(lines):
    numbers = set()
    in_block = False
    for number, line in enumerate(lines, 1):
        stripped = line.strip()
        if in_block:
            numbers.add(number)
            in_block = "*/" not in stripped
            continue
        if stripped.startswith("//"):
            numbers.add(number)
            continue
        if stripped.startswith("/*"):
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
            open_quote = None if line.count(open_quote) % 2 == 1 else open_quote
            continue
        if stripped.startswith("#"):
            numbers.add(number)
            continue
        if not triple_quotes:
            continue

        opened = _opened_triple_quote(line, stripped)
        open_quote = opened.quote
        if opened.is_text_line:
            numbers.add(number)
    return numbers


class _OpenedTripleQuote(NamedTuple):
    quote: object
    is_text_line: bool
    index: int


def _opened_triple_quote(line, stripped):
    """An _OpenedTripleQuote: the triple quote that the line leaves open or None, whether the line is docstring text,
    the index of that opening quote in the line or -1. A line that starts with a triple quote, with an optional string
    prefix such as `r`, is docstring text; a string assigned on the line opens a region but is not text. A triple
    quote inside a single-quoted literal or after a `#` does not count."""
    is_text_line = TRIPLE_QUOTE_START.match(stripped) is not None
    position = 0
    while True:
        found = TRIPLE_QUOTE_SCAN.search(line, position)
        if found is None or found.group() == "#":
            return _OpenedTripleQuote(None, is_text_line, -1)

        quote = found.group()
        if quote not in ('"""', "'''"):
            position = found.end()
            continue

        closing = line.find(quote, found.end())
        if closing < 0:
            return _OpenedTripleQuote(quote, is_text_line, found.start())

        position = closing + len(quote)


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


def without_string_text(line):
    """The line with the text of every single-line string literal (single, double or backtick quotes) removed, so a
    search of the result sees code but not data held in a string. A trailing comment that holds a quote is mangled;
    split it off first with split_trailing_comment."""
    return STRING_LITERAL.sub(lambda found: found.group("quote") * 2, line)


def split_trailing_comment(line, style=None):
    """(code, comment): the line cut at the first comment marker that is not inside a single-line string literal. The
    marker is `#` for style `hash` or `hash_triple`, `//` for `slash`, and either for no style. The comment keeps its
    marker; it is empty when the line has none."""
    start = COMMENT_START_OF_STYLE.get(style, STRING_OR_COMMENT_START)
    for found in start.finditer(line):
        if found.group("string") is None:
            return line[:found.start()], line[found.start():]
    return line, ""


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


def _closing_backtick(line):
    """The index of the first backtick of a line that is not escaped by a backslash, or -1."""
    position = 0
    while position < len(line):
        if line[position] == "\\":
            position += 2
            continue
        if line[position] == "`":
            return position
        position += 1
    return -1


def _open_backtick_index(line):
    """The index of the backtick that the line leaves open (outside any quoted string and any trailing comment), or
    -1."""
    for found in OPEN_BACKTICK_SCAN.finditer(line):
        if found.group("string") is not None:
            continue
        return found.start() if found.group() == "`" else -1
    return -1


class StringDataRegions(NamedTuple):
    numbers: set
    closing_tails: dict
    openings: dict


def string_data_regions(lines, style):
    """StringDataRegions(numbers, closing_tails, openings) of the multi-line strings held as data, from one scan.
    numbers is the 1-based numbers of the lines
    that continue one: the lines after the line that opens a triple-quoted string assigned or passed on the line
    (`x = \"\"\"`, `f(\"\"\"`; style `hash_triple`) or a backtick template literal (style `slash`), up to but not
    including the line that closes it. A triple quote that starts its own line is data when the previous code line
    ends with `(`, `[`, `{`, `,` or `=`. Any other line that starts with a triple quote, with an optional string
    prefix, is a docstring, which is prose and is not listed. closing_tails maps the number of each line that closes
    one to the text after its closing quote, which is code or a comment; the tail stops at a backtick that opens
    another template on the same line. openings maps the number of each line that opens one to the text before the
    opening quote: from the quote on the line is data, only that head is code. For style slash, a line that also
    closes a string is in closing_tails instead; for style hash_triple, such a line counts as inside the string and is
    listed in numbers. Other styles give no lines."""
    if style == "hash_triple":
        return _triple_quote_regions(lines)
    if style == "slash":
        return _template_literal_regions(lines)
    return StringDataRegions(set(), {}, {})


class _TripleQuoteScan:
    """The state of a line-by-line scan for triple-quoted strings held as data."""

    def __init__(self):
        self.regions = StringDataRegions(set(), {}, {})
        self.open_quote = None
        self.is_data = False
        self.previous = ""

    def read_line(self, number, line):
        stripped = line.strip()
        if self.open_quote:
            self._read_inside_string(number, line)
        elif not stripped.startswith("#"):
            self._read_outside_string(number, line, stripped)
        if stripped and not stripped.startswith("#"):
            self.previous = stripped

    def _read_inside_string(self, number, line):
        if line.count(self.open_quote) % 2 == 0:
            if self.is_data:
                self.regions.numbers.add(number)
            return

        if self.is_data:
            tail_start = line.index(self.open_quote) + len(self.open_quote)
            self.regions.closing_tails[number] = line[tail_start:]
        self.open_quote = None

    def _read_outside_string(self, number, line, stripped):
        opened = _opened_triple_quote(line, stripped)
        self.open_quote = opened.quote
        continues_assignment = self.previous.endswith(STRING_OPENING_ENDINGS)
        self.is_data = opened.quote is not None and (not opened.is_text_line or continues_assignment)
        if self.is_data:
            self.regions.openings[number] = line[:opened.index]


def _triple_quote_regions(lines):
    scan = _TripleQuoteScan()
    for number, line in enumerate(lines, 1):
        scan.read_line(number, line)
    return scan.regions


def _continue_template(regions, number, line):
    """Record a line inside a backtick template; return whether the template is still open after it."""
    closing = _closing_backtick(line)
    if closing < 0:
        regions.numbers.add(number)
        return True

    tail = line[closing + 1:]
    open_index = _open_backtick_index(tail)
    if open_index < 0:
        regions.closing_tails[number] = tail
        return False

    regions.closing_tails[number] = tail[:open_index]
    return True


def _start_template(regions, number, line):
    """Record a line that may open a backtick template; return whether one is open after it."""
    open_index = _open_backtick_index(line)
    if open_index < 0:
        return False

    regions.openings[number] = line[:open_index]
    return True


def _template_literal_regions(lines):
    regions = StringDataRegions(set(), {}, {})
    comment_numbers = _slash_comment_numbers(lines)
    in_template = False
    for number, line in enumerate(lines, 1):
        if in_template:
            in_template = _continue_template(regions, number, line)
            continue
        if number in comment_numbers:
            continue
        in_template = _start_template(regions, number, line)
    return regions
