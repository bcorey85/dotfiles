"""Read the command word of a raw word list: `command_word_index`, `raw_word_names_command`, `word_names_command`,
`unquoted_word`, `placed_raw_words`, `joined_raw_words`, `gap_before_part`, `rejoined_word`,
`before_subshell_closer`, `script_call_arguments`, `command_call_arguments` and `variable_assignments`.

Owner of the raw, still-quoted words of a placed simple command (`placed_raw_words`): import it, never add a second
copy."""
import os
import shlex
import sys

from shell_command import (
    closed_segment_words,
    command_after_wrappers,
    parse_raw_simple_commands,
    resolved_command_words,
    split_simple_commands,
    step_words,
    without_substitutions,
)
from shell_quoting import quoted_positions
from shell_statements import ASSIGNMENT, shell_code


def unquoted_word(raw_word):
    """The raw word with its quotes removed, or the raw word when a quote never closes."""
    words = closed_segment_words(raw_word)
    return words[0] if words else raw_word


def word_names_command(word, name):
    """Whether the word, quotes removed, is the command `name` by its basename (`tee`, `/usr/bin/tee`)."""
    return os.path.basename(word) == name


def raw_word_names_command(raw_word, name):
    """Whether the raw word reads as the command `name` once its quotes, escapes and a leading `(` are removed (`"tee"`,
    `\\tee`, `/usr/bin/tee`, `(tee`)."""
    unquoted = closed_segment_words(raw_word)
    if not unquoted:
        return False
    return word_names_command(unquoted[0].lstrip("("), name)


def command_word_index(raw_words, name):
    """Index in raw_words of the command word, once leading `(` and wrapper words (`env`, `sudo`, `nice`, assignments)
    are peeled, when it reads as the command `name`; None when the command is another one. A `name` among the
    arguments of another command (`grep tee *.py`) is no match."""
    unquoted = [unquoted_word(raw_word) for raw_word in raw_words]
    first = 0
    while first < len(unquoted) and set(unquoted[first]) == {"("}:
        first += 1
    if first == len(unquoted):
        return None

    unquoted[first] = unquoted[first].lstrip("(")
    peeled = command_after_wrappers(unquoted[first:], peel_containers=False)
    if not peeled:
        return None

    command_index = len(raw_words) - len(peeled)
    if not raw_word_names_command(raw_words[command_index], name):
        return None
    return command_index


def command_call_arguments(command, command_name):
    """One list per simple command of `command` whose command word (wrappers peeled) is `command_name` by its
    basename: the words after it. `grep tee f` and `echo tee f` give nothing for `tee`. Read as
    `script_call_arguments` reads."""
    code = shell_code(command)
    words_by_command = resolved_command_words(code) or step_words(code)
    return [words[1:] for words in words_by_command if words and word_names_command(words[0], command_name)]


def script_call_arguments(command, script_name):
    """One list per simple command of `command` that runs the script `script_name` (a word whose basename is it): the
    words after that word. An empty list when the script is called with no arguments. The command is read as
    `shell_code` gives it, so a quote inside a heredoc body hides no later call; text shlex cannot read (`grep 'a\\|b'`)
    is read through `step_words`."""
    code = shell_code(command)
    words_by_command = resolved_command_words(code) or step_words(code)
    calls = []
    for words in words_by_command:
        for index, word in enumerate(words):
            if word_names_command(word, script_name):
                calls.append(words[index + 1:])
                break
    return calls


def variable_assignments(command):
    """{name: value} for each simple command of `command` that is a bare `NAME=value` assignment, a later one
    replacing an earlier one. A `$(...)` or backtick span in a value reads as `x`. Empty when the command cannot be
    read: a caller then knows no value, as `resolved_command_words` does."""
    code = without_substitutions(shell_code(command))
    try:
        simple_commands = split_simple_commands(code)
    except ValueError:
        return {}

    assigned = {}
    for words in simple_commands:
        if len(words) == 1 and ASSIGNMENT.match(words[0]):
            name, value = words[0].split("=", 1)
            assigned[name] = value
    return assigned


def gap_before_part(step, cursor, part):
    """(gap, end): the text of `step` between `cursor` and the next `part`, and the position after that part. None
    when the part is not found."""
    start = step.find(part, cursor)
    if start < 0:
        return None
    return step[cursor:start], start + len(part)


def rejoined_word(raw_words, index, step, cursor, raw_word, placed_word):
    """(raw_word, index, cursor): `raw_word` with the following raw words, from `index`, joined onto it with the text
    of `step` between them until its unquoted text is `placed_word`. None when the parts run out, one is missing from
    `step`, a redirection lies between two parts, or the joined text never equals `placed_word`."""
    while index < len(raw_words) and unquoted_word(raw_word) != placed_word:
        located = gap_before_part(step, cursor, raw_words[index])
        if located is None:
            return None
        gap, cursor = located
        # A redirection between two parts of one word cannot be rejoined into it.
        if gap.strip(" \t\r") != "":
            return None
        raw_word += gap + raw_words[index]
        index += 1
    if unquoted_word(raw_word) != placed_word:
        return None
    return raw_word, index, cursor


def joined_raw_words(raw_words, placed_words, step):
    """The raw words joined into one raw word per placed word: a word that glues a quoted part to more text
    (`"$PWD":/app`) or holds a blank inside quotes (`"a b"` after `X=`) is cut in several parts by the raw parser, and
    the parts are joined back, with the text of `step` that lay between them, until their unquoted text is the placed
    word. None when the raw words do not line up with the placed words or with `step`."""
    joined = []
    index = 0
    cursor = 0
    for placed_word in placed_words:
        if index >= len(raw_words):
            return None
        # Take one raw word before comparing: an empty placed word (`""`) already equals the empty text.
        raw_word = raw_words[index]
        index += 1
        located = gap_before_part(step, cursor, raw_word)
        if located is None:
            return None
        cursor = located[1]
        rejoined = rejoined_word(raw_words, index, step, cursor, raw_word, placed_word)
        if rejoined is None:
            return None
        raw_word, index, cursor = rejoined
        joined.append(raw_word)
    if index != len(raw_words):
        return None
    return joined


def placed_raw_words(placed):
    """The raw words of the placed simple command, quotes kept and redirections left out: the raw command of its step
    whose words, unquoted, are the placed command's, with glued parts joined. When none lines up, the placed command's
    resolved words stand in for them, quoted again so that unquoting them gives each word back whole."""
    try:
        raw_commands = parse_raw_simple_commands(placed.step)
    except ValueError as error:
        # A quote that the raw reader cannot close (`--x="a "`) leaves only the resolved words to go on.
        sys.stderr.write(f"placed_raw_words: raw words of {placed.step!r} unreadable ({error}); using resolved words\n")
        raw_commands = []
    for raw_words in raw_commands:
        joined = joined_raw_words(raw_words, placed.simple_command, placed.step)
        if joined is not None:
            return joined
    return [shlex.quote(word) for word in placed.simple_command]


def before_subshell_closer(text):
    """The text up to the first unquoted `)` that closes a subshell opened before the text, not one of the text's own
    `(`, without the blanks before it. The rest belongs to the outer command (`echo $(docker run img) > out`)."""
    quoted = quoted_positions(text, unclosed_is_quoted=False)
    depth = 0
    for index, char in enumerate(text):
        if index in quoted:
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        if depth < 0:
            return text[:index].rstrip()
    return text.rstrip()
