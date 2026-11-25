"""Which characters of a shell command sit inside quotes, a comment or after a backslash, and `shell_word`: a path as
one quoted shell word a person can paste."""
import re
import shlex

_QUOTE_CHARACTERS = re.compile(r"[\"'\\]")


_UNSAFE_IN_DOUBLE_QUOTES = re.compile(r"[\"$`\\!\n]")


def shell_word(text):
    """The text as one shell word a person can paste: in double quotes, or in shell quoting from `shlex.quote`
    when the text holds a character that double quotes would expand or end on."""
    text = str(text)
    if not _UNSAFE_IN_DOUBLE_QUOTES.search(text):
        return f'"{text}"'
    return shlex.quote(text)


def without_quote_characters(text):
    """The text with every quote and backslash dropped, as the shell drops them from `t""ee` or `git 'commit'` before
    the program runs."""
    return _QUOTE_CHARACTERS.sub("", text)


def quoted_positions(command, unclosed_is_quoted=True):
    # The indexes of the characters that sit inside quotes, inside a comment (after its `#`, up to the newline) or
    # right after a backslash outside single quotes. A quote that never closes covers the rest of the command, unless
    # unclosed_is_quoted is False: then the text after it counts as unquoted, as a check that must not be hidden by a
    # stray quote needs. A quote character inside a comment opens no quote. The text of a `$(...)` or backtick span
    # inside double quotes is code the shell runs, so it is not quoted: it is read with its own quote state.
    scan = _QuoteScan(command)
    scan.run()
    positions = scan.positions
    if scan.levels[0]["quote"] is not None and not unclosed_is_quoted:
        positions = {position for position in positions if position < scan.quote_opened_at}
    return positions


def starts_comment(command, index):
    """Whether a `#` at index starts a word, so it would open a comment unless it sits in quotes. A `(` before it
    counts only when that `(` itself starts a word (`( #` and `((#`, not `*(#q.)` or `$(#`). A `)` before it never
    does: reading more text is the safe side for the gates."""
    if index == 0:
        return True
    before = command[index - 1]
    if before == "(":
        return starts_comment(command, index - 1)
    return before in " \t\r\f\v\n;&|"


_LINE_CONTINUATION = re.compile(r"\\\r?\n")


def join_line_continuations(text):
    """The text with each backslash-newline dropped, as the shell does. A backslash that is itself escaped (`\\\\`
    before the newline) or sits in single quotes or a comment joins nothing: the line ends there."""
    hidden = quoted_positions(text)
    pieces = []
    last_end = 0
    for match in _LINE_CONTINUATION.finditer(text):
        if match.start() in hidden:
            continue
        pieces.append(text[last_end:match.start()])
        last_end = match.end()
    pieces.append(text[last_end:])
    return "".join(pieces)


def ansi_c_quote_starts(command):
    """The index of the `$` of each `$'...'` string that the quote scan opens as ANSI-C: not one in quotes or a
    comment, and not the second `$` of `$$'`."""
    scan = _QuoteScan(command)
    scan.run()
    return scan.ansi_c_starts


