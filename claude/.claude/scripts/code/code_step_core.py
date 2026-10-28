"""code_step_core.py: what every part of code_step.py shares: the constants, the git and state-file helpers, the
event log of a run, the hand-back matcher and the printed output.

Installed beside code_step.py. Imports run one way: code_step_core, code_step_boundary, code_step_hooks,
code_step_gates, code_step_start, code_step_report, code_step_review, code_step.

A hand-back is one `handback` event in the run's events.jsonl, written by the log hook. A verb that waits for an agent
looks for the newest hand-back event of the awaited agent's id after the time it was dispatched."""
import contextlib
import datetime
import json
import os
import pathlib
import re
import shutil
import signal
import sys
import time

SIBLING_FOLDERS = ("code", "lib", "review", "telemetry")
sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / folder) for folder in SIBLING_FOLDERS]
import plan_format
import script_utils
from script_utils import git_output

CLAUDE_DIR = pathlib.Path(os.environ.get("CODE_STEP_CLAUDE_DIR", pathlib.Path(__file__).resolve().parents[2]))
SCRIPTS_DIR = CLAUDE_DIR / "scripts"
SELF_COMMAND = "python3 " + str(pathlib.Path(__file__).resolve().with_name("code_step.py"))
INSTALLED_COMMAND = "python3 ~/.claude/scripts/code/code_step.py"
EVENT_VERSION = 1
RUNS_DIR_NAME = "runs"
DISPATCH_MARKER = "code-step-dispatch:"
DISPATCH_MARKER_PATTERN = re.compile(re.escape(DISPATCH_MARKER) + r"\s+([^\s/]+)/(d\d+)\b")
PROMPT_DENIAL_LIMIT = 3
FORK_STOP_BLOCK_LIMIT = 2
HANDBACK_WAIT_SECONDS = 570
HANDBACK_POLL_SECONDS = 2
STOP_ROW_WAIT_SECONDS = 15
HANDBACK_TOTAL_WAIT_MULTIPLE = 3
LAUNCH_EXPECTED_SECONDS = 60
BASH_TIMEOUT_MS = 600000
CODER = "coder"
REVIEW_LOOP = "review-loop"
REVIEW_LOOP_SCRIPT = SCRIPTS_DIR / "review" / "review_loop_script.py"
REVIEW_SCRIPT_AGENT_PREFIX = "loop-script-"
FINISHED_REVIEW_SCRIPT_KEYS = ("reviewScriptPid", "resumableReview", "resumeWaitAt")
RESUME_VERB = "resume"
RESUME_LINE = "When the {noun} is fixed, run `python3 ~/.claude/scripts/code/code_step.py {verb}`."
TICKET_ID = re.compile(r"^[A-Za-z]+-\d+$")
SESSION_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]+")
HOOK_STAGES = ("coder", "review", "asks-coder", "plan-coder")
# The stages in which the run owns its session's review-loop hand-backs, so review_fix.py `packet` refuses to read
# their saved hand-back.
REVIEW_HANDBACK_STAGES = ("coder", "review", "asks-coder")
CODER_STAGES = ("coder", "asks-coder")
# The agent the /code skill forks into (its `agent:` line). It has no Edit or Write tool.
FORK_AGENT_TYPE = "code-fork"
SAY_MAX_AGE_SECONDS = 6 * 3600


# ---------- git and state file ----------

def git_names(cwd, *args):
    # Names from a git command that takes -z: a name with a non-ASCII or special character comes back as it is.
    output = git_output(cwd, *args, "-z")
    return [name for name in (output or "").split("\0") if name]


def repo_root_or_exit():
    root = script_utils.repo_root(os.getcwd())
    if root is None:
        sys.exit("code-step: not inside a git repo")
    return root


def state_dir(cwd):
    found = git_output(cwd, "rev-parse", "--path-format=absolute", "--git-path", "code-step")
    if found is None:
        return None
    return pathlib.Path(found)


class StateFileError(Exception):
    pass


def load_state(cwd):
    directory = state_dir(cwd)
    if directory is None:
        return None
    return read_state_file(directory)


def read_state_file(directory):
    state_file = directory / "state.json"
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text())
    except ValueError:
        raise StateFileError(f"{state_file} is not readable JSON") from None


