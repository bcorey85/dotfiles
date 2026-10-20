#!/usr/bin/env python3
"""Cap a quality check at one re-run per edit.

PostToolUse(Write|Edit|MultiEdit|NotebookEdit) touches `edits`; PreToolUse(Bash) denies a check whose last run is
newer than `edits`, unless a file in the repo was changed by means the Write/Edit hook never sees (shell
redirection, a script) more recently than that run, then it allows. PostToolUse(Bash) records the run;
PostToolUseFailure(Bash) does too, except when the failure was a timeout or an interrupt. Key: normalized command +
effective cwd (POSIX cksum). Escape: a trailing `#skip-quality-cap`. Fails closed only on the PreToolUse Bash path;
state errors fail open. State lives in ~/.claude/state/quality-check/<session>/.
"""
import json
import os
import re
import subprocess
import sys
import time

import hook_input
from hook_input import JqError, cksum, jq_get, jq_str, split_segments, truthy

WS ="[ \t\n\r\f\v]"
SP = " \t\n\r\f\v"
CHECKS = ("(npm|pnpm|yarn|bun)( run)? (test|lint|typecheck|type-check|check|build)|jest|vitest|pytest|tsc|eslint|"
          "ruff|mypy|go (test|vet)|golangci-lint|cargo (test|clippy|check)|make (test|lint|check|typecheck)|"
          "(bundle exec )?rspec|phpunit|dotnet test|mvn test|gradle test|shellcheck|luacheck|stylua")
CHECK_START = re.compile("^(" + CHECKS + ")(" + WS + "|$)")
CD_SEGMENT = re.compile("^cd" + WS + "+([^" + SP + "]+)$")
WRAPPER = re.compile("^(time|env|npx|bunx|pnpm exec|yarn dlx)" + WS + "+")
ASSIGNMENT = re.compile(r"^[^\W\d]\w*=[^" + SP + "]*" + WS + "+")
DENY_TEXT = ("' already ran this session and nothing has been edited since. Re-running unchanged code cannot "
             "produce a different result. Redirect the failing run to /tmp/check.log, read the WHOLE log, fix every "
             "failure in one batch, then run it once more. If it still fails after that batch fix, stop and ask "
             "the user. If this deny is wrong, re-run the command with a trailing #skip-quality-cap comment "
             "— it disarms this gate for that one command.")


class Deny(Exception):
    pass


class Exit(Exception):
    def __init__(self, rc=0):
        Exception.__init__(self)
        self.rc = rc


EMPTY = object()


def field(root, *keys, **options):
    """jq -r '.a.b // default'. Empty input makes jq print nothing, so the field is empty even with a default.
    Only a missing, null or false value takes the default; an empty string stays empty."""
    if root is EMPTY:
        return ""
    value = jq_get(root, *keys)
    if "default" in options and not truthy(value):
        return options["default"]
    return jq_str(value)


def emit_deny(reason):
    hook_input.emit_decision("deny", reason)


def touch(path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT, 0o666)
    os.close(descriptor)
    os.utime(path, None)


def newer(path, other):
    """bash `[[ path -nt other ]]`."""
    try:
        mine = os.stat(path).st_mtime_ns
    except OSError:
        return False
    try:
        theirs = os.stat(other).st_mtime_ns
    except OSError:
        return True
    return mine > theirs


def prune_old(directory, now=None):
    """find directory -mindepth 1 -mtime +2 -delete. Like find, an entry's age is read before its children go."""
    now = time.time() if now is None else now
    try:
        names = os.listdir(directory)
    except OSError:
        return
    for name in names:
        path = os.path.join(directory, name)
        try:
            info = os.lstat(path)
            is_dir = os.path.isdir(path) and not os.path.islink(path)
            if is_dir:
                prune_old(path, now)
            if int((now - info.st_mtime) / 86400) > 2:
                if is_dir:
                    os.rmdir(path)
                else:
                    os.unlink(path)
        except OSError:
            pass


