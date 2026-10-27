"""Termination test for code_step.py: drive the script the way the /code subagent does and check every run ends.

The explorer starts from each entry verb. For every ACTION the script prints it feeds each outcome the script accepts
(fake agent reports written into the files the script reads; Claude never runs), then calls the next verb. It walks
the tree breadth-first. One segment is the run between two hand-backs to the user. A segment passes when it reaches a
stop or an ask-user. It fails when it calls the same verb on the same saved state after the same agent outcome twice,
when it passes STEP_LIMIT calls, or when a call crashes or prints no ACTION.

Identical configurations reached by different paths are explored once. The verdict of a shared tail covers every path
that reaches it. A hand-back starts a new segment: the user's answer (decide, asks-done, resume, start) is one
more entry verb, so loops that only close through a user answer are not counted as stuck.

A hand-back must also leave the user a way out. Every command a hand-back names (in its output, or in the say.md and
question.md it points to) is run on a copy of the repo, and none may be refused.
"""
import atexit
import collections
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from unittest import mock

import toolkit_paths

HERE = pathlib.Path(__file__).parent
REPO_SCRIPT = HERE.parent.parent / "claude" / ".claude" / "scripts" / "code" / "code_step.py"
SCRIPT = pathlib.Path(os.environ["CODE_STEP_SCRIPT"]) if os.environ.get("CODE_STEP_SCRIPT") else \
    HERE / "code_step.py" if (HERE / "code_step.py").exists() else REPO_SCRIPT
REAL_CLAUDE = SCRIPT.parent.parent.parent if (SCRIPT.parent / "coder_gate.py").exists() else toolkit_paths.CLAUDE_DIR
SCRIPTS_ROOT = SCRIPT.parent.parent
HANDBACK_SCRIPT = pathlib.Path(os.environ.get("HANDBACK_SCRIPT") or REAL_CLAUDE / "scripts" / "review" / "handback.py")
sys.path.insert(0, str(HANDBACK_SCRIPT.parent))
sys.path.insert(0, str(SCRIPT.parent))
import functools
import operator

import handback
import script_utils  # noqa: F401  (loaded before handback, so handback and code-step share the script directory's copy)

STEP_LIMIT = 30
MAX_HANDBACKS = 3
NODE_BUDGET = 5000
# The plan-edit coder is reached only through an adopted plan change, deep in the tree. A second, small exploration
# over those entries alone makes sure the plan-edit wait is covered whatever the other entries spend of the budget.
PLAN_EDIT_NODE_BUDGET = 1500
HAND_BACK_ACTIONS = ("ask-user", "stop", "rerun", "judgment", "stop-block-B", "stop-block-C")
# The verbs a hand-back may name for the user to run.
NAMEABLE_VERBS = ("start", "resume", "decide", "asks-done", "skill-done", "review-again", "tick", "verify",
                  "after-coder", "after-review", "after-plan-edit")
BACKTICKED_TEXT = re.compile(r"`([^`\n]+)`")

TMP_ROOT = pathlib.Path(tempfile.mkdtemp(prefix="termination-"))
CLAUDE_STUB = TMP_ROOT / "claude"
(CLAUDE_STUB / "scripts").mkdir(parents=True)
(CLAUDE_STUB / "skills/review").mkdir(parents=True)
for script_name in ("coder_gate.py", "coder_packet.py", "plan_format.py", "script_utils.py", "resolve-task-dir.sh",
                    *toolkit_paths.CODE_STEP_MODULES, "shell_command.py", "makefile_text.py", "test_run_output.py"):
    try:
        source_file = toolkit_paths.script_in(SCRIPTS_ROOT, script_name)
    except FileNotFoundError:
        source_file = toolkit_paths.script_in(toolkit_paths.SCRIPTS_DIR, script_name)
    staged_file = CLAUDE_STUB / "scripts" / source_file.parent.name / script_name
    staged_file.parent.mkdir(exist_ok=True)
    shutil.copy(source_file, staged_file)
(CLAUDE_STUB / "scripts" / "telemetry").mkdir(exist_ok=True)
for stub_name in ("scripts/telemetry/log-scan", "skills/review/log-review-finding"):
    stub_file = CLAUDE_STUB / stub_name
    stub_file.write_text("#!/usr/bin/env bash\nexit 0\n")
    stub_file.chmod(0o755)
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "CODE_STEP_CLAUDE_DIR": str(CLAUDE_STUB), "CODE_STEP_WAIT_SECONDS": "0", "HOME": str(TMP_ROOT / "home"),
           "CODE_STEP_REVIEW_LOOP": "agent",
           "CLAUDE_CODE_SESSION_ID": "sess-termination", "CODE_STEP_NVIM_JUMP": "true",
           # The explorer makes no Agent calls and takes minutes: no dispatch may age into the launch grace period.
           "CODE_STEP_LAUNCH_SECONDS": "1000000"}
