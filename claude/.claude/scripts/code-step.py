#!/usr/bin/env python3
"""code-step.py: the routing of /code as a script. The forked Sonnet subagent of /code runs one verb, reads its
ACTION lines, does exactly that, and runs the next verb. The script builds every prompt and every argument.

  code-step.py start [<plan>] [+fast|+deep] [--phase <id>]
                                                next phase of the plan (or the named one): checks, gate, packet, the
                                                exact coder dispatch. `start --help` prints usage.
  code-step.py start --task "<text>"           planless work: the coder dispatch without gate or packet
  code-step.py after-coder                      wait for the coder's hand-back, clear the gate, build the exact
                                                review-loop dispatch (or the plan-disagreement modal)
  code-step.py decide <adopt|keep> --by <user|session> --ruling "<the words>"
                                                only --by user is the user's own word: a session ruling never changes a criterion
  code-step.py decide discuss                   ask the user how to rule when the code and the plan disagree; records nothing
  code-step.py after-plan-edit                  the coder rewrote the plan to an adopted change: build the review dispatch
  code-step.py after-review                    route on the loop packet; on converged/deferred also run the phase gates
  code-step.py asks-done <outcome>...           log the user's answer to each ask[] entry, then run the phase gates
  code-step.py skill-done <pass|fail>          a closing phase's skill returned: mark it done (pass) or stop (fail)
  code-step.py verify                           re-run the phase gates after a failed Automated Verification was fixed
  code-step.py review-again                     dispatch the review loop again on the same diff, after its packet did not parse
  code-step.py tick <phase id>                  mark a phase done that the user finished outside /code
  code-step.py hook                             PreToolUse hook on SubagentHandback: save coder and review-loop messages
  code-step.py stop-hook                        SubagentStop hook: keep the /code fork from stopping while a dispatch is open
  code-step.py plan-hook                        PostToolUse hook on Edit|Write: reject a plan edit that does not parse
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
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import plan_format
import script_utils

CLAUDE_DIR = pathlib.Path(os.environ.get("CODE_STEP_CLAUDE_DIR", pathlib.Path.home() / ".claude"))
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
SELF_COMMAND = "python3 " + str(pathlib.Path(__file__).resolve())
INSTALLED_COMMAND = "python3 ~/.claude/scripts/code-step.py"
PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]
DECISION_WORDS = {"adopt": PLAN_IMPACT_OPTIONS[0], "keep": PLAN_IMPACT_OPTIONS[1], "discuss": PLAN_IMPACT_OPTIONS[2]}
CLOSING_TITLE_END = r"\b(?!\s*\w)"
CLOSING_PHASES = [
    (re.compile(r"^Refactor pass" + CLOSING_TITLE_END, re.I), "/refactor +deep"),
    (re.compile(r"^Test audit" + CLOSING_TITLE_END, re.I), "/test-audit"),
    (re.compile(r"^Verify pass" + CLOSING_TITLE_END, re.I), "/verify-branch"),
    (re.compile(r"^Recap" + CLOSING_TITLE_END, re.I), "/branch-recap"),
]
HANDBACK_WAIT_SECONDS = 570
HANDBACK_POLL_SECONDS = 2
HANDBACK_TOTAL_WAIT_MULTIPLE = 3
FRESH_CALL_AFTER_SECONDS = 60
FORK_STOP_BLOCK_LIMIT = 2
BASH_TIMEOUT_MS = 600000
CODER = "coder"
REVIEW_LOOP = "review-loop"
GATE_RESULTS_THAT_END_THE_WAIT = ("pass", "cap")
START_USAGE = ('usage: code-step.py start [<plan>] [+fast|+deep] [--phase <id>]\n'
               '       code-step.py start --task "<task text>"\n'
               '--phase <id> starts the named phase. Text that follows the plan (or comes first, when there is no '
               'plan file, ticket id or directory) is the task text. A flag before it, or after a plan, must be '
               'known. --take-over starts over a run that another live session left open in this checkout.')
OTHER_SESSION_LIVE_SECONDS = 2 * 60 * 60
WAITING_STAGES = ("asks", "impact-coder", "impact-review", "skill", "plan-coder")
ASKS_DONE_USAGE = ("asks-done needs one outcome per ask: accepted, rejected or modified. Each modified ask needs the "
                   "user's change after it as `--change \"<text>\"`.")
# The state each verb needs: the stages it may run at, the stop reasons it accepts when the stage is "stopped", and the
# stop text when the state is anything else. `start` and `tick` run at any stage and are not in the table.
STAGE_GUARDS = {
    "after-coder": {"stages": ("coder", "asks-coder"),
                    "message": "after-coder ran with no coder dispatch pending. Run `start` first."},
    "decide": {"stages": ("impact-coder", "impact-review"),
               "message": "decide needs a pending PLAN-IMPACT and one word: adopt, keep or discuss."},
    "review-again": {"stages": ("stopped",), "stopReasons": ("invalid-packet",),
                     "message": "review-again ran with no unreadable review packet pending."},
    "after-plan-edit": {"stages": ("plan-coder",),
                        "message": "after-plan-edit ran with no plan edit pending. Run `start` first."},
    "after-review": {"stages": ("review",), "message": "after-review ran with no review pending. Run `start` first."},
    "asks-done": {"stages": ("asks",), "message": ASKS_DONE_USAGE},
    "skill-done": {"stages": ("skill",), "message": "skill-done ran with no closing-phase skill pending."},
    "verify": {"stages": ("stopped",), "stopReasons": ("verification", "plan-format"),
               "message": "verify ran with no failed Automated Verification or unparsed Manual Verification pending."},
}
RESUMABLE_STOP_REASONS = STAGE_GUARDS["verify"]["stopReasons"] + STAGE_GUARDS["review-again"]["stopReasons"]
RESUME_LINE = "When the {noun} is fixed, run `python3 ~/.claude/scripts/code-step.py {verb}`."
VERIFY_TIMEOUT_SECONDS = 600
TIMEOUT_EXIT_CODE = 124
HOOK_STAGES = ("coder", "review", "asks-coder", "plan-coder")
FORK_AGENT_TYPE = "general-purpose"
SAY_MAX_AGE_SECONDS = 6 * 3600
TICKET_ID = re.compile(r"^[A-Za-z]+-\d+$")
CARGO_CLIPPY = "cargo clippy --all-targets -- -D warnings"
TYPECHECK_SCRIPTS = ["typecheck", "type-check", "check-types", "tsc"]
SCRIPT_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mts", ".mjs")
TEST_SUFFIXES = ".test.ts,.test.tsx,.spec.ts,.spec.tsx,.test.js,.test.jsx"
TEST_FILE = re.compile(r"\.(test|spec)\.|(^|/)test_[^/]*\.py$|_test\.py$")
BARE_CARGO_MANIFEST = re.compile(r"`(Cargo\.toml)`")
PATH_IN_BACKTICKS = re.compile(r"`([\w.@-]+(?:/[\w.@\[\]()-]+)+\.\w+)(?::\d+(?:-\d+)?)?`")
WHOLE_SUITE = re.compile(r"^(?:(?:cd \S+ && )?(?:npm|pnpm|yarn) (?:run )?(?:test|lint)"
                         r"|(?:cd \S+ && )?npx (?:vitest|jest)(?: run)?|(?:python3 -m )?pytest|ruff check)$")


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
    code, output = run_command(["git", "-c", "core.quotepath=false", *args], cwd)
    return output if code == 0 else None


def git_names(cwd, *args):
    # Names from a git command that takes -z: a name with a non-ASCII or special character comes back as it is.
    output = git_output(cwd, *args, "-z")
    return [name for name in (output or "").split("\0") if name]


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


def latest_coder_row(repoRoot, stage, since=None):
    # The saved row of the coder dispatched last: the newest row of this stage that the hand-back gate let through.
    # Rows of earlier coders of the same stage are not part of it, and with `since` (the dispatch time) neither is a
    # row saved before that dispatch. None when no such row exists.
    reportsFile = state_dir(repoRoot) / "reports.jsonl"
    if not reportsFile.exists():
        return None
    latest = None
    for line in reportsFile.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if not isinstance(row, dict) or row.get("agent_type") != CODER or row.get("stage") != stage:
            continue
        if since is not None and not (isinstance(row.get("ts"), (int, float)) and row["ts"] > since):
            continue
        if coder_gate_allows(repoRoot, row.get("agent_id") or "unknown"):
            latest = row
    return latest


def latest_coder_message(repoRoot, stage, since=None):
    row = latest_coder_row(repoRoot, stage, since)
    return None if row is None else row.get("message", "")


def with_earlier_report(state, latestReport):
    # An addendum coder of the same phase run reports on top of the coder before it: both reports describe the change.
    # None when there is no latest report, so a missing hand-back still reads as missing.
    if latestReport is None:
        return None
    return "\n\n".join(filter(None, [state.get("earlierCoderReport"), latestReport]))


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


def session_pin():
    # The id of the session that runs /code. The fork sees its parent's id here, and hook events carry the same id.
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or None


def head_commit(repoRoot):
    head = git_output(repoRoot, "rev-parse", "HEAD")
    return head.strip() if head else None


def committed_since(repoRoot, baseHead):
    # Files the coder committed itself since the phase started. A commit leaves no dirty file behind, so the dirty
    # list alone would call the phase empty.
    if not baseHead or head_commit(repoRoot) in (None, baseHead):
        return []
    return git_names(repoRoot, "diff", "--name-only", baseHead, "HEAD")


def uncommitted_files(repoRoot, previous):
    # The files of the previous phase's commit line that are still dirty.
    files = previous.get("commitFiles") or []
    if not files:
        return []
    return git_names(repoRoot, "status", "--porcelain", "--", *files)


def abandon_open_dispatch(repoRoot, previous):
    # A run that starts over leaves no open dispatch behind: the stage becomes stopped and dispatchAt goes. The
    # baseline stays, so a restart of the same phase keeps its own-files record.
    if previous.get("dispatchAt") is None or previous.get("stage") not in HOOK_STAGES:
        return
    abandoned = dict(previous)
    abandoned.pop("dispatchAt")
    abandoned["stage"] = "stopped"
    save_state(repoRoot, abandoned)


def open_dispatch(state):
    # A dispatch is open from here until the dispatched agent's hand-back row is newer than dispatchAt.
    state["dispatchAt"] = time.time()
    state.pop("forkDenied", None)
    state.pop("forkStopBlocks", None)


def timed_command(verb):
    return f"`{INSTALLED_COMMAND} {verb}` as a Bash call with timeout {BASH_TIMEOUT_MS}"


def next_after(verb):
    return f"NEXT: right after the Agent call, run {timed_command(verb)}."


def expected_agent(state):
    return REVIEW_LOOP if state.get("stage") == "review" else CODER


def ask_text(item):
    # The shared reader copies a finding into the question (and the reverse) when only one is given: show it once.
    return script_utils.joined_distinct([str(item.get("finding") or ""), str(item.get("question") or "")])


def load_handback():
    # The shared hand-back reader is imported where it is used. When it is missing the caller reports that and stops.
    try:
        import handback
    except ImportError as error:
        return None, f"handback.py could not be imported ({error}); install it beside code-step.py"
    return handback, None


def handback_store_row(state):
    # The review-loop hand-back the shared store holds for the pinned session, or None.
    sessionId = state.get("sessionId")
    module, _ = load_handback()
    if module is None or not sessionId:
        return None
    try:
        return module.latest(sessionId)["handback"]
    except (OSError, ValueError, KeyError):
        return None


def coder_gate_allows(repoRoot, agentId):
    # The coder's hand-back counts once the hand-back gate let it through (pass) or gave up (cap). With no gate set
    # there is nothing to wait for. A deny sends the coder back to work, so its row is not the report.
    try:
        gate = gate_results(repoRoot)
    except ValueError:
        return True
    if gate is None:
        return True
    result = (gate.get("coders") or {}).get(agentId, {}).get("result")
    return result in GATE_RESULTS_THAT_END_THE_WAIT


def latest_handback_row(repoRoot, state, agentType, since):
    # The one source of the wait and of the fork denial: the newest hand-back row of this agent type after `since`.
    # A row without a timestamp is old. A state with no pinned session claims no hand-backs.
    if not state.get("sessionId"):
        return None
    rows = []
    reportsFile = state_dir(repoRoot) / "reports.jsonl"
    if reportsFile.exists():
        for line in reportsFile.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict) and row.get("agent_type") == agentType:
                rows.append(row)
    if agentType == REVIEW_LOOP:
        storeRow = handback_store_row(state)
        if isinstance(storeRow, dict):
            rows.append(storeRow)
    fresh = [row for row in rows if isinstance(row.get("ts"), (int, float)) and row["ts"] > since]
    if agentType == CODER:
        fresh = [row for row in fresh if coder_gate_allows(repoRoot, row.get("agent_id") or "unknown")]
    return max(fresh, key=lambda row: row["ts"]) if fresh else None


def dispatch_time_text(since):
    return datetime.datetime.fromtimestamp(since).isoformat(timespec="seconds")


def wait_for_handback(repoRoot, state, verb, longChecksFollow=False):
    # Nested Agent calls return at once, so the verb that follows a dispatch waits here for the hand-back row.
    # CODE_STEP_WAIT_SECONDS=0 skips the wait. Returns False after emitting the line that says to run the verb again,
    # or a stop once the dispatch is older than HANDBACK_TOTAL_WAIT_MULTIPLE waits. longChecksFollow: when the wait
    # took longer than FRESH_CALL_AFTER_SECONDS, return False so the checks after it start in a call of their own.
    limit = float(os.environ.get("CODE_STEP_WAIT_SECONDS", HANDBACK_WAIT_SECONDS))
    since = state.get("dispatchAt")
    if limit <= 0 or since is None:
        return True
    interval = float(os.environ.get("CODE_STEP_POLL_SECONDS", HANDBACK_POLL_SECONDS))
    agentType = expected_agent(state)
    totalCap = limit * HANDBACK_TOTAL_WAIT_MULTIPLE
    isPastCap = time.time() - since > totalCap
    waitStarted = time.time()
    # The state is read again on each poll: a hook may pin the session while the wait runs.
    found = script_utils.wait_for(lambda: latest_handback_row(repoRoot, load_state(repoRoot) or state, agentType, since),
                                  0 if isPastCap else limit, interval)
    if found:
        waited = time.time() - waitStarted
        threshold = float(os.environ.get("CODE_STEP_FRESH_CALL_SECONDS", FRESH_CALL_AFTER_SECONDS))
        if longChecksFollow and waited > threshold:
            emit("wait", f"The report arrived after {waited:.0f} seconds; run the same command again so the checks "
                 f"after it start in a call of their own: {timed_command(verb)}.")
            return False
        return True
    if time.time() - since > totalCap:
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        emit("stop", f"The {agentType} dispatched at {dispatch_time_text(since)} has not handed back in "
             f"{time.time() - since:.0f} seconds (the cap is {totalCap:g}). It may have died or been stopped. Do not "
             "dispatch it again and do not wait longer. Tell the user.")
        return False
    emit("wait", f"The dispatched agent has not handed back after {limit:g} seconds. Do not dispatch it again and do "
         f"not hand back. To keep waiting, run the same command again: `{INSTALLED_COMMAND} {verb}` (Bash timeout "
         f"{BASH_TIMEOUT_MS}).")
    return False


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
        print("BACKGROUND: no. Never set run_in_background. The Agent call returns at once: do not wait for its "
              "result; the NEXT verb waits for the report.")
    for line in lines:
        print(line)
    if prompt is not None:
        print("PROMPT (pass it verbatim, add and remove nothing):")
        print("-----BEGIN PROMPT-----")
        print(own_path(prompt))
        print("-----END PROMPT-----")


# ---------- plan parsing ----------

def closing_skill(title):
    return next((skill for pattern, skill in CLOSING_PHASES if pattern.search(title)), None)


def parse_plan(planLines):
    return plan_format.parse_plan(planLines, closing_skill)


def ordered_pending(entries):
    pending = [entry for entry in entries if not entry["done"]]
    return [e for e in pending if not e["closing"]] + [e for e in pending if e["closing"]]


def reopen_closing_phases(planPath):
    planLines = planPath.read_text().split("\n")
    reopened = [e for e in parse_plan(planLines)["entries"] if e["closing"] and e["done"]]
    for entry in reopened:
        planLines[entry["line"]] = re.sub(r"\[[xX]\]", "[ ]", planLines[entry["line"]], count=1)
    planPath.write_text("\n".join(planLines))
    return [entry["number"] for entry in reopened]


def added_phase_lines(repoRoot, state):
    before = state.get("phaseText")
    if before is None or not state.get("plan"):
        return None
    planLines = (repoRoot / state["plan"]).read_text().splitlines()
    after = phase_text(planLines, state["phase"])
    if after is None or after == before:
        return None
    added = script_utils.lines_added(before.splitlines(), after.splitlines())
    return {"text": after, "added": added} if added else None


def command_plan_hook():
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            return
        cwd = event.get("cwd") or "."
        toolInput = event.get("tool_input") or {}
        editedPath = toolInput.get("file_path") if isinstance(toolInput, dict) else None
        if not isinstance(cwd, str) or not isinstance(editedPath, str) or not editedPath:
            return
        state = load_state(cwd)
        if state is None or not state.get("plan"):
            return
        planPath = pathlib.Path(cwd) / state["plan"]
        if pathlib.Path(editedPath).resolve() != planPath.resolve():
            return
        planLines = planPath.read_text().splitlines()
        plan = parse_plan(planLines)
        if plan["failures"]:
            print(plan_failure_message(plan, state["plan"]), file=sys.stderr)
            sys.exit(2)
        manualFailure = manual_format_failure(planLines, state["plan"])
        if manualFailure:
            print(manualFailure, file=sys.stderr)
            sys.exit(2)
    except ValueError:
        return
    except (OSError, StateFileError) as error:
        print(f"code-step plan-hook: {error}", file=sys.stderr)


def plan_failure_rows(plan, planName):
    return [f"{planName}:{f['line']}: {f['kind']}: {f['detail']}" for f in plan["failures"]]


def plan_failure_message(plan, planName):
    rows = plan_failure_rows(plan, planName)
    return "The plan's Phase Status does not parse. Report each line to the user and stop:\n" + "\n".join(rows)


def phase_manual_items(planLines, number, planName):
    # The grammar reads the whole plan, so a PlanFormatError names the line in the file. A phase keeps its own items.
    items = plan_format.manual_verification("\n".join(planLines), planName)
    if number is None:
        return items
    return [item for item in items if item["phase"] == str(number)]


def manual_format_message(error, resumeLine=""):
    message = ("The plan's Manual Verification section does not parse. Do not mark the phase done. Report to the "
               f"user and stop:\n{error}")
    return message + ("\n" + resumeLine if resumeLine else "")


def manual_format_failure(planLines, planName, resumeLine=""):
    # The stop message for a Manual Verification section the grammar does not parse, or None when all parse.
    try:
        plan_format.manual_verification("\n".join(planLines), planName)
    except plan_format.PlanFormatError as error:
        return manual_format_message(error, resumeLine)
    return None


def phase_text(planLines, number):
    section = plan_format.phase_section(planLines, number)
    if section is None:
        return None
    return "\n".join(planLines[section["start"]:section["end"]])


def command_plan(args):
    if len(args) < 2 or args[0] not in ("check", "parse"):
        sys.exit("usage: code-step.py plan check|parse <path>")
    planLines = pathlib.Path(args[1]).read_text().splitlines()
    plan = parse_plan(planLines)
    if args[0] == "parse":
        return print(json.dumps(plan, indent=1))
    for row in plan_failure_rows(plan, args[1]):
        print(row)
    manualFailure = manual_format_failure(planLines, args[1])
    if manualFailure:
        print(manualFailure)
    sys.exit(1 if plan["failures"] or manualFailure else 0)


def automated_verification_items(phaseSection):
    items = []
    inside = False
    for line in phaseSection.splitlines():
        if line.startswith("#### "):
            inside = line.startswith("#### Automated Verification")
            continue
        if re.match(r"#{1,3} ", line) or line.strip() == "---":
            inside = False
        if inside and re.match(r"^- \[[ x]\]", line):
            items.append(line)
    return items


# ---------- gate derivation ----------

def nearest_directory_with(repoRoot, relPath, manifestName):
    manifest = script_utils.nearest_file_upward((repoRoot / relPath).parent, manifestName, repoRoot)
    return manifest.parent if manifest else None


def in_directory(command, packageRel):
    return f"cd {shlex.quote(packageRel)} && {command}" if packageRel else command


def script_package_commands(repoRoot, packageDir, paths):
    packageJson = json.loads((packageDir / "package.json").read_text())
    scripts = packageJson.get("scripts", {})
    dependencies = {**packageJson.get("dependencies", {}), **packageJson.get("devDependencies", {})}
    packageRel = script_utils.directory_relative_to(repoRoot, packageDir)
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


def cargo_commands(repoRoot, paths):
    crateDirs = []
    for path in paths:
        if not (path.endswith(".rs") or pathlib.PurePosixPath(path).name == "Cargo.toml"):
            continue

        crateDir = nearest_directory_with(repoRoot, path, "Cargo.toml")
        if crateDir is not None and crateDir not in crateDirs:
            crateDirs.append(crateDir)

    commands = []
    for crateDir in crateDirs:
        crateRel = script_utils.directory_relative_to(repoRoot, crateDir)
        commands.append(in_directory(CARGO_CLIPPY, crateRel))
    return commands


def derive_gate_commands(repoRoot, phaseSection):
    paths = []
    for match in PATH_IN_BACKTICKS.finditer(phaseSection):
        if match.group(1) not in paths:
            paths.append(match.group(1))

    byPackage = {}
    for path in paths:
        packageDir = nearest_directory_with(repoRoot, path, "package.json")
        if packageDir is not None:
            byPackage.setdefault(packageDir, []).append(path)

    commands = []
    for packageDir, packagePaths in byPackage.items():
        commands += script_package_commands(repoRoot, packageDir, packagePaths)
    rootManifests = BARE_CARGO_MANIFEST.findall(phaseSection)
    commands += cargo_commands(repoRoot, paths + rootManifests)
    commands += python_commands(repoRoot, paths)
    return commands


# ---------- start ----------

def file_hashes(repoRoot):
    tracked = git_names(repoRoot, "diff", "--name-only", "HEAD")
    untracked = git_names(repoRoot, "ls-files", "--others", "--exclude-standard")
    hashes = {}
    for name in sorted(set(tracked + untracked)):
        # A deleted file has no content to hash: its hash is None, which still differs from a baseline that had it.
        hashes[name] = git_output(repoRoot, "hash-object", name) if (repoRoot / name).exists() else None
    return hashes


def usage_error(message):
    print(f"code-step.py start: {message}\n{START_USAGE}", file=sys.stderr)
    sys.exit(2)


def parse_start_args(args):
    # Flags are read left to right up to the first word that is not a plan file, ticket id or directory: that word
    # and everything after it is task text, as is everything after --task. --help prints usage and exits 0 before
    # any state is touched; an unknown flag, and --phase without an id, exits 2.
    modifiers = []
    planArgs = []
    taskText = None
    phaseId = None
    takeOver = False
    position = 0
    while position < len(args):
        word = args[position]
        if word == "--take-over":
            takeOver = True
        elif word == "--task":
            taskText = " ".join(args[position + 1:])
            break
        elif word in ("+fast", "+deep"):
            modifiers.append(word)
        elif word in ("--help", "-h"):
            print(START_USAGE)
            sys.exit(0)
        elif word == "--phase":
            if position + 1 >= len(args) or args[position + 1].startswith("-"):
                usage_error("--phase needs a phase id")
            phaseId = args[position + 1]
            position += 1
        elif word.startswith("-") and len(word) > 1:
            usage_error(f"unknown flag {word}")
        elif looks_like_plan_argument(word):
            planArgs.append(word)
        else:
            taskText = " ".join(args[position:])
            break
        position += 1
    if taskText is not None and planArgs and "--task" not in args:
        usage_error("task text after a plan. Put the task text after --task, or leave the plan out")
    modifier = "+deep" if "+deep" in modifiers else "+fast" if modifiers else None
    return modifier, planArgs, taskText, phaseId, takeOver


def state_file_age_seconds(repoRoot):
    try:
        return time.time() - (state_dir(repoRoot) / "state.json").stat().st_mtime
    except OSError:
        return None


def other_session_run_age(repoRoot, previous):
    # Seconds since the last sign of life of a run that a different, pinned session owns, or None when no such run
    # is open. A run with an open dispatch (the coder, the plan-edit coder or the review-loop) ages from the dispatch.
    # A run that waits (for the user, for a closing skill, or stopped on a fix the user makes) ages from the last
    # change of the state file.
    # A run older than OTHER_SESSION_LIVE_SECONDS is abandoned by the caller.
    owner = previous.get("sessionId")
    if not owner or owner == session_pin():
        return None
    stage = previous.get("stage")
    if previous.get("dispatchAt") is not None and stage in HOOK_STAGES:
        return time.time() - previous["dispatchAt"]
    isStoppedForFix = stage == "stopped" and previous.get("stopReason") in RESUMABLE_STOP_REASONS
    if stage in WAITING_STAGES or isStoppedForFix:
        return state_file_age_seconds(repoRoot)
    return None


def looks_like_plan_argument(word):
    path = pathlib.Path(word)
    return looks_like_plan_path(word) or TICKET_ID.match(word) is not None or path.is_file() or path.is_dir()


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


def stop_while_plan_edit_coder_is_out(repoRoot, state, verbText):
    # A restore or a drop of the saved criteria while the plan-edit coder is still out would leave its later write
    # unchecked. Returns True after printing the stop, with no state changed.
    if state.get("stage") != "plan-coder" or not is_dispatch_open(repoRoot, state):
        return False
    emit("stop", "The plan-edit coder has not reported yet, so the saved acceptance criteria stay as they are. Run "
         "`! python3 ~/.claude/scripts/code-step.py after-plan-edit` from the repo root first: it waits for the "
         f"report and restores the criteria. Then run `{verbText}` again. Tell the user.")
    return True


def command_start(args):
    modifier, planArgs, taskText, phaseId, takeOver = parse_start_args(args)
    repoRoot = repo_root()
    os.chdir(repoRoot)
    previous = load_state(repoRoot) or {}
    branch = current_branch(repoRoot)
    ageSeconds = other_session_run_age(repoRoot, previous)
    if not takeOver and ageSeconds is not None and ageSeconds < OTHER_SESSION_LIVE_SECONDS:
        phaseName = f"Phase {previous['phase']} of " if previous.get("phase") is not None else ""
        lastActive = datetime.datetime.fromtimestamp(time.time() - ageSeconds).strftime("%H:%M")
        liftsAt = datetime.datetime.fromtimestamp(time.time() - ageSeconds + OTHER_SESSION_LIVE_SECONDS)
        takeOverArgs = " ".join(["--take-over", *args])
        return emit("stop", f"Another Claude session has a /code run open in this checkout: {phaseName}"
                    f"{previous.get('plan') or 'a task with no plan'}. Starting here would cancel it. Tell the user to "
                    "run this work in a git worktree. "
                    f"Last active {lastActive}, {int(ageSeconds // 60)} min ago in another session; this block lifts "
                    f"at {liftsAt.strftime('%H:%M')}. If the user says that session has ended, invoke Skill code with "
                    f"`{takeOverArgs}`.")

    if stop_while_plan_edit_coder_is_out(repoRoot, previous, " ".join(["start", *args])):
        return

    # The owner check above runs first: a restore never touches a state that another live session owns.
    # The state is saved only when a saved copy was restored or dropped, and then under this session.
    criteriaMessage = None
    if previous.get("criteriaGuard") is not None:
        criteriaMessage = settle_criteria_guard(repoRoot, previous, branch)
        previous["sessionId"] = session_pin()
        save_state(repoRoot, previous)

    isAutoAdvanceTextPending = previous.get("stage") == "done" and previous.get("autoAdvance")
    isOldTextStale = previous.get("stage") is not None and not isAutoAdvanceTextPending
    if isOldTextStale or taskText is not None:
        clear_say(repoRoot)

    if criteriaMessage:
        say(repoRoot, criteriaMessage)

    if isAutoAdvanceTextPending and uncommitted_files(repoRoot, previous):
        return emit("stop", "The previous phase's files are not committed yet, so the next phase would take them as "
                    "its own. Run the commit line, then run `start` again:", previous.get("commitLine", ""))
    abandon_open_dispatch(repoRoot, previous)

    if taskText is not None:
        return start_planless(repoRoot, modifier, taskText, branch)

    planArg = planArgs[0] if planArgs else None
    lane = previous.get("lane", "code")
    isUnknownArg = planArg is not None and not pathlib.Path(planArg).is_file()
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

    plan = parse_plan(planLines)
    if plan["failures"]:
        return emit("stop", plan_failure_message(plan, planRel))
    manualFailure = manual_format_failure(planLines, planRel, RESUME_LINE.format(noun="section", verb="start"))
    if manualFailure:
        return emit("stop", manualFailure)

    entries = plan["entries"]
    hasPhases = bool(plan["sections"])
    if not entries and hasPhases:
        return emit("judgment", "The plan has phases but no '## Phase Status' section. Use `git status` and each "
                    "phase's success criteria to pick the next phase, tell the user to backfill the section, then "
                    "run `code-step.py start` again after adding it.")
    pending = ordered_pending(entries)
    if phaseId is not None:
        entry = next((e for e in entries if e["number"] == phaseId), None)
        if entry is None:
            listed = ", ".join(e["number"] for e in entries) or "none"
            return emit("stop", f"Phase {phaseId} is not in the Phase Status of {planRel}. Listed phases: {listed}. "
                        "Tell the user.")
        if entry["done"]:
            return emit("stop", f"Phase {phaseId} is already marked done in {planRel}. No coder was dispatched. Tell "
                        "the user; to run it again, they uncheck it in Phase Status first.")
    elif entries and not pending:
        return emit("stop", "Every phase in the plan is checked. Tell the user the plan is complete.")
    else:
        entry = pending[0] if pending else None

    number = entry["number"] if entry else None
    section = phase_text(planLines, number) if entry else "\n".join(planLines)

    if entry:
        closingSkill = next((skill for pattern, skill in CLOSING_PHASES if pattern.search(entry["title"])), None)
        if closingSkill:
            return start_closing_phase(repoRoot, planRel, lane, modifier, entry, closingSkill, section, branch,
                                       phaseId)

    if not check_acceptance_criteria(repoRoot, planLines, planRel):
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
    baseHead = previous.get("baseHead") if isSameUnfinishedPhase and previous.get("baseHead") else head_commit(repoRoot)

    phaseLabel = f"Phase {number} of `{planRel}`" if entry and hasPhases else f"`{planRel}`"
    prompt = (f"Implement {phaseLabel}. Read the plan phase-scoped.\n"
              "If the task turns out architectural, report back and recommend /eng-spec.\n\n" + packetText).rstrip()
    state = {"stage": "coder", "plan": planRel, "lane": lane, "phase": statePhase, "branch": branch,
             "modifier": modifier, "risk": entry["risk"] if entry else "high", "title": entry["title"] if entry else "",
             "gateCommands": commands, "baseline": baseline, "baseHead": baseHead, "startedAt": time.time(),
             "phaseText": section if entry and hasPhases else None, "onlyPhase": phaseId,
             "sessionId": session_pin()}
    open_dispatch(state)
    save_state(repoRoot, state)
    model = "haiku" if modifier == "+fast" else None
    emit("dispatch", gateNote, next_after("after-coder"), prompt=prompt, agent="coder", model=model)


def start_planless(repoRoot, modifier, taskText, branch="-"):
    state = {"stage": "coder", "plan": None, "lane": "code", "phase": None, "branch": branch, "modifier": modifier,
             "risk": "high", "title": "", "gateCommands": [], "baseline": file_hashes(repoRoot),
             "startedAt": time.time(), "sessionId": session_pin()}
    open_dispatch(state)
    directory = state_dir(repoRoot)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "reports.jsonl").unlink(missing_ok=True)
    save_state(repoRoot, state)
    prompt = (f"Implement: {taskText}\nRun the typecheck, and lint and tests for only the files you changed, once, "
              "after all edits. If the task turns out architectural, report back and recommend /eng-spec.")
    model = "haiku" if modifier == "+fast" else None
    emit("dispatch", next_after("after-coder"), prompt=prompt, agent="coder", model=model)


def start_closing_phase(repoRoot, planRel, lane, modifier, entry, skill, section, branch, onlyPhase=None):
    state = {"stage": "skill", "plan": planRel, "lane": lane, "phase": entry["number"], "branch": branch,
             "modifier": modifier, "risk": entry["risk"], "title": entry["title"], "gateCommands": [], "behavior": [],
             "baseline": file_hashes(repoRoot), "onlyPhase": onlyPhase, "sessionId": session_pin()}
    save_state(repoRoot, state)
    verdictStep = ("run `python3 ~/.claude/scripts/code-step.py skill-done pass` when the phase's Success Criteria "
                   "hold, or `skill-done fail` when they do not (for the Verify pass, any MISSING criterion fails it)")
    sectionLines = ["The phase's own plan section follows. Follow its steps and gates; the skill alone is not the phase:",
                    section] if section else []
    emit("invoke-skill", f"Phase {entry['number']} ({entry['title']}) is a closing phase. Invoke the Skill tool with "
         f"`{skill}`; a coder is not dispatched.", *sectionLines, f"The skill needs judgment. When it returns, {verdictStep}.")


def check_acceptance_criteria(repoRoot, planLines, planRel):
    hasCriteriaSection = any(line.strip() == "## Acceptance Criteria" for line in planLines)
    if not hasCriteriaSection:
        return True
    criteriaRel = criteria_rel(planRel)
    criteria = repoRoot / criteriaRel
    if criteria.is_file() and criteria.read_text().strip():
        return True

    note = f"{criteriaRel} is missing or empty"
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


PLAN_IMPACT_HEADER = re.compile(r"^[ \t>*`_-]*PLAN-IMPACT[*`_]*:?[*`_]*[ \t]*$")
PLAN_IMPACT_KEY = re.compile(r"^[ \t>*`_-]*(?:assumed|found|changes)[*`_]*:", re.I)


def plan_impact_block(report):
    # The block is the header line `PLAN-IMPACT:` (bold or backticked is fine) and the lines under it: indented lines,
    # or lines that start with one of the three keys. Blank lines may sit between the header and the first line.
    lines = report.splitlines()
    for index, line in enumerate(lines):
        if not PLAN_IMPACT_HEADER.match(line):
            continue
        body = []
        for later in lines[index + 1:]:
            if not later.strip():
                if body:
                    break
                continue
            if later[0] in " \t":
                body.append(later.rstrip())
            elif PLAN_IMPACT_KEY.match(later):
                body.append("  " + later.strip())
            else:
                break
        if body:
            return "PLAN-IMPACT:\n" + "\n".join(body)
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


DOCS_SUFFIXES = (".md", ".mdx", ".rst", ".txt")


def asks_coder_changed_files(changedNow, asksBaseline):
    # The files whose hash differs between the snapshot taken at the asks-coder dispatch and now, new and deleted included.
    names = set(changedNow) | set(asksBaseline)
    return sorted(name for name in names if changedNow.get(name) != asksBaseline.get(name))


def command_after_coder(repoRoot, state, args):
    if not wait_for_handback(repoRoot, state, "after-coder", longChecksFollow=state["stage"] == "asks-coder"):
        return
    state = load_state(repoRoot)

    coderStage = state["stage"]
    isAskFix = coderStage == "asks-coder"
    addendum = None if isAskFix else added_phase_lines(repoRoot, state)
    if addendum:
        state["phaseText"] = addendum["text"]
        firstReport = with_earlier_report(state, latest_coder_message(repoRoot, coderStage, state.get("dispatchAt")))
        if firstReport is not None:
            state["earlierCoderReport"] = firstReport
        open_dispatch(state)
        save_state(repoRoot, state)
        prompt = (f"Phase {state['phase']} of `{state['plan']}` gained lines after the first coder was dispatched. "
                  "Implement only these added or changed lines. Do not redo the rest of the phase:\n\n"
                  + "\n".join(addendum["added"]))
        return emit("dispatch", "The plan phase changed while the coder ran. Dispatch a coder for the added lines "
                    "before the review.",
                    next_after("after-coder"), prompt=prompt, agent="coder")
    gate = None if isAskFix else gate_results(repoRoot)
    gateLines = state.get("gateLines", "")
    if not isAskFix:
        code, gateLines = run_command(["python3", str(SCRIPTS_DIR / "coder-gate.py"), "clear"], repoRoot)
    latestRow = latest_coder_row(repoRoot, coderStage, state.get("dispatchAt"))
    if latestRow is None:
        return emit("stop", "No coder report was saved. The SubagentHandback hook (code-step.py hook) is not "
                    "installed or the coder never handed back. Tell the user.")
    report = latestRow.get("message", "")
    if not isAskFix:
        report = with_earlier_report(state, report)

    capped = [coder for coder in (gate or {"coders": {}})["coders"].values() if coder["result"] == "cap"]
    flagged = list(state.get("flagged", [])) if isAskFix else []
    for coder in capped:
        flagged.append("hand-back gate cap: " + ", ".join(coder["failed"]) + " still failing after 3 denials")
    flagged += coder_flags(report)

    changedNow = file_hashes(repoRoot)
    baseline = state["baseline"]
    changedFiles = [name for name, digest in changedNow.items() if name not in baseline or baseline[name] != digest]
    changedFiles += [name for name in committed_since(repoRoot, state.get("baseHead")) if name not in changedFiles]
    asksCoderChangedNothing = isAskFix and changedNow == state.get("asksBaseline")
    if not changedFiles or asksCoderChangedNothing or "/eng-spec" in report:
        state["stage"] = "stopped"
        state["resumableCoderAt"] = time.time()
        state["resumableCoderId"] = latestRow.get("agent_id") or "unknown"
        state.pop("dispatchAt", None)
        save_state(repoRoot, state)
        tickText = (f" If the user says Phase {state['phase']} is already done, invoke Skill code with `tick "
                    f"{state['phase']}`; do that only on the user's word." if state.get("plan") and state.get("phase")
                    else "")
        resumeText = (" If the user answers the coder's blocker, resume that coder with SendMessage, then run "
                      f"{timed_command('after-coder')}.")
        return emit("stop", "The coder produced no reviewable change, or recommended /eng-spec. Do not dispatch a "
                    "review. Do not mark the phase done." + tickText + resumeText
                    + " Relay the coder's report to the user:", report)

    asksBaseline = state.get("asksBaseline")
    if isAskFix and asksBaseline is not None:
        # The review after an asks-coder covers only what the asks-coder changed. A state from before asksBaseline
        # existed keeps the whole-phase scope.
        changedFiles = asks_coder_changed_files(changedNow, asksBaseline)
        if all(name.lower().endswith(DOCS_SUFFIXES) for name in changedFiles):
            state.update({"files": changedFiles, "coderStage": coderStage})
            state["stage"] = "review"
            save_state(repoRoot, state)
            say(repoRoot, "The asks coder changed only docs files. No review runs on them.")
            return finish_phase(repoRoot, state)

    behavior = behavior_lines(report)
    whyGroups = resolve_report_paths(why_by_file(report), changedFiles)
    testsRun = tests_run_text(gate, state)
    if isAskFix:
        behavior = list(state.get("behavior", [])) + behavior
        for path, notes in state["why"].items():
            if path in changedFiles:
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
        fileLine = item.get("file_line", "")
        issueText = ask_text(item)
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


def decide_call(word):
    return f"`decide {word} --by user --ruling \"<the user's answer>\"`"


DECIDE_BY_NOTE = ("If the user told you to make the call yourself, or you rule without asking, pass `--by session` in "
                  "place of `--by user`. A session ruling never changes the acceptance criteria.")


def emit_plan_impact_modal(impact, repoRoot):
    word = preset_decision(repoRoot)
    if word:
        print(f"PLAN-IMPACT answered by the pre-set decision '{word}'. No question to the user.")
        state = load_state(repoRoot)
        return command_decide(repoRoot, state, [word, "--by", "session", "--ruling",
                                                f"pre-set decision '{word}'; no user was asked"],
                              rulingBy="the pre-set decision")
    ask_user(repoRoot, "the code and the plan disagree. Ask the user this question in plain text and wait for the "
             "answer. Then invoke Skill code with the args after the option the user chose, with the user's whole "
             "answer, in their words, as the --ruling text.",
             impact, "",
             f"1. {PLAN_IMPACT_OPTIONS[0]} (a coder rewrites the plan steps to match the ruling): "
             f"{decide_call('adopt')}",
             f"2. {PLAN_IMPACT_OPTIONS[1]}: {decide_call('keep')}",
             f"3. {PLAN_IMPACT_OPTIONS[2]}: talk it through here, then invoke Skill code with "
             f"{decide_call('adopt')} or {decide_call('keep')}",
             DECIDE_BY_NOTE)


def record_deviation(repoRoot, state):
    ruling = state["ruling"]
    entry = [f"- {time.strftime('%Y-%m-%d')} (Phase {state['phase']}): {ruling['decision']}. "
             f"Ruled by {ruling['by']} at {ruling['at']}.", "",
             "  The user's words:" if ruling["byUser"] else "  The ruling's words:"]
    entry += ["  > " + line for line in ruling["words"].splitlines()]
    entry += ["", "  The disagreement:"]
    entry += ["  " + line for line in state["impact"].splitlines()]
    append_deviation(repoRoot / state["plan"], entry)


def append_deviation(planPath, entry):
    # Add the entry lines at the end of the plan's `## Plan Deviations` section, creating it before `## References`.
    lines = planPath.read_text().split("\n")
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
    # The decision word, who ruled (`--by user|session`, None when missing), then the words after `--ruling`,
    # joined when the caller left them unquoted.
    word = args[0].lower() if args else ""
    rulingAt = args.index("--ruling") if "--ruling" in args else len(args)
    byWords = args[:rulingAt]
    by = byWords[byWords.index("--by") + 1] if "--by" in byWords[:-1] else None
    rulingWords = " ".join(args[rulingAt + 1:])
    return word, by, rulingWords.strip()


def resolved_plan_impact(state):
    # review-loop reads a block that starts RESOLVED as settled, so it reviews against the ruling instead of
    # returning the question again.
    ruling = state["ruling"]
    if ruling["byUser"]:
        resolved, wordsLabel = "the user ruled on this disagreement", "Ruling, in the user's words:"
    elif ruling["by"] == "the pre-set decision":
        resolved, wordsLabel = "the pre-set decision ruled on this disagreement, not the user", "The ruling's words:"
    else:
        resolved, wordsLabel = "the session ruled on this disagreement, not the user", "The ruling's words:"
    lines = [f"RESOLVED: {resolved}. Review the code against the ruling. It is not an open question.",
             f"Decision: {ruling['decision']}",
             f"Ruled by: {ruling['by']}, at {ruling['at']}",
             wordsLabel]
    lines += ["  " + line for line in ruling["words"].splitlines()]
    lines.append("The disagreement it settles:")
    lines += ["  " + line for line in state["impact"].splitlines()]
    return "\n".join(lines)


DECIDE_USAGE = 'decide <adopt|keep> --by <user|session> --ruling "<the user\'s answer>"'


def command_decide(repoRoot, state, args, rulingBy=None):
    word, by, rulingWords = split_decide_args(args)
    if not word:
        return emit("stop", STAGE_GUARDS["decide"]["message"])
    decision = DECISION_WORDS.get(word)
    if decision is None:
        return emit("stop", "decide takes adopt, keep or discuss.")
    if decision == "Discuss":
        return ask_user(repoRoot, "discuss this disagreement between the code and the plan with the user in plain "
                        f"words. When the user chooses, invoke Skill code with {decide_call('adopt')} or "
                        f"{decide_call('keep')}. {DECIDE_BY_NOTE}", state["impact"])
    if by not in ("user", "session"):
        return emit("stop", f"decide {word} needs --by user or --by session. Usage: `{DECIDE_USAGE}`. {DECIDE_BY_NOTE}")
    if not rulingWords:
        return emit("stop", f"decide {word} needs the ruling's words: {decide_call(word)}. {DECIDE_BY_NOTE} "
                    "Hand back and ask the main session for them.")

    if state.get("plan") and not (repoRoot / state["plan"]).is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")
    rulingAt = time.strftime("%Y-%m-%d %H:%M")
    byUser = by == "user" and not rulingBy
    if rulingBy:
        rulingName = rulingBy
    elif byUser:
        rulingName = git_user_name(repoRoot)
    else:
        rulingName = "the session, not the user"
    state["ruling"] = {"decision": decision, "words": rulingWords, "by": rulingName, "byUser": byUser,
                       "at": rulingAt}
    if not byUser and state.get("plan") and criteria_file(repoRoot, state):
        print("The acceptance criteria stay as written: verify-branch reports any criterion the code now fails as "
              "failing.")
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


def criteria_rel(planRel):
    # The plan's acceptance criteria live beside it.
    return str(pathlib.PurePath(planRel).parent / "acceptance-criteria.md")


def criteria_file(repoRoot, state):
    # None when the plan has no criteria file.
    criteriaRel = criteria_rel(state["plan"])
    if not (repoRoot / criteriaRel).is_file():
        return None
    return criteriaRel


def save_criteria_guard(repoRoot, state):
    # Before a plan edit that the user did not rule: remember the criteria file's path and text, or None for "no
    # file", so that restore_criteria can put it back.
    criteriaRel = criteria_rel(state["plan"])
    criteriaPath = repoRoot / criteriaRel
    criteriaText = criteriaPath.read_text() if criteriaPath.is_file() else None
    state["criteriaGuard"] = {"path": criteriaRel, "text": criteriaText}


def save_replaced_criteria(repoRoot, criteriaName, text):
    # Keep the text a restore replaces in the git dir, outside the worktree, one new file per restore.
    found = git_output(repoRoot, "rev-parse", "--path-format=absolute", "--git-path", "code-step-replaced-criteria")
    folder = pathlib.Path(found)
    folder.mkdir(parents=True, exist_ok=True)

    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    counter = 1
    while True:
        target = folder / f"{stamp}-{counter:02d}-{criteriaName}"
        try:
            with open(target, "x") as handle:
                handle.write(text)
            return target
        except FileExistsError:
            counter += 1


def settle_criteria_guard(repoRoot, state, branch):
    # Resolve the saved criteria copy of a plan edit that the user did not rule. Returns the message for the user,
    # or None when there was nothing to do. The caller saves the state: the guard is popped here.
    if state.get("criteriaGuard") is None:
        return None
    if state.get("branch") != branch:
        state.pop("criteriaGuard")
        return ("The saved acceptance criteria belong to a plan edit on another branch, so the script dropped them "
                "and restored nothing.")
    return restore_criteria(repoRoot, state)


def restore_criteria(repoRoot, state):
    # Put the folder back as it was at the save. The text of a file that differs, or that did not exist at the save,
    # goes to a copy under the git dir first. Returns the message for the user, or None when nothing changed.
    guard = state.pop("criteriaGuard")
    criteriaPath = repoRoot / guard["path"]
    if not criteriaPath.parent.is_dir():
        return (f"The saved acceptance criteria belong to {guard['path']}, whose folder is gone, so the script "
                "dropped them and restored nothing.")

    if guard["text"] is None:
        if not criteriaPath.is_file():
            return None
        kept = save_replaced_criteria(repoRoot, criteriaPath.name, criteriaPath.read_text())
        criteriaPath.unlink()
        return (f"No acceptance criteria file existed before a ruling the user did not make, and {guard['path']} "
                f"appeared after it, so the script deleted it. The text it deleted is in {kept}.")

    changedNote = ""
    if criteriaPath.is_file():
        currentText = criteriaPath.read_text()
        if currentText == guard["text"]:
            return None
        kept = save_replaced_criteria(repoRoot, criteriaPath.name, currentText)
        changedNote = f" The text it replaced is in {kept}."

    criteriaPath.write_text(guard["text"])
    return (f"The acceptance criteria in {guard['path']} changed after a ruling the user did not make, and the "
            f"script restored them.{changedNote}")


def plan_edit_prompt(state, criteriaRel):
    ruling = state["ruling"]
    userRuled = ruling["byUser"]
    editScope = f"the plan file {state['plan']}"
    if criteriaRel and userRuled:
        editScope += f" and its acceptance criteria file {criteriaRel}"
    lines = [
        f"Edit only {editScope}. In Phase {state['phase']}, the code and the plan disagreed:",
        "",
        state["impact"],
        "",
        (f"The user ruled ({ruling['by']}, {ruling['at']}). The ruling, in the user's words:" if userRuled
         else f"The ruling ({ruling['by']}, {ruling['at']}). The ruling's words:"),
        "",
        ruling["words"],
        "",
        "Rewrite each step, Automated Verification command and Success Criteria line of the plan that the ruling "
        "contradicts, so that the plan states the ruling. Keep every other line as it is. Leave the "
        "`## Plan Deviations` section as it is. Edit no code and no test, and run no check.",
    ]
    if criteriaRel and not userRuled:
        lines += ["", f"Do not edit {criteriaRel}. Only the user's own sign-off changes an acceptance criterion."]
    if criteriaRel and userRuled:
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
    ruling = state["ruling"]
    if not ruling["byUser"]:
        save_criteria_guard(repoRoot, state)
    state.update({"stage": "plan-coder", "planEditBaseline": file_hashes(repoRoot),
                  "followUpBefore": change_snapshot(repoRoot)})
    open_dispatch(state)
    save_state(repoRoot, state)

    prompt = plan_edit_prompt(state, criteriaRel)
    if ruling["byUser"]:
        criteriaClause = " and acceptance criteria" if criteriaRel else ""
        headline = (f"The user adopted the plan change. Dispatch a coder to rewrite the plan steps{criteriaClause} "
                    "it contradicts.")
    else:
        unchangedClause = " The acceptance criteria do not change." if criteriaRel else ""
        headline = (f"The plan change was adopted by {ruling['by']}. Dispatch a coder to rewrite the plan steps it "
                    f"contradicts.{unchangedClause}")
    emit("dispatch", headline,
         next_after("after-plan-edit"), prompt=prompt, agent="coder")


def command_review_again(repoRoot, state, args):
    state.pop("stopReason")
    # A failed review that ran the structure pass runs it again; one that skipped it skips it again.
    if not state.get("structurePassSkipped"):
        state.pop("reviewRan", None)
    emit_review_dispatch(repoRoot, state)


def command_after_plan_edit(repoRoot, state, args):
    if not wait_for_handback(repoRoot, state, "after-plan-edit"):
        return
    state = load_state(repoRoot)
    state["sessionId"] = session_pin() or state.get("sessionId")

    # Nothing below changes state until the run is on the plan's branch with the plan in place: the saved criteria
    # and the baseline wait for it. /code sends only decide, asks-done, verify, review-again and tick on as verbs, and
    # none of them resumes a plan edit, so the user runs the verb by hand.
    startBranch = state.get("branch")
    if "branch" in state and current_branch(repoRoot) != startBranch:
        where = (f"Switch back to branch {startBranch}" if startBranch not in (None, "-")
                 else "Check out the branch or commit where the plan edit started")
        return emit("stop", f"after-plan-edit ran on a different branch from the plan edit. {where}, then run "
                    "`! python3 ~/.claude/scripts/code-step.py after-plan-edit` from the repo root, and tell the "
                    "session to follow its ACTION line. Tell the user.")

    if not (repoRoot / state["plan"]).is_file():
        return emit("stop", f"The plan {state['plan']} is missing from this checkout, so the plan edit cannot be "
                    f"read. Restore {state['plan']}, then run "
                    "`! python3 ~/.claude/scripts/code-step.py after-plan-edit` from the repo root, and tell the "
                    "session to follow its ACTION line. Tell the user.")

    hadCriteriaGuard = state.get("criteriaGuard") is not None
    criteriaMessage = settle_criteria_guard(repoRoot, state, current_branch(repoRoot))
    if criteriaMessage:
        say(repoRoot, criteriaMessage)

    if hadCriteriaGuard:
        save_state(repoRoot, state)

    baseline = state.pop("planEditBaseline")
    changedNow = file_hashes(repoRoot)
    editedFiles = [name for name, digest in changedNow.items() if baseline.get(name) != digest]

    criteriaRel = criteria_file(repoRoot, state)
    allowedFiles = (state["plan"], criteriaRel) if state["ruling"]["byUser"] else (state["plan"],)
    strayFiles = [name for name in editedFiles if name not in allowedFiles]
    if strayFiles:
        state["files"] += [name for name in strayFiles if name not in state["files"]]
        state["flagged"].append("the plan-edit coder also changed " + ", ".join(strayFiles))
        state["exception"] = True

    planLines = (repoRoot / state["plan"]).read_text().splitlines()
    state["phaseText"] = phase_text(planLines, state["phase"])

    planNote = f"The plan {state['plan']} now states the ruling."
    if criteriaRel and criteriaRel in editedFiles and state["ruling"]["byUser"]:
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


SMALL_FOLLOW_UP_LINES = 40
LOCKFILE_NAMES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "uv.lock", "Cargo.lock",
                  "Gemfile.lock", "composer.lock", "go.sum", "bun.lockb"}


def is_test_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    parts = lowered.split("/")[:-1]
    return (any(part in ("test", "tests", "__tests__", "spec", "specs") for part in parts)
            or name.startswith("test_") or ".test." in name or ".spec." in name or "_test." in name)


def is_uncounted_path(path):
    lowered = path.lower()
    name = lowered.rsplit("/", 1)[-1]
    return (path.rsplit("/", 1)[-1] in LOCKFILE_NAMES or name.endswith(".lock") or "__snapshots__" in lowered
            or name.endswith(".snap") or "generated" in lowered or ".generated." in name or ".gen." in name
            or name.endswith(".min.js"))


def is_counted_source(path):
    return not is_test_path(path) and not is_uncounted_path(path)


def change_snapshot(repoRoot):
    # Added lines per file (tracked diff against HEAD, and the line count of each untracked file) and the files that
    # are new, so the change a coder makes is the difference between two snapshots.
    added = {}
    newFiles = set()
    for row in (git_output(repoRoot, "diff", "--numstat", "HEAD") or "").split("\n"):
        columns = row.split("\t")
        if len(columns) == 3:
            added[columns[2]] = int(columns[0]) if columns[0].isdigit() else 0
    for row in (git_output(repoRoot, "diff", "--name-status", "HEAD") or "").split("\n"):
        columns = row.split("\t")
        if len(columns) == 2 and columns[0] == "A":
            newFiles.add(columns[1])
    untracked = (git_output(repoRoot, "ls-files", "--others", "--exclude-standard") or "").split("\n")
    for name in untracked:
        if not name:
            continue
        newFiles.add(name)
        path = repoRoot / name
        added[name] = path.read_bytes().count(b"\n") if path.is_file() else 0
    return {"added": added, "newFiles": sorted(newFiles)}


def follow_up_is_small(before, after):
    # True when the coder that ran between the two snapshots added under SMALL_FOLLOW_UP_LINES lines to counted
    # non-test files and created no new non-test source file.
    addedLines = sum(max(count - before["added"].get(name, 0), 0) for name, count in after["added"].items()
                     if is_counted_source(name))
    createdSource = [name for name in after["newFiles"] if name not in before["newFiles"]
                     and name not in before["added"] and is_counted_source(name)]
    return addedLines < SMALL_FOLLOW_UP_LINES and not createdSource


def emit_review_dispatch(repoRoot, state):
    coderStages = ["coder"] + (["asks-coder"] if state.get("coderStage") == "asks-coder" else [])
    stageReports = []
    for stage in coderStages:
        stageReport = latest_coder_message(repoRoot, stage)
        stageReports.append(with_earlier_report(state, stageReport) if stage == "coder" else stageReport)
    report = "\n\n".join(stageReport for stageReport in stageReports if stageReport is not None)
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
    # The structure pass runs on the first review of a phase. A re-review after a ruling, or after a follow-up coder
    # whose own change is small, skips it. The review-loop round count (iter) is a separate matter.
    followUpBefore = state.pop("followUpBefore", None)
    isSmallFollowUp = followUpBefore is None or follow_up_is_small(followUpBefore, change_snapshot(repoRoot))
    state["structurePassSkipped"] = bool(state.get("reviewRan") and isSmallFollowUp)
    if state["structurePassSkipped"]:
        header.append("structure-pass: skip")
    state["reviewRan"] = True
    prompt = "\n".join(header) + "\n\n" + handoff_block(state)
    state["stage"] = "review"
    open_dispatch(state)
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
    emit("dispatch", next_after("after-review"), prompt=prompt, agent="review-loop", model="sonnet")


# ---------- hook ----------

def is_pinned_fork_event(event, state):
    # The /code fork is the one general-purpose agent in the session that /code pinned. A general-purpose agent of
    # another session, or of a session /code did not pin, is not touched. The agent type is the only thing a hook
    # event records about the fork (its description is not in the event).
    sessionId = event.get("session_id")
    pinnedSession = state.get("sessionId")
    return event.get("agent_type") == FORK_AGENT_TYPE and bool(sessionId) and sessionId == pinnedSession


def open_dispatch_verb(state):
    verbs = {"review": "after-review", "plan-coder": "after-plan-edit"}
    return verbs.get(state["stage"], "after-coder")


def is_dispatch_open(cwd, state):
    # A dispatch is open while the dispatched agent has no hand-back row after dispatchAt.
    since = state.get("dispatchAt")
    if since is None or time.time() - since > SAY_MAX_AGE_SECONDS:
        return False
    return latest_handback_row(cwd, state, expected_agent(state), since) is None


def deny_early_fork_handback(cwd, state):
    # The fork's hand-back while a coder or review-loop is still out leaves that agent's report with nobody to read
    # it. Deny it once per dispatch and name the command that waits.
    if state.get("forkDenied") == state.get("dispatchAt") or not is_dispatch_open(cwd, state):
        return
    state["forkDenied"] = state["dispatchAt"]
    save_state(cwd, state)
    reason = (f"A dispatched agent has not handed back yet. Do not hand back. Run `{own_path(INSTALLED_COMMAND)} "
              f"{open_dispatch_verb(state)}` with Bash timeout {BASH_TIMEOUT_MS}: it waits for the hand-back and "
              "prints the next action.")
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": reason}}))


def command_stop_hook():
    # SubagentStop: the fork ends its turn while a dispatch is open (it answered the Agent call's immediate return
    # instead of waiting). Block that stop and name the waiting command, at most FORK_STOP_BLOCK_LIMIT times per dispatch.
    try:
        event = json.load(sys.stdin)
        cwd = event.get("cwd") or "."
        state = load_state(cwd)
        if state is None or state["stage"] not in HOOK_STAGES or not is_pinned_fork_event(event, state):
            return
        blocks = state.get("forkStopBlocks", 0)
        if blocks >= FORK_STOP_BLOCK_LIMIT or not is_dispatch_open(cwd, state):
            return
        state["forkStopBlocks"] = blocks + 1
        save_state(cwd, state)
        reason = (f"The dispatched {expected_agent(state)} has not handed back. Do not stop. Run "
                  f"`{own_path(INSTALLED_COMMAND)} {open_dispatch_verb(state)}` with Bash timeout {BASH_TIMEOUT_MS}: "
                  "it waits for the hand-back and prints the next action.")
        print(json.dumps({"decision": "block", "reason": reason}))
    except Exception as error:
        print(f"code-step stop-hook: {error}", file=sys.stderr)


def command_hook():
    try:
        event = json.load(sys.stdin)
        agentType = event.get("agent_type")
        if agentType not in ("coder", "review-loop", FORK_AGENT_TYPE):
            return
        cwd = event.get("cwd") or "."
        state = load_state(cwd)
        isResumedCoder = (state is not None and state["stage"] == "stopped" and agentType == CODER
                          and state.get("resumableCoderAt") is not None
                          and state.get("resumableCoderId") == (event.get("agent_id") or "unknown"))
        if state is None or (state["stage"] not in HOOK_STAGES and not isResumedCoder):
            return
        sessionId = event.get("session_id")
        pinnedSession = state.get("sessionId")
        if sessionId and pinnedSession and sessionId != pinnedSession:
            return
        if isResumedCoder:
            # A coder resumed after the run stopped on its report is the same coder: its next hand-back goes to review.
            state["stage"] = "coder"
            state["dispatchAt"] = state.pop("resumableCoderAt")
            state.pop("resumableCoderId", None)
            state.pop("forkDenied", None)
            state.pop("forkStopBlocks", None)
            save_state(cwd, state)
        if agentType == FORK_AGENT_TYPE:
            if is_pinned_fork_event(event, state):
                deny_early_fork_handback(cwd, state)
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

def command_after_review(repoRoot, state, args):
    if not wait_for_handback(repoRoot, state, "after-review", longChecksFollow=True):
        return
    state = load_state(repoRoot)
    messages = saved_messages(repoRoot, "review-loop", "review", state.get("reviewReportsFloor", 0))
    if not messages:
        # The shared store can see the hand-back before this script's own hook has written its row.
        storeRow = handback_store_row(state)
        if isinstance(storeRow, dict) and storeRow.get("ts", 0) > state.get("dispatchAt", 0) and storeRow.get("message"):
            messages = [storeRow["message"]]
    if not messages:
        return emit("stop", "No review-loop packet was saved. The SubagentHandback hook is not installed. Tell the user.")
    module, importError = load_handback()
    if module is None:
        return emit("stop", f"Cannot read the review-loop packet: {importError}. Tell the user.")
    try:
        packet = module.load(messages[-1])
    except module.PacketError as error:
        state.update({"stage": "stopped", "stopReason": "invalid-packet"})
        save_state(repoRoot, state)
        return emit("stop", "The review-loop packet does not parse. Show the user the raw packet. Problems: "
                    + "; ".join(error.problems), messages[-1],
                    "To review the same diff again, invoke Skill code with `review-again`.")
    status = packet["status"]
    state["iter"] = packet["iter"]
    if packet["spec_iter"] is not None:
        state["spec_iter"] = packet["spec_iter"]
    state["packet"] = packet

    if status == "plan-impact":
        state.update({"stage": "impact-review", "impact": packet["plan_impact"]})
        save_state(repoRoot, state)
        return emit_plan_impact_modal(state["impact"], repoRoot)
    if status == "critical-blocker":
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        return emit("stop", "Review found a critical blocker. Present these to the user. Do not mark the phase done.",
                    *["- " + module.item_text(item, "finding", "file_line") for item in packet["blockers"]])
    if status == "cap-reached":
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        return emit("stop", "The review cap was reached. Report these findings to the user. Do not mark the phase "
                    "done. The session stays dirty, so git commit stays blocked.",
                    *["- " + module.item_text(item, "finding", "file_line") for item in packet["findings_remaining"]])

    save_state(repoRoot, state)
    say(repoRoot, module.render(packet, "code"))
    print("The review packet was saved for the user. Do not repeat it.")
    asks = packet["ask"]
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
        fileLine = item.get("file_line", "")
        question = item.get("question", "")
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
            f"{n + 1}. {ask_text(item)}" for n, item in enumerate(asks)))
        log_ask_outcomes(repoRoot, state, [presetOutcome] * len(asks))
        return apply_asks_or_finish(repoRoot, state, [presetOutcome] * len(asks), [None] * len(asks))
    ask_the_user(repoRoot, state, asks)


def ask_the_user(repoRoot, state, asks):
    if not mark_review_gate_clean(repoRoot, state):
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        return
    state["stage"] = "asks"
    save_state(repoRoot, state)
    say(repoRoot, "\n".join([
        "## Question for the user", "",
        f"Main session: ask the user about each review ask below in plain text and wait for the answers. Each answer "
        f"is accepted, rejected or modified. Then invoke Skill code with the args `asks-done` and {len(asks)} outcome "
        "word(s), in order. After a modified outcome, add `--change \"<the user's change text>\"`.", "",
        *[f"{n + 1}. {ask_text(item)}" for n, item in enumerate(asks)]]))
    emit("ask-user", "The question for the user is in say.md. Hand back.")


def log_ask_outcomes(repoRoot, state, outcomes):
    branch = git_output(repoRoot, "branch", "--show-current") or "-"
    for item, outcome in zip(state["asks"], outcomes):
        fileLine = item.get("file_line", "-:0")
        path, _, line = fileLine.partition(":")
        run_command(["bash", str(CLAUDE_DIR / "skills/review/log-review-finding"), "kind=finding",
                     f"repo={repoRoot.name}", f"branch={branch}", f"lane={state['lane']}", "scope=phase",
                     f"phase={state.get('phase') or '-'}", f"iter={state['iter']}",
                     f"gate={item.get('gate', 'code-reviewer')}",
                     "disposition=ask", f"class={item.get('class', 'other')}", f"file={path}",
                     f"line={re.sub(r'[^0-9].*', '', line) or '0'}", "actioned=ask", f"ask_outcome={outcome}",
                     f"desc=ask resolved: {item.get('question', '')[:100]}"], repoRoot)


def asks_coder_prompt(acceptedAsks):
    lines = ["Apply these review asks. The user accepted them. Change only what they name.", ""]
    for number, (item, outcome, changeText) in enumerate(acceptedAsks, 1):
        location = item.get("file_line", "")
        lines.append(f"{number}. [{outcome}] {ask_text(item)}"
                     + (f" ({location})" if location else ""))
        if changeText:
            lines.append(f"   The user's change: {changeText}")
    lines += ["", "Run the typecheck, and lint and tests for only the files you changed, once, after all edits. "
              "If an ask turns out architectural, report back and recommend /eng-spec."]
    return "\n".join(lines)


def apply_asks_or_finish(repoRoot, state, outcomes, changeTexts):
    # An accepted or modified ask is owed work: a coder applies it, then a review of that coder's diff runs (none when
    # the diff is docs only) before the phase can finish.
    acceptedAsks = [[item, outcome, changeText] for item, outcome, changeText in zip(state["asks"], outcomes, changeTexts)
                    if outcome != "rejected"]
    if not acceptedAsks:
        state["stage"] = "review"
        save_state(repoRoot, state)
        return finish_phase(repoRoot, state)

    state.update({"stage": "asks-coder", "acceptedAsks": acceptedAsks, "asksApplied": True,
                  "asksBaseline": file_hashes(repoRoot), "followUpBefore": change_snapshot(repoRoot)})
    open_dispatch(state)
    save_state(repoRoot, state)
    model = "haiku" if state.get("modifier") == "+fast" else None
    emit("dispatch", "The user accepted review asks. Dispatch a coder to apply them. A review of that coder's "
         "diff runs after it (none when the diff is docs only) before the phase can finish.",
         next_after("after-coder"), prompt=asks_coder_prompt(acceptedAsks), agent="coder", model=model)


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


def command_asks_done(repoRoot, state, args):
    outcomes, givenChanges = split_asks_done_args(args)
    if len(outcomes) != len(state["asks"]) \
            or any(outcome not in ASK_OUTCOMES for outcome in outcomes) or givenChanges is None \
            or len(givenChanges) != outcomes.count("modified"):
        return emit("stop", ASKS_DONE_USAGE)

    remainingChanges = iter(givenChanges)
    changeTexts = [next(remainingChanges) if outcome == "modified" else None for outcome in outcomes]
    log_ask_outcomes(repoRoot, state, outcomes)
    apply_asks_or_finish(repoRoot, state, outcomes, changeTexts)


# ---------- phase gates and boundary ----------

def command_skill_done(repoRoot, state, args):
    verdict = args[0].lower() if args else "pass"
    if verdict not in ("pass", "fail"):
        return emit("stop", "skill-done takes pass or fail.")
    if verdict == "fail":
        state["stage"] = "stopped"
        save_state(repoRoot, state)
        return emit("stop", "The closing phase's check failed (a MISSING criterion, or an unmet Success Criteria). "
                    "Do not mark the phase done. Report what failed to the user.")
    finish_phase(repoRoot, state, skipVerification=True)


def command_tick(args):
    # The user finished a phase outside /code. The main session runs this only on the user's word.
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    if len(args) != 1:
        return emit("stop", "usage: code-step.py tick <phase id>")
    if state is None or not state.get("plan"):
        return emit("stop", "tick needs a plan run: there is no saved plan state. Run `start <plan>` first.")
    if stop_while_plan_edit_coder_is_out(repoRoot, state, "tick " + " ".join(args)):
        return
    planPath = repoRoot / state["plan"]
    if not planPath.is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")
    plan = parse_plan(planPath.read_text().splitlines())
    if plan["failures"]:
        return emit("stop", plan_failure_message(plan, state["plan"]))
    number = args[0]
    entry = next((e for e in plan["entries"] if e["number"] == number), None)
    if entry is None:
        listed = ", ".join(e["number"] for e in plan["entries"]) or "none"
        return emit("stop", f"Phase {number} is not in the Phase Status of {state['plan']}. Listed phases: {listed}.")
    if entry["done"]:
        return emit("stop", f"Phase {number} is already marked done in {state['plan']}.")

    criteriaMessage = settle_criteria_guard(repoRoot, state, current_branch(repoRoot))
    if criteriaMessage:
        say(repoRoot, criteriaMessage)

    mark_phase_done(planPath, number)
    append_deviation(planPath, [f"- {time.strftime('%Y-%m-%d')} (Phase {number}): marked done with `tick`, outside "
                                "the coder, review and verification steps of /code."])
    state.update({"stage": "done", "phase": number, "autoAdvance": False, "commitFiles": [], "commitLine": ""})
    state.pop("dispatchAt", None)
    save_state(repoRoot, state)
    emit("stop", f"Phase {number} is marked done in {state['plan']}. Run `start` for the next phase when the user "
         "asks.")


def command_verify(repoRoot, state, args):
    finish_phase(repoRoot, state)


ENV_ASSIGNMENTS = re.compile(r"""(?:[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|[^\s"']*)\s+)+""")
COMMAND_START = re.compile(r"^(?:" + ENV_ASSIGNMENTS.pattern + r")?"
                           r"(cd |npm |npx |pnpm |yarn |git |node |python3? |pytest|ruff |bash |curl |make "
                           r"|cargo |go |deno |bun |uv |poetry |tsc\b|eslint |vitest|jest|mvn |gradle |\./"
                           r"|dotnet |docker |just |rake |bundle |ruby |php |composer |mix |swift |sbt |bazel |tox\b"
                           r"|mypy |pyright|sh )")

# An Automated Verification item that says there is nothing to run: "- [ ] N/A — docs only", "- [ ] none".
NO_AUTOMATED_CHECK = re.compile(r"^- \[[ x]\]\s*[*_`]*\s*(?:n/a|none)\b", re.IGNORECASE)


def verification_command(line):
    # The first backticked span that starts like a shell command, after any leading NAME=value assignments, which the
    # shell passes to the command; the line may continue after it ("`npm run build` exits 0.").
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
    unparsed = []
    timeout = int(os.environ.get("CODE_STEP_VERIFY_TIMEOUT", VERIFY_TIMEOUT_SECONDS))
    for line in automated_verification_items(phaseSection):
        if NO_AUTOMATED_CHECK.match(line):
            continue
        command = verification_command(line)
        if command is None:
            unparsed.append(line.strip())
            continue
        if WHOLE_SUITE.match(ENV_ASSIGNMENTS.sub("", command, count=1)):
            skipped.append(command)
            continue
        code, output = run_command(command, repoRoot, timeout=timeout)
        if "git grep" in command:
            results.append(check_prohibition(repoRoot, command, code, output))
            continue
        results.append((command, code, output))
    return results, skipped, unparsed


def mark_phase_done(planPath, number):
    planLines = planPath.read_text().split("\n")
    entry = next((e for e in parse_plan(planLines)["entries"] if e["number"] == number and not e["done"]), None)
    if entry:
        planLines[entry["line"]] = planLines[entry["line"]].replace("[ ]", "[x]", 1)
    planPath.write_text("\n".join(planLines))


def boundary_decision(state, entries, number):
    # A run started with --phase N ends after phase N, whatever other phases are still open.
    isLast = state.get("onlyPhase") == number or not [e for e in entries if not e["done"] and e["number"] != number]
    if isLast:
        return "C", "last phase"
    if number == "1":
        return "B", "low - Phase 1 calibration" if state["risk"] == "low" else state["risk"]
    if state.get("exception"):
        return "B", "low - exception" if state["risk"] == "low" else state["risk"]
    if state["risk"] == "low":
        return "A", "low"
    return "B", "high"


def mark_review_gate_clean(repoRoot, state):
    # The review-commit-gate hook reads this file: the review loop ended clean, so the session may commit.
    # Returns False after emitting a stop when the hand-back record shows the loop did not end clean, or when the
    # shared hand-back reader is not installed. Nothing is written then.
    module, importError = load_handback()
    if module is None:
        emit("stop", f"Cannot confirm the review loop ended clean: {importError}. The review gate is not marked "
             "clean. Tell the user.")
        return False
    reason = module.false_clean_reason(os.environ.get("CLAUDE_CODE_SESSION_ID"))
    if reason:
        emit("stop", f"The review gate is not marked clean: {reason}. Tell the user.")
        return False
    gateDir = pathlib.Path.home() / ".claude" / "state" / "review-gate"
    gateDir.mkdir(parents=True, exist_ok=True)
    (gateDir / (session_pin() or state.get("sessionId") or "unknown")).write_text("clean\n")
    return True


def count_lines(path):
    try:
        return len(path.read_text(errors="replace").splitlines())
    except OSError:
        return 0


def diff_stat_rows(repoRoot, files):
    # One "path | +added -deleted" row per file: git's numstat for tracked files, the line count for new ones.
    numstat = {}
    for row in (git_output(repoRoot, "diff", "--numstat", "HEAD", "--", *files) or "").splitlines():
        added, deleted, name = row.split("\t", 2)
        numstat[name] = (added, deleted)
    rows = []
    for name in files:
        added, deleted = numstat.get(name) or (str(count_lines(repoRoot / name)), "0")
        rows.append(f"{name} | +{added} -{deleted}")
    return rows


TICKET_IN_NAME = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]+-\d+)(?![A-Za-z0-9])")


