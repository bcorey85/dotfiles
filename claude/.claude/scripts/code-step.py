#!/usr/bin/env python3
"""code-step.py: the routing of /code as a script. The forked Sonnet subagent of /code runs one verb, reads its
ACTION lines, does exactly that, and runs the next verb. The script builds every prompt and every argument.

  code-step.py start [<plan>] [+fast|+deep]   next phase of the plan: checks, gate, packet, the exact coder dispatch
  code-step.py start --task "<text>"           planless work: the coder dispatch without gate or packet
  code-step.py after-coder                      clear the gate, find PLAN-IMPACT, build the exact review-loop dispatch
  code-step.py decide <adopt|keep|discuss> [--ruling "<the user's words>"]
                                                record the user's ruling when the code and the plan disagree
  code-step.py after-plan-edit                  the coder rewrote the plan to an adopted change: build the review dispatch
  code-step.py after-review                    route on the loop packet; on converged/deferred also run the phase gates
  code-step.py asks-done <outcome>...           log the user's answer to each ask[] entry, then run the phase gates
  code-step.py skill-done <pass|fail>          a closing phase's skill returned: mark it done (pass) or stop (fail)
  code-step.py verify                           re-run the phase gates after a failed Automated Verification was fixed
  code-step.py hook                             PreToolUse hook on SubagentHandback: save coder and review-loop messages
  code-step.py status                           print the saved state

One coder runs per phase. The current skill's two parallel coders for deliverables that share no file are dropped by design.
Run from the repo root. State lives in <git dir>/code-step/. Env CODE_STEP_CLAUDE_DIR overrides ~/.claude."""
import datetime
import json
import os
import pathlib
import re
import shlex
import shutil
import signal
import subprocess
import sys
import textwrap
import time

CLAUDE_DIR = pathlib.Path(os.environ.get("CODE_STEP_CLAUDE_DIR", pathlib.Path.home() / ".claude"))
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
SELF_COMMAND = "python3 " + str(pathlib.Path(__file__).resolve())
INSTALLED_COMMAND = "python3 ~/.claude/scripts/code-step.py"
PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]
DECISION_WORDS = {"adopt": PLAN_IMPACT_OPTIONS[0], "keep": PLAN_IMPACT_OPTIONS[1], "discuss": PLAN_IMPACT_OPTIONS[2]}
CLOSING_TITLE_END = r"\b(?:\s*[—–:-]|\s*\(risk|\s*$)"
CLOSING_PHASES = [
    (re.compile(r"^Refactor pass" + CLOSING_TITLE_END, re.I), "/refactor +deep"),
    (re.compile(r"^Test audit" + CLOSING_TITLE_END, re.I), "/test-audit"),
    (re.compile(r"^Verify pass" + CLOSING_TITLE_END, re.I), "/verify-branch"),
    (re.compile(r"^Recap" + CLOSING_TITLE_END, re.I), "/branch-recap"),
]
VERIFY_TIMEOUT_SECONDS = 600
TIMEOUT_EXIT_CODE = 124
HOOK_STAGES = ("coder", "review", "asks-coder")
SAY_MAX_AGE_SECONDS = 6 * 3600
TICKET_ID = re.compile(r"^[A-Za-z]+-\d+$")
PACKET_KEYS = ["status", "iter", "spec_iter", "fixed", "skipped_fp", "blockers", "findings_remaining", "plan_impact",
               "ask", "class_closure", "files_touched", "nit", "load_bearing_clean"]
LIST_KEYS = ["fixed", "skipped_fp", "blockers", "findings_remaining", "ask", "nit"]
TYPECHECK_SCRIPTS = ["typecheck", "type-check", "check-types", "tsc"]
SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs")
TEST_SUFFIXES = ".test.ts,.test.tsx,.spec.ts,.spec.tsx,.test.js,.test.jsx"
TEST_FILE = re.compile(r"\.(test|spec)\.|(^|/)test_[^/]*\.py$|_test\.py$")
PATH_IN_BACKTICKS = re.compile(r"`([\w.@-]+(?:/[\w.@\[\]()-]+)+\.\w+)(?::\d+(?:-\d+)?)?`")
WHOLE_SUITE = re.compile(r"^(?:(?:cd \S+ && )?(?:npm|pnpm|yarn) (?:run )?(?:test|lint)"
                         r"|(?:cd \S+ && )?npx (?:vitest|jest)(?: run)?|(?:python3 -m )?pytest|ruff check)$")
NONE_VALUE = re.compile(r"^\[\s*\]|^\(?\s*(none|n/a|null)\b", re.I)


def run_command(command, cwd, stdin=None, timeout=None):
    # A timeout kills the whole process group, so a shell command that started a server cannot keep the pipes open.
    process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE if stdin is not None else None,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               shell=isinstance(command, str), start_new_session=True)
    try:
        stdout, stderr = process.communicate(stdin, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
        tail = (stdout + stderr).strip()
        return TIMEOUT_EXIT_CODE, (tail + f"\ntimed out after {timeout} seconds").strip()
    return process.returncode, (stdout + stderr).strip()


def git_output(cwd, *args):
    code, output = run_command(["git", *args], cwd)
    return output if code == 0 else None


def repo_root():
    root = git_output(os.getcwd(), "rev-parse", "--show-toplevel")
    if root is None:
        sys.exit("code-step: not inside a git repo")
    return pathlib.Path(root)


def state_dir(cwd):
    found = git_output(cwd, "rev-parse", "--path-format=absolute", "--git-path", "code-step")
    if found is None:
        return None
    return pathlib.Path(found)


class StateFileError(Exception):
    pass


def load_state(cwd):
    directory = state_dir(cwd)
    if directory is None or not (directory / "state.json").exists():
        return None
    stateFile = directory / "state.json"
    try:
        return json.loads(stateFile.read_text())
    except ValueError:
        raise StateFileError(f"{stateFile} is not readable JSON")


def current_branch(cwd):
    return git_output(cwd, "branch", "--show-current") or "-"


def save_state(cwd, state):
    directory = state_dir(cwd)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "state.json").write_text(json.dumps(state, indent=1))


def saved_messages(cwd, agentType, stage, skipRows=0):
    # The last message per agent id of this type saved while the state was in this stage, ignoring the first
    # skipRows rows of the file.
    reportsFile = state_dir(cwd) / "reports.jsonl"
    if not reportsFile.exists():
        return []
    lastPerAgent = {}
    for line in reportsFile.read_text().splitlines()[skipRows:]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row["agent_type"] == agentType and row["stage"] == stage:
            lastPerAgent.pop(row["agent_id"], None)
            lastPerAgent[row["agent_id"]] = row["message"]
    return list(lastPerAgent.values())


def all_saved_messages(cwd, agentType, stage):
    reportsFile = state_dir(cwd) / "reports.jsonl"
    if not reportsFile.exists():
        return []
    messages = []
    for line in reportsFile.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row["agent_type"] == agentType and row["stage"] == stage:
            messages.append(row["message"])
    return messages


def own_path(text):
    # Printed commands name this file by its real path, so they work from a bench copy as well as from ~/.claude/scripts.
    return text.replace(INSTALLED_COMMAND, SELF_COMMAND)


def say(repoRoot, text):
    # User-facing text goes to a file the /code subagent hands back verbatim, so the model never has to copy it.
    directory = state_dir(repoRoot)
    if directory is None:
        return
    directory.mkdir(parents=True, exist_ok=True)
    with open(directory / "say.md", "a") as sayFile:
        sayFile.write(own_path(text).rstrip() + "\n\n")


def command_say_hook():
    # Stop hook: print the saved user-facing text as the hook's systemMessage, keep a copy in say.log, empty say.md.
    try:
        event = json.loads(sys.stdin.read() or "{}")
        directory = state_dir(pathlib.Path(event.get("cwd") or os.getcwd()))
        if directory is None or not (directory / "say.md").exists():
            return
        sayFile = directory / "say.md"
        isStale = time.time() - sayFile.stat().st_mtime > SAY_MAX_AGE_SECONDS
        text = sayFile.read_text().strip()
        sayFile.write_text("")
        if not text or isStale:
            return
        with open(directory / "say.log", "a") as logFile:
            logFile.write(f"--- {datetime.datetime.now().isoformat()}\n{text}\n")
        print(json.dumps({"systemMessage": text}))
    except Exception as error:
        print(f"code-step say-hook: {error}", file=sys.stderr)


def clear_say(repoRoot):
    directory = state_dir(repoRoot)
    if directory is not None and (directory / "say.md").exists():
        (directory / "say.md").write_text("")


def ask_user(repoRoot, instruction, *questionLines):
    # The /code subagent cannot ask the user: the question goes in say.md for the main session to ask.
    say(repoRoot, "\n".join(["## Question for the user", "", "Main session: " + instruction, "", *questionLines]))
    emit("ask-user", "The question for the user is in say.md. Hand back.")


