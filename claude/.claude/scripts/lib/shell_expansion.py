"""What zsh expands in a raw command word: glob characters, glob qualifiers, brace lists, a leading
`=command`, unescaped `$` and backtick substitutions outside single quotes, and a leading `~`. Also the redirect target
words of a command text."""
import re

from code_text import SPC
from shell_command import (
    REDIRECT_OPERATOR,
    WORD_END_CHARACTERS,
    substitution_bounds,
    without_substitution_bodies,
)
from shell_quoting import literal_positions, quoted_positions, unquoted_matches

# A glob character zsh expands in a word. A brace list is read apart: only one with a comma or a sequence expands.
_GLOB_CHARACTER = re.compile(r"[*?\[]")
# A `(` right after one of these opens a substitution (`$(`) or a process substitution (`<(`, `>(`), not glob syntax.
_SUBSTITUTION_OPENER_PREFIX = "$<>"
# A `(` that zsh reads as the start of a glob qualifier (`f(:s.a.b.)`); `=(` is a process substitution too.
_GLOB_QUALIFIER_OPEN = rf"(?<![{re.escape(_SUBSTITUTION_OPENER_PREFIX)}=])\("
_GLOB_QUALIFIER = re.compile(_GLOB_QUALIFIER_OPEN)
# A `(` or `<` right after a word character, and the run of word characters that ends a text.
_WORD_CHARACTER = "[^" + re.escape(WORD_END_CHARACTERS) + "]"
_ATTACHED_OPENER = re.compile("(?<=" + _WORD_CHARACTER + ")[(<]")
_WORD_TAIL = re.compile(_WORD_CHARACTER + "+$")
_EXPANDING_CHARACTER = re.compile(_GLOB_CHARACTER.pattern + "|" + _GLOB_QUALIFIER_OPEN)
_PARAMETER_BODY = re.compile(r"\$\{[^}]*\}")
_EQUALS_EXPANSION = re.compile(r"=\w")
_DOLLAR = re.compile(r"\$")

def unquoted_expanding_word(word):
    """Whether the raw word holds an unquoted glob character, glob-qualifier `(`, leading `=command` or brace list
    with a comma or a sequence, which zsh expands (`{x}` and `a{}` are literal names). The inside of a `$(...)`, a
    backtick span or a `${...}` is not read: its characters are not the word's own."""
    without_bodies = _PARAMETER_BODY.sub("${x}", without_substitution_bodies(word))
    if unquoted_matches(_EXPANDING_CHARACTER, without_bodies):
        return True
    if _expands_equals(without_bodies):
        return True
    return _has_brace_list(without_bodies)


def has_substitution_or_tilde(word):
    """True when the raw word has a `$` or backtick outside single quotes and not backslash-escaped, or starts with a
    `~`. A `$` inside double quotes still expands."""
    if word.startswith("~"):
        return True
    literal = literal_positions(word)
    return any(letter in "$`" and index not in literal for index, letter in enumerate(word))


def _expands_equals(word):
    # zsh EQUALS: an unquoted `=` opening the word, then a name, is that command's path (`=python3`). A word with an
    # unquoted `$` is left to the variable check.
    if not _EQUALS_EXPANSION.match(word):
        return False
    return not unquoted_matches(_DOLLAR, word)


def _has_brace_list(word):
    # Whether an unquoted `{` in the word opens a list that expand_braces reads or rejects: a comma list or a sequence.
    for _start, close, alternatives in _unquoted_brace_lists(word):
        if len(alternatives) >= 2 or _is_sequence(word, close, alternatives):
            return True
    return False


def _unquoted_brace_lists(word):
    # (index of the `{`, index of its closer, the parts) for each `{` outside quotes that does not open a `${`.
    quoted = quoted_positions(word)
    for start, character in enumerate(word):
        if character != "{" or start in quoted or word[start - 1:start] == "$":
            continue
        close, alternatives = _brace_list(word, start, quoted)
        yield start, close, alternatives


def has_attached_glob_syntax(step):
    """True when a `(` or `<` sits against the word text before it (`$S/a(:h:h)`, `$S/a<->`, `S=(a b)`). zsh reads it as
    a glob qualifier, a numeric range or an array, and the command parser cuts the word there, so a target word read
    from the step stops short. A `$(`, a `<(`, a file descriptor before `<` (`2<in`) and a `(` or `<` inside a quoted
    span (a sed script) are no such syntax."""
    for match in unquoted_matches(_ATTACHED_OPENER, step):
        opener = match.group(0)
        run = _WORD_TAIL.search(step[:match.start()]).group(0)
        # The run holds no `<` or `>`, so only a `$` can open a substitution here.
        if run[-1] == "$" or (opener == "<" and run.isdigit()):
            continue
        return True
    return False