def ticket_prefix(state):
    # The ticket id the plan folder or the branch carries, as the commit subject's prefix; "" when neither has one.
    planFolder = pathlib.PurePosixPath(state["plan"]).parent.name if state.get("plan") else ""
    for name in (planFolder, state.get("branch") or ""):
        found = TICKET_IN_NAME.search(name)
        if found:
            return found.group(1) + ": "
    return ""


def phase_commit(repoRoot, state):
    # The phase's own changed files: dirty now, and not dirty before the phase started. Files that were dirty before
    # stay out of the command, except the plan: the script ticks the phase in it, so the commit carries it even when it
    # held other uncommitted edits before the phase. The commit names its files after `--`, so it takes only those
    # files from the index and leaves anything the user staged by hand staged and uncommitted.
    # Returns (text for the user, the commit command line, the files it commits); the text and line are "" with no files.
    baseline = state.get("baseline") or {}
    dirtyNow = file_hashes(repoRoot)
    planName = state.get("plan")
    changedSince = [name for name in dirtyNow if name in baseline and dirtyNow[name] != baseline[name]]
    planHadEarlierEdits = planName in changedSince
    ownFiles = [name for name in dirtyNow if name not in baseline or (name == planName and planHadEarlierEdits)]
    leftOut = [name for name in changedSince if name != planName]
    if not ownFiles:
        return "", "", []
    behaviorLines = state.get("behavior") or []
    message = behaviorLines[0] if behaviorLines else (state.get("title") or "phase work")
    prefix = ticket_prefix(state)
    if prefix and not message.lower().startswith(prefix.lower()):
        message = prefix + message
    quotedFiles = " ".join(shlex.quote(name) for name in ownFiles)
    commitLine = f"git add -- {quotedFiles} && git commit -m {shlex.quote(message)} -- {quotedFiles}"
    lines = ["Files changed by this phase:", *diff_stat_rows(repoRoot, ownFiles), ""]
    if planHadEarlierEdits:
        lines += [f"{planName} had uncommitted edits before the phase. The commit includes them with the phase tick.", ""]
    if leftOut:
        lines += ["Dirty before the phase and left out of the commit: " + ", ".join(leftOut), ""]
    lines += ["Commit command (not run by the script):", commitLine]
    return "\n".join(lines), commitLine, ownFiles