def git_output(args):
    try:
        finished = subprocess.run(["git"] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    except OSError:
        return None
    return finished.stdout if finished.returncode == 0 else None


def changed_since_run(cwd, run_file):
    top_bytes = git_output(["-C", cwd, "rev-parse", "--show-toplevel"])
    if top_bytes is None:
        return False
    top = os.fsdecode(top_bytes).rstrip("\n")
    listing = git_output(["-C", top, "ls-files", "-z", "--modified", "--others", "--exclude-standard"])
    if not listing:
        return False
    for name in listing.split(b"\0"):
        if name and newer(top + "/" + os.fsdecode(name), run_file):
            return True
    return False


def normalize(segment):
    segment = re.sub(r"[0-9]*>&[0-9]+", "", segment)
    segment = re.sub("[0-9]*>>?" + WS + "*[^" + SP + "]+", "", segment)
    segment = re.sub(WS + "+", " ", segment)
    segment = re.sub("^ ", "", segment)
    return re.sub(" $", "", segment)


def state_dir_for(root, session):
    return root + "/" + session


def run(raw, state):
    if raw.strip() == "":
        root_json = EMPTY
    else:
        try:
            root_json = json.loads(raw)
            state["tool"] = field(root_json, "tool_name")
        except (ValueError, JqError):
            raise Exit(0)
    tool = state["tool"]
    event = field(root_json, "hook_event_name")
    state["event"] = event
    session = field(root_json, "session_id", default="unknown")
    cwd = field(root_json, "cwd") or os.getcwd()

    home = os.environ["HOME"]
    root = home + "/.claude/state/quality-check"
    state_dir = state_dir_for(root, session)
    try:
        os.makedirs(state_dir, exist_ok=True)
    except OSError:
        raise Exit(0)
    prune_old(root)

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        try:
            touch(state_dir + "/edits")
        except OSError:
            pass
        return
    if tool != "Bash":
        return

    if event == "PostToolUseFailure":
        error_type = field(root_json, "tool_error", "error_type")
        if error_type in ("timeout", "interrupted"):
            return
        if "Command timed out after" in field(root_json, "error"):
            return

    command = field(root_json, "tool_input", "command")
    if not command:
        return
    if event == "PreToolUse" and "#skip-quality-cap" in command:
        return
    command = command.replace("#skip-quality-cap", "")

    for segment in split_segments(command):
        segment = re.sub("^" + WS + "+", "", segment)
        segment = re.sub(WS + "+$", "", segment)
        moved = CD_SEGMENT.match(segment)
        if moved:
            target = moved.group(1)
            if target.startswith("~"):
                target = home + target[1:]
            cwd = target if target.startswith("/") else cwd + "/" + target
            continue
        while True:
            stripped = ASSIGNMENT.sub("", WRAPPER.sub("", segment, count=1), count=1)
            if stripped == segment:
                break
            segment = stripped
        if not CHECK_START.search(segment):
            continue

        norm = normalize(segment)
        key = str(cksum((norm + "\n" + cwd).encode("utf-8", "surrogateescape")))
        run_file = state_dir + "/run-" + key

        if event in ("PostToolUse", "PostToolUseFailure"):
            try:
                touch(run_file)
            except OSError:
                raise Exit(0)
            continue

        if newer(run_file, state_dir + "/edits"):
            if not changed_since_run(cwd, run_file):
                raise Deny("[quality-check-cap] '" + norm + DENY_TEXT)


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    state = {"tool": "", "event": ""}
    internal = None
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"), state)
    except Deny as denied:
        emit_deny(str(denied))
    except Exit as done:
        return done.rc
    except JqError as error:
        internal = error.rc
    except Exception:
        internal = 1
    if internal is None:
        return 0
    if state["tool"] == "Bash" and state["event"] == "PreToolUse":
        emit_deny("[quality-check-cap] internal error (exit %d) — failing closed. Report this to the "
                  "user." % internal)
        return 0
    return internal


if __name__ == "__main__":
    hook_input.run_gate(main)
