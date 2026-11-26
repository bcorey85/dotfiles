#!/usr/bin/env python3
"""PreToolUse hook on Bash: stop an `rg` call that has no path and no piped input.

A command that is one step of one simple command is allowed with the path `.` appended (updatedInput) when the `.`
becomes rg's path, the command has no output redirection, its first word is exactly `rg`, and nothing in it expands.
Any other hanging command is denied, with the command to run instead when that command would not hang: an allow
must never cover a step the permission flow has not seen.

The Bash tool gives a command a stdin that is not a terminal. ripgrep then searches stdin and waits until the
timeout. A step that is fed by a pipe (`cmd | rg foo`) or by a `<` redirection reads that input on purpose and passes.
`rg foo | head` has rg first in its pipeline, so it hangs too. The gate is fail-open: a command the shared parser
cannot trust exits 0 with no output, and a crash in the check exits 0 after a report on
stderr; a broken import exits 1, which also lets the call run.
"""
import json
import os
import shlex
import sys

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(_SCRIPT_DIR), "lib")]
from shell_command import (
    parse_raw_simple_commands,
    parse_simple_commands,
    split_command_steps,
    without_assignments,
)
from shell_command_words import joined_raw_words
from shell_expansion import has_substitution_or_tilde, unquoted_expanding_word
from shell_statements import shell_code

# rg options that take a value; `--opt=value` is one word and needs no entry.
VALUE_SHORT_OPTIONS = set("efEmjgdtTABCMr")
VALUE_LONG_OPTIONS = {
    "--regexp", "--file", "--encoding", "--max-count", "--threads", "--glob", "--max-depth", "--type", "--type-not",
    "--after-context", "--before-context", "--context", "--max-columns", "--replace", "--pre", "--pre-glob",
    "--dfa-size-limit", "--engine", "--regex-size-limit", "--iglob", "--ignore-file", "--max-filesize",
    "--type-add", "--type-clear", "--color", "--colors", "--context-separator", "--field-context-separator",
    "--field-match-separator", "--hostname-bin", "--hyperlink-format", "--path-separator", "--sort", "--sortr",
    "--generate",
}
PATTERN_SHORT_OPTIONS = set("ef")
PATTERN_LONG_OPTIONS = {"--regexp", "--file"}
# Options after which rg searches no input at all, or the working directory.
NO_SEARCH_OPTIONS = {"--files", "--type-list", "--help", "-h", "--version", "-V", "--generate", "--pcre2-version"}

REASON_NO_FIX = ("`rg` with no path searches stdin, and the Bash tool's stdin never closes, so it hangs until the "
                 "timeout. Pass the path.")
REASON = REASON_NO_FIX + " Run this instead: {fixed}"


def is_rg(word):
    return word == "rg" or word.endswith("/rg")


def positional_count_and_flags(arguments):
    """(positional words, whether -e/-f/--regexp/--file gave the pattern, whether a no-search option is present)."""
    positionals = []
    has_pattern_option = False
    has_no_search = False
    index = 0
    while index < len(arguments):
        word = arguments[index]
        index += 1
        if word == "--":
            positionals.extend(arguments[index:])
            break
        if word.split("=", 1)[0] in NO_SEARCH_OPTIONS:
            has_no_search = True
        if word.startswith("--"):
            name = word.split("=", 1)[0]
            has_pattern_option = has_pattern_option or name in PATTERN_LONG_OPTIONS
            if "=" not in word and name in VALUE_LONG_OPTIONS:
                index += 1
            continue
        if word.startswith("-") and len(word) > 1:
            for position, letter in enumerate(word[1:], start=1):
                if letter not in VALUE_SHORT_OPTIONS:
                    continue
                has_pattern_option = has_pattern_option or letter in PATTERN_SHORT_OPTIONS
                if position == len(word) - 1:
                    index += 1
                break
            continue
        positionals.append(word)
    return positionals, has_pattern_option, has_no_search


def rg_without_path(words):
    """True when the simple command's words are an rg call that would search stdin."""
    words = without_assignments(words)
    if not words or not is_rg(words[0]):
        return False
    positionals, has_pattern_option, has_no_search = positional_count_and_flags(words[1:])
    if has_no_search:
        return False
    paths = positionals if has_pattern_option else positionals[1:]
    return not paths