def branch_label(cwd):
    # The branch name for a log row: "-" on a detached HEAD or when git fails.
    return script_utils.current_branch(cwd) or "-"


def save_state(cwd, state):
    directory = state_dir(cwd)
    directory.mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(directory / "state.json", json.dumps(state, indent=1))

    register_session_repo(cwd, state.get("sessionId"))


def session_repos_file(session_id):
    # The list of repos whose /code state a session pinned, or None for an id that is not a plain name. A hook event
    # carries the session's cwd, which is another checkout when /code runs in a worktree, so the hooks read this list.
    if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
        return None
    return pathlib.Path.home() / ".claude" / "state" / "code-step-sessions" / session_id


def session_repo_dirs(session_id):
    # The repos the session pinned that still exist, in the order it pinned them.
    repos_file = session_repos_file(session_id)
    if repos_file is None:
        return []
    try:
        listed = repos_file.read_text().splitlines()
    except OSError:
        return []
    return [repo for repo in listed if repo and pathlib.Path(repo).is_dir()]


def register_session_repo(cwd, session_id):
    repos_file = session_repos_file(session_id)
    if repos_file is None:
        return

    repo = str(pathlib.Path(cwd).resolve())
    if repo in session_repo_dirs(session_id):
        return
    repos_file.parent.mkdir(parents=True, exist_ok=True)
    with repos_file.open("a") as listing:
        listing.write(repo + "\n")


def is_run_open(state):
    return state.get("stage") not in (None, "done")


def holds_open_run(repo, session_id):
    state = load_state(repo)
    return state is not None and is_run_open(state) and state.get("sessionId") == session_id


def session_open_run_repos(session_id):
    return [repo for repo in session_repo_dirs(session_id) if holds_open_run(repo, session_id)]


RULED_ASKS_FILE = "ruled-asks.json"


def ruled_asks_path(cwd):
    return state_dir(cwd) / RULED_ASKS_FILE


def read_ruled_asks(cwd):
    path = ruled_asks_path(cwd)
    if not path.exists():
        return []
    return json.loads(path.read_text())


def record_ruled_asks(cwd, state, outcomes, change_texts):
    # The outcome of every ask the user (or a pre-set outcome) ruled on. It outlives the phase: a later review, plan
    # impact or refactor pass of the same plan reads it so that it does not raise the same ask again.
    ruled = read_ruled_asks(cwd)
    for item, outcome, change_text in zip(state["asks"], outcomes, change_texts, strict=True):
        ruled.append({"plan": state.get("plan"), "phase": state.get("phase"), "file_line": item.get("file_line", ""),
                      "ask": script_utils.joined_distinct([str(item.get("finding") or ""),
                                                           str(item.get("question") or "")]),
                      "outcome": outcome, "change": change_text or ""})
    state_dir(cwd).mkdir(parents=True, exist_ok=True)
    script_utils.write_text_atomically(ruled_asks_path(cwd), json.dumps(ruled, indent=1))


def ruled_asks_lines(cwd, plan):
    # One line per ask already ruled in this plan's run, for a prompt. Empty when none was ruled.
    lines = []
    for ruled in read_ruled_asks(cwd):
        if ruled["plan"] != plan:
            continue
        where = f" ({ruled['file_line']})" if ruled["file_line"] else ""
        change = f" - the user's change: {ruled['change']}" if ruled["change"] else ""
        lines.append(f"{ruled['ask']}{where}: {ruled['outcome']}, Phase {ruled['phase']}{change}")
    return lines


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


def file_hashes(repo_dir):
    tracked = git_names(repo_dir, "diff", "--name-only", "HEAD")
    untracked = git_names(repo_dir, "ls-files", "--others", "--exclude-standard")
    hashes = {}
    for name in sorted(set(tracked + untracked)):
        # A deleted file has no content to hash: its hash is None, which still differs from a baseline that had it.
        hashes[name] = git_output(repo_dir, "hash-object", name) if (repo_dir / name).exists() else None
    return hashes


