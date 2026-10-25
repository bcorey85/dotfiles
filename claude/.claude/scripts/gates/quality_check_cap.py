#!/usr/bin/env python3
"""Cap a quality check at one re-run per edit.

PostToolUse(Write|Edit|MultiEdit|NotebookEdit) touches `edits`; PreToolUse(Bash) denies a check whose last run is
newer than `edits`, unless a file in the repo was changed by means the Write/Edit hook never sees (shell
redirection, a script) more recently than that run, then it allows. PostToolUse(Bash) records the run;
PostToolUseFailure(Bash) does too, except when the run did not finish: an interrupt (`is_interrupt`) or an exit
status of 129 to 192 (128 + signal number: ended by a signal, such as a pkill or a timeout kill), so the rerun is
allowed. Exit 128 and 255 are ordinary failures (git and PHP fatal errors) and are recorded. A check is recorded only
when it
surely ran: after a failure, a check behind `&&` or `||` may never have started, so it is not recorded; after
a success, a check behind `||` is not. A command with a formatter that rewrites files (`cargo fmt`, `prettier
--write`, `ruff format`...) is never denied when every check in it runs only after the formatter succeeded (joined
to it by `&&`, pipes allowed), and resets the cap like an edit. Key: normalized command + effective cwd (POSIX cksum)
+ the agent
that ran it: a run is capped only against an earlier run by the same agent, so a subagent's first run of a check is
always allowed. The agent is the hook input's `agent_id` (set only inside a subagent); the main thread has none.
Edits are shared by every agent of the session, because they change the tree all of them see. Escape: a trailing
`#skip-quality-cap`. Fails closed only on the PreToolUse Bash path; state errors fail open. State lives in
~/.claude/state/quality-check/<session>/.
"""
import contextlib
import hashlib
import json
import os
import re
import sys
import time

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
from hook_input import JqError, cksum, exit_code_in_error_text, jq_get, jq_str, truthy
from shell_command import runs_only_after_success, split_command_steps, step_surely_ran

SIGNAL_EXIT_CODES = range(129, 193)
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


class DenyError(Exception):
    pass


class ExitError(Exception):
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


def timed_git_output(cwd, *args):
    return script_utils.git_output(cwd, *args, timeout=GIT_TIMEOUT_SECONDS)


def tree_fingerprint(cwd):
    """A hash of HEAD, the diff against HEAD and the untracked file list: it changes when git (merge, pull,
    checkout, reset, rebase, apply...) or any shell write changes the tree. None when cwd is not a repo or git fails."""
    top = timed_git_output(cwd, "rev-parse", "--show-toplevel")
    if top is None:
        return None
    head = timed_git_output(top, "rev-parse", "--verify", "-q", "HEAD")
    if head is None:
        head = "unborn"
        diff = timed_git_output(top, "diff")
        staged = timed_git_output(top, "diff", "--cached")
        diff = None if diff is None or staged is None else diff + staged
    else:
        diff = timed_git_output(top, "diff", "HEAD")
    untracked = timed_git_output(top, "ls-files", "-o", "--exclude-standard")
    if diff is None or untracked is None:
        return None
    digest = hashlib.sha256()
    for part in (head, diff, untracked):
        part_bytes = os.fsencode(part)
        digest.update(hashlib.sha256(part_bytes).digest())
    return digest.hexdigest()


def recorded_fingerprint(run_file):
    try:
        with open(run_file) as handle:
            return handle.read().strip()
    except OSError:
        return ""


def changed_since_run(cwd, run_file):
    top = timed_git_output(cwd, "rev-parse", "--show-toplevel")
    if top is None:
        return False
    listing = timed_git_output(top, "ls-files", "-z", "--modified", "--others", "--exclude-standard")
    if not listing:
        return False
    return any(name and newer(top + "/" + name, run_file) for name in listing.split("\x00"))


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


def follows_a_formatter(steps, format_indexes, check_index):
    """True when some formatter step is one the check at `check_index` runs only after."""
    return any(runs_only_after_success(steps, format_index, check_index) for format_index in format_indexes)


