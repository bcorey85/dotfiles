#!/usr/bin/env python3
"""code_step.py: the routing of /code as a script. The forked Sonnet subagent of /code runs one verb, reads its
ACTION lines, does exactly that, and runs the next verb. The script builds every prompt and every argument.

  code_step.py start [<plan>] [+fast|+deep] [--phase <id>] [--restart]
                                                next phase of the plan (or the named one): checks, gate, packet, the
                                                exact coder dispatch. `start --help` prints usage. --restart drops an
                                                unfinished run first.
  code_step.py start --task "<text>"           planless work: the coder dispatch without gate or packet
  code_step.py resume                           do the next step of the saved run, whatever stage or stop it is in
  code_step.py decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"
                                                only --by user is the user's own word: a session ruling never changes
                                                a criterion
  code_step.py decide discuss                   ask the user how to rule when the code and the plan disagree; records
                                                nothing
  code_step.py asks-done <outcome>...           log the user's answer to each ask[] entry, then run the phase gates
  code_step.py skill-done <pass|fail>          a closing phase's skill returned: mark it done (pass) or stop (fail)
  code_step.py verify                           re-run the phase gates after a failed Automated Verification was fixed
  code_step.py review-again                     dispatch the review loop again on the same diff, after its packet did
                                                not parse
  code_step.py tick <phase id>                  mark a phase done that the user finished outside /code
  code_step.py hook                             PreToolUse hook on SubagentHandback: save coder and review-loop messages
  code_step.py log-hook                         PostToolUse hook on Agent|SubagentHandback|SendMessage: log launch,
                                                hand-back and resume events of the run
  code_step.py dispatch-hook                    PreToolUse hook on Agent: deny a coder or review-loop launch whose
                                                prompt lacks the saved dispatch prompt, or a repeat launch of a coder
  code_step.py stop-hook                        SubagentStop hook: keep the /code fork from stopping while a dispatch
                                                is open
  code_step.py plan-hook                        PostToolUse hook on Edit|Write: reject a plan edit that does not parse
  code_step.py status                           print the saved state

One coder runs per phase. The current skill's two parallel coders for deliverables that share no file are dropped by
design.
Run from the repo root. State lives in <git dir>/code-step/. Env CODE_STEP_CLAUDE_DIR overrides ~/.claude.
Each run also keeps <git dir>/code-step/runs/<run id>/events.jsonl and one prompt-<dispatch id>.txt per dispatch."""
import collections
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
INSTALLED_COMMAND = "python3 ~/.claude/scripts/code_step.py"
EVENT_VERSION = 1
RUNS_DIR_NAME = "runs"
DISPATCH_MARKER = "code-step-dispatch:"
DISPATCH_MARKER_PATTERN = re.compile(re.escape(DISPATCH_MARKER) + r"\s+([^\s/]+)/(d\d+)\b")
PROMPT_DENIAL_LIMIT = 3
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
LAUNCH_EXPECTED_SECONDS = 60
FORK_STOP_BLOCK_LIMIT = 2
BASH_TIMEOUT_MS = 600000
CODER = "coder"
REVIEW_LOOP = "review-loop"
GATE_RESULTS_THAT_END_THE_WAIT = ("pass", "cap")
START_USAGE = ('usage: code_step.py start [<plan>] [+fast|+deep] [--phase <id>] [--restart]\n'
               '       code_step.py start --task "<task text>"\n'
               '--phase <id> starts the named phase. Text that follows the plan (or comes first, when there is no '
               'plan file, ticket id or directory) is the task text. A flag before it, or after a plan, must be '
               'known. --restart drops an unfinished run and starts over. --take-over starts over a run that another '
               'live session left open in this checkout.')
FOLLOW_UP_HINT = ("A follow-up change to a finished plan needs the task text: invoke Skill code with "
                  "`start --task \"<text>\"`.")
OTHER_SESSION_LIVE_SECONDS = 2 * 60 * 60
WAITING_STAGES = ("asks", "impact-coder", "impact-review", "skill", "plan-coder")
ASKS_DONE_USAGE = ("asks-done needs one outcome per ask: accepted, rejected or modified. Each modified ask needs the "
                   "user's change after it as `--change \"<text>\"`.")
# The state each guarded verb needs: the stages it may run at, the stop reasons it accepts when the stage is "stopped",
# and the refusal text when the state is anything else. `start`, `tick` and `resume` run at any stage and are not in
# the table. A review-loop resumed after the wait cap also counts for review-again.
STAGE_GUARDS = {
    "decide": {"stages": ("impact-coder", "impact-review"),
               "message": "decide needs a pending PLAN-IMPACT and one word: adopt, keep or discuss."},
    "review-again": {"stages": ("stopped",), "stopReasons": ("invalid-packet",),
                     "message": "review-again ran with no unreadable review packet or silent review-loop pending."},
    "asks-done": {"stages": ("asks",), "message": ASKS_DONE_USAGE},
    "skill-done": {"stages": ("skill",), "message": "skill-done ran with no closing-phase skill pending."},
    "verify": {"stages": ("stopped",), "stopReasons": ("verification", "plan-format"),
               "message": "verify ran with no failed Automated Verification or unparsed Manual Verification pending."},
}
RESUME_VERB = "resume"
# The verbs that older printed commands still name. Each one now does what `resume` does.
RESUME_ALIASES = ("after-coder", "after-review", "after-plan-edit")
VERB_WORDS_REPLACED_BY_RESUME = ("continue", "resume", *RESUME_ALIASES)
VERB_WORDS_THAT_CARRY_INPUT = ("review-again", "decide", "asks-done", "skill-done", "tick", "verify")
RESUMABLE_STOP_REASONS = STAGE_GUARDS["verify"]["stopReasons"] + STAGE_GUARDS["review-again"]["stopReasons"]
RESUME_LINE = "When the {noun} is fixed, run `python3 ~/.claude/scripts/code_step.py {verb}`."
VERIFY_TIMEOUT_SECONDS = 600
TIMEOUT_EXIT_CODE = 124
HOOK_STAGES = ("coder", "review", "asks-coder", "plan-coder")
CODER_STAGES = ("coder", "asks-coder")
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
    state_file = directory / "state.json"
    try:
        return json.loads(state_file.read_text())
    except ValueError:
        raise StateFileError(f"{state_file} is not readable JSON") from None


def current_branch(cwd):
    return git_output(cwd, "branch", "--show-current") or "-"


def save_state(cwd, state):
    directory = state_dir(cwd)
    directory.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(directory / "state.json", json.dumps(state, indent=1))


# ---------- event log ----------

def runs_dir(cwd):
    return state_dir(cwd) / RUNS_DIR_NAME


def start_run(cwd):
    # A new run: the logs and prompt files of older runs go, and the new run's id comes back. The run's folder is made
    # by its first write.
    shutil.rmtree(runs_dir(cwd), ignore_errors=True)
    return script_utils.sortable_unique_id()


def run_events_path(cwd, run_id):
    return runs_dir(cwd) / run_id / "events.jsonl"


def log_event(cwd, run_id, event, session_id, **fields):
    row = {"v": EVENT_VERSION, "ts": time.time(), "event": event, "session_id": session_id, **fields}
    script_utils.append_jsonl(run_events_path(cwd, run_id), row)


def read_events(cwd, run_id):
    return script_utils.read_jsonl(run_events_path(cwd, run_id))


def dispatch_marker(prompt_text):
    # (run id, dispatch id) of the last marker in the prompt of an Agent call, or None. The marker counts wherever it
    # stands: on its own line, after other text on a folded line, or with text after it.
    found = DISPATCH_MARKER_PATTERN.findall(str(prompt_text or ""))
    return found[-1] if found else None


def dispatch_standing(events):
    # What the log says of the newest dispatch: the launch that names it (the first one) and the denials of Agent calls
    # for it. Hand-backs, stops and the open or closed reading are not read from the log yet.
    dispatches = [event for event in events if event.get("event") == "dispatch"]
    if not dispatches:
        return {"dispatch": None, "launched": None, "blocks": []}
    current = dispatches[-1]
    of_current = [event for event in events if event.get("dispatch") == current["id"]]
    launches = [event for event in of_current if event.get("event") == "launch"]
    blocks = [event for event in of_current if event.get("event") == "fork-block"]
    return {"dispatch": current, "launched": launches[0] if launches else None, "blocks": blocks}


def record_dispatch(repo_dir, state, verb, agent_type, model, prompt):
    # Saves the dispatch prompt in the run's folder, ending with the marker line that the launch hook reads back, and
    # logs the dispatch. Returns the prompt with its marker and the path of the saved file.
    run_id = state["runId"]
    dispatch_count = sum(1 for event in read_events(repo_dir, run_id) if event.get("event") == "dispatch")
    dispatch_id = f"d{dispatch_count + 1}"
    marked_prompt = f"{own_path(prompt).rstrip()}\n\n{DISPATCH_MARKER} {run_id}/{dispatch_id}"
    prompt_file = runs_dir(repo_dir) / run_id / f"prompt-{dispatch_id}.txt"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(marked_prompt + "\n")
    log_event(repo_dir, run_id, "dispatch", session_pin(), id=dispatch_id, agent_type=agent_type, stage=state["stage"],
              verb=verb, model=model, prompt_file=str(prompt_file))
    return marked_prompt, prompt_file


def emit_dispatch(repo_dir, state, verb, *lines, prompt, agent, model=None):
    # The one way a dispatch reaches the fork: logged and saved first, then printed with the path of the saved prompt.
    # Every agent it dispatches runs a gate, so the repo's gate env vars go in the prompt.
    plan_rel = state.get("plan")
    gate_env = plan_format.repo_gate_env(repo_dir, plan_rel)
    gate_env_text = plan_format.gate_env_text(gate_env)
    if gate_env_text:
        prompt = f"{prompt.rstrip()}\n\n{gate_env_text}"

    marked_prompt, prompt_file = record_dispatch(repo_dir, state, verb, agent, model, prompt)

    emit("dispatch", *lines, next_after(verb), prompt=marked_prompt, agent=agent, model=model, prompt_file=prompt_file)


def saved_messages(cwd, agent_type, stage, skip_rows=0, agent_id=None):
    # The last message per agent id of this type saved while the state was in this stage, ignoring the first
    # skip_rows rows of the file. With agentId, only that agent's rows count.
    reports_file = state_dir(cwd) / "reports.jsonl"
    if not reports_file.exists():
        return []
    last_per_agent = {}
    for line in reports_file.read_text().splitlines()[skip_rows:]:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if agent_id is not None and row.get("agent_id") != agent_id:
            continue
        if row["agent_type"] == agent_type and row["stage"] == stage:
            last_per_agent.pop(row["agent_id"], None)
            last_per_agent[row["agent_id"]] = row["message"]
    return list(last_per_agent.values())


def report_rows(repo_dir, agent_type):
    # Every saved hook row of this agent type, oldest first. Lines that are not JSON objects are skipped.
    reports_file = state_dir(repo_dir) / "reports.jsonl"
    if not reports_file.exists():
        return []
    rows = []
    for line in reports_file.read_text().splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("agent_type") == agent_type:
            rows.append(row)
    return rows


def is_after(row, since):
    # A row without a numeric timestamp is old.
    return isinstance(row.get("ts"), (int, float)) and row["ts"] > since


def coder_rows(repo_dir, stage, since=None):
    # The saved rows of this stage that the hand-back gate let through, oldest first. The rows of a coder whose latest
    # gate result is not pass or cap are left out: that coder is a draft or still running, so its row is not a report.
    # With `since` (the dispatch time) a row saved before that dispatch is left out.
    rows = []
    for row in report_rows(repo_dir, CODER):
        if row.get("stage") != stage:
            continue
        if since is not None and not is_after(row, since):
            continue
        if coder_gate_allows(repo_dir, row.get("agent_id") or "unknown"):
            rows.append(row)
    return rows


def resumed_coder_row(repo_dir, state):
    # The row the resumed coder saved after the stop, whatever its stage or gate result: the hook saves the flipped
    # state before it writes the row, so a row of that coder while the stage still reads stopped means a stale save
    # overwrote the flip. None when the state awaits no resumed coder or the coder has not handed back.
    if not awaits_resumed_coder(state) or not state.get("resumableCoderId"):
        return None
    for row in reversed(report_rows(repo_dir, CODER)):
        if row.get("agent_id") == state["resumableCoderId"] and is_after(row, state["resumableCoderAt"]):
            return row
    return None


def latest_coder_row(repo_dir, stage, since=None):
    # The saved row of the coder dispatched last: the newest row of coder_rows. Rows of earlier coders of the same
    # stage are not part of it. None when no such row exists.
    rows = coder_rows(repo_dir, stage, since)
    return rows[-1] if rows else None


def latest_coder_message(repo_dir, stage, since=None):
    row = latest_coder_row(repo_dir, stage, since)
    return None if row is None else row.get("message", "")


def with_earlier_report(state, latest_report):
    # An addendum coder of the same phase run reports on top of the coder before it: both reports describe the change.
    # None when there is no latest report, so a missing hand-back still reads as missing.
    if latest_report is None:
        return None
    return "\n\n".join(filter(None, [state.get("earlierCoderReport"), latest_report]))


def session_pin():
    # The id of the session that runs /code. The fork sees its parent's id here, and hook events carry the same id.
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or None


def head_commit(repo_dir):
    head = git_output(repo_dir, "rev-parse", "HEAD")
    return head.strip() if head else None


def committed_since(repo_dir, base_head):
    # Files the coder committed itself since the phase started. A commit leaves no dirty file behind, so the dirty
    # list alone would call the phase empty.
    if not base_head or head_commit(repo_dir) in (None, base_head):
        return []
    return git_names(repo_dir, "diff", "--name-only", base_head, "HEAD")


def uncommitted_files(repo_dir, previous):
    # The files of the previous phase's commit line that are still dirty.
    files = previous.get("commitFiles") or []
    if not files:
        return []
    return git_names(repo_dir, "status", "--porcelain", "--", *files)


def abandon_open_dispatch(repo_dir, previous):
    # A run that starts over leaves no open dispatch behind: the stage becomes stopped and dispatchAt goes. The
    # baseline stays, so a restart of the same phase keeps its own-files record.
    if previous.get("dispatchAt") is None or previous.get("stage") not in HOOK_STAGES:
        return
    abandoned = dict(previous)
    abandoned.pop("dispatchAt")
    abandoned["stage"] = "stopped"
    save_state(repo_dir, abandoned)


def open_dispatch(state):
    # A dispatch is open from here until the dispatched agent's hand-back row is newer than dispatchAt.
    state["dispatchAt"] = time.time()
    if not state.get("runId"):
        state["runId"] = script_utils.sortable_unique_id()
    state.pop("forkDenied", None)
    state.pop("forkStopBlocks", None)


def timed_command(verb):
    return f"`{INSTALLED_COMMAND} {verb}` as a Bash call with timeout {BASH_TIMEOUT_MS}"


def next_after(verb):
    return f"NEXT: right after the Agent call, run {timed_command(verb)}."


def expected_agent(state):
    return REVIEW_LOOP if state.get("stage") == "review" or awaits_resumed_review(state) else CODER


def ask_text(item):
    # The shared reader copies a finding into the question (and the reverse) when only one is given: show it once.
    return script_utils.joined_distinct([str(item.get("finding") or ""), str(item.get("question") or "")])


def load_handback():
    # The shared hand-back reader is imported where it is used. When it is missing the caller reports that and stops.
    try:
        import handback
    except ImportError as error:
        return None, f"handback.py could not be imported ({error}); install it beside code_step.py"
    return handback, None


def handback_store_row(state):
    # The review-loop hand-back the shared store holds for the pinned session, or None.
    session_id = state.get("sessionId")
    module, _ = load_handback()
    if module is None or not session_id:
        return None
    try:
        return module.latest(session_id)["handback"]
    except (OSError, ValueError, KeyError):
        return None


def coder_gate_allows(repo_dir, agent_id):
    # The coder's hand-back counts once the hand-back gate let it through (pass) or gave up (cap). With no gate set
    # there is nothing to wait for. A deny sends the coder back to work, so its row is not the report.
    try:
        gate = gate_results(repo_dir)
    except ValueError:
        return True
    if gate is None:
        return True
    result = (gate.get("coders") or {}).get(agent_id, {}).get("result")
    return result in GATE_RESULTS_THAT_END_THE_WAIT


def pending_review_agent_id(repo_dir, state):
    # The agent id of the launch of the pending review dispatch, or None when that dispatch has no launch row yet. A
    # review-loop resumed with SendMessage keeps this id.
    if not state.get("runId"):
        return None
    standing = dispatch_standing(read_events(repo_dir, state["runId"]))
    dispatch, launched = standing["dispatch"], standing["launched"]
    if dispatch is None or launched is None or dispatch.get("agent_type") != REVIEW_LOOP:
        return None
    return launched.get("agent_id")


def from_pending_review_launch(repo_dir, state, rows):
    # The review-loop hand-back rows that count: those from the agent the pending review dispatch launched. With no
    # launch row yet, none does.
    launch_id = pending_review_agent_id(repo_dir, state)
    if launch_id is None:
        return []
    return [row for row in rows if row.get("agent_id") == launch_id]


def latest_handback_row(repo_dir, state, agent_type, since):
    # The one source of the wait and of the fork denial: the newest hand-back row of this agent type after `since`.
    # A row without a timestamp is old. A state with no pinned session claims no hand-backs. A review-loop row counts
    # only when its agent id is the launch id of the pending review dispatch.
    if not state.get("sessionId"):
        return None
    rows = report_rows(repo_dir, agent_type)
    if agent_type == REVIEW_LOOP:
        store_row = handback_store_row(state)
        if isinstance(store_row, dict):
            rows.append(store_row)
        rows = from_pending_review_launch(repo_dir, state, rows)
    fresh = [row for row in rows if is_after(row, since)]
    if agent_type == CODER:
        fresh = [row for row in fresh if coder_gate_allows(repo_dir, row.get("agent_id") or "unknown")]
    return max(fresh, key=lambda row: row["ts"]) if fresh else None


def dispatch_time_text(since):
    return datetime.datetime.fromtimestamp(since).isoformat(timespec="seconds")


def awaits_resumed_coder(state):
    # The run stopped on a coder's report and the user answered: that coder, resumed with SendMessage, has no dispatch
    # of its own. Its hook puts the stage back to coder when it hands back.
    return state.get("stage") == "stopped" and state.get("resumableCoderAt") is not None


def awaits_resumed_review(state):
    # The wait for a review-loop gave up at the cap and stopped the run. The user may resume that review-loop with
    # SendMessage: its hand-back, still after dispatchAt, then counts as the pending review.
    return state.get("stage") == "stopped" and bool(state.get("resumableReview"))


def sent_message_since(repo_dir, state, since, agent_id=None):
    # True when the log of the run holds a SendMessage after `since`, to `agentId` when one is given.
    if not state.get("runId"):
        return False
    for event in read_events(repo_dir, state["runId"]):
        if event.get("event") != "resume" or not is_after(event, since):
            continue
        if agent_id is None or event.get("agent_id") == agent_id:
            return True
    return False


