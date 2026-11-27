#!/usr/bin/env python3
"""PostToolUse hook on Write|Edit: block workflow-marker leaks and long comment blocks that are not a kept kind.

Enforces the workflow-marker rule of _shared/code-vocabulary.md deterministically. Reads the edited file from
disk. A marker counts when its line matches a line of the new text exactly. A comment line counts only when its
stripped text is also absent from the old text (a Write's file before the write, else HEAD), so a re-indented comment
is not new. The comment check holds each added comment line to the kept kinds: a license header, a lint or format
suppression or tool directive, a comment block on an exported or public symbol (a Go package doc and a leading run of
Rust `//!` lines included), or a line with a URL. A run of consecutive non-kept comment lines
(new or old; a blank, delimiter, suppression, directive or URL line inside a comment block keeps the run going
without counting; a license header, a public-symbol doc line or a gap ends it) passes
while at most MAX_FREE_BLOCK_LINES of them are new; a run with more is blocked, only its new lines listed, and the
message sends architecture prose to the repo's architecture docs. Heredoc bodies in shell files are data, not comments.
Files under a docs/ folder skip the comment check but not the marker check. On an Edit, only comment lines inside the
span new_string occupies in the file are charged (the whole file when new_string is not found in it). Only whole
comment lines count, never a trailing comment.
Exit 2 with the reason on stderr blocks; every other path exits 0. Gate policy: fail-open, so an error exits 0
after main reports it on stderr.
"""
import json
import os
import re
import sys
from typing import NamedTuple

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
import shell_statements
import source_paths
import source_text
from hook_input import emit_stderr

GIT_PROBE_TIMEOUT_SECONDS = 2
MAX_FREE_BLOCK_LINES = 2

SPACE = r"\s"
NONBLANK = re.compile(r"\S")
CODE_FILE = re.compile(
    r"\.(ts|tsx|js|jsx|mjs|cjs|py|go|rs|rb|java|kt|swift|php|c|h|cc|cpp|hpp|lua|qml|sh|bash|zsh|yml|yaml|json|sql)$",
    re.M)

# Only for a suffix with no comment style (json): the leaders that file could carry.
COMMENT_LINE = re.compile(r"^" + SPACE + r"*(//|#|/\*)")
# A bare docstring/JSDoc delimiter is structure, not prose.
DELIMITER_LINE = re.compile(r"^" + SPACE + r"*(\"\"\"|'''|/\*\*?|\*/)" + SPACE + r"*$")