_REDIRECT_OPENER = re.compile(REDIRECT_OPERATOR + SPC + "*")


def redirect_target_words(text, extra_hidden=()):
    """The raw word after each `>` operator outside quotes and outside a `$(...)` or backtick span in text (a span's
    own text is read on its own), quotes and escapes kept, as the shell reads it:
    a blank, operator or `(` ends it only outside quotes, an escape and a `$(...)` or backtick span. A word that a
    `(` ends carries that `(`, so unquoted_expanding_word sees a glob qualifier. A `>` with no word (`>(cmd)`) gives
    none. extra_hidden holds positions where an operator is not one (arithmetic)."""
    hidden = quoted_positions(text, unclosed_is_quoted=False)
    substitution_positions = _substitution_positions(text)
    hidden.update(substitution_positions)
    words = []
    for opener in unquoted_matches(_REDIRECT_OPENER, text, set(extra_hidden) | substitution_positions):
        start = opener.end()
        end = start
        while end < len(text) and (end in hidden or text[end] not in WORD_END_CHARACTERS):
            end += 1
        if end == start:
            continue
        ends_in_paren = text[end:end + 1] == "("
        words.append(text[start:end] + ("(" if ends_in_paren else ""))
    return words


def cut_at_glob_qualifier(word):
    """The raw word cut at its first unquoted glob-qualifier `(`, keeping that `(` as the marker redirect_target_words
    gives; the word itself when it holds none. The parser also stops a target at that `(`."""
    hidden = _substitution_positions(word)
    qualifiers = unquoted_matches(_GLOB_QUALIFIER, word, hidden)
    if not qualifiers:
        return word
    return word[:qualifiers[0].end()]


def _substitution_positions(text):
    # The positions of each outermost `$(...)` and backtick span, its opener and closer included.
    positions = set()
    for start, end in substitution_bounds(text):
        opener_length = 2 if text[start - 1] == "(" else 1
        positions.update(range(start - opener_length, end + 1))
    return positions


BRACE_ALTERNATIVE_LIMIT = 64
# A zsh sequence list: `{1..3}`, `{-2..2..2}`, `{a..e}`.
_BRACE_SEQUENCE = re.compile(r"^(-?\d+\.\.-?\d+|[A-Za-z]\.\.[A-Za-z])(\.\.-?\d+)?$")


class BraceListError(ValueError):
    """A brace list that expand_braces does not read: it has more than BRACE_ALTERNATIVE_LIMIT words, or it is a
    sequence list (`{1..3}`)."""


class _TooManyWordsError(BraceListError):
    """The words of a list passed BRACE_ALTERNATIVE_LIMIT; expand_braces words the message with the written word."""


def expand_braces(word):
    """The words an unquoted comma list in the raw word expands to (`a{b,c}d` gives `abd` and `acd`), nested lists
    too; the word itself when it holds no list with a comma. Raises BraceListError for a list of more than
    BRACE_ALTERNATIVE_LIMIT words or for a sequence list, which it does not expand. The too-many message names the
    word as given, not a partly expanded one."""
    try:
        return _expand(word)
    except _TooManyWordsError:
        raise BraceListError(f"{word} expands to more than {BRACE_ALTERNATIVE_LIMIT} words") from None


def _expand(word):
    for start, close, alternatives in _unquoted_brace_lists(word):
        if len(alternatives) < 2:
            _reject_sequence(word, start, close, alternatives)
            continue
        return _expand_alternatives(word, start, close, alternatives)
    return [word]


def _expand_alternatives(word, start, close, alternatives):
    expanded = []
    for alternative in alternatives:
        expanded += _expand(word[:start] + alternative + word[close + 1:])
        if len(expanded) > BRACE_ALTERNATIVE_LIMIT:
            raise _TooManyWordsError
    return expanded


def _is_sequence(word, close, alternatives):
    # A one-part list with a closer that reads as a sequence (`{1..3}`).
    return close < len(word) and bool(_BRACE_SEQUENCE.match(alternatives[0]))


def _reject_sequence(word, start, close, alternatives):
    if _is_sequence(word, close, alternatives):
        raise BraceListError(f"{word[start:close + 1]} is a sequence list, which is not expanded")


def _brace_list(word, start, quoted):
    # (index of the `}` that closes the `{` at start, the comma-separated parts between them). No closer gives a
    # one-part list.
    depth = 0
    part_start = start + 1
    parts = []
    for index in range(start, len(word)):
        if index in quoted:
            continue
        character = word[index]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif character == "," and depth == 1:
            parts.append(word[part_start:index])
            part_start = index + 1
        if depth == 0:
            parts.append(word[part_start:index])
            return index, parts
    return len(word), [word]
