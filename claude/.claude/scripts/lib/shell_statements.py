"""Read a shell command as statements of words, ignoring heredoc bodies (except one fed to a shell interpreter, which
is code, and the `$(...)` and backtick spans of an unquoted one, which the shell runs), quoted strings and comments."""
import os
import re
from typing import NamedTuple

import shell_command

SKIP_WORDS = {"do", "then", "else", "elif", "if", "!", "time"}
# The delimiter is the whole shell word after `<<`: unquoted characters, quoted strings and escapes.
HEREDOC = re.compile(r"""(?<!<)<<(?!<)-?[ \t]*((?:[^\s|&;()<>'"\\]|\\.|'[^']*'|"(?:[^"\\]|\\.)*")+)""")
DELIMITER_PART = re.compile(r"""\\(.)|'([^']*)'|"((?:[^"\\]|\\.)*)"|([^'"\\]+)""")
ARITHMETIC = re.compile(r"\$?\(\(.*?\)\)")
QUOTED = re.compile(r"'[^']*'|\"(?:[^\"\\]|\\.)*\"")
QUOTE_MARK = re.compile("\x01(\\d+)\x01")
COMMENT_START = re.compile(r"(^|[\s;&|()])#")
COMMENT = re.compile(r"(^|\s)#[^\n]*")
COMMAND_SUBSTITUTION = re.compile(r"\$\(([^()]*)\)")
# A `&` inside a redirection (`2>&1`, `&>file`) is no separator.
SEPARATORS = re.compile(r"\n|;|&&|\|\||\|&|\||(?<![<>])&(?!>)|\(|\)")
STATEMENT_SPLIT = re.compile("(" + SEPARATORS.pattern + ")")
LINE_CONTINUING_OPERATORS = {"&&", "||", "|", "|&"}
ASSIGNMENT = re.compile(r"^[A-Za-z_]\w*=")


def substitution_pieces(body):
    """The `$(...)` and backtick spans of a heredoc body's lines, each wrapped in parentheses as its own command."""
    body_text = "\n".join(body)
    pieces = []
    for _start, _end, span in code_spans(body_text):
        pieces += ["(", span, ")"]
    return pieces


def strip_heredocs(command):
    """The command with each heredoc body and its terminator line cut out, except that the body of a heredoc fed to
    a shell interpreter (`bash <<EOF`) stays: it is code, and so does each `$(...)` and backtick span in the body of
    a heredoc whose delimiter is unquoted: the shell runs those. A line may open several heredocs; their bodies
    follow in order. The delimiter is the whole shell word, quotes removed. A `<<` inside quotes, a comment or
    arithmetic and a `<<<` here-string open none; a heredoc with no terminator line is not cut. A kept body is
    wrapped in `(` and `)` lines: the shell runs it in its own process."""
    def keep_bodies(line, lines, index, heredocs):
        bodies = heredoc_bodies(lines, index, [delimiter for delimiter, _quoted in heredocs])
        if not heredocs or bodies is None:
            return None

        added = []
        shell_body = opens_shell_heredoc(line)
        for (_delimiter, quoted), body in zip(heredocs, bodies, strict=True):
            if shell_body:
                added += ["(", *body, ")"]
            elif not quoted:
                added += substitution_pieces(body)
        return added, sum(len(body) + 1 for body in bodies)

    return rewrite_heredoc_lines(command, keep_bodies)


def strip_stored_heredocs(command):
    """The command with the body and terminator line of each heredoc cut out where the heredocs its line opens only
    store text: cat or tee writing a file, or an interpreter given a script file. The `$(...)` and backtick spans of an
    unquoted body stay, wrapped in `(` and `)` lines, because the shell runs them. Every other heredoc stays as
    written."""
    def cut_stored(line, lines, index, heredocs):
        if not heredocs:
            return None

        bodies = heredoc_bodies(lines, index, [delimiter for delimiter, _quoted in heredocs])
        if bodies is None or not stores_heredoc_text(line):
            return None

        added = []
        for (_delimiter, quoted), body in zip(heredocs, bodies, strict=True):
            if not quoted:
                added += substitution_pieces(body)
        return added, sum(len(body) + 1 for body in bodies)

    return rewrite_heredoc_lines(command, cut_stored)


def rewrite_heredoc_lines(command, handle):
    # Walk the lines, keeping each. For a line that holds `<<`, handle(line, lines, next_index, heredocs) returns None
    # to leave the following lines alone, or (lines to add after it, count of following lines to skip).
    lines = command.split("\n")
    kept = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        if "<<" not in line:
            continue

        text = "\n".join(kept)
        heredocs = heredoc_openers(text, len(text) - len(line))
        result = handle(line, lines, index, heredocs)
        if result is None:
            continue

        added, skipped = result
        kept += added
        index += skipped
    return "\n".join(kept)