def dispatch_since(state):
    # The time the agent that the next verb waits for was dispatched, or None when the state records none. A coder
    # resumed after a stop counts from the stop.
    if state.get("dispatchAt") is not None:
        return state["dispatchAt"]
    if awaits_resumed_coder(state):
        return state["resumableCoderAt"]
    return None


def put_resumed_coder_back(repo_dir, state):
    # A coder resumed after the run stopped on its report is the same coder: its next hand-back goes to review. Its
    # dispatch time is the stop.
    state["stage"] = "coder"
    state["dispatchAt"] = state.pop("resumableCoderAt")
    state.pop("resumableCoderId", None)
    state.pop("resumeWaitAt", None)
    state.pop("forkDenied", None)
    state.pop("forkStopBlocks", None)
    save_state(repo_dir, state)


def put_resumed_review_back(repo_dir, state):
    # A review-loop resumed after the wait cap is the pending review again: its hand-back goes to the review step. It
    # keeps the dispatch time of the loop that went past the cap.
    state["stage"] = "review"
    state.pop("resumableReview")
    state.pop("resumeWaitAt", None)
    save_state(repo_dir, state)


def resumed_agent_pending_stop(agent_type):
    # The stop text for a resume that ran while the agent the user resumed has not handed back yet.
    return (f"The resumed {agent_type} has not handed back yet. Do not dispatch again and do not run `start`. Once it "
            f"has handed back, run {timed_command(RESUME_VERB)}.")


def unlaunched_dispatch(repo_dir, state, agent_type):
    # The newest dispatch of this run when its Agent call never left: no launch row, and older than the launch grace.
    # Only the dispatch the state is in can be waited for; a resumed agent has a launch row of its own.
    if state.get("stage") not in HOOK_STAGES or not state.get("runId"):
        return None
    standing = dispatch_standing(read_events(repo_dir, state["runId"]))
    dispatch = standing["dispatch"]
    if dispatch is None or standing["launched"] is not None:
        return None

    if dispatch.get("stage") != state["stage"] or dispatch.get("agent_type") != agent_type:
        return None

    grace_seconds = float(os.environ.get("CODE_STEP_LAUNCH_SECONDS", LAUNCH_EXPECTED_SECONDS))
    if time.time() - dispatch["ts"] < grace_seconds:
        return None
    return dispatch


def emit_unlaunched_dispatch(dispatch):
    # Prints the logged dispatch again from its saved prompt file. It logs no new dispatch: the first one stands.
    prompt_file = pathlib.Path(dispatch.get("prompt_file") or "")
    age = time.time() - dispatch["ts"]
    notice = (f"Dispatch {dispatch['id']} was logged {age:.0f} seconds ago and no Agent call for it was launched. "
              "Make the Agent call now with the prompt below; do not wait for it.")
    next_verb = next_after(dispatch["verb"])
    agent = dispatch.get("agent_type")
    model = dispatch.get("model")

    try:
        saved_prompt = prompt_file.read_text().rstrip()
    except OSError:
        emit("dispatch", notice, f"Read the prompt file {prompt_file} and pass its whole text.", next_verb,
             agent=agent, model=model, prompt_file=prompt_file)
        return

    emit("dispatch", notice, next_verb, prompt=saved_prompt, agent=agent, model=model, prompt_file=prompt_file)


def wait_for_handback(repo_dir, state, verb, long_checks_follow=False):
    # Nested Agent calls return at once, so the verb that follows a dispatch waits here for the hand-back row.
    # CODE_STEP_WAIT_SECONDS=0 skips the wait. Returns False after emitting the line that says to run the verb again,
    # or a stop once the dispatch is older than HANDBACK_TOTAL_WAIT_MULTIPLE waits. long_checks_follow: when the wait
    # took longer than FRESH_CALL_AFTER_SECONDS, return False so the checks after it start in a call of their own.
    limit = float(os.environ.get("CODE_STEP_WAIT_SECONDS", HANDBACK_WAIT_SECONDS))
    if limit <= 0:
        return True
    since = dispatch_since(state)
    if since is None:
        return True
    interval = float(os.environ.get("CODE_STEP_POLL_SECONDS", HANDBACK_POLL_SECONDS))
    agent_type = expected_agent(state)
    total_cap = limit * HANDBACK_TOTAL_WAIT_MULTIPLE
    wait_started = time.time()
    if awaits_resumed_coder(state) or awaits_resumed_review(state):
        # A resumed agent's dispatch time is the stop that came before the user's answer, so the cap counts from the
        # first wait on it. The first wait is saved once; the hook that sees the resumed hand-back clears it.
        if state.get("resumeWaitAt") is None:
            # The hook may have put the stage back since this state was read: save onto the newest state, and only
            # while the agent is still awaited, so the save never overwrites that flip.
            newest = load_state(repo_dir) or state
            if awaits_resumed_coder(newest) or awaits_resumed_review(newest):
                newest["resumeWaitAt"] = wait_started
                save_state(repo_dir, newest)
            state["resumeWaitAt"] = wait_started
        clock_start = state["resumeWaitAt"]
    else:
        clock_start = since
    # The wait ends at the cap, not at the end of the wait that passes it.
    until_cap = max(0.0, clock_start + total_cap - wait_started)
    ends_at_cap = until_cap <= limit

    def handback_or_unlaunched():
        # The state is read again on each poll: a hook may pin the session while the wait runs.
        handback_row = latest_handback_row(repo_dir, load_state(repo_dir) or state, agent_type, since)
        if handback_row:
            return "handback", handback_row
        if until_cap <= 0:
            # The cap is spent: the cap stop comes next, not another print of the dispatch.
            return None
        dispatch = unlaunched_dispatch(repo_dir, load_state(repo_dir) or state, agent_type)
        return ("unlaunched", dispatch) if dispatch else None

    found = script_utils.wait_for(handback_or_unlaunched, min(limit, until_cap), interval)
    if found and found[0] == "unlaunched":
        emit_unlaunched_dispatch(found[1])
        return False
    if found:
        waited = time.time() - wait_started
        threshold = float(os.environ.get("CODE_STEP_FRESH_CALL_SECONDS", FRESH_CALL_AFTER_SECONDS))
        if long_checks_follow and waited > threshold:
            emit("wait", f"The report arrived after {waited:.0f} seconds; run the same command again so the checks "
                 f"after it start in a call of their own: {timed_command(verb)}.")
            return False
        return True
    if ends_at_cap:
        resume_text = ""
        stopped_at = time.time()
        state.pop("stopReason", None)
        if agent_type == REVIEW_LOOP:
            state["resumableReview"] = stopped_at
            resume_text = (f" If the user resumes it with SendMessage, run {timed_command(RESUME_VERB)}. If it died, "
                          f"the user's word to review the same diff again runs `{INSTALLED_COMMAND} review-again`.")
        else:
            resume_text = stop_a_silent_coder(repo_dir, state, stopped_at)
        state["stage"] = "stopped"
        # The cap is spent: a wait after the user resumes the agent again counts from its own first wait.
        state.pop("resumeWaitAt", None)
        save_state(repo_dir, state)
        emit(
            "stop",
            f"The {agent_type} dispatched at {dispatch_time_text(clock_start)} has not handed back in "
            f"{stopped_at - clock_start:.0f} seconds (the cap is {total_cap:g}). It may have died or been stopped. Do "
            "not "
            "dispatch it again and do not wait longer. Tell the user." + resume_text,
        )
        return False
    emit("wait", f"The dispatched agent has not handed back after {limit:g} seconds. Do not dispatch it again and do "
         f"not hand back. To keep waiting, run the same command again: `{INSTALLED_COMMAND} {verb}` (Bash timeout "
         f"{BASH_TIMEOUT_MS}).")
    return False


def restart_instruction(state, restart_command="start --restart"):
    # A restart with no task text resolves the branch's plan, which is the wrong work for a run that had no plan.
    # A plan run keeps its single phase and its modifier through the restart.
    modifier_words = [state["modifier"]] if state.get("modifier") else []
    if state.get("plan"):
        phase_words = ["--phase", str(state["onlyPhase"])] if state.get("onlyPhase") else []
        return "run `" + " ".join([restart_command, *phase_words, *modifier_words]) + "`"

    planless_words = [restart_command, *modifier_words, "--task", "\"<the task text>\""]
    return "ask the user for the task text, then run `" + " ".join(planless_words) + "`"


def stop_a_silent_coder(repo_dir, state, stopped_at):
    # The coder wait ran to the cap. A coder whose launch has an agent id can be resumed with SendMessage: the state
    # then reads like the stop on a coder's report. A coder that was resumed once keeps its id. Only the phase coder
    # is resumed this way: the hook puts a resumed coder back at the coder stage, so a plan-edit coder, and a launch
    # with no agent id, leave only a restart.
    restart_command = script_command("start --restart")
    restart_instruction_text = restart_instruction(state, restart_command)
    if awaits_resumed_coder(state):
        agent_id = state["resumableCoderId"]
    elif state.get("stage") == "plan-coder":
        state["stopReason"] = "coder-cap"
        return (" The plan-edit coder cannot be resumed: only the phase coder can. To dispatch the phase coder "
                f"again, {restart_instruction_text}.")
    else:
        standing = (
            dispatch_standing(read_events(repo_dir, state["runId"])) if state.get("runId") else {"launched": None}
        )
        launched = standing["launched"]
        agent_id = launched.get("agent_id") if launched else None
        if not agent_id:
            state["stopReason"] = "coder-cap"
            return (f" Its launch has no agent id, so it cannot be resumed: {restart_instruction_text} "
                    "to dispatch a new one.")

    state["resumableCoderAt"] = stopped_at
    state["resumableCoderId"] = agent_id
    state.pop("dispatchAt", None)
    return (f" If the user resumes coder {agent_id} with SendMessage, run {timed_command(RESUME_VERB)}. To dispatch a "
            f"new coder instead, {restart_instruction_text}.")


def own_path(text):
    # Printed commands name this file by its real path, so they work from a bench copy as well as from
    # ~/.claude/scripts.
    return text.replace(INSTALLED_COMMAND, SELF_COMMAND)


def say_file_in(directory):
    # say.md sits in the state folder, one level above the run folders.
    return directory / "say.md"


def say_file(repo_dir):
    # The real path of say.md for this repo.
    directory = state_dir(repo_dir)
    return say_file_in(directory) if directory is not None else pathlib.Path("say.md")


def say(repo_dir, text):
    # User-facing text goes to a file the /code subagent hands back verbatim, so the model never has to copy it.
    directory = state_dir(repo_dir)
    if directory is None:
        return
    directory.mkdir(parents=True, exist_ok=True)
    with open(say_file_in(directory), "a") as say_handle:
        say_handle.write(own_path(text).rstrip() + "\n\n")


def command_say_hook():
    # Stop hook: print the saved user-facing text as the hook's systemMessage, keep a copy in say.log, empty say.md.
    try:
        event = json.loads(sys.stdin.read() or "{}")
        directory = state_dir(pathlib.Path(event.get("cwd") or os.getcwd()))
        if directory is None or not say_file_in(directory).exists():
            return
        say_path = say_file_in(directory)
        is_stale = time.time() - say_path.stat().st_mtime > SAY_MAX_AGE_SECONDS
        text = say_path.read_text().strip()
        say_path.write_text("")
        if not text or is_stale:
            return
        with open(directory / "say.log", "a") as log_file:
            log_file.write(f"--- {datetime.datetime.now().isoformat()}\n{text}\n")
        print(json.dumps({"systemMessage": text}))
    except Exception as error:
        print(f"code-step say-hook: {error}", file=sys.stderr)


def clear_say(repo_dir):
    directory = state_dir(repo_dir)
    if directory is not None and say_file_in(directory).exists():
        say_file_in(directory).write_text("")


def ask_user(repo_dir, instruction, *question_lines):
    # The /code subagent cannot ask the user: the question goes in say.md for the main session to ask.
    say(repo_dir, "\n".join(["## Question for the user", "", "Main session: " + instruction, "", *question_lines]))
    emit("ask-user", f"The question for the user is in {say_file(repo_dir)}. Hand back.")


def emit(action, *lines, prompt=None, agent=None, model=None, prompt_file=None):
    lines = [own_path(line) for line in lines]
    header_lines = [f"ACTION: {action}"]
    if agent:
        header_lines += [f"AGENT: {agent}", f"MODEL: {model or 'omit the model argument'}"]

    for header_line in header_lines:
        print(header_line)
    if agent:
        print("BACKGROUND: no. Never set run_in_background. The Agent call returns at once: do not wait for its "
              "result; the NEXT verb waits for the report.")
    for line in lines:
        print(line)
    if prompt_file is not None:
        print(f"PROMPT FILE: {prompt_file}")
    if prompt is not None:
        print("PROMPT (pass it verbatim, add and remove nothing):")
        print("-----BEGIN PROMPT-----")
        print(own_path(prompt))
        print("-----END PROMPT-----")
    if agent:
        # A reader that keeps only the tail of a long output still sees what to do.
        for header_line in header_lines:
            print(header_line)
        for line in lines:
            if line.startswith("NEXT:"):
                print(line)


def script_command(verb_words):
    return f"{INSTALLED_COMMAND} {verb_words}".rstrip()


def task_command(task_words, modifier):
    # The `start` line that runs the words as task text, with the user's +fast or +deep kept.
    quoted_task_text = shlex.quote(" ".join(task_words))
    modifier_words = [modifier] if modifier else []
    return script_command(" ".join(["start", *modifier_words, "--task", quoted_task_text]))


def refuse(reason, *commands, notes=()):
    # The one shape of a refusal: `Refused: <reason>` first. One command to run instead prints `ACTION: rerun` with it;
    # a choice between commands prints `ACTION: stop` and lists them. Nothing was changed.
    print("Refused: " + own_path(reason))
    if len(commands) == 1:
        return emit("rerun", "COMMAND: " + commands[0], *notes)
    command_lines = [f"- `{command}`" for command in commands]
    choices = ["Run one of these on the user's word:", *command_lines]
    return emit("stop", *choices, *notes)


# ---------- plan parsing ----------

def closing_skill(title):
    return next((skill for pattern, skill in CLOSING_PHASES if pattern.search(title)), None)


def parse_plan(plan_lines):
    return plan_format.parse_plan(plan_lines, closing_skill)


def gated_phase_text(entries):
    return "; ".join(f"Phase {entry['number']} (gate: {entry['gate']})" for entry in entries)


def gate_blockers(pending):
    # A run never starts a phase past an open gated one. Returns the gated open phases ahead of the first open phase
    # without a gate, and that phase (None when every open phase is gated).
    next_ungated = next((entry for entry in pending if not entry["gate"]), None)
    gated_ahead = pending[:pending.index(next_ungated)] if next_ungated else pending
    return gated_ahead, next_ungated


def gate_block_text(gated_ahead, next_ungated):
    gated_text = gated_phase_text(gated_ahead)
    text = f"open phases with a gate clause come first: {gated_text}. The script does not judge a gate."
    if next_ungated:
        text += f" The next open phase without a gate is Phase {next_ungated['number']}."
    return text + " `start --phase <id>` runs one anyway."


def moved_phase_text(entries):
    return ", ".join(f"Phase {entry['number']} to {entry['movedTo']}" for entry in entries if entry["moved"])


def moved_phase_stop(entry, plan_name, coder_ran=False):
    # coder_ran is True when the phase became moved after its coder was dispatched.
    if coder_ran:
        ran_text = "The coder ran, and its work is not marked done or committed."
    else:
        ran_text = "No coder was dispatched."
    return (f"Phase {entry['number']} is moved to {entry['movedTo']} in {plan_name}, so this plan does not run it. "
            f"{ran_text} Tell the user; the phase is worked under {entry['movedTo']}.")


def ordered_pending(entries):
    pending = [entry for entry in entries if entry["open"]]
    return [e for e in pending if not e["closing"]] + [e for e in pending if e["closing"]]


def reopen_closing_phases(plan_path):
    plan_lines = plan_path.read_text().split("\n")
    reopened = [e for e in parse_plan(plan_lines)["entries"] if e["closing"] and e["done"]]
    for entry in reopened:
        plan_lines[entry["line"]] = re.sub(r"\[[xX]\]", "[ ]", plan_lines[entry["line"]], count=1)
    plan_path.write_text("\n".join(plan_lines))
    return [entry["number"] for entry in reopened]


def added_phase_lines(repo_dir, state):
    before = state.get("phaseText")
    if before is None or not state.get("plan"):
        return None
    plan_lines = (repo_dir / state["plan"]).read_text().splitlines()
    after = phase_text(plan_lines, state["phase"])
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
        tool_input = event.get("tool_input") or {}
        edited_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
        if not isinstance(cwd, str) or not isinstance(edited_path, str) or not edited_path:
            return
        state = load_state(cwd)
        if state is None or not state.get("plan"):
            return
        plan_path = pathlib.Path(cwd) / state["plan"]
        if pathlib.Path(edited_path).resolve() != plan_path.resolve():
            return
        plan_lines = plan_path.read_text().splitlines()
        plan = parse_plan(plan_lines)
        if plan["failures"]:
            print(plan_failure_message(plan, state["plan"]), file=sys.stderr)
            sys.exit(2)
        manual_failure = manual_format_failure(plan_lines, state["plan"])
        if manual_failure:
            print(manual_failure, file=sys.stderr)
            sys.exit(2)
        verification_failure = verification_format_failure(
            plan_lines, state["plan"], pathlib.Path(cwd), plan["entries"]
        )
        if verification_failure:
            print(verification_failure, file=sys.stderr)
            sys.exit(2)
    except ValueError:
        return
    except (OSError, StateFileError) as error:
        print(f"code-step plan-hook: {error}", file=sys.stderr)


def plan_failure_rows(plan, plan_name):
    return [f"{plan_name}:{f['line']}: {f['kind']}: {f['detail']}" for f in plan["failures"]]


def plan_failure_message(plan, plan_name):
    rows = plan_failure_rows(plan, plan_name)
    return "The plan's Phase Status does not parse. Report each line to the user and stop:\n" + "\n".join(rows)


def phase_manual_items(plan_lines, number, plan_name):
    # The grammar reads the whole plan, so a PlanFormatError names the line in the file. A phase keeps its own items.
    items = plan_format.manual_verification("\n".join(plan_lines), plan_name)
    if number is None:
        return items
    return [item for item in items if item["phase"] == str(number)]


def manual_format_message(error, resume_line=""):
    message = ("The plan's Manual Verification section does not parse. Do not mark the phase done. Report to the "
               f"user and stop:\n{error}")
    return message + ("\n" + resume_line if resume_line else "")


def manual_format_failure(plan_lines, plan_name, resume_line=""):
    # The stop message for a Manual Verification section the grammar does not parse, or None when all parse.
    try:
        plan_format.manual_verification("\n".join(plan_lines), plan_name)
    except plan_format.PlanFormatError as error:
        return manual_format_message(error, resume_line)
    return None


