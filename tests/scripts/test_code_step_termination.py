"""Termination test for code-step.py: drive the script the way the /code subagent does and check every run ends.

The explorer starts from each entry verb. For every ACTION the script prints it feeds each outcome the script accepts
(fake agent reports written into the files the script reads; Claude never runs), then calls the next verb. It walks
the tree breadth-first. One segment is the run between two hand-backs to the user. A segment passes when it reaches a
stop or an ask-user. It fails when it calls the same verb on the same saved state after the same agent outcome twice,
when it passes STEP_LIMIT calls, or when a call crashes or prints no ACTION.

Identical configurations reached by different paths are explored once. The verdict of a shared tail covers every path
that reaches it. A hand-back starts a new segment: the user's answer (decide, asks-done, verify, start) is one more
entry verb, so loops that only close through a user answer are not counted as stuck.
"""
import collections
import contextlib
import atexit
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).parent
REPO_SCRIPT = HERE.parent.parent / "claude" / ".claude" / "scripts" / "code-step.py"
SCRIPT = pathlib.Path(os.environ["CODE_STEP_SCRIPT"]) if os.environ.get("CODE_STEP_SCRIPT") else \
    HERE / "code-step.py" if (HERE / "code-step.py").exists() else REPO_SCRIPT
REAL_CLAUDE = SCRIPT.parent.parent if (SCRIPT.parent / "coder-gate.py").exists() else pathlib.Path.home() / ".claude"
HANDBACK_SCRIPT = pathlib.Path(os.environ.get("HANDBACK_SCRIPT") or REAL_CLAUDE / "scripts" / "handback.py")
sys.path.insert(0, str(HANDBACK_SCRIPT.parent))
sys.path.insert(0, str(SCRIPT.parent))
import script_utils  # noqa: F401  (loaded before handback, so handback and code-step share the script directory's copy)
import handback
STEP_LIMIT = 30
MAX_HANDBACKS = 3
NODE_BUDGET = 5000
HAND_BACK_ACTIONS = ("ask-user", "stop", "judgment", "stop-block-B", "stop-block-C")

TMP_ROOT = pathlib.Path(tempfile.mkdtemp(prefix="termination-"))
CLAUDE_STUB = TMP_ROOT / "claude"
(CLAUDE_STUB / "scripts").mkdir(parents=True)
(CLAUDE_STUB / "skills/review").mkdir(parents=True)
for scriptName in ("coder-gate.py", "coder-packet.py", "plan_format.py", "script_utils.py", "resolve-task-dir.sh"):
    shutil.copy(SCRIPT.parent / scriptName if (SCRIPT.parent / scriptName).exists() else pathlib.Path.home() / ".claude/scripts" / scriptName, CLAUDE_STUB / "scripts" / scriptName)
for stubName in ("scripts/log-scan", "skills/review/log-review-finding"):
    stubFile = CLAUDE_STUB / stubName
    stubFile.write_text("#!/usr/bin/env bash\nexit 0\n")
    stubFile.chmod(0o755)
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
           "CODE_STEP_CLAUDE_DIR": str(CLAUDE_STUB), "CODE_STEP_WAIT_SECONDS": "0", "HOME": str(TMP_ROOT / "home"),
           "CLAUDE_CODE_SESSION_ID": "sess-termination"}
NO_ROW_YET_PRESETS = {"CODE_STEP_WAIT_SECONDS": "0.2", "CODE_STEP_POLL_SECONDS": "0.05"}

# code-step.py reads CODE_STEP_CLAUDE_DIR once, at import. Set it only while the module loads, so the real log
# scripts and the live ~/.claude files are never reached and other test modules keep their environment.
atexit.register(shutil.rmtree, TMP_ROOT, ignore_errors=True)
moduleSpec = importlib.util.spec_from_file_location("code_step_under_test", SCRIPT)
codeStep = importlib.util.module_from_spec(moduleSpec)
with mock.patch.dict(os.environ, {"CODE_STEP_CLAUDE_DIR": str(CLAUDE_STUB)}):
    moduleSpec.loader.exec_module(codeStep)

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
PLAN_NO_CRITERIA = "# P\n\n## Acceptance Criteria\n\n- c\n\n## Phase Status\n\n- [ ] Phase 1: One (risk: low)\n\n## Phase 1: One\n\nx\n"
PLAN_SINGLE = "# Single\n\n## Overview\n\nDo `backend/src/single.ts`.\n"