NO_ROW_YET_PRESETS = {"CODE_STEP_WAIT_SECONDS": "0.2", "CODE_STEP_POLL_SECONDS": "0.05"}

# code_step.py reads CODE_STEP_CLAUDE_DIR once, at import. Set it only while the module loads, so the real log
# scripts and the live ~/.claude files are never reached and other test modules keep their environment.
atexit.register(shutil.rmtree, TMP_ROOT, ignore_errors=True)
module_spec = importlib.util.spec_from_file_location("code_step_under_test", SCRIPT)
code_step = importlib.util.module_from_spec(module_spec)
with mock.patch.dict(os.environ, {"CODE_STEP_CLAUDE_DIR": str(CLAUDE_STUB)}):
    module_spec.loader.exec_module(code_step)
import code_step_core

PLAN_DIR = "docs/plans/ORD-1-orders"
PLAN_A = f"{PLAN_DIR}/spec.md"
VERIFY_LINE = '- [ ] **Check**: flag - `bash -c "test -f verify.flag"`'
PLAN_A_TEXT = f"""# Orders Plan

## Overview

Add orders.

## Phase Status

- [ ] Phase 1: Walking skeleton (risk: low)
- [ ] Phase 2: Totals (risk: low)
- [ ] Phase 3: Verify pass (risk: low)

## Acceptance Criteria

- **Criteria file**: `{PLAN_DIR}/acceptance-criteria.md`

## Phase 1: Walking skeleton

**File**: `backend/src/orders.ts`
**File**: `backend/src/orders.test.ts`

#### Automated Verification:

{VERIFY_LINE}

#### Manual Verification:

- [ ] **Manual-verified** (agent-verified): hit /orders

## Phase 2: Totals

**File**: `backend/src/totals.ts`

#### Automated Verification:

{VERIFY_LINE}

## Phase 3: Verify pass

Check every criterion.

## References

- none
"""
PLAN_NO_PHASE_STATUS = "# P\n\n## Overview\n\nx\n\n## Phase 1: One\n\nDo it.\n"
PLAN_NO_CRITERIA = (
    "# P\n\n## Acceptance Criteria\n\n- c\n\n## Phase Status\n\n- [ ] Phase 1: One (risk: low)\n\n## "
    "Phase 1: One\n\nx\n"
)
PLAN_SINGLE = "# Single\n\n## Overview\n\nDo `backend/src/single.ts`.\n"

PLAN_EDIT_PLANS = {"docs/other/single.md": PLAN_SINGLE, "docs/other/no-status.md": PLAN_NO_PHASE_STATUS,
                   "docs/other/no-criteria.md": PLAN_NO_CRITERIA}

# ---------- fake agent outcomes ----------

ASK_ONE = (
    '{"finding": "f", "file_line": "backend/src/orders.ts:2", "question": "keep?", "gate": "code-reviewer", '
    '"class": "correctness"}'
)
ASK_TWO = (
    '{"finding": "g", "file_line": "backend/src/orders.ts:3", "question": "drop?", "gate": "code-reviewer", '
    '"class": "other"}'
)
REVIEW_OUTCOMES = {
    "converged-clean": "status: converged\niter: 1\nfixed: []\nask: []\nnit: []",
    "converged-fixed": 'status: converged\niter: 2\nfixed:\n- {finding: "x", file_line: "backend/src/orders.ts:1", '
                       'blocker: false}\nask: []',
    "converged-ask1": f"status: converged\niter: 1\nfixed: []\nask: [{ASK_ONE}]",
    "converged-ask2": f"status: converged\niter: 1\nfixed: []\nask: [{ASK_ONE}, {ASK_TWO}]",
    "deferred-ask": f'status: deferred\niter: 1\nfindings_remaining:\n- {{finding: "d", file_line: "a.ts:2"}}\nask: '
                    f'[{ASK_ONE}]',
    "critical-blocker": 'status: critical-blocker\niter: 1\nblockers:\n- {finding: "b", file_line: "a.ts:1"}',
    "cap-reached": 'status: cap-reached\niter: 3\nfindings_remaining:\n- {finding: "r", file_line: "a.ts:1"}',
    "plan-impact": "status: plan-impact\niter: 1\nplan_impact: |\n  assumed: a\n  changes: b",
    "plan-impact-no-description": "status: plan-impact\niter: 1",
    "no-status": "iter: 1\nfixed: []",
    "empty-message": "",
    "missing-report": None,
}
PLAN_IMPACT_BLOCK = "PLAN-IMPACT:\n  assumed: the plan says A\n  changes: the code does B"
CODER_REPORT = "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters\nREVIEW: recommended"
# name: (files written, flag written, gate result or None for untouched, report text or None for no report row)
CODER_OUTCOMES = {
    "green": (["src"], True, "pass", CODER_REPORT),
    "green-verify-fails": (["src"], False, "pass", CODER_REPORT),
    "red-gate-cap": (["src"], True, "cap", CODER_REPORT),
    "no-change": ([], False, "pass", CODER_REPORT),
    "recommends-eng-spec": (["src"], True, "pass", CODER_REPORT + "\nRecommend /eng-spec."),
    "plan-impact": (["src"], True, "pass", CODER_REPORT + "\n" + PLAN_IMPACT_BLOCK),
    "open-question": (["src"], True, "pass", CODER_REPORT + "\nOpen question: who owns the rounding rule?"),
    "missing-report": (["src"], True, "pass", None),
    "malformed-report": (["src"], True, "pass", "\x00```\nWHY: \nBEHAVIOR:"),
}
PLAN_EDIT_OUTCOMES = ("plan-edited", "plan-edited-and-stray-file", "plan-not-edited")