def stores_heredoc_text(line):
    # True when the line parses, a command on it takes a heredoc, and each such command reads it as data that no
    # later command is piped from.
    try:
        piped_commands = shell_command.parse_piped_commands(strip_comments(line))
    except ValueError:
        return False

    takers = [position for position, (_words, redirections, _piped) in enumerate(piped_commands)
              if any(operator == "<<" for operator, _target in redirections)]
    if not takers:
        return False

    for position in takers:
        following = piped_commands[position + 1:position + 2]
        if following and following[0][2]:
            return False
        words, redirections, _piped = piped_commands[position]
        if not reads_heredoc_as_data(words, redirections):
            return False
    return True


def reads_heredoc_as_data(words, redirections):
    # cat or tee that writes a file, or an interpreter given a script file: stdin is text it stores or reads.
    words = shell_command.command_after_wrappers(words)
    if not words:
        return False

    program = os.path.basename(words[0])
    if program in {"cat", "tee"}:
        writes_file = any(shell_command.redirection_writes_file(operator, target) for operator, target in redirections)
        tee_file = program == "tee" and any(not word.startswith("-") for word in words[1:])
        return writes_file or tee_file
    if not shell_command.INTERPRETER.fullmatch(program):
        return False
    if shell_command.reads_code_from_stdin(words, redirections, False):
        return False
    return given_script_file_after_value_options(words)


def given_script_file_after_value_options(words):
    # True when the interpreter's options are all value-taking ones and a script file follows them. Any other option
    # (-i, -d, -m, --interactive) may read stdin as code, so the body stays readable.
    family = shell_command.interpreter_family(words[0])
    value_options = shell_command.INTERPRETER_FAMILIES[family]["value_options"]
    index = 1
    while index < len(words):
        word = words[index]
        if not word.startswith("-"):
            return True
        if word not in value_options:
            return False
        index += 2
    return False


def heredoc_bodies(lines, start, delimiters):
    # The body lines of each heredoc a line opens, in order, from lines[start:]; each ends at the first line that is
    # its delimiter. None when a terminator line is missing.
    bodies = []
    position = start
    for delimiter in delimiters:
        body = []
        while position < len(lines) and lines[position].strip() != delimiter:
            body.append(lines[position])
            position += 1
        if position == len(lines):
            return None
        position += 1
        bodies.append(body)
    return bodies


def code_spans(body):
    # (start offset, end offset, text) of each outermost `$(...)` and backtick span in body: the shell runs them.
    # The text is body[start:end]. A `\$` and a `\`` are plain text.
    spans = []
    index = 0
    while index < len(body):
        character = body[index]
        if character == "\\":
            index += 2
            continue
        if character == "$" and body[index + 1:index + 2] == "(":
            depth = 0
            for end in range(index + 1, len(body)):
                depth += {"(": 1, ")": -1}.get(body[end], 0)
                if depth == 0:
                    break
            spans.append((index + 2, end, body[index + 2:end]))
            index = end
        elif character == "`":
            end = body.find("`", index + 1)
            if end == -1:
                end = len(body)
            spans.append((index + 1, end, body[index + 1:end]))
            index = end
        index += 1
    return spans


def opens_shell_heredoc(line):
    # True when a command on the line takes a heredoc and runs a shell interpreter. A line this reading cannot parse
    # counts as a shell when any of its words names one: its body is kept and read as commands.
    try:
        piped_commands = shell_command.parse_piped_commands(strip_comments(line))
    except ValueError:
        words = re.split(r"[\s|&;()<>]+", line)
        return any(os.path.basename(word.strip("'\"")) in shell_command.SHELL_INTERPRETERS for word in words)
    return any(shell_command.runs_shell(words) and any(operator == "<<" for operator, _target in redirections)
               for words, redirections, _piped in piped_commands)


def heredoc_openers(text, line_start):
    # (delimiter, quoted) for each heredoc the last line of text opens, in order: the line starts at line_start. A
    # `<<` inside quotes (also quotes that open on an earlier line), a comment or arithmetic opens none. quoted is
    # True when any part of the delimiter word is quoted: the body then holds no substitution.
    hidden_positions = shell_command.quoted_positions(text)
    for arithmetic in ARITHMETIC.finditer(text, line_start):
        hidden_positions.update(range(arithmetic.start(), arithmetic.end()))
    openers = []
    for found in HEREDOC.finditer(text, line_start):
        if found.start() in hidden_positions:
            continue
        word = found.group(1)
        openers.append((delimiter_text(word), bool(re.search(r"""['"\\]""", word))))
    return openers


def delimiter_text(word):
    # The shell word with its quotes and escapes removed.
    parts = []
    for found in DELIMITER_PART.finditer(word):
        escaped, single, double, plain = found.groups()
        parts.append(escaped or single or (re.sub(r"\\(.)", r"\1", double) if double is not None else plain or ""))
    return "".join(parts)


def strip_comments(command):
    """The command with each comment outside quotes cut off, from its `#` to the end of its line. A quote character
    inside a comment opens no quote."""
    for comment in reversed(shell_command.unquoted_matches(COMMENT_START, command)):
        comment_start = comment.end() - 1
        line_end = command.find("\n", comment_start)
        command = command[:comment_start] + (command[line_end:] if line_end != -1 else "")
    return command