PLAN_EDIT_PLANS = {"docs/other/single.md": PLAN_SINGLE, "docs/other/no-status.md": PLAN_NO_PHASE_STATUS,
                   "docs/other/no-criteria.md": PLAN_NO_CRITERIA}

# ---------- fake agent outcomes ----------

ASK_ONE = '{"finding": "f", "file_line": "backend/src/orders.ts:2", "question": "keep?", "gate": "code-reviewer", "class": "correctness"}'
ASK_TWO = '{"finding": "g", "file_line": "backend/src/orders.ts:3", "question": "drop?", "gate": "code-reviewer", "class": "other"}'
REVIEW_OUTCOMES = {
    "converged-clean": "status: converged\niter: 1\nfixed: []\nask: []\nnit: []",
    "converged-fixed": 'status: converged\niter: 2\nfixed:\n- {finding: "x", file_line: "backend/src/orders.ts:1", blocker: false}\nask: []',
    "converged-ask1": f"status: converged\niter: 1\nfixed: []\nask: [{ASK_ONE}]",
    "converged-ask2": f"status: converged\niter: 1\nfixed: []\nask: [{ASK_ONE}, {ASK_TWO}]",
    "deferred-ask": f'status: deferred\niter: 1\nfindings_remaining:\n- {{finding: "d", file_line: "a.ts:2"}}\nask: [{ASK_ONE}]',
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


def write_text(repo, relativePath, text):
    target = repo / relativePath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)


def apply_coder_outcome(repo, name, uniqueText):
    files, flag, gateResult, report = CODER_OUTCOMES[name]
    if "src" in files:
        write_text(repo, "backend/src/orders.ts", f"export const o = '{uniqueText}'\n")
    if flag:
        write_text(repo, "verify.flag", "ok\n")
    gatePath = repo / ".git/coder-gate.json"
    if gatePath.exists():
        gate = json.loads(gatePath.read_text())
        if gateResult == "never":
            gate["coders"] = {}
        elif gateResult == "cap":
            gate["coders"] = {"a1": {"runs": 4, "denies": 3, "failed": gate["commands"][:1], "skipped": [], "result": "cap"}}
        else:
            gate["coders"] = {"a1": {"runs": 1, "denies": 0, "failed": [], "skipped": [], "result": "pass"}}
        gatePath.write_text(json.dumps(gate))
    return report


def store_review_loop_report(repo, message):
    # The shared hand-back store records a review-loop dispatch and its hand-back. A packet that does not parse is
    # refused once and recorded when the agent hands back again, as the real hook does.
    event = {"session_id": GIT_ENV["CLAUDE_CODE_SESSION_ID"], "agent_type": "review-loop", "agent_id": "a1",
             "tool_input": {"message": message}}
    with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(repo / ".git/handback-store")}):
        handback.handle_hook({**event, "tool_input": {"subagent_type": "review-loop"}}, "dispatch")
        for _ in range(2):
            handback.handle_hook(event, "handback")


def save_report(repo, agentType, message):
    if agentType == "review-loop":
        store_review_loop_report(repo, message)
    stateFile = repo / ".git/code-step/state.json"
    stage = json.loads(stateFile.read_text())["stage"]
    row = {"ts": time.time(), "agent_type": agentType, "agent_id": "a1", "stage": stage, "message": message}
    with (repo / ".git/code-step/reports.jsonl").open("a") as reportsFile:
        reportsFile.write(json.dumps(row) + "\n")


def date_dispatch_now(repo):
    stateFile = repo / ".git/code-step/state.json"
    saved = json.loads(stateFile.read_text())
    saved["dispatchAt"] = time.time()
    stateFile.write_text(json.dumps(saved, indent=1))


def apply_plan_edit_outcome(repo, name, planPath):
    if name == "plan-not-edited":
        return
    planFile = repo / planPath
    planFile.write_text(planFile.read_text().replace("Add orders.", "Add orders, with the adopted change."))
    if name == "plan-edited-and-stray-file":
        write_text(repo, "backend/src/stray.ts", "export const s = 1\n")


# ---------- repo and script calls ----------