def write_text(repo, relative_path, text):
    target = repo / relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def apply_coder_outcome(repo, name, unique_text):
    files, flag, gate_result, report = CODER_OUTCOMES[name]
    if "src" in files:
        write_text(repo, "backend/src/orders.ts", f"export const o = '{unique_text}'\n")
    if flag:
        write_text(repo, "verify.flag", "ok\n")
    gate_path = repo / ".git/coder-gate.json"
    if gate_path.exists():
        gate = json.loads(gate_path.read_text())
        if gate_result == "never":
            gate["coders"] = {}
        elif gate_result == "cap":
            gate["coders"] = {
                "a1": {"runs": 4, "denies": 3, "failed": gate["commands"][:1], "skipped": [], "result": "cap"}
            }
        else:
            gate["coders"] = {"a1": {"runs": 1, "denies": 0, "failed": [], "skipped": [], "result": "pass"}}
        gate_path.write_text(json.dumps(gate))
    return report


SESSION = GIT_ENV["CLAUDE_CODE_SESSION_ID"]
REVIEW_AGENT_ID = "a1"


def launch_the_pending_dispatch(repo):
    # A hand-back counts only from the agent the pending dispatch launched. Log that launch, as the log hook does after
    # the Agent call. A dispatch that is already launched keeps its launch.
    run_id = load_saved_state(repo).get("runId")
    if not run_id:
        return

    events = code_step_core.read_events(repo, run_id)
    dispatches = [event for event in events if event["event"] == "dispatch"]
    if not dispatches:
        return

    dispatch_id = dispatches[-1]["id"]
    if any(event["event"] == "launch" and event.get("dispatch") == dispatch_id for event in events):
        return

    code_step_core.log_event(repo, run_id, "launch", SESSION, agent_id=REVIEW_AGENT_ID, dispatch=dispatch_id)


def send_message_to(agent_id):
    # The setup for a user answer that reached the agent with SendMessage: the log hook records it as a resume.
    def setup(repo):
        run_id = load_saved_state(repo).get("runId")
        code_step_core.log_event(repo, run_id, "resume", SESSION, agent_id=agent_id)

    return setup


def store_review_loop_report(repo, message, agent_id="a1"):
    # The shared hand-back store records a review-loop dispatch and its hand-back. A packet that does not parse is
    # refused once and recorded when the agent hands back again, as the real hook does.
    event = {"session_id": GIT_ENV["CLAUDE_CODE_SESSION_ID"], "agent_type": "review-loop", "agent_id": agent_id,
             "tool_input": {"message": message}}
    with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(repo / ".git/handback-store")}):
        handback.handle_hook({**event, "tool_input": {"subagent_type": "review-loop"}}, "dispatch")
        for _ in range(2):
            handback.handle_hook(event, "handback")


def save_report(repo, agent_type, message, agent_id="a1"):
    # The log hook records a hand-back that went through; the dispatch it answers is launched first.
    if agent_type == "review-loop":
        store_review_loop_report(repo, message, agent_id)
    launch_the_pending_dispatch(repo)
    run_id = load_saved_state(repo).get("runId")
    code_step_core.log_event(repo, run_id, "handback", SESSION, agent_id=agent_id, agent_type=agent_type,
                             message=message)


def date_dispatch_now_and_launch(repo):
    state_file = repo / ".git/code-step/state.json"
    saved = json.loads(state_file.read_text())
    saved["dispatchAt"] = time.time()
    state_file.write_text(json.dumps(saved, indent=1))
    launch_the_pending_dispatch(repo)


def apply_plan_edit_outcome(repo, name, plan_path):
    if name == "plan-not-edited":
        return
    plan_file = repo / plan_path
    plan_file.write_text(plan_file.read_text().replace("Add orders.", "Add orders, with the adopted change."))
    if name == "plan-edited-and-stray-file":
        write_text(repo, "backend/src/stray.ts", "export const s = 1\n")


# ---------- repo and script calls ----------