class _QuoteScan:
    """The state of one quoted_positions pass over a command, one character at a time."""

    def __init__(self, command):
        self.command = command
        self.positions = set()
        self.ansi_c_starts = []
        self.comment_starts = []
        # One level per open `"$(` or "`" span, after the base level: its quote, how it closes, its open `(` count, and
        # whether its quote is ANSI-C.
        self.levels = [{"quote": None, "closer": None, "depth": 0, "ansi_c": False}]
        self.quote_opened_at = 0
        self.index = 0

    def run(self):
        while self.index < len(self.command):
            character = self.command[self.index]
            level = self.levels[-1]
            if level["quote"] is None:
                self._read_unquoted(character, level)
            else:
                self._read_quoted(character, level)
            self.index += 1

    def _read_unquoted(self, character, level):
        if character in "'\"":
            self._open_quote(character, level, ansi_c=False)
        elif character == "$" and self.command[self.index + 1:self.index + 2] in ("$", "'"):
            self._read_dollar_pair(level)
        elif character == "\\":
            self._hide_next_character()
        elif character == "#" and starts_comment(self.command, self.index) and not self._follows_hidden_character():
            self._hide_comment()
        else:
            self._read_span_syntax(character, level)

    def _follows_hidden_character(self):
        # `x\ #` is one word: the backslash hid the blank, so no comment starts at the `#`.
        # The shell removes a backslash-newline first, so a `#` after one is judged by the text before the backslash.
        if self.index == 0 or self.index - 1 not in self.positions:
            return False
        follows_continuation = self.index >= 2 and self.command[self.index - 2:self.index] == "\\\n"
        if follows_continuation:
            return not starts_comment(self.command, self.index - 2)
        return True

    def _read_span_syntax(self, character, level):
        # Track the parentheses of an open `$(` span and the character that closes the span.
        if character == "(" and level["closer"] == ")":
            level["depth"] += 1
        elif character == ")" and level["closer"] == ")" and level["depth"]:
            level["depth"] -= 1
        elif character == level["closer"]:
            self.levels.pop()

    def _read_quoted(self, character, level):
        quote = level["quote"]
        if character == quote:
            level["quote"] = None
        elif character == "\\" and (quote == '"' or level["ansi_c"]):
            self._hide_next_character()
        elif quote == '"' and self.command.startswith("$(", self.index):
            self.levels.append({"quote": None, "closer": ")", "depth": 0, "ansi_c": False})
            self.index += 1
        elif quote == '"' and character == "`":
            self.levels.append({"quote": None, "closer": "`", "depth": 0, "ansi_c": False})
        else:
            self.positions.add(self.index)

    def _read_dollar_pair(self, level):
        # `$$` is the process id, so a quote after it is plain. `$'...'` is an ANSI-C string: a backslash escapes the
        # quote character inside it.
        self.index += 1
        if self.command[self.index] == "'":
            self.ansi_c_starts.append(self.index - 1)
            self._open_quote("'", level, ansi_c=True)

    def _open_quote(self, character, level, ansi_c):
        level["quote"] = character
        level["ansi_c"] = ansi_c
        if len(self.levels) == 1:
            self.quote_opened_at = self.index

    def _hide_next_character(self):
        self.positions.add(self.index + 1)
        self.index += 1

    def _hide_comment(self):
        self.comment_starts.append(self.index)
        comment_end = self.command.find("\n", self.index)
        if comment_end == -1:
            comment_end = len(self.command)
        self.positions.update(range(self.index + 1, comment_end))
        # run() adds one after each character, so stop on the newline's predecessor.
        self.index = comment_end - 1


def strip_comments(command):
    """The command with each comment outside quotes cut off, from its `#` to the end of its line. A quote character
    inside a comment opens no quote. The text after a quote that never closes is read again as a command of its
    own, so a comment in it is cut too."""
    scan = _QuoteScan(command)
    scan.run()
    if scan.levels[0]["quote"] is None:
        return _cut_comments(command, scan.comment_starts)

    head = command[:scan.quote_opened_at + 1]
    tail = command[scan.quote_opened_at + 1:]
    return _cut_comments(head, scan.comment_starts) + strip_comments(tail)


def _cut_comments(command, comment_starts):
    for index in reversed(comment_starts):
        line_end = command.find("\n", index)
        command = command[:index] + (command[line_end:] if line_end != -1 else "")
    return command


def unquoted_matches(pattern, text, extra_hidden=()):
    """The matches of the compiled pattern in text whose start is not inside quotes, nor at a position in
    extra_hidden. A quote that never closes hides nothing."""
    hidden = quoted_positions(text, unclosed_is_quoted=False)
    hidden.update(extra_hidden)
    return [match for match in pattern.finditer(text) if match.start() not in hidden]