def build_template():
    template = TMP_ROOT / "template"
    template.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "ORD-1-work", "--template="], cwd=template, check=True, capture_output=True)
    write_text(template, "backend/package.json", json.dumps({
        "scripts": {"typecheck": "tsc --noEmit", "lint": "eslint ."}, "devDependencies": {"vitest": "1", "eslint": "9"}}))
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
    scriptEnv = {name: value for name, value in os.environ.items()
                 if name not in ("CODE_STEP_IMPACT_DECISION", "CODE_STEP_ASKS_OUTCOME")}
    scriptEnv.update(GIT_ENV)
    scriptEnv["HANDBACK_STORE_DIR"] = str(repo / ".git/handback-store")
    scriptEnv.update(presets)
    previousDirectory = os.getcwd()
    previousArgv = sys.argv
    os.chdir(repo)
    sys.argv = ["code-step.py", *argv]
    captured = io.StringIO()
    crash = None
    try:
        with mock.patch.dict(os.environ, scriptEnv, clear=True), \
                contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            try:
                codeStep.main()
            except SystemExit as stopped:
                captured.write(f"[exit: {stopped.code}]\n")
    except Exception:
        crash = traceback.format_exc()
    finally:
        os.chdir(previousDirectory)
        sys.argv = previousArgv
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
    stateFile = repo / ".git/code-step/state.json"
    if not stateFile.exists():
        return {}
    try:
        return json.loads(stateFile.read_text())
    except ValueError:
        return {"unreadable": True}


def plan_progress(repo):
    # Which phases are checked, so finishing a phase counts as progress and not as a repeat.
    progress = []
    for planFile in sorted((repo / "docs").rglob("*.md")):
        progress.append(planFile.name + ":" + "".join("x" if line.startswith("- [x]") else "" for line in planFile.read_text().splitlines()))
    return "|".join(progress)


IGNORED_STATE_KEYS = ("startedAt", "baseline", "planEditBaseline", "asksBaseline", "sessionId", "dispatchAt", "forkDenied",
                      "forkStopBlocks")


MINUTE_STAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}")


def state_signature(repo):
    # The script stamps each ruling with the wall-clock minute. Two visits to one state a minute apart must still
    # compare equal, or whether a loop is caught depends on when the run happens to cross a minute.
    state = {key: value for key, value in load_saved_state(repo).items() if key not in IGNORED_STATE_KEYS}
    stateText = MINUTE_STAMP.sub("<minute>", json.dumps(state, sort_keys=True))
    return stateText + "#" + plan_progress(repo)


# ---------- the explorer ----------

class Node:
    def __init__(self, repo, presets, action, agent, history, stepsInSegment, seenInSegment, handbacks,
                 ancestorsInSegment=frozenset(), ancestorAnswers=None, answerCount=0):
        self.ancestorsInSegment = ancestorsInSegment
        self.ancestorAnswers = ancestorAnswers or {}
        self.answerCount = answerCount
        self.repo = repo
        self.presets = presets
        self.action = action
        self.agent = agent
        self.history = history
        self.stepsInSegment = stepsInSegment
        self.seenInSegment = seenInSegment
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
    answers = []
    if stage in ("impact-coder", "impact-review"):
        ruling = ["--by", "user", "--ruling", "the user's words"]
        sessionRuling = ["--by", "session", "--ruling", "the session's words"]
        answers += [("decide adopt", ["decide", "adopt", *ruling], None), ("decide keep", ["decide", "keep", *ruling], None),
                    ("decide adopt by session", ["decide", "adopt", *sessionRuling], None),
                    ("decide keep by session", ["decide", "keep", *sessionRuling], None),
                    ("decide keep without --by", ["decide", "keep", "--ruling", "the user's words"], None),
                    ("decide keep without a ruling", ["decide", "keep"], None),
                    ("decide discuss", ["decide", "discuss"], None), ("decide bogus", ["decide", "maybe"], None)]
    if stage == "asks":
        count = len(state.get("asks", []))
        answers += [("asks-done all accepted", ["asks-done"] + ["accepted"] * count, None),
                    ("asks-done all rejected", ["asks-done"] + ["rejected"] * count, None),
                    ("asks-done all modified", ["asks-done"] + sum([["modified", "--change", "use X"]] * count, []), None)]
    if stage == "stopped" and state.get("stopReason") == "invalid-packet":
        answers += [("review-again", ["review-again"], None)]
    if stage == "stopped" and state.get("stopReason") in ("verification", "plan-format"):
        answers += [("verify (still failing)", ["verify"], None),
                    ("verify (fixed)", ["verify"], lambda repo: write_text(repo, "verify.flag", "ok\n"))]
    answers += [("start", ["start"], None)]
    return answers