def build_template():
    template = TMP_ROOT / "template"
    template.mkdir()
    subprocess.run(
        ["git", "init", "-q", "-b", "ORD-1-work", "--template="], cwd=template, check=True, capture_output=True
    )
    # A commit starts a detached git maintenance run. Its lock file vanishes while copytree copies the template.
    for setting in (["maintenance.auto", "false"], ["gc.auto", "0"]):
        subprocess.run(["git", "config", *setting], cwd=template, check=True, capture_output=True)

    write_text(
        template,
        "backend/package.json",
        json.dumps(
            {
                "scripts": {"typecheck": "tsc --noEmit", "lint": "eslint ."},
                "devDependencies": {"vitest": "1", "eslint": "9"},
            }
        ),
    )
    write_text(template, "backend/src/existing.ts", "export const a = 1\n")
    write_text(template, PLAN_A, PLAN_A_TEXT)
    write_text(template, f"{PLAN_DIR}/acceptance-criteria.md", "AC-1 orders exist\n")
    for path, text in PLAN_EDIT_PLANS.items():
        write_text(template, path, text)
    for command in (["git", "add", "-A"], ["git", "commit", "-qm", "base"]):
        subprocess.run(command, cwd=template, check=True, capture_output=True, env={**os.environ, **GIT_ENV})
    return template


def call_script(repo, presets, argv):
    # Run one verb in-process. Returns (stdout, crashTraceback or None).
    script_env = {name: value for name, value in os.environ.items()
                 if name not in ("CODE_STEP_IMPACT_DECISION", "CODE_STEP_ASKS_OUTCOME")}
    script_env.update(GIT_ENV)
    script_env["HANDBACK_STORE_DIR"] = str(repo / ".git/handback-store")
    script_env.update(presets)
    previous_directory = os.getcwd()
    previous_argv = sys.argv
    os.chdir(repo)
    sys.argv = ["code_step.py", *argv]
    captured = io.StringIO()
    crash = None
    try:
        with mock.patch.dict(os.environ, script_env, clear=True), \
                contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            try:
                code_step.main()
            except SystemExit as stopped:
                captured.write(f"[exit: {stopped.code}]\n")
    except Exception:
        crash = traceback.format_exc()
    finally:
        os.chdir(previous_directory)
        sys.argv = previous_argv
    return captured.getvalue(), crash


def parse_action(output):
    action = agent = None
    for line in output.splitlines():
        if line.startswith("ACTION: "):
            action = line[len("ACTION: "):].strip()
        elif line.startswith("AGENT: "):
            agent = line[len("AGENT: "):].strip()
    return action, agent


def load_saved_state(repo):
    state_file = repo / ".git/code-step/state.json"
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text())
    except ValueError:
        return {"unreadable": True}


def plan_progress(repo):
    # Which phases are checked, so finishing a phase counts as progress and not as a repeat.
    progress = []
    for plan_file in sorted((repo / "docs").rglob("*.md")):
        progress.append(
            plan_file.name
            + ":"
            + "".join("x" if line.startswith("- [x]") else "" for line in plan_file.read_text().splitlines())
        )
    return "|".join(progress)


IGNORED_STATE_KEYS = (
    "startedAt",
    "baseline",
    "planEditBaseline",
    "asksBaseline",
    "sessionId",
    "dispatchAt",
)


MINUTE_STAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")


def state_signature(repo):
    # The script stamps each ruling with the wall-clock minute. Two visits to one state a minute apart must still
    # compare equal, or whether a loop is caught depends on when the run happens to cross a minute.
    state = {key: value for key, value in load_saved_state(repo).items() if key not in IGNORED_STATE_KEYS}
    state_text = MINUTE_STAMP.sub("<minute>", json.dumps(state, sort_keys=True))
    return state_text + "#" + plan_progress(repo)


# ---------- the explorer ----------

class Node:
    def __init__(self, repo, presets, action, agent, history, steps_in_segment, seen_in_segment, handbacks,
                 ancestors_in_segment=frozenset(), ancestor_answers=None, answer_count=0, hand_back_commands=()):
        self.hand_back_commands = hand_back_commands
        self.ancestors_in_segment = ancestors_in_segment
        self.ancestor_answers = ancestor_answers or {}
        self.answer_count = answer_count
        self.repo = repo
        self.presets = presets
        self.action = action
        self.agent = agent
        self.history = history
        self.steps_in_segment = steps_in_segment
        self.seen_in_segment = seen_in_segment
        self.handbacks = handbacks


class Failure:
    def __init__(self, kind, history, detail, cycle):
        self.kind = kind
        self.history = history
        self.detail = detail
        self.cycle = cycle