def clean(command, quotes=None):
    """The command with heredoc bodies, quoted strings and comments blanked. When `quotes` is a list, each quoted
    string is replaced by a QUOTE_MARK word part holding its index in `quotes`, and the string is appended there."""
    without_heredocs = strip_heredocs(command)
    if quotes is None:
        without_quotes = QUOTED.sub('""', without_heredocs)
    else:
        without_quotes = QUOTED.sub(lambda found: marked_quote(found.group(), quotes), without_heredocs)
    without_comments = COMMENT.sub(r"\1", without_quotes)
    return COMMAND_SUBSTITUTION.sub(lambda match: "$<" + match.group(1).replace(" ", "\x00") + ">", without_comments)


def marked_quote(quoted, quotes):
    # The quoted string's content (quotes removed, escapes in double quotes resolved) goes into quotes; the mark
    # that stands for it has no space, separator or quote character.
    inner = quoted[1:-1]
    if quoted[0] == '"':
        inner = re.sub(r'\\(["\\$`])', r"\1", inner)
    quotes.append(inner)
    return f"\x01{len(quotes) - 1}\x01"


class Statement(NamedTuple):
    operator_before: str
    words: list
    # The separator right after the statement; "" when the command ends there.
    operator_after: str


def statements_with_operators(command, kept_words=(), quotes=None):
    """Each statement as a Statement. `operator_before` is the separator right before the statement ("" for the
    first); `operator_after` is the one right after it. A newline after `&&`, `||`, `|` or `|&` leaves that operator
    in place as the next statement's `operator_before`, since the statement still hangs on it. A `&` ends its command,
    so a newline after it continues nothing. Leading do/then/else and env assignments are dropped from the words,
    except the words in `kept_words`. A list in `quotes` is filled as clean() describes, and the words then hold
    quote marks."""
    parsed = []
    operator = ""
    after_is_open = False
    for index, piece in enumerate(STATEMENT_SPLIT.split(clean(command, quotes))):
        if index % 2 == 1:
            if after_is_open:
                parsed[-1] = parsed[-1]._replace(operator_after=piece)
                after_is_open = False
            if piece != "\n" or operator not in LINE_CONTINUING_OPERATORS:
                operator = piece
            continue
        words = piece.split()
        while words and words[0] not in kept_words and (words[0] in SKIP_WORDS or ASSIGNMENT.match(words[0])):
            words = words[1:]
        if words:
            parsed.append(Statement(operator, words, ""))
            operator = ""
            after_is_open = True
    return parsed


def statements(command):
    # Each statement is a list of words. Leading do/then/else and env assignments are dropped.
    return [statement.words for statement in statements_with_operators(command)]


class WordPair(NamedTuple):
    # The statement's words with each quoted string blanked to `""`, and the same words with the quotes removed.
    blanked: list
    resolved: list


def statement_word_pairs(command):
    # Each statement of the command as a WordPair; the two lists have the same length.
    quotes = []
    pairs = []
    for statement in statements_with_operators(command, quotes=quotes):
        blanked = [QUOTE_MARK.sub('""', word) for word in statement.words]
        resolved = [resolved_word(word, quotes) for word in statement.words]
        pairs.append(WordPair(blanked, resolved))
    return pairs


ANSI_C_ESCAPE = re.compile(r"\\(x[0-9A-Fa-f]{1,2}|u[0-9A-Fa-f]{1,4}|U[0-9A-Fa-f]{1,8}|[0-7]{1,3}|.)", re.DOTALL)
MAX_CODE_POINT = 0x10FFFF
ANSI_C_SINGLE = {"a": "\a", "b": "\b", "e": "\x1b", "E": "\x1b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
                 "v": "\v"}


def decode_ansi_c_escape(found):
    body = found.group(1)
    if body[0] in "xuU" and len(body) > 1:
        code_point = int(body[1:], 16)
        if code_point > MAX_CODE_POINT:
            return found.group(0)
        return chr(code_point)
    if body[0] in "01234567":
        return chr(int(body, 8) & 0xFF)
    return ANSI_C_SINGLE.get(body, body)


def decode_ansi_c(content):
    # The text of a `$'...'` string as bash reads it: \xHH, \NNN, \uHHHH, \n and the like become their characters.
    return ANSI_C_ESCAPE.sub(decode_ansi_c_escape, content)


def resolved_word(word, quotes):
    """The word as the shell reads it: each quoted string put back without its quotes, a `$` before a quote
    (`$'--hard'`) dropped with its escapes decoded, and each backslash outside quotes removed from the character
    it escapes."""
    parts = []
    position = 0
    for mark in QUOTE_MARK.finditer(word):
        before = re.sub(r"\\(.)", r"\1", word[position:mark.start()])
        position = mark.end()
        content = quotes[int(mark.group(1))]
        if before.endswith("$"):
            content = decode_ansi_c(content)
        parts.append(before.removesuffix("$"))
        parts.append(content)
    parts.append(re.sub(r"\\(.)", r"\1", word[position:]))
    return "".join(parts)