def commit_everything(repo):
    for command in (["git", "add", "-A"], ["git", "commit", "-qm", "phase"]):
        subprocess.run(command, cwd=repo, check=True, capture_output=True, env={**os.environ, **GIT_ENV})


def children_of(node):
    # Each child: (label, setup function on the copied repo, argv for the next verb, presets).
    state = load_saved_state(node.repo)
    stage = state.get("stage")
    children = []
    waitingOn = None
    isPlanEdit = stage == "plan-coder" and node.action in ("dispatch", "wait")
    if node.action == "wait" and not isPlanEdit:
        waitingOn = "coder" if stage in ("coder", "asks-coder") else "review-loop"
    if node.action == "dispatch" and node.agent in ("coder", "review-loop"):
        # The agent has not handed back when the verb that follows the dispatch runs: the verb says to run it again.
        verb = "after-review" if node.agent == "review-loop" else "after-coder"
        setup = lambda repo: None
        if isPlanEdit:
            # The saved dispatch is older than the wait cap by now: date it again so the wait itself is tried.
            verb, setup = "after-plan-edit", date_dispatch_now
        children.append(("[no report yet]", setup, [verb], NO_ROW_YET_PRESETS))
    if isPlanEdit:
        for name in PLAN_EDIT_OUTCOMES:
            def setup(repo, name=name):
                apply_plan_edit_outcome(repo, name, state["plan"])
                save_report(repo, "coder", "plan edited")
            children.append((f"[plan-edit coder: {name}]", setup, ["after-plan-edit"]))
    elif waitingOn == "coder" or (node.action == "dispatch" and node.agent == "coder"):
        for name in CODER_OUTCOMES:
            def setup(repo, name=name):
                report = apply_coder_outcome(repo, name, f"v{len(node.history)}")
                if report is not None:
                    save_report(repo, "coder", report)
            children.append((f"[coder: {name}]", setup, ["after-coder"]))
    elif waitingOn == "review-loop" or (node.action == "dispatch" and node.agent == "review-loop"):
        isAnswered = state.get("planImpact", "none") != "none"
        for name, message in REVIEW_OUTCOMES.items():
            # A reviewer re-raises an answered question unless the dispatch tells it the question is resolved.
            if name.startswith("plan-impact") and isAnswered and "RESOLVED" in state.get("lastReviewPrompt", ""):
                continue
            def setup(repo, message=message):
                if message is not None:
                    save_report(repo, "review-loop", message)
            children.append((f"[review-loop: {name}]", setup, ["after-review"]))
    elif node.action in ("invoke-skill", "dispatch"):
        for verdict in ("pass", "fail", "bogus"):
            children.append((f"[skill result: {verdict}]", lambda repo: None, ["skill-done", verdict]))
    elif node.action == "auto-advance":
        modifier = state.get("modifier")
        startVerb = ["start"] + ([modifier] if modifier else [])
        children.append(("[auto-advance, commit not run]", lambda repo: None, startVerb))
        children.append(("[auto-advance, commit run first]", commit_everything, startVerb))
    return children


