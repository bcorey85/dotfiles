"""Read the command word of a raw word list: `command_word_index`, `raw_word_names_command`, `word_names_command`,
`unquoted_word` and `without_subshell_closers`."""
import os

from shell_command import closed_segment_words, command_after_wrappers
from shell_steps import paren_depth_change


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


def without_subshell_closers(word):
    """The raw word without the unquoted trailing `)` that close a subshell, not one of the word's own `(`."""
    spare_closers = -paren_depth_change(word)
    while spare_closers > 0 and word.endswith(")"):
        word = word[:-1]
        spare_closers -= 1
    return word
