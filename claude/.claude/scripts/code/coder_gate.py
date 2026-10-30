"""Hand-back gate for coder subagents. Run set and clear from inside the repo.

  coder_gate.py set [--env NAME=value]... [--run RUN_ID --dispatch DISPATCH_ID] <command>...
                                  store the check commands the gate runs, each one shell command from the repo root,
                                  and the variables each one runs with. --run and --dispatch name the /code run and
                                  the coder dispatch the gate is for: the hook gates only a coder launched for that
                                  dispatch. A gate set with neither gates any coder.
  coder_gate.py summary           print each coder's last gate result
  coder_gate.py clear             print each coder's last gate result, then delete the gate
  coder_gate.py hook              PreToolUse hook on SubagentHandback
  coder_gate.py bash-hook         PreToolUse hook on Bash: refuses a coder's whole-package check

A command may hold {files}, or {files:.ts,.tsx} to keep only those suffixes, and {tests} or {tests:.ts,.tsx} to keep
only test-named files; {jest-tests} also keeps the script files under __tests__/, which jest runs. At every hand-back
the gate fills it with the files the coder changed: tracked changes against HEAD plus untracked files, relative to the
directory of a leading `cd <dir> &&`, else the repo root. A command whose list is empty is skipped, never passed or
failed.

set and bash-hook refuse a command that runs a whole test suite, lints a whole package or runs a build, also when
a make target or a docker exec or run call runs it (make is read from the Makefile text; a NAME=value argument, a
missing Makefile or a missing target lets the call through, and make -n, -q, -t or -h runs no recipe line except one
marked `+` or one that names `$(MAKE)`, which is not judged). The gate runs at every hand-back and a coder runs its
checks after every edit, and the review loop runs the full check command once, at its end.

The hook runs the stored commands when a coder calls SubagentHandback. If any command fails, it refuses the call
and returns the output tail of each failed command to the coder, at most 3 times per coder. A command that hits the
timeout (1200 s) gave no test result: it is stored as timed_out, apart from failed, and never denies the call. A run
with no failures and a timed-out command has the result "timeout". On a pass, a timeout or the cap, it appends the
gate result to the hand-back message, so the caller reads the report as final. The stamp names each timed-out command
with the last 600 characters of its output, and says that the gate got no result from it: the command is too broad,
or a test hangs. The whole run has a time budget (GATE_BUDGET_SECONDS) under the hook's own timeout, so a slow run
still ends with a verdict: a command gets at most the budget left, and one that cannot start in what is left is stored
as not-started, apart from failed, and never denies the call (a run with no failure, command error or setup fault then
has the result "timeout"). A failure that shows the environment cannot run the check (exit 126 or 127, a runner that
cannot start the program, no package manifest where it ran, a run that found no test to run, a `manage.py test` run
that exits 0 after running none, a package-manager or engine version mismatch, a missing module from outside the repo
with no failed test, or, under pytest, a Django settings error with no failed test unless the coder changed a settings
module or an app config) is a setup fault: it never denies the call or counts toward the cap, a run with only setup
faults has the result "setup-fault", and the stamp names each one with its output tail. A denial lists the failing
tests above the output tail. With no gate, a gate older than 6 hours, another agent type, or a keyed gate that the
coder was not launched for (another run, another dispatch, or no launch on record), the hand-back goes through
untouched. Parallel coders take turns.
A failure whose output names a path that does not exist where the command ran (pytest's `file or directory not
found`, python's `can't open file`, a shell or `cd` error) is a command error: the command is wrong, not the code. It
never denies the call or counts toward the cap, a run whose only failures are command errors has the result
"command-error", and the stamp names each one with its missing-path line."""
import fcntl
import json
import os
import pathlib
import re
import shlex
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / folder) for folder in ("lib", "telemetry")]
import script_utils
from check_output import (
    failing_test_lines,
    failing_test_quote,
    is_django_settings_fault,
    is_setup_fault,
    missing_path,
    tail_with_failing_tests,
)
from check_scope import scanned_command
from source_paths import is_runnable_test_file