class Explorer:
    def __init__(self, template):
        self.template = template
        self.nodeCount = 0
        self.visited = {}
        self.edges = collections.defaultdict(list)
        self.failures = []
        self.queue = collections.deque()
        self.budgetHit = False
        self.roots = []
        self.planEditCallsFromWait = 0

    def new_repo(self):
        self.nodeCount += 1
        target = TMP_ROOT / f"n{self.nodeCount}"
        shutil.copytree(self.template, target, symlinks=True)
        return target

    def run_step(self, parent, repo, label, argv, presets, newSegment, nodeId, callPresets=None):
        # Run one verb on the copied repo. Returns the new node, or None when the path ended (pass or fail).
        verbText = " ".join(argv)
        history = parent.history + [f"{label} {verbText}"] if parent else [f"{verbText}"]
        steps = 1 if newSegment else parent.stepsInSegment + 1
        seen = frozenset() if newSegment else parent.seenInSegment
        handbacks = (parent.handbacks + (1 if newSegment else 0)) if parent else 0

        stepKey = (verbText, label if not newSegment else "", state_signature(repo))
        if stepKey in seen:
            self.failures.append(Failure("repeated (verb, state)", history, f"{verbText} on {stepKey[2][:600]}",
                                         self.cycle_of(history, stepKey, parent)))
            return "fail"
        if steps > STEP_LIMIT:
            self.failures.append(Failure(f"over the {STEP_LIMIT}-step limit", history, "", history[-6:]))
            return "fail"

        if parent and parent.action == "wait" and label.startswith("[plan-edit coder:") \
                and load_saved_state(parent.repo).get("stage") == "plan-coder":
            self.planEditCallsFromWait += 1

        output, crash = call_script(repo, {**presets, **(callPresets or {})}, argv)
        action, agent = parse_action(output)
        if crash:
            self.failures.append(Failure("crash", history, crash.strip().splitlines()[-1], history[-2:]))
            return "fail"
        if action is None:
            self.failures.append(Failure("no ACTION line", history, output.strip()[-200:], history[-2:]))
            return "fail"
        isRuledDecision = (argv[0] == "decide" and argv[1:2] in (["adopt"], ["keep"]) and "--ruling" in argv
                           and argv[argv.index("--by") + 1:][:1] in (["user"], ["session"]) if "--by" in argv else False)
        isAnswer = newSegment and (isRuledDecision or argv[0] == "asks-done")
        answerCount = (parent.answerCount if parent else 0) + (1 if isAnswer else 0)
        ancestorsInSegment = frozenset() if newSegment or parent is None else parent.ancestorsInSegment | {parent.nodeId}
        ancestorAnswers = dict(parent.ancestorAnswers) if parent and argv[0] != "start" else {}
        if parent and argv[0] != "start":
            ancestorAnswers[parent.nodeId] = parent.answerCount
        node = Node(repo, presets, action, agent, history, steps, seen | {stepKey}, handbacks, ancestorsInSegment,
                    ancestorAnswers, answerCount)
        return node

    def cycle_of(self, history, stepKey, parent):
        # The verbs between the first and the second call of the repeated pair.
        verbText, label = stepKey[0], stepKey[1]
        marker = f"{label} {verbText}" if label else verbText
        positions = [index for index, entry in enumerate(history[:-1]) if entry == marker]
        start = positions[-1] if positions else 0
        return history[start:]

    def cycle_between(self, node, nodeId):
        # The calls since this configuration was last seen: they are the loop.
        return node.history[-8:]

    def node_id(self, node):
        state = state_signature(node.repo)
        return (node.action, node.agent, tuple(sorted(node.presets.items())), state)

    def explore_root(self, rootLabel, argv, presets):
        repo = self.new_repo()
        result = self.run_step(None, repo, "", argv, presets, True, None)
        if result == "fail":
            return None
        rootId = self.register(result, None, rootLabel)
        self.roots.append(rootId)
        return rootId

    def register(self, node, parentId, label):
        nodeId = self.node_id(node)
        node.nodeId = nodeId
        if nodeId in node.ancestorsInSegment:
            self.failures.append(Failure("repeated (verb, state)", node.history, f"back at {nodeId[0]} {nodeId[1] or ''} on "
                                         f"{nodeId[3][:600]}", self.cycle_between(node, nodeId)))
            self.edges[parentId].append("LEAF")
            return None
        if nodeId in node.ancestorAnswers and node.answerCount > node.ancestorAnswers[nodeId]:
            self.failures.append(Failure("question answered, then asked again (across hand-backs)", node.history,
                                         f"back at {nodeId[0]} {nodeId[1] or ''} on {nodeId[3][:600]}",
                                         self.cycle_between(node, nodeId)))
            self.edges[parentId].append("LEAF")
            return None
        if parentId is not None:
            self.edges[parentId].append(nodeId)
        if nodeId in self.visited:
            shutil.rmtree(node.repo, ignore_errors=True)
            return nodeId
        self.visited[nodeId] = True
        self.queue.append((nodeId, node))
        return nodeId

    def expand(self, nodeId, node):
        if node.action in HAND_BACK_ACTIONS:
            if node.handbacks >= MAX_HANDBACKS:
                return
            for label, argv, setup in user_answers(node.repo):
                self.step_child(node, nodeId, f"[user: {label}]", argv, setup, True)
            return
        for label, setup, argv, *callPresets in children_of(node):
            self.step_child(node, nodeId, label, argv, setup, False, callPresets[0] if callPresets else {})

    def step_child(self, node, nodeId, label, argv, setup, newSegment, callPresets=None):
        if self.nodeCount > NODE_BUDGET:
            self.budgetHit = True
            return
        repo = self.new_repo()
        shutil.rmtree(repo)
        shutil.copytree(node.repo, repo, symlinks=True)
        if setup:
            setup(repo)
        result = self.run_step(node, repo, label, argv, node.presets, newSegment, nodeId, callPresets or {})
        if result == "fail":
            shutil.rmtree(repo, ignore_errors=True)
            self.edges[nodeId].append("LEAF")
            return
        self.register(result, nodeId, label)

    def run(self, entries):
        for rootLabel, argv, presets in entries:
            self.explore_root(rootLabel, argv, presets)
        while self.queue:
            nodeId, node = self.queue.popleft()
            self.expand(nodeId, node)
            if node.action not in HAND_BACK_ACTIONS and not children_of(node):
                self.edges[nodeId].append("LEAF")
            shutil.rmtree(node.repo, ignore_errors=True)
            if not self.edges[nodeId]:
                self.edges[nodeId].append("LEAF")
            if self.nodeCount > NODE_BUDGET:
                self.budgetHit = True
                break

    def path_count(self):
        # Complete paths from the start verbs to a leaf. A shared tail counts once per way of reaching it.
        counts = {}
        onStack = set()
        sys.setrecursionlimit(20000)

        def count(nodeId):
            if nodeId == "LEAF" or nodeId is None or nodeId in onStack:
                return 1
            if nodeId in counts:
                return counts[nodeId]
            onStack.add(nodeId)
            total = sum(count(child) for child in self.edges.get(nodeId, [])) or 1
            onStack.discard(nodeId)
            counts[nodeId] = total
            return total

        return sum(count(rootId) for rootId in self.roots) + len(self.failures)