def user_answers(repo):
    # What the user can say after a hand-back: each is one more entry verb into a new run.
    state = load_saved_state(repo)
    stage = state.get("stage")
    reason = state.get("stopReason")
    is_stopped = stage == "stopped"
    answers = [
        ("resume", ["resume"], None),
        ("start", ["start"], None),
        ("start --restart", ["start", "--restart"], None),
        ("start after-review", ["start", "after-review"], None),
    ]
    if stage in ("impact-coder", "impact-review"):
        ruling = ["--by", "user", "--ruling", "the user's words"]
        session_ruling = ["--by", "session", "--ruling", "the session's words"]
        answers += [
            ("decide adopt", ["decide", "adopt", *ruling], None),
            ("decide keep", ["decide", "keep", *ruling], None),
            ("decide adopt by session", ["decide", "adopt", *session_ruling], None),
            ("decide keep by session", ["decide", "keep", *session_ruling], None),
            ("decide keep without --by", ["decide", "keep", "--ruling", "the user's words"], None),
            ("decide keep without a ruling", ["decide", "keep"], None),
            ("decide discuss", ["decide", "discuss"], None),
            ("decide bogus", ["decide", "maybe"], None),
        ]
    if stage == "asks":
        count = len(state.get("asks", []))
        answers += [
            ("asks-done all accepted", ["asks-done"] + ["accepted"] * count, None),
            ("asks-done all rejected", ["asks-done"] + ["rejected"] * count, None),
            (
                "asks-done all modified",
                ["asks-done", *functools.reduce(operator.iadd, [["modified", "--change", "use X"]] * count, [])],
                None,
            ),
        ]
    if stage == "skill":
        answers += [
            ("skill-done pass", ["skill-done", "pass"], None),
            ("skill-done fail", ["skill-done", "fail"], None),
        ]
    if is_stopped and reason == "invalid-packet":
        answers += [("review-again", ["review-again"], None)]
    if is_stopped and code_step.awaits_resumed_review(state):
        answers += [("review-again", ["review-again"], None),
                    ("resume after SendMessage to the review-loop", ["resume"], send_message_to(REVIEW_AGENT_ID))]
    if is_stopped and code_step.awaits_resumed_coder(state):
        answers += [("resume after SendMessage to the coder", ["resume"], send_message_to(state["resumableCoderId"]))]
    if is_stopped and reason in ("verification", "plan-format"):
        answers += [("verify (still failing)", ["verify"], None),
                    ("verify (fixed)", ["verify"], lambda repo: write_text(repo, "verify.flag", "ok\n"))]
    return answers


def verb_words(quoted_text):
    # "python3 <path>/code_step.py start --restart" and "start --restart" both give ["start", "--restart"]. Text that is
    # not a script verb, or that holds a placeholder the user fills in, gives None.
    words = quoted_text.replace("COMMAND: ", "").split("code_step.py ", 1)[-1].strip()
    if "<" in words or words.split(" ", 1)[0] not in NAMEABLE_VERBS:
        return None

    try:
        return shlex.split(words)
    except ValueError:
        return None


def named_commands(text):
    # Every script command the text tells the reader to run: inside backticks, or on a COMMAND: line.
    candidates = BACKTICKED_TEXT.findall(text)
    candidates += [line for line in text.splitlines() if line.startswith("COMMAND: ")]
    commands = []
    for candidate in candidates:
        argv = verb_words(candidate)
        if argv and argv not in commands:
            commands.append(argv)
    return commands


def saved_say_text(repo):
    # say.md, then question.md: the two files a hand-back points to.
    state_folder = repo / ".git/code-step"
    saved_files = [state_folder / "say.md", state_folder / "question.md"]
    return "".join(saved_file.read_text() for saved_file in saved_files if saved_file.exists())


def commit_everything(repo):
    for command in (["git", "add", "-A"], ["git", "commit", "-qm", "phase"]):
        subprocess.run(command, cwd=repo, check=True, capture_output=True, env={**os.environ, **GIT_ENV})


