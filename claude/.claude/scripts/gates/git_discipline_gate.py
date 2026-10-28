#!/usr/bin/env python3
"""PreToolUse hook on Bash: enforce git rules the generic bash safety gate does not cover.

  1. git stash in every form but list and show, and autostash on pull, rebase or merge (`--autostash`, or the
     rebase.autoStash / merge.autoStash config turned on through `-c` or `git config`)
  2. git commit --amend
  3. attribution or session trailers in commit and PR text
  4. git commit or push on a branch that still carries the auto-generated `worktree-` prefix
  5. git commit on main or master, unless ./CLAUDE.md declares a "direct-edit repo"

Rules 1, 2, 4 and 5 read git calls in command position, after git's own options (`-C <dir>`, `-c <key=value>`,
`--no-pager`) and wrapper words (env, timeout), and inside `$(...)` and backticks. Heredoc bodies, quoted strings and
comments are text, not calls. A command that names a code runner (`bash -c`, eval, xargs, ssh) is read as text: every
`git` word in it starts a call.

Denies with PreToolUse decision JSON. Fails closed on internal error.
"""
import json
import os
import re
import sys
from typing import NamedTuple

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
import shell_command
import shell_statements
from hook_input import JqError, jq_get, jq_str

S =r"[ \t\r\f\v]+"
COMMIT_OR_PR = re.compile(r"\bgit" + S + r"commit\b|\bgh" + S + r"pr" + S + r"(create|edit)\b", re.I)
ATTRIBUTION = re.compile(r"Claude-Session:|claude\.ai/code/session_|Co-Authored-By:[ \t\r\f\v]*Claude", re.I)
# The text of one git call inside code the gate cannot parse: from the `git` word to a separator or a quote.
GIT_CALL_TEXT = re.compile(r"\bgit\b[^\n;&|'\"`()]*", re.I)
LINE_CONTINUATION = re.compile(r"\\\n")
# git's own options that take the next word as their value.
GIT_VALUE_OPTIONS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}
STASH_READS = {"list", "show"}
AUTOSTASH_COMMANDS = {"pull", "rebase", "merge"}
AUTOSTASH_KEYS = {"rebase.autostash", "merge.autostash"}
FALSE_VALUES = {"false", "no", "off", "0"}


class GitCall(NamedTuple):
    subcommand: str
    arguments: list
    config: dict


class DenyError(Exception):
    pass


def git_call(words):
    """The GitCall the words run, once wrapper words and git's own options are dropped; None when they run no git
    subcommand."""
    words = shell_command.command_after_wrappers(words)
    if not words or os.path.basename(words[0]).lower() != "git":
        return None

    config = {}
    index = 1
    while index < len(words) and words[index].startswith("-"):
        option = words[index]
        takes_value = option in GIT_VALUE_OPTIONS and index + 1 < len(words)
        if option == "-c" and takes_value:
            key, _equals, value = words[index + 1].partition("=")
            config[key.lower()] = value.lower()
        index += 2 if takes_value else 1
    if index == len(words):
        return None
    return GitCall(words[index].lower(), words[index + 1:], config)


def git_calls(command):
    """Every GitCall the command makes in command position, those inside `$(...)` and backticks included. In code
    that names a code runner, each `git` word starts a call, quoted or not."""
    without_heredocs = shell_statements.strip_heredocs(command)
    joined = LINE_CONTINUATION.sub(" ", without_heredocs)
    code = shell_statements.strip_comments(joined)
    if shell_command.names_code_runner(code):
        texts = [found.group() for found in GIT_CALL_TEXT.finditer(code)]
        return [call for call in map(git_call, (text.split() for text in texts)) if call]

    calls = [call for call in map(git_call, shell_statements.statements(code)) if call]
    for span in shell_statements.code_spans(code):
        calls += git_calls(span)
    return calls


def is_stash(call):
    if call.subcommand != "stash":
        return False
    action = call.arguments[0].lower() if call.arguments else ""
    return action not in STASH_READS


def is_autostash(call):
    if call.subcommand == "config":
        return turns_on_autostash_config(call.arguments)
    if call.subcommand not in AUTOSTASH_COMMANDS:
        return False

    flags = [argument for argument in call.arguments if argument in ("--autostash", "--no-autostash")]
    if flags:
        return flags[-1] == "--autostash"
    return any(call.config[key] not in FALSE_VALUES for key in AUTOSTASH_KEYS if key in call.config)


def turns_on_autostash_config(arguments):
    # `git config [--global] rebase.autoStash true` sets it; a read (`--get`, no value) and a false value do not.
    for index, argument in enumerate(arguments):
        if argument.lower() not in AUTOSTASH_KEYS:
            continue
        if index + 1 == len(arguments):
            return False
        return arguments[index + 1].lower() not in FALSE_VALUES
    return False


def command_of(raw):
    """`jq -r '.tool_input.command // ""'` with trailing newlines dropped. Raises on input jq rejects."""
    if raw.strip() == "":
        return ""
    payload = json.loads(raw)
    return jq_str(jq_get(payload, "tool_input", "command"))


def is_direct_edit_repo():
    try:
        with open("CLAUDE.md", "rb") as handle:
            return b"direct-edit repo" in handle.read().lower()
    except OSError:
        return False


def run(raw):
    try:
        command = command_of(raw)
    except (ValueError, JqError):
        raise DenyError(
            "[git-discipline-gate] hook input did not parse — failing closed. Report this to the user."
        ) from None
    if not command:
        return

    branch = script_utils.current_branch(".") or ""
    calls = git_calls(command)
    subcommands = {call.subcommand for call in calls}

    if any(is_stash(call) for call in calls):
        raise DenyError("[git-discipline-gate] git stash is blocked in every form, a tagged `git stash push -m <tag>` "
                        "included: every worktree shares one stash stack, and a stash resets staged files. Set work "
                        "aside with a temporary WIP commit on your branch. If stashing is genuinely needed, ask the "
                        "user — they can run it themselves.")

    if any(is_autostash(call) for call in calls):
        raise DenyError("[git-discipline-gate] git autostash is blocked: it runs a git stash, which every worktree "
                        "shares and which resets staged files. Commit or set your work aside with a temporary WIP "
                        "commit first, or pass --no-autostash.")

    if any(call.subcommand == "commit" and "--amend" in call.arguments for call in calls):
        raise DenyError("[git-discipline-gate] git commit --amend is blocked: never rewrite history unless the user "
                   "explicitly asked. Make a new commit, or ask the user.")

    if COMMIT_OR_PR.search(command) and ATTRIBUTION.search(command):
        raise DenyError("[git-discipline-gate] Commit and PR text must carry no attribution or session trailer. Remove "
                   "it and retry.")

    if subcommands & {"commit", "push"} and branch.startswith("worktree-"):
        raise DenyError("[git-discipline-gate] branch '" + branch + "' still carries the auto-generated worktree- "
                   "prefix. Rename it to the plain TICKET-NUM-desc form and push it with -u first, then retry.")

    if "commit" in subcommands and branch in ("main", "master") and not is_direct_edit_repo():
        raise DenyError("[git-discipline-gate] git commit on " + branch + " is blocked: create a feature branch "
                   "first (global rule). If committing here is genuinely intended, the user can run it "
                   "themselves.")


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    internal = False
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"))
    except DenyError as denied:
        hook_input.emit_decision("deny", str(denied))
    except Exception:
        internal = True
    if internal:
        hook_input.emit_decision("deny", "[git-discipline-gate] internal error (exit 1) — failing closed. "
                                         "Report this to the user.")
    return 0


if __name__ == "__main__":
    hook_input.run_gate(main)
