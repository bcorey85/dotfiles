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

set and bash-hook refuse a command that runs a whole test suite, lints a whole package or runs a build. The gate
runs at every hand-back and a coder runs its checks after every edit, and the review loop runs the full check
command once, at its end.

The hook runs the stored commands when a coder calls SubagentHandback. If any command fails, it refuses the call
and returns the output tail of each failed command to the coder, at most 3 times per coder. On a pass or at the cap,
it appends the gate result to the hand-back message, so the caller reads the report as final. With no gate, a gate
older than 6 hours or another agent type, the hand-back goes through untouched. Parallel coders take turns."""
import fcntl
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / folder) for folder in ("lib", "telemetry")]
import script_utils

try:
    from telemetry_enabled import telemetry_enabled
except ImportError:
    def telemetry_enabled():
        return False

MAX_DENIES = 3
MAX_GATE_AGE_SECONDS = 6 * 3600
COMMAND_TIMEOUT_SECONDS = 1200
TAIL_CHARS = 6000
GATE_LOG = pathlib.Path.home() / ".claude/coder-gate.jsonl"

# A simple command that starts with one of these runs tests or lint. With no path, test name or changed-files flag
# after it, it covers the whole package. "test" and "lint" also match script names such as "test:unit".
CHECK_RUN_PREFIXES = [
    ["npm", "test"], ["npm", "t"], ["npm", "run", "test"], ["yarn", "test"], ["yarn", "run", "test"],
    ["pnpm", "test"], ["pnpm", "run", "test"], ["bun", "test"], ["npx", "vitest"], ["npx", "jest"],
    ["vitest"], ["jest"], ["pytest"], ["python", "-m", "pytest"], ["python3", "-m", "pytest"],
    ["uv", "run", "pytest"],
    ["npm", "run", "lint"], ["yarn", "lint"], ["yarn", "run", "lint"], ["pnpm", "lint"], ["pnpm", "run", "lint"],
    ["npx", "eslint"], ["eslint"], ["ruff", "check"],
]
# A build always covers the whole package.
BUILD_PREFIXES = [
    ["npm", "run", "build"], ["yarn", "build"], ["yarn", "run", "build"], ["pnpm", "build"], ["pnpm", "run", "build"],
    ["bun", "run", "build"],
]
SCRIPT_VARIANT_WORDS = ("test", "lint", "build")
WHOLE_PACKAGE_REASON = ("This command runs a whole test suite, lints a whole package or runs a build. Run the "
                        "typecheck, and lint and tests for only the files you changed. The review loop runs the full "
                        "check once, at its end.")
CHANGED_FILES_FLAGS = ("--changed", "--onlyChanged")
WHOLE_PACKAGE_PATHS = {".", "./"}
SHELL_OPERATORS = {"&&", "||", ";", "|", "&", "(", ")"}
REDIRECT_CHARS = set("<>&")
FILES_PLACEHOLDER = re.compile(r"\{files(?::([^{}]*))?\}")
ENV_ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=")


def git_output(cwd, *args):
    found = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if found.returncode != 0:
        return None
    return found.stdout.strip()


def gate_path(cwd):
    git_path = git_output(cwd, "rev-parse", "--path-format=absolute", "--git-path", "coder-gate.json")
    if git_path is None:
        return None
    return pathlib.Path(git_path)


def simple_commands(command):
    # Split a shell line at its operators and drop redirections such as `> out.log` and `2>&1`.
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    words = []
    skip_redirect_target = False
    for token in lexer:
        if token in SHELL_OPERATORS:
            yield words
            words = []
            continue
        if set(token) <= REDIRECT_CHARS:
            if words and words[-1].isdigit():
                words.pop()
            skip_redirect_target = True
            continue
        if skip_redirect_target:
            skip_redirect_target = False
            continue
        words.append(token)
    yield words


def matches_prefix(words, prefix):
    if len(words) < len(prefix):
        return False
    for word, expected in zip(words, prefix, strict=False):
        script_variant = expected in SCRIPT_VARIANT_WORDS and word.startswith(expected + ":")
        if word != expected and not script_variant:
            return False
    return True


def covers_whole_package(words):
    while words and "=" in words[0] and not words[0].startswith("-"):
        words = words[1:]

    if any(matches_prefix(words, prefix) for prefix in BUILD_PREFIXES):
        return True

    for prefix in CHECK_RUN_PREFIXES:
        if not matches_prefix(words, prefix):
            continue
        scope_words = [word for word in words[len(prefix):]
                      if word.startswith(CHANGED_FILES_FLAGS)
                      or not (word.startswith("-") or word == "run" or word in WHOLE_PACKAGE_PATHS)]
        return not scope_words
    return False


def runs_whole_package(command):
    try:
        simple_command_list = list(simple_commands(command))
    except ValueError:
        # shlex cannot split some valid shell, such as $'...' quotes. Let the command through.
        return False
    return any(covers_whole_package(words) for words in simple_command_list)


def environment_from_assignments(assignments):
    # {name: value} for NAME=value shell words such as `A=1` or `B="two words"`. Exits on a word that is not one.
    environment = {}
    for assignment in assignments:
        try:
            words = shlex.split(assignment)
        except ValueError:
            words = []
        is_one_assignment = len(words) == 1 and ENV_ASSIGNMENT.match(words[0])
        if not is_one_assignment:
            sys.exit(f"coder-gate: --env needs NAME=value, got {assignment!r}")

        name, value = words[0].split("=", 1)
        environment[name] = value
    return environment


def set_gate(commands, gate_assignments=()):
    gate_file = gate_path(".")
    if gate_file is None:
        sys.exit("coder-gate: not inside a git repo")
    if not commands:
        sys.exit("coder-gate: set needs at least one command")

    whole_package_commands = [command for command in commands if runs_whole_package(command)]
    if whole_package_commands:
        refused_lines = "\n".join(f"  {command}" for command in whole_package_commands)
        sys.exit("coder-gate: refused. These commands run a whole test suite, lint a whole package or run a build:\n"
                 + refused_lines + "\nName the test files, test names or lint paths that the phase changes, or "
                 "use {files}. The review loop runs the full check command once, at its end.")

    environment = environment_from_assignments(gate_assignments)
    repo_root = git_output(".", "rev-parse", "--show-toplevel")
    gate = {"repoRoot": repo_root, "commands": commands, "env": environment, "setAt": time.time(), "coders": {}}
    script_utils.write_text_atomically(gate_file, json.dumps(gate, indent=1))
    print(f"coder gate set: {len(commands)} command(s)")


def clear_gate():
    gate_file = gate_path(".")
    if gate_file is None or not gate_file.exists():
        print("coder gate: none set")
        return

    gate = json.loads(gate_file.read_text())
    for coder in gate["coders"].values():
        failed_commands = ", ".join(coder["failed"]) or "none"
        skipped_commands = ", ".join(coder.get("skipped", [])) or "none"
        print(f"coder gate: {coder['result']} after {coder['runs']} run(s), failed: {failed_commands}, "
              f"skipped: {skipped_commands}")
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
    tracked_files = git_output(directory, "diff", "--name-only", "--relative", "--diff-filter=d", "HEAD") or ""
    untracked_files = git_output(directory, "ls-files", "--others", "--exclude-standard") or ""
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
    failures = []
    skipped = []
    environment = {**os.environ, **gate.get("env", {})}
    for command in gate["commands"]:
        filled_command = fill_files(command, gate["repoRoot"])
        if filled_command is None:
            skipped.append(command)
            continue

        try:
            finished = subprocess.run(filled_command, shell=True, cwd=gate["repoRoot"], env=environment,
                                      stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                                      timeout=COMMAND_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            failures.append((command, f"timeout after {COMMAND_TIMEOUT_SECONDS} s", ""))
            continue
        if finished.returncode != 0:
            failures.append((command, f"exit {finished.returncode}", finished.stdout))
    return failures, skipped


def denial(failures):
    chunks = []
    for command, outcome, output in failures:
        chunks.append(f"=== `{command}` failed ({outcome}), output tail ===\n{output[-TAIL_CHARS:]}")
    failure_text = "\n\n".join(chunks)
    reason = ("The hand-back gate ran the phase's checks and they failed.\n\n" + failure_text
              + "\n\nFix these. Do not run the checks yourself. Then call SubagentHandback again.")
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                   "permissionDecisionReason": reason}}


def stamped_handback(tool_input, coder):
    # The coder writes its report before the gate runs, so the report can still say that a re-run is pending.
    failed_commands = ", ".join(coder["failed"]) or "none"
    skipped_commands = ", ".join(coder.get("skipped", [])) or "none"
    stamp = (f"\n\nHAND-BACK GATE: {coder['result']} after {coder['runs']} run(s), failed: {failed_commands}, "
             f"skipped (no changed files): {skipped_commands}. "
             "The gate ran after this report was written. The report is final.")
    stamped_input = dict(tool_input)
    stamped_input["message"] = str(tool_input.get("message", "")) + stamp
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
                                   "updatedInput": stamped_input}}


def append_gate_log(row):
    if not telemetry_enabled():
        return

    with GATE_LOG.open("a") as log_file:
        log_file.write(json.dumps(row) + "\n")


def log_gate_run(gate, coder, seconds, failed_count):
    repo_name = pathlib.Path(gate["repoRoot"]).name
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repo": repo_name, "result": coder["result"],
           "run": coder["runs"], "seconds": seconds, "failed": failed_count}
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
        failures, skipped = run_commands(gate)
        seconds = round(time.time() - started)

        agent_id = event.get("agent_id") or "unknown"
        coder = gate["coders"].get(agent_id, {"runs": 0, "denies": 0, "failed": [], "result": "none"})
        coder["runs"] += 1
        coder["failed"] = [command for command, _, _ in failures]
        coder["skipped"] = skipped
        if not failures:
            coder["result"] = "pass"
        elif coder["denies"] >= MAX_DENIES:
            coder["result"] = "cap"
        else:
            coder["result"] = "deny"
            coder["denies"] += 1
        gate["coders"][agent_id] = coder
        script_utils.write_text_atomically(gate_file, json.dumps(gate, indent=1))

    log_gate_run(gate, coder, seconds, len(failures))

    if coder["result"] == "deny":
        print(json.dumps(denial(failures)))
        return

    tool_input = event.get("tool_input") or {}
    print(json.dumps(stamped_handback(tool_input, coder)))


def run_bash_hook():
    event = json.load(sys.stdin)
    if event.get("agent_type") != "coder":
        return

    command = str((event.get("tool_input") or {}).get("command", ""))
    if not runs_whole_package(command):
        return

    repo_name = pathlib.Path(event.get("cwd") or ".").name
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "repo": repo_name, "result": "whole-package-deny"}
    append_gate_log(row)

    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": WHOLE_PACKAGE_REASON}}))


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