def entry_verbs():
    none = {}
    impactKeep = {"CODE_STEP_IMPACT_DECISION": "keep"}
    impactAdopt = {"CODE_STEP_IMPACT_DECISION": "adopt"}
    presetSets = [none, impactKeep, impactAdopt, {"CODE_STEP_ASKS_OUTCOME": "accepted"},
                  {**impactKeep, "CODE_STEP_ASKS_OUTCOME": "accepted"}]
    verbs = [["start", PLAN_A], ["start", PLAN_A, "+fast"], ["start"], ["start", "--task", "add a thing"],
             ["start", "docs/other/single.md"], ["start", "docs/other/no-status.md"], ["start", "docs/other/no-criteria.md"],
             ["start", "docs/missing.md"],
             ["after-coder"], ["after-review"], ["after-plan-edit"], ["decide", "keep"], ["asks-done", "accepted"],
             ["skill-done", "pass"], ["verify"]]
    if hasattr(codeStep, "command_standalone"):
        verbs += [["review"], ["fix", "null guard in orders.ts"], ["fix"], ["fix", "no-review", "null guard"]]
    entries = []
    for presets in presetSets:
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


def summarize(explorer, entries):
    grouped = collections.OrderedDict()
    for failure in explorer.failures:
        signature = (failure.kind, tuple(step.split("] ", 1)[-1] if "] " in step else step for step in failure.cycle),
                     tuple(step for step in failure.cycle))
        grouped.setdefault(signature, []).append(failure)
    lines = [f"entry verbs x preset sets: {len(entries)} starts; script calls (nodes): {explorer.nodeCount}; "
             f"distinct configurations: {len(explorer.visited)}; paths explored: {explorer.path_count()}; failing paths: {len(explorer.failures)}; "
             f"distinct failures: {len(grouped)}"
             + ("; stopped at the node budget (breadth-first, shortest paths first)" if explorer.budgetHit else "")]
    for signature, failures in grouped.items():
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
        self.assertGreater(explorer.planEditCallsFromWait, 0)


if __name__ == "__main__":
    unittest.main()