def load_handback():
    # The shared hand-back reader is imported where it is used. When it is missing the caller reports that and stops.
    try:
        import handback
    except ImportError as error:
        return None, f"handback.py could not be imported ({error}); install it in scripts/review"
    return handback, None


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
    # and hand-backs for it. The open or closed reading is is_dispatch_open's.
    dispatches = [event for event in events if event.get("event") == "dispatch"]
    if not dispatches:
        return {"dispatch": None, "launched": None, "blocks": []}
    current = dispatches[-1]
    of_current = [event for event in events if event.get("dispatch") == current["id"]]
    launches = [event for event in of_current if event.get("event") == "launch"]
    blocks = [event for event in of_current if event.get("event") == "fork-block"]
    return {"dispatch": current, "launched": launches[0] if launches else None, "blocks": blocks}


def newest_dispatch_standing(repo_dir, state):
    if not state.get("runId"):
        return {"dispatch": None, "launched": None, "blocks": []}
    return dispatch_standing(read_events(repo_dir, state["runId"]))


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


def prompt_with_gate_env(repo_dir, state, prompt):
    # The prompt, with the repo's gate env vars appended when it has any.
    gate_env = plan_format.repo_gate_env(repo_dir, state.get("plan"))
    gate_env_text = plan_format.gate_env_text(gate_env)
    if not gate_env_text:
        return prompt
    return f"{prompt.rstrip()}\n\n{gate_env_text}"


def checkout_line(repo_dir):
    # The agent starts in the session's cwd, which is another checkout when /code runs in a worktree or another repo.
    checkout = pathlib.Path(repo_dir).resolve()
    return (f"This run's checkout is {checkout}. Read, edit and run commands only there: use absolute paths under it "
            "and run each Bash command from it. Name this checkout in the prompt of every agent you dispatch.")


def emit_dispatch(repo_dir, state, verb, *lines, prompt, agent, model=None):
    # The one way a dispatch reaches the fork: logged and saved first, then printed with the path of the saved prompt.
    # Every agent it dispatches runs a gate, so the repo's gate env vars go in the prompt.
    prompt_in_checkout = f"{checkout_line(repo_dir)}\n\n{prompt}"
    prompt = prompt_with_gate_env(repo_dir, state, prompt_in_checkout)

    marked_prompt, prompt_file = record_dispatch(repo_dir, state, verb, agent, model, prompt)

    emit("dispatch", *lines, next_after(verb), prompt=marked_prompt, agent=agent, model=model, prompt_file=prompt_file)


def open_dispatch(state):
    # A dispatch is open from here until the dispatched agent's hand-back event is newer than dispatchAt. The session
    # that opens it pins the run: a new session that resumes the run reads the events of the agents it launches.
    state["dispatchAt"] = time.time()
    # A finished review script's pid would read as gone on the next wait; launch_review_script sets it after this.
    state.pop("reviewScriptPid", None)
    state["sessionId"] = session_pin() or state.get("sessionId")
    if not state.get("runId"):
        state["runId"] = script_utils.sortable_unique_id()


def abandon_open_dispatch(repo_dir, previous):
    # A run that starts over leaves no open dispatch behind: the stage becomes stopped and dispatchAt goes. The
    # baseline stays, so a restart of the same phase keeps its own-files record. A review script still running,
    # including one a wait-cap stop left running, is killed; stopping it drops the pid and the resume keys from the
    # saved state.
    abandoned = dict(previous)
    had_review_script = stop_review_script(abandoned) is not None

    if abandoned.get("dispatchAt") is None or abandoned.get("stage") not in HOOK_STAGES:
        if had_review_script:
            save_state(repo_dir, abandoned)
        return

    abandoned.pop("dispatchAt")
    abandoned["stage"] = "stopped"
    save_state(repo_dir, abandoned)


# ---------- hand-back matcher ----------

def is_after(row, since):
    # A row without a numeric timestamp is old.
    return isinstance(row.get("ts"), (int, float)) and row["ts"] > since


def handback_event(events, agent_id, since):
    # The one hand-back record: the newest `handback` event of this agent id after `since`, or None.
    if agent_id is None:
        return None
    matches = [event for event in events
               if event.get("event") == "handback" and event.get("agent_id") == agent_id and is_after(event, since)]
    return max(matches, key=lambda event: event["ts"]) if matches else None


def awaits_resumed_coder(state):
    # The run stopped on a coder's report and the user answered: that coder, resumed with SendMessage, has no dispatch
    # of its own. The verb that finds its hand-back puts the stage back to coder.
    return state.get("stage") == "stopped" and state.get("resumableCoderAt") is not None


