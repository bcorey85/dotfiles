#!/usr/bin/env python3
"""PreToolUse hook on Bash: deny an `rg` call that has no path and no piped input, with the command to run instead.

The Bash tool gives a command a stdin that is not a terminal. ripgrep then searches stdin and waits until the
timeout. A step that is fed by a pipe (`cmd | rg foo`) or by a `<` redirection reads that input on purpose and passes.
`rg foo | head` has rg first in its pipeline, so it hangs too. Any error, or a command the shared parser cannot
trust, exits 0 with no output.
"""
import json
import os
import shlex
import sys

_SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path[:0] = [os.path.join(os.path.dirname(_SCRIPT_DIR), "lib")]
from shell_command import parse_simple_commands, split_command_steps, without_assignments

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

REASON = ("`rg` with no path searches stdin, and the Bash tool's stdin never closes, so it hangs until the timeout. "
          "Pass the path. Run this instead: {fixed}")


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
    for operator, step in split_command_steps(command):
        if operator == "|":
            continue
        for words, redirections in parse_simple_commands(step):
            reads_input_file = any("<" in redirect_operator for redirect_operator, _target in redirections)
            if not reads_input_file and rg_without_path(words):
                return without_assignments(words)
    return None


def main():
    try:
        payload = json.loads(sys.stdin.read())
        command = (payload.get("tool_input") or {}).get("command")
        if os.environ.get("CLAUDE_SKIP_HOOKS") or not isinstance(command, str) or "rg" not in command:
            sys.exit(0)
        words = hanging_rg(command)
        if words is not None:
            fixed = shlex.join([*words, "."])
            sys.stdout.write(json.dumps({"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "deny",
                "permissionDecisionReason": REASON.format(fixed=fixed)}}))
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
