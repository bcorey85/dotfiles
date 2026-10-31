"""The git calls a Bash command makes, and the directory each runs in.

Calls are read in command position, after git's own options (`-C <dir>`, `-c <key=value>`, `--no-pager`) and wrapper
words (env, timeout), and inside `$(...)` and backticks. Heredoc bodies, comments and quoted strings are text, not
calls, except that a `$(...)` or backtick span is still read as a call inside quotes, single or double (the shell
runs it only inside double quotes; the gate deliberately over-reads the single-quoted form). A call's
directory is its `-C` directory, taken relative to the target of an earlier `cd` in the same command, else to the
starting directory. A command with a `cd` after a `(` not preceded by `$` follows no `cd`, and a quoted, variable or
substituted target is not read: those calls run from the directory the earlier calls resolved to, with the `-C`
directory joined to it. SUBSHELL_CD matches such a `(` before a `cd`, quoted or not. A command that names a code runner
(`bash -c`, eval, xargs, ssh) is read as text: every `git` word in it starts a call.
"""
import os
import re
from typing import NamedTuple

import shell_command
import shell_statements

# The text of one git call inside code the gate cannot parse: from the `git` word to a separator or a quote.
GIT_CALL_TEXT = re.compile(r"\bgit\b[^\n;&|'\"`()]*", re.I)
SUBSHELL_CD = re.compile(r"(?<!\$)\(.*\bcd\b", re.S)
LINE_CONTINUATION = re.compile(r"\\\n")
CD_OPTIONS = ("-L", "-P", "-e", "-@", "--")
# A path word holding one of these is a quoted string, a variable, a substitution or a glob the gate cannot read.
UNREAD_PATH_MARKS = ('"', "'", "$", "`", "*", "?")


class GitCall(NamedTuple):
    subcommand: str
    arguments: list
    config: dict
    directory: str


def joined_directory(directory, target):
    """The directory `cd <target>` or `git -C <target>` moves to from `directory`; `directory` when the gate cannot
    read the target or the target is an option (`cd -`, `cd -P <dir>`)."""
    if not target or target.startswith("-") or any(mark in target for mark in UNREAD_PATH_MARKS):
        return directory
    expanded_target = os.path.expanduser(target)
    return os.path.join(directory, expanded_target)


def git_call(words, directory="."):
    """The GitCall the words run from `directory`, once wrapper words and git's own options are dropped; None when
    they run no git subcommand."""
    words = shell_command.command_after_wrappers(words)
    if not words or os.path.basename(words[0]).lower() != "git":
        return None

    config = {}
    options, index = shell_command.git_options(words)
    for option, value in options:
        if option == "-c" and value is not None:
            key, _equals, config_value = value.partition("=")
            config[key.lower()] = config_value.lower()
        if option == "-C" and value is not None:
            directory = joined_directory(directory, value)
    if index == len(words):
        return None
    return GitCall(words[index].lower(), words[index + 1:], config, directory)


def git_calls(command, directory="."):
    """Every GitCall the command makes in command position, those inside `$(...)` and backticks included. A call
    runs in the directory an earlier `cd` of the command moved to, else in `directory`. In code that names a code
    runner, each `git` word starts a call, quoted or not."""
    without_heredocs = shell_statements.strip_heredocs(command)
    joined = LINE_CONTINUATION.sub(" ", without_heredocs)
    code = shell_statements.strip_comments(joined)
    # A `cd` after a `(` may run in a subshell, whose directory does not carry on, so none is followed.
    follows_cds = SUBSHELL_CD.search(code) is None

    def directory_at(offset):
        if not follows_cds:
            return directory
        return resolved_directory(code[:offset], directory)

    if shell_command.names_code_runner(code):
        text_calls = [git_call(found.group().split(), directory_at(found.start()))
                      for found in GIT_CALL_TEXT.finditer(code)]
        return [call for call in text_calls if call]

    spans = shell_statements.code_spans(code)
    outer_code = code
    for span_start, span_end, _span in reversed(spans):
        outer_code = outer_code[:span_start] + outer_code[span_end:]

    calls = []
    statement_directory = directory
    for words in shell_statements.statements(outer_code):
        if words[0] == "cd":
            if follows_cds:
                statement_directory = cd_directory(words, statement_directory)
            continue
        call = git_call(words, statement_directory)
        if call:
            calls.append(call)

    for span_start, _span_end, span in spans:
        calls += git_calls(span, directory_at(span_start))
    return calls


def resolved_directory(code, directory):
    """The directory the `cd` statements of `code` leave a command in, starting from `directory`."""
    for words in shell_statements.statements(code):
        if words[0] == "cd":
            directory = cd_directory(words, directory)
    return directory


def cd_directory(words, directory):
    """The directory the `cd` statement `words` moves to from `directory`: `cd -L|-P|-e|-@|-- <dir>` follows `<dir>`,
    a bare `cd` goes home and `cd -` stays (OLDPWD is not known)."""
    arguments = words[1:]
    while arguments and arguments[0] in CD_OPTIONS:
        arguments = arguments[1:]
    if not arguments:
        return joined_directory(directory, os.path.expanduser("~"))
    return joined_directory(directory, arguments[0])