MAX_DENIES = 3
# A backstop only: a keyed gate is cleared at its coder's hand-back (unless the run stops to resume that coder), at
# abort, and at the next start, and a gate that a crashed run left behind is never gated to a live coder because its
# key matches no launch. The age stops an unkeyed gate (set by hand) from outliving a working day.
MAX_GATE_AGE_SECONDS = 6 * 3600
COMMAND_TIMEOUT_SECONDS = 1200
# The timeout of the SubagentHandback hook that runs the gate (settings.json). Claude Code kills the hook at it and the
# hand-back then passes with no verdict.
HOOK_TIMEOUT_SECONDS = 3600
# The whole gate run's budget, counted from the hook's entry: the hook timeout less 10 minutes for the git calls, the
# output sort and the state write, so the hook finishes on its own. The age and key check run before the lock and the
# lock wait comes off the budget.
GATE_BUDGET_SECONDS = HOOK_TIMEOUT_SECONDS - 600
# A command is not started with less budget left than this: it could not give a result.
MIN_COMMAND_SECONDS = 60
TAIL_CHARS = 6000
TIMEOUT_TAIL_CHARS = 600
GATE_LOG = pathlib.Path.home() / ".claude/coder-gate.jsonl"
# The gate's state file, kept in the repo's git dir.
CODER_GATE_FILE = "coder-gate.json"

WHOLE_PACKAGE_REASON = ("This command runs a whole test suite, lints a whole package or runs a build. Run the "
                        "typecheck, and lint and tests for only the files you changed. The review loop runs the full "
                        "check once, at its end.")
FILES_PLACEHOLDER = re.compile(r"\{(files|tests|jest-tests)(?::([^{}]*))?\}")
# manage.py test exits 0 when its labels hold no Django tests, as pytest-style tests do: that run gave no test result.
DJANGO_TEST_COMMAND = re.compile(r"\bmanage\.py\s+test\b")
DJANGO_RAN_NO_TESTS = re.compile(r"^Ran 0 tests\b", re.MULTILINE)
# What a command did at the gate. A coder's stored "commands" map holds {command: {"outcome": ..., "detail": ...}} for
# each command that did not pass: the detail is the output tail of a timeout or setup fault, the missing-path line of a
# command error, else "".
FAILED = "failed"
TIMED_OUT = "timed-out"
SETUP_FAULT = "setup-fault"
COMMAND_ERROR = "command-error"
SKIPPED = "skipped"
# The gate's time budget ran out before the command could start: it gave no test result, as a timeout gives none.
NOT_STARTED = "not-started"
NOT_STARTED_DETAIL = "the gate's time budget was used up before this command could start"
# The outcome of a whole gate run, in the result vocabulary the coder stores.
RESULT_FAILED = "failed"
RESULT_COMMAND_ERROR = "command-error"
RESULT_SETUP_FAULT = "setup-fault"
RESULT_TIMEOUT = "timeout"
RESULT_PASS = "pass"
# The command outcomes that clear prints after a coder's result, each with its label, in print order.
CLEAR_COMMAND_OUTCOMES = ((FAILED, "failed"), (TIMED_OUT, "timed out (no test result)"),
                          (SETUP_FAULT, "setup fault (no test result)"),
                          (COMMAND_ERROR, "command error (missing path)"),
                          (NOT_STARTED, "not started (time budget used up)"), (SKIPPED, "skipped"))
# The stamp section of each kind of command that gave no test result: (outcome, heading, closing advice, line format
# of one command). The heading fills {budget_seconds}; a line fills {command}, {detail} and, for a timeout,
# {timeout_seconds}, the timeout that command got.
NO_RESULT_STAMP_SECTIONS = (
    (TIMED_OUT,
     "\nHAND-BACK GATE TIMEOUT: these commands timed out with no test result:",
     "\nThe gate got no result from these commands; they are not among the failures. The command is too broad for the "
     "gate, or a test hangs. Read the output tail for a failure printed before the hang.",
     "\n  `{command}`, timed out after {timeout_seconds} s, output tail:\n{detail}"),
    (SETUP_FAULT,
     "\nHAND-BACK GATE SETUP FAULT: these commands could not run the checks in this environment:",
     "\nThe gate got no test result from these commands; they are not among the failures. The command misses the "
     "repo's test runner or virtualenv, or a dependency is not installed, or no package manifest is where it ran, or "
     "it ran no test, or the package-manager or engine version does not match. Run the repo's own test command for "
     "these files.",
     "\n  `{command}`, output tail:\n{detail}"),
    (COMMAND_ERROR,
     "\nHAND-BACK GATE COMMAND ERROR: these commands name a path that does not exist where they ran:",
     "\nThe gate got no test result from these commands; they are not among the failures and spent no denial. The gate "
     "command is wrong, not the code. Run the repo's own test command for these files.",
     "\n  `{command}`: {detail}"),
    (NOT_STARTED,
     "\nHAND-BACK GATE TIME BUDGET: the gate ran out of its {budget_seconds} s budget, so these commands were not "
     "started:",
     "\nThe gate got no test result from these commands; they are not among the failures. The commands before them "
     "were too slow. Run the repo's own test command for these files.",
     "\n  `{command}`"),
)