def finish_phase(repoRoot, state, skipVerification=False):
    if not skipVerification and not mark_review_gate_clean(repoRoot, state):
        return

    if not state.get("plan"):
        state["stage"] = "done"
        save_state(repoRoot, state)
        commitText, _, _ = phase_commit(repoRoot, state)
        if commitText:
            say(repoRoot, commitText)
        return emit("stop", "Planless task reviewed. Tell the user the result.")

    planPath = repoRoot / state["plan"]
    if not planPath.is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")

    planLines = planPath.read_text().splitlines()
    plan = parse_plan(planLines)
    if plan["failures"]:
        return emit("stop", plan_failure_message(plan, state["plan"]))

    number = state["phase"]
    section = phase_text(planLines, number) if number is not None else "\n".join(planLines)
    section = section or ""
    verifyResults, skipped, unparsed = ([], [], [])
    if not skipVerification:
        verifyResults, skipped, unparsed = run_verification_commands(repoRoot, section)
    # A section that lists items while none yields a command means the parse missed them: the phase is not verified.
    if unparsed and not verifyResults and not skipped:
        state.update({"stage": "stopped", "stopReason": "verification"})
        save_state(repoRoot, state)
        tickText = (f" For a check that cannot be automated, the user can confirm it; on the user's word only, invoke "
                    f"Skill code with `tick {state['phase']}` to mark the phase done." if state.get("phase") else
                    " For a check that cannot be automated, the user can confirm it and mark the phase done with `tick`.")
        return emit("stop", "The phase has an Automated Verification section but no command could be read from it, so "
                    "nothing was run. Do not mark the phase done. Report to the user; the lines are:",
                    *[f"- {line}" for line in unparsed],
                    "Each item needs a backticked command that starts with a known program (npm, cargo, go, pytest, "
                    "git, bash, sh, ./script ...)." + tickText + " " + RESUME_LINE.format(noun="section", verb="verify"))
    failed = [(command, code, output) for command, code, output in verifyResults if code != 0]
    if failed:
        state.update({"stage": "stopped", "stopReason": "verification"})
        save_state(repoRoot, state)
        return emit("stop", "Automated Verification failed. Do not mark the phase done. Report to the user:",
                    *[f"- `{command}` exit {code}: {output[-400:]}" for command, code, output in failed],
                    RESUME_LINE.format(noun="failure", verb="verify"))

    try:
        manualItems = phase_manual_items(planLines, number, state["plan"])
    except plan_format.PlanFormatError as error:
        state.update({"stage": "stopped", "stopReason": "plan-format"})
        save_state(repoRoot, state)
        return emit("stop", manual_format_message(error, RESUME_LINE.format(noun="section", verb="verify")))

    manualGroups = {
        "verified": [manual_item_line(i) for i in manualItems if i["verified"]],
        "notRun": [manual_item_line(i) for i in manualItems if not i["humanOnly"] and not i["verified"]],
        "humanOnly": [manual_item_line(i) for i in manualItems if i["humanOnly"] and not i["checked"]]}
    reopened = []
    if number is not None:
        isClosing = any(e["number"] == number and e["closing"] for e in plan["entries"])
        mark_phase_done(planPath, number)
        reopened = [] if isClosing else reopen_closing_phases(planPath)
    entries = parse_plan(planPath.read_text().splitlines())["entries"]
    block, riskLabel = boundary_decision(state, entries, number)
    nextPending = ordered_pending(entries)
    commitText, commitLine, commitFiles = phase_commit(repoRoot, state)
    state["stage"] = "done"
    state["autoAdvance"] = block == "A"
    state["commitFiles"] = commitFiles
    state["commitLine"] = commitLine
    state.pop("stopReason", None)
    save_state(repoRoot, state)

    doneText = f"Phase {number} marked done in {state['plan']}." if number is not None \
        else f"The plan {state['plan']} is finished."
    doneLine = (f"{doneText} Verification run: "
                f"{len(verifyResults)} command(s) green ({'; '.join(c for c, _, _ in verifyResults) or 'none'}); "
                f"skipped as covered by the review loop: {len(skipped)}.")
    if reopened:
        doneLine += (f" Closing phase(s) {', '.join(reopened)} were checked and are unchecked again, so they run on "
                     "the new code.")
    print(doneLine)
    say(repoRoot, doneLine)
    if commitText:
        say(repoRoot, commitText)

    if block == "A":
        nextStart = f"{INSTALLED_COMMAND} start" + (f" {state['modifier']}" if state.get("modifier") else "")
        say(repoRoot, block_a(number, riskLabel, manualGroups, nextPending[0]["number"]))
        commitStep = (f"First run this commit command as a Bash call: {commitLine}\nThen " if commitLine else "")
        emit("auto-advance", "The user sees block A at the end of the turn. "
             + f"{commitStep}in the same response run `{nextStart}` for Phase " + nextPending[0]["number"] + ".")
        return
    blockText = block_b_or_c(block, number, riskLabel, state, manualGroups,
                             nextPending[0]["number"] if nextPending else None)
    say(repoRoot, blockText.replace("<<STAGE QUEUE>>", "(the /stage queue is printed above in this turn)"))
    emit("stop-block-" + block,
         "Invoke the Skill tool with `stage` and print its queue verbatim. The user sees the rest of the phase-complete "
         "block at the end of the turn: do not write it. Then wait for the user. When they say continue, run "
         "`code-step.py start`.")