def emit(action, *lines, prompt=None, agent=None, model=None):
    lines = [own_path(line) for line in lines]
    print(f"ACTION: {action}")
    if agent:
        print(f"AGENT: {agent}")
        print(f"MODEL: {model or 'omit the model argument'}")
        print("BACKGROUND: no. Never set run_in_background.")
    for line in lines:
        print(line)
    if prompt is not None:
        print("PROMPT (pass it verbatim, add and remove nothing):")
        print("-----BEGIN PROMPT-----")
        print(own_path(prompt))
        print("-----END PROMPT-----")


# ---------- plan parsing ----------

def plan_sections(planLines):
    return [index for index, line in enumerate(planLines) if line.startswith("## ")]


def phase_status_entries(planLines):
    entries = []
    inStatus = False
    for index, line in enumerate(planLines):
        if line.startswith("## "):
            inStatus = line.strip() == "## Phase Status"
            continue
        match = re.match(r"^- \[( |x)\] Phase (\d+):\s*(.*)$", line) if inStatus else None
        if match:
            risk = re.search(r"\(risk:\s*(low|high)\)", match.group(3))
            entries.append({"line": index, "done": match.group(1) == "x", "number": match.group(2),
                            "title": match.group(3), "risk": risk.group(1) if risk else "high"})
    return entries


def phase_text(planLines, number):
    sections = plan_sections(planLines)
    start = next((i for i in sections if re.match(rf"## Phase {number}\b", planLines[i])), None)
    if start is None:
        return None
    end = next((i for i in sections if i > start), len(planLines))
    return "\n".join(planLines[start:end])


def verification_items(phaseSection, heading):
    items = []
    inside = False
    for line in phaseSection.splitlines():
        if line.startswith("#### "):
            inside = line.startswith(f"#### {heading}")
            continue
        if line.startswith("## ") or line.strip() == "---":
            inside = False
        if inside and re.match(r"^- \[[ x]\]", line):
            items.append(line)
    return items


# ---------- gate derivation ----------

def nearest_package(repoRoot, relPath):
    directory = (repoRoot / relPath).parent
    while True:
        if (directory / "package.json").is_file():
            return directory
        if directory == repoRoot or repoRoot not in directory.parents:
            return None
        directory = directory.parent


def in_directory(command, packageRel):
    return f"cd {shlex.quote(packageRel)} && {command}" if packageRel else command


