#!/usr/bin/env python3
"""Cap a quality check at one re-run per edit.

PostToolUse(Write|Edit|MultiEdit|NotebookEdit) touches `edits`; PreToolUse(Bash) denies a check whose last run is
newer than `edits`, unless a file in the repo was changed by means the Write/Edit hook never sees (shell
redirection, a script) more recently than that run, then it allows. PostToolUse(Bash) records the run;
PostToolUseFailure(Bash) does too, except when the run did not finish: an interrupt (`is_interrupt`) or an exit
status of 129 to 192 (128 + signal number: ended by a signal, such as a pkill or a timeout kill), so the rerun is
allowed. Exit 128 and 255 are ordinary failures (git and PHP fatal errors) and are recorded. A check is recorded only
when it surely ran: after a failure, a check behind `&&` or `||` may never have started, so it is not recorded; after
a success, a check behind `||` is not. A check whose output redirection the shell could not open (a redirect into a
missing folder, `> gone/x.log`) never started, so it is not recorded. A run record keeps
the run's start in a line, so an edit made while the check ran allows the rerun; the record's own time is the run's
end. A command with a formatter that rewrites files (`cargo fmt`, `prettier --write`, `ruff format`...) or a git
call that rewrites the tree (`git merge`, `checkout`, `reset`...) is never denied when every check in it runs only
after the formatter succeeded (joined to it by `&&`, pipes allowed), and resets the cap
like an edit; its checks are recorded with no start line. Key: normalized command + effective cwd (POSIX cksum) +
the agent that ran it: a run is capped only against an earlier run by the same agent, so a subagent's first run of a
check is always allowed. The agent is the hook input's `agent_id` (set only inside a subagent); the main thread has
none. Edits are shared by every agent of the session, because they change the tree all of them see. A `cargo test`
scoped to a named target (`--lib`, `--doc`, `--test <name>`, `--bin <name>`, a test-name filter) is never capped;
unscoped it is. A check step with `--help`, `-h`, `--version` or `-V` as a whole word runs nothing: never denied,
never recorded. A check in the body of a `for` loop (`for i in 1 2 3; do pytest x; done`) is never denied, so a flake
check can repeat with no edit between; it is still recorded, so a plain rerun after it is denied. A `while` or `until`
body, an `if`, a bare `true;` and a `for` over fewer than two values get no such exemption. A run whose output was
piped into `tail`, `head` or `grep` and not kept in a file (`>`, `&>`, `| tee <file>`) is recorded as cut: one rerun
with stdout sent to a file is then allowed, and the deny names that form without rebuilding the command. Escape: a
trailing `#skip-quality-cap`. Fails closed only on the PreToolUse Bash path; state errors fail open. State lives in
~/.claude/state/quality-check/<session>/.
"""
import collections
import contextlib
import hashlib
import json
import os
import re
import shlex
import sys
import time

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
import script_utils
from hook_input import EMPTY_INPUT, JqError, cksum, exit_code_in_error_text, jq_field, jq_get, truthy
from shell_command import (
    git_subcommand,
    parse_simple_commands,
    path_word,
    redirection_writes_file,
    runs_only_after_success,
    split_command_steps,
    step_surely_ran,
)
from shell_statements import strip_comments, strip_heredocs

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
# The git subcommands that rewrite the work tree.
GIT_TREE_REWRITE_SUBCOMMANDS = {"merge", "checkout", "switch", "reset", "pull", "rebase", "restore", "cherry-pick",
                                "revert", "am", "apply", "clean", "rm", "mv"}
CARGO_TEST = re.compile("^cargo test(" + WS + "|$)")
CARGO_TARGET_FLAGS = ("--test", "--bin", "--example", "--bench")
CARGO_WHOLE_TREE_FLAGS = ("--workspace", "--all", "--all-targets")
CARGO_VALUE_FLAGS = ("-p", "--package", "--features", "-F", "--target", "--manifest-path", "-j", "--jobs",
                     "--profile", "--color", "--target-dir", "--exclude", "--message-format", "--config", "-Z")