def hanging_rg(command):
    """The words of the first rg call in the command that would hang, or None."""
    joined = shell_code(command)
    for operator, step in split_command_steps(joined):
        if operator == "|":
            continue
        try:
            simple_commands = parse_simple_commands(step)
        except ValueError:
            continue
        for words, redirections in simple_commands:
            reads_input_file = any("<" in redirect_operator for redirect_operator, _target in redirections)
            if not reads_input_file and rg_without_path(words):
                return without_assignments(words)
    return None


def is_one_simple_step(command):
    """True when the command, after comments and heredoc bodies are cut, is one step of one simple command that is
    the whole command with no output redirection, so an appended path cannot land on a different step."""
    joined = shell_code(command)
    if joined.strip() != command.strip():
        return False
    steps = split_command_steps(joined.strip())
    if len(steps) != 1:
        return False
    simple_commands = parse_simple_commands(steps[0][1])
    if len(simple_commands) != 1:
        return False
    _words, redirections = simple_commands[0]
    # An output redirection is a write the permission flow must see, so the call is denied, not rewritten.
    writes_output = any(">" in redirect_operator for redirect_operator, _target in redirections)
    return not writes_output


def is_plain_rg_call(command):
    """True when the command's first word is exactly `rg` and nothing in it expands or substitutes (no `$` or backtick
    outside single quotes that a backslash does not escape, no `~` word, glob, brace list or `=command` word), so the
    call is the one a `Bash(rg *)` permission rule covers. False when the raw words cannot be read or paired with the
    parsed words: the call is then denied, never allowed unchecked."""
    try:
        raw_commands = parse_raw_simple_commands(command)
        parsed_commands = parse_simple_commands(command)
    except ValueError as error:
        sys.stderr.write(f"rg_path_gate: raw words of {command!r} unreadable ({error}); call not rewritten\n")
        return False
    if len(raw_commands) != 1 or len(parsed_commands) != 1:
        return False
    # A word that glues a quoted part to more text is cut differently by the raw parser; join the parts back.
    raw_words = joined_raw_words(raw_commands[0], parsed_commands[0][0], command)
    if raw_words is None or raw_words[0] != "rg":
        return False
    if any(has_substitution_or_tilde(word) for word in raw_words):
        return False
    return not any(unquoted_expanding_word(word) for word in raw_words)


def decision(tool_input, command, words):
    """The hook output for a hanging rg call: an allow with the path appended, or a deny that names the fixed command
    when that command would not hang."""
    updated = command.rstrip() + " ."
    # The appended path must make rg's path; a dangling option would take it as its value.
    appended_fixes = is_one_simple_step(command) and hanging_rg(updated) is None
    if appended_fixes and is_plain_rg_call(command.strip()):
        return {"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "allow",
            "updatedInput": {**tool_input, "command": updated}}}
    # One step: the raw text keeps its quoting and expansions. Re-quoting the parsed words would change the meaning
    # (`"$X"` would turn into the literal `'$X'`). A raw text that the appended path does not fix (`(rg foo)`) is
    # re-joined from the parsed words.
    fixed = shlex.join([*words, "."])
    if appended_fixes:
        fixed = updated
    reason = REASON_NO_FIX if hanging_rg(fixed) is not None else REASON.format(fixed=fixed)
    return {"hookSpecificOutput": {
        "hookEventName": "PreToolUse", "permissionDecision": "deny",
        "permissionDecisionReason": reason}}


def main():
    try:
        payload = json.loads(sys.stdin.read())
        tool_input = payload.get("tool_input") or {}
        command = tool_input.get("command")
        if os.environ.get("CLAUDE_SKIP_HOOKS") or not isinstance(command, str) or "rg" not in command:
            sys.exit(0)
        words = hanging_rg(command)
        if words is not None:
            sys.stdout.write(json.dumps(decision(tool_input, command, words)))
    except Exception as error:
        # Fail-open: a crash never blocks the call, but it is reported.
        sys.stderr.write(f"rg_path_gate: crashed, call allowed unchecked: {error!r}\n")
    sys.exit(0)


if __name__ == "__main__":
    main()