def awaits_resumed_review(state):
    # The wait for a review-loop gave up at the cap and stopped the run. The user may resume that review-loop with
    # SendMessage, or keep waiting on a review script that still runs: its hand-back, still after dispatchAt, then
    # counts as the pending review.
    return state.get("stage") == "stopped" and bool(state.get("resumableReview"))


def awaited_agent_id(repo_dir, state):
    # The agent the next verb waits for: the coder resumed after a stop, else the agent the newest dispatch launched
    # (a review-loop resumed with SendMessage keeps that id). None when no launch is logged yet.
    if awaits_resumed_coder(state):
        return state.get("resumableCoderId")
    launched = newest_dispatch_standing(repo_dir, state)["launched"]
    return launched.get("agent_id") if launched else None


def dispatch_since(state):
    # The time the agent that the next verb waits for was dispatched, or None when the state records none. A coder
    # resumed after a stop counts from the stop.
    if state.get("dispatchAt") is not None:
        return state["dispatchAt"]
    if awaits_resumed_coder(state):
        return state["resumableCoderAt"]
    return None


def stop_row_wait_seconds():
    # How long a reader of a review-loop's hand-back waits for the gate's stop row after it. CODE_STEP_WAIT_SECONDS=0
    # skips the wait.
    return min(float(os.environ.get("CODE_STEP_WAIT_SECONDS", HANDBACK_WAIT_SECONDS)), STOP_ROW_WAIT_SECONDS)


def loop_stopped_after(state, handback):
    # A review-loop agent's hand-back counts once the review-loop gate lets the loop stop after it. A stop the gate
    # blocked sends the loop back to work, so only a later stop counts. With no stop row after the stop-row wait, the
    # gate wrote none and the hand-back counts. A coder and a review script stop with no gate.
    is_script = str(handback.get("agent_id")).startswith(REVIEW_SCRIPT_AGENT_PREFIX)
    if expected_agent(state) != REVIEW_LOOP or is_script:
        return True

    module, _import_error = load_handback()
    if module is None:
        return True
    session_id = state.get("sessionId") or session_pin() or ""
    stops = module.stop_rows_after(session_id, handback.get("agent_id"), handback["ts"])
    if any(not row.get("blocked") for row in stops):
        return True
    if stops:
        return False
    return time.time() - handback["ts"] >= stop_row_wait_seconds()


def newest_handback(repo_dir, state):
    # The newest hand-back event of the awaited agent after its dispatch, whether or not the loop stopped after it.
    since = dispatch_since(state)
    if since is None or not state.get("runId"):
        return None
    return handback_event(read_events(repo_dir, state["runId"]), awaited_agent_id(repo_dir, state), since)


def awaited_handback(repo_dir, state):
    # The hand-back event of the awaited agent after its dispatch, or None. A review-loop's hand-back waits for the
    # loop's stop after it.
    handback = newest_handback(repo_dir, state)
    if handback is None or not loop_stopped_after(state, handback):
        return None
    return handback


def take_handback(repo_dir, state, agent_type, missing_text):
    # The hand-back event of the agent the verb waited for, after a resumed agent is put back in its stage; None after
    # printing the stop. A resumed agent that has not handed back yet gets its own stop.
    is_resumed = awaits_resumed_coder(state) or awaits_resumed_review(state)
    handback = awaited_handback(repo_dir, state)
    if handback is None and newest_handback(repo_dir, state) is not None:
        return emit("wait", f"The {agent_type} handed back, but its stop was blocked, so it is still working. Do not "
                    f"dispatch it again. Run {timed_command(RESUME_VERB)} to wait for its next hand-back.")
    if handback is None:
        return emit("stop", resumed_agent_pending_stop(agent_type) if is_resumed else missing_text)

    pin_session(repo_dir, state)
    state.pop("reviewScriptPid", None)
    if awaits_resumed_coder(state):
        put_resumed_coder_back(repo_dir, state)
    elif awaits_resumed_review(state):
        put_resumed_review_back(repo_dir, state)
    return handback