def gate_path(cwd):
    return script_utils.git_path(cwd, CODER_GATE_FILE)


def whole_recipe_lines(scan):
    # One line for each make recipe command that runs a whole suite: the make call, the recipe command and its target.
    return [f"`{make_call}` runs `{recipe_command}` in target `{target}`."
            for make_call, target, recipe_command in dict.fromkeys(scan.whole_recipes)]


def whole_package_reason(command, cwd):
    # The refusal text for a command that runs a whole suite, else None.
    scan = scanned_command(command, cwd)
    if not scan.runs_whole():
        return None

    recipe_lines = whole_recipe_lines(scan)
    if not recipe_lines:
        return WHOLE_PACKAGE_REASON
    return "\n".join([WHOLE_PACKAGE_REASON, *recipe_lines,
                      "Run the targeted command from the recipe directly on the changed files."])


def set_gate(commands, gate_assignments=(), run_id=None, dispatch_id=None):
    if (run_id is None) != (dispatch_id is None):
        sys.exit("coder-gate: --run and --dispatch go together")

    gate_file = gate_path(".")
    if gate_file is None:
        sys.exit("coder-gate: not inside a git repo")
    if not commands:
        sys.exit("coder-gate: set needs at least one command")

    # The gate runs each command from the repo root, so the commands are judged from there.
    repo_root = script_utils.git_output(".", "rev-parse", "--show-toplevel")
    if repo_root is None:
        sys.exit("coder-gate: set must run inside a git work tree")
    refused_lines = []
    for command in commands:
        scan = scanned_command(command, repo_root)
        if not scan.runs_whole():
            continue

        refused_lines.append(f"  {command}")
        refused_lines.extend(f"    {recipe_line}" for recipe_line in whole_recipe_lines(scan))
    if refused_lines:
        sys.exit("coder-gate: refused. These commands run a whole test suite, lint a whole package or run a build:\n"
                 + "\n".join(refused_lines) + "\nName the test files, test names or lint paths that the phase "
                 "changes, or use {files} or {tests}. The review loop runs the full check command once, at its end.")

    try:
        environment = script_utils.environment_from_assignments(gate_assignments)
    except ValueError as error:
        sys.exit(f"coder-gate: --env {error}")
    gate = {"repoRoot": repo_root, "commands": commands, "env": environment, "setAt": time.time(), "coders": {},
            "runId": run_id, "dispatchId": dispatch_id}
    script_utils.write_text_atomically(gate_file, json.dumps(gate, indent=1))
    print(f"coder gate set: {len(commands)} command(s)")


def joined_commands(coder, outcome):
    # The coder's commands with this outcome as one comma-separated text, "none" when it has none. A coder stored
    # before the commands map existed has no commands.
    return ", ".join(script_utils.details_with_outcome(coder.get("commands", {}), outcome)) or "none"


def print_gate_summary():
    # Prints each coder's last result and returns True, or prints "none set" and returns False.
    gate_file = gate_path(".")
    if gate_file is None or not gate_file.exists():
        print("coder gate: none set")
        return False

    gate = json.loads(gate_file.read_text())
    for coder in gate["coders"].values():
        command_lists = ", ".join(f"{label}: {joined_commands(coder, outcome)}"
                                  for outcome, label in CLEAR_COMMAND_OUTCOMES)
        print(f"coder gate: {coder['result']} after {coder['runs']} run(s), {command_lists}")
    if not gate["coders"]:
        print("coder gate: never ran, no coder handed back through it")
    return True