def children_of(node):
    # Each child: (label, setup function on the copied repo, argv for the next verb, presets).
    state = load_saved_state(node.repo)
    stage = state.get("stage")
    children = []
    waiting_on = None
    is_plan_edit = stage == "plan-coder" and node.action in ("dispatch", "wait")
    if node.action == "wait" and not is_plan_edit:
        waiting_on = "coder" if stage in ("coder", "asks-coder") else "review-loop"
    if node.action == "dispatch" and node.agent in ("coder", "review-loop"):
        # The agent has not handed back when the verb that follows the dispatch runs: the verb says to run it again.
        # A plan-edit dispatch is older than the wait cap by now: date it again so the wait itself is tried.
        setup = date_dispatch_now_and_launch if is_plan_edit else launch_the_pending_dispatch
        children.append(("[no report yet]", setup, ["resume"], NO_ROW_YET_PRESETS))
        if node.agent == "review-loop":
            children.append(("[no report yet, launch not logged]", lambda repo: None, ["resume"], NO_ROW_YET_PRESETS))
    if is_plan_edit:
        for name in PLAN_EDIT_OUTCOMES:
            def setup(repo, name=name):
                apply_plan_edit_outcome(repo, name, state["plan"])
                save_report(repo, "coder", "plan edited")
            children.append((f"[plan-edit coder: {name}]", setup, ["resume"]))
    elif waiting_on == "coder" or (node.action == "dispatch" and node.agent == "coder"):
        for name in CODER_OUTCOMES:
            def setup(repo, name=name):
                report = apply_coder_outcome(repo, name, f"v{len(node.history)}")
                if report is not None:
                    save_report(repo, "coder", report)
            children.append((f"[coder: {name}]", setup, ["resume"]))
    elif waiting_on == "review-loop" or (node.action == "dispatch" and node.agent == "review-loop"):
        is_answered = state.get("planImpact", "none") != "none"
        for name, message in REVIEW_OUTCOMES.items():
            # A reviewer re-raises an answered question unless the dispatch tells it the question is resolved.
            if name.startswith("plan-impact") and is_answered and "RESOLVED" in state.get("lastReviewPrompt", ""):
                continue
            def setup(repo, message=message):
                launch_the_pending_dispatch(repo)
                if message is not None:
                    save_report(repo, "review-loop", message)
            children.append((f"[review-loop: {name}]", setup, ["resume"]))
        if node.action == "dispatch":
            def setup_other_agent(repo):
                launch_the_pending_dispatch(repo)
                save_report(repo, "review-loop", REVIEW_OUTCOMES["converged-clean"], agent_id="other-agent")
            children.append(("[review-loop: converged-clean from another agent]", setup_other_agent, ["resume"],
                             NO_ROW_YET_PRESETS))
    elif node.action in ("invoke-skill", "dispatch"):
        for verdict in ("pass", "fail", "bogus"):
            children.append((f"[skill result: {verdict}]", lambda repo: None, ["skill-done", verdict]))
    elif node.action == "auto-advance":
        children.append(("[auto-advance, commit not run]", lambda repo: None, ["resume"]))
        children.append(("[auto-advance, commit run first]", commit_everything, ["resume"]))
    return children