def is_dispatch_open(cwd, state):
    # A dispatch is open from dispatchAt until the awaited agent's hand-back event.
    since = state.get("dispatchAt")
    if since is None or time.time() - since > SAY_MAX_AGE_SECONDS:
        return False
    return awaited_handback(cwd, state) is None


def pin_session(repo_dir, state):
    # A state with no pinned session takes the session of the launch event of its dispatch. The caller saves the state.
    if state.get("sessionId"):
        return
    launched = newest_dispatch_standing(repo_dir, state)["launched"]
    if launched and launched.get("session_id"):
        state["sessionId"] = launched["session_id"]


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


def put_resumed_coder_back(repo_dir, state):
    # A coder resumed after the run stopped on its report is the same coder: its next hand-back goes to review. Its
    # dispatch time is the stop.
    state["stage"] = "coder"
    state["dispatchAt"] = state.pop("resumableCoderAt")
    state.pop("resumableCoderId", None)
    state.pop("resumeWaitAt", None)
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


PLAN_EDIT_OPEN_CHOICE = re.compile(r"^[ \t]*OPEN CHOICE:[ \t]*(\S.*)$", re.MULTILINE)


def plan_edit_open_choices(report):
    # The choices the plan-edit coder left to the user, one per `OPEN CHOICE:` line of its report.
    return [choice.strip() for choice in PLAN_EDIT_OPEN_CHOICE.findall(report or "")]


def phase_coder_reports(repo_dir, state):
    # The agents that coder-stage dispatches launched, one (agent id, stage, messages, attempts) per agent in launch
    # order. The messages of an agent are every hand-back event it logged, oldest first; its attempts are every message
    # it tried to hand back, denied or not. An asks round keeps only the agents of the newest asks-coder dispatch: the
    # asks of an earlier round are ruled already. The phase coder stage keeps every agent.
    if not state.get("runId"):
        return []
    events = read_events(repo_dir, state["runId"])
    dispatch_stages = {event["id"]: event.get("stage") for event in events if event.get("event") == "dispatch"}
    asks_dispatches = [event["id"] for event in events
                       if event.get("event") == "dispatch" and event.get("stage") == "asks-coder"]
    newest_asks_dispatch = asks_dispatches[-1] if asks_dispatches else None
    reports = []
    for launch in (event for event in events if event.get("event") == "launch"):
        stage = dispatch_stages.get(launch.get("dispatch"))
        if stage not in ("coder", "asks-coder") or not launch.get("agent_id"):
            continue
        if stage == "asks-coder" and launch.get("dispatch") != newest_asks_dispatch:
            continue
        of_agent = [event for event in events if event.get("agent_id") == launch["agent_id"]]
        messages = [event.get("message", "") for event in of_agent if event.get("event") == "handback"]
        attempts = [event.get("message", "") for event in of_agent if event.get("event") == "handback-attempt"]
        reports.append({"agent_id": launch["agent_id"], "stage": stage, "messages": messages, "attempts": attempts})
    return reports


def timed_command(verb):
    return f"`{INSTALLED_COMMAND} {verb}` as a Bash call with timeout {BASH_TIMEOUT_MS}"


def next_after(verb):
    return f"NEXT: right after the Agent call, run {timed_command(verb)}."


def expected_agent(state):
    return REVIEW_LOOP if state.get("stage") == "review" or awaits_resumed_review(state) else CODER


def dispatch_time_text(since):
    return datetime.datetime.fromtimestamp(since).isoformat(timespec="seconds")


# ---------- the wait ----------

def unlaunched_dispatch(repo_dir, state, agent_type):
    # The newest dispatch of this run when its Agent call never left: no launch row, and older than the launch grace.
    # Only the dispatch the state is in can be waited for; a resumed agent has a launch row of its own.
    if state.get("stage") not in HOOK_STAGES:
        return None
    standing = newest_dispatch_standing(repo_dir, state)
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