def manual_item_line(item):
    return f"- [{'x' if item['checked'] else ' '}] {item['text']}"


def block_a(number, riskLabel, manualGroups, nextNumber):
    verifiedCount, notRunCount, humanCount = (len(manualGroups[name]) for name in ("verified", "notRun", "humanOnly"))
    return (f"Phase {number} complete - machine gates green (review ✓, execution ✓, automated-verification ✓). "
            f"Risk: low. Manual verification: {verifiedCount} verified, {notRunCount} agent-run items not yet run "
            f"(/verify-branch runs them at the end of the branch), {humanCount} human-only deferred to the "
            f"/verify-branch packet.\n-> Auto-advancing to Phase {nextNumber} in-session (no /clear; interrupt anytime).")


def block_b_or_c(block, number, riskLabel, state, manualGroups, nextNumber):
    behavior = state.get("behavior") or []
    lastText = f"Phase {number} complete (last phase)." if number is not None else "The plan is complete."
    isOnlyPhase = number is not None and state.get("onlyPhase") == number
    if isOnlyPhase:
        lastText = f"Phase {number} complete (the phase this run was started for)."
    parts = [f"Phase {number} complete. Risk: {riskLabel}. Phase-level sign-off requested." if block == "B"
             else lastText, ""]
    if behavior:
        parts += ["Behavior delta (observable change + its proof, max 3 - no internals, no paths):",
                  *[f"- {line}" for line in behavior[:3]], ""]
    parts += ["Read first (/stage queue, blast-radius order):", "<<STAGE QUEUE>>", ""]
    if manualGroups["verified"]:
        parts += ["Verified (checked, or marked agent-verified in the plan):", *manualGroups["verified"], ""]
    if manualGroups["notRun"]:
        parts += ["Agent-run, not yet run (/verify-branch runs these at the end of the branch):",
                  *manualGroups["notRun"], ""]
    if manualGroups["humanOnly"]:
        parts += ["Human-only verification remaining:", *manualGroups["humanOnly"], ""]
    if block == "B":
        queueSteps = ["Read the queue (`]k`/`[k` in nvim)"] if manualGroups["verified"] or manualGroups["humanOnly"] \
            else ["Read the /stage queue"]
        if manualGroups["verified"]:
            queueSteps.append("spot-check the verified items")
        if manualGroups["humanOnly"]:
            queueSteps.append("run the human-only items")
        step1 = "; ".join(queueSteps) + "."
        parts += ["Next:", f"  1. {step1}",
                  f"  2. Stage what you've read, then run /clear and /code to start Phase {nextNumber} fresh. "
                  "To keep this context, confirm here.", "", "Or give feedback now for revisions to Phase " + number + "."]
    elif isOnlyPhase:
        parts += ["This run was started for this phase only. Other phases may be open; run `start` when the user "
                  "asks for the next one."]
    else:
        parts += ["All phases complete. Next: /verify-branch (completeness + review packet; includes the remaining "
                  "human-only checks), then you open the PR."]
    return "\n".join(parts)