class Explorer:
    def __init__(self, template, node_budget=NODE_BUDGET):
        self.template = template
        self.node_budget = node_budget
        self.node_count = 0
        self.visited = {}
        self.edges = collections.defaultdict(list)
        self.failures = []
        self.queue = collections.deque()
        self.budget_hit = False
        self.roots = []
        self.plan_edit_calls_from_wait = 0

    def new_repo(self):
        self.node_count += 1
        target = TMP_ROOT / f"budget{self.node_budget}-n{self.node_count}"
        shutil.copytree(self.template, target, symlinks=True)
        return target

    def run_step(self, parent, repo, label, argv, presets, new_segment, node_id, call_presets=None):
        # Run one verb on the copied repo. Returns the new node, or None when the path ended (pass or fail).
        verb_text = " ".join(argv)
        history = [*parent.history, f"{label} {verb_text}"] if parent else [f"{verb_text}"]
        steps = 1 if new_segment else parent.steps_in_segment + 1
        seen = frozenset() if new_segment else parent.seen_in_segment
        handbacks = (parent.handbacks + (1 if new_segment else 0)) if parent else 0

        step_key = (verb_text, label if not new_segment else "", state_signature(repo))
        if step_key in seen:
            self.failures.append(Failure("repeated (verb, state)", history, f"{verb_text} on {step_key[2][:600]}",
                                         self.cycle_of(history, step_key, parent)))
            return "fail"
        if steps > STEP_LIMIT:
            self.failures.append(Failure(f"over the {STEP_LIMIT}-step limit", history, "", history[-6:]))
            return "fail"

        if parent and parent.action == "wait" and label.startswith("[plan-edit coder:") \
                and load_saved_state(parent.repo).get("stage") == "plan-coder":
            self.plan_edit_calls_from_wait += 1

        output, crash = call_script(repo, {**presets, **(call_presets or {})}, argv)
        action, agent = parse_action(output)
        if crash:
            self.failures.append(Failure("crash", history, crash.strip().splitlines()[-1], history[-2:]))
            return "fail"
        if action is None:
            self.failures.append(Failure("no ACTION line", history, output.strip()[-200:], history[-2:]))
            return "fail"
        is_ruled_decision = (
            argv[0] == "decide"
            and argv[1:2] in (["adopt"], ["keep"])
            and "--ruling" in argv
            and argv[argv.index("--by") + 1 :][:1] in (["user"], ["session"])
            if "--by" in argv
            else False
        )
        is_answer = new_segment and (is_ruled_decision or argv[0] == "asks-done")
        answer_count = (parent.answer_count if parent else 0) + (1 if is_answer else 0)
        ancestors_in_segment = (
            frozenset() if new_segment or parent is None else parent.ancestors_in_segment | {parent.node_id}
        )
        starts_again = argv[0] == "start"
        ancestor_answers = dict(parent.ancestor_answers) if parent and not starts_again else {}
        if parent and not starts_again:
            ancestor_answers[parent.node_id] = parent.answer_count
        hand_back_commands = named_commands(output + saved_say_text(repo)) if action in HAND_BACK_ACTIONS else ()
        node = Node(repo, presets, action, agent, history, steps, seen | {step_key}, handbacks, ancestors_in_segment,
                    ancestor_answers, answer_count, hand_back_commands)
        return node

    def cycle_of(self, history, step_key, parent):
        # The verbs between the first and the second call of the repeated pair.
        verb_text, label = step_key[0], step_key[1]
        marker = f"{label} {verb_text}" if label else verb_text
        positions = [index for index, entry in enumerate(history[:-1]) if entry == marker]
        start = positions[-1] if positions else 0
        return history[start:]

    def cycle_between(self, node, node_id):
        # The calls since this configuration was last seen: they are the loop.
        return node.history[-8:]

    def node_id(self, node):
        state = state_signature(node.repo)
        return (node.action, node.agent, tuple(sorted(node.presets.items())), state)

    def explore_root(self, root_label, argv, presets):
        repo = self.new_repo()
        result = self.run_step(None, repo, "", argv, presets, True, None)
        if result == "fail":
            return None
        root_id = self.register(result, None, root_label)
        self.roots.append(root_id)
        return root_id

    def register(self, node, parent_id, label):
        node_id = self.node_id(node)
        node.node_id = node_id
        if node_id in node.ancestors_in_segment:
            self.failures.append(
                Failure(
                    "repeated (verb, state)",
                    node.history,
                    f"back at {node_id[0]} {node_id[1] or ''} on {node_id[3][:600]}",
                    self.cycle_between(node, node_id),
                )
            )
            self.edges[parent_id].append("LEAF")
            return None
        if node_id in node.ancestor_answers and node.answer_count > node.ancestor_answers[node_id]:
            self.failures.append(Failure("question answered, then asked again (across hand-backs)", node.history,
                                         f"back at {node_id[0]} {node_id[1] or ''} on {node_id[3][:600]}",
                                         self.cycle_between(node, node_id)))
            self.edges[parent_id].append("LEAF")
            return None
        if parent_id is not None:
            self.edges[parent_id].append(node_id)
        if node_id in self.visited:
            shutil.rmtree(node.repo, ignore_errors=True)
            return node_id
        self.visited[node_id] = True
        self.queue.append((node_id, node))
        return node_id

    def check_named_commands(self, node):
        # A hand-back that names a command for the user to run must not name one the script then refuses.
        for argv in node.hand_back_commands:
            if self.node_count > self.node_budget:
                self.budget_hit = True
                return

            repo = self.new_repo()
            shutil.rmtree(repo)
            shutil.copytree(node.repo, repo, symlinks=True)
            output, crash = call_script(repo, node.presets, argv)
            shutil.rmtree(repo, ignore_errors=True)
            history = [*node.history, f"[user: the named command] {' '.join(argv)}"]
            if crash:
                self.failures.append(Failure("crash", history, crash.strip().splitlines()[-1], history[-2:]))
                continue

            refusal = next((line for line in output.splitlines() if line.startswith("Refused:")), None)
            if refusal:
                self.failures.append(Failure("dead end: a named command is refused", history, refusal, history[-2:]))

    def expand(self, node_id, node):
        if node.action in HAND_BACK_ACTIONS:
            self.check_named_commands(node)
            if node.handbacks >= MAX_HANDBACKS:
                return
            for label, argv, setup in user_answers(node.repo):
                self.step_child(node, node_id, f"[user: {label}]", argv, setup, True)
            return
        for label, setup, argv, *call_presets in children_of(node):
            self.step_child(node, node_id, label, argv, setup, False, call_presets[0] if call_presets else {})

    def step_child(self, node, node_id, label, argv, setup, new_segment, call_presets=None):
        if self.node_count > self.node_budget:
            self.budget_hit = True
            return
        repo = self.new_repo()
        shutil.rmtree(repo)
        shutil.copytree(node.repo, repo, symlinks=True)
        if setup:
            setup(repo)
        result = self.run_step(node, repo, label, argv, node.presets, new_segment, node_id, call_presets or {})
        if result == "fail":
            shutil.rmtree(repo, ignore_errors=True)
            self.edges[node_id].append("LEAF")
            return
        self.register(result, node_id, label)

    def run(self, entries):
        for root_label, argv, presets in entries:
            self.explore_root(root_label, argv, presets)
        while self.queue:
            node_id, node = self.queue.popleft()
            self.expand(node_id, node)
            if node.action not in HAND_BACK_ACTIONS and not children_of(node):
                self.edges[node_id].append("LEAF")
            shutil.rmtree(node.repo, ignore_errors=True)
            if not self.edges[node_id]:
                self.edges[node_id].append("LEAF")
            if self.node_count > self.node_budget:
                self.budget_hit = True
                break

    def path_count(self):
        # Complete paths from the start verbs to a leaf. A shared tail counts once per way of reaching it.
        counts = {}
        on_stack = set()
        sys.setrecursionlimit(20000)

        def count(node_id):
            if node_id == "LEAF" or node_id is None or node_id in on_stack:
                return 1
            if node_id in counts:
                return counts[node_id]
            on_stack.add(node_id)
            total = sum(count(child) for child in self.edges.get(node_id, [])) or 1
            on_stack.discard(node_id)
            counts[node_id] = total
            return total

        return sum(count(root_id) for root_id in self.roots) + len(self.failures)