def clear_gate():
    if not print_gate_summary():
        return

    gate_file = gate_path(".")
    gate_file.unlink()
    gate_file.with_suffix(".lock").unlink(missing_ok=True)


def command_directory(command, repo_root):
    # A leading `cd <dir> &&` or `cd <dir> ;` sets the directory that {files} or {tests} is relative to.
    try:
        words = shlex.split(command)
    except ValueError:
        return repo_root
    if len(words) >= 3 and words[0] == "cd" and words[2] in ("&&", ";"):
        return str((pathlib.Path(repo_root) / words[1]).resolve())
    return repo_root


def changed_files(directory):
    # Tracked changes against HEAD, deletions excluded, plus untracked files, all relative to directory.
    tracked_files = script_utils.git_output(directory, "diff", "--name-only", "--relative", "--diff-filter=d",
                                            "HEAD") or ""
    untracked_files = script_utils.git_output(directory, "ls-files", "--others", "--exclude-standard") or ""
    names = [name for name in (tracked_files + "\n" + untracked_files).split("\n") if name]
    return sorted(set(names))


def fill_files(command, repo_root):
    # Returns the command with each {files}, {tests} or {jest-tests} filled, or None when a placeholder keeps no file.
    if not FILES_PLACEHOLDER.search(command):
        return command

    directory = command_directory(command, repo_root)
    changed_file_list = changed_files(directory)

    filled_command = command
    for match in FILES_PLACEHOLDER.finditer(command):
        keeps_only_tests = match.group(1) != "files"
        counts_jest_tests_folder = match.group(1) == "jest-tests"
        suffixes = tuple(suffix for suffix in (match.group(2) or "").split(",") if suffix)
        kept_files = [name for name in changed_file_list
                      if (not suffixes or name.endswith(suffixes))
                      and (not keeps_only_tests or is_runnable_test_file(name, counts_jest_tests_folder))]
        if not kept_files:
            return None
        quoted_files = " ".join(shlex.quote(name) for name in kept_files)
        filled_command = filled_command.replace(match.group(0), quoted_files, 1)
    return filled_command


def run_commands(gate, budget_seconds=None):
    # (failures, skipped, timed_out, not_started). A command that hit the timeout gave no test result, so timed_out
    # holds (command, output so far, the timeout it got), never failures. With a budget, each command gets at most the
    # budget left, and a command that cannot start with MIN_COMMAND_SECONDS left is in not_started: no command runs
    # past the budget.
    failures = []
    skipped = []
    timed_out = []
    not_started = []
    environment = {**os.environ, **gate.get("env", {})}
    started = time.monotonic()
    for command in gate["commands"]:
        filled_command = fill_files(command, gate["repoRoot"])
        if filled_command is None:
            skipped.append(command)
            continue

        command_timeout = COMMAND_TIMEOUT_SECONDS
        if budget_seconds is not None:
            seconds_left = budget_seconds - (time.monotonic() - started)
            if seconds_left < MIN_COMMAND_SECONDS:
                not_started.append(command)
                continue
            command_timeout = min(COMMAND_TIMEOUT_SECONDS, seconds_left)

        code, stdout, stderr = script_utils.run_process(filled_command, gate["repoRoot"], env=environment,
                                                        timeout=command_timeout)
        if code is None:
            timed_out.append((command, stdout + stderr, command_timeout))
            continue
        if code != 0:
            failures.append((command, f"exit {code}", stdout + stderr))
            continue

        if DJANGO_TEST_COMMAND.search(command) and DJANGO_RAN_NO_TESTS.search(stdout + stderr):
            failures.append((command, "exit 0", stdout + stderr))
    return failures, skipped, timed_out, not_started


def missing_path_line(command, output, repo_root):
    # The output line that names a path missing from the work tree where the command ran, else None.
    missing = missing_path(output.splitlines())
    if missing is None:
        return None

    line, path = missing
    directory = pathlib.Path(command_directory(command, repo_root))
    if (directory / path).exists():
        return None
    return line