def phase_text(plan_lines, number):
    section = plan_format.phase_section(plan_lines, number)
    if section is None:
        return None
    return "\n".join(plan_lines[section["start"]:section["end"]])


def command_plan(args):
    if len(args) < 2 or args[0] not in ("check", "parse"):
        sys.exit("usage: code_step.py plan check|parse <path>")
    plan_lines = pathlib.Path(args[1]).read_text().splitlines()
    plan = parse_plan(plan_lines)
    if args[0] == "parse":
        return print(json.dumps(plan, indent=1))
    for row in plan_failure_rows(plan, args[1]):
        print(row)
    manual_failure = manual_format_failure(plan_lines, args[1])
    if manual_failure:
        print(manual_failure)
    verification_failure = verification_format_failure(plan_lines, args[1], pathlib.Path.cwd(), plan["entries"])
    if verification_failure:
        print(verification_failure)
    sys.exit(1 if plan["failures"] or manual_failure or verification_failure else 0)


# ---------- gate derivation ----------

def nearest_directory_with(repo_dir, rel_path, manifest_name):
    manifest = script_utils.nearest_file_upward((repo_dir / rel_path).parent, manifest_name, repo_dir)
    return manifest.parent if manifest else None


def in_directory(command, package_rel):
    return f"cd {shlex.quote(package_rel)} && {command}" if package_rel else command


def script_package_commands(repo_dir, package_dir, paths):
    package_json = json.loads((package_dir / "package.json").read_text())
    scripts = package_json.get("scripts", {})
    dependencies = {**package_json.get("dependencies", {}), **package_json.get("devDependencies", {})}
    package_rel = script_utils.directory_relative_to(repo_dir, package_dir)
    relative_paths = [str((repo_dir / path).relative_to(package_dir)) for path in paths]
    commands = []

    typecheck_name = next((name for name in TYPECHECK_SCRIPTS if name in scripts), None)
    if typecheck_name:
        commands.append(in_directory(f"npm run {typecheck_name}", package_rel))
    elif (package_dir / "tsconfig.json").is_file():
        commands.append(in_directory("npx tsc --noEmit", package_rel))

    source_suffixes = sorted({pathlib.Path(p).suffix for p in relative_paths
                             if p.endswith(SCRIPT_SUFFIXES) and not TEST_FILE.search(p)}
                            | {pathlib.Path(p).suffix for p in relative_paths if p.endswith(SCRIPT_SUFFIXES)})
    if ("eslint" in dependencies or "lint" in scripts) and source_suffixes:
        commands.append(in_directory("npx eslint {files:" + ",".join(source_suffixes) + "}", package_rel))

    test_paths = [p for p in relative_paths if TEST_FILE.search(p)]
    runner = "vitest run" if "vitest" in dependencies else "jest" if "jest" in dependencies else None
    if runner:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npx {runner} {scope}", package_rel))
    elif "test" in scripts:
        scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:" + TEST_SUFFIXES + "}"
        commands.append(in_directory(f"npm test -- {scope}", package_rel))
    return commands


def python_commands(repo_dir, paths):
    python_paths = [p for p in paths if p.endswith(".py")]
    if not python_paths or not any(
        (repo_dir / name).is_file() for name in ("pyproject.toml", "pytest.ini", "setup.cfg")
    ):
        return []
    commands = []
    pyproject = (repo_dir / "pyproject.toml")
    if pyproject.is_file() and "ruff" in pyproject.read_text():
        commands.append("ruff check {files:.py}")
    test_paths = [p for p in python_paths if TEST_FILE.search(p)]
    scope = " ".join(shlex.quote(p) for p in test_paths) or "{files:_test.py}"
    commands.append(f"python3 -m pytest {scope}")
    return commands


def cargo_test_scope(crate_dir, file_in_crate):
    # The cargo test arguments for one Rust file, given the crate directory and the file's path from it, or None when
    # no test belongs to it. `src/bin/<name>.rs` and every file under `src/bin/<name>/` are the binary `<name>`.
    # Any other file under `src/`, `lib.rs` and `main.rs` included, runs the library and binary unit tests
    # (`--lib --bins`) in a crate with a `src/lib.rs`, and the binaries (`--bins`) in a crate with none; `--lib` alone
    # would skip the unit tests in `main.rs` and in the modules only `main.rs` reaches. `tests/<name>.rs` is the test
    # target `<name>`. Any file under `tests/<dir>/` is the test target `<dir>` when `tests/<dir>/main.rs` exists, and
    # otherwise a helper that any integration test can include, so it runs every test target (`--tests`),
    # which already covers the library and every binary, so the crate's other test commands are dropped.
    # A `src/` change does not run the integration tests in `tests/`, because CI runs the full suite.
    # No module filter: a test in an unchanged module can pin the old behavior of the changed one, and the cost is
    # compiling the test binary, which a filter does not save.
    parts = pathlib.PurePosixPath(file_in_crate).with_suffix("").parts
    if len(parts) < 2:
        return None

    if parts[0] == "tests":
        if len(parts) == 2:
            return f"--test {parts[1]}"

        is_target_main_file = parts[2:] == ("main",)
        is_test_target_directory = is_target_main_file or (crate_dir / "tests" / parts[1] / "main.rs").is_file()
        return f"--test {parts[1]}" if is_test_target_directory else "--tests"

    if parts[0] != "src":
        return None

    is_under_bin_directory = parts[1] == "bin" and len(parts) > 2
    if is_under_bin_directory:
        return f"--bin {parts[2]}"

    if (crate_dir / "src" / "lib.rs").is_file():
        return "--lib --bins"
    return "--bins"


def cargo_commands(repo_dir, paths):
    commands_by_crate = {}
    for path in paths:
        is_rust_file = path.endswith(".rs")
        if not (is_rust_file or pathlib.PurePosixPath(path).name == "Cargo.toml"):
            continue

        crate_dir = nearest_directory_with(repo_dir, path, "Cargo.toml")
        if crate_dir is None:
            continue

        crate_commands = commands_by_crate.setdefault(crate_dir, [CARGO_CLIPPY])
        if not is_rust_file:
            continue

        path_in_crate = str((repo_dir / path).relative_to(crate_dir))
        scope = cargo_test_scope(crate_dir, path_in_crate)
        test_command = f"cargo test {scope}" if scope else None
        if test_command and test_command not in crate_commands:
            crate_commands.append(test_command)

    commands = []
    for crate_dir, crate_commands in commands_by_crate.items():
        if "cargo test --tests" in crate_commands:
            crate_commands = [CARGO_CLIPPY, "cargo test --tests"]

        crate_rel = script_utils.directory_relative_to(repo_dir, crate_dir)
        commands += [in_directory(command, crate_rel) for command in crate_commands]
    return commands


def derive_gate_commands(repo_dir, phase_section):
    paths = []
    for match in PATH_IN_BACKTICKS.finditer(phase_section):
        if match.group(1) not in paths:
            paths.append(match.group(1))

    by_package = {}
    for path in paths:
        package_dir = nearest_directory_with(repo_dir, path, "package.json")
        if package_dir is not None:
            by_package.setdefault(package_dir, []).append(path)

    commands = []
    for package_dir, package_paths in by_package.items():
        commands += script_package_commands(repo_dir, package_dir, package_paths)
    root_manifests = BARE_CARGO_MANIFEST.findall(phase_section)
    commands += cargo_commands(repo_dir, paths + root_manifests)
    commands += python_commands(repo_dir, paths)
    return commands


# ---------- start ----------

def file_hashes(repo_dir):
    tracked = git_names(repo_dir, "diff", "--name-only", "HEAD")
    untracked = git_names(repo_dir, "ls-files", "--others", "--exclude-standard")
    hashes = {}
    for name in sorted(set(tracked + untracked)):
        # A deleted file has no content to hash: its hash is None, which still differs from a baseline that had it.
        hashes[name] = git_output(repo_dir, "hash-object", name) if (repo_dir / name).exists() else None
    return hashes


def usage_error(message):
    print(f"code_step.py start: {message}\n{START_USAGE}", file=sys.stderr)
    sys.exit(2)


StartArgs = collections.namedtuple(
    "StartArgs", "modifier plan_args task_text phase_id take_over restart positional_words"
)


def parse_start_args(args):
    # Flags are read left to right up to the first word that is not a plan file, ticket id or directory: that word
    # and everything after it is task text, as is everything after --task. --help prints usage and exits 0 before
    # any state is touched; an unknown flag, and --phase without an id, exits 2. positional_words holds the words of
    # task text that did not follow --task (None otherwise): start_refusal reads them.
    modifiers = []
    plan_args = []
    task_text = None
    positional_words = None
    phase_id = None
    take_over = False
    restart = False
    position = 0
    while position < len(args):
        word = args[position]
        if word == "--take-over":
            take_over = True
        elif word == "--restart":
            restart = True
        elif word == "--task":
            task_text = " ".join(args[position + 1:])
            break
        elif word in ("+fast", "+deep"):
            modifiers.append(word)
        elif word in ("--help", "-h"):
            print(START_USAGE)
            sys.exit(0)
        elif word == "--phase":
            if position + 1 >= len(args) or args[position + 1].startswith("-"):
                usage_error("--phase needs a phase id")
            phase_id = args[position + 1]
            position += 1
        elif word.startswith("-") and len(word) > 1:
            usage_error(f"unknown flag {word}")
        elif looks_like_plan_argument(word):
            plan_args.append(word)
        else:
            positional_words = args[position:]
            task_text = " ".join(positional_words)
            break
        position += 1
    modifier = "+deep" if "+deep" in modifiers else "+fast" if modifiers else None
    return StartArgs(modifier, plan_args, task_text, phase_id, take_over, restart or take_over, positional_words)


def phase_label(state):
    plan_name = state.get("plan") or "a task with no plan"
    return f"Phase {state['phase']} of {plan_name}" if state.get("phase") is not None else plan_name


def phase_flag_position(words):
    # Where an explicit `--phase <phase id>` sits in the words, or None. A `--phase` with no word after it, or with a
    # word that is not a phase id after it, is part of the text.
    for index, word in enumerate(words):
        is_last = index + 1 >= len(words)
        if word == "--phase" and not is_last and re.fullmatch(plan_format.PHASE_ID, words[index + 1]):
            return index

    return None


def first_word_is_verb(words):
    # Whether `start` was given a verb name in place of task text. `start` and `status` are verbs only where a verb
    # would fit: `status` alone, and `start` alone or before a flag or a modifier. More plain words after either make
    # task text, as in `start start caching the list`.
    first_word = words[0]
    if first_word == "status":
        return len(words) == 1
    if first_word == "start":
        return len(words) == 1 or words[1].startswith(("-", "+"))

    return first_word in VERB_WORDS_REPLACED_BY_RESUME + VERB_WORDS_THAT_CARRY_INPUT


def start_refusal(repo_dir, previous, branch, args, parsed):
    # Why `start` does not run, as (reason, commands, notes), or None. Checked before anything is written: a verb
    # name as task text, an unfinished run (--task does not get past it), a plan or --phase inside task text, and
    # task text over a plan with open phases.
    resume_command = script_command(RESUME_VERB)
    words = script_utils.words_of_arguments(parsed.positional_words) if parsed.positional_words else []
    has_task_text = bool(words)
    if has_task_text:
        task_command_text = task_command(parsed.positional_words, parsed.modifier)
        task_hint = (f"For task text, use `{task_command_text}`.",)
        first_word = words[0]
        if not parsed.plan_args and first_word_is_verb(words):
            verb_reason = f"`{first_word}` is a verb, not task text."
            if first_word in VERB_WORDS_REPLACED_BY_RESUME and len(words) > 1:
                return verb_reason, [resume_command, task_command_text], ()

            command = (
                resume_command if first_word in VERB_WORDS_REPLACED_BY_RESUME else script_command(shlex.join(words))
            )
            return verb_reason, [command], task_hint

    if previous.get("stage") not in (None, "done") and not parsed.restart:
        reason = f"a /code run is open here: {phase_label(previous)} at stage {previous['stage']}."
        if not args:
            return reason, [resume_command], ()
        restart_command = script_command(f"start --restart {shlex.join(args)}")
        return reason, [resume_command, restart_command], (
            "`resume` goes on with the open run. `start --restart` drops it and starts over.",)

    if not has_task_text:
        return None

    # Only a plan file as the first word, a plan argument before the text, or an explicit --phase is not task text.
    plan_words = list(parsed.plan_args)
    is_plan_file_first = not plan_words and pathlib.Path(first_word).is_file()
    if is_plan_file_first:
        plan_words = [first_word]
    text_words = words[1:] if is_plan_file_first else list(words)
    phase_id = parsed.phase_id
    phase_flag_at = phase_flag_position(text_words)
    if phase_flag_at is not None:
        phase_id = text_words[phase_flag_at + 1]
        del text_words[phase_flag_at:phase_flag_at + 2]
    if plan_words or parsed.phase_id or phase_flag_at is not None:
        start_words = ["start", *plan_words] + (["--phase", phase_id] if phase_id else []) + (
            [parsed.modifier] if parsed.modifier else [])
        start_command = script_command(shlex.join(start_words))
        commands = [start_command]
        # A word that is no plan file (a directory, a ticket id, a source file) may be the first word of the task, so
        # the task choice keeps it in the text.
        has_word_that_is_no_plan_file = any(
            not (pathlib.Path(plan_word).is_file() and plan_word.endswith(".md")) for plan_word in plan_words)
        task_words = [*plan_words, *text_words] if has_word_that_is_no_plan_file else text_words
        if task_words:
            commands.append(task_command(task_words, parsed.modifier))
        return ("the text after the plan or phase is not task text.", commands,
                ("The text after it was not passed to the coder. Tell the user.",))

    saved_plan = reusable_plan(previous, branch)
    open_phases = open_phase_numbers(repo_dir, saved_plan)
    if open_phases:
        return (f"{saved_plan} has open phases ({', '.join(open_phases)}).", [resume_command, task_command_text], (
            "`resume` goes on with the plan. `start --task` is for separate work.",))
    return None


def open_phase_numbers(repo_dir, plan_rel):
    # The numbers of the plan's phases that are still open, or [] when the plan is unnamed or cannot be read.
    if not plan_rel:
        return []
    try:
        plan_lines = (repo_dir / plan_rel).read_text().splitlines()
    except OSError:
        return []
    return [entry["number"] for entry in ordered_pending(parse_plan(plan_lines)["entries"])]


def state_file_age_seconds(repo_dir):
    try:
        return time.time() - (state_dir(repo_dir) / "state.json").stat().st_mtime
    except OSError:
        return None


def other_session_run_age(repo_dir, previous):
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
    is_stopped_for_fix = stage == "stopped" and previous.get("stopReason") in RESUMABLE_STOP_REASONS
    if stage in WAITING_STAGES or is_stopped_for_fix:
        return state_file_age_seconds(repo_dir)
    return None


def looks_like_plan_argument(word):
    path = pathlib.Path(word)
    # A word with whitespace is task text that happens to name a file, unless it is itself a file (a real plan whose
    # path has a space).
    if script_utils.has_whitespace(word) and not path.is_file():
        return False

    return looks_like_plan_path(word) or TICKET_ID.match(word) is not None or path.is_file() or path.is_dir()


def resolve_plan(repo_dir, argument=None):
    command = ["bash", str(SCRIPTS_DIR / "resolve-task-dir.sh")] + ([argument] if argument else [])
    code, output = run_command(command, repo_dir)
    if code == 0:
        return str(pathlib.PurePath(output) / "spec.md"), "eng-spec"
    if code == 5:
        return output, "eng-spec"
    if code == 3:
        ask_user(repo_dir, "several tasks match. Ask the user which one to implement. Then invoke Skill code with "
                 "the chosen plan path.", output)
    else:
        ask_user(repo_dir, "no task or plan resolves. Ask the user what to implement. Then invoke Skill code with a "
                 "plan path or the task text.")
    return None, None


def looks_like_plan_path(argument):
    return "/" in argument or argument.endswith(".md")


def reusable_plan(previous, branch):
    # The saved plan serves a bare `start` only on the branch it was saved on, and not after a plan with no phases
    # finished.
    if not previous.get("plan") or previous.get("branch") != branch:
        return None
    if previous.get("stage") == "done" and previous.get("phase") is None:
        return None
    return previous["plan"]


def is_finished_single_phase_plan(repo_dir, previous, branch, resolved_plan):
    # A plan with no phases that finished on this branch is not run again when a bare `start` resolves to the same file.
    if previous.get("stage") != "done" or previous.get("phase") is not None or previous.get("branch") != branch:
        return False
    if not previous.get("plan"):
        return False
    try:
        resolved_rel = str(pathlib.Path(resolved_plan).resolve().relative_to(repo_dir))
    except ValueError:
        return False
    return resolved_rel == previous["plan"]


def stop_while_plan_edit_coder_is_out(repo_dir, state, verb_text):
    # A restore or a drop of the saved criteria while the plan-edit coder is still out would leave its later write
    # unchecked. Returns True after printing the stop, with no state changed.
    if state.get("stage") != "plan-coder" or not is_dispatch_open(repo_dir, state):
        return False
    emit("stop", "The plan-edit coder has not reported yet, so the saved acceptance criteria stay as they are. Run "
         f"`! {INSTALLED_COMMAND} {RESUME_VERB}` from the repo root first: it waits for the "
         f"report and restores the criteria. Then run `{verb_text}` again. Tell the user.")
    return True


def without_blank_task_text(args):
    # Blank task text is no task text: `start "  "` and `start --task "  "` act as a bare `start`.
    non_blank_args = [word for word in args if word.strip()]
    if parse_start_args(non_blank_args).task_text == "":
        return non_blank_args[:-1]

    return non_blank_args