def wait_clock_start(repo_dir, state, since, wait_started):
    # The time the cap counts from. A resumed agent's dispatch time is the stop that came before the user's answer, so
    # the cap counts from the first wait on it. That first wait is saved once; the verb that finds the hand-back
    # clears it. Any other agent counts from the launch of the newest dispatch when one is logged (the dispatch is
    # printed before the Agent call, and the worker may hold it a long time), and never earlier than `since`.
    if not (awaits_resumed_coder(state) or awaits_resumed_review(state)):
        launched = newest_dispatch_standing(repo_dir, state)["launched"]
        launched_at = launched.get("ts") if launched else None
        if isinstance(launched_at, (int, float)):
            return max(since, launched_at)
        return since
    if state.get("resumeWaitAt") is None:
        state["resumeWaitAt"] = wait_started
        save_state(repo_dir, state)
    return state["resumeWaitAt"]


def launch_has_no_agent_id(repo_dir, state):
    # The newest dispatch was launched, but the launch event holds no agent id: no hand-back can be matched to it.
    if awaits_resumed_coder(state):
        return False
    standing = newest_dispatch_standing(repo_dir, state)
    return standing["launched"] is not None and not standing["launched"].get("agent_id")


def runs_review_script():
    # The review loop runs as review_loop_script.py; CODE_STEP_REVIEW_LOOP=agent dispatches the review-loop agent.
    return os.environ.get("CODE_STEP_REVIEW_LOOP", "script") != "agent"


def review_script_running(state):
    pid = state.get("reviewScriptPid")
    if not pid:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def stop_review_script(state):
    # Kills the running review loop script and every claude call it started. The caller saves the state.
    pid = state.pop("reviewScriptPid", None)
    if pid is None:
        return None
    # A killed script leaves nothing to resume.
    for finished_key in FINISHED_REVIEW_SCRIPT_KEYS:
        state.pop(finished_key, None)
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pid, signal.SIGTERM)
    return pid


def handback_or_unlaunched(repo_dir, state, agent_type, cap_spent):
    if awaited_handback(repo_dir, state):
        return "handback", None
    if state.get("reviewScriptPid") and not review_script_running(state):
        # The script writes its hand-back, then exits: a hand-back that landed after the first read still counts.
        return ("handback", None) if awaited_handback(repo_dir, state) else ("script-gone", None)
    if launch_has_no_agent_id(repo_dir, state):
        return "no-agent-id", None
    if cap_spent:
        # The cap is spent: the cap stop comes next, not another print of the dispatch.
        return None
    dispatch = unlaunched_dispatch(repo_dir, state, agent_type)
    return ("unlaunched", dispatch) if dispatch else None


def wait_for_handback(repo_dir, state, verb):
    # Nested Agent calls return at once, so the verb that follows a dispatch waits here for the hand-back event.
    # CODE_STEP_WAIT_SECONDS=0 skips the wait. Returns False after emitting the line that says to run the verb again,
    # or a stop once the dispatch is older than HANDBACK_TOTAL_WAIT_MULTIPLE waits.
    limit = float(os.environ.get("CODE_STEP_WAIT_SECONDS", HANDBACK_WAIT_SECONDS))
    since = dispatch_since(state)
    if limit <= 0 or since is None:
        return True

    interval = float(os.environ.get("CODE_STEP_POLL_SECONDS", HANDBACK_POLL_SECONDS))
    agent_type = expected_agent(state)
    total_cap = limit * float(os.environ.get("CODE_STEP_WAIT_MULTIPLE", HANDBACK_TOTAL_WAIT_MULTIPLE))
    wait_started = time.time()
    clock_start = wait_clock_start(repo_dir, state, since, wait_started)
    # The wait ends at the cap, not at the end of the wait that passes it.
    until_cap = max(0.0, clock_start + total_cap - wait_started)

    found = script_utils.wait_for(lambda: handback_or_unlaunched(repo_dir, state, agent_type, until_cap <= 0),
                                  min(limit, until_cap), interval)
    if found and found[0] == "unlaunched":
        emit_unlaunched_dispatch(found[1])
        return False
    if found and found[0] == "no-agent-id":
        return stop_on_launch_without_agent_id(repo_dir, state, agent_type)
    if found and found[0] == "script-gone":
        return stop_on_gone_review_script(repo_dir, state)
    if found:
        return True
    if until_cap <= limit:
        stop_at_wait_cap(repo_dir, state, agent_type, clock_start, total_cap)
        return False

    emit("wait", f"The dispatched agent has not handed back after {limit:g} seconds. Do not dispatch it again and do "
         f"not hand back. To keep waiting, run the same command again: `{INSTALLED_COMMAND} {verb}` (Bash timeout "
         f"{BASH_TIMEOUT_MS}).")
    return False