def sort_failures(failures, repo_root):
    # (real failures, setup faults, command errors). A command error names a path that does not exist: the command
    # is wrong, not the code.
    real_failures = []
    setup_faults = []
    command_errors = []
    changed_file_list = changed_files(repo_root) if failures else []
    for command, outcome, output in failures:
        code = int(outcome.removeprefix("exit "))
        error_line = missing_path_line(command, output, repo_root)
        if error_line:
            command_errors.append((command, error_line))
        elif is_setup_fault(code, output, repo_root) or is_django_settings_fault(command, output, changed_file_list):
            setup_faults.append((command, output))
        else:
            real_failures.append((command, outcome, output))
    return real_failures, setup_faults, command_errors


def gate_outcome(real_failures, command_errors, setup_faults, timed_out, not_started=()):
    # The one outcome of a gate run, worst first. A command error ranks above a setup fault: the command names a path
    # that does not exist, so the command is wrong whatever the environment is, and the fix is to correct the command.
    # A command that fails and also shows a setup fault was already sorted as a command error by sort_failures.
    if real_failures:
        return RESULT_FAILED
    if command_errors:
        return RESULT_COMMAND_ERROR
    if setup_faults:
        return RESULT_SETUP_FAULT
    if timed_out or not_started:
        return RESULT_TIMEOUT
    return RESULT_PASS


def command_outcomes(real_failures, command_errors, setup_faults, timed_out, skipped, not_started=()):
    # The coder's {command: {"outcome": ..., "detail": ...}} map for every command that did not pass.
    outcomes = {}
    for command, _outcome, _output in real_failures:
        outcomes[command] = {"outcome": FAILED, "detail": ""}
    for command, output, command_timeout in timed_out:
        outcomes[command] = {"outcome": TIMED_OUT, "detail": output[-TIMEOUT_TAIL_CHARS:],
                             "timeout_seconds": round(command_timeout)}
    for command, output in setup_faults:
        outcomes[command] = {"outcome": SETUP_FAULT, "detail": output[-TIMEOUT_TAIL_CHARS:]}
    for command, missing_line in command_errors:
        outcomes[command] = {"outcome": COMMAND_ERROR, "detail": missing_line}
    for command in not_started:
        outcomes[command] = {"outcome": NOT_STARTED, "detail": NOT_STARTED_DETAIL}
    for command in skipped:
        outcomes[command] = {"outcome": SKIPPED, "detail": ""}
    return outcomes


def run_scoped_tests(repo_root, commands, gate_env, log_path):
    # (one-line result, the failing commands' tails). The scoped commands, run as the gate runs them, outside a hook.
    # A failing or timed-out command's whole output goes to log_path, and a failed, setup-fault, command-error or
    # timeout result names it.
    if not commands:
        return "not run (no scoped test commands)", []

    gate = {"commands": commands, "repoRoot": repo_root,
            "env": script_utils.environment_from_assignments(gate_env)}
    # No hook timeout bounds this run, so it takes no budget and starts every command.
    failures, skipped, timed_out, _not_started = run_commands(gate)
    if failures or timed_out:
        timed_out_outputs = [(command, "timeout", output) for command, output, _timeout in timed_out]
        script_utils.write_command_outputs(log_path, failures + timed_out_outputs)
    log_note = f"; full output: {log_path}"
    failures, setup_faults, command_errors = sort_failures(failures, repo_root)

    outcome = gate_outcome(failures, command_errors, setup_faults, timed_out)
    if outcome == RESULT_FAILED:
        return scoped_test_failure(failures, log_path)
    if outcome == RESULT_COMMAND_ERROR:
        command_error_text = "; ".join(f"{command} ({line})" for command, line in command_errors)
        return "command error: " + command_error_text + log_note, []
    if outcome == RESULT_SETUP_FAULT:
        return "setup fault: " + "; ".join(command for command, _output in setup_faults) + log_note, []
    if outcome == RESULT_TIMEOUT:
        return "not run (timeout): " + "; ".join(command for command, _output, _timeout in timed_out) + log_note, []
    if len(skipped) == len(commands):
        return "not run (no changed file matches)", []
    return "passed", []