def command_start(args):
    args = without_blank_task_text(args)
    parsed = parse_start_args(args)
    modifier, plan_args, task_text, phase_id, take_over = (parsed.modifier, parsed.plan_args, parsed.task_text,
                                                       parsed.phase_id, parsed.take_over)
    repo_dir = repo_root()
    os.chdir(repo_dir)
    previous = load_state(repo_dir) or {}
    branch = current_branch(repo_dir)
    age_seconds = other_session_run_age(repo_dir, previous)
    if not take_over and age_seconds is not None and age_seconds < OTHER_SESSION_LIVE_SECONDS:
        phase_name = f"Phase {previous['phase']} of " if previous.get("phase") is not None else ""
        last_active = datetime.datetime.fromtimestamp(time.time() - age_seconds).strftime("%H:%M")
        lifts_at = datetime.datetime.fromtimestamp(time.time() - age_seconds + OTHER_SESSION_LIVE_SECONDS)
        take_over_args = " ".join(["--take-over", *args])
        return emit("stop", f"Another Claude session has a /code run open in this checkout: {phase_name}"
                    f"{previous.get('plan') or 'a task with no plan'}. Starting here would cancel it. Tell the user to "
                    "run this work in a git worktree. "
                    f"Last active {last_active}, {int(age_seconds // 60)} min ago in another session; this block lifts "
                    f"at {lifts_at.strftime('%H:%M')}. If the user says that session has ended, invoke Skill code with "
                    f"`{take_over_args}`.")

    refusal = start_refusal(repo_dir, previous, branch, args, parsed)
    if refusal:
        reason, commands, notes = refusal
        return refuse(reason, *commands, notes=notes)

    start_command = script_command(shlex.join(["start", *args]))
    if stop_while_plan_edit_coder_is_out(repo_dir, previous, start_command):
        return

    # The owner check above runs first: a restore never touches a state that another live session owns.
    # The state is saved only when a saved copy was restored or dropped, and then under this session.
    criteria_message = None
    if previous.get("criteriaGuard") is not None:
        criteria_message = settle_criteria_guard(repo_dir, previous, branch)
        previous["sessionId"] = session_pin()
        save_state(repo_dir, previous)

    is_auto_advance_text_pending = previous.get("stage") == "done" and previous.get("autoAdvance")
    is_old_text_stale = previous.get("stage") is not None and not is_auto_advance_text_pending
    if is_old_text_stale or task_text is not None:
        clear_say(repo_dir)

    if criteria_message:
        say(repo_dir, criteria_message)

    if is_auto_advance_text_pending and uncommitted_files(repo_dir, previous):
        return emit("stop", "The previous phase's files are not committed yet, so the next phase would take them as "
                    f"its own. Run the commit line, then run `{INSTALLED_COMMAND} {RESUME_VERB}`:",
                    previous.get("commitLine", ""))
    abandon_open_dispatch(repo_dir, previous)

    if task_text is not None:
        return start_planless(repo_dir, modifier, task_text, branch)

    plan_arg = plan_args[0] if plan_args else None
    lane = previous.get("lane", "code")
    is_unknown_arg = plan_arg is not None and not pathlib.Path(plan_arg).is_file()
    if is_unknown_arg and (TICKET_ID.match(plan_arg) or pathlib.Path(plan_arg).is_dir()):
        plan_arg, lane = resolve_plan(repo_dir, plan_arg)
        if plan_arg is None:
            return
        print(f"Resolved the task input: {plan_arg} (lane {lane}).")
    elif plan_arg is None and reusable_plan(previous, branch):
        plan_arg = previous["plan"]
    elif plan_arg is None:
        plan_arg, lane = resolve_plan(repo_dir)
        if plan_arg is None:
            return
        if is_finished_single_phase_plan(repo_dir, previous, branch, plan_arg):
            return emit("stop", f"The plan {previous['plan']} is complete. Tell the user the plan is complete. "
                        + FOLLOW_UP_HINT)
        print(f"Resolved the task input: {plan_arg} (lane {lane}).")
    elif previous.get("plan") != plan_arg:
        lane = "code"

    plan_path = pathlib.Path(plan_arg)
    if not plan_path.is_file():
        return ask_user(repo_dir, f"no plan file is at {plan_arg}. Ask the user for the path. Then invoke Skill code "
                        "with that path.")
    try:
        plan_rel = str(plan_path.resolve().relative_to(repo_dir))
    except ValueError:
        return ask_user(repo_dir, f"the plan {plan_arg} is outside the repo {repo_dir}. Ask the user for a plan inside "
                        "the repo. Then invoke Skill code with that path.")
    plan_lines = plan_path.read_text().splitlines()

    plan = parse_plan(plan_lines)
    if plan["failures"]:
        return emit("stop", plan_failure_message(plan, plan_rel))
    start_line = RESUME_LINE.format(noun="section", verb=shlex.join(["start", *args]))
    manual_failure = manual_format_failure(plan_lines, plan_rel, start_line)
    if manual_failure:
        return emit("stop", manual_failure)
    verification_failure = verification_format_failure(plan_lines, plan_rel, repo_dir, plan["entries"])
    if verification_failure:
        return emit("stop", verification_failure + " " + start_line)

    entries = plan["entries"]
    has_phases = bool(plan["sections"])
    if not entries and has_phases:
        return emit("judgment", "The plan has phases but no '## Phase Status' section. Use `git status` and each "
                    "phase's success criteria to pick the next phase, tell the user to backfill the section, then "
                    f"run `{start_command}` again after adding it.")
    pending = ordered_pending(entries)
    if phase_id is not None:
        entry = next((e for e in entries if e["number"] == phase_id), None)
        if entry is None:
            listed = ", ".join(e["number"] for e in entries) or "none"
            return emit("stop", f"Phase {phase_id} is not in the Phase Status of {plan_rel}. Listed phases: {listed}. "
                        "Tell the user.")
        if entry["moved"]:
            return emit("stop", moved_phase_stop(entry, plan_rel))
        if entry["done"]:
            return emit("stop", f"Phase {phase_id} is already marked done in {plan_rel}. No coder was dispatched. Tell "
                        "the user; to run it again, they uncheck it in Phase Status first.")
    elif entries and not pending:
        moved_text = moved_phase_text(entries)
        checked_text = f"checked or moved to another ticket ({moved_text})" if moved_text else "checked"
        return emit("stop", f"Every phase in the plan is {checked_text}. Tell the user the plan is complete. "
                    + FOLLOW_UP_HINT)
    else:
        gated_ahead, entry = gate_blockers(pending)
        if gated_ahead:
            return emit("stop", "No phase was started, and no coder was dispatched: "
                        + gate_block_text(gated_ahead, entry) + " Tell the user.")

    number = entry["number"] if entry else None
    section = phase_text(plan_lines, number) if entry else "\n".join(plan_lines)

    if entry:
        closing_skill_name = next((skill for pattern, skill in CLOSING_PHASES if pattern.search(entry["title"])), None)
        if closing_skill_name:
            return start_closing_phase(repo_dir, plan_rel, lane, modifier, entry, closing_skill_name, section, branch,
                                       phase_id)

    if not check_acceptance_criteria(repo_dir, plan_lines, plan_rel):
        return

    commands = derive_gate_commands(repo_dir, section) if entry else []
    gate_note = set_gate_and_packet_note(repo_dir, plan_rel, commands)
    packet_body = packet_text(repo_dir, plan_rel, number, has_phases and entry)

    reports_file = state_dir(repo_dir) / "reports.jsonl"
    reports_file.unlink(missing_ok=True)
    run_id = start_run(repo_dir)

    state_phase = number if has_phases and entry else None
    is_same_unfinished_phase = (previous.get("plan") == plan_rel and previous.get("phase") == state_phase
                             and previous.get("stage") not in (None, "done") and previous.get("baseline") is not None)
    baseline = previous["baseline"] if is_same_unfinished_phase else file_hashes(repo_dir)
    base_head = (
        previous.get("baseHead") if is_same_unfinished_phase and previous.get("baseHead") else head_commit(repo_dir)
    )

    phase_description = f"Phase {number} of `{plan_rel}`" if entry and has_phases else f"`{plan_rel}`"
    prompt = (f"Implement {phase_description}. Read the plan phase-scoped.\n"
              "If the task turns out architectural, report back and recommend /eng-spec.\n\n" + packet_body).rstrip()
    state = {"stage": "coder", "plan": plan_rel, "lane": lane, "phase": state_phase, "branch": branch,
             "modifier": modifier, "risk": entry["risk"] if entry else "high", "title": entry["title"] if entry else "",
             "gateCommands": commands, "baseline": baseline, "baseHead": base_head, "startedAt": time.time(),
             "phaseText": section if entry and has_phases else None, "onlyPhase": phase_id,
             "sessionId": session_pin(), "runId": run_id}
    open_dispatch(state)
    save_state(repo_dir, state)
    model = "haiku" if modifier == "+fast" else None
    emit_dispatch(repo_dir, state, RESUME_VERB, gate_note, prompt=prompt, agent="coder", model=model)


def start_planless(repo_dir, modifier, task_text, branch="-"):
    directory = state_dir(repo_dir)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "reports.jsonl").unlink(missing_ok=True)
    state = {"stage": "coder", "plan": None, "lane": "code", "phase": None, "branch": branch, "modifier": modifier,
             "risk": "high", "title": "", "gateCommands": [], "baseline": file_hashes(repo_dir),
             "startedAt": time.time(), "sessionId": session_pin(), "runId": start_run(repo_dir)}
    open_dispatch(state)
    save_state(repo_dir, state)
    prompt = (f"Implement: {task_text}\nRun the typecheck, and lint and tests for only the files you changed, once, "
              "after all edits. If the task turns out architectural, report back and recommend /eng-spec.")
    model = "haiku" if modifier == "+fast" else None
    emit_dispatch(repo_dir, state, RESUME_VERB, prompt=prompt, agent="coder", model=model)


def start_closing_phase(repo_dir, plan_rel, lane, modifier, entry, skill, section, branch, only_phase=None):
    state = {"stage": "skill", "plan": plan_rel, "lane": lane, "phase": entry["number"], "branch": branch,
             "modifier": modifier, "risk": entry["risk"], "title": entry["title"], "gateCommands": [], "behavior": [],
             "baseline": file_hashes(repo_dir), "onlyPhase": only_phase, "sessionId": session_pin()}
    save_state(repo_dir, state)
    verdict_step = ("run `python3 ~/.claude/scripts/code_step.py skill-done pass` when the phase's Success Criteria "
                   "hold, or `skill-done fail` when they do not (for the Verify pass, any MISSING criterion fails it)")
    section_lines = (
        ["The phase's own plan section follows. Follow its steps and gates; the skill alone is not the phase:", section]
        if section
        else []
    )
    emit(
        "invoke-skill",
        f"Phase {entry['number']} ({entry['title']}) is a closing phase. Invoke the Skill tool with "
        f"`{skill}`; a coder is not dispatched.",
        *section_lines,
        f"The skill needs judgment. When it returns, {verdict_step}.",
    )


def check_acceptance_criteria(repo_dir, plan_lines, plan_rel):
    has_criteria_section = any(line.strip() == "## Acceptance Criteria" for line in plan_lines)
    if not has_criteria_section:
        return True
    criteria_path = criteria_rel(plan_rel)
    criteria = repo_dir / criteria_path
    if criteria.is_file() and criteria.read_text().strip():
        return True

    note = f"{criteria_path} is missing or empty"
    run_command(["bash", str(SCRIPTS_DIR / "log-scan"), f"repo={repo_dir.name}", "scan=acceptance-stub",
                 "stage=code-phase", "exit=0", "candidates=1", "confirmed=1", f"note={note}"], repo_dir)
    emit("stop", f"Plan defect: {note}, and the plan has an Acceptance Criteria section.",
         "Do not dispatch. Do not write the criteria. Report the defect to the user and wait.")
    return False


def set_gate_and_packet_note(repo_dir, plan_rel, commands):
    if not commands:
        return "GATE: none derived; the coder runs its own checks (the packet says so)."

    # The gate runs the commands later, at each hand-back, so the repo's gate env goes into the stored gate.
    gate_env = plan_format.repo_gate_env(repo_dir, plan_rel)
    env_arguments = [argument for assignment in gate_env for argument in ("--env", assignment)]
    code, output = run_command(["python3", str(SCRIPTS_DIR / "coder_gate.py"), "set", *env_arguments, *commands],
                               repo_dir)
    if code != 0:
        return f"GATE: not set ({output.splitlines()[0] if output else 'refused'}); the coder runs its own checks."

    env_note = f" With: {' '.join(gate_env)}." if gate_env else ""
    return f"GATE: {output}. Commands: " + " | ".join(commands) + env_note


def packet_text(repo_dir, plan_rel, number, use_packet):
    if not use_packet:
        return ""
    code, output = run_command(["python3", str(SCRIPTS_DIR / "coder_packet.py"), plan_rel, str(number)], repo_dir)
    if code != 0:
        sys.exit(f"code-step: coder-packet failed: {output}")
    return output


# ---------- coder hand-back ----------

def coder_flags(report):
    flagged = []
    for line in report.splitlines():
        mentions_open_point = re.search(r"\bambigu(ous|ity|ities)\b|open question", line, re.I)
        denies_open_point = re.search(r"\b(no|none)\b", line, re.I)
        if mentions_open_point and not denies_open_point:
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


ALREADY_DONE_LINE = re.compile(
    r"^[ \t>*`_-]*ALREADY-DONE[*`_]*:[ \t]*(?:ask[ \t]*)?(\d+)[ \t]*(?:—|–|--?)[ \t]*(.*)$", re.M
)


def already_done_ask_numbers(repo_dir, report):
    # The numbers of the asks the coder says need no edit. Each one counts only when its ALREADY-DONE line holds nothing
    # but a file:line (a closing period, comma or semicolon aside) and that file exists in the repo.
    numbers = set()
    for match in ALREADY_DONE_LINE.finditer(report):
        location = script_utils.PATH_LINE.fullmatch(match.group(2).strip().rstrip(".,;"))
        if location and (repo_dir / script_utils.normalize_path(location.group(1))).is_file():
            numbers.add(int(match.group(1)))
    return numbers


def every_accepted_ask_already_done(repo_dir, state, report):
    accepted_ask_numbers = set(range(1, len(state["acceptedAsks"]) + 1))
    return accepted_ask_numbers <= already_done_ask_numbers(repo_dir, report)


def why_by_file(report):
    grouped = {}
    for match in re.finditer(r"^WHY:\s*`?(\S+?)`?(?::|\s+)(\d+-\d+)\s*[—-]+\s*(.+)$", report, re.M):
        grouped.setdefault(match.group(1), []).append({"lines": match.group(2), "note": match.group(3).strip()})
    return grouped


def behavior_lines(report):
    found = [m.group(1).strip() for m in re.finditer(r"^BEHAVIOR:\s*(.+)$", report, re.M)]
    return [line for line in found if line.lower() != "none"]


def path_suffixes(path, min_parts=2):
    parts = path.split("/")
    return ["/".join(parts[start:]) for start in range(len(parts)) if len(parts) - start >= min(min_parts, len(parts))]


def mentions_path(line, path, files=()):
    # True when the line names the path, or a trailing part of it (reports often drop the leading backend/src/).
    # A bare file name counts only when no other changed file shares it.
    base_name = path.rsplit("/", 1)[-1]
    shares_base_name = any(name != path and name.rsplit("/", 1)[-1] == base_name for name in files)
    suffixes = path_suffixes(path) + ([] if shares_base_name else [base_name])
    return any(re.search(rf"(?<![\w./-]){re.escape(suffix)}(?![\w/])", line) for suffix in suffixes)


def resolve_report_paths(grouped, files):
    # Re-key a report's per-path dict to the changed files' full paths, matching on trailing path parts.
    resolved = {}
    for report_path, value in grouped.items():
        candidates = [name for name in files if name == report_path or name.endswith("/" + report_path)
                      or report_path.endswith("/" + name)]
        target = candidates[0] if len(candidates) == 1 else report_path
        resolved.setdefault(target, []).extend(value)
    return resolved


def change_line(report, path, files, fallback_behavior, is_new_file=False):
    # A report names a file's change on a bullet that starts with the path (or a trailing part of it).
    # Prose lines that only mention the path, and grouped "Created: a, b" lines, do not count.
    base_name = path.rsplit("/", 1)[-1]
    shares_base_name = any(name != path and name.rsplit("/", 1)[-1] == base_name for name in files)
    suffixes = sorted(path_suffixes(path) + ([] if shares_base_name else [base_name]), key=len, reverse=True)
    for line in report.splitlines():
        if not re.match(r"^\s*[-*]\s", line):
            continue
        body = line.strip().lstrip("-* ").lstrip("`")
        for suffix in suffixes:
            match = re.match(rf"{re.escape(suffix)}`?\s*(?:[:—-]+\s*|\s+)(.+)$", body)
            if match:
                return re.sub(r"\s+", " ", match.group(1).strip())[:160]
    if is_new_file:
        return "new file"
    return fallback_behavior or "changed by the coder"


def gate_results(repo_dir):
    gate_file = git_output(repo_dir, "rev-parse", "--path-format=absolute", "--git-path", "coder-gate.json")
    if gate_file is None or not pathlib.Path(gate_file).exists():
        return None
    return json.loads(pathlib.Path(gate_file).read_text())


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


def asks_coder_changed_files(changed_now, asks_baseline):
    # The files whose hash differs between the snapshot taken at the asks-coder dispatch and now, new and deleted
    # included.
    names = set(changed_now) | set(asks_baseline)
    return sorted(name for name in names if changed_now.get(name) != asks_baseline.get(name))


def finish_without_review(repo_dir, state, changed_files, coder_stage, say_text):
    # No review has anything to cover: run the phase's verification commands and tick, as after a clean review.
    state.update({"files": changed_files, "coderStage": coder_stage, "stage": "review"})
    save_state(repo_dir, state)
    say(repo_dir, say_text)
    return finish_phase(repo_dir, state)


