"""Hand-back gate for coder subagents. Run set and clear from inside the repo.

  coder_gate.py set [--env NAME=value]... <command>...
                                  store the check commands the gate runs, each one shell command from the repo root,
                                  and the variables each one runs with
  coder_gate.py clear             print each coder's last gate result, then delete the gate
  coder_gate.py hook              PreToolUse hook on SubagentHandback
  coder_gate.py bash-hook         PreToolUse hook on Bash: refuses a coder's whole-package check

A command may hold {files}, or {files:.ts,.tsx} to keep only those suffixes. At every hand-back the gate fills it
with the files the coder changed: tracked changes against HEAD plus untracked files, relative to the directory of a
leading `cd <dir> &&`, else the repo root. A command whose list is empty is skipped, never passed or failed.

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
or a test hangs. A failure that shows the environment cannot run the check (exit 126 or 127, a runner that cannot
start the program, no package manifest where it ran, a run that found no test to run, a `manage.py test` run that
exits 0 after running none, a package-manager or engine version mismatch, a missing module from outside the repo with
no failed test, or, under pytest, a Django settings error with no failed test unless the coder changed a settings
module or an app config) is a setup fault: it never denies the call or counts toward the cap, a run with only setup
faults has the result "setup-fault", and the
stamp names each one with its output tail. A denial lists the failing tests above the output tail. With no gate, a gate
older than 6 hours or another agent type, the hand-back goes through untouched. Parallel coders take turns.
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
from check_output import is_django_settings_fault, is_setup_fault, missing_path, tail_with_failing_tests
from check_scope import scanned_command

MAX_DENIES = 3
MAX_GATE_AGE_SECONDS = 6 * 3600
COMMAND_TIMEOUT_SECONDS = 1200
TAIL_CHARS = 6000
TIMEOUT_TAIL_CHARS = 600
GATE_LOG = pathlib.Path.home() / ".claude/coder-gate.jsonl"

WHOLE_PACKAGE_REASON = ("This command runs a whole test suite, lints a whole package or runs a build. Run the "
                        "typecheck, and lint and tests for only the files you changed. The review loop runs the full "
                        "check once, at its end.")
FILES_PLACEHOLDER = re.compile(r"\{files(?::([^{}]*))?\}")
# manage.py test exits 0 when its labels hold no Django tests, as pytest-style tests do: that run gave no test result.
DJANGO_TEST_COMMAND = re.compile(r"\bmanage\.py\s+test\b")
DJANGO_RAN_NO_TESTS = re.compile(r"^Ran 0 tests\b", re.MULTILINE)
# The coder's stored lists that clear prints after its result, each with its label, in print order.
CLEAR_COMMAND_LISTS = (("failed", "failed"), ("timed_out", "timed out (no test result)"),
                       ("setup_faults", "setup fault (no test result)"),
                       ("command_errors", "command error (missing path)"), ("skipped", "skipped"))
# The stamp section of each kind of command that gave no test result: (stored list of commands, stored detail of each
# command, heading, closing advice, line format of one command). The heading fills {timeout_seconds}. When a section's
# stored-list key is None, the detail keyed by command stands for the list: the section names those commands in the
# detail's order.
NO_RESULT_STAMP_SECTIONS = (
    ("timed_out", "timed_out_tails",
     "\nHAND-BACK GATE TIMEOUT: these commands timed out after {timeout_seconds} s with no test result:",
     "\nThe gate got no result from these commands; they are not among the failures. The command is too broad for the "
     "gate, or a test hangs. Read the output tail for a failure printed before the hang.",
     "\n  `{command}`, output tail:\n{detail}"),
    ("setup_faults", "setup_fault_tails",
     "\nHAND-BACK GATE SETUP FAULT: these commands could not run the checks in this environment:",
     "\nThe gate got no test result from these commands; they are not among the failures. The command misses the "
     "repo's test runner or virtualenv, or a dependency is not installed, or no package manifest is where it ran, or "
     "it ran no test, or the package-manager or engine version does not match. Run the repo's own test command for "
     "these files.",
     "\n  `{command}`, output tail:\n{detail}"),
    (None, "command_error_lines",
     "\nHAND-BACK GATE COMMAND ERROR: these commands name a path that does not exist where they ran:",
     "\nThe gate got no test result from these commands; they are not among the failures and spent no denial. The gate "
     "command is wrong, not the code. Run the repo's own test command for these files.",
     "\n  `{command}`: {detail}"),
)


def gate_path(cwd):
    git_path = script_utils.git_output(cwd, "rev-parse", "--path-format=absolute", "--git-path", "coder-gate.json")
    if git_path is None:
        return None
    return pathlib.Path(git_path)


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


def set_gate(commands, gate_assignments=()):
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
                 "changes, or use {files}. The review loop runs the full check command once, at its end.")

    try:
        environment = script_utils.environment_from_assignments(gate_assignments)
    except ValueError as error:
        sys.exit(f"coder-gate: --env {error}")
    gate = {"repoRoot": repo_root, "commands": commands, "env": environment, "setAt": time.time(), "coders": {}}
    script_utils.write_text_atomically(gate_file, json.dumps(gate, indent=1))
    print(f"coder gate set: {len(commands)} command(s)")


def joined_commands(coder, key):
    # The coder's stored list of commands as one comma-separated text, "none" when the list is empty or missing.
    return ", ".join(coder.get(key, [])) or "none"


def clear_gate():
    gate_file = gate_path(".")
    if gate_file is None or not gate_file.exists():
        print("coder gate: none set")
        return

    gate = json.loads(gate_file.read_text())
    for coder in gate["coders"].values():
        command_lists = ", ".join(f"{label}: {joined_commands(coder, key)}" for key, label in CLEAR_COMMAND_LISTS)
        print(f"coder gate: {coder['result']} after {coder['runs']} run(s), {command_lists}")
    if not gate["coders"]:
        print("coder gate: never ran, no coder handed back through it")

    gate_file.unlink()
    gate_file.with_suffix(".lock").unlink(missing_ok=True)


def command_directory(command, repo_root):
    # A leading `cd <dir> &&` or `cd <dir> ;` sets the directory that {files} is relative to.
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
    # Returns the command with each {files} filled, or None when a placeholder keeps no file.
    if not FILES_PLACEHOLDER.search(command):
        return command

    directory = command_directory(command, repo_root)
    changed_file_list = changed_files(directory)

    filled_command = command
    for match in FILES_PLACEHOLDER.finditer(command):
        suffixes = tuple(suffix for suffix in (match.group(1) or "").split(",") if suffix)
        kept_files = [name for name in changed_file_list if not suffixes or name.endswith(suffixes)]
        if not kept_files:
            return None
        quoted_files = " ".join(shlex.quote(name) for name in kept_files)
        filled_command = filled_command.replace(match.group(0), quoted_files, 1)
    return filled_command


def run_commands(gate):
    # A command that hit the timeout gave no test result, so timed_out holds (command, output so far), never failures.
    failures = []
    skipped = []
    timed_out = []
    environment = {**os.environ, **gate.get("env", {})}
    for command in gate["commands"]:
        filled_command = fill_files(command, gate["repoRoot"])
        if filled_command is None:
            skipped.append(command)
            continue

        code, stdout, stderr = script_utils.run_process(filled_command, gate["repoRoot"], env=environment,
                                                        timeout=COMMAND_TIMEOUT_SECONDS)
        if code is None:
            timed_out.append((command, stdout + stderr))
            continue
        if code != 0:
            failures.append((command, f"exit {code}", stdout + stderr))
            continue

        if DJANGO_TEST_COMMAND.search(command) and DJANGO_RAN_NO_TESTS.search(stdout + stderr):
            failures.append((command, "exit 0", stdout + stderr))
    return failures, skipped, timed_out


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


def denial(failures):
    chunks = []
    for command, outcome, output in failures:
        tail = tail_with_failing_tests(output, output[-TAIL_CHARS:])
        chunks.append(f"=== `{command}` failed ({outcome}), output tail ===\n{tail}")
    failure_text = "\n\n".join(chunks)
    reason = ("The hand-back gate ran the phase's checks and they failed.\n\n" + failure_text
              + "\n\nFix these. Do not run the checks yourself. Then call SubagentHandback again.")
    return reason


def no_result_commands(coder, commands_key, details_key):
    # (command, detail) for each command of one stamp section, in the order the section names them.
    details = coder.get(details_key, {})
    if commands_key is None:
        return list(details.items())
    return [(command, details.get(command, "")) for command in coder.get(commands_key, [])]


def stamped_handback(tool_input, coder):
    # The coder writes its report before the gate runs, so the report can still say that a re-run is pending.
    stamp = (f"{script_utils.HAND_BACK_GATE_MARKER} {coder['result']} after {coder['runs']} run(s), "
             f"failed: {joined_commands(coder, 'failed')}, "
             f"skipped (no changed files): {joined_commands(coder, 'skipped')}. "
             "The gate ran after this report was written. The report is final.")
    for commands_key, details_key, heading, advice, line_format in NO_RESULT_STAMP_SECTIONS:
        no_result = no_result_commands(coder, commands_key, details_key)
        if not no_result:
            continue

        lines = "".join(line_format.format(command=command, detail=detail) for command, detail in no_result)
        stamp += heading.format(timeout_seconds=COMMAND_TIMEOUT_SECONDS) + lines + advice
    stamped_input = dict(tool_input)
    stamped_input["message"] = str(tool_input.get("message", "")) + stamp
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                   "updatedInput": stamped_input}}


def append_gate_log(row):
    if not script_utils.telemetry_switch_on():
        return

    with GATE_LOG.open("a") as log_file:
        log_file.write(json.dumps(row) + "\n")


def log_gate_run(gate, coder, seconds, failed_count, timed_out_count, setup_fault_count):
    repo_name = pathlib.Path(gate["repoRoot"]).name
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repo": repo_name, "result": coder["result"],
           "run": coder["runs"], "seconds": seconds, "failed": failed_count, "timed_out": timed_out_count,
           "setup_faults": setup_fault_count}
    append_gate_log(row)


def run_hook():
    event = json.load(sys.stdin)
    if event.get("agent_type") != "coder":
        return

    gate_file = gate_path(event.get("cwd") or ".")
    if gate_file is None or not gate_file.exists():
        return

    lock_path = gate_file.with_suffix(".lock")
    with lock_path.open("w") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)

        gate = json.loads(gate_file.read_text())
        if time.time() - gate["setAt"] > MAX_GATE_AGE_SECONDS:
            return

        started = time.time()
        failures, skipped, timed_out = run_commands(gate)
        seconds = round(time.time() - started)

        failures, setup_faults, command_errors = sort_failures(failures, gate["repoRoot"])

        agent_id = event.get("agent_id") or "unknown"
        coder = gate["coders"].get(agent_id, {"runs": 0, "denies": 0, "failed": [], "result": "none"})
        coder["runs"] += 1
        coder["failed"] = [command for command, _, _ in failures]
        coder["skipped"] = skipped
        coder["timed_out"] = [command for command, _ in timed_out]
        coder["timed_out_tails"] = {command: output[-TIMEOUT_TAIL_CHARS:] for command, output in timed_out}
        coder["setup_faults"] = [command for command, _ in setup_faults]
        coder["setup_fault_tails"] = {command: output[-TIMEOUT_TAIL_CHARS:] for command, output in setup_faults}
        coder["command_errors"] = [command for command, _ in command_errors]
        coder["command_error_lines"] = dict(command_errors)
        if not failures:
            if command_errors:
                coder["result"] = "command-error"
            else:
                coder["result"] = "setup-fault" if setup_faults else "timeout" if timed_out else "pass"
        elif coder["denies"] >= MAX_DENIES:
            coder["result"] = "cap"
        else:
            coder["result"] = "deny"
            coder["denies"] += 1
        gate["coders"][agent_id] = coder
        script_utils.write_text_atomically(gate_file, json.dumps(gate, indent=1))

    log_gate_run(gate, coder, seconds, len(failures), len(timed_out), len(setup_faults))

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
        while len(set_arguments) >= 2 and set_arguments[0] == "--env":
            env_assignments.append(set_arguments[1])
            set_arguments = set_arguments[2:]
        if "--env" in set_arguments:
            sys.exit("coder-gate: --env needs NAME=value, got nothing after it")

        set_gate(set_arguments, env_assignments)
    elif verb == "clear":
        clear_gate()
    elif verb == "hook":
        run_hook()
    elif verb == "bash-hook":
        run_bash_hook()
    else:
        sys.exit("usage: coder_gate.py set [--env NAME=value]... <command>... | clear | hook | bash-hook")


if __name__ == "__main__":
    main()