HELP_FLAGS = ("--help", "-h", "--version", "-V")
LOOP_HEADER = re.compile("^(for|while|until)" + WS)
LOOP_BODY_START = re.compile("^(do|then|else)(" + WS + "+|$)")
LOOP_END = re.compile("^done(" + WS + "|$)")
FOR_VALUES = re.compile("^for" + WS + r"+\w+" + WS + "+in" + WS + "+(.*)$", re.S)
SEQ_COUNT = re.compile(r"^\$\(seq" + WS + r"+(\d+)(?:" + WS + r"+(\d+))?" + WS + r"*\)$")
BRACE_RANGE = re.compile(r"^\{(\d+)\.\.(\d+)\}$")
CD_SEGMENT = re.compile("^cd" + WS + "+([^" + SP + "]+)$")
WRAPPER = re.compile("^(time|env|npx|bunx|pnpm exec|yarn dlx)" + WS + "+")
ASSIGNMENT = re.compile(r"^[^\W\d]\w*=[^" + SP + "]*" + WS + "+")
OUTPUT_FILTER_START = re.compile("^(tail|head|grep)(" + WS + "|$)")
TEE_TO_FILE = re.compile("^tee(" + WS + "+-a)?" + WS + "+[^-" + SP + "]")
# `>`, `>>`, `1>`, `&>` or `&>>` onto a file: stdout lands in it. `2>` and a descriptor copy (`>&2`) do not count.
STDOUT_TO_FILE = re.compile("(^|" + WS + ")[1&]?>>?" + WS + "*(?!/dev/null(" + WS + "|$))[^&|;<>" + SP + "]")
# The second line of a run record whose output went through tail, head or grep and was not kept in a file.
CUT_MARK = "cut"
DENY_TAIL = (" If it still fails after that batch fix, stop and ask the user. To repeat a check on purpose, run it in "
             "one loop over two or more values, `for i in 1 2 3; do <check>; done`. If you believe this deny is "
             "wrong, stop and tell the user what you were about to run.")
DENY_TEXT = ("' already ran this session and nothing has been edited since. Re-running unchanged code cannot "
             "produce a different result. Read that run's whole output, fix every failure in one batch, then run "
             "it once more with its output redirected to /tmp/check.log and read the WHOLE log." + DENY_TAIL)
CUT_DENY_TEXT = ("' already ran this session and nothing has been edited since, and that run's output went through "
                 "tail, head or grep. Run it once more with no tail, head or grep after it and its output sent to a "
                 "file, `<check> > /tmp/check.log 2>&1`, with any file list written out rather than built by a `$( )` "
                 "substitution. Read the WHOLE log, fix every failure in one batch, then run it once more." + DENY_TAIL)
CHAIN_DENY_TEXT = (" This call was denied as a whole because of that fragment alone: none of its other steps ran. "
                   "Send the other steps again without it, as their own call.")

UNRESOLVED_PATH = re.compile(r"[$`*?\[]")
# Written when the cap lets a check start; the run record then carries that start time in a line, so an edit made
# while it ran still counts as after it. The record's own time stays at the run's end.
START_SUFFIX = ".start"
START_PREFIX = "start "

CheckStep = collections.namedtuple(
    "CheckStep", "index norm run_file cwd in_repeat_loop output_saved output_cut redirect_files")


class DenyError(Exception):
    pass


class ExitError(Exception):
    def __init__(self, rc=0):
        Exception.__init__(self)
        self.rc = rc


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


def prune_old_state_tree(directory, now=None):
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
                prune_old_state_tree(path, now)
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


def run_record_lines(run_file):
    """The lines of a run record: the tree fingerprint, then CUT_MARK when that run's output was cut, then
    `start <ns>` when the cap marked the run's start."""
    try:
        with open(run_file) as handle:
            return handle.read().splitlines()
    except OSError:
        return []


def recorded_fingerprint(run_file):
    record_lines = run_record_lines(run_file)
    return record_lines[0].strip() if record_lines else ""


def recorded_output_was_cut(run_file):
    return CUT_MARK in run_record_lines(run_file)[1:]


def piped_step(steps, index):
    """The step that reads the output of the step at `index` through a pipe, stripped, or None."""
    if index + 1 >= len(steps) or steps[index + 1][0] != "|":
        return None
    return steps[index + 1][1].strip(SP)


def saves_output(steps, index, segment):
    """True when the check step sends its stdout to a file, by a redirection or through `| tee <file>`."""
    if STDOUT_TO_FILE.search(segment):
        return True
    reader = piped_step(steps, index)
    return reader is not None and TEE_TO_FILE.match(reader) is not None


def cuts_output(steps, index):
    """True when the check step's output goes into tail, head or grep."""
    reader = piped_step(steps, index)
    return reader is not None and OUTPUT_FILTER_START.match(reader) is not None


def redirect_files(segment, cwd):
    """The files the check step's output redirections write, as absolute paths. A target the hook cannot resolve (a
    variable, a glob, a substitution) and a /dev path are left out."""
    try:
        commands = parse_simple_commands(segment)
    except ValueError:
        return []

    files = []
    for _words, redirections in commands:
        for operator, target in redirections:
            if not redirection_writes_file(operator, target):
                continue
            if not target or UNRESOLVED_PATH.search(target) or target.startswith("/dev/"):
                continue

            expanded_target = path_word(target)
            path = os.path.normpath(os.path.join(cwd, expanded_target))
            files.append(path)
    return files