def script_package_commands(repoRoot, packageDir, paths):
    packageJson = json.loads((packageDir / "package.json").read_text())
    scripts = packageJson.get("scripts", {})
    dependencies = {**packageJson.get("dependencies", {}), **packageJson.get("devDependencies", {})}
    packageRel = str(packageDir.relative_to(repoRoot)) if packageDir != repoRoot else ""
    relativePaths = [str((repoRoot / path).relative_to(packageDir)) for path in paths]
    commands = []

    typecheckName = next((name for name in TYPECHECK_SCRIPTS if name in scripts), None)
    if typecheckName:
        commands.append(in_directory(f"npm run {typecheckName}", packageRel))
    elif (packageDir / "tsconfig.json").is_file():
        commands.append(in_directory("npx tsc --noEmit", packageRel))

    sourceSuffixes = sorted({pathlib.Path(p).suffix for p in relativePaths
                             if p.endswith(SCRIPT_SUFFIXES) and not TEST_FILE.search(p)}
                            | {pathlib.Path(p).suffix for p in relativePaths if p.endswith(SCRIPT_SUFFIXES)})
    if ("eslint" in dependencies or "lint" in scripts) and sourceSuffixes:
        commands.append(in_directory("npx eslint {files:" + ",".join(sourceSuffixes) + "}", packageRel))

    testPaths = [p for p in relativePaths if TEST_FILE.search(p)]
    runner = "vitest run" if "vitest" in dependencies else "jest" if "jest" in dependencies else None
    if runner:
        scope = " ".join(shlex.quote(p) for p in testPaths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npx {runner} {scope}", packageRel))
    elif "test" in scripts:
        scope = " ".join(shlex.quote(p) for p in testPaths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npm test -- {scope}", packageRel))
    return commands


def python_commands(repoRoot, paths):
    pythonPaths = [p for p in paths if p.endswith(".py")]
    if not pythonPaths or not any((repoRoot / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg")):
        return []
    commands = []
    pyproject = (repoRoot / "pyproject.toml")
    if pyproject.is_file() and "ruff" in pyproject.read_text():
        commands.append("ruff check {files:.py}")
    testPaths = [p for p in pythonPaths if TEST_FILE.search(p)]
    scope = " ".join(shlex.quote(p) for p in testPaths) or "{files:_test.py}"
    commands.append(f"python3 -m pytest {scope}")
    return commands


def derive_gate_commands(repoRoot, phaseSection):
    paths = []
    for match in PATH_IN_BACKTICKS.finditer(phaseSection):
        if match.group(1) not in paths:
            paths.append(match.group(1))

    byPackage = {}
    for path in paths:
        packageDir = nearest_package(repoRoot, path)
        if packageDir is not None:
            byPackage.setdefault(packageDir, []).append(path)

    commands = []
    for packageDir, packagePaths in byPackage.items():
        commands += script_package_commands(repoRoot, packageDir, packagePaths)
    commands += python_commands(repoRoot, paths)
    return commands


# ---------- start ----------

def file_hashes(repoRoot):
    tracked = git_output(repoRoot, "diff", "--name-only", "HEAD") or ""
    untracked = git_output(repoRoot, "ls-files", "--others", "--exclude-standard") or ""
    hashes = {}
    for name in sorted({n for n in (tracked + "\n" + untracked).split("\n") if n}):
        # A deleted file has no content to hash: its hash is None, which still differs from a baseline that had it.
        hashes[name] = git_output(repoRoot, "hash-object", name) if (repoRoot / name).exists() else None
    return hashes


def parse_start_args(args):
    modifiers = [a for a in args if a in ("+fast", "+deep")]
    rest = [a for a in args if a not in ("+fast", "+deep")]
    modifier = "+deep" if "+deep" in modifiers else "+fast" if modifiers else None
    taskText = None
    if "--task" in rest:
        taskText = " ".join(rest[rest.index("--task") + 1:])
        rest = rest[:rest.index("--task")]
    return modifier, rest, taskText


def resolve_plan(repoRoot, argument=None):
    command = ["bash", str(SCRIPTS_DIR / "resolve-task-dir.sh")] + ([argument] if argument else [])
    code, output = run_command(command, repoRoot)
    if code == 0:
        return str(pathlib.PurePath(output) / "spec.md"), "eng-spec"
    if code == 5:
        return output, "eng-spec"
    if code == 3:
        ask_user(repoRoot, "several tasks match. Ask the user which one to implement. Then invoke Skill code with "
                 "the chosen plan path.", output)
    else:
        ask_user(repoRoot, "no task or plan resolves. Ask the user what to implement. Then invoke Skill code with a "
                 "plan path or the task text.")
    return None, None


def looks_like_plan_path(argument):
    return "/" in argument or argument.endswith(".md")


def reusable_plan(previous, branch):
    # The saved plan serves a bare `start` only on the branch it was saved on, and not after a plan with no phases finished.
    if not previous.get("plan") or previous.get("branch") != branch:
        return None
    if previous.get("stage") == "done" and previous.get("phase") is None:
        return None
    return previous["plan"]


def is_finished_single_phase_plan(repoRoot, previous, branch, resolvedPlan):
    # A plan with no phases that finished on this branch is not run again when a bare `start` resolves to the same file.
    if previous.get("stage") != "done" or previous.get("phase") is not None or previous.get("branch") != branch:
        return False
    if not previous.get("plan"):
        return False
    try:
        resolvedRel = str(pathlib.Path(resolvedPlan).resolve().relative_to(repoRoot))
    except ValueError:
        return False
    return resolvedRel == previous["plan"]


def command_start(args):
    repoRoot = repo_root()
    os.chdir(repoRoot)
    modifier, planArgs, taskText = parse_start_args(args)
    previous = load_state(repoRoot) or {}
    branch = current_branch(repoRoot)
    isAutoAdvanceTextPending = previous.get("stage") == "done" and previous.get("autoAdvance")
    if previous.get("stage") is not None and not isAutoAdvanceTextPending:
        clear_say(repoRoot)

    if taskText is not None:
        return start_planless(repoRoot, modifier, taskText, branch)

    planArg = planArgs[0] if planArgs else None
    lane = previous.get("lane", "code")
    isUnknownArg = planArg is not None and not pathlib.Path(planArg).is_file()
    if isUnknownArg and not looks_like_plan_path(planArg) and not TICKET_ID.match(planArg) \
            and not pathlib.Path(planArg).is_dir():
        return start_planless(repoRoot, modifier, " ".join(planArgs), branch)
    if isUnknownArg and (TICKET_ID.match(planArg) or pathlib.Path(planArg).is_dir()):
        planArg, lane = resolve_plan(repoRoot, planArg)
        if planArg is None:
            return
        print(f"Resolved the task input: {planArg} (lane {lane}).")
    elif planArg is None and reusable_plan(previous, branch):
        planArg = previous["plan"]
    elif planArg is None:
        planArg, lane = resolve_plan(repoRoot)
        if planArg is None:
            return
        if is_finished_single_phase_plan(repoRoot, previous, branch, planArg):
            return emit("stop", f"The plan {previous['plan']} is complete. Tell the user the plan is complete.")
        print(f"Resolved the task input: {planArg} (lane {lane}).")
    elif previous.get("plan") != planArg:
        lane = "code"

    planPath = pathlib.Path(planArg)
    if not planPath.is_file():
        return ask_user(repoRoot, f"no plan file is at {planArg}. Ask the user for the path. Then invoke Skill code "
                        "with that path.")
    try:
        planRel = str(planPath.resolve().relative_to(repoRoot))
    except ValueError:
        return ask_user(repoRoot, f"the plan {planArg} is outside the repo {repoRoot}. Ask the user for a plan inside "
                        "the repo. Then invoke Skill code with that path.")
    planLines = planPath.read_text().splitlines()

    entries = phase_status_entries(planLines)
    hasPhases = any(re.match(r"## Phase \d", line) for line in planLines)
    if not entries and hasPhases:
        return emit("judgment", "The plan has phases but no '## Phase Status' section. Use `git status` and each "
                    "phase's success criteria to pick the next phase, tell the user to backfill the section, then "
                    "run `code-step.py start` again after adding it.")
    pending = [entry for entry in entries if not entry["done"]]
    if entries and not pending:
        return emit("stop", "Every phase in the plan is checked. Tell the user the plan is complete.")
    entry = pending[0] if pending else None

    number = entry["number"] if entry else None
    section = phase_text(planLines, number) if entry else "\n".join(planLines)
    if entry and section is None:
        return emit("stop", f"Phase Status lists Phase {number} but the plan has no '## Phase {number}' section. "
                    "Report a plan defect to the user.")

    if entry:
        closingSkill = next((skill for pattern, skill in CLOSING_PHASES if pattern.search(entry["title"])), None)
        if closingSkill:
            return start_closing_phase(repoRoot, planRel, lane, modifier, entry, closingSkill, section, branch)

    if not check_acceptance_criteria(repoRoot, planPath, planLines, planRel, number):
        return

    commands = derive_gate_commands(repoRoot, section) if entry else []
    gateNote = set_gate_and_packet_note(repoRoot, commands)
    packetText = packet_text(repoRoot, planRel, number, hasPhases and entry)

    reportsFile = state_dir(repoRoot) / "reports.jsonl"
    reportsFile.unlink(missing_ok=True)

    statePhase = number if hasPhases and entry else None
    isSameUnfinishedPhase = (previous.get("plan") == planRel and previous.get("phase") == statePhase
                             and previous.get("stage") not in (None, "done") and previous.get("baseline") is not None)
    baseline = previous["baseline"] if isSameUnfinishedPhase else file_hashes(repoRoot)

    phaseLabel = f"Phase {number} of `{planRel}`" if entry and hasPhases else f"`{planRel}`"
    prompt = (f"Implement {phaseLabel}. Read the plan phase-scoped.\n"
              "If the task turns out architectural, report back and recommend /eng-spec.\n\n" + packetText).rstrip()
    state = {"stage": "coder", "plan": planRel, "lane": lane, "phase": statePhase, "branch": branch,
             "modifier": modifier, "risk": entry["risk"] if entry else "high", "title": entry["title"] if entry else "",
             "gateCommands": commands, "baseline": baseline, "startedAt": time.time()}
    save_state(repoRoot, state)
    model = "haiku" if modifier == "+fast" else None
    emit("dispatch", gateNote, "NEXT: when the coder returns, run `python3 ~/.claude/scripts/code-step.py after-coder`.",
         prompt=prompt, agent="coder", model=model)


def start_planless(repoRoot, modifier, taskText, branch="-"):
    state = {"stage": "coder", "plan": None, "lane": "code", "phase": None, "branch": branch, "modifier": modifier,
             "risk": "high", "title": "", "gateCommands": [], "baseline": file_hashes(repoRoot),
             "startedAt": time.time()}
    directory = state_dir(repoRoot)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "reports.jsonl").unlink(missing_ok=True)
    clear_say(repoRoot)
    save_state(repoRoot, state)
    prompt = (f"Implement: {taskText}\nRun the typecheck, and lint and tests for only the files you changed, once, "
              "after all edits. If the task turns out architectural, report back and recommend /eng-spec.")
    model = "haiku" if modifier == "+fast" else None
    emit("dispatch", "NEXT: when the coder returns, run `python3 ~/.claude/scripts/code-step.py after-coder`.",
         prompt=prompt, agent="coder", model=model)


def start_closing_phase(repoRoot, planRel, lane, modifier, entry, skill, section, branch):
    state = {"stage": "skill", "plan": planRel, "lane": lane, "phase": entry["number"], "branch": branch,
             "modifier": modifier, "risk": entry["risk"], "title": entry["title"], "gateCommands": [], "behavior": []}
    save_state(repoRoot, state)
    verdictStep = ("run `python3 ~/.claude/scripts/code-step.py skill-done pass` when the phase's Success Criteria "
                   "hold, or `skill-done fail` when they do not (for the Verify pass, any MISSING criterion fails it)")
    sectionLines = ["The phase's own plan section follows. Follow its steps and gates; the skill alone is not the phase:",
                    section]
    if skill == "/verify-branch":
        prompt = ("Branch-wide deep review: review the whole branch diff against its base branch (git diff "
                  "<base>...HEAD), backend and frontend together. This is the only review of cross-phase interactions. "
                  "Report findings with file:line and severity.")
        return emit("dispatch", f"Phase {entry['number']} ({entry['title']}) is a closing phase. Step 1 of 2: the "
                    "branch-wide deep review.", *sectionLines,
                    "NEXT: route the findings with /review and log them with scope=branch-exit. Then invoke the Skill "
                    "tool with `/verify-branch` and reconcile every acceptance criterion (the covering test as file:line, or "
                    f"MISSING). Then {verdictStep}.", prompt=prompt, agent="code-reviewer")
    emit("invoke-skill", f"Phase {entry['number']} ({entry['title']}) is a closing phase. Invoke the Skill tool with "
         f"`{skill}`; a coder is not dispatched.", *sectionLines, f"The skill needs judgment. When it returns, {verdictStep}.")


def check_acceptance_criteria(repoRoot, planPath, planLines, planRel, number):
    hasCriteriaSection = any(line.strip() == "## Acceptance Criteria" for line in planLines)
    if not hasCriteriaSection:
        return True
    criteria = planPath.resolve().parent / "acceptance-criteria.md"
    if criteria.is_file() and criteria.read_text().strip():
        return True

    note = f"{criteria.relative_to(repoRoot)} is missing or empty"
    run_command(["bash", str(SCRIPTS_DIR / "log-scan"), f"repo={repoRoot.name}", "scan=acceptance-stub",
                 "stage=code-phase", "exit=0", "candidates=1", "confirmed=1", f"note={note}"], repoRoot)
    emit("stop", f"Plan defect: {note}, and the plan has an Acceptance Criteria section.",
         "Do not dispatch. Do not write the criteria. Report the defect to the user and wait.")
    return False


def set_gate_and_packet_note(repoRoot, commands):
    if not commands:
        return "GATE: none derived; the coder runs its own checks (the packet says so)."
    code, output = run_command(["python3", str(SCRIPTS_DIR / "coder-gate.py"), "set", *commands], repoRoot)
    if code != 0:
        return f"GATE: not set ({output.splitlines()[0] if output else 'refused'}); the coder runs its own checks."
    return f"GATE: {output}. Commands: " + " | ".join(commands)


def packet_text(repoRoot, planRel, number, usePacket):
    if not usePacket:
        return ""
    code, output = run_command(["python3", str(SCRIPTS_DIR / "coder-packet.py"), planRel, str(number)], repoRoot)
    if code != 0:
        sys.exit(f"code-step: coder-packet failed: {output}")
    return output


# ---------- after-coder ----------

def coder_flags(report):
    flagged = []
    for line in report.splitlines():
        mentionsOpenPoint = re.search(r"\bambigu(ous|ity|ities)\b|open question", line, re.I)
        deniesOpenPoint = re.search(r"\b(no|none)\b", line, re.I)
        if mentionsOpenPoint and not deniesOpenPoint:
            flagged.append(line.strip())
    return flagged


def plan_impact_block(report):
    match = re.search(r"^PLAN-IMPACT:[ \t]*\n((?:[ \t]+\S.*\n?)+)", report, re.M)
    if match:
        return "PLAN-IMPACT:\n" + match.group(1).rstrip()
    if re.search(r"^PLAN-IMPACT:\s*yes\s*$", report, re.M):
        return "PLAN-IMPACT: yes (block not found in the report; read the report)"
    return None


def first_plan_impact(messages):
    for message in messages:
        block = plan_impact_block(message)
        if block:
            return block
    return None


def why_by_file(report):
    grouped = {}
    for match in re.finditer(r"^WHY:\s*`?(\S+?)`?(?::|\s+)(\d+-\d+)\s*[—-]+\s*(.+)$", report, re.M):
        grouped.setdefault(match.group(1), []).append({"lines": match.group(2), "note": match.group(3).strip()})
    return grouped


def behavior_lines(report):
    found = [m.group(1).strip() for m in re.finditer(r"^BEHAVIOR:\s*(.+)$", report, re.M)]
    return [line for line in found if line.lower() != "none"]


def path_suffixes(path, minParts=2):
    parts = path.split("/")
    return ["/".join(parts[start:]) for start in range(len(parts)) if len(parts) - start >= min(minParts, len(parts))]


def mentions_path(line, path, files=()):
    # True when the line names the path, or a trailing part of it (reports often drop the leading backend/src/).
    # A bare file name counts only when no other changed file shares it.
    baseName = path.rsplit("/", 1)[-1]
    sharesBaseName = any(name != path and name.rsplit("/", 1)[-1] == baseName for name in files)
    suffixes = path_suffixes(path) + ([] if sharesBaseName else [baseName])
    for suffix in suffixes:
        if re.search(rf"(?<![\w./-]){re.escape(suffix)}(?![\w/])", line):
            return True
    return False


def resolve_report_paths(grouped, files):
    # Re-key a report's per-path dict to the changed files' full paths, matching on trailing path parts.
    resolved = {}
    for reportPath, value in grouped.items():
        candidates = [name for name in files if name == reportPath or name.endswith("/" + reportPath)
                      or reportPath.endswith("/" + name)]
        target = candidates[0] if len(candidates) == 1 else reportPath
        resolved.setdefault(target, []).extend(value)
    return resolved


def change_line(report, path, files, fallbackBehavior, isNewFile=False):
    # A report names a file's change on a bullet that starts with the path (or a trailing part of it).
    # Prose lines that only mention the path, and grouped "Created: a, b" lines, do not count.
    baseName = path.rsplit("/", 1)[-1]
    sharesBaseName = any(name != path and name.rsplit("/", 1)[-1] == baseName for name in files)
    suffixes = sorted(path_suffixes(path) + ([] if sharesBaseName else [baseName]), key=len, reverse=True)
    for line in report.splitlines():
        if not re.match(r"^\s*[-*]\s", line):
            continue
        body = line.strip().lstrip("-* ").lstrip("`")
        for suffix in suffixes:
            match = re.match(rf"{re.escape(suffix)}`?\s*(?:[:—-]+\s*|\s+)(.+)$", body)
            if match:
                return re.sub(r"\s+", " ", match.group(1).strip())[:160]
    if isNewFile:
        return "new file"
    return fallbackBehavior or "changed by the coder"


def gate_results(repoRoot):
    gateFile = git_output(repoRoot, "rev-parse", "--path-format=absolute", "--git-path", "coder-gate.json")
    if gateFile is None or not pathlib.Path(gateFile).exists():
        return None
    return json.loads(pathlib.Path(gateFile).read_text())


def tests_run_text(gate, state):
    if gate is None or not gate["coders"]:
        return "none"
    parts = []
    for coder in gate["coders"].values():
        for command in gate["commands"]:
            if command in coder["failed"]:
                parts.append(f"{command} -> failed at the hand-back gate ({coder['result']})")
            elif command in coder.get("skipped", []):
                parts.append(f"{command} -> skipped, no changed files")
            else:
                parts.append(f"{command} -> exit 0")
    return "; ".join(parts)


def command_after_coder(args):
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    if state is None or state["stage"] not in ("coder", "asks-coder"):
        return emit("stop", "after-coder ran with no coder dispatch pending. Run `start` first.")

    coderStage = state["stage"]
    isAskFix = coderStage == "asks-coder"
    gate = None if isAskFix else gate_results(repoRoot)
    gateLines = state.get("gateLines", "")
    if not isAskFix:
        code, gateLines = run_command(["python3", str(SCRIPTS_DIR / "coder-gate.py"), "clear"], repoRoot)
    reports = saved_messages(repoRoot, "coder", coderStage)
    if not reports:
        return emit("stop", "No coder report was saved. The SubagentHandback hook (code-step.py hook) is not "
                    "installed or the coder never handed back. Tell the user.")
    report = "\n\n".join(reports)

    capped = [coder for coder in (gate or {"coders": {}})["coders"].values() if coder["result"] == "cap"]
    flagged = list(state.get("flagged", [])) if isAskFix else []
    for coder in capped:
        flagged.append("hand-back gate cap: " + ", ".join(coder["failed"]) + " still failing after 3 denials")
    flagged += coder_flags(report)

    changedNow = file_hashes(repoRoot)
    baseline = state["baseline"]
    changedFiles = [name for name, digest in changedNow.items() if name not in baseline or baseline[name] != digest]
    asksCoderChangedNothing = isAskFix and changedNow == state.get("asksBaseline")
    if not changedFiles or asksCoderChangedNothing or "/eng-spec" in report:
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        return emit("stop", "The coder produced no reviewable change, or recommended /eng-spec. Do not dispatch a "
                    "review. Do not mark the phase done. Relay the coder's report to the user:", report)

    behavior = behavior_lines(report)
    whyGroups = resolve_report_paths(why_by_file(report), changedFiles)
    testsRun = tests_run_text(gate, state)
    if isAskFix:
        behavior = list(state.get("behavior", [])) + behavior
        for path, notes in state["why"].items():
            whyGroups[path] = notes + whyGroups.get(path, [])
        testsRun = state["testsRun"] + "; ask-fix coder -> ran its own checks"
        state.update({"iter": 0, "spec_iter": 0, "priorIssues": prior_issues(state["acceptedAsks"])})
    state.update({"gateLines": gateLines, "flagged": flagged, "behavior": behavior, "exception": bool(flagged),
                  "files": changedFiles, "why": whyGroups, "testsRun": testsRun, "coderStage": coderStage})

    impact = first_plan_impact(all_saved_messages(repoRoot, "coder", coderStage))
    if impact:
        state.update({"stage": "impact-coder", "impact": impact})
        save_state(repoRoot, state)
        return emit_plan_impact_modal(impact, repoRoot)

    state["planImpact"] = "none"
    save_state(repoRoot, state)
    emit_review_dispatch(repoRoot, state)


def prior_issues(acceptedAsks):
    issues = []
    for item, outcome, changeText in acceptedAsks:
        fileLine = item.get("file_line", "") if isinstance(item, dict) else ""
        issueText = item_text(item, "finding", "question")
        if changeText:
            issueText += f" (user's change: {changeText})"
        issues.append({"issue": issueText, "file": fileLine.partition(":")[0]})
    return issues


def preset_decision(repoRoot):
    # A pre-answered decision for runs with no AskUserQuestion (claude -p, bench): env var or a file in the state dir.
    word = os.environ.get("CODE_STEP_IMPACT_DECISION", "").strip().lower()
    presetFile = state_dir(repoRoot) / "impact-decision"
    if not word and presetFile.exists():
        word = presetFile.read_text().strip().lower()
    return word if word in ("adopt", "keep") else None


def emit_plan_impact_modal(impact, repoRoot):
    word = preset_decision(repoRoot)
    if word:
        print(f"PLAN-IMPACT answered by the pre-set decision '{word}'. No question to the user.")
        return command_decide([word, "--ruling", f"pre-set decision '{word}'; no user was asked"],
                              rulingBy="the pre-set decision")
    ask_user(repoRoot, "the code and the plan disagree. Ask the user this question in plain text and wait for the "
             "answer. Then invoke Skill code with the args after the option the user chose, with the user's whole "
             "answer, in their words, as the --ruling text.",
             impact, "",
             f"1. {PLAN_IMPACT_OPTIONS[0]} (a coder rewrites the plan steps to match the ruling): "
             "`decide adopt --ruling \"<the user's answer>\"`",
             f"2. {PLAN_IMPACT_OPTIONS[1]}: `decide keep --ruling \"<the user's answer>\"`",
             f"3. {PLAN_IMPACT_OPTIONS[2]}: talk it through here, then invoke Skill code with "
             "`decide adopt --ruling \"<the user's answer>\"` or `decide keep --ruling \"<the user's answer>\"`")


def record_deviation(repoRoot, state):
    ruling = state["ruling"]
    planPath = repoRoot / state["plan"]
    lines = planPath.read_text().split("\n")
    entry = [f"- {time.strftime('%Y-%m-%d')} (Phase {state['phase']}): {ruling['decision']}. "
             f"Ruled by {ruling['by']} at {ruling['at']}.", "", "  The user's words:"]
    entry += ["  > " + line for line in ruling["words"].splitlines()]
    entry += ["", "  The disagreement:"]
    entry += ["  " + line for line in state["impact"].splitlines()]
    sections = [i for i, line in enumerate(lines) if line.startswith("## ")]
    existing = next((i for i in sections if lines[i].strip() == "## Plan Deviations"), None)
    if existing is not None:
        end = next((i for i in sections if i > existing), len(lines))
        lines[end:end] = entry + [""]
    else:
        references = next((i for i in sections if lines[i].strip() == "## References"), len(lines))
        lines[references:references] = ["## Plan Deviations", ""] + entry + [""]
    planPath.write_text("\n".join(lines))


def split_decide_args(args):
    # The decision word, then the user's words after `--ruling`, joined when the caller left them unquoted.
    word = args[0].lower() if args else ""
    if "--ruling" not in args:
        return word, ""
    rulingWords = " ".join(args[args.index("--ruling") + 1:])
    return word, rulingWords.strip()


def resolved_plan_impact(state):
    # review-loop reads a block that starts RESOLVED as settled, so it reviews against the ruling instead of
    # returning the question again.
    ruling = state["ruling"]
    lines = ["RESOLVED: the user ruled on this disagreement. Review the code against the ruling. It is not an open "
             "question.",
             f"Decision: {ruling['decision']}",
             f"Ruled by: {ruling['by']}, at {ruling['at']}",
             "Ruling, in the user's words:"]
    lines += ["  " + line for line in ruling["words"].splitlines()]
    lines.append("The disagreement it settles:")
    lines += ["  " + line for line in state["impact"].splitlines()]
    return "\n".join(lines)


def command_decide(args, rulingBy=None):
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    word, rulingWords = split_decide_args(args)
    if state is None or state["stage"] not in ("impact-coder", "impact-review") or not word:
        return emit("stop", "decide needs a pending PLAN-IMPACT and one word: adopt, keep or discuss.")
    decision = DECISION_WORDS.get(word)
    if decision is None:
        return emit("stop", "decide takes adopt, keep or discuss.")
    if decision == "Discuss":
        return ask_user(repoRoot, "discuss this disagreement between the code and the plan with the user in plain "
                        "words. When the user chooses, invoke Skill code with `decide adopt --ruling \"<the user's "
                        "answer>\"` or `decide keep --ruling \"<the user's answer>\"`.", state["impact"])
    if not rulingWords:
        return emit("stop", f"decide {word} needs the user's answer, in their words: "
                    f"`decide {word} --ruling \"<the user's answer>\"`. Hand back and ask the main session for it.")

    if state.get("plan") and not (repoRoot / state["plan"]).is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")
    rulingAt = time.strftime("%Y-%m-%d %H:%M")
    state["ruling"] = {"decision": decision, "words": rulingWords, "by": rulingBy or git_user_name(repoRoot),
                       "at": rulingAt}
    if state.get("plan"):
        record_deviation(repoRoot, state)
    state["planImpact"] = resolved_plan_impact(state)
    # A ruling opens a new review: the round cap of the review that raised the question does not carry over.
    state["iter"] = 0

    if decision == PLAN_IMPACT_OPTIONS[0] and state.get("plan"):
        return emit_plan_edit_dispatch(repoRoot, state)
    emit_review_dispatch(repoRoot, state)


def git_user_name(repoRoot):
    return git_output(repoRoot, "config", "user.name") or "the user"


def criteria_file(repoRoot, state):
    # The plan's acceptance criteria live beside it. None when the plan has no criteria file.
    criteriaRel = str(pathlib.PurePath(state["plan"]).parent / "acceptance-criteria.md")
    if not (repoRoot / criteriaRel).is_file():
        return None
    return criteriaRel


def plan_edit_prompt(state, criteriaRel):
    ruling = state["ruling"]
    editScope = f"the plan file {state['plan']}" + (f" and its acceptance criteria file {criteriaRel}" if criteriaRel else "")
    lines = [
        f"Edit only {editScope}. In Phase {state['phase']}, the code and the plan disagreed:",
        "",
        state["impact"],
        "",
        f"The user ruled ({ruling['by']}, {ruling['at']}). The ruling, in the user's words:",
        "",
        ruling["words"],
        "",
        "Rewrite each step, Automated Verification command and Success Criteria line of the plan that the ruling "
        "contradicts, so that the plan states the ruling. Keep every other line as it is. Leave the "
        "`## Plan Deviations` section as it is. Edit no code and no test, and run no check.",
    ]
    if criteriaRel:
        lines += ["",
                  f"Rewrite each criterion in {criteriaRel} that the ruling changes, so that it states the ruling. Under "
                  f"each one you rewrite, add `Signed off by {ruling['by']}, {ruling['at']}: \"<the user's words on "
                  "this criterion>\"`. Keep every other criterion as it is."]
    lines += ["", "Report each line you changed as `<file>:<line number>: <new text>`."]
    return "\n".join(lines)


def emit_plan_edit_dispatch(repoRoot, state):
    # An adopted change stays only in Plan Deviations unless the steps that contradict it change too, and the
    # reviewer then reads the old step and raises the same disagreement again.
    criteriaRel = criteria_file(repoRoot, state)
    state.update({"stage": "plan-coder", "planEditBaseline": file_hashes(repoRoot)})
    save_state(repoRoot, state)

    prompt = plan_edit_prompt(state, criteriaRel)
    emit("dispatch", "The user adopted the plan change. Dispatch a coder to rewrite the plan steps and acceptance "
         "criteria it contradicts.",
         "NEXT: when the coder returns, run `python3 ~/.claude/scripts/code-step.py after-plan-edit`.",
         prompt=prompt, agent="coder")


def command_after_plan_edit(args):
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    if state is None or state["stage"] != "plan-coder":
        return emit("stop", "after-plan-edit ran with no plan edit pending. Run `start` first.")

    baseline = state.pop("planEditBaseline")
    changedNow = file_hashes(repoRoot)
    editedFiles = [name for name, digest in changedNow.items() if baseline.get(name) != digest]
    criteriaRel = criteria_file(repoRoot, state)
    strayFiles = [name for name in editedFiles if name not in (state["plan"], criteriaRel)]
    if strayFiles:
        state["files"] += [name for name in strayFiles if name not in state["files"]]
        state["flagged"].append("the plan-edit coder also changed " + ", ".join(strayFiles))
        state["exception"] = True

    planNote = f"The plan {state['plan']} now states the ruling."
    if criteriaRel in editedFiles:
        planNote += f" The acceptance criteria in {criteriaRel} changed too: read them before you stage."
    say(repoRoot, planNote)
    emit_review_dispatch(repoRoot, state)


def handoff_block(state):
    lines = ["handoff:", "  files:"]
    behaviorFallback = state["behavior"][0] if state.get("behavior") else None
    report = state.get("reportText", "")
    for path in state["files"]:
        lines.append(f"    - path: {path}")
        lines.append(f"      change: {state['changes'].get(path) or behaviorFallback or 'changed by the coder'}")
        notes = state["why"].get(path)
        if notes:
            lines.append("      why:")
            for note in notes:
                lines.append(f"        - lines: {note['lines']}")
                lines.append(f"          note: {note['note']}")
    if state.get("priorIssues"):
        lines.append("  prior-issues:")
        for priorIssue in state["priorIssues"]:
            lines.append(f"    - issue: {priorIssue['issue']}")
            lines.append("      status: fixed")
            lines.append(f"      file: {priorIssue['file'] or '-'}")
    lines.append(f"  tests-run: {state['testsRun']}")
    lines.append("  flagged: " + ("; ".join(state["flagged"]) if state["flagged"] else "none"))
    planImpact = state.get("planImpact", "none")
    if planImpact == "none":
        lines.append("  plan_impact: none")
    else:
        lines.append("  plan_impact: |")
        lines += ["    " + line for line in planImpact.splitlines()]
    lines.append(f"  iter: {state.get('iter', 0)}")
    if state.get("spec_iter"):
        lines.append(f"  spec_iter: {state['spec_iter']}")
    return "\n".join(lines)


def emit_review_dispatch(repoRoot, state):
    coderStages = ["coder"] + (["asks-coder"] if state.get("coderStage") == "asks-coder" else [])
    reports = [report for stage in coderStages for report in saved_messages(repoRoot, "coder", stage)]
    report = "\n\n".join(reports)
    untrackedText = git_output(repoRoot, "ls-files", "--others", "--exclude-standard") or ""
    untrackedFiles = set(untrackedText.split("\n"))
    # One behavior sentence describes one file. Across several files it tells the reviewer the wrong change.
    isOneFile = len(state["files"]) == 1
    behaviorFallback = state["behavior"][0] if state["behavior"] and isOneFile else None
    state["changes"] = {path: change_line(report, path, state["files"], behaviorFallback, path in untrackedFiles)
                        for path in state["files"]}
    header = ["mode: review-first", "caller: code", f"lane: {state['lane']}"]
    if state.get("plan"):
        header.append(f"plan: {state['plan']}")
        if state.get("phase"):
            header.append(f"phase: {state['phase']}")
    if state.get("modifier"):
        header.append(state["modifier"])
    prompt = "\n".join(header) + "\n\n" + handoff_block(state)
    state["stage"] = "review"
    # after-review reads only reports saved after this dispatch, so a report already acted on is not read again.
    reportsFile = state_dir(repoRoot) / "reports.jsonl"
    state["reviewReportsFloor"] = len(reportsFile.read_text().splitlines()) if reportsFile.exists() else 0
    state["lastReviewPrompt"] = prompt
    save_state(repoRoot, state)

    summary = ["Implemented: " + ("; ".join(state["behavior"]) or "see the diff.")]
    summary.append("Flagged: " + ("; ".join(state["flagged"]) if state["flagged"] else "none."))
    for path, notes in state["why"].items():
        summary += [f"  {path}:{note['lines']} - {note['note']}" for note in notes]
    summary.append("Auto-dispatching review to check the implementation before committing.")
    say(repoRoot, "\n".join(summary))
    emit("dispatch", "NEXT: when review-loop returns, run `python3 ~/.claude/scripts/code-step.py after-review`.",
         prompt=prompt, agent="review-loop", model="sonnet")


# ---------- hook ----------

def command_hook():
    try:
        event = json.load(sys.stdin)
        agentType = event.get("agent_type")
        if agentType not in ("coder", "review-loop"):
            return
        cwd = event.get("cwd") or "."
        state = load_state(cwd)
        if state is None or state["stage"] not in HOOK_STAGES:
            return
        sessionId = event.get("session_id")
        pinnedSession = state.get("sessionId")
        if sessionId and pinnedSession and sessionId != pinnedSession:
            return
        if sessionId and not pinnedSession and state["stage"] == "coder":
            state["sessionId"] = sessionId
            save_state(cwd, state)
        row = {"ts": time.time(), "agent_type": agentType, "agent_id": event.get("agent_id") or "unknown",
               "stage": state["stage"], "message": str((event.get("tool_input") or {}).get("message", ""))}
        with (state_dir(cwd) / "reports.jsonl").open("a") as reportsFile:
            reportsFile.write(json.dumps(row) + "\n")
    except Exception as error:
        print(f"code-step hook: {error}", file=sys.stderr)


# ---------- after-review ----------

def ends_packet_value(key, valueLines, line):
    # A scalar key owns one line. A list key owns its dash lines and their indented continuations; the first
    # unindented prose line after them is the loop's closing note, not another item.
    if key in SCALAR_PACKET_KEYS:
        return True
    if is_block_scalar(valueLines):
        return line[:1] not in (" ", "\t")
    isList = valueLines[0] == "" and len(valueLines) > 1 and valueLines[1].lstrip().startswith("-")
    isEmptyListKey = key in LIST_KEYS and valueLines == [""]
    return (isList or isEmptyListKey) and line[:1] not in (" ", "-", "[", "{", "]", "}", "\t")


SCALAR_PACKET_KEYS = ("status", "iter", "spec_iter", "load_bearing_clean")
BLOCK_INDICATOR = re.compile(r"^[|>][+-]?$")


def is_block_scalar(valueLines):
    return BLOCK_INDICATOR.match(valueLines[0].strip()) is not None


def packet_value(valueLines):
    # A `key: |` block keeps its text indented under the key: drop the indicator line and the indent.
    if is_block_scalar(valueLines):
        return textwrap.dedent("\n".join(valueLines[1:])).strip()
    return "\n".join(valueLines).strip()


def parse_packet(message):
    text = "\n".join(line for line in message.splitlines() if not line.strip().startswith("```"))
    fields = {}
    trailer = []
    key = None
    for line in text.splitlines():
        match = re.match(r"^([a-z_]+):[ \t]*(.*)$", line)
        isPacketKey = match is not None and match.group(1) in PACKET_KEYS
        if isPacketKey and match.group(1) not in fields:
            key = match.group(1)
            fields[key] = [match.group(2)]
        elif isPacketKey:
            key = None
            trailer.append(line)
        elif key and not line.strip() and is_block_scalar(fields[key]):
            fields[key].append("")
        elif key and not line.strip():
            if key in LIST_KEYS and fields[key][0] == "":
                continue
            key = None
            trailer.append("")
        elif key and ends_packet_value(key, fields[key], line):
            key = None
            trailer.append(line)
        elif key:
            fields[key].append(line)
        else:
            trailer.append(line)
    packet = {name: packet_value(value) for name, value in fields.items()}
    packet["trailer"] = "\n".join(trailer).strip()
    return packet


FLOW_KEYS = ["disposition", "finding", "file_line", "blocker", "question", "gate", "class", "reason", "item", "phase"]
FLOW_KEY_AT = re.compile(r"(?:^|,\s*)(" + "|".join(FLOW_KEYS) + r")\s*:\s*")


def unquote(text):
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def parse_flow_mapping(chunk):
    # The loop writes items as `{finding: "...", file_line: a.ts:1, blocker: false}`: YAML flow style, not JSON.
    body = chunk.strip()[1:-1]
    matches = list(FLOW_KEY_AT.finditer(body))
    if not matches:
        return None
    fields = {}
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(body)
        fields[match.group(1)] = unquote(body[match.end():end])
    return fields


def list_items(raw):
    raw = raw.strip()
    hasItems = re.search(r"^\s*-\s|\{", raw, re.M) is not None
    if raw == "" or (not hasItems and NONE_VALUE.match(raw)):
        return []
    try:
        loaded = json.loads(raw)
        return loaded if isinstance(loaded, list) else [loaded]
    except ValueError:
        pass
    items = []
    for chunk in re.split(r"^\s*-\s+", raw, flags=re.M):
        chunk = chunk.strip()
        if not chunk:
            continue
        flowFields = parse_flow_mapping(chunk) if chunk.startswith("{") and chunk.endswith("}") else None
        if flowFields:
            items.append(flowFields)
            continue
        pairs = dict(re.findall(r"^\s*(\w+):\s*(.+)$", chunk, re.M))
        items.append(pairs if pairs and all(name in FLOW_KEYS for name in pairs) else unquote(chunk))
    return items


def first_number(value):
    found = re.search(r"\d+", value or "")
    return int(found.group()) if found else 0


def item_text(item, *keys):
    if isinstance(item, dict):
        return " - ".join(str(item[key]) for key in keys if item.get(key))
    return str(item)


def render_packet(packet):
    lines = ["### Fixed"]
    fixed = list_items(packet.get("fixed", ""))
    fixed.sort(key=lambda item: not (isinstance(item, dict) and str(item.get("blocker", "")).lower() in ("true", "yes")))
    for item in fixed:
        isBlocker = isinstance(item, dict) and str(item.get("blocker", "")).lower() in ("true", "yes")
        lines.append(f"- {'[blocker] ' if isBlocker else ''}{item_text(item, 'finding', 'file_line')}")
    if not fixed:
        lines.append("- none")
    for heading, key in (("### Skipped as false positives", "skipped_fp"), ("### Nits", "nit"),
                         ("### Deferred to branch exit", "findings_remaining")):
        items = list_items(packet.get(key, ""))
        if items:
            lines.append(heading)
            lines += [f"- {item_text(item, 'finding', 'item', 'file_line', 'reason')}" for item in items]
    loadBearing = packet.get("load_bearing_clean", "")
    if loadBearing and loadBearing.lower() not in ("none", "omitted"):
        lines.append("Note: " + loadBearing)
    if packet.get("trailer"):
        lines.append(packet["trailer"])
    return "\n".join(lines)


def command_after_review(args):
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    if state is None or state["stage"] != "review":
        return emit("stop", "after-review ran with no review pending. Run `start` first.")
    messages = saved_messages(repoRoot, "review-loop", "review", state.get("reviewReportsFloor", 0))
    if not messages:
        return emit("stop", "No review-loop packet was saved. The SubagentHandback hook is not installed. Tell the user.")
    packet = parse_packet(messages[-1])
    status = packet.get("status", "").split()[0] if packet.get("status") else ""
    state["iter"] = first_number(packet.get("iter"))
    if packet.get("spec_iter"):
        state["spec_iter"] = first_number(packet["spec_iter"])
    state["packet"] = packet

    if status == "plan-impact" and not packet.get("plan_impact"):
        return emit("stop", "The review-loop reported plan-impact with no description. Show the user the raw packet.",
                    messages[-1])
    if status == "plan-impact":
        state.update({"stage": "impact-review", "impact": packet.get("plan_impact", "")})
        save_state(repoRoot, state)
        return emit_plan_impact_modal(state["impact"], repoRoot)
    if status == "critical-blocker":
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        return emit("stop", "Review found a critical blocker. Present these to the user. Do not mark the phase done.",
                    *["- " + str(item) for item in list_items(packet.get("blockers", ""))])
    if status == "cap-reached":
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        return emit("stop", "The review cap was reached. Report these findings to the user. Do not mark the phase "
                    "done. The session stays dirty, so git commit stays blocked.",
                    *["- " + item_text(item, "finding", "file_line") for item in
                      list_items(packet.get("findings_remaining", ""))])
    if status not in ("converged", "deferred"):
        return emit("stop", "The review-loop packet has no readable status. Show the user the raw packet.",
                    messages[-1])

    save_state(repoRoot, state)
    say(repoRoot, render_packet(packet))
    print("The review packet was saved for the user. Do not repeat it.")
    asks = list_items(packet.get("ask", ""))
    if asks:
        return present_asks(repoRoot, state, asks)
    finish_phase(repoRoot, state)


ASK_OUTCOMES = ("accepted", "rejected", "modified")


def preset_ask_outcome(repoRoot):
    # A pre-answered outcome for every review ask, for runs with no user (claude -p, bench): env var or a file in the state dir.
    word = os.environ.get("CODE_STEP_ASKS_OUTCOME", "").strip().lower()
    presetFile = state_dir(repoRoot) / "asks-outcome"
    if not word and presetFile.exists():
        word = presetFile.read_text().strip().lower()
    return word if word in ASK_OUTCOMES else None


def present_asks(repoRoot, state, asks):
    anchors = []
    for item in asks:
        fileLine = item.get("file_line", "") if isinstance(item, dict) else ""
        question = item.get("question", "") if isinstance(item, dict) else str(item)
        isSingleAnchor = re.match(r"^[^\s,;]+:\d+(-\d+)?$", fileLine) is not None
        if isSingleAnchor and shutil.which("nvim-jump"):
            anchors += ["--note", question[:120], fileLine]
    if anchors:
        run_command(["nvim-jump", *anchors], repoRoot)
    state["asks"] = asks
    presetOutcome = preset_ask_outcome(repoRoot)
    isNewAskAfterAsksCoder = presetOutcome and presetOutcome != "rejected" and state.get("asksApplied")
    if isNewAskAfterAsksCoder:
        print(f"{len(asks)} new review ask(s) came back after the asks coder ran. The pre-set outcome "
              f"'{presetOutcome}' does not cover them: they go to the user.")
        return ask_the_user(repoRoot, state, asks)
    if presetOutcome:
        print(f"{len(asks)} review ask(s) answered by the pre-set outcome '{presetOutcome}'. No question to the user:")
        say(repoRoot, "Review asks, answered by the pre-set outcome:\n" + "\n".join(
            f"{n + 1}. {item_text(item, 'finding', 'question')}" for n, item in enumerate(asks)))
        log_ask_outcomes(repoRoot, state, [presetOutcome] * len(asks))
        return apply_asks_or_finish(repoRoot, state, [presetOutcome] * len(asks), [None] * len(asks), clean_marked=False)
    ask_the_user(repoRoot, state, asks)


def ask_the_user(repoRoot, state, asks):
    state["stage"] = "asks"
    save_state(repoRoot, state)
    say(repoRoot, "\n".join([
        "## Question for the user", "",
        f"Main session: ask the user about each review ask below in plain text and wait for the answers. Each answer "
        f"is accepted, rejected or modified. Then invoke Skill code with the args `asks-done` and {len(asks)} outcome "
        "word(s), in order. After a modified outcome, add `--change \"<the user's change text>\"`.", "",
        *[f"{n + 1}. {item_text(item, 'finding', 'question')}" for n, item in enumerate(asks)]]))
    emit("ask-user", "The question for the user is in say.md.",
         "Run `bash ~/.claude/scripts/review-gate-mark clean` as its own Bash command now. Then hand back.")


def log_ask_outcomes(repoRoot, state, outcomes):
    branch = git_output(repoRoot, "branch", "--show-current") or "-"
    for item, outcome in zip(state["asks"], outcomes):
        fields = item if isinstance(item, dict) else {}
        fileLine = fields.get("file_line", "-:0")
        path, _, line = fileLine.partition(":")
        run_command(["bash", str(CLAUDE_DIR / "skills/review/log-review-finding"), "kind=finding",
                     f"repo={repoRoot.name}", f"branch={branch}", f"lane={state['lane']}", "scope=phase",
                     f"phase={state.get('phase') or '-'}", f"iter={state['iter']}", f"gate={fields.get('gate', 'code-reviewer')}",
                     "disposition=ask", f"class={fields.get('class', 'other')}", f"file={path}",
                     f"line={re.sub(r'[^0-9].*', '', line) or '0'}", "actioned=ask", f"ask_outcome={outcome}",
                     f"desc=ask resolved: {fields.get('question', '')[:100]}"], repoRoot)


def asks_coder_prompt(acceptedAsks):
    lines = ["Apply these review asks. The user accepted them. Change only what they name.", ""]
    for number, (item, outcome, changeText) in enumerate(acceptedAsks, 1):
        location = item.get("file_line", "") if isinstance(item, dict) else ""
        lines.append(f"{number}. [{outcome}] {item_text(item, 'finding', 'question')}"
                     + (f" ({location})" if location else ""))
        if changeText:
            lines.append(f"   The user's change: {changeText}")
    lines += ["", "Run the typecheck, and lint and tests for only the files you changed, once, after all edits. "
              "If an ask turns out architectural, report back and recommend /eng-spec."]
    return "\n".join(lines)


def apply_asks_or_finish(repoRoot, state, outcomes, changeTexts, clean_marked):
    # An accepted or modified ask is owed work: a coder applies it and a fresh review runs before the phase can finish.
    acceptedAsks = [[item, outcome, changeText] for item, outcome, changeText in zip(state["asks"], outcomes, changeTexts)
                    if outcome != "rejected"]
    if not acceptedAsks:
        state["stage"] = "review"
        save_state(repoRoot, state)
        return finish_phase(repoRoot, state, clean_marked=clean_marked)

    state.update({"stage": "asks-coder", "acceptedAsks": acceptedAsks, "asksApplied": True,
                  "asksBaseline": file_hashes(repoRoot)})
    save_state(repoRoot, state)
    model = "haiku" if state.get("modifier") == "+fast" else None
    emit("dispatch", "The user accepted review asks. Dispatch a coder to apply them. A fresh review runs after it "
         "and before the phase can finish.",
         "NEXT: when the coder returns, run `python3 ~/.claude/scripts/code-step.py after-coder`.",
         prompt=asks_coder_prompt(acceptedAsks), agent="coder", model=model)


def split_asks_done_args(args):
    # Outcome words in order, and the text after each `--change` flag, one per modified ask, in order.
    outcomes = []
    changeTexts = []
    position = 0
    while position < len(args):
        if args[position] == "--change":
            if position + 1 >= len(args):
                return outcomes, None
            changeTexts.append(args[position + 1])
            position += 2
            continue
        outcomes.append(args[position])
        position += 1
    return outcomes, changeTexts


def command_asks_done(args):
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    outcomes, givenChanges = split_asks_done_args(args)
    usage = ("asks-done needs one outcome per ask: accepted, rejected or modified. Each modified ask needs the user's "
             "change after it as `--change \"<text>\"`.")
    if state is None or state["stage"] != "asks" or len(outcomes) != len(state["asks"]) \
            or any(outcome not in ASK_OUTCOMES for outcome in outcomes) or givenChanges is None \
            or len(givenChanges) != outcomes.count("modified"):
        return emit("stop", usage)

    remainingChanges = iter(givenChanges)
    changeTexts = [next(remainingChanges) if outcome == "modified" else None for outcome in outcomes]
    log_ask_outcomes(repoRoot, state, outcomes)
    apply_asks_or_finish(repoRoot, state, outcomes, changeTexts, clean_marked=True)


# ---------- phase gates and boundary ----------

def command_skill_done(args):
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    if state is None or state["stage"] != "skill":
        return emit("stop", "skill-done ran with no closing-phase skill pending.")
    verdict = args[0].lower() if args else "pass"
    if verdict not in ("pass", "fail"):
        return emit("stop", "skill-done takes pass or fail.")
    if verdict == "fail":
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        return emit("stop", "The closing phase's check failed (a MISSING criterion, or an unmet Success Criteria). "
                    "Do not mark the phase done. Report what failed to the user.")
    finish_phase(repoRoot, state, skipVerification=True)


def command_verify(args):
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    if state is None or state["stage"] != "stopped" or state.get("stopReason") != "verification":
        return emit("stop", "verify ran with no failed Automated Verification pending.")
    finish_phase(repoRoot, state, clean_marked=True)


COMMAND_START = re.compile(r"^(cd |npm |npx |pnpm |yarn |git |node |python3? |pytest|ruff |bash |curl |make )")


def verification_command(line):
    # The first backticked span that starts like a shell command; the line may continue after it ("`npm run build` exits 0.").
    for span in re.findall(r"`([^`]+)`", line):
        if COMMAND_START.match(span):
            return span
    return None


def check_prohibition(repoRoot, command, code, output):
    # A git grep ban passes on exit 1 (no match) and fails on exit 0 (a hit). Any other exit is an error that stops.
    # A pipe form is judged by its output: empty or 0 passes.
    hitRows = len([row for row in output.splitlines() if row.strip()])
    if "|" in command:
        verdict = 0 if output.strip() in ("", "0") else 1
        hits = 0 if verdict == 0 else int(output) if output.strip().isdigit() else hitRows
    elif code == 1:
        verdict, hits = 0, 0
    elif code == 0:
        verdict, hits = 1, hitRows
    else:
        verdict, hits = code, 0
    run_command(["bash", str(SCRIPTS_DIR / "log-scan"), f"repo={repoRoot.name}", "scan=prohibition",
                 "stage=code-phase", f"exit={verdict}", f"candidates={hits}", f"confirmed={hits}",
                 f"branch={current_branch(repoRoot)}", f"note={command[:120]}"], repoRoot)
    return command, verdict, output


def run_verification_commands(repoRoot, phaseSection):
    results = []
    skipped = []
    timeout = int(os.environ.get("CODE_STEP_VERIFY_TIMEOUT", VERIFY_TIMEOUT_SECONDS))
    for line in verification_items(phaseSection, "Automated Verification"):
        command = verification_command(line)
        if command is None:
            continue
        if WHOLE_SUITE.match(command):
            skipped.append(command)
            continue
        code, output = run_command(command, repoRoot, timeout=timeout)
        if "git grep" in command:
            results.append(check_prohibition(repoRoot, command, code, output))
            continue
        results.append((command, code, output))
    return results, skipped


def mark_phase_done(planPath, number):
    text = planPath.read_text()
    updated = re.sub(rf"^- \[ \] (Phase {number}:)", r"- [x] \1", text, count=1, flags=re.M)
    planPath.write_text(updated)


def boundary_decision(state, entries, number):
    isLast = not [e for e in entries if not e["done"] and e["number"] != number]
    if isLast:
        return "C", "last phase"
    if number == "1":
        return "B", "low - Phase 1 calibration" if state["risk"] == "low" else state["risk"]
    if state.get("exception"):
        return "B", "low - exception" if state["risk"] == "low" else state["risk"]
    if state["risk"] == "low":
        return "A", "low"
    return "B", "high"


def finish_phase(repoRoot, state, clean_marked=False, skipVerification=False):
    gateActions = []
    if not clean_marked and not skipVerification:
        gateActions.append("run `bash ~/.claude/scripts/review-gate-mark clean` as its own Bash command")

    if not state.get("plan"):
        state["stage"] = "done"
        save_state(repoRoot, state)
        return emit("stop", "Planless task reviewed. Tell the user the result.", *[f"Then {a}." for a in gateActions])

    planPath = repoRoot / state["plan"]
    if not planPath.is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.",
                    *[f"Also {a}." for a in gateActions])

    planLines = planPath.read_text().splitlines()
    number = state["phase"]
    section = phase_text(planLines, number) if number is not None else "\n".join(planLines)
    section = section or ""
    verifyResults, skipped = ([], [])
    if not skipVerification:
        verifyResults, skipped = run_verification_commands(repoRoot, section)
    failed = [(command, code, output) for command, code, output in verifyResults if code != 0]
    if failed:
        state.update({"stage": "stopped", "stopReason": "verification"})
        save_state(repoRoot, state)
        return emit("stop", "Automated Verification failed. Do not mark the phase done. Report to the user:",
                    *[f"- `{command}` exit {code}: {output[-400:]}" for command, code, output in failed],
                    "When the failure is fixed, run `python3 ~/.claude/scripts/code-step.py verify`.",
                    *[f"Also {a}." for a in gateActions])

    manualItems = verification_items(section, "Manual Verification")
    agentVerified = [i for i in manualItems if "agent-verified" in i]
    humanOnly = [i for i in manualItems if i not in agentVerified]
    if number is not None:
        mark_phase_done(planPath, number)
    entries = phase_status_entries(planPath.read_text().splitlines())
    block, riskLabel = boundary_decision(state, entries, number)
    nextPending = [e for e in entries if not e["done"]]
    state["stage"] = "done"
    state["autoAdvance"] = block == "A"
    state.pop("stopReason", None)
    save_state(repoRoot, state)

    doneText = f"Phase {number} marked done in {state['plan']}." if number is not None \
        else f"The plan {state['plan']} is finished."
    doneLine = (f"{doneText} Verification run: "
                f"{len(verifyResults)} command(s) green ({'; '.join(c for c, _, _ in verifyResults) or 'none'}); "
                f"skipped as covered by the review loop: {len(skipped)}.")
    print(doneLine)
    say(repoRoot, doneLine)

    if block == "A":
        nextStart = "python3 ~/.claude/scripts/code-step.py start" + (f" {state['modifier']}" if state.get("modifier") else "")
        say(repoRoot, block_a(number, riskLabel, len(agentVerified), len(humanOnly), nextPending[0]["number"]))
        emit("auto-advance", "The user sees block A at the end of the turn. " + "; ".join(gateActions + [
             f"in the same response run `{nextStart}` for Phase " + nextPending[0]["number"]]) + ".")
        return
    blockText = block_b_or_c(block, number, riskLabel, state, agentVerified, humanOnly,
                             nextPending[0]["number"] if nextPending else None)
    say(repoRoot, blockText.replace("<<STAGE QUEUE>>", "(the /stage queue is printed above in this turn)"))
    emit("stop-block-" + block, *[f"First {a}." for a in gateActions],
         "Invoke the Skill tool with `stage` and print its queue verbatim. The user sees the rest of the phase-complete "
         "block at the end of the turn: do not write it. Then wait for the user. When they say continue, run "
         "`code-step.py start`.")


def block_a(number, riskLabel, agentCount, humanCount, nextNumber):
    return (f"Phase {number} complete - machine gates green (review ✓, execution ✓, automated-verification ✓). "
            f"Risk: low. Manual verification: {agentCount} agent-verified, {humanCount} human-only deferred to the "
            f"/verify-branch packet.\n-> Auto-advancing to Phase {nextNumber} in-session (no /clear; interrupt anytime).")


def block_b_or_c(block, number, riskLabel, state, agentVerified, humanOnly, nextNumber):
    behavior = state.get("behavior") or []
    lastText = f"Phase {number} complete (last phase)." if number is not None else "The plan is complete."
    parts = [f"Phase {number} complete. Risk: {riskLabel}. Phase-level sign-off requested." if block == "B"
             else lastText, ""]
    if behavior:
        parts += ["Behavior delta (observable change + its proof, max 3 - no internals, no paths):",
                  *[f"- {line}" for line in behavior[:3]], ""]
    parts += ["Read first (/stage queue, blast-radius order):", "<<STAGE QUEUE>>", ""]
    if agentVerified:
        parts += ["Agent-verified (evidence in the plan):", *agentVerified, ""]
    if humanOnly:
        parts += ["Human-only verification remaining:", *humanOnly, ""]
    if block == "B":
        step1 = "Read the queue (`]k`/`[k` in nvim); spot-check the evidence lines; run the human-only items." \
            if (agentVerified or humanOnly) else "Read the /stage queue."
        parts += ["Next:", f"  1. {step1}",
                  f"  2. Stage what you've read, then run /clear and /code to start Phase {nextNumber} fresh. "
                  "To keep this context, confirm here.", "", "Or give feedback now for revisions to Phase " + number + "."]
    else:
        parts += ["All phases complete. Next: /verify-branch (completeness + review packet; includes the remaining "
                  "human-only checks), then you open the PR."]
    return "\n".join(parts)


def command_status():
    state = load_state(repo_root())
    print(json.dumps(state, indent=1) if state else "no code-step state")


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    args = sys.argv[2:]
    verbs = {"start": command_start, "after-coder": command_after_coder, "decide": command_decide,
             "after-plan-edit": command_after_plan_edit, "after-review": command_after_review,
             "asks-done": command_asks_done, "skill-done": command_skill_done, "verify": command_verify}
    # These verbs open a new /code run after the user answered. The last run's say.md text was already handed back.
    resumeVerbs = ("decide", "asks-done", "verify")
    if verb == "hook":
        return command_hook()
    if verb == "say-hook":
        return command_say_hook()
    if verb == "status":
        try:
            return command_status()
        except StateFileError as error:
            return print(error)
    if verb not in verbs:
        sys.exit("usage: code-step.py start|after-coder|decide|after-plan-edit|after-review|asks-done|skill-done|verify"
                 "|hook|status")
    if verb in resumeVerbs:
        clear_say(repo_root())
    try:
        verbs[verb](args)
    except StateFileError as error:
        emit("stop", f"{error}. Tell the user to delete that file, then run `start`.")


if __name__ == "__main__":
    main()