def scoped_test_failure(failures, log_path):
    # (one-line result, tails) for real scoped-test failures: the result names the commands, each failing test and the
    # log; each tail quotes the failing tests' error text, or the output tail when a test has none.
    tails = []
    failing_tests = []
    for command, outcome, output in failures:
        quote = failing_test_quote(output, output[-TAIL_CHARS:])
        tails.append(f"`{command}` ({outcome}):\n{quote}\nFull output: {log_path}")
        failing_tests += failing_test_lines(output)

    result = "failed: " + "; ".join(command for command, _outcome, _output in failures)
    if failing_tests:
        result += "; failing tests: " + " | ".join(failing_tests)
    return f"{result}; full output: {log_path}", tails


def denial(failures):
    chunks = []
    for command, outcome, output in failures:
        tail = tail_with_failing_tests(output, output[-TAIL_CHARS:])
        chunks.append(f"=== `{command}` failed ({outcome}), output tail ===\n{tail}")
    failure_text = "\n\n".join(chunks)
    reason = ("The hand-back gate ran the phase's checks and they failed.\n\n" + failure_text
              + "\n\nFix these. Do not run the checks yourself. Then call SubagentHandback again.")
    return reason


def stamped_handback(tool_input, coder):
    # The coder writes its report before the gate runs, so the report can still say that a re-run is pending.
    stamp = (f"{script_utils.HAND_BACK_GATE_MARKER} {coder['result']} after {coder['runs']} run(s), "
             f"failed: {joined_commands(coder, FAILED)}, "
             f"skipped (no changed files): {joined_commands(coder, SKIPPED)}. "
             "The gate ran after this report was written. The report is final.")
    stored_commands = coder.get("commands", {})
    for outcome, heading, advice, line_format in NO_RESULT_STAMP_SECTIONS:
        no_result = script_utils.details_with_outcome(stored_commands, outcome)
        if not no_result:
            continue

        lines = ""
        for command, detail in no_result.items():
            command_timeout = stored_commands[command].get("timeout_seconds")
            lines += line_format.format(command=command, detail=detail, timeout_seconds=command_timeout)
        stamp += heading.format(budget_seconds=GATE_BUDGET_SECONDS) + lines + advice
    stamped_input = dict(tool_input)
    stamped_input["message"] = str(tool_input.get("message", "")) + stamp
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                   "updatedInput": stamped_input}}


def append_gate_log(row):
    if not script_utils.telemetry_switch_on():
        return

    script_utils.append_jsonl(GATE_LOG, row)


def log_gate_run(gate, coder, seconds, failed_count, timed_out_count, setup_fault_count, not_started_count):
    repo_name = pathlib.Path(gate["repoRoot"]).name
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repo": repo_name, "result": coder["result"],
           "run": coder["runs"], "seconds": seconds, "failed": failed_count, "timed_out": timed_out_count,
           "setup_faults": setup_fault_count, "not_started": not_started_count}
    append_gate_log(row)


def is_gated_coder(gate, event):
    # Fail-open: a keyed gate whose key does not match this coder (another run, another dispatch, or no launch on record
    # for its agent id) never gates it. The commands were derived for the dispatch the gate names; run against another
    # coder they deny it for failures it cannot fix, and its edits would be judged by a plan phase it does not work on.
    # A lost check is caught by the review loop's own scoped and full checks. A gate with no key was set by hand and
    # gates any coder.
    run_id = gate.get("runId")
    if run_id is None:
        return True

    import code_step_core  # Loaded here: only a keyed gate reads the event log, and the Bash hook must start fast.

    event_cwd = pathlib.Path(event.get("cwd") or ".")
    agent_id = event.get("agent_id")
    dispatch = code_step_core.launched_dispatch(event_cwd, run_id, agent_id)
    return dispatch is not None and dispatch == gate.get("dispatchId")