def redirect_failed(check):
    """True when the shell could not open an output redirection of the check: the folder the file goes into is
    missing. An output file the command itself deleted later is no failure."""
    return any(not os.path.isdir(os.path.dirname(path)) for path in check.redirect_files)


def mark_run_starts(checks):
    for check in checks:
        with contextlib.suppress(OSError):
            touch(check.run_file + START_SUFFIX)


def clear_run_starts(checks):
    """Drop the start marks, so a later Post does not date a run by a mark an earlier refused call left."""
    for check in checks:
        with contextlib.suppress(OSError):
            os.unlink(check.run_file + START_SUFFIX)


def take_run_start(run_file):
    """The start mark's time in ns, removing the mark; None when there is none."""
    start_file = run_file + START_SUFFIX
    try:
        start_ns = os.stat(start_file).st_mtime_ns
        os.unlink(start_file)
    except OSError:
        return None
    return start_ns


def run_started_ns(run_file):
    """When the recorded run started: the record's start line, else its own time."""
    for line in run_record_lines(run_file)[1:]:
        if line.startswith(START_PREFIX):
            with contextlib.suppress(ValueError):
                return int(line[len(START_PREFIX):])
    return os.stat(run_file).st_mtime_ns


def ran_since_last_edit(run_file, edits_file):
    """True when the recorded run started after the last edit. An edit made while the run went on is newer than its
    start, so it allows the rerun."""
    try:
        started = run_started_ns(run_file)
    except OSError:
        return False
    try:
        edited = os.stat(edits_file).st_mtime_ns
    except OSError:
        return True
    return started > edited


def record_runs(checks, steps, succeeded, state_dir, has_formatter):
    for check in checks:
        if not step_surely_ran(steps, check.index, succeeded):
            continue
        if redirect_failed(check):
            continue

        start_ns = take_run_start(check.run_file)
        record = [tree_fingerprint(check.cwd) or ""]
        if check.output_cut:
            record.append(CUT_MARK)
        if start_ns is not None and not has_formatter:
            record.append(START_PREFIX + str(start_ns))

        try:
            with open(check.run_file, "w") as handle:
                handle.write("\n".join(record))
            touch_after(check.run_file, state_dir + "/edits")
        except OSError:
            raise ExitError(0) from None


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
    """True when the segment is a formatter or fixer that rewrites files, or a git call that rewrites the tree."""
    words = segment.split()
    if words and words[0] == "git" and git_subcommand(words) in GIT_TREE_REWRITE_SUBCOMMANDS:
        return True
    if not FORMATTER_START.search(segment):
        return False
    if FORMATTER_READS_ONLY.search(segment):
        return False
    return bool(FORMATTER_WRITES.search(segment) or FORMATTER_WRITES_BY_DEFAULT.search(segment))


def is_scoped_cargo_test(segment):
    """True when a `cargo test` names its target: --lib, --doc, --test/--bin/--example/--bench <name>, or a test-name
    filter. A run over the whole workspace or with no scope is the full suite and stays capped."""
    if not CARGO_TEST.search(segment):
        return False
    try:
        words = shlex.split(segment)
    except ValueError:
        words = segment.split()
    words = words[2:]
    if "--" in words:
        words = words[:words.index("--")]
    if any(word in CARGO_WHOLE_TREE_FLAGS for word in words):
        return False
    skip_value = False
    for word in words:
        if skip_value:
            skip_value = False
            continue
        if word in ("--lib", "--doc") or word in CARGO_TARGET_FLAGS or word.split("=")[0] in CARGO_TARGET_FLAGS:
            return True
        if word in CARGO_VALUE_FLAGS:
            skip_value = True
            continue
        if not word.startswith("-"):
            return True
    return False


def is_help_probe(segment):
    """True when the check step asks for usage or the version (`--help`, `-h`, `--version`, `-V` as a whole word of
    this step) and so runs nothing."""
    try:
        words = shlex.split(segment)
    except ValueError:
        words = segment.split()
    return any(word in HELP_FLAGS for word in words)