def wait_for_loop_stop(state, module, handback):
    # The review-loop's hand-back row reaches the shared store before the stop row of the same loop, and a stop that
    # the review gate blocked is followed by more ledger rows. A reader of the stop row's ask rows waits, on the
    # hand-back poll, for a stop the gate let through at or after the hand-back. CODE_STEP_WAIT_SECONDS=0 skips the
    # wait. On a timeout it says so on stderr and the reader goes on without the row.
    limit = stop_row_wait_seconds()
    if limit <= 0:
        return

    interval = float(os.environ.get("CODE_STEP_POLL_SECONDS", HANDBACK_POLL_SECONDS))
    session_id = state.get("sessionId") or session_pin() or ""
    agent_id = handback.get("agent_id")
    settled = script_utils.wait_for(lambda: module.settled_stop_row(session_id, agent_id, handback["ts"]),
                                    limit, interval)
    if settled is None:
        print(f"code-step: no settled stop row from the review-loop within {limit:g} seconds: its logged ask rows "
              "may be missed, so an ask it logged may get a second ask row.", file=sys.stderr)


def stop_on_gone_review_script(repo_dir, state):
    log_path = state.get("reviewScriptLog", "")
    # A wait-cap stop before this one left the review resumable; a gone script has nothing left to resume.
    for finished_key in FINISHED_REVIEW_SCRIPT_KEYS:
        state.pop(finished_key, None)
    state.update({"stage": "stopped", "stopReason": "invalid-packet"})
    save_state(repo_dir, state)
    emit("stop", f"The review loop script exited with no hand-back. Show the user its log: {log_path}",
         "To review the same diff again, invoke Skill code with `review-again`.")
    return False


def stop_on_launch_without_agent_id(repo_dir, state, agent_type):
    # A review-loop goes on to its own no-launch-record stop. A coder stops here, with the restart text.
    if agent_type == REVIEW_LOOP:
        return True

    resume_text = stop_a_silent_coder(repo_dir, state, time.time())
    state["stage"] = "stopped"
    state.pop("resumeWaitAt", None)
    save_state(repo_dir, state)
    stop_with_question(
        repo_dir, f"the {agent_type} was launched, but the launch has no agent id, so its hand-back cannot be matched.",
        [], resume_text.strip(),
        f"The {agent_type} was launched, but the launch has no agent id, so its hand-back cannot be "
        "matched. Do not dispatch it again and do not wait. Tell the user." + resume_text)
    return False


def stop_at_wait_cap(repo_dir, state, agent_type, clock_start, total_cap):
    stopped_at = time.time()
    state.pop("stopReason", None)
    if agent_type == REVIEW_LOOP and state.get("reviewScriptPid"):
        state["resumableReview"] = stopped_at
        resume_text = (f" The review loop runs as a script; its log is {state.get('reviewScriptLog', '')}. If the user "
                       f"wants it to keep waiting, run {timed_command(RESUME_VERB)}. If the user wants it killed and a "
                       f"new loop started on the same diff, run `{INSTALLED_COMMAND} review-again`.")
    elif agent_type == REVIEW_LOOP:
        state["resumableReview"] = stopped_at
        resume_text = (f" If the user resumes it with SendMessage, run {timed_command(RESUME_VERB)}. If it died, "
                       f"the user's word to review the same diff again runs `{INSTALLED_COMMAND} review-again`.")
    else:
        resume_text = stop_a_silent_coder(repo_dir, state, stopped_at)
    state["stage"] = "stopped"
    # The cap is spent: a wait after the user resumes the agent again counts from its own first wait.
    state.pop("resumeWaitAt", None)
    save_state(repo_dir, state)
    silent_text = (f"The {agent_type} has not handed back in {stopped_at - clock_start:.0f} seconds, counted from "
                   f"{dispatch_time_text(clock_start)} (the cap is {total_cap:g}). It may have died or been stopped.")
    stop_with_question(repo_dir, silent_text, [], resume_text.strip(),
                       silent_text + " Do not dispatch it again and do not wait longer. Tell the user." + resume_text)


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
    # is resumed this way: a resumed coder goes back to the coder stage, so a plan-edit coder, and a launch with no
    # agent id, leave only a restart.
    restart_command = script_command("start --restart")
    restart_instruction_text = restart_instruction(state, restart_command)
    if state.get("stage") == "plan-coder":
        state["stopReason"] = "coder-cap"
        return (" The plan-edit coder cannot be resumed: only the phase coder can. To dispatch the phase coder "
                f"again, {restart_instruction_text}.")

    agent_id = awaited_agent_id(repo_dir, state)
    if not agent_id:
        state["stopReason"] = "coder-cap"
        return (f" Its launch has no agent id, so it cannot be resumed: {restart_instruction_text} "
                "to dispatch a new one.")

    state["resumableCoderAt"] = stopped_at
    state["resumableCoderId"] = agent_id
    state.pop("dispatchAt", None)
    return (f" If the user resumes coder {agent_id} with SendMessage, run {timed_command(RESUME_VERB)}. To dispatch a "
            f"new coder instead, {restart_instruction_text}.")