def command_after_coder(repo_dir, state, args):
    if not wait_for_handback(repo_dir, state, RESUME_VERB, long_checks_follow=state["stage"] == "asks-coder"):
        return
    state = load_state(repo_dir)
    if awaits_resumed_coder(state):
        # A resumed coder's hook puts the stage back when it hands back. A row of that coder while the stage still reads
        # stopped means a stale save overwrote the hook's flip: flip here, the way the review step does. With no row, no
        # report came.
        if resumed_coder_row(repo_dir, state) is None:
            return emit("stop", resumed_agent_pending_stop(CODER))
        put_resumed_coder_back(repo_dir, state)
    if state["stage"] not in CODER_STAGES:
        return refuse("no coder dispatch is pending any more.", script_command(RESUME_VERB))

    coder_stage = state["stage"]
    is_ask_fix = coder_stage == "asks-coder"
    addendum = None if is_ask_fix else added_phase_lines(repo_dir, state)
    if addendum:
        state["phaseText"] = addendum["text"]
        first_report = with_earlier_report(state, latest_coder_message(repo_dir, coder_stage, state.get("dispatchAt")))
        if first_report is not None:
            state["earlierCoderReport"] = first_report
        open_dispatch(state)
        save_state(repo_dir, state)
        prompt = (f"Phase {state['phase']} of `{state['plan']}` gained lines after the first coder was dispatched. "
                  "Implement only these added or changed lines. Do not redo the rest of the phase:\n\n"
                  + "\n".join(addendum["added"]))
        return emit_dispatch(repo_dir, state, RESUME_VERB, "The plan phase changed while the coder ran. Dispatch a "
                             "coder for the added lines before the review.", prompt=prompt, agent="coder")
    gate = None if is_ask_fix else gate_results(repo_dir)
    # Read before `clear` deletes the gate: with no gate every row counts, so a draft or a still-running coder's row
    # would read as a report.
    dispatched_rows = coder_rows(repo_dir, coder_stage, state.get("dispatchAt"))
    gate_lines = state.get("gateLines", "")
    if not is_ask_fix:
        _code, gate_lines = run_command(["python3", str(SCRIPTS_DIR / "coder_gate.py"), "clear"], repo_dir)
    # The rows read before `clear` name the report when the gate let one through; after the clear the rows of a coder
    # with no gate result count again, so that read is the fallback.
    latest_row = (
        dispatched_rows[-1] if dispatched_rows else latest_coder_row(repo_dir, coder_stage, state.get("dispatchAt"))
    )
    if latest_row is None:
        return emit("stop", "No coder report was saved. The SubagentHandback hook (code_step.py hook) is not "
                    "installed or the coder never handed back. Tell the user.")
    report = latest_row.get("message", "")
    if not is_ask_fix:
        report = with_earlier_report(state, report)

    capped = [coder for coder in (gate or {"coders": {}})["coders"].values() if coder["result"] == "cap"]
    flagged = list(state.get("flagged", [])) if is_ask_fix else []
    for coder in capped:
        flagged.append("hand-back gate cap: " + ", ".join(coder["failed"]) + " still failing after 3 denials")
    flagged += coder_flags(report)

    changed_now = file_hashes(repo_dir)
    baseline = state["baseline"]
    changed_files = [name for name, digest in changed_now.items() if name not in baseline or baseline[name] != digest]
    changed_files += [name for name in committed_since(repo_dir, state.get("baseHead")) if name not in changed_files]
    asks_coder_changed_nothing = is_ask_fix and changed_now == state.get("asksBaseline")
    recommends_eng_spec = "/eng-spec" in report
    report_raises_blocker = recommends_eng_spec or bool(first_plan_impact([report])) or bool(coder_flags(report))
    every_ask_already_done = asks_coder_changed_nothing and every_accepted_ask_already_done(repo_dir, state, report)
    if asks_coder_changed_nothing and every_ask_already_done and not report_raises_blocker:
        # The user confirmed the asks and the coder named, for each one, the file:line that already does it: the review
        # has converged. Any other report with no change (a failed edit, a blocked hook, a question) stops below.
        return finish_without_review(repo_dir, state, changed_files, coder_stage,
                                     "The asks coder changed nothing, and named where each confirmed ask is already in "
                                     "the code. No review runs. The coder reported:\n" + report)
    if not changed_files or asks_coder_changed_nothing or recommends_eng_spec:
        state["stage"] = "stopped"
        state.pop("stopReason", None)
        state["resumableCoderAt"] = time.time()
        state["resumableCoderId"] = latest_row.get("agent_id") or "unknown"
        if not is_ask_fix:
            # The resumed coder's report is the only row after the stop, so this one keeps its PLAN-IMPACT. A report of
            # an earlier stop is kept too: a second stop must not drop the first one's PLAN-IMPACT.
            state["stoppedCoderReport"] = "\n\n".join(filter(None, [state.get("stoppedCoderReport"), report]))
        state.pop("dispatchAt", None)
        save_state(repo_dir, state)
        tick_text = (f" If the user says Phase {state['phase']} is already done, invoke Skill code with `tick "
                    f"{state['phase']}`; do that only on the user's word." if state.get("plan") and state.get("phase")
                    else "")
        resume_text = (" If the user answers the coder's blocker, resume that coder with SendMessage, then run "
                      f"{timed_command(RESUME_VERB)}.")
        return emit("stop", "The coder produced no reviewable change, or recommended /eng-spec. Do not dispatch a "
                    "review. Do not mark the phase done." + tick_text + resume_text
                    + " Relay the coder's report to the user:", report)

    asks_baseline = state.get("asksBaseline")
    if is_ask_fix and asks_baseline is not None:
        # The review after an asks-coder covers only what the asks-coder changed. A state from before asksBaseline
        # existed keeps the whole-phase scope.
        changed_files = asks_coder_changed_files(changed_now, asks_baseline)
        if all(name.lower().endswith(DOCS_SUFFIXES) for name in changed_files):
            return finish_without_review(repo_dir, state, changed_files, coder_stage,
                                         "The asks coder changed only docs files. No review runs on them.")

    behavior = behavior_lines(report)
    why_groups = resolve_report_paths(why_by_file(report), changed_files)
    tests_run = tests_run_text(gate, state)
    if is_ask_fix:
        behavior = list(state.get("behavior", [])) + behavior
        for path, notes in state["why"].items():
            if path in changed_files:
                why_groups[path] = notes + why_groups.get(path, [])
        tests_run = state["testsRun"] + "; ask-fix coder -> ran its own checks"
        state.update({"iter": 0, "spec_iter": 0, "priorIssues": prior_issues(state["acceptedAsks"])})
    state.update({"gateLines": gate_lines, "flagged": flagged, "behavior": behavior, "exception": bool(flagged),
                  "files": changed_files, "why": why_groups, "testsRun": tests_run, "coderStage": coder_stage})

    dispatched_reports = [row.get("message", "") for row in dispatched_rows]
    stopped_report = state.pop("stoppedCoderReport", None)
    earlier_reports = [] if is_ask_fix else list(filter(None, [state.get("earlierCoderReport"), stopped_report]))
    impact = first_plan_impact(earlier_reports + dispatched_reports)
    if impact:
        state.update({"stage": "impact-coder", "impact": impact})
        save_state(repo_dir, state)
        return emit_plan_impact_modal(impact, repo_dir)

    state["planImpact"] = "none"
    save_state(repo_dir, state)
    emit_review_dispatch(repo_dir, state)


def prior_issues(accepted_asks):
    issues = []
    for item, _outcome, change_text in accepted_asks:
        file_line = item.get("file_line", "")
        issue_text = ask_text(item)
        if change_text:
            issue_text += f" (user's change: {change_text})"
        issues.append({"issue": issue_text, "file": file_line.partition(":")[0]})
    return issues


def preset_decision(repo_dir):
    # A pre-answered decision for runs with no AskUserQuestion (claude -p, bench): env var or a file in the state dir.
    word = os.environ.get("CODE_STEP_IMPACT_DECISION", "").strip().lower()
    preset_file = state_dir(repo_dir) / "impact-decision"
    if not word and preset_file.exists():
        word = preset_file.read_text().strip().lower()
    return word if word in ("adopt", "keep") else None


def decide_call(word):
    return f"`decide {word} --by user --ruling \"<the decision in one line>\"`"


DECIDE_BY_NOTE = ("If the user told you to make the call yourself, or you rule without asking, pass `--by session` in "
                  "place of `--by user`. A session ruling never changes the acceptance criteria.")


def emit_plan_impact_modal(impact, repo_dir):
    word = preset_decision(repo_dir)
    if word:
        print(f"PLAN-IMPACT answered by the pre-set decision '{word}'. No question to the user.")
        state = load_state(repo_dir)
        return command_decide(repo_dir, state, [word, "--by", "session", "--ruling",
                                                f"pre-set decision '{word}'; no user was asked"],
                              ruling_by="the pre-set decision")
    ask_user(repo_dir, "the code and the plan disagree. Ask the user this question in plain text and wait for the "
             "answer. Then invoke Skill code with the args after the option the user chose, with the ruling in one "
             "line, in your own words, as the --ruling text. Do not quote the user.",
             impact, "",
             f"1. {PLAN_IMPACT_OPTIONS[0]} (a coder rewrites the plan steps to match the ruling): "
             f"{decide_call('adopt')}",
             f"2. {PLAN_IMPACT_OPTIONS[1]}: {decide_call('keep')}",
             f"3. {PLAN_IMPACT_OPTIONS[2]}: talk it through here, then invoke Skill code with "
             f"{decide_call('adopt')} or {decide_call('keep')}",
             DECIDE_BY_NOTE)


def record_deviation(repo_dir, state):
    ruling = state["ruling"]
    ruling_line = " ".join(ruling["words"].split())
    entry = [f"- {time.strftime('%Y-%m-%d')} (Phase {state['phase']}): {ruling['decision']}. "
             f"Ruled by {ruling['by']} at {ruling['at']}.", "",
             f"  The ruling: {ruling_line}"]
    entry += ["", "  The disagreement:"]
    entry += ["  " + line for line in state["impact"].splitlines()]
    append_deviation(repo_dir / state["plan"], entry)


def append_deviation(plan_path, entry):
    # Add the entry lines at the end of the plan's `## Plan Deviations` section, creating it before `## References`.
    lines = plan_path.read_text().split("\n")
    sections = [i for i, line in enumerate(lines) if line.startswith("## ")]
    existing = next((i for i in sections if lines[i].strip() == "## Plan Deviations"), None)
    if existing is not None:
        end = next((i for i in sections if i > existing), len(lines))
        lines[end:end] = [*entry, ""]
    else:
        references = next((i for i in sections if lines[i].strip() == "## References"), len(lines))
        lines[references:references] = ["## Plan Deviations", "", *entry, ""]
    plan_path.write_text("\n".join(lines))


def split_decide_args(args):
    # The decision word, who ruled (`--by user|session`, None when missing), then the words after `--ruling`,
    # joined when the caller left them unquoted.
    word = args[0].lower() if args else ""
    ruling_at = args.index("--ruling") if "--ruling" in args else len(args)
    by_words = args[:ruling_at]
    by = by_words[by_words.index("--by") + 1] if "--by" in by_words[:-1] else None
    ruling_words = " ".join(args[ruling_at + 1:])
    return word, by, ruling_words.strip()


def resolved_plan_impact(state):
    # review-loop reads a block that starts RESOLVED as settled, so it reviews against the ruling instead of
    # returning the question again.
    ruling = state["ruling"]
    if ruling["byUser"]:
        resolved = "the user ruled on this disagreement"
    elif ruling["by"] == "the pre-set decision":
        resolved = "the pre-set decision ruled on this disagreement, not the user"
    else:
        resolved = "the session ruled on this disagreement, not the user"
    lines = [f"RESOLVED: {resolved}. Review the code against the ruling. It is not an open question.",
             f"Decision: {ruling['decision']}",
             f"Ruled by: {ruling['by']}, at {ruling['at']}",
             "The ruling:"]
    lines += ["  " + line for line in ruling["words"].splitlines()]
    lines.append("The disagreement it settles:")
    lines += ["  " + line for line in state["impact"].splitlines()]
    return "\n".join(lines)


DECIDE_USAGE = 'decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"'


def command_decide(repo_dir, state, args, ruling_by=None):
    word, by, ruling_words = split_decide_args(args)
    if not word:
        return emit("stop", STAGE_GUARDS["decide"]["message"])
    decision = DECISION_WORDS.get(word)
    if decision is None:
        return emit("stop", "decide takes adopt, keep or discuss.")
    if decision == "Discuss":
        return ask_user(repo_dir, "discuss this disagreement between the code and the plan with the user in plain "
                        f"words. When the user chooses, invoke Skill code with {decide_call('adopt')} or "
                        f"{decide_call('keep')}. {DECIDE_BY_NOTE}", state["impact"])
    if by not in ("user", "session"):
        return emit("stop", f"decide {word} needs --by user or --by session. Usage: `{DECIDE_USAGE}`. {DECIDE_BY_NOTE}")
    if not ruling_words:
        return emit("stop", f"decide {word} needs the ruling's words: {decide_call(word)}. {DECIDE_BY_NOTE} "
                    "Hand back and ask the main session for them.")

    if state.get("plan") and not (repo_dir / state["plan"]).is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")
    ruling_at = time.strftime("%Y-%m-%d %H:%M")
    by_user = by == "user" and not ruling_by
    if ruling_by:
        ruling_name = ruling_by
    elif by_user:
        ruling_name = git_user_name(repo_dir)
    else:
        ruling_name = "the session, not the user"
    state["ruling"] = {"decision": decision, "words": ruling_words, "by": ruling_name, "byUser": by_user,
                       "at": ruling_at}
    if not by_user and state.get("plan") and criteria_file(repo_dir, state):
        print("The acceptance criteria stay as written: verify-branch reports any criterion the code now fails as "
              "failing.")
    if state.get("plan"):
        record_deviation(repo_dir, state)
    state["planImpact"] = resolved_plan_impact(state)
    # A ruling opens a new review: the round cap of the review that raised the question does not carry over.
    state["iter"] = 0

    if decision == PLAN_IMPACT_OPTIONS[0] and state.get("plan"):
        return emit_plan_edit_dispatch(repo_dir, state)
    emit_review_dispatch(repo_dir, state)


def git_user_name(repo_dir):
    return git_output(repo_dir, "config", "user.name") or "the user"


def criteria_rel(plan_rel):
    # The plan's acceptance criteria live beside it.
    return str(pathlib.PurePath(plan_rel).parent / "acceptance-criteria.md")


def criteria_file(repo_dir, state):
    # None when the plan has no criteria file.
    criteria_path = criteria_rel(state["plan"])
    if not (repo_dir / criteria_path).is_file():
        return None
    return criteria_path


def save_criteria_guard(repo_dir, state):
    # Before a plan edit that the user did not rule: remember the criteria file's path and text, or None for "no
    # file", so that restore_criteria can put it back.
    relative_criteria_path = criteria_rel(state["plan"])
    criteria_path = repo_dir / relative_criteria_path
    criteria_text = criteria_path.read_text() if criteria_path.is_file() else None
    state["criteriaGuard"] = {"path": relative_criteria_path, "text": criteria_text}


def save_replaced_criteria(repo_dir, criteria_name, text):
    # Keep the text a restore replaces in the git dir, outside the worktree, one new file per restore.
    found = git_output(repo_dir, "rev-parse", "--path-format=absolute", "--git-path", "code-step-replaced-criteria")
    folder = pathlib.Path(found)
    folder.mkdir(parents=True, exist_ok=True)

    stamp = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")
    counter = 1
    while True:
        target = folder / f"{stamp}-{counter:02d}-{criteria_name}"
        try:
            with open(target, "x") as handle:
                handle.write(text)
            return target
        except FileExistsError:
            counter += 1


def settle_criteria_guard(repo_dir, state, branch):
    # Resolve the saved criteria copy of a plan edit that the user did not rule. Returns the message for the user,
    # or None when there was nothing to do. The caller saves the state: the guard is popped here.
    if state.get("criteriaGuard") is None:
        return None
    if state.get("branch") != branch:
        state.pop("criteriaGuard")
        return ("The saved acceptance criteria belong to a plan edit on another branch, so the script dropped them "
                "and restored nothing.")
    return restore_criteria(repo_dir, state)


def restore_criteria(repo_dir, state):
    # Put the folder back as it was at the save. The text of a file that differs, or that did not exist at the save,
    # goes to a copy under the git dir first. Returns the message for the user, or None when nothing changed.
    guard = state.pop("criteriaGuard")
    criteria_path = repo_dir / guard["path"]
    if not criteria_path.parent.is_dir():
        return (f"The saved acceptance criteria belong to {guard['path']}, whose folder is gone, so the script "
                "dropped them and restored nothing.")

    if guard["text"] is None:
        if not criteria_path.is_file():
            return None
        kept = save_replaced_criteria(repo_dir, criteria_path.name, criteria_path.read_text())
        criteria_path.unlink()
        return (f"No acceptance criteria file existed before a ruling the user did not make, and {guard['path']} "
                f"appeared after it, so the script deleted it. The text it deleted is in {kept}.")

    changed_note = ""
    if criteria_path.is_file():
        current_text = criteria_path.read_text()
        if current_text == guard["text"]:
            return None
        kept = save_replaced_criteria(repo_dir, criteria_path.name, current_text)
        changed_note = f" The text it replaced is in {kept}."

    criteria_path.write_text(guard["text"])
    return (f"The acceptance criteria in {guard['path']} changed after a ruling the user did not make, and the "
            f"script restored them.{changed_note}")


def plan_edit_prompt(state, criteria_path):
    ruling = state["ruling"]
    user_ruled = ruling["byUser"]
    edit_scope = f"the plan file {state['plan']}"
    if criteria_path and user_ruled:
        edit_scope += f" and its acceptance criteria file {criteria_path}"
    lines = [
        f"Edit only {edit_scope}. In Phase {state['phase']}, the code and the plan disagreed:",
        "",
        state["impact"],
        "",
        (f"The user ruled ({ruling['by']}, {ruling['at']}):" if user_ruled
         else f"The ruling ({ruling['by']}, {ruling['at']}):"),
        "",
        ruling["words"],
        "",
        "Rewrite each step, Automated Verification command and Success Criteria line of the plan that the ruling "
        "contradicts, so that the plan states the ruling. Keep every other line as it is. Leave the "
        "`## Plan Deviations` section as it is. Edit no code and no test, and run no check.",
    ]
    if criteria_path and not user_ruled:
        lines += ["", f"Do not edit {criteria_path}. Only the user's own sign-off changes an acceptance criterion."]
    if criteria_path and user_ruled:
        lines += [
            "",
            f"Rewrite each criterion in {criteria_path} that the ruling changes, so that it states the ruling. Under "
            f"each one you rewrite, add `Signed off by {ruling['by']}, {ruling['at']}: <the change in one line>`. "
            "Keep every other criterion as it is.",
        ]
    lines += ["", "Report each line you changed as `<file>:<line number>: <new text>`."]
    return "\n".join(lines)


def emit_plan_edit_dispatch(repo_dir, state):
    # An adopted change stays only in Plan Deviations unless the steps that contradict it change too, and the
    # reviewer then reads the old step and raises the same disagreement again.
    criteria_path = criteria_file(repo_dir, state)
    ruling = state["ruling"]
    if not ruling["byUser"]:
        save_criteria_guard(repo_dir, state)
    state.update({"stage": "plan-coder", "planEditBaseline": file_hashes(repo_dir),
                  "followUpBefore": change_snapshot(repo_dir)})
    open_dispatch(state)
    save_state(repo_dir, state)

    prompt = plan_edit_prompt(state, criteria_path)
    if ruling["byUser"]:
        criteria_clause = " and acceptance criteria" if criteria_path else ""
        headline = (f"The user adopted the plan change. Dispatch a coder to rewrite the plan steps{criteria_clause} "
                    "it contradicts.")
    else:
        unchanged_clause = " The acceptance criteria do not change." if criteria_path else ""
        headline = (f"The plan change was adopted by {ruling['by']}. Dispatch a coder to rewrite the plan steps it "
                    f"contradicts.{unchanged_clause}")
    emit_dispatch(repo_dir, state, RESUME_VERB, headline, prompt=prompt, agent="coder")


def command_review_again(repo_dir, state, args):
    state.pop("stopReason", None)
    state.pop("resumableReview", None)
    state.pop("resumeWaitAt", None)
    # A failed review that ran the structure pass runs it again; one that skipped it skips it again.
    if not state.get("structurePassSkipped"):
        state.pop("reviewRan", None)
    emit_review_dispatch(repo_dir, state)