def for_loop_repeats(header):
    """True when a `for` header runs its body at least twice: two or more listed values, `$(seq N)` or `{a..b}` with
    N or b - a + 1 at least 2. A one-value loop is a dodge, not a repeat."""
    values = FOR_VALUES.match(header)
    if not values:
        return False

    listed = values.group(1).strip()
    seq = SEQ_COUNT.match(listed)
    if seq:
        first = int(seq.group(1)) if seq.group(2) else 1
        last = int(seq.group(2) or seq.group(1))
        return last - first + 1 >= 2

    brace = BRACE_RANGE.match(listed)
    if brace:
        return abs(int(brace.group(2)) - int(brace.group(1))) + 1 >= 2

    return len(listed.split()) >= 2


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
        root_json = EMPTY_INPUT
    else:
        try:
            root_json = json.loads(raw)
            state["tool"] = jq_field(root_json, "tool_name")
        except (ValueError, JqError):
            raise ExitError(0) from None
    tool = state["tool"]
    event = jq_field(root_json, "hook_event_name")
    state["event"] = event
    session = jq_field(root_json, "session_id", default="unknown")
    cwd = jq_field(root_json, "cwd") or os.getcwd()
    agent_id = jq_field(root_json, "agent_id")

    home = os.environ["HOME"]
    root = home + "/.claude/state/quality-check"
    state_dir = state_dir_for(root, session)
    try:
        os.makedirs(state_dir, exist_ok=True)
    except OSError:
        raise ExitError(0) from None
    prune_old_state_tree(root)

    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        with contextlib.suppress(OSError):
            touch(state_dir + "/edits")
        return
    if tool != "Bash":
        return

    if event == "PostToolUseFailure":
        if truthy(jq_get(root_json, "is_interrupt")):
            return
        if exit_code_in_error_text(jq_field(root_json, "error")) in SIGNAL_EXIT_CODES:
            return

    command = jq_field(root_json, "tool_input", "command")
    if not command:
        return
    skipped = event == "PreToolUse" and "#skip-quality-cap" in command
    command = command.replace("#skip-quality-cap", "")

    steps = split_command_steps(strip_comments(strip_heredocs(command)))
    succeeded = event == "PostToolUse"
    checks = []
    format_indexes = []
    loop_kinds = []
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
        segment = LOOP_BODY_START.sub("", segment)
        if LOOP_HEADER.match(segment):
            loop_kinds.append("repeat" if for_loop_repeats(segment) else segment.split()[0])
        elif LOOP_END.match(segment):
            if loop_kinds:
                loop_kinds.pop()
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

        if is_help_probe(segment):
            continue

        if is_scoped_cargo_test(normalize(segment)):
            continue

        norm = normalize(segment)
        key = str(cksum((norm + "\n" + cwd).encode("utf-8", "surrogateescape")))
        run_file = run_file_for(state_dir, key, agent_id)
        in_repeat_loop = bool(loop_kinds) and loop_kinds[-1] == "repeat"
        output_saved = saves_output(steps, index, segment)
        output_cut = not output_saved and cuts_output(steps, index)
        checks.append(CheckStep(index, norm, run_file, cwd, in_repeat_loop, output_saved, output_cut,
                                redirect_files(segment, cwd)))

    if event in ("PostToolUse", "PostToolUseFailure"):
        if format_indexes:
            with contextlib.suppress(OSError):
                touch(state_dir + "/edits")
        record_runs(checks, steps, succeeded, state_dir, bool(format_indexes))
        return

    if skipped:
        clear_run_starts(checks)
        return

    if format_indexes:
        every_check_follows_a_formatter = all(follows_a_formatter(steps, format_indexes, check.index)
                                              for check in checks)
        if every_check_follows_a_formatter:
            clear_run_starts(checks)
            return

    is_real_chain = any(op in ("&&", "||", ";", "&") and step.strip() for op, step in steps[1:])
    chain_text = CHAIN_DENY_TEXT if is_real_chain else ""
    for check in checks:
        if check.in_repeat_loop:
            continue
        ran_after_last_edit = ran_since_last_edit(check.run_file, state_dir + "/edits")
        if (not ran_after_last_edit or changed_since_run(check.cwd, check.run_file)
                or tree_changed_since_run(check.cwd, check.run_file)):
            continue

        if not recorded_output_was_cut(check.run_file):
            raise DenyError("[quality-check-cap] '" + check.norm + DENY_TEXT + chain_text)
        if check.output_saved:
            continue
        raise DenyError("[quality-check-cap] '" + check.norm + CUT_DENY_TEXT + chain_text)

    mark_run_starts(checks)


def main():
    if os.environ.get("CLAUDE_SKIP_HOOKS"):
        return 0
    state = {"tool": "", "event": ""}
    internal = None
    try:
        run(sys.stdin.buffer.read().decode("utf-8", "replace"), state)
    except DenyError as denied:
        hook_input.emit_decision("deny", str(denied))
    except ExitError as done:
        return done.rc
    except JqError as error:
        internal = error.rc
    except Exception:
        internal = 1
    if internal is None:
        return 0
    if state["tool"] == "Bash" and state["event"] == "PreToolUse":
        hook_input.emit_decision("deny", f"[quality-check-cap] internal error (exit {internal}) — failing closed. "
                                         "Report this to the user.")
        return 0
    return internal


if __name__ == "__main__":
    hook_input.run_gate(main)