# A plan path or provenance in a shipped string still leaks, so outside test files these search the whole line,
# strings included.
RAW_LINE_MARKERS = [re.compile(pattern, re.I) for pattern in (
    r"docs/plans/",
    r"per the (architect|plan|spec|ledger)",
    r"written by the (coder|architect|poller|assistant|agent)",
)]
CASE_INSENSITIVE_MARKERS = [re.compile(pattern, re.I) for pattern in (
    r"\bphases?" + SPACE + r"*[0-9]",
    r"\b(PR|issue)" + SPACE + r"*#[0-9]+",
    r"decision ledger|acceptance contract",
    r"user ruling",
    r"end-of-branch",
)]
# Words that are the domain of the agent-evals repo and step names in shell code: they count only in comments, and
# never in an agent-evals checkout.
EVAL_DOMAIN_MARKERS = [re.compile(pattern, re.I) for pattern in (
    r"acceptance criteri",
    r"plan[ -]?impact",
)]
AGENT_EVALS_CHECKOUT = re.compile(r"(^|/)agent-evals(-[^/]+)?/")
SHELL_FILE = re.compile(r"\.(sh|bash|zsh)$")
CASE_SENSITIVE_MARKERS = [re.compile(pattern) for pattern in (
    r"\(D[0-9]+[):]",
    r"\bD[0-9]+:",
    r"\bPD[0-9]+\b",
    r"(?<![#\w])AC[0-9]+[a-z]?\b",
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

LICENSE_WORDS = re.compile(r"SPDX-License-Identifier|Copyright|\bLicen[sc]e\b", re.I)
SUPPRESSION = re.compile(
    r"eslint-(?:disable|enable)|prettier-ignore|noqa|type:\s*ignore|pylint:\s*disable|ts-ignore|ts-expect-error"
    r"|ts-nocheck|nolint|rubocop:\s*disable|shellcheck\s+disable|biome-ignore"
    r"|istanbul\s+ignore|c8\s+ignore|fmt:\s*(?:off|on)\b|yamllint\s+disable", re.I)
# A tool reads these comments, so deleting one changes what the tool does.
DIRECTIVE = re.compile(
    r"^\s*//go:\w+|^\s*// \+build|^\s*///\s*<reference|@ts-check|clang-format\s+(?:off|on)"
    r"|swiftlint:(?:disable|enable)|mypy:|pyright:|pragma:\s*no\s*cover|-\*-\s*coding[:=]"
    r"|^\s*/\*\*\s*@(?:type|typedef)\b.*\*/\s*$", re.I)
URL = re.compile(r"https?://")
SHEBANG = "#!"
DECORATOR_LINE = re.compile(r"^\s*(?:@[\w.]+(?:\([^)]*\))?|#\[.*\])\s*$")
PYTHON_HEADER = re.compile(r"^\s*(?:async\s+def|def|class)\s+(\w+)")
PYTHON_HEADER_LOOKBACK = 12
PYTHON_CLASS_HEADER = re.compile(r"^class\s+(\w+)")
GO_PACKAGE_LINE = re.compile(r"^package\s+\w+")
RUST_MODULE_DOC_LINE = "//!"

# The line under a comment block decides whether it documents a public symbol, by the rule of the file's suffix. Shell,
# lua, sql, yaml, json and qml have no public marker, so their comment blocks are never kept; c, cc and cpp files keep
# none either, since a definition there is private to its file unless a header names it.
EXPORT_LINE = re.compile(r"^\s*export\b")
COMMONJS_EXPORT_LINE = re.compile(r"^\s*(?:export\b|module\.exports\b|exports\.)")
TS_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
TS_EXPORTED_OWNER = re.compile(
    r"^export\s+(?:default\s+)?(?:declare\s+)?(?:abstract\s+)?(?:(?:const\s+)?enum|class|interface)\b"
    r"|^export\s+(?:declare\s+)?type\s+\w+[^=]*=\s*\{\s*$")
RUST_OWNER = re.compile(r"^\s*pub\s+(?:enum|trait)\b")
TS_NON_PUBLIC_MEMBER = re.compile(r"^\s*(?:\w+\s+)*?(?:private|protected)\b|^\s*#")
KOTLIN_OWNER = re.compile(r"^\s*(?!.*\b(?:private|internal)\b)(?:\w+\s+)*(?:class|object|interface)\b")
PYTHON_CONSTANT = re.compile(r"^([A-Za-z_]\w*)\s*(?::[^=]+)?=(?!=)")
HEADER_DECLARATION = re.compile(r"^(?!static\b|#)\w")
DECLARATION_START = r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*"
GO_FIELD_LINE = re.compile(r"^\s+[A-Z]\w*\b")
GO_FIELD_OWNER = re.compile(r"^\s*(?:type\s+)?[A-Z]\w*\s+(?:struct|interface)\s*\{|^(?:const|var|type)\s*\(\s*$")
# Python is not in this table: whether a def is public depends on the lines around it (python_symbol_is_public).
PUBLIC_SYMBOL = {
    ".go": re.compile(r"^\s*(?:func\s+(?:\([^)]*\)\s*)?|type\s+|var\s+|const\s+)[A-Z]"),
    ".rs": re.compile(r"^\s*pub\b(?!\()"),
    ".java": re.compile(DECLARATION_START + r"public\b"),
    ".swift": re.compile(DECLARATION_START + r"(?:public|open)\b"),
    ".kt": re.compile(r"^(?!.*\b(?:private|internal|protected)\b)"
                      r"(?:@\w+(?:\([^)]*\))?\s+)*(?:\w+\s+)*(?:fun|class|object|interface|val|var)\b"),
    ".php": re.compile(r"^\s*(?!.*\b(?:private|protected)\b)"
                       r"(?:public\b|(?:abstract\s+|final\s+)?(?:function|class|interface|trait)\b)"),
    ".rb": re.compile(r"^\s*(?:def|class|module)\s+(?:self\.)?[A-Za-z]"),
    ".h": HEADER_DECLARATION,
    ".hpp": HEADER_DECLARATION,
    **dict.fromkeys(TS_SUFFIXES, EXPORT_LINE),
    ".js": COMMONJS_EXPORT_LINE,
    ".cjs": COMMONJS_EXPORT_LINE,
}


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


def first_marker(row, markers):
    """The text of the first marker the row matches, or None."""
    if NOT_A_MARKER.search(row):
        return None
    for pattern in markers:
        found = pattern.search(row)
        if found:
            return found.group()
    return None


def marker_hit(raw_row, searched_row, eval_domain_counts):
    """The text of the marker a row carries, or None: the raw-line markers search raw_row, the others searched_row,
    the row with string text removed. The eval-domain markers count only when eval_domain_counts is true."""
    searched_markers = CASE_INSENSITIVE_MARKERS + CASE_SENSITIVE_MARKERS
    if eval_domain_counts:
        searched_markers = searched_markers + EVAL_DOMAIN_MARKERS
    raw_marker = first_marker(raw_row, RAW_LINE_MARKERS)
    if raw_marker:
        return raw_marker
    return first_marker(searched_row, searched_markers)


def marker_rows(file_lines, comments_only=False, file_path=""):
    """(number, line, marker text) of the non-blank lines carrying a workflow marker, ordered by line number.

    comments_only limits the scan to comment lines, for formats whose values are data, not prose. Lines inside a
    multi-line string held as data are not searched; on the line that opens one, only the text before the opening
    quote is, and on the line that closes one, only the text after the closing quote; on a template-literal line
    that closes one and opens another, only the text between them. In a test file the raw-line markers also skip
    string text: a plan path there is fixture data."""
    in_test_file = source_paths.is_test_path(file_path)
    in_agent_evals = AGENT_EVALS_CHECKOUT.search(file_path) is not None
    in_shell_file = SHELL_FILE.search(file_path) is not None
    style = source_text.comment_style_of(file_path)
    comment_numbers = comment_numbers_of(file_lines, style)
    code = source_text.code_text_by_line(file_path, file_lines)
    rows = []
    for number, line in enumerate(file_lines, 1):
        if not NONBLANK.search(line) or number not in code:
            continue
        is_comment = number in comment_numbers or (style is None and COMMENT_LINE.match(line))
        if comments_only and not is_comment:
            continue
        raw = code[number]
        searched = line
        if source_text.masks_string_text(line, raw, is_comment):
            searched = searchable_text(raw, style)

        raw_row = f"{number}:{searched}" if in_test_file else f"{number}:{raw}"
        eval_domain_counts = not in_agent_evals and (is_comment or not in_shell_file)
        marker = marker_hit(raw_row, f"{number}:{searched}", eval_domain_counts)
        if marker:
            rows.append((number, line, marker))
    return rows


def repo_relative_path(file_path, surface):
    """The file's path from its git work tree root, or `surface` when git does not name the root. An ancestor folder
    of the work tree never counts as a folder of the repo."""
    top = script_utils.work_tree_top(file_path, timeout=GIT_PROBE_TIMEOUT_SECONDS)
    if top is None:
        return surface
    return script_utils.repo_relative(top, os.path.realpath(file_path)) or surface


def old_text_lines(tool_input, file_path, original_file):
    """The set of lines the edit did not add: the lines of the file before the edit when the tool response carries it
    (`original_file`, a string), else the lines of the file at HEAD (none for a file HEAD does not hold, or outside a
    git work tree), plus an Edit's old_string. None when git failed and the file may be committed, so the old lines
    are unknown."""
    before = lines_before_edit(file_path, original_file)
    if before is None or "old_string" not in tool_input:
        return before
    return before | set(first_present(tool_input, "old_string").split("\n"))


def lines_before_edit(file_path, original_file):
    """The set of lines of `original_file` when it is a string, else the lines at HEAD (see committed_lines)."""
    if isinstance(original_file, str):
        return set(original_file.split("\n"))
    return committed_lines(file_path)


def committed_lines(file_path):
    """The set of lines of the file at HEAD; empty when HEAD lacks it or git has no work tree here; None when git
    failed and the file may be committed."""
    committed = script_utils.committed_text(file_path, GIT_PROBE_TIMEOUT_SECONDS)
    if committed is None:
        return None
    if committed == "":
        return set()
    return set(committed.split("\n"))


class CommentLines(NamedTuple):
    numbers: set
    data_numbers: set


def comment_lines_of(file_path, file_lines):
    """The comment line numbers of the file and the numbers of the lines inside a multi-line string held as data, or
    that close one, or inside a shell heredoc: none of those starts a statement. A suffix with no comment style falls
    back to COMMENT_LINE, which sees a line that opens with a comment leader; lines of a multi-line string held as
    data are never comments. A line that opens such a string is no comment, but it can start a statement."""
    style = source_text.comment_style_of(file_path)
    if style is None:
        numbers = {number for number, line in enumerate(file_lines, 1) if COMMENT_LINE.match(line)}
        return CommentLines(numbers, set())
    regions = source_text.string_data_regions(file_lines, style)
    data_numbers = regions.numbers | set(regions.closing_tails)
    if SHELL_FILE.search(file_path):
        data_numbers |= shell_statements.heredoc_body_line_numbers("\n".join(file_lines))
    numbers = comment_numbers_of(file_lines, style) - data_numbers - set(regions.openings)
    return CommentLines(numbers, data_numbers)


def python_symbol_is_public(file_lines, number, data_numbers):
    """True when the def or class header on line `number` (1-based) is public API: a column-0 symbol, or a method one
    level inside a public column-0 class. A name with no leading underscore is public, and so is a dunder. The walk
    up to the class skips comments, the lines of a multi-line string (`data_numbers`) and the lines of a bracketed
    class header."""
    header = PYTHON_HEADER.match(file_lines[number - 1])
    if header is None or not source_text.python_name_is_public(header.group(1)):
        return False
    if source_text.indent_of(file_lines[number - 1]) == 0:
        return True
    return python_owner_class_is_public(file_lines, number, data_numbers)


def python_owner_class_is_public(file_lines, number, data_numbers):
    """True when the nearest less-indented line above line `number` (1-based) is a public class header. The walk skips
    comments, the lines of a multi-line string (`data_numbers`) and the lines of a bracketed class header."""
    def skipped(line_number, line):
        return (line_number in data_numbers
                or line.lstrip().startswith(("#", "]", "}")))

    owner_line = owner_line_above(file_lines, number, skipped)
    if owner_line is None:
        return False
    owner = PYTHON_CLASS_HEADER.match(owner_line)
    return owner is not None and source_text.python_name_is_public(owner.group(1))


def python_docstring_is_public(file_lines, comment_numbers, first, data_numbers):
    """True for a docstring that starts at line `first` (1-based) and is the module's or a public def's or class's."""
    if not source_text.TRIPLE_QUOTE_START.match(file_lines[first - 1].strip()):
        return False
    above = file_lines[:first - 1]
    if all(not NONBLANK.search(line) or number in comment_numbers for number, line in enumerate(above, 1)):
        return True
    header_text = next((line for line in reversed(above) if NONBLANK.search(line)), "")
    if not header_text.rstrip().endswith(":"):
        return False
    for number in range(len(above), max(len(above) - PYTHON_HEADER_LOOKBACK, 0), -1):
        if PYTHON_HEADER.match(above[number - 1]):
            after_header = [line for line in above[number:] if NONBLANK.search(line)]
            if above[number - 1].rstrip().endswith(":") and after_header:
                return False
            if any(line.rstrip().endswith(":") for line in after_header[:-1]):
                return False
            return python_symbol_is_public(file_lines, number, data_numbers)
    return False


def symbol_number_below(file_lines, last):
    """The 1-based number of the line of code right under the comment block that ends at line `last`, past any
    decorators, or None."""
    for number in range(last + 1, len(file_lines) + 1):
        line = file_lines[number - 1]
        if DECORATOR_LINE.match(line):
            continue
        return number if NONBLANK.search(line) else None
    return None


def go_field_is_exported(file_lines, number):
    """True when line `number` (1-based) is an indented capitalised name directly inside a type struct, interface or
    type group, found by the nearest less-indented line above it."""
    if GO_FIELD_LINE.match(file_lines[number - 1]) is None:
        return False
    owner = owner_line_above(file_lines, number)
    return owner is not None and GO_FIELD_OWNER.match(owner) is not None


def owner_line_above(file_lines, number, skipped=None):
    """The nearest non-blank line above line `number` (1-based) that is less indented than it, or None. A line that
    starts with `)` or `>` closes a multi-line header, so the walk goes on to the header line. `skipped(line_number,
    line)`, when given, names the lines the walk passes over as well."""
    indent = source_text.indent_of(file_lines[number - 1])
    for line_number in range(number - 1, 0, -1):
        line = file_lines[line_number - 1]
        if not NONBLANK.search(line) or source_text.indent_of(line) >= indent:
            continue
        if skipped is not None and skipped(line_number, line):
            continue
        if line.lstrip().startswith((")", ">")):
            continue
        return line
    return None


def ts_member_is_exported(file_lines, number):
    """True when line `number` (1-based) is an indented member of an exported class or interface that is neither
    private, protected nor a `#` field."""
    line = file_lines[number - 1]
    if source_text.indent_of(line) == 0 or TS_NON_PUBLIC_MEMBER.match(line):
        return False
    owner = owner_line_above(file_lines, number)
    return owner is not None and TS_EXPORTED_OWNER.match(owner) is not None


def kotlin_member_is_public(file_lines, number):
    """True when the indented declaration on line `number` (1-based) sits directly in a class, object or interface
    that is not private or internal, and is not private, internal or protected itself."""
    line = file_lines[number - 1]
    rule = PUBLIC_SYMBOL[".kt"]
    if source_text.indent_of(line) == 0 or rule.search(line.lstrip()) is None:
        return False
    owner = owner_line_above(file_lines, number)
    return owner is not None and KOTLIN_OWNER.match(owner) is not None


def rust_member_is_public(file_lines, number):
    """True when line `number` (1-based) is indented directly inside a `pub enum` or `pub trait`, whose variants and
    items carry no `pub` of their own."""
    if source_text.indent_of(file_lines[number - 1]) == 0:
        return False
    owner = owner_line_above(file_lines, number)
    return owner is not None and RUST_OWNER.match(owner) is not None


def python_constant_is_public(file_lines, number, data_numbers):
    """True for a `NAME = value` or `NAME: type = value` line (1-based `number`) with a public name, at column 0 or
    directly inside a public column-0 class."""
    line = file_lines[number - 1]
    constant = PYTHON_CONSTANT.match(line.lstrip())
    if constant is None or not source_text.python_name_is_public(constant.group(1)):
        return False
    if source_text.indent_of(line) == 0:
        return True
    return python_owner_class_is_public(file_lines, number, data_numbers)


def block_documents_public_symbol(suffix, file_lines, block, data_numbers):
    last = block[1]
    symbol_number = symbol_number_below(file_lines, last)
    if symbol_number is None:
        return False
    if suffix == ".py":
        return (python_symbol_is_public(file_lines, symbol_number, data_numbers)
                or python_constant_is_public(file_lines, symbol_number, data_numbers))
    if suffix == ".go" and go_field_is_exported(file_lines, symbol_number):
        return True
    if suffix == ".go" and GO_PACKAGE_LINE.match(file_lines[symbol_number - 1]):
        return True
    if suffix in TS_SUFFIXES and ts_member_is_exported(file_lines, symbol_number):
        return True
    if suffix == ".kt" and kotlin_member_is_public(file_lines, symbol_number):
        return True
    if suffix == ".rs" and rust_member_is_public(file_lines, symbol_number):
        return True
    rule = PUBLIC_SYMBOL.get(suffix)
    return rule is not None and rule.search(file_lines[symbol_number - 1]) is not None


def leading_block(file_lines, blocks):
    """The (first, last) pair of the file's leading comment block, past a shebang and blank lines, or None."""
    first_line = 1
    while first_line <= len(file_lines):
        text = file_lines[first_line - 1]
        is_shebang = first_line == 1 and text.startswith(SHEBANG)
        if NONBLANK.search(text) and not is_shebang:
            break
        first_line += 1
    return next((block for block in blocks if block[0] <= first_line <= block[1]), None)


def is_license_header(file_lines, block, header):
    """True when `block` is the file's leading comment block and some line of it names a license or copyright."""
    if block != header:
        return False
    return any(LICENSE_WORDS.search(file_lines[number - 1]) for number in range(header[0], header[1] + 1))


def rust_module_doc_last_line(file_lines, block, header):
    """The number of the last line of the run of `//!` lines that opens the file's leading block, or the number of the
    line before the block when it does not open with one."""
    first, last = block
    if block != header:
        return first - 1
    kept_last = first - 1
    for number in range(first, last + 1):
        if not file_lines[number - 1].lstrip().startswith(RUST_MODULE_DOC_LINE):
            break
        kept_last = number
    return kept_last


def kept_through_line(file_path, file_lines, block, header, comment_lines):
    """The number of the last line of `block` kept as a license header or a comment block on a public symbol, or the
    number of the line before the block when no line of it is kept. A public Python docstring keeps only the lines
    of its quoted span: a `#` line under it is checked on its own."""
    first, last = block
    if is_license_header(file_lines, block, header):
        return last
    suffix = os.path.splitext(file_path)[1]
    if suffix == ".rs":
        module_doc_last = rust_module_doc_last_line(file_lines, block, header)
        if module_doc_last >= first:
            return module_doc_last
    if block_documents_public_symbol(suffix, file_lines, block, comment_lines.data_numbers):
        return last
    is_public_docstring = suffix == ".py" and python_docstring_is_public(
        file_lines, comment_lines.numbers, first, comment_lines.data_numbers)
    if is_public_docstring:
        return min(last, source_text.triple_quote_close_line(file_lines, first))
    return first - 1


def unkept_comment_lines(file_path, file_lines, comment_lines, added, edited_numbers, counting):
    """(number, stripped text) of each comment line in the charged span whose stripped text is in `added` that is not a
    kept kind and sits in a run of consecutive non-kept comment lines holding more than MAX_FREE_BLOCK_LINES lines
    whose stripped text is in `counting`, in line order. The run extends past the charged span through contiguous
    comment lines; only new lines inside the span are listed. A blank, delimiter, suppression, directive or URL line
    inside a comment block keeps the run going without counting; a license header or public-doc line ends it.
    `edited_numbers`, when given, limits the listed lines to those line numbers."""
    blocks = source_text.contiguous_runs(comment_lines.numbers)
    header = leading_block(file_lines, blocks)
    charged = charged_comment_numbers(comment_lines, edited_numbers)
    unkept = []
    bridges = set()
    for block in blocks:
        kept_last = kept_through_line(file_path, file_lines, block, header, comment_lines)
        for number in range(block[0], block[1] + 1):
            line = file_lines[number - 1]
            if not NONBLANK.search(line) or DELIMITER_LINE.match(line):
                if number > kept_last:
                    bridges.add(number)
                continue
            if number == 1 and line.startswith(SHEBANG):
                continue
            if number <= kept_last:
                continue
            if SUPPRESSION.search(line) or DIRECTIVE.search(line) or URL.search(line):
                bridges.add(number)
                continue
            unkept.append((number, line.strip()))
    long_numbers = in_long_runs(unkept, bridges, counting)
    return [(number, text) for number, text in unkept
            if number in long_numbers and number in charged and text in added]


def in_long_runs(unkept, bridges, counting):
    """The numbers of the `unkept` lines that sit in a run of consecutive line numbers holding more than
    MAX_FREE_BLOCK_LINES lines whose text is in `counting`. A line outside `counting` stays in the run without
    counting; a bridge number (a blank, delimiter, suppression, directive or URL line) joins the runs on either side
    without counting."""
    long_numbers = set()
    run_numbers = sorted({number for number, _ in unkept} | bridges)
    for first, last in source_text.contiguous_runs(run_numbers):
        run = [number for number, text in unkept if first <= number <= last]
        counted = [number for number, text in unkept if first <= number <= last and text in counting]
        if len(counted) > MAX_FREE_BLOCK_LINES:
            long_numbers.update(run)
    return long_numbers


def counting_texts(file_path, file_lines, added):
    """The stripped texts that count toward the run limit: when HEAD holds a copy of the file, every line of the file
    that HEAD lacks (so lines an earlier edit added still count); else `added`."""
    committed = committed_lines(file_path)
    if not committed:
        return added
    committed_stripped = {line.strip() for line in committed}
    return {line.strip() for line in file_lines} - committed_stripped - {""}


def stripped_added(added_lines, old_lines):
    """The stripped text of each line in `added_lines` that no line of `old_lines` has once stripped, blank
    excluded."""
    old_stripped = {line.strip() for line in old_lines}
    added = {line.strip() for line in added_lines} - old_stripped
    added.discard("")
    return added


def charged_comment_numbers(comment_lines, edited_numbers):
    """The comment line numbers the check charges: those inside the edited span, or all of them when `edited_numbers`
    is None."""
    if edited_numbers is None:
        return set(comment_lines.numbers)
    return comment_lines.numbers & edited_numbers


def touches_comment_line(tool_input, file_lines, comment_lines, added_lines, edited_numbers):
    """True when some comment line in the edited span (the whole file when `edited_numbers` is None) has stripped text
    in the new text and not in an Edit's old_string. Runs no git, so the gate can stop before it."""
    old_string_lines = []
    if "old_string" in tool_input:
        old_string_lines = first_present(tool_input, "old_string").split("\n")
    candidates = stripped_added(added_lines, old_string_lines)
    charged = charged_comment_numbers(comment_lines, edited_numbers)
    return any(file_lines[number - 1].strip() in candidates for number in charged)


def block_inside_repo(file_path, reason):
    """Exit 2 with the reason, except for a file outside a git work tree or one git ignores: a scratch probe there is
    free to name plan paths and other workflow strings."""
    if (not script_utils.inside_git_work_tree(file_path, GIT_PROBE_TIMEOUT_SECONDS)
            or script_utils.is_git_ignored(file_path, GIT_PROBE_TIMEOUT_SECONDS)):
        return 0
    emit_stderr(reason)
    return 2


def check(raw):
    payload = json.loads(raw)
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict):
        return 0
    tool_response = payload.get("tool_response")
    original_file = tool_response.get("originalFile") if isinstance(tool_response, dict) else None

    file_path = first_present(tool_input, "file_path")
    if not file_path or not os.path.isfile(file_path):
        return 0
    if not CODE_FILE.search(file_path):
        return 0
    surface = surface_of(file_path)
    if "/.claude/" in "/" + surface:
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
    leaks = [f'  {number}:{line}  <- marker "{marker}"\n'
             for number, line, marker in marker_rows(file_lines, data_only, file_path)
             if line in added_lines]
    if leaks:
        return block_inside_repo(
            file_path,
            f"comment-bloat-gate: private-workflow marker in an added line ({name}). Zero "
            "exceptions — drop the pointer (_shared/code-vocabulary.md):\n" + "".join(leaks),
        )

    edited_numbers = None
    if "old_string" in tool_input:
        edited_numbers = source_text.line_numbers_of_text(file_text, new_text)
    comment_lines = comment_lines_of(file_path, file_lines)
    if not touches_comment_line(tool_input, file_lines, comment_lines, added_lines, edited_numbers):
        return 0

    if source_paths.is_doc_path(repo_relative_path(file_path, surface)):
        return 0

    old_lines = old_text_lines(tool_input, file_path, original_file)
    if old_lines is None:
        emit_stderr(f"comment-bloat-gate: comment check skipped for {name}: git could not say what the file held "
                    "before this write.\n")
        return 0
    added_stripped = stripped_added(added_lines, old_lines)
    counting = counting_texts(file_path, file_lines, added_stripped)
    unkept = unkept_comment_lines(file_path, file_lines, comment_lines, added_stripped, edited_numbers, counting)
    if not unkept:
        return 0
    listing = "".join(f"  {number}: {text}\n" for number, text in unkept)
    return block_inside_repo(
        file_path,
        f"comment-bloat-gate: {len(unkept)} comment line(s) added to {name} sit in blocks of "
        f"{MAX_FREE_BLOCK_LINES + 1}+ lines that are not a kept kind (license header, lint or format suppression or "
        "tool directive, comment block on an exported or public symbol, line with a URL). Architecture goes in the "
        "repo's architecture docs, never in code comments (comment rule: skills/coder-core/SKILL.md). Delete each "
        "one, or turn it into a name: rename the code so it needs no comment.\n" + listing,
    )


def main():
    try:
        code = check(hook_input.read_stdin_text())
    except Exception as error:
        # Fail-open: a crash in this gate must not stop an edit, so it is reported and the edit goes on.
        emit_stderr(f"comment-bloat-gate: skipped after {type(error).__name__}: {error}\n")
        code = 0
    return code


if __name__ == "__main__":
    hook_input.run_gate(main)