def command_after_plan_edit(repo_dir, state, args):
    if not wait_for_handback(repo_dir, state, RESUME_VERB):
        return
    state = load_state(repo_dir)
    state["sessionId"] = session_pin() or state.get("sessionId")

    # Nothing below changes state until the run is on the plan's branch with the plan in place: the saved criteria
    # and the baseline wait for it. /code sends only decide, asks-done, resume, review-again and tick on as verbs, so
    # the user runs the resume by hand.
    resume_command = f"`! python3 ~/.claude/scripts/code_step.py {RESUME_VERB}`"
    start_branch = state.get("branch")
    if "branch" in state and current_branch(repo_dir) != start_branch:
        where = (f"Switch back to branch {start_branch}" if start_branch not in (None, "-")
                 else "Check out the branch or commit where the plan edit started")
        return emit(
            "stop",
            f"The plan edit finished on a different branch from the one it started on. {where}, then "
            f"run {resume_command} from the repo root, and tell the session to follow its ACTION line. Tell the "
            "user.",
        )

    if not (repo_dir / state["plan"]).is_file():
        return emit("stop", f"The plan {state['plan']} is missing from this checkout, so the plan edit cannot be "
                    f"read. Restore {state['plan']}, then run {resume_command} from the repo root, and tell the "
                    "session to follow its ACTION line. Tell the user.")

    had_criteria_guard = state.get("criteriaGuard") is not None
    criteria_message = settle_criteria_guard(repo_dir, state, current_branch(repo_dir))
    if criteria_message:
        say(repo_dir, criteria_message)

    if had_criteria_guard:
        save_state(repo_dir, state)

    baseline = state.pop("planEditBaseline")
    changed_now = file_hashes(repo_dir)
    edited_files = [name for name, digest in changed_now.items() if baseline.get(name) != digest]

    criteria_path = criteria_file(repo_dir, state)
    allowed_files = (state["plan"], criteria_path) if state["ruling"]["byUser"] else (state["plan"],)
    stray_files = [name for name in edited_files if name not in allowed_files]
    if stray_files:
        state["files"] += [name for name in stray_files if name not in state["files"]]
        state["flagged"].append("the plan-edit coder also changed " + ", ".join(stray_files))
        state["exception"] = True

    plan_lines = (repo_dir / state["plan"]).read_text().splitlines()
    state["phaseText"] = phase_text(plan_lines, state["phase"])

    plan_note = f"The plan {state['plan']} now states the ruling."
    if criteria_path and criteria_path in edited_files and state["ruling"]["byUser"]:
        plan_note += f" The acceptance criteria in {criteria_path} changed too: read them before you stage."
    say(repo_dir, plan_note)

    emit_review_dispatch(repo_dir, state)


def handoff_block(state):
    lines = ["handoff:", "  files:"]
    behavior_fallback = state["behavior"][0] if state.get("behavior") else None
    for path in state["files"]:
        lines.append(f"    - path: {path}")
        lines.append(f"      change: {state['changes'].get(path) or behavior_fallback or 'changed by the coder'}")
        notes = state["why"].get(path)
        if notes:
            lines.append("      why:")
            for note in notes:
                lines.append(f"        - lines: {note['lines']}")
                lines.append(f"          note: {note['note']}")
    if state.get("priorIssues"):
        lines.append("  prior-issues:")
        for prior_issue in state["priorIssues"]:
            lines.append(f"    - issue: {prior_issue['issue']}")
            lines.append("      status: fixed")
            lines.append(f"      file: {prior_issue['file'] or '-'}")
    lines.append(f"  tests-run: {state['testsRun']}")
    lines.append("  flagged: " + ("; ".join(state["flagged"]) if state["flagged"] else "none"))
    plan_impact = state.get("planImpact", "none")
    if plan_impact == "none":
        lines.append("  plan_impact: none")
    else:
        lines.append("  plan_impact: |")
        lines += ["    " + line for line in plan_impact.splitlines()]
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


def change_snapshot(repo_dir):
    # Added lines per file (tracked diff against HEAD, and the line count of each untracked file) and the files that
    # are new, so the change a coder makes is the difference between two snapshots.
    added = {}
    new_files = set()
    for row in (git_output(repo_dir, "diff", "--numstat", "HEAD") or "").split("\n"):
        columns = row.split("\t")
        if len(columns) == 3:
            added[columns[2]] = int(columns[0]) if columns[0].isdigit() else 0
    for row in (git_output(repo_dir, "diff", "--name-status", "HEAD") or "").split("\n"):
        columns = row.split("\t")
        if len(columns) == 2 and columns[0] == "A":
            new_files.add(columns[1])
    untracked = (git_output(repo_dir, "ls-files", "--others", "--exclude-standard") or "").split("\n")
    for name in untracked:
        if not name:
            continue
        new_files.add(name)
        path = repo_dir / name
        added[name] = path.read_bytes().count(b"\n") if path.is_file() else 0
    return {"added": added, "newFiles": sorted(new_files)}


def follow_up_is_small(before, after):
    # True when the coder that ran between the two snapshots added under SMALL_FOLLOW_UP_LINES lines to counted
    # non-test files and created no new non-test source file.
    added_lines = sum(max(count - before["added"].get(name, 0), 0) for name, count in after["added"].items()
                     if is_counted_source(name))
    created_source = [name for name in after["newFiles"] if name not in before["newFiles"]
                     and name not in before["added"] and is_counted_source(name)]
    return added_lines < SMALL_FOLLOW_UP_LINES and not created_source


def emit_review_dispatch(repo_dir, state):
    coder_stages = ["coder"] + (["asks-coder"] if state.get("coderStage") == "asks-coder" else [])
    stage_reports = []
    for stage in coder_stages:
        stage_report = latest_coder_message(repo_dir, stage)
        stage_reports.append(with_earlier_report(state, stage_report) if stage == "coder" else stage_report)
    report = "\n\n".join(stage_report for stage_report in stage_reports if stage_report is not None)
    untracked_text = git_output(repo_dir, "ls-files", "--others", "--exclude-standard") or ""
    untracked_files = set(untracked_text.split("\n"))
    # One behavior sentence describes one file. Across several files it tells the reviewer the wrong change.
    is_one_file = len(state["files"]) == 1
    behavior_fallback = state["behavior"][0] if state["behavior"] and is_one_file else None
    state["changes"] = {path: change_line(report, path, state["files"], behavior_fallback, path in untracked_files)
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
    follow_up_before = state.pop("followUpBefore", None)
    is_small_follow_up = follow_up_before is None or follow_up_is_small(follow_up_before, change_snapshot(repo_dir))
    state["structurePassSkipped"] = bool(state.get("reviewRan") and is_small_follow_up)
    if state["structurePassSkipped"]:
        header.append("structure-pass: skip")
    state["reviewRan"] = True
    prompt = "\n".join(header) + "\n\n" + handoff_block(state)
    state["stage"] = "review"
    open_dispatch(state)
    # The review step reads only reports saved after this dispatch, so a report already acted on is not read again.
    reports_file = state_dir(repo_dir) / "reports.jsonl"
    state["reviewReportsFloor"] = len(reports_file.read_text().splitlines()) if reports_file.exists() else 0
    state["lastReviewPrompt"] = prompt
    save_state(repo_dir, state)

    summary = ["Implemented: " + ("; ".join(state["behavior"]) or "see the diff.")]
    summary.append("Flagged: " + ("; ".join(state["flagged"]) if state["flagged"] else "none."))
    for path, notes in state["why"].items():
        summary += [f"  {path}:{note['lines']} - {note['note']}" for note in notes]
    summary.append("Auto-dispatching review to check the implementation before committing.")
    say(repo_dir, "\n".join(summary))
    emit_dispatch(repo_dir, state, RESUME_VERB, prompt=prompt, agent="review-loop", model="sonnet")


# ---------- hook ----------

def is_pinned_fork_event(event, state):
    # The /code fork is the one general-purpose agent in the session that /code pinned. A general-purpose agent of
    # another session, or of a session /code did not pin, is not touched. The agent type is the only thing a hook
    # event records about the fork (its description is not in the event).
    session_id = event.get("session_id")
    pinned_session = state.get("sessionId")
    return event.get("agent_type") == FORK_AGENT_TYPE and bool(session_id) and session_id == pinned_session


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
              f"{RESUME_VERB}` with Bash timeout {BASH_TIMEOUT_MS}: it waits for the hand-back and "
              "prints the next action.")
    script_utils.pre_tool_use_deny(reason)


def tool_response_agent_id(tool_response):
    # The id in the tool_response of a nested Agent call that launched async, or None when the response holds none.
    if not isinstance(tool_response, dict):
        return None
    return tool_response.get("agentId")


HookCall = collections.namedtuple("HookCall", "event cwd state run_id session_id tool_input")


def read_hook_call(require_run=True):
    # The setup every hook shares. Reads the event on stdin and returns it with the repo's state, the run id, the
    # session and the tool call's input. Returns None when the event is not an object, the repo holds no state, the
    # state is pinned to another session, or (require_run) the state has no run.
    event = json.load(sys.stdin)
    if not isinstance(event, dict):
        return None

    cwd = event.get("cwd") or "."
    state = load_state(cwd)
    if not state:
        return None

    run_id = state.get("runId")
    if require_run and not run_id:
        return None

    session_id = event.get("session_id")
    if session_id and state.get("sessionId") and session_id != state["sessionId"]:
        return None

    tool_input = event.get("tool_input") if isinstance(event.get("tool_input"), dict) else {}
    return HookCall(event, cwd, state, run_id, session_id, tool_input)


def command_log_hook():
    # PostToolUse on Agent, SubagentHandback and SendMessage: one event per call that went through. A hand-back that
    # the PreToolUse gates denied never reaches PostToolUse, so it is never logged.
    try:
        call = read_hook_call()
        if call is None or call.state.get("stage") == "done":
            return

        tool_name = call.event.get("tool_name")
        if tool_name == "Agent":
            marker = dispatch_marker(call.tool_input.get("prompt"))
            if marker is None or marker[0] != call.run_id:
                return

            agent_id = tool_response_agent_id(call.event.get("tool_response"))
            if agent_id is None:
                print("code-step log-hook: the Agent call's tool_response has no agentId; no launch logged",
                      file=sys.stderr)
                return

            log_event(call.cwd, call.run_id, "launch", call.session_id, agent_id=agent_id, dispatch=marker[1])
        elif tool_name == "SendMessage":
            log_event(call.cwd, call.run_id, "resume", call.session_id, agent_id=call.tool_input.get("to"))
        elif tool_name == "SubagentHandback":
            message = str(call.tool_input.get("message", ""))
            log_event(call.cwd, call.run_id, "handback", call.session_id, agent_id=call.event.get("agent_id"),
                      agent_type=call.event.get("agent_type"), message=message)
    except Exception as error:
        print(f"code-step log-hook: {error}", file=sys.stderr)


def command_dispatch_hook():
    # PreToolUse on Agent: while a coder or review-loop dispatch of the run is pending, the Agent call for that agent
    # type must carry the whole saved dispatch prompt. A coder dispatch may not be launched twice: an Agent call that
    # carries its marker after its launch is denied. A review-loop launch is never denied for a repeat, because the
    # shared hand-back store records a review-loop dispatch even when this hook denies the call.
    try:
        call = read_hook_call()
        if call is None or call.event.get("tool_name") != "Agent" or call.state.get("stage") not in HOOK_STAGES:
            return

        standing = dispatch_standing(read_events(call.cwd, call.run_id))
        dispatch = standing["dispatch"]
        if dispatch is None or dispatch.get("stage") != call.state["stage"]:
            return
        if time.time() - dispatch["ts"] > SAY_MAX_AGE_SECONDS:
            return
        if call.tool_input.get("subagent_type") != dispatch.get("agent_type"):
            return

        if standing["launched"] is not None:
            carries_marker = dispatch_marker(call.tool_input.get("prompt")) == (call.run_id, dispatch["id"])
            if dispatch.get("agent_type") != CODER or not carries_marker:
                return

            reason = (f"This dispatch was already launched (agent {standing['launched'].get('agent_id')}). Do not "
                      f"dispatch it again. Run {own_path(timed_command(dispatch['verb']))}: it waits for the "
                      "hand-back and prints the next action.")
            log_event(call.cwd, call.run_id, "fork-block", call.session_id, dispatch=dispatch["id"], kind="relaunch")
            script_utils.pre_tool_use_deny(reason)
            return

        prompt_file = dispatch.get("prompt_file") or ""
        try:
            saved_prompt = pathlib.Path(prompt_file).read_text()
        except OSError:
            return
        if script_utils.contains_ignoring_whitespace(call.tool_input.get("prompt"), saved_prompt):
            return

        reason = (f"The prompt of this Agent call is not the dispatch prompt. Read {prompt_file} and pass its whole "
                  "text.")
        denials = sum(1 for block in standing["blocks"] if block.get("kind") == "prompt-deny")
        if denials >= PROMPT_DENIAL_LIMIT:
            reason = (f"This Agent call was denied {denials} times. Stop. Do not dispatch again and do not run another "
                      f"verb. Tell the user the dispatch prompt in {prompt_file} could not be passed.")
        log_event(call.cwd, call.run_id, "fork-block", call.session_id, dispatch=dispatch["id"], kind="prompt-deny")
        script_utils.pre_tool_use_deny(reason)
    except Exception as error:
        print(f"code-step dispatch-hook: {error}", file=sys.stderr)


def command_stop_hook():
    # SubagentStop: the fork ends its turn while a dispatch is open (it answered the Agent call's immediate return
    # instead of waiting). Block that stop and name the waiting command, at most FORK_STOP_BLOCK_LIMIT times per
    # dispatch.
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
                  f"`{own_path(INSTALLED_COMMAND)} {RESUME_VERB}` with Bash timeout {BASH_TIMEOUT_MS}: "
                  "it waits for the hand-back and prints the next action.")
        print(json.dumps({"decision": "block", "reason": reason}))
    except Exception as error:
        print(f"code-step stop-hook: {error}", file=sys.stderr)


def command_hook():
    try:
        call = read_hook_call(require_run=False)
        if call is None:
            return

        event, cwd, state, session_id = call.event, call.cwd, call.state, call.session_id
        agent_type = event.get("agent_type")
        if agent_type not in ("coder", "review-loop", FORK_AGENT_TYPE):
            return

        is_resumed_coder = (state["stage"] == "stopped" and agent_type == CODER
                          and state.get("resumableCoderAt") is not None
                          and state.get("resumableCoderId") == (event.get("agent_id") or "unknown"))
        launch_id = pending_review_agent_id(cwd, state)
        is_resumed_review = (agent_type == REVIEW_LOOP and awaits_resumed_review(state)
                           and launch_id is not None and event.get("agent_id") == launch_id)
        if state["stage"] not in HOOK_STAGES and not is_resumed_coder and not is_resumed_review:
            return

        pinned_session = state.get("sessionId")
        if is_resumed_coder:
            put_resumed_coder_back(cwd, state)
        if is_resumed_review:
            state.pop("forkDenied", None)
            state.pop("forkStopBlocks", None)
            put_resumed_review_back(cwd, state)
        if agent_type == FORK_AGENT_TYPE:
            if is_pinned_fork_event(event, state):
                deny_early_fork_handback(cwd, state)
            return
        if session_id and not pinned_session and state["stage"] == "coder":
            state["sessionId"] = session_id
            save_state(cwd, state)
        row = {"ts": time.time(), "agent_type": agent_type, "agent_id": event.get("agent_id") or "unknown",
               "stage": state["stage"], "message": str(call.tool_input.get("message", ""))}
        with (state_dir(cwd) / "reports.jsonl").open("a") as reports_file:
            reports_file.write(json.dumps(row) + "\n")
    except Exception as error:
        print(f"code-step hook: {error}", file=sys.stderr)


# ---------- review ----------

def command_after_review(repo_dir, state, args):
    if not wait_for_handback(repo_dir, state, RESUME_VERB, long_checks_follow=True):
        return
    state = load_state(repo_dir)
    if awaits_resumed_review(state):
        # The run stopped at the wait cap. The hook puts the stage back when the resumed review-loop hands back; the
        # shared store row, which can come first, does the same here.
        if latest_handback_row(repo_dir, state, REVIEW_LOOP, state.get("dispatchAt") or 0) is None:
            return emit("stop", resumed_agent_pending_stop(REVIEW_LOOP))
        put_resumed_review_back(repo_dir, state)

    # Only the review-loop that the pending review dispatch launched is read. Another review-loop's hand-back is
    # ignored.
    launch_id = pending_review_agent_id(repo_dir, state)
    if launch_id is None:
        return emit("stop", "The pending review-loop dispatch has no launch record, so no hand-back can be matched to "
                    f"it. Launch it as printed, then run `{script_command(RESUME_VERB)}` again.")
    messages = saved_messages(repo_dir, "review-loop", "review", state.get("reviewReportsFloor", 0), agent_id=launch_id)
    if not messages:
        # The shared store can see the hand-back before this script's own hook has written its row.
        store_row = handback_store_row(state)
        if (isinstance(store_row, dict) and store_row.get("agent_id") == launch_id
                and store_row.get("ts", 0) > (state.get("dispatchAt") or 0) and store_row.get("message")):
            messages = [store_row["message"]]
    if not messages:
        return emit(
            "stop", "No review-loop packet was saved. The SubagentHandback hook is not installed. Tell the user."
        )
    module, import_error = load_handback()
    if module is None:
        return emit("stop", f"Cannot read the review-loop packet: {import_error}. Tell the user.")
    try:
        packet = module.load(messages[-1])
    except module.PacketError as error:
        state.update({"stage": "stopped", "stopReason": "invalid-packet"})
        save_state(repo_dir, state)
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
        save_state(repo_dir, state)
        return emit_plan_impact_modal(state["impact"], repo_dir)
    if status == "critical-blocker":
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        return emit("stop", "Review found a critical blocker. Present these to the user. Do not mark the phase done.",
                    *["- " + module.item_text(item, "finding", "file_line") for item in packet["blockers"]])
    if status == "cap-reached":
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        return emit("stop", "The review cap was reached. Report these findings to the user. Do not mark the phase "
                    "done. The session stays dirty, so git commit stays blocked.",
                    *["- " + module.item_text(item, "finding", "file_line") for item in packet["findings_remaining"]])

    save_state(repo_dir, state)
    say(repo_dir, module.render(packet, "code"))
    print("The review packet was saved for the user. Do not repeat it.")
    asks = packet["ask"]
    if asks:
        return present_asks(repo_dir, state, asks)
    finish_phase(repo_dir, state)


ASK_OUTCOMES = ("accepted", "rejected", "modified")


def preset_ask_outcome(repo_dir):
    # A pre-answered outcome for every review ask, for runs with no user (claude -p, bench): env var or a file in the
    # state dir.
    word = os.environ.get("CODE_STEP_ASKS_OUTCOME", "").strip().lower()
    preset_file = state_dir(repo_dir) / "asks-outcome"
    if not word and preset_file.exists():
        word = preset_file.read_text().strip().lower()
    return word if word in ASK_OUTCOMES else None


