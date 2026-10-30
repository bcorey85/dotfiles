#!/usr/bin/env python3
"""PreToolUse hook on Bash: enforce git rules the generic bash safety gate does not cover.

  1. git stash in every form but list and show, and autostash on pull, rebase or merge (`--autostash`, or the
     rebase.autoStash / merge.autoStash config turned on through `-c` or `git config`)
  2. git commit --amend
  3. attribution or session trailers in commit and PR text
  4. git commit or push on a branch that still carries the auto-generated `worktree-` prefix
  5. git commit on main or master, unless the repo's CLAUDE.md declares a "direct-edit repo"

Rules 4 and 5 read the branch of the repo each call runs in. How the gate finds git calls and the directory each runs
in is documented in git_calls.py.

Denies with PreToolUse decision JSON. Fails closed on internal error.
"""
import json
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
from git_calls import git_calls
from hook_input import JqError, jq_get, jq_str

S =r"[ \t\r\f\v]+"
COMMIT_OR_PR = re.compile(r"\bgit" + S + r"commit\b|\bgh" + S + r"pr" + S + r"(create|edit)\b", re.I)
ATTRIBUTION = re.compile(r"Claude-Session:|claude\.ai/code/session_|Co-Authored-By:[ \t\r\f\v]*Claude", re.I)
STASH_READS = {"list", "show"}
AUTOSTASH_COMMANDS = {"pull", "rebase", "merge"}
AUTOSTASH_KEYS = {"rebase.autostash", "merge.autostash"}
# The path the stash and autostash denies name for bringing a base into unfinished work.
MERGE_WITH_WORK_UNCOMMITTED = ("To bring a base into unfinished work, run `git merge <base>` with the work "
                               "uncommitted: git stops and changes nothing when the merge touches an edited file. If "
                               "it stops, commit the work once /review hands back converged or deferred, then merge.")
FALSE_VALUES = {"false", "no", "off", "0"}


class DenyError(Exception):
    pass


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


def is_direct_edit_repo(directory):
    root = script_utils.repo_root(directory)
    if root is None:
        return False
    try:
        with open(root / "CLAUDE.md", "rb") as handle:
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

    calls = git_calls(command)

    if any(is_stash(call) for call in calls):
        raise DenyError("[git-discipline-gate] git stash is blocked in every form, a tagged `git stash push -m <tag>` "
                        "included: every worktree shares one stash stack, and a stash resets staged files. "
                        f"{MERGE_WITH_WORK_UNCOMMITTED} If stashing is genuinely needed, ask the user — they can run "
                        "it themselves.")

    if any(is_autostash(call) for call in calls):
        raise DenyError("[git-discipline-gate] git autostash is blocked: it runs a git stash, which every worktree "
                        "shares and which resets staged files. Pass --no-autostash to the command, or do not set the "
                        f"autostash config. {MERGE_WITH_WORK_UNCOMMITTED}")

    if any(call.subcommand == "commit" and "--amend" in call.arguments for call in calls):
        raise DenyError("[git-discipline-gate] git commit --amend is blocked: never rewrite history unless the user "
                   "explicitly asked. Make a new commit, or ask the user.")

    if COMMIT_OR_PR.search(command) and ATTRIBUTION.search(command):
        raise DenyError("[git-discipline-gate] Commit and PR text must carry no attribution or session trailer. Remove "
                   "it and retry.")

    for call in calls:
        check_branch(call)


def check_branch(call):
    """Rules 4 and 5 for one commit or push call, on the branch of the repo it runs in."""
    if call.subcommand not in ("commit", "push"):
        return
    branch = script_utils.current_branch(call.directory) or ""

    if branch.startswith("worktree-"):
        raise DenyError("[git-discipline-gate] branch '" + branch + "' still carries the auto-generated worktree- "
                   "prefix. Rename it to the plain TICKET-NUM-desc form and push it with -u first, then retry.")

    if call.subcommand == "commit" and branch in ("main", "master") and not is_direct_edit_repo(call.directory):
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