def run_guarded_verb(verb, handler, args):
    guard = STAGE_GUARDS[verb]
    repoRoot = repo_root()
    os.chdir(repoRoot)
    state = load_state(repoRoot)
    atStage = state is not None and state["stage"] in guard["stages"]
    reasonAllowed = "stopReasons" not in guard or (state or {}).get("stopReason") in guard["stopReasons"]
    if not atStage or not reasonAllowed:
        return emit("stop", guard["message"])
    handler(repoRoot, state, args)


def command_status():
    state = load_state(repo_root())
    print(json.dumps(state, indent=1) if state else "no code-step state")


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    args = sys.argv[2:]
    verbs = {"start": command_start, "after-coder": command_after_coder, "decide": command_decide,
             "after-plan-edit": command_after_plan_edit, "after-review": command_after_review,
             "asks-done": command_asks_done, "skill-done": command_skill_done, "verify": command_verify,
             "tick": command_tick, "review-again": command_review_again}
    # These verbs open a new /code run after the user answered. The last run's say.md text was already handed back.
    resumeVerbs = ("decide", "asks-done", "verify", "review-again")
    if verb == "hook":
        return command_hook()
    if verb == "plan-hook":
        return command_plan_hook()
    if verb == "stop-hook":
        return command_stop_hook()
    if verb == "plan":
        return command_plan(args)
    if verb == "say-hook":
        return command_say_hook()
    if verb == "status":
        try:
            return command_status()
        except StateFileError as error:
            return print(error)
    if verb not in verbs:
        sys.exit("usage: code-step.py start|after-coder|decide|after-plan-edit|after-review|asks-done|skill-done|verify"
                 "|review-again|tick|hook|stop-hook|say-hook|status|plan|plan-hook")
    if verb in resumeVerbs:
        clear_say(repo_root())
    try:
        if verb in STAGE_GUARDS:
            run_guarded_verb(verb, verbs[verb], args)
        else:
            verbs[verb](args)
    except StateFileError as error:
        emit("stop", f"{error}. Tell the user to delete that file, then run `start`.")


if __name__ == "__main__":
    main()