def present_asks(repo_dir, state, asks):
    anchors = []
    for item in asks:
        file_line = item.get("file_line", "")
        question = item.get("question", "")
        is_single_anchor = re.match(r"^[^\s,;]+:\d+(-\d+)?$", file_line) is not None
        if is_single_anchor and shutil.which("nvim-jump"):
            anchors += ["--note", question[:120], file_line]
    if anchors:
        run_command(["nvim-jump", *anchors], repo_dir)
    state["asks"] = asks
    preset_outcome = preset_ask_outcome(repo_dir)
    is_new_ask_after_asks_coder = preset_outcome and preset_outcome != "rejected" and state.get("asksApplied")
    if is_new_ask_after_asks_coder:
        print(f"{len(asks)} new review ask(s) came back after the asks coder ran. The pre-set outcome "
              f"'{preset_outcome}' does not cover them: they go to the user.")
        return ask_the_user(repo_dir, state, asks)
    if preset_outcome:
        print(f"{len(asks)} review ask(s) answered by the pre-set outcome '{preset_outcome}'. No question to the user:")
        say(repo_dir, "Review asks, answered by the pre-set outcome:\n" + "\n".join(
            f"{n + 1}. {ask_text(item)}" for n, item in enumerate(asks)))
        log_ask_outcomes(repo_dir, state, [preset_outcome] * len(asks))
        return apply_asks_or_finish(repo_dir, state, [preset_outcome] * len(asks), [None] * len(asks))
    ask_the_user(repo_dir, state, asks)


def ask_the_user(repo_dir, state, asks):
    if not mark_review_gate_clean(repo_dir, state):
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        return
    state["stage"] = "asks"
    save_state(repo_dir, state)
    say(repo_dir, "\n".join([
        "## Question for the user", "",
        f"Main session: ask the user about each review ask below in plain text and wait for the answers. Each answer "
        f"is accepted, rejected or modified. Then invoke Skill code with the args `asks-done` and {len(asks)} outcome "
        "word(s), in order. After a modified outcome, add `--change \"<the user's change text>\"`.", "",
        *[f"{n + 1}. {ask_text(item)}" for n, item in enumerate(asks)]]))
    emit("ask-user", f"The question for the user is in {say_file(repo_dir)}. Hand back.")


def log_ask_outcomes(repo_dir, state, outcomes):
    module, import_error = load_handback()
    if module is None:
        print(f"code-step: ask outcomes not logged: {import_error}", file=sys.stderr)
        return

    branch = git_output(repo_dir, "branch", "--show-current") or "-"
    for item, outcome in zip(state["asks"], outcomes, strict=False):
        finding_id = module.ask_finding_id(item)
        if finding_id is None:
            # The outcome supersedes its ask row by finding_id. Only an id the ledger writer mints replaces a row:
            # a placeholder such as "none" or a damaged id would add a second finding.
            ignored_value = item.get("finding_id")
            ignored_text = "no finding_id" if ignored_value is None else f"ignored {ignored_value!r}"
            print(f"code-step: ask outcome without a valid finding_id ({ignored_text}), not logged", file=sys.stderr)
            continue

        file_line = item.get("file_line", "-:0")
        path, _, line = file_line.partition(":")
        # The writer takes phase as a token, so a run with no phase sends none.
        phase_args = [f"phase={state['phase']}"] if state.get("phase") else []
        logger_code, logger_output = run_command(
            ["bash", str(CLAUDE_DIR / "skills/review/log-review-finding"), "kind=finding",
             f"finding_id={finding_id}", f"branch={branch}", f"lane={state['lane']}", "scope=phase",
             *phase_args, f"iter={state['iter']}",
             f"gate={item.get('gate', 'code-reviewer')}",
             "disposition=ask", f"class={item.get('class', 'other')}", f"file={path}",
             f"line={re.sub(r'[^0-9].*', '', line) or '0'}", "actioned=ask", f"ask_outcome={outcome}"], repo_dir)
        if logger_code != 0:
            print(f"code-step: ask outcome for finding_id {finding_id} not logged: log-review-finding exited "
                  f"{logger_code}: {script_utils.one_line(logger_output)}", file=sys.stderr)


def asks_coder_prompt(accepted_asks):
    lines = ["Apply these review asks. The user accepted them. Change only what they name.", ""]
    for number, (item, outcome, change_text) in enumerate(accepted_asks, 1):
        location = item.get("file_line", "")
        lines.append(f"{number}. [{outcome}] {ask_text(item)}"
                     + (f" ({location})" if location else ""))
        if change_text:
            lines.append(f"   The user's change: {change_text}")
    lines += [
        "",
        "Run the typecheck, and lint and tests for only the files you changed, once, after all edits. "
        "If an ask turns out architectural, report back and recommend /eng-spec.",
        "For each ask whose change the code already makes, so that it needs no edit, add one line to your report: "
        "`ALREADY-DONE: <ask number> — <file:line>`. Add that line for no other ask.",
    ]
    return "\n".join(lines)


def apply_asks_or_finish(repo_dir, state, outcomes, change_texts):
    # An accepted or modified ask is owed work: a coder applies it, then a review of that coder's diff runs (none when
    # the diff is docs only) before the phase can finish.
    accepted_asks = [
        [item, outcome, change_text]
        for item, outcome, change_text in zip(state["asks"], outcomes, change_texts, strict=False)
        if outcome != "rejected"
    ]
    if not accepted_asks:
        state["stage"] = "review"
        save_state(repo_dir, state)
        return finish_phase(repo_dir, state)

    state.update({"stage": "asks-coder", "acceptedAsks": accepted_asks, "asksApplied": True,
                  "asksBaseline": file_hashes(repo_dir), "followUpBefore": change_snapshot(repo_dir)})
    open_dispatch(state)
    save_state(repo_dir, state)
    model = "haiku" if state.get("modifier") == "+fast" else None
    emit_dispatch(repo_dir, state, RESUME_VERB, "The user accepted review asks. Dispatch a coder to apply them. A "
                  "review of that coder's diff runs after it (none when the diff is docs only) before the phase can "
                  "finish.", prompt=asks_coder_prompt(accepted_asks), agent="coder", model=model)


def split_asks_done_args(args):
    # Outcome words in order, and the text after each `--change` flag, one per modified ask, in order.
    outcomes = []
    change_texts = []
    position = 0
    while position < len(args):
        if args[position] == "--change":
            if position + 1 >= len(args):
                return outcomes, None
            change_texts.append(args[position + 1])
            position += 2
            continue
        outcomes.append(args[position])
        position += 1
    return outcomes, change_texts


def command_asks_done(repo_dir, state, args):
    outcomes, given_changes = split_asks_done_args(args)
    if len(outcomes) != len(state["asks"]) \
            or any(outcome not in ASK_OUTCOMES for outcome in outcomes) or given_changes is None \
            or len(given_changes) != outcomes.count("modified"):
        return emit("stop", ASKS_DONE_USAGE)

    remaining_changes = iter(given_changes)
    change_texts = [next(remaining_changes) if outcome == "modified" else None for outcome in outcomes]
    log_ask_outcomes(repo_dir, state, outcomes)
    apply_asks_or_finish(repo_dir, state, outcomes, change_texts)


# ---------- phase gates and boundary ----------

def command_skill_done(repo_dir, state, args):
    verdict = args[0].lower() if args else "pass"
    if verdict not in ("pass", "fail"):
        return emit("stop", "skill-done takes pass or fail.")
    if verdict == "fail":
        state["stage"] = "stopped"
        save_state(repo_dir, state)
        return emit("stop", "The closing phase's check failed (a MISSING criterion, or an unmet Success Criteria). "
                    "Do not mark the phase done. Report what failed to the user.")
    finish_phase(repo_dir, state, skip_verification=True)


def command_tick(args):
    # The user finished a phase outside /code. The main session runs this only on the user's word.
    repo_dir = repo_root()
    os.chdir(repo_dir)
    state = load_state(repo_dir)
    if len(args) != 1:
        return emit("stop", "usage: code_step.py tick <phase id>")
    if state is None or not state.get("plan"):
        return emit("stop", "tick needs a plan run: there is no saved plan state. Run `start <plan>` first.")
    if stop_while_plan_edit_coder_is_out(repo_dir, state, "tick " + " ".join(args)):
        return
    plan_path = repo_dir / state["plan"]
    if not plan_path.is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")
    plan = parse_plan(plan_path.read_text().splitlines())
    if plan["failures"]:
        return emit("stop", plan_failure_message(plan, state["plan"]))
    number = args[0]
    entry = next((e for e in plan["entries"] if e["number"] == number), None)
    if entry is None:
        listed = ", ".join(e["number"] for e in plan["entries"]) or "none"
        return emit("stop", f"Phase {number} is not in the Phase Status of {state['plan']}. Listed phases: {listed}.")
    if entry["moved"]:
        return emit("stop", moved_phase_stop(entry, state["plan"]))
    if entry["done"]:
        return emit("stop", f"Phase {number} is already marked done in {state['plan']}.")

    criteria_message = settle_criteria_guard(repo_dir, state, current_branch(repo_dir))
    if criteria_message:
        say(repo_dir, criteria_message)

    mark_phase_done(plan_path, number)
    append_deviation(plan_path, [f"- {time.strftime('%Y-%m-%d')} (Phase {number}): marked done with `tick`, outside "
                                "the coder, review and verification steps of /code."])
    state.update({"stage": "done", "phase": number, "autoAdvance": False, "commitFiles": [], "commitLine": ""})
    state.pop("dispatchAt", None)
    save_state(repo_dir, state)
    emit("stop", f"Phase {number} is marked done in {state['plan']}. Run `resume` for the next phase when the user "
         "asks.")


def command_verify(repo_dir, state, args):
    finish_phase(repo_dir, state)


COMMAND_START = re.compile(r"^(?:" + script_utils.ENV_PREFIX.pattern + r")?"
                           r"(cd |npm |npx |pnpm |yarn |git |node |python3? |pytest|ruff |bash |curl |make "
                           r"|cargo |go |deno |bun |uv |poetry |tsc\b|eslint |vitest|jest|mvn |gradle |\./"
                           r"|dotnet |docker |just |rake |bundle |ruby |php |composer |mix |swift |sbt |bazel |tox\b"
                           r"|mypy |pyright|sh )")

# Programs that a prose span can start with but that are never a check: they start a session, never end or wait for
# input. `tail` is one only when it follows a file (see TAIL_FOLLOWS).
NOT_A_CHECK_PROGRAMS = ("claude", "yes", "watch", "top", "htop", "less", "more", "vi", "vim", "nano", "sleep")
TAIL_FOLLOWS = re.compile(r"^(?:-[A-Za-z0-9]*[fF][A-Za-z0-9]*|--follow(?:=\w+)?)$")


def deferred_verification_items(phase_section):
    # (tag, item text) for each Automated Verification item the plan leaves to CI or to a person, in file order.
    deferred = []
    for _, line in plan_format.automated_verification_rows(phase_section.splitlines()):
        tag = plan_format.deferred_verification_tag(line)
        if not tag:
            continue

        item_text = plan_format.automated_item_text(line)
        deferred.append((tag, item_text))
    return deferred


def never_returns(words):
    # True when the command in `words` is a program that never ends or waits for input, so it cannot be a check.
    program_name = pathlib.PurePath(words[0]).name
    if program_name in NOT_A_CHECK_PROGRAMS:
        return True

    return program_name == "tail" and any(TAIL_FOLLOWS.match(word) for word in words[1:])


def starts_like_a_program_here(span, repo_dir):
    # A span COMMAND_START does not know is a command when it starts with a path to an executable file of the repo,
    # or with a program on PATH that has at least one argument after it (a program word alone is how prose names a
    # tool, and a bare word is looked up on PATH only, never in the repo).
    words = script_utils.without_leading_env_assignments(span).split()
    if not words:
        return False

    program = words[0]
    has_slash = "/" in program
    if has_slash and repo_dir is not None and script_utils.is_executable_file_inside(repo_dir, program):
        return True

    if len(words) < 2 or never_returns(words):
        return False

    # A relative path with a slash is looked up from the working directory, not PATH: only the repo-file rule above
    # may accept it, and that rule keeps it inside the repo.
    if has_slash and not pathlib.PurePath(program).is_absolute():
        return False

    return shutil.which(program) is not None


def verification_command(line, repo_dir=None):
    # The first backticked span that starts with a known program, after any leading NAME=value assignments, which the
    # shell passes to the command; when none does, the first span that starts with a program of this machine. The
    # line may continue after it ("`npm run build` exits 0.").
    spans = script_utils.backticked_spans(line)
    for span in spans:
        if COMMAND_START.match(span):
            return span

    for span in spans:
        if starts_like_a_program_here(span, repo_dir):
            return span

    return None


def verification_item_problem(line, repo_dir):
    # Why an Automated Verification item cannot run, or None when it runs, says there is nothing to run or is left to
    # CI or a person. The write-time check of a plan and the stop after a phase use this one reading.
    if plan_format.runs_no_command(line):
        return None
    if verification_command(line, repo_dir):
        return None

    spans = script_utils.backticked_spans(line)
    if not spans:
        return "it has no backticked command and is not marked N/A, CI-verified or human-only"

    start_words = []
    for span in spans:
        first_word = script_utils.first_command_word(span) or span
        start_words.append(f"`{first_word}`")
    return ("no backticked span starts with a program on PATH (with an argument) or an executable file in the repo "
            f"(it starts with {', '.join(start_words)})")


VERIFICATION_ITEM_SHAPE = (
    "Each Automated Verification item is one line in one of three shapes. (1) One backticked command that starts with "
    "a program on PATH (with at least one argument) or an executable file in the repo, for example the line "
    "'- [ ] **Name**: what it checks - `npm test`'. (2) N/A, for example '- [ ] N/A - docs only'. (3) A tag that "
    "says CI or a person runs it, for example '- [ ] **CI-verified**: the pipeline runs it' or '- [ ] Human-only: "
    "look at the page'. This script never runs the third shape.")


def verification_format_failure(plan_lines, plan_name, repo_dir, entries):
    # The write-time message for open phases whose Automated Verification items cannot run, or None when all can. A
    # closing phase is checked by its skill, which runs no verification command.
    problems = []
    for entry in entries:
        if not entry["open"] or entry["closing"]:
            continue

        section = plan_format.phase_section(plan_lines, entry["number"])
        if section is None:
            continue

        section_lines = plan_lines[section["start"]:section["end"]]
        for index, line in plan_format.automated_verification_rows(section_lines):
            problem = verification_item_problem(line, repo_dir)
            if problem:
                problems.append(f"{plan_name}:{section['start'] + index + 1}: {line.strip()[:100]} - {problem}")

    if not problems:
        return None

    return ("The plan has Automated Verification items that cannot run. Fix each line:\n" + "\n".join(problems) + "\n"
            + VERIFICATION_ITEM_SHAPE)


def check_prohibition(repo_dir, command, code, output):
    # A git grep ban passes on exit 1 (no match) and fails on exit 0 (a hit). Any other exit is an error that stops.
    # A pipe form is judged by its output: empty or 0 passes.
    hit_rows = len([row for row in output.splitlines() if row.strip()])
    if "|" in command:
        verdict = 0 if output.strip() in ("", "0") else 1
        hits = 0 if verdict == 0 else int(output) if output.strip().isdigit() else hit_rows
    elif code == 1:
        verdict, hits = 0, 0
    elif code == 0:
        verdict, hits = 1, hit_rows
    else:
        verdict, hits = code, 0
    run_command(["bash", str(SCRIPTS_DIR / "log-scan"), f"repo={repo_dir.name}", "scan=prohibition",
                 "stage=code-phase", f"exit={verdict}", f"candidates={hits}", f"confirmed={hits}",
                 f"branch={current_branch(repo_dir)}", f"note={command[:120]}"], repo_dir)
    return command, verdict, output


def run_verification_commands(repo_dir, phase_section):
    results = []
    skipped = []
    unparsed = []
    timeout = int(os.environ.get("CODE_STEP_VERIFY_TIMEOUT", VERIFY_TIMEOUT_SECONDS))
    for _, line in plan_format.automated_verification_rows(phase_section.splitlines()):
        if plan_format.runs_no_command(line):
            continue
        command = verification_command(line, repo_dir)
        if command is None:
            unparsed.append(line.strip())
            continue
        if WHOLE_SUITE.match(script_utils.without_leading_env_assignments(command)):
            skipped.append(command)
            continue
        code, output = run_command(command, repo_dir, timeout=timeout)
        if "git grep" in command:
            results.append(check_prohibition(repo_dir, command, code, output))
            continue
        results.append((command, code, output))
    return results, skipped, unparsed


def mark_phase_done(plan_path, number):
    plan_lines = plan_path.read_text().split("\n")
    entry = next((e for e in parse_plan(plan_lines)["entries"] if e["number"] == number and e["open"]), None)
    if entry:
        plan_lines[entry["line"]] = plan_lines[entry["line"]].replace("[ ]", "[x]", 1)
    plan_path.write_text("\n".join(plan_lines))


def boundary_decision(state, entries, number):
    # A run started with --phase N ends after phase N, whatever other phases are still open. A run never starts a phase
    # past an open gated one, so when a gated phase comes first (or only gated phases are open) this is the last phase
    # the run can do.
    gated_ahead, next_ungated = gate_blockers([e for e in ordered_pending(entries) if e["number"] != number])
    is_last = state.get("onlyPhase") == number or bool(gated_ahead) or next_ungated is None
    if is_last:
        return "C", "last phase"
    if number == "1":
        return "B", "low - Phase 1 calibration" if state["risk"] == "low" else state["risk"]
    if state.get("exception"):
        return "B", "low - exception" if state["risk"] == "low" else state["risk"]
    if state["risk"] == "low":
        return "A", "low"
    return "B", "high"


def mark_review_gate_clean(repo_dir, state):
    # The review-commit-gate hook reads this file: the review loop ended clean, so the session may commit.
    # Returns False after emitting a stop when the hand-back record shows the loop did not end clean, or when the
    # shared hand-back reader is not installed. Nothing is written then.
    module, import_error = load_handback()
    if module is None:
        emit("stop", f"Cannot confirm the review loop ended clean: {import_error}. The review gate is not marked "
             "clean. Tell the user.")
        return False
    reason = module.false_clean_reason(os.environ.get("CLAUDE_CODE_SESSION_ID"))
    if reason:
        emit("stop", f"The review gate is not marked clean: {reason}. Tell the user.")
        return False
    gate_dir = pathlib.Path.home() / ".claude" / "state" / "review-gate"
    gate_dir.mkdir(parents=True, exist_ok=True)
    (gate_dir / (session_pin() or state.get("sessionId") or "unknown")).write_text("clean\n")
    return True


def count_lines(path):
    try:
        return len(path.read_text(errors="replace").splitlines())
    except OSError:
        return 0


def diff_stat_rows(repo_dir, files):
    # One "path | +added -deleted" row per file: git's numstat for tracked files, the line count for new ones.
    numstat = {}
    for row in (git_output(repo_dir, "diff", "--numstat", "HEAD", "--", *files) or "").splitlines():
        added, deleted, name = row.split("\t", 2)
        numstat[name] = (added, deleted)
    rows = []
    for name in files:
        added, deleted = numstat.get(name) or (str(count_lines(repo_dir / name)), "0")
        rows.append(f"{name} | +{added} -{deleted}")
    return rows


TICKET_IN_NAME = re.compile(r"(?<![A-Za-z0-9])([A-Z][A-Z0-9]+-\d+)(?![A-Za-z0-9])")