def run_hook():
    hook_started = time.monotonic()
    event = json.load(sys.stdin)
    if event.get("agent_type") != "coder":
        return

    gate_file = gate_path(event.get("cwd") or ".")
    if gate_file is None:
        return

    # The age and key check run before the lock, so a coder that the gate does not cover never waits on the lock. The
    # gate is read again under the lock: a coder that held it may have written its result.
    # Fail-open: a gate that does not exist, or that a clear removed since the path was built (clear takes no lock),
    # leaves nothing to run, so the hand-back goes through.
    try:
        checked_gate = json.loads(gate_file.read_text())
    except FileNotFoundError:
        return

    if time.time() - checked_gate["setAt"] > MAX_GATE_AGE_SECONDS or not is_gated_coder(checked_gate, event):
        return

    lock_path = gate_file.with_suffix(".lock")
    with lock_path.open("w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)

        # Fail-open: a gate cleared, or set again (new setAt, run or dispatch) during the lock wait, is not the gate
        # that was checked above, so the hand-back goes through.
        try:
            gate = json.loads(gate_file.read_text())
        except FileNotFoundError:
            return
        if (gate["setAt"] != checked_gate["setAt"] or gate.get("runId") != checked_gate.get("runId")
                or gate.get("dispatchId") != checked_gate.get("dispatchId")):
            return

        budget_seconds = GATE_BUDGET_SECONDS - (time.monotonic() - hook_started)
        started = time.time()
        failures, skipped, timed_out, not_started = run_commands(gate, budget_seconds)
        seconds = round(time.time() - started)

        failures, setup_faults, command_errors = sort_failures(failures, gate["repoRoot"])

        # Only the run and deny counts carry over; a coder stored in an older format loses its old command lists.
        agent_id = event.get("agent_id") or "unknown"
        earlier = gate["coders"].get(agent_id, {})
        coder = {"runs": earlier.get("runs", 0) + 1, "denies": earlier.get("denies", 0), "result": "none",
                 "commands": command_outcomes(failures, command_errors, setup_faults, timed_out, skipped,
                                              not_started)}
        outcome = gate_outcome(failures, command_errors, setup_faults, timed_out, not_started)
        if outcome != RESULT_FAILED:
            coder["result"] = outcome
        elif coder["denies"] >= MAX_DENIES:
            coder["result"] = "cap"
        else:
            coder["result"] = "deny"
            coder["denies"] += 1
        gate["coders"][agent_id] = coder
        script_utils.write_text_atomically(gate_file, json.dumps(gate, indent=1))

    log_gate_run(gate, coder, seconds, len(failures), len(timed_out), len(setup_faults), len(not_started))

    if coder["result"] == "deny":
        script_utils.pre_tool_use_deny(denial(failures))
        return

    tool_input = event.get("tool_input") or {}
    print(json.dumps(stamped_handback(tool_input, coder)))


def run_bash_hook():
    event = json.load(sys.stdin)
    if event.get("agent_type") != "coder":
        return

    command = str((event.get("tool_input") or {}).get("command", ""))
    cwd = event.get("cwd") or "."
    reason = whole_package_reason(command, cwd)
    if reason is None:
        return

    repo_name = pathlib.Path(cwd).name
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repo": repo_name, "result": "whole-package-deny"}
    append_gate_log(row)

    script_utils.pre_tool_use_deny(reason)


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    if verb == "set":
        set_arguments = sys.argv[2:]
        env_assignments = []
        key_flags = {}
        while len(set_arguments) >= 2 and set_arguments[0] in ("--env", "--run", "--dispatch"):
            if set_arguments[0] == "--env":
                env_assignments.append(set_arguments[1])
            else:
                key_flags[set_arguments[0]] = set_arguments[1]
            set_arguments = set_arguments[2:]
        if "--env" in set_arguments:
            sys.exit("coder-gate: --env needs NAME=value, got nothing after it")
        for key_flag in ("--run", "--dispatch"):
            if key_flag in set_arguments:
                if set_arguments[0] != key_flag:
                    sys.exit(f"coder-gate: {key_flag} goes before the command, got it after one")
                sys.exit(f"coder-gate: {key_flag} needs a value, got nothing after it")

        set_gate(set_arguments, env_assignments, key_flags.get("--run"), key_flags.get("--dispatch"))
    elif verb == "summary":
        print_gate_summary()
    elif verb == "clear":
        clear_gate()
    elif verb == "hook":
        run_hook()
    elif verb == "bash-hook":
        run_bash_hook()
    else:
        sys.exit("usage: coder_gate.py set [--env NAME=value]... [--run RUN_ID --dispatch DISPATCH_ID] <command>... "
                 "| summary | clear | hook | bash-hook")


if __name__ == "__main__":
    main()