# ---------- output ----------

def own_path(text):
    # Printed commands name code_step.py by its real path, so they work from a bench copy as well as from
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


def clear_say(repo_dir):
    directory = state_dir(repo_dir)
    if directory is not None and say_file_in(directory).exists():
        say_file_in(directory).write_text("")


def question_file_in(directory):
    # question.md sits beside say.md. The Stop say-hook empties say.md, never question.md.
    return directory / "question.md"


def question_file(repo_dir):
    # The real path of question.md for this repo.
    directory = state_dir(repo_dir)
    return question_file_in(directory) if directory is not None else pathlib.Path("question.md")


def clear_question(repo_dir):
    # Every verb run answers or replaces the last question.
    directory = state_dir(repo_dir)
    if directory is not None and question_file_in(directory).exists():
        question_file_in(directory).write_text("")


def write_question(repo_dir, question_lines):
    directory = state_dir(repo_dir)
    if directory is None:
        return
    directory.mkdir(parents=True, exist_ok=True)
    question_file_in(directory).write_text(own_path("\n".join(question_lines)).rstrip() + "\n")


def ask_user(repo_dir, instruction, *question_lines):
    # The /code subagent cannot ask the user: the question goes in question.md for the main session to ask.
    write_question(repo_dir, ["## Question for the user", "", "Main session: " + instruction, "", *question_lines])
    emit("ask-user", f"The question for the user is in {question_file(repo_dir)}. Hand back.")


def stop_with_question(repo_dir, why, items, next_step, *stop_lines):
    # A stop on an agent's report or silence: question.md names why the run stopped, each open item on one line and
    # the command that goes on, so the hand-back never rests on free text alone.
    item_lines = [f"- {script_utils.one_line(item, 300)}" for item in items] or ["- (none reported)"]
    write_question(repo_dir, ["## The run stopped", "", "Main session: tell the user why the run stopped and what "
                              "waits on them.", "", "Why: " + why, "", "Open items:", *item_lines, "",
                              "Next: " + next_step])
    emit("stop", *stop_lines)


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
        print_prompt(prompt)
    if agent:
        print_tail_reminder(header_lines, lines)


def print_prompt(prompt):
    print("PROMPT (pass it verbatim, add and remove nothing):")
    print("-----BEGIN PROMPT-----")
    print(own_path(prompt))
    print("-----END PROMPT-----")


def print_tail_reminder(header_lines, lines):
    # A reader that keeps only the tail of a long output still sees what to do.
    for header_line in header_lines:
        print(header_line)
    for line in lines:
        if line.startswith("NEXT:"):
            print(line)


def script_command(verb_words):
    return f"{INSTALLED_COMMAND} {verb_words}".rstrip()


def refuse(reason, *commands, notes=()):
    # The one shape of a refusal: `Refused: <reason>` first. One command to run instead prints `ACTION: rerun` with it;
    # a choice between commands prints `ACTION: stop` and lists them. Nothing was changed.
    print("Refused: " + own_path(reason))
    if len(commands) == 1:
        return emit("rerun", "COMMAND: " + commands[0], *notes)
    command_lines = [f"- `{command}`" for command in commands]
    choices = ["Run one of these on the user's word:", *command_lines]
    return emit("stop", *choices, *notes)