def ticket_prefix(state):
    # The ticket id the plan folder or the branch carries, as the commit subject's prefix; "" when neither has one.
    plan_folder = pathlib.PurePosixPath(state["plan"]).parent.name if state.get("plan") else ""
    for name in (plan_folder, state.get("branch") or ""):
        found = TICKET_IN_NAME.search(name)
        if found:
            return found.group(1) + ": "
    return ""


def phase_commit(repo_dir, state):
    # The phase's own changed files: dirty now, and not dirty before the phase started. Files that were dirty before
    # stay out of the command, except the plan: the script ticks the phase in it, so the commit carries it even when it
    # held other uncommitted edits before the phase. The commit names its files after `--`, so it takes only those
    # files from the index and leaves anything the user staged by hand staged and uncommitted.
    # Returns (text for the user, the commit command line, the files it commits); the text and line are "" with no
    # files.
    baseline = state.get("baseline") or {}
    dirty_now = file_hashes(repo_dir)
    plan_name = state.get("plan")
    changed_since = [name for name in dirty_now if name in baseline and dirty_now[name] != baseline[name]]
    plan_had_earlier_edits = plan_name in changed_since
    own_files = [name for name in dirty_now if name not in baseline or (name == plan_name and plan_had_earlier_edits)]
    left_out = [name for name in changed_since if name != plan_name]
    if not own_files:
        return "", "", []
    recorded_behavior = state.get("behavior") or []
    message = recorded_behavior[0] if recorded_behavior else (state.get("title") or "phase work")
    prefix = ticket_prefix(state)
    if prefix and not message.lower().startswith(prefix.lower()):
        message = prefix + message
    quoted_files = " ".join(shlex.quote(name) for name in own_files)
    commit_line = f"git add -- {quoted_files} && git commit -m {shlex.quote(message)} -- {quoted_files}"
    lines = ["Files changed by this phase:", *diff_stat_rows(repo_dir, own_files), ""]
    if plan_had_earlier_edits:
        lines += [
            f"{plan_name} had uncommitted edits before the phase. The commit includes them with the phase tick.",
            "",
        ]
    if left_out:
        lines += ["Dirty before the phase and left out of the commit: " + ", ".join(left_out), ""]
    lines += ["Commit command (not run by the script):", commit_line]
    return "\n".join(lines), commit_line, own_files


def finish_phase(repo_dir, state, skip_verification=False):
    if not skip_verification and not mark_review_gate_clean(repo_dir, state):
        return

    if not state.get("plan"):
        state["stage"] = "done"
        save_state(repo_dir, state)
        commit_text, _, _ = phase_commit(repo_dir, state)
        if commit_text:
            say(repo_dir, commit_text)
        return emit("stop", "Planless task reviewed. Tell the user the result.")

    plan_path = repo_dir / state["plan"]
    if not plan_path.is_file():
        return emit("stop", f"The plan file {state['plan']} is missing (a branch switch?). Tell the user.")

    plan_lines = plan_path.read_text().splitlines()
    plan = parse_plan(plan_lines)
    if plan["failures"]:
        return emit("stop", plan_failure_message(plan, state["plan"]))

    number = state["phase"]
    running_entry = next((e for e in plan["entries"] if e["number"] == number), None)
    if running_entry and running_entry["moved"]:
        state["stage"] = "stopped"
        state.pop("stopReason", None)
        save_state(repo_dir, state)
        return emit("stop", moved_phase_stop(running_entry, state["plan"], coder_ran=True))

    section = phase_text(plan_lines, number) if number is not None else "\n".join(plan_lines)
    section = section or ""
    verify_results, skipped, unparsed = ([], [], [])
    if not skip_verification:
        verify_results, skipped, unparsed = run_verification_commands(repo_dir, section)
    # An item that yields no command was not run: the phase is not verified, whatever the other items did.
    if unparsed:
        state.update({"stage": "stopped", "stopReason": "verification"})
        save_state(repo_dir, state)
        tick_text = (
            f" For a check that cannot be automated, the user can confirm it; on the user's word only, invoke "
            f"Skill code with `tick {state['phase']}` to mark the phase done."
            if state.get("phase")
            else " For a check that cannot be automated, the user can confirm it and mark the phase done with `tick`."
        )
        ran_text = ("nothing was run" if not verify_results and not skipped else
                   f"{len(verify_results)} other command(s) ran")
        return emit("stop", f"The phase has Automated Verification items that could not be run ({ran_text}). Do not "
                    "mark the phase done. Report each line to the user:",
                    *[f"- {line} - {verification_item_problem(line, repo_dir)}" for line in unparsed],
                    VERIFICATION_ITEM_SHAPE + tick_text + " " + RESUME_LINE.format(noun="section", verb="verify"))
    failed = [(command, code, output) for command, code, output in verify_results if code != 0]
    if failed:
        state.update({"stage": "stopped", "stopReason": "verification"})
        save_state(repo_dir, state)
        return emit("stop", "Automated Verification failed. Do not mark the phase done. Report to the user:",
                    *[f"- `{command}` exit {code}: {output[-400:]}" for command, code, output in failed],
                    RESUME_LINE.format(noun="failure", verb="verify"))

    try:
        manual_items = phase_manual_items(plan_lines, number, state["plan"])
    except plan_format.PlanFormatError as error:
        state.update({"stage": "stopped", "stopReason": "plan-format"})
        save_state(repo_dir, state)
        return emit("stop", manual_format_message(error, RESUME_LINE.format(noun="section", verb="verify")))

    manual_groups = {
        "verified": [manual_item_line(i) for i in manual_items if i["verified"]],
        "notRun": [manual_item_line(i) for i in manual_items if not i["humanOnly"] and not i["verified"]],
        "humanOnly": [manual_item_line(i) for i in manual_items if i["humanOnly"] and not i["checked"]]}
    reopened = []
    if number is not None:
        is_closing = any(e["number"] == number and e["closing"] for e in plan["entries"])
        mark_phase_done(plan_path, number)
        reopened = [] if is_closing else reopen_closing_phases(plan_path)
    entries = parse_plan(plan_path.read_text().splitlines())["entries"]
    block, risk_label = boundary_decision(state, entries, number)
    gated_ahead, next_ungated = gate_blockers(ordered_pending(entries))
    next_number = next_ungated["number"] if next_ungated else None
    gate_block_message = gate_block_text(gated_ahead, next_ungated) if gated_ahead else ""
    moved_text = moved_phase_text(entries)
    commit_text, commit_line, commit_files = phase_commit(repo_dir, state)
    state["stage"] = "done"
    state["autoAdvance"] = block == "A"
    state["commitFiles"] = commit_files
    state["commitLine"] = commit_line
    state.pop("stopReason", None)
    save_state(repo_dir, state)

    done_text = f"Phase {number} marked done in {state['plan']}." if number is not None \
        else f"The plan {state['plan']} is finished."
    listed_items = [line for _, line in plan_format.automated_verification_rows(section.splitlines())
                   if not plan_format.NO_AUTOMATED_CHECK.match(line)]
    if not verify_results and not skipped and not listed_items:
        done_line = f"{done_text} The phase lists no verification commands, so none were run."
    else:
        done_line = (f"{done_text} Verification run: "
                    f"{len(verify_results)} command(s) green ({'; '.join(c for c, _, _ in verify_results) or 'none'}); "
                    f"skipped as covered by the review loop: {len(skipped)}.")
        not_run_here = [f"not run here: {tag} - {text[:120]}" for tag, text in deferred_verification_items(section)]
        if not_run_here:
            done_line += " " + "; ".join(not_run_here) + "."
    if reopened:
        done_line += (f" Closing phase(s) {', '.join(reopened)} were checked and are unchecked again, so they run on "
                     "the new code.")
    print(done_line)
    say(repo_dir, done_line)
    if commit_text:
        say(repo_dir, commit_text)

    if block == "A":
        next_start = f"{INSTALLED_COMMAND} {RESUME_VERB}"
        say(repo_dir, block_a(number, risk_label, manual_groups, next_number))
        commit_step = (f"First run this commit command as a Bash call: {commit_line}\nThen " if commit_line else "")
        emit("auto-advance", "The user sees block A at the end of the turn. "
             + f"{commit_step}in the same response run `{next_start}` for Phase " + next_number + ".")
        return
    block_text = block_b_or_c(
        block, number, risk_label, state, manual_groups, next_number, gate_block_message, moved_text
    )
    say(repo_dir, block_text.replace("<<STAGE QUEUE>>", "(the /stage queue is printed above in this turn)"))
    emit(
        "stop-block-" + block,
        "Invoke the Skill tool with `stage` and print its queue verbatim. The user sees the rest of the phase-complete "
        "block at the end of the turn: do not write it. Then wait for the user. When they say continue, run "
        f"`code_step.py {RESUME_VERB}`.",
    )


def manual_item_line(item):
    return f"- [{'x' if item['checked'] else ' '}] {item['text']}"


def block_a(number, risk_label, manual_groups, next_number):
    verified_count, not_run_count, human_count = (
        len(manual_groups[name]) for name in ("verified", "notRun", "humanOnly")
    )
    return (
        f"Phase {number} complete - machine gates green (review ✓, execution ✓, automated-verification ✓). "
        f"Risk: low. Manual verification: {verified_count} verified, {not_run_count} agent-run items not yet run "
        f"(/verify-branch runs them at the end of the branch), {human_count} human-only deferred to the "
        f"/verify-branch packet.\n-> Auto-advancing to Phase {next_number} in-session (no /clear; interrupt anytime)."
    )


def block_b_or_c(block, number, risk_label, state, manual_groups, next_number, gate_block_message="", moved_text=""):
    behavior = state.get("behavior") or []
    last_text = f"Phase {number} complete (last phase)." if number is not None else "The plan is complete."
    if number is not None and gate_block_message:
        # Open gated phases mean the plan is not complete, so this phase is not the last one.
        last_text = f"Phase {number} complete."
    is_only_phase = number is not None and state.get("onlyPhase") == number
    if is_only_phase:
        last_text = f"Phase {number} complete (the phase this run was started for)."
    parts = [f"Phase {number} complete. Risk: {risk_label}. Phase-level sign-off requested." if block == "B"
             else last_text, ""]
    if behavior:
        parts += ["Behavior delta (observable change + its proof, max 3 - no internals, no paths):",
                  *[f"- {line}" for line in behavior[:3]], ""]
    parts += ["Read first (/stage queue, blast-radius order):", "<<STAGE QUEUE>>", ""]
    if manual_groups["verified"]:
        parts += ["Verified (checked, or marked agent-verified in the plan):", *manual_groups["verified"], ""]
    if manual_groups["notRun"]:
        parts += ["Agent-run, not yet run (/verify-branch runs these at the end of the branch):",
                  *manual_groups["notRun"], ""]
    if manual_groups["humanOnly"]:
        parts += ["Human-only verification remaining:", *manual_groups["humanOnly"], ""]
    if block == "B":
        queue_steps = (
            ["Read the queue (`]k`/`[k` in nvim)"]
            if manual_groups["verified"] or manual_groups["humanOnly"]
            else ["Read the /stage queue"]
        )
        if manual_groups["verified"]:
            queue_steps.append("spot-check the verified items")
        if manual_groups["humanOnly"]:
            queue_steps.append("run the human-only items")
        step1 = "; ".join(queue_steps) + "."
        parts += [
            "Next:",
            f"  1. {step1}",
            f"  2. Stage what you've read, then run /clear and /code to start Phase {next_number} fresh. "
            "To keep this context, confirm here.",
            "",
            "Or give feedback now for revisions to Phase " + number + ".",
        ]
    elif is_only_phase:
        parts += ["This run was started for this phase only. Other phases may be open; run `resume` when the user "
                  "asks for the next one."]
    elif gate_block_message:
        parts += [f"No phase starts on its own: {gate_block_message} Tell the user. The plan is not complete."]
    elif moved_text:
        parts += [f"All other phases are complete or moved to another ticket ({moved_text}). Next: /verify-branch "
                  "(completeness + review packet; includes the remaining human-only checks), then you open the PR."]
    else:
        parts += ["All phases complete. Next: /verify-branch (completeness + review packet; includes the remaining "
                  "human-only checks), then you open the PR."]
    return "\n".join(parts)


# ---------- resume ----------

def run_guarded_verb(verb, handler, args):
    guard = STAGE_GUARDS[verb]
    repo_dir = repo_root()
    os.chdir(repo_dir)
    state = load_state(repo_dir)
    at_stage = state is not None and state["stage"] in guard["stages"]
    reason_allowed = "stopReasons" not in guard or (state or {}).get("stopReason") in guard["stopReasons"]
    resumed_review = verb == "review-again" and state is not None and awaits_resumed_review(state)
    if not (at_stage and reason_allowed) and not resumed_review:
        return refuse(guard["message"], script_command(RESUME_VERB))
    handler(repo_dir, state, args)


def coder_answer_sent(repo_dir, state):
    # The user's answer reached the stopped coder: it handed back already, or a SendMessage to it is logged after the
    # stop.
    if resumed_coder_row(repo_dir, state) is not None:
        return True
    coder_id = state.get("resumableCoderId")
    return sent_message_since(repo_dir, state, state["resumableCoderAt"], None if coder_id == "unknown" else coder_id)


def review_answer_sent(repo_dir, state):
    # The user resumed the review-loop that the wait cap stopped on.
    launch_id = pending_review_agent_id(repo_dir, state)
    return launch_id is not None and sent_message_since(repo_dir, state, state["resumableReview"], launch_id)


def stopped_route(repo_dir, state):
    if awaits_resumed_coder(state):
        return "after-coder" if coder_answer_sent(repo_dir, state) else "ask-coder"
    if awaits_resumed_review(state):
        return "after-review" if review_answer_sent(repo_dir, state) else "ask-review-cap"

    return "ask-coder-cap" if state.get("stopReason") == "coder-cap" else "ask-unknown"


def resume_route(repo_dir, state):
    # The step that comes next for the saved run, by its stage and stop reason. Pure: it reads and changes nothing.
    if state is None:
        return "start"

    stage = state["stage"]
    if stage in HOOK_STAGES and dispatch_since(state) is None:
        return "ask-unknown"
    if stage in CODER_STAGES:
        return "after-coder"
    if stage == "review":
        return "after-review"
    if stage == "plan-coder":
        return "after-plan-edit"
    if stage in ("impact-coder", "impact-review"):
        return "ask-impact"
    if stage == "asks":
        return "ask-asks"
    if stage == "done":
        return "done"
    if stage == "stopped":
        return stopped_route(repo_dir, state)
    return "ask-unknown"


def ask_about_stopped_coder(repo_dir, state):
    phase_tick = (f" If the user says Phase {state['phase']} is done, run `tick {state['phase']}`."
                 if state.get("plan") and state.get("phase") else "")
    report = state.get("stoppedCoderReport") or "(none saved)"
    restart_instruction_text = restart_instruction(state)
    ask_user(
        repo_dir,
        f"The coder stopped and waits for the user's answer. Its report: {report}. Send the user's "
        f"answer to agent {state['resumableCoderId']} with SendMessage, then run resume.{phase_tick} To dispatch a "
        f"new coder for the phase, {restart_instruction_text}.",
    )


def ask_about_unrecorded_state(repo_dir, state):
    # The fallback stop for a saved state that no route covers: it prints the state and the command that goes on.
    stage = state["stage"]
    stop_reason = state.get("stopReason")
    saved = f"The run is at stage {stage}" + (f" with stop reason {stop_reason}." if stop_reason else ".")
    guarded_verb = next((verb for verb, guard in STAGE_GUARDS.items()
                        if stage in guard["stages"] and stop_reason in guard.get("stopReasons", ())), None)
    if guarded_verb:
        next_step = f"When the cause is fixed, run `{guarded_verb}`."
    elif stage == "skill":
        skill = closing_skill(state.get("title", ""))
        next_step = (f"Invoke the Skill tool with `{skill}`. When it returns, run `skill-done pass` when the phase's "
                    "Success Criteria hold, or `skill-done fail` when they do not.")
    else:
        restart_instruction_text = restart_instruction(state)
        status_command = script_command("status")
        next_step = (
            f"Run `{status_command}` to read the saved state. To start the phase over, {restart_instruction_text}."
        )
    ask_user(repo_dir, f"{saved} {next_step}")


def run_resume_route(repo_dir, state, route):
    if route == "start":
        return command_start([])
    if route == "done":
        return command_start([state["modifier"]] if state.get("modifier") else [])
    if route == "after-coder":
        return command_after_coder(repo_dir, state, [])
    if route == "after-review":
        return command_after_review(repo_dir, state, [])
    if route == "after-plan-edit":
        return command_after_plan_edit(repo_dir, state, [])
    if route == "ask-impact":
        return emit_plan_impact_modal(state["impact"], repo_dir)
    if route == "ask-asks":
        return ask_the_user(repo_dir, state, state["asks"])
    if route == "ask-coder":
        return ask_about_stopped_coder(repo_dir, state)
    if route == "ask-review-cap":
        return ask_user(repo_dir, "The review-loop never handed back. If the user resumes it with SendMessage, run "
                        "resume. If it died, invoke Skill code with `review-again`.")
    if route == "ask-coder-cap":
        restart_instruction_text = restart_instruction(state)
        return ask_user(repo_dir, "The coder never handed back and cannot be resumed here: it is a plan-edit coder, or "
                        f"its launch has no agent id. To dispatch the phase coder again, {restart_instruction_text}.")
    return ask_about_unrecorded_state(repo_dir, state)


def command_resume(args):
    repo_dir = repo_root()
    os.chdir(repo_dir)
    if args:
        return refuse("resume takes no arguments.", script_command(RESUME_VERB),
                      notes=("For new work, use `start --task \"<text>\"`.",))

    state = load_state(repo_dir)
    route = resume_route(repo_dir, state)
    if state is not None and (state["stage"] == "stopped" or state["stage"] in WAITING_STAGES):
        clear_say(repo_dir)
    run_resume_route(repo_dir, state, route)


def command_status():
    state = load_state(repo_root())
    print(json.dumps(state, indent=1) if state else "no code-step state")


def main():
    verb = sys.argv[1] if len(sys.argv) > 1 else ""
    args = sys.argv[2:]
    verbs = {"start": command_start, RESUME_VERB: command_resume, "decide": command_decide,
             "asks-done": command_asks_done, "skill-done": command_skill_done, "verify": command_verify,
             "tick": command_tick, "review-again": command_review_again}
    verbs.update(dict.fromkeys(RESUME_ALIASES, command_resume))
    # These verbs open a new /code run after the user answered. The last run's say.md text was already handed back.
    resume_verbs = ("decide", "asks-done", "verify", "review-again")
    if verb == "hook":
        return command_hook()
    if verb == "log-hook":
        return command_log_hook()
    if verb == "dispatch-hook":
        return command_dispatch_hook()
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
        sys.exit("usage: code_step.py start|resume|decide|asks-done|skill-done|verify|review-again|tick|hook|log-hook"
                 "|dispatch-hook|stop-hook|say-hook|status|plan|plan-hook")
    if verb in resume_verbs:
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
