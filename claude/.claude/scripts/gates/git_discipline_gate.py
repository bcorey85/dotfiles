#!/usr/bin/env python3
"""PreToolUse hook on Bash: enforce git rules the generic bash safety gate does not cover.

  1. git stash (list and show are fine)
  2. git commit --amend
  3. attribution or session trailers in commit and PR text
  4. git commit or push on a branch that still carries the auto-generated `worktree-` prefix
  5. git commit on main or master, unless ./CLAUDE.md declares a "direct-edit repo"

Denies with PreToolUse decision JSON. Fails closed on internal error.
"""
import json
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
from hook_input import JqError, jq_get, jq_str

S =r"[ \t\r\f\v]+"
STASH = re.compile(r"\bgit" + S + r"stash\b", re.I)
STASH_READ = re.compile(r"\bgit" + S + r"stash" + S + r"(list|show)\b", re.I)
COMMIT = re.compile(r"\bgit" + S + r"commit\b", re.I)
AMEND = re.compile(r"(^|[ \t\r\f\v])--amend\b", re.M)
COMMIT_OR_PR = re.compile(r"\bgit" + S + r"commit\b|\bgh" + S + r"pr" + S + r"(create|edit)\b", re.I)
ATTRIBUTION = re.compile(r"Claude-Session:|claude\.ai/code/session_|Co-Authored-By:[ \t\r\f\v]*Claude", re.I)
COMMIT_OR_PUSH = re.compile(r"\bgit" + S + r"(commit|push)\b", re.I)


class DenyError(Exception):
    pass


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
    except ValueError, JqError:
        raise DenyError(
            "[git-discipline-gate] hook input did not parse — failing closed. Report this to the user."
        ) from None
    if not command:
        return

    branch = script_utils.current_branch(".") or ""

    if STASH.search(command) and not STASH_READ.search(command):
        raise DenyError("[git-discipline-gate] git stash is blocked: it breaks parallel-agent work and resets staged "
                   "files. If stashing is genuinely needed, ask the user — they can run it themselves.")

    if COMMIT.search(command) and AMEND.search(command):
        raise DenyError("[git-discipline-gate] git commit --amend is blocked: never rewrite history unless the user "
                   "explicitly asked. Make a new commit, or ask the user.")

    if COMMIT_OR_PR.search(command) and ATTRIBUTION.search(command):
        raise DenyError("[git-discipline-gate] Commit and PR text must carry no attribution or session trailer. Remove "
                   "it and retry.")

    if COMMIT_OR_PUSH.search(command) and branch.startswith("worktree-"):
        raise DenyError("[git-discipline-gate] branch '" + branch + "' still carries the auto-generated worktree- "
                   "prefix. Rename it to the plain TICKET-NUM-desc form and push it with -u first, then retry.")

    if COMMIT.search(command) and branch in ("main", "master") and not is_direct_edit_repo():
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