def run_file_for(state_dir, key, agent_id):
    """The run record of one check. The main thread has no agent_id and keeps the bare name; an agent's name ends
    in a hash of its id, so no id can name a path."""
    if not agent_id:
        return state_dir + "/run-" + key
    agent_digest = hashlib.sha256(agent_id.encode("utf-8", "surrogateescape")).hexdigest()
    return state_dir + "/run-" + key + "-" + agent_digest[:16]


def run(raw, state):
    if raw.strip() == "":
        root_json = EMPTY
    else:
        try:
            root_json = json.loads(raw)
            state["tool"] = field(root_json, "tool_name")
        except (ValueError, JqError):
            raise ExitError(0) from None
    tool = state["tool"]
    event = field(root_json, "hook_event_name")
    state["event"] = event
    session = field(root_json, "session_id", default="unknown")
    cwd = field(root_json, "cwd") or os.getcwd()
    agent_id = field(root_json, "agent_id")

    home = os.environ["HOME"]
    root = home + "/.claude/state/quality-check"
    state_dir = state_dir_for(root, session)
    try:
        os.makedirs(state_dir, exist_ok=True)
    except OSError:
        raise ExitError(0) from None
    prune_old(root)

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        with contextlib.suppress(OSError):
            touch(state_dir + "/edits")
        return
    if tool != "Bash":
        return

    if event == "PostToolUseFailure":
        if truthy(jq_get(root_json, "is_interrupt")):
            return
        if exit_code_in_error_text(field(root_json, "error")) in SIGNAL_EXIT_CODES:
            return

    command = field(root_json, "tool_input", "command")
    if not command:
        return
    if event == "PreToolUse" and "#skip-quality-cap" in command:
        return
    command = command.replace("#skip-quality-cap", "")

    steps = split_command_steps(command)
    succeeded = event == "PostToolUse"
    checks = []
    format_indexes = []
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
            format_indexes.append(index)
            continue
        if not CHECK_START.search(segment):
            continue

        norm = normalize(segment)
        key = str(cksum((norm + "\n" + cwd).encode("utf-8", "surrogateescape")))
        run_file = run_file_for(state_dir, key, agent_id)
        checks.append((index, norm, run_file, cwd))

    if event in ("PostToolUse", "PostToolUseFailure"):
        if format_indexes:
            with contextlib.suppress(OSError):
                touch(state_dir + "/edits")
        for index, _, run_file, check_cwd in checks:
            if not step_surely_ran(steps, index, succeeded):
                continue
            try:
                with open(run_file, "w") as handle:
                    handle.write(tree_fingerprint(check_cwd) or "")
                touch_after(run_file, state_dir + "/edits")
            except OSError:
                raise ExitError(0) from None
        return

    if format_indexes:
        every_check_follows_a_formatter = all(follows_a_formatter(steps, format_indexes, check_index)
                                              for check_index, _, _, _ in checks)
        if every_check_follows_a_formatter:
            return
    for _, norm, run_file, check_cwd in checks:
        edited_since_run = newer(run_file, state_dir + "/edits")
        if (edited_since_run and not changed_since_run(check_cwd, run_file)
                and not tree_changed_since_run(check_cwd, run_file)):
            raise DenyError("[quality-check-cap] '" + norm + DENY_TEXT)


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    state = {"tool": "", "event": ""}
    internal = None
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"), state)
    except DenyError as denied:
        emit_deny(str(denied))
    except ExitError as done:
        return done.rc
    except JqError as error:
        internal = error.rc
    except Exception:
        internal = 1
    if internal is None:
        return 0
    if state["tool"] == "Bash" and state["event"] == "PreToolUse":
        emit_deny(f"[quality-check-cap] internal error (exit {internal}) — failing closed. Report this to the "
                  f"user.")
        return 0
    return internal


if __name__ == "__main__":
    hook_input.run_gate(main)