def entry_verbs():
    none = {}
    impact_keep = {"CODE_STEP_IMPACT_DECISION": "keep"}
    impact_adopt = {"CODE_STEP_IMPACT_DECISION": "adopt"}
    preset_sets = [none, impact_keep, impact_adopt, {"CODE_STEP_ASKS_OUTCOME": "accepted"},
                  {**impact_keep, "CODE_STEP_ASKS_OUTCOME": "accepted"}]
    verbs = [
        ["start", PLAN_A],
        ["start", PLAN_A, "+fast"],
        ["start"],
        ["start", "--task", "add a thing"],
        ["start", "docs/other/single.md"],
        ["start", "docs/other/no-status.md"],
        ["start", "docs/other/no-criteria.md"],
        ["start", "docs/missing.md"],
        ["start", "continue"],
        ["start", "after-review"],
        ["start", PLAN_A, "--phase", "2", "—", "brief"],
        ["start", f"{PLAN_A} --phase 2 — brief"],
        ["start", "fix", "a", "typo"],
        ["start", "--phase", "2", "—", "brief"],
        ["resume"],
        ["decide", "keep"],
        ["asks-done", "accepted"],
        ["skill-done", "pass"],
    ]
    if hasattr(code_step, "command_standalone"):
        verbs += [["review"], ["fix", "null guard in orders.ts"], ["fix"], ["fix", "no-review", "null guard"]]
    entries = []
    for presets in preset_sets:
        for argv in verbs:
            if presets is not none and argv not in (["start", PLAN_A], ["start", "--task", "add a thing"]):
                continue
            tag = ",".join(f"{key.split('_')[-2].lower()}={value}" for key, value in presets.items()) or "no presets"
            entries.append((f"{' '.join(argv)} [{tag}]", argv, presets))
    return entries


def describe(failure):
    lines = [f"FAIL {failure.kind}: {len(failure.history)} calls"]
    lines += [f"    {number + 1:>2}. {step}" for number, step in enumerate(failure.history)]
    if failure.detail:
        lines.append(f"    repeated / last state: {failure.detail}")
    return "\n".join(lines)


def explore_all():
    template = build_template()
    explorer = Explorer(template)
    entries = entry_verbs()
    explorer.run(entries)
    return explorer, entries


def explore_plan_edit(template, entries):
    adopt_entries = [entry for entry in entries if "impact=adopt" in entry[0]]
    explorer = Explorer(template, PLAN_EDIT_NODE_BUDGET)
    explorer.run(adopt_entries)
    return explorer, adopt_entries


def summarize(explorer, entries):
    grouped = collections.OrderedDict()
    for failure in explorer.failures:
        signature = (failure.kind, tuple(step.split("] ", 1)[-1] if "] " in step else step for step in failure.cycle),
                     tuple(step for step in failure.cycle))
        grouped.setdefault(signature, []).append(failure)
    lines = [
        f"entry verbs x preset sets: {len(entries)} starts; script calls (nodes): {explorer.node_count}; "
        f"distinct configurations: {len(explorer.visited)}; paths explored: {explorer.path_count()}; failing paths: "
        f"{len(explorer.failures)}; "
        f"distinct failures: {len(grouped)}"
        + ("; stopped at the node budget (breadth-first, shortest paths first)" if explorer.budget_hit else "")
    ]
    for failures in grouped.values():
        shortest = min(failures, key=lambda failure: len(failure.history))
        lines.append(f"--- {len(failures)} path(s) with this loop")
        lines.append(describe(shortest))
    return "\n".join(lines)


class TerminationTest(unittest.TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(TMP_ROOT, ignore_errors=True)

    def test_every_path_ends_in_a_stop_or_a_hand_back(self):
        explorer, entries = explore_all()
        report = summarize(explorer, entries)
        print("\n" + report)
        self.assertEqual([], explorer.failures, report)

        plan_edit_explorer, adopt_entries = explore_plan_edit(explorer.template, entries)
        plan_edit_report = summarize(plan_edit_explorer, adopt_entries)
        self.assertEqual([], plan_edit_explorer.failures, plan_edit_report)
        self.assertGreater(plan_edit_explorer.plan_edit_calls_from_wait, 0)


if __name__ == "__main__":
    unittest.main()
