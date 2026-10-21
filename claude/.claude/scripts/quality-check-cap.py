#!/usr/bin/env python3
"""Cap a quality check at one re-run per edit.

PostToolUse(Write|Edit|MultiEdit|NotebookEdit) touches `edits`; PreToolUse(Bash) denies a check whose last run is
newer than `edits`, unless a file in the repo was changed by means the Write/Edit hook never sees (shell
redirection, a script) more recently than that run, then it allows. PostToolUse(Bash) records the run;
PostToolUseFailure(Bash) does too, except when the failure was a timeout or an interrupt. A check is recorded only
when it surely ran: after a failure, a check behind `&&` or `||` may never have started, so it is not recorded; after
a success, a check behind `||` is not. A command with a formatter that rewrites files (`cargo fmt`, `prettier
--write`, `ruff format`...) is never denied, and resets the cap like an edit. Key: normalized command +
effective cwd (POSIX cksum). Escape: a trailing `#skip-quality-cap`. Fails closed only on the PreToolUse Bash path;
state errors fail open. State lives in ~/.claude/state/quality-check/<session>/.
"""
import json
import os
import re
import subprocess
import sys
import time

import hashlib

import hook_input
from hook_input import JqError, cksum, jq_get, jq_str, truthy
from shell_command import split_command_steps, step_surely_ran

WS ="[ \t\n\r\f\v]"
SP = " \t\n\r\f\v"
CHECKS = ("(npm|pnpm|yarn|bun)( run)? (test|lint|typecheck|type-check|check|build)|jest|vitest|pytest|tsc|eslint|"
          "ruff|mypy|go (test|vet)|golangci-lint|cargo (test|clippy|check)|make (test|lint|check|typecheck)|"
          "(bundle exec )?rspec|phpunit|dotnet test|mvn test|gradle test|shellcheck|luacheck|stylua")
CHECK_START = re.compile("^(" + CHECKS + ")(" + WS + "|$)")
FORMATTERS = ("cargo fmt|rustfmt|black|gofmt|go fmt|ruff format|prettier|biome (format|check)|eslint|dotnet format|"
              "(npx )?stylelint|rubocop|php-cs-fixer")
FORMATTER_START = re.compile("^(" + FORMATTERS + ")(" + WS + "|$)")
FORMATTER_WRITES = re.compile(r"--write|(^|\s)-w(\s|$)|--fix|--apply")
FORMATTER_READS_ONLY = re.compile(r"--check|--diff|--dry-run|(^|\s)-l(\s|$)|--list-different")
FORMATTER_WRITES_BY_DEFAULT = re.compile("^(cargo fmt|rustfmt|black|ruff format|go fmt|dotnet format)")
CD_SEGMENT = re.compile("^cd" + WS + "+([^" + SP + "]+)$")
WRAPPER = re.compile("^(time|env|npx|bunx|pnpm exec|yarn dlx)" + WS + "+")
ASSIGNMENT = re.compile(r"^[^\W\d]\w*=[^" + SP + "]*" + WS + "+")
DENY_TEXT = ("' already ran this session and nothing has been edited since. Re-running unchanged code cannot "
             "produce a different result. Redirect the failing run to /tmp/check.log, read the WHOLE log, fix every "
             "failure in one batch, then run it once more. If it still fails after that batch fix, stop and ask "
             "the user. If you believe this deny is wrong, stop and tell the user what you were about to run.")
REVIEW_GATE_LOG = re.compile(r">[ \t]*/tmp/review-gate\.log")


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


def touch_after(path, other):
    """Touch `path` so that it is strictly newer than `other`, even when the file system clock is coarse."""
    touch(path)
    try:
        floor = os.stat(other).st_mtime_ns + 1
    except OSError:
        return
    if os.stat(path).st_mtime_ns < floor:
        os.utime(path, ns=(floor, floor))


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


GIT_TIMEOUT_SECONDS = 5


def git_output(args):
    try:
        finished = subprocess.run(["git"] + args, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  timeout=GIT_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return None
    return finished.stdout if finished.returncode == 0 else None


def tree_fingerprint(cwd):
    """A hash of HEAD, the diff against HEAD and the untracked file list: it changes when git (merge, pull,
    checkout, reset, rebase, apply...) or any shell write changes the tree. None when cwd is not a repo or git fails."""
    top = git_output(["-C", cwd, "rev-parse", "--show-toplevel"])
    if top is None:
        return None
    top = os.fsdecode(top).rstrip("\n")
    head = git_output(["-C", top, "rev-parse", "--verify", "-q", "HEAD"])
    if head is None:
        head = b"unborn"
        diff = git_output(["-C", top, "diff"])
        staged = git_output(["-C", top, "diff", "--cached"])
        diff = None if diff is None or staged is None else diff + staged
    else:
        diff = git_output(["-C", top, "diff", "HEAD"])
    untracked = git_output(["-C", top, "ls-files", "-o", "--exclude-standard"])
    if diff is None or untracked is None:
        return None
    digest = hashlib.sha256()
    for part in (head, diff, untracked):
        digest.update(hashlib.sha256(part).digest())
    return digest.hexdigest()


def recorded_fingerprint(run_file):
    try:
        with open(run_file) as handle:
            return handle.read().strip()
    except OSError:
        return ""


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


def tree_changed_since_run(cwd, run_file):
    """True when the run recorded a tree fingerprint and the tree now differs from it, or git cannot say."""
    recorded = recorded_fingerprint(run_file)
    if not recorded:
        return False
    return tree_fingerprint(cwd) != recorded


def normalize(segment):
    segment = re.sub(r"[0-9]*>&[0-9]+", "", segment)
    segment = re.sub("[0-9]*>>?" + WS + "*[^" + SP + "]+", "", segment)
    segment = re.sub(WS + "+", " ", segment)
    segment = re.sub("^ ", "", segment)
    segment = re.sub(" $", "", segment)
    while segment.endswith(")") and segment.count(")") > segment.count("("):
        segment = segment[:-1].rstrip(" ")
    return segment


def writes_files(segment):
    """True when the segment is a formatter or fixer that rewrites files."""
    if not FORMATTER_START.search(segment):
        return False
    if FORMATTER_READS_ONLY.search(segment):
        return False
    return bool(FORMATTER_WRITES.search(segment) or FORMATTER_WRITES_BY_DEFAULT.search(segment))


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
    if event == "PreToolUse" and field(root_json, "agent_type") == "review-loop" and REVIEW_GATE_LOG.search(command):
        return
    command = command.replace("#skip-quality-cap", "")

    steps = split_command_steps(command)
    succeeded = event == "PostToolUse"
    checks = []
    format_index = None
    for index, (_, segment) in enumerate(steps):
        segment = re.sub("^" + WS + "+", "", segment)
        segment = re.sub(WS + "+$", "", segment)
        moved = CD_SEGMENT.match(segment)
        if moved:
            target = moved.group(1)
            if target.startswith("~"):
                target = home + target[1:]
            cwd = target if target.startswith("/") else cwd + "/" + target
            continue
        segment = re.sub(r"^[({ \t]+", "", segment)
        while True:
            stripped = ASSIGNMENT.sub("", WRAPPER.sub("", segment, count=1), count=1)
            if stripped == segment:
                break
            segment = stripped
        if writes_files(segment):
            if format_index is None:
                format_index = index
            continue
        if not CHECK_START.search(segment):
            continue

        norm = normalize(segment)
        key = str(cksum((norm + "\n" + cwd).encode("utf-8", "surrogateescape")))
        run_file = state_dir + "/run-" + key
        checks.append((index, norm, run_file, cwd))

    if event in ("PostToolUse", "PostToolUseFailure"):
        if format_index is not None:
            try:
                touch(state_dir + "/edits")
            except OSError:
                pass
        for index, _, run_file, check_cwd in checks:
            if not step_surely_ran(steps, index, succeeded):
                continue
            try:
                with open(run_file, "w") as handle:
                    handle.write(tree_fingerprint(check_cwd) or "")
                touch_after(run_file, state_dir + "/edits")
            except OSError:
                raise Exit(0)
        return

    if format_index is not None and all(index > format_index for index, _, _, _ in checks):
        return
    for _, norm, run_file, check_cwd in checks:
        if newer(run_file, state_dir + "/edits"):
            if not changed_since_run(check_cwd, run_file) and not tree_changed_since_run(check_cwd, run_file):
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
