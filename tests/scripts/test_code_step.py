import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = REPO_ROOT / "claude" / ".claude"
SCRIPT = pathlib.Path(os.environ.get("CODE_STEP_SCRIPT") or REAL_CLAUDE / "scripts" / "code-step.py")
HANDBACK_SCRIPT = pathlib.Path(os.environ.get("HANDBACK_SCRIPT") or REAL_CLAUDE / "scripts" / "handback.py")
sys.path.insert(0, str(SCRIPT.parent))
moduleSpec = importlib.util.spec_from_file_location("code_step", SCRIPT)
code_step = importlib.util.module_from_spec(moduleSpec)
moduleSpec.loader.exec_module(code_step)

PLAN = """# Orders Plan

## Overview

Add orders.

## Phase Status

- [ ] Phase 1: Walking skeleton (risk: low)
- [ ] Phase 2: Totals (risk: low)
- [ ] Phase 3: Audit trail (risk: high)
- [ ] Phase 4: Refactor pass - /refactor cleanup sweep (risk: low)

## Acceptance Criteria

- **Criteria file**: `docs/plans/orders/acceptance-criteria.md`

## Phase 1: Walking skeleton

**File**: `backend/src/orders.ts`
**File**: `backend/src/orders.test.ts`

#### Automated Verification:

- [ ] **Test-verified**: orders pass - `npx vitest run`
- [ ] **Prohibition**: no console.log - `git grep -n --untracked console.log -- backend/src/orders.ts`

#### Manual Verification:

- [ ] **Manual-verified** (agent-verified): hit /orders

## Phase 2: Totals

**File**: `backend/src/totals.ts`

## Phase 3: Audit trail

**File**: `backend/src/audit.ts`

## Phase 4: Refactor pass

Sweep.

## Testing Strategy

Tests.

## References

- none
"""


def run(cwd, env, *args, stdin=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=cwd, env=env, input=stdin,
                          capture_output=True, text=True)


class CodeStepTest(unittest.TestCase):
    SESSION = "sess-1"

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.claude = self.tmp / "claude"
        (self.claude / "scripts").mkdir(parents=True)
        (self.claude / "skills/review").mkdir(parents=True)
        for name in ("coder-gate.py", "coder-packet.py", "resolve-task-dir.sh"):
            shutil.copy(REAL_CLAUDE / "scripts" / name, self.claude / "scripts" / name)
        self.log = self.tmp / "calls.log"
        for name in ("scripts/log-scan", "skills/review/log-review-finding"):
            stub = self.claude / name
            stub.write_text(f'#!/usr/bin/env bash\necho "{name} $@" >> {self.log}\n')
            stub.chmod(0o755)
        self.repo = self.tmp / "repo"
        (self.repo / "backend/src").mkdir(parents=True)
        (self.repo / "docs/plans/orders").mkdir(parents=True)
        (self.repo / "backend/package.json").write_text(json.dumps({
            "scripts": {"typecheck": "tsc --noEmit", "lint": "eslint ."},
            "devDependencies": {"vitest": "1", "eslint": "9"}}))
        (self.repo / "backend/src/existing.ts").write_text("export const a = 1\n")
        (self.repo / "docs/plans/orders/spec.md").write_text(PLAN)
        (self.repo / "docs/plans/orders/acceptance-criteria.md").write_text("AC-1 orders exist\n")
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = dict(os.environ, CODE_STEP_CLAUDE_DIR=str(self.claude), GIT_AUTHOR_NAME="t",
                        GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t",
                        HOME=str(self.home), CODE_STEP_WAIT_SECONDS="0", CLAUDE_CODE_SESSION_ID=self.SESSION,
                        HANDBACK_STORE_DIR=str(self.tmp / "handback-store"),
                        PYTHONPATH=str(HANDBACK_SCRIPT.parent))
        self.env.pop("CODE_STEP_IMPACT_DECISION", None)
        self.env.pop("CODE_STEP_ASKS_OUTCOME", None)
        for command in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "base"]):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True, env=self.env)
        self.plan = "docs/plans/orders/spec.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def step(self, *args, stdin=None):
        return run(self.repo, self.env, *args, stdin=stdin).stdout

    def handback_hook(self, kind, event):
        return subprocess.run([sys.executable, str(HANDBACK_SCRIPT), "hook", kind], env=self.env,
                              input=json.dumps(event), capture_output=True, text=True)

    def hook(self, agentType, message, agentId="a1", session=SESSION):
        event = {"agent_type": agentType, "agent_id": agentId, "cwd": str(self.repo),
                 "tool_input": {"message": message}}
        if session:
            event["session_id"] = session
        if agentType == "review-loop" and session:
            # The shared hand-back store sees the review-loop's dispatch and hand-back, as its own hooks record them.
            self.handback_hook("dispatch", {"session_id": session, "tool_input": {"subagent_type": "review-loop"}})
            self.handback_hook("handback", event)
        return run(self.repo, self.env, "hook", stdin=json.dumps(event))

    def commit_all(self):
        for command in (["git", "add", "-A"], ["git", "commit", "-qm", "phase"]):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True, env=self.env)

    def state(self):
        return json.loads(self.step("status"))

    def gate_mark(self, session=SESSION):
        markFile = self.home / ".claude/state/review-gate" / session
        return markFile.read_text() if markFile.exists() else None

    def assertMarkedClean(self, out, session=SESSION):
        # The script writes the review-commit-gate state file itself, so the output no longer tells the model to.
        self.assertNotIn("review-gate-mark", out)
        self.assertEqual("clean\n", self.gate_mark(session))

    def said(self):
        sayFile = self.repo / ".git/code-step/say.md"
        return sayFile.read_text() if sayFile.exists() else ""

    def plan_text(self):
        return (self.repo / self.plan).read_text()

    def start_phase_one(self, *extra):
        return self.step("start", self.plan, *extra)

    def begin_coder(self, source="export const o = 1\n"):
        self.start_phase_one()
        gatePath = self.repo / ".git/coder-gate.json"
        if gatePath.exists():
            gate = json.loads(gatePath.read_text())
            gate["coders"]["a1"] = {"runs": 1, "denies": 0, "failed": [], "skipped": [], "result": "pass"}
            gatePath.write_text(json.dumps(gate))
        (self.repo / "backend/src/orders.ts").write_text(source)

    def coder_round(self, report=None, source="export const o = 1\n"):
        report = report or "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters\nREVIEW: recommended"
        self.begin_coder(source)
        self.hook("coder", report)
        return self.step("after-coder")

    def finish_phase_one(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        return self.step("after-review")

    def set_verification(self, line):
        old = "- [ ] **Prohibition**: no console.log - `git grep -n --untracked console.log -- backend/src/orders.ts`"
        self.assertIn(old, self.plan_text())
        (self.repo / self.plan).write_text(self.plan_text().replace(old, line))

    ASK = ('status: converged\niter: 1\nfixed: []\nask: [{"finding": "f", "file_line": "backend/src/orders.ts:2", '
           '"question": "keep?", "gate": "code-reviewer", "class": "correctness"}]')

    LOOP_OK = "status: converged\niter: 1\nfixed: []\nask: []\nnit: []"

    def test_start_builds_gate_and_prompt(self):
        out = self.start_phase_one()
        self.assertIn("ACTION: dispatch", out)
        self.assertIn("AGENT: coder", out)
        self.assertIn("BACKGROUND: no", out)
        self.assertIn("Implement Phase 1 of `docs/plans/orders/spec.md`", out)
        self.assertIn("Packet for Phase 1", out)
        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        joined = " | ".join(gate["commands"])
        self.assertIn("cd backend && npm run typecheck", joined)
        self.assertIn("npx eslint {files:.ts}", joined)
        self.assertIn("npx vitest run src/orders.test.ts", joined)
        self.assertEqual(self.state()["stage"], "coder")

    def test_gate_skips_a_package_in_a_sibling_repo(self):
        sibling = self.tmp / "sibling/evals"
        (sibling / "truth").mkdir(parents=True)
        (sibling / "package.json").write_text(json.dumps({"devDependencies": {"vitest": "1"}}))
        (sibling / "tsconfig.json").write_text("{}")
        siblingFile = "**File**: `backend/src/orders.test.ts`\n**File**: `../sibling/evals/truth/context.json`"
        (self.repo / self.plan).write_text(self.plan_text().replace("**File**: `backend/src/orders.test.ts`", siblingFile))

        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        joined = " | ".join(gate["commands"])
        self.assertNotIn("sibling", joined)
        self.assertIn("cd backend && npm run typecheck", joined)

    def test_fast_modifier_sets_haiku(self):
        self.assertIn("MODEL: haiku", self.start_phase_one("+fast"))

    def test_missing_criteria_stops_and_logs(self):
        (self.repo / "docs/plans/orders/acceptance-criteria.md").write_text("")
        out = self.start_phase_one()
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("scan=acceptance-stub", self.log.read_text())

    def test_hook_saves_only_during_a_run_and_only_for_known_agents(self):
        self.hook("coder", "early")
        self.assertFalse((self.repo / ".git/code-step").exists())
        self.start_phase_one()
        self.hook("Explore", "ignored")
        self.hook("coder", "kept")
        rows = (self.repo / ".git/code-step/reports.jsonl").read_text().splitlines()
        self.assertEqual(len(rows), 1)
        self.assertEqual(json.loads(rows[0])["message"], "kept")

    def test_after_coder_builds_review_prompt(self):
        out = self.coder_round()
        for expected in ("ACTION: dispatch", "AGENT: review-loop", "MODEL: sonnet", "mode: review-first",
                         "caller: code", "lane: code", "plan: docs/plans/orders/spec.md", "phase: 1", "iter: 0",
                         "- path: backend/src/orders.ts", "lines: 3-5", "plan_impact: none", "flagged: none"):
            self.assertIn(expected, out)
        self.assertNotIn("SAY TO THE USER", out)
        self.assertIn("Auto-dispatching review", self.said())
        self.assertIn("Implemented: orders exist", self.said())
        self.assertIn("order matters", self.said())
        self.assertIn("-> exit 0", out)
        self.assertEqual(self.state()["stage"], "review")

    def test_after_coder_ignores_files_dirty_before_start(self):
        (self.repo / "backend/src/existing.ts").write_text("export const a = 2\n")
        out = self.coder_round()
        self.assertNotIn("path: backend/src/existing.ts", out)

    def test_plan_impact_asks_then_decide_records_deviation(self):
        report = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes"
        out = self.coder_round(report)
        self.assertIn("ACTION: ask-user", out)
        self.assertIn("## Question for the user", self.said())
        for option in ("Adopt plan change", "Keep plan as written", "Discuss",
                       "`decide adopt --ruling \"<the user's answer>\"`", "`decide keep --ruling \"<the user's answer>\"`"):
            self.assertIn(option, self.said())
        self.assertNotIn("AskUserQuestion", out + self.said())
        self.assertNotIn("AGENT: review-loop", out)
        out = self.step("decide", "keep", "--ruling", "keep it, the importer is right")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("Decision: Keep plan as written", out)
        self.assertNotIn("## Question for the user", self.said())
        self.assertIn("## Plan Deviations", self.plan_text())
        self.assertLess(self.plan_text().index("## Plan Deviations"), self.plan_text().index("## References"))

    def test_plan_impact_preset_decision_skips_the_question(self):
        self.env["CODE_STEP_IMPACT_DECISION"] = "adopt"
        report = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes"
        out = self.coder_round(report)
        self.assertNotIn("ACTION: ask-user", out)
        self.assertIn("AGENT: coder", out)
        self.assertIn("Edit only the plan file", out)
        out = self.step("after-plan-edit")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("Decision: Adopt plan change", out)
        self.assertIn("## Plan Deviations", self.plan_text())

    def test_adopt_rewrites_the_plan_before_the_review(self):
        report = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes"
        self.coder_round(report)
        out = self.step("decide", "adopt", "--ruling", "adopt it, drop the header")
        self.assertIn("AGENT: coder", out)
        self.assertNotIn("AGENT: review-loop", out)
        self.assertEqual("plan-coder", self.state()["stage"])
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        out = self.step("after-plan-edit")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("flagged: none", out)
        self.assertIn("now states the ruling", self.said())

    def test_review_packet_block_scalar_reaches_the_question_without_its_indicator(self):
        self.coder_round()
        self.hook("review-loop", "status: plan-impact\niter: 1\nplan_impact: |\n    PLAN-IMPACT:\n      found: B\n")
        self.step("after-review")
        self.assertEqual("PLAN-IMPACT:\n  found: B", self.state()["impact"])

    def test_phase_one_converged_stops_with_block_b_and_marks_done(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: stop-block-B", out)
        self.assertMarkedClean(out)
        self.assertNotIn("Phase 1 complete.", out)
        self.assertIn("Phase 1 complete. Risk: low - Phase 1 calibration", self.said())
        self.assertNotIn("<<STAGE QUEUE>>", self.said())
        self.assertIn("### Fixed", self.said())
        self.assertIn("- [x] Phase 1:", self.plan_text())
        self.assertIn("- [ ] Phase 2:", self.plan_text())

    def test_failed_prohibition_blocks_marking(self):
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("Automated Verification failed", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        self.assertIn("scan=prohibition", self.log.read_text())

    FENCED_MANUAL_ITEM = "- [ ] **Manual-verified** (agent-verified): hit /orders\n  ```\n  curl /orders\n  ```"

    def break_manual_section(self):
        # Returns the 1-based file line of the bad row.
        old = "- [ ] **Manual-verified** (agent-verified): hit /orders"
        text = self.plan_text()
        self.assertIn(old, text)
        (self.repo / self.plan).write_text(text.replace(old, self.FENCED_MANUAL_ITEM))
        return text[:text.index(old)].count("\n") + 2

    def test_a_manual_verification_format_stop_names_the_file_line_and_verify_resumes(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        badLine = self.break_manual_section()
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertEqual("plan-format", self.state()["stopReason"])
        self.assertIn(f"{self.plan}:{badLine}:", out)
        self.assertIn("code-step.py verify", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        (self.repo / self.plan).write_text(self.plan_text().replace(self.FENCED_MANUAL_ITEM,
                                                                  "- [ ] **Manual-verified** (agent-verified): hit /orders"))
        out = self.step("verify")
        self.assertIn("ACTION: stop-block-B", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_start_stops_on_a_manual_verification_section_that_does_not_parse(self):
        badLine = self.break_manual_section()
        out = self.start_phase_one()
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn(f"{self.plan}:{badLine}:", out)

    def test_plan_check_reports_a_manual_verification_section_that_does_not_parse(self):
        badLine = self.break_manual_section()
        result = run(self.repo, self.env, "plan", "check", self.plan)
        self.assertEqual(1, result.returncode)
        self.assertIn(f"{self.plan}:{badLine}:", result.stdout)

    def test_a_converged_packet_with_a_labelled_ask_list_asks_the_user(self):
        self.coder_round()
        asks = "\n".join(f'  - {{question: "q{n}", file_line: "backend/src/orders.ts:{n}", gate: code-reviewer}}'
                         for n in (1, 2, 3))
        self.hook("review-loop", f"status: converged\niter: 1\nfixed: []\nask (for the user):\n{asks}")
        out = self.step("after-review")
        self.assertIn("ACTION: ask-user", out)
        self.assertEqual(3, len(self.state()["asks"]))
        self.assertEqual("asks", self.state()["stage"])

    def advance_to_phase_two(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        self.step("start")

    def test_low_risk_phase_two_auto_advances(self):
        self.advance_to_phase_two()
        self.assertEqual(self.state()["phase"], "2")
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: auto-advance", out)
        self.assertIn("Auto-advancing to Phase 3", self.said())

    def test_gate_cap_forces_stop_block(self):
        self.advance_to_phase_two()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals\nThere is an ambiguity in the rounding rule.")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: stop-block-B", out)
        self.assertIn("low - exception", self.said())

    def test_cap_reached_and_blocker_stop_without_marking(self):
        self.coder_round()
        self.hook("review-loop", "status: cap-reached\niter: 2\nfindings_remaining:\n  - finding: x\n    file_line: a.ts:1")
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def test_asks_flow_logs_outcomes(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        out = self.step("after-review")
        self.assertIn("ACTION: ask-user", out)
        self.assertMarkedClean(out)
        self.assertIn("`asks-done`", self.said())
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        out = self.step("asks-done", "accepted")
        self.assertIn("ask_outcome=accepted", self.log.read_text())
        self.assertIn("ACTION: dispatch", out)
        self.assertIn("AGENT: coder", out)
        self.assertIn("[accepted] f - keep? (backend/src/orders.ts:2)", out)
        self.assertNotIn("marked done", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        self.assertEqual("asks-coder", self.state()["stage"])
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("applied the ask", self.said())
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("Phase 1 marked done", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_rejected_asks_finish_the_phase_without_a_coder(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")
        out = self.step("asks-done", "rejected")
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("Phase 1 marked done", out)

    def test_preset_ask_outcome_records_and_applies_before_finishing(self):
        self.env["CODE_STEP_ASKS_OUTCOME"] = "accepted"
        self.coder_round()
        self.hook("review-loop", self.ASK)
        out = self.step("after-review")
        self.assertNotIn("present-asks-and-wait", out)
        self.assertIn("answered by the pre-set outcome 'accepted'", out)
        self.assertIn("ask_outcome=accepted", self.log.read_text())
        self.assertIn("AGENT: coder", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("Phase 1 marked done", out)
        self.assertMarkedClean(out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_say_hook_relays_and_empties_the_file(self):
        self.coder_round()
        expected = self.said().strip()
        self.assertTrue(expected)
        result = run(self.repo, self.env, "say-hook", stdin=json.dumps({"cwd": str(self.repo), "hook_event_name": "Stop"}))
        self.assertEqual(0, result.returncode)
        self.assertEqual({"systemMessage": expected}, json.loads(result.stdout))
        self.assertEqual("", self.said())
        self.assertIn(expected, (self.repo / ".git/code-step/say.log").read_text())
        again = run(self.repo, self.env, "say-hook", stdin=json.dumps({"cwd": str(self.repo)}))
        self.assertEqual("", again.stdout)

    def test_say_hook_is_silent_without_a_run(self):
        result = run(self.repo, self.env, "say-hook", stdin=json.dumps({"cwd": str(self.repo)}))
        self.assertEqual(("", 0), (result.stdout, result.returncode))
        result = run(self.repo, self.env, "say-hook", stdin="not json")
        self.assertEqual(0, result.returncode)

    def test_closing_phase_invokes_skill(self):
        text = self.plan_text()
        for n in (1, 2, 3):
            text = text.replace(f"- [ ] Phase {n}:", f"- [x] Phase {n}:")
        (self.repo / self.plan).write_text(text)
        out = self.step("start", self.plan)
        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("/refactor +deep", out)
        out = self.step("skill-done")
        self.assertIn("ACTION: stop-block-C", out)
        self.assertIn("All phases complete", self.said())

    def test_planless_task(self):
        out = self.step("start", "--task", "add a flag")
        self.assertIn("Implement: add a flag", out)
        self.assertEqual(self.state()["plan"], None)


    # ---------- defects from the code review ----------

    def test_start_clears_say_text_left_by_an_aborted_run(self):
        self.start_phase_one()
        (self.repo / ".git/code-step/say.md").write_text("Phase 3 complete. Auto-advancing to Phase 4\n")
        self.start_phase_one()
        self.assertEqual("", self.said())

    def test_say_hook_drops_text_older_than_six_hours(self):
        self.coder_round()
        sayFile = self.repo / ".git/code-step/say.md"
        longAgo = time.time() - 7 * 3600
        os.utime(sayFile, (longAgo, longAgo))
        result = run(self.repo, self.env, "say-hook", stdin=json.dumps({"cwd": str(self.repo)}))
        self.assertEqual("", result.stdout)
        self.assertEqual("", self.said())

    def test_hook_saves_nothing_once_the_phase_is_done(self):
        self.finish_phase_one()
        reportsFile = self.repo / ".git/code-step/reports.jsonl"
        before = len(reportsFile.read_text().splitlines())
        self.hook("coder", "from another session")
        self.assertEqual(before, len(reportsFile.read_text().splitlines()))

    def test_hook_ignores_a_session_other_than_the_one_that_started_the_coder(self):
        self.start_phase_one()
        self.hook("coder", "mine")
        self.hook("coder", "theirs", agentId="a2", session="s2")
        rows = (self.repo / ".git/code-step/reports.jsonl").read_text().splitlines()
        self.assertEqual(["mine"], [json.loads(row)["message"] for row in rows])

    def test_bare_start_on_another_branch_resolves_the_plan_again(self):
        self.finish_phase_one()
        subprocess.run(["git", "checkout", "-q", "-b", "ABC-2"], cwd=self.repo, check=True, env=self.env)
        out = self.step("start")
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("ACTION: ask-user", out)
        self.assertIn("no task or plan resolves", self.said())

    SINGLE_PLAN = ("# Single\n\n**File**: `backend/src/orders.ts`\n\n#### Automated Verification:\n\n"
                   "- [ ] **Prohibition**: no console.log - `git grep -n --untracked console.log -- backend/src/orders.ts`\n")

    def use_single_phase_plan(self):
        self.plan = "docs/plans/single/spec.md"
        (self.repo / "docs/plans/single").mkdir()
        (self.repo / self.plan).write_text(self.SINGLE_PLAN)

    def test_finished_single_phase_plan_is_not_implemented_again(self):
        self.use_single_phase_plan()
        self.finish_phase_one()
        out = self.step("start")
        self.assertNotIn("AGENT: coder", out)

    def test_single_phase_plan_runs_its_verification_and_names_itself(self):
        self.use_single_phase_plan()
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("after-review"))

    def test_single_phase_plan_completion_text_has_no_phase_none(self):
        self.use_single_phase_plan()
        self.finish_phase_one()
        self.assertNotIn("Phase None", self.said())
        self.assertIn("The plan is complete", self.said())

    def test_coder_with_no_change_stops_instead_of_reviewing(self):
        self.start_phase_one()
        self.hook("coder", "Blocked: the schema is missing.")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: review-loop", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_coder_recommending_eng_spec_stops_instead_of_reviewing(self):
        self.begin_coder()
        self.hook("coder", "This is architectural, I recommend /eng-spec.")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: review-loop", out)

    def test_deleted_file_counts_as_changed(self):
        self.start_phase_one()
        (self.repo / "backend/src/existing.ts").unlink()
        self.hook("coder", "BEHAVIOR: removed the constant")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("- path: backend/src/existing.ts", out)

    def test_closing_phase_titles_must_be_the_closing_phase(self):
        titles = {"Refactor password hashing to argon2 (risk: high)": None, "Verify password reset tokens": None,
                  "Weekly recap email": None, "Refactor pass — /refactor +deep whole-branch sweep (risk: low)":
                  "/refactor +deep", "Verify pass (risk: high)": "/verify-branch", "Recap": "/branch-recap",
                  "Test audit — /test-audit cross-phase test gate (risk: high)": "/test-audit"}
        for title, expected in titles.items():
            found = next((skill for pattern, skill in code_step.CLOSING_PHASES if pattern.search(title)), None)
            self.assertEqual(expected, found, title)

    def test_closing_phase_prints_its_own_section(self):
        self.mark_phases_done(1, 2, 3)
        out = self.step("start", self.plan)
        self.assertIn("## Phase 4: Refactor pass", out)
        self.assertIn("Sweep.", out)

    def test_verify_pass_invokes_verify_branch_and_dispatches_no_reviewer(self):
        self.mark_phases_done(1, 2, 3)
        (self.repo / self.plan).write_text(self.plan_text().replace("Refactor pass - /refactor cleanup sweep",
                                                                    "Verify pass — deep review + /verify-branch"))
        out = self.step("start", self.plan)
        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("`/verify-branch`", out)
        self.assertIn("skill-done fail", out)
        self.assertIn("any MISSING criterion fails it", out)
        self.assertNotIn("AGENT: code-reviewer", out)
        self.assertNotIn("branch-wide deep review", out.lower().split("verify pass", 1)[0])

    def test_verify_pass_with_a_period_invokes_verify_branch(self):
        self.mark_phases_done(1, 2, 3)
        (self.repo / self.plan).write_text(self.plan_text().replace("Refactor pass - /refactor cleanup sweep",
                                                                    "Verify pass. Branch-wide deep review plus /verify-branch"))
        out = self.step("start", self.plan)
        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("`/verify-branch`", out)
        self.assertNotIn("AGENT: code-reviewer", out)

    def test_refactor_pass_with_a_period_invokes_refactor_deep(self):
        self.mark_phases_done(1, 2, 3)
        (self.repo / self.plan).write_text(self.plan_text().replace("Refactor pass - /refactor cleanup sweep",
                                                                    "Refactor pass. Whole-branch sweep"))
        out = self.step("start", self.plan)
        self.assertIn("/refactor +deep", out)

    def test_verify_pass_rate_fix_stays_a_coding_phase(self):
        self.mark_phases_done(1, 2, 3)
        (self.repo / self.plan).write_text(self.plan_text().replace("Refactor pass - /refactor cleanup sweep",
                                                                    "Verify pass rate fix (risk: high)"))
        out = self.step("start", self.plan)
        self.assertIn("AGENT: coder", out)
        self.assertNotIn("`/verify-branch`", out)

    def test_lettered_phases_run_in_order_and_are_marked_done(self):
        text = self.plan_text()
        for old, new in (("Phase 1", "Phase 6A"), ("Phase 2", "Phase 6B"), ("Phase 3", "Phase 7")):
            text = text.replace(old, new)
        (self.repo / self.plan).write_text(text)
        out = self.step("start", self.plan)
        self.assertIn("Implement Phase 6A of", out)
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("Phase 6A marked done", out)
        self.assertIn("- [x] Phase 6A:", self.plan_text())
        self.assertIn("- [ ] Phase 6B:", self.plan_text())
        self.commit_all()
        self.assertIn("Implement Phase 6B of", self.step("start"))

    def test_phase_section_lookup_keeps_six_and_six_a_apart(self):
        lines = ["## Phase 6A: x", "a", "## Phase 6: y", "b"]
        self.assertEqual("## Phase 6: y\nb", code_step.phase_text(lines, "6"))
        self.assertEqual("## Phase 6A: x\na", code_step.phase_text(lines, "6A"))

    def test_phase_status_line_formats_a_real_plan_can_use(self):
        lines = ["## Phase Status", "",
                 "- [ ] Phase 6C2: Deep id (risk: low).",
                 "- [X] Phase 7 — capital X and em dash (risk: high)",
                 "- [ ] Phase 8. Period after number (risk: Low)",
                 "-  [ ]  Phase  9:  Extra spaces (risk: low)",
                 "* [ ] Phase 10 – En dash and star bullet",
                 "- [ ] Phase 11: No risk tag"]
        entries = code_step.phase_status_entries(lines)
        self.assertEqual(["6C2", "7", "8", "9", "10", "11"], [e["number"] for e in entries])
        self.assertEqual(["low", "high", "low", "low", "high", "high"], [e["risk"] for e in entries])
        self.assertEqual([False, True, False, False, False, False], [e["done"] for e in entries])

    def test_logged_phase_id_shapes_parse_look_up_and_mark_done(self):
        ids = ["10.5", "8.6b", "4.6", "7.5", "8.6", "P4", "P9", "1-2", "6A-6D", "P9-slice-1"]
        statusLines = [f"- [ ] Phase {i}: Title {i} (risk: low)" for i in ids]
        sections = [f"## Phase {i}: Title {i}\nbody {i}" for i in ids]
        planPath = self.repo / "ids.md"
        planPath.write_text("\n".join(["## Phase Status", "", *statusLines, "", *sections, ""]))
        planLines = planPath.read_text().splitlines()
        self.assertEqual(ids, [e["number"] for e in code_step.phase_status_entries(planLines)])
        for i in ids:
            self.assertEqual(f"## Phase {i}: Title {i}\nbody {i}", code_step.phase_text(planLines, i))
            code_step.mark_phase_done(planPath, i)
        self.assertEqual([True] * len(ids), [e["done"] for e in code_step.phase_status_entries(
            planPath.read_text().splitlines())])

    def test_dotted_phase_section_is_not_the_whole_number_section(self):
        lines = ["## Phase 10.5: x", "a", "## Phase 10: y", "b"]
        self.assertEqual("## Phase 10: y\nb", code_step.phase_text(lines, "10"))

    def test_unparsed_phase_status_line_stops_with_its_line_number(self):
        (self.repo / self.plan).write_text(self.plan_text().replace("- [ ] Phase 2: Totals", "- [ ] Step two: Totals"))
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertIn("docs/plans/orders/spec.md:10: unparsed-line", out)
        self.assertIn("Step two: Totals", out)
        self.assertIn("- [ ] Phase <id>: <title>", out)

    def test_duplicate_phase_ids_stop_naming_both_lines(self):
        (self.repo / self.plan).write_text(self.plan_text().replace("Phase 2: Totals", "Phase 1: Totals"))
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertIn("Phase 1 twice", out)
        self.assertIn("line 9 and line 10", out)

    def test_verify_pass_after_a_two_digit_id_with_a_period_invokes_verify_branch(self):
        text = self.plan_text().replace("Phase 4: Refactor pass - /refactor cleanup sweep",
                                        "Phase 10. Verify pass. Branch-wide review")
        text = text.replace("## Phase 4: Refactor pass", "## Phase 10: Verify pass")
        (self.repo / self.plan).write_text(text)
        self.mark_phases_done(1, 2, 3)
        out = self.step("start", self.plan)
        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("Phase 10", out)
        self.assertNotIn("AGENT: code-reviewer", out)

    def test_closing_phase_without_a_section_passes_the_check_and_still_invokes_its_skill(self):
        text = self.plan_text().replace("## Phase 4: Refactor pass", "## Notes")
        (self.repo / self.plan).write_text(text)
        self.assertEqual(0, self.plan_check(text).returncode)
        self.mark_phases_done(1, 2, 3)
        out = self.step("start", self.plan)
        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("/refactor +deep", out)

    def test_coding_phase_without_a_section_still_fails_the_check(self):
        text = self.plan_text().replace("## Phase 2:", "## Notes 2:")
        self.assertEqual(1, self.plan_check(text).returncode)

    def plan_check(self, text):
        planPath = self.repo / "check.md"
        planPath.write_text(text)
        return run(self.repo, self.env, "plan", "check", str(planPath))

    def test_plan_check_names_each_failure_kind_and_exits_one(self):
        result = self.plan_check("## Phase Status\n\n- [ ] Phase 1: A\n- [ ] Phase 1: B\n- [ ] Step two\n"
                                 "- [ ] Phase 3: C\n\n## Phase 1: A\n\n### Phase 9: Added later\n")
        self.assertEqual(1, result.returncode)
        self.assertIn(":4: duplicate-id", result.stdout)
        self.assertIn(":5: unparsed-line", result.stdout)
        self.assertIn(":6: missing-section", result.stdout)
        self.assertIn(":10: section-without-status", result.stdout)
        self.assertIn("Add `- [ ] Phase 9: Added later`", result.stdout)

    def test_plan_check_passes_a_clean_plan_with_any_heading_level_and_indented_notes(self):
        result = self.plan_check("## Phase Status\n\n- [ ] Phase 1: A\n  - [ ] note under one\n- [ ] Phase 2: B\n"
                                 "- [ ] Phase 3.5: C\n\n## Phase 1: A\n\n### Phase 2: B\n\n#### Phase 3.5: C\n")
        self.assertEqual((0, ""), (result.returncode, result.stdout))

    def test_plan_parse_prints_entries_sections_and_failures_as_json(self):
        planPath = self.repo / "check.md"
        planPath.write_text("## Phase Status\n\n- [x] Phase P9-slice-1: A (risk: low)\n\n## Phase P9-slice-1: A\n")
        parsed = json.loads(run(self.repo, self.env, "plan", "parse", str(planPath), "--json").stdout)
        self.assertEqual(["P9-slice-1"], [e["number"] for e in parsed["entries"]])
        self.assertEqual(["P9-slice-1"], list(parsed["sections"]))
        self.assertEqual([], parsed["failures"])

    def test_closing_phase_waits_for_every_coding_phase(self):
        text = self.plan_text()
        closing = "- [ ] Phase 4: Refactor pass - /refactor cleanup sweep (risk: low)\n"
        text = text.replace(closing, "").replace("- [ ] Phase 2:", closing + "- [ ] Phase 2:")
        (self.repo / self.plan).write_text(text.replace("- [ ] Phase 1:", "- [x] Phase 1:"))
        self.assertIn("Implement Phase 2 of", self.step("start", self.plan))

    def test_finishing_a_coding_phase_unchecks_checked_closing_phases(self):
        self.mark_phases_done(1, 2, 4)
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("Phase 3 marked done", out)
        self.assertIn("Closing phase(s) 4 were checked and are unchecked again", out)
        self.assertIn("- [ ] Phase 4:", self.plan_text())

    def test_steps_added_to_the_phase_during_the_run_get_their_own_coder_before_the_review(self):
        self.begin_coder()
        (self.repo / self.plan).write_text(self.plan_text().replace(
            "## Phase 2: Totals", "- Add a CSV export.\n\n## Phase 2: Totals"))
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        out = self.step("after-coder")
        self.assertIn("AGENT: coder", out)
        self.assertIn("Add a CSV export.", out)
        self.hook("coder", "BEHAVIOR: csv export\nREVIEW: recommended", agentId="a2")
        self.assertNotIn("Add a CSV export.", self.step("after-coder"))

    def test_plan_hook_prints_failures_only_for_an_edit_of_the_active_plan(self):
        self.start_phase_one()
        (self.repo / self.plan).write_text(self.plan_text().replace("- [ ] Phase 2: Totals", "- [ ] Step two"))
        event = {"cwd": str(self.repo), "tool_input": {"file_path": str(self.repo / self.plan)}}
        result = run(self.repo, self.env, "plan-hook", stdin=json.dumps(event))
        self.assertEqual(2, result.returncode)
        self.assertIn("unparsed-line", result.stderr)
        event["tool_input"]["file_path"] = str(self.repo / "backend/src/orders.ts")
        self.assertEqual(0, run(self.repo, self.env, "plan-hook", stdin=json.dumps(event)).returncode)

    def test_plan_hook_during_a_hook_stage_exits_2_and_names_the_bad_manual_verification_line(self):
        self.start_phase_one()
        okLine = "- [ ] **Manual-verified** (agent-verified): hit /orders"
        (self.repo / self.plan).write_text(self.plan_text().replace(okLine, okLine + "\n> a quoted line"))
        badLineNumber = self.plan_text().splitlines().index("> a quoted line") + 1
        self.assertEqual("coder", self.state()["stage"])
        event = {"cwd": str(self.repo), "tool_input": {"file_path": str(self.repo / self.plan)}}
        result = run(self.repo, self.env, "plan-hook", stdin=json.dumps(event))
        self.assertEqual(2, result.returncode)
        self.assertIn(f"spec.md:{badLineNumber}:", result.stderr)

    def test_manual_items_are_listed_as_verified_not_yet_run_and_human_only(self):
        okLine = "- [ ] **Manual-verified** (agent-verified): hit /orders"
        (self.repo / self.plan).write_text(self.plan_text().replace(
            okLine, okLine + "\n- [x] ticked by the coder\n- [ ] run the export\n- [ ] human-only: judge the layout"
            "\n- [x] human-only: ticked layout"))
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        said = self.said()
        verifiedList = said.split("Verified (checked, or marked agent-verified in the plan):")[1].split("Agent-run")[0]
        self.assertIn("hit /orders", verifiedList)
        self.assertIn("ticked by the coder", verifiedList)
        self.assertNotIn("run the export", verifiedList)
        self.assertIn("ticked layout", verifiedList)
        self.assertNotIn("ticked layout", said.split("Human-only verification remaining:")[1])
        self.assertIn("Verified (checked, or marked agent-verified in the plan):", said)
        self.assertIn("Agent-run, not yet run (/verify-branch runs these at the end of the branch):", said)
        self.assertIn("Human-only verification remaining:", said)
        notRunList = said.split("not yet run (/verify-branch runs these at the end of the branch):")[1]
        self.assertIn("run the export", notRunList.split("Human-only verification remaining:")[0])
        self.assertNotIn("run the export", said.split("Agent-run, not yet run")[0])
        self.assertNotIn("evidence in the plan", said)

    def phase_one_next_step_after(self, manualLine):
        okLine = "- [ ] **Manual-verified** (agent-verified): hit /orders"
        (self.repo / self.plan).write_text(self.plan_text().replace(okLine, manualLine))
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        return next(line for line in self.said().splitlines() if line.startswith("  1. "))

    def test_the_next_step_names_only_the_kinds_of_manual_item_the_phase_has(self):
        checkedOnly = self.phase_one_next_step_after("- [x] human-only: ticked layout")
        self.assertIn("spot-check the verified items", checkedOnly)
        self.assertNotIn("run the human-only items", checkedOnly)

    def test_the_next_step_for_an_unticked_human_only_item_does_not_ask_for_a_spot_check(self):
        humanOnly = self.phase_one_next_step_after("- [ ] human-only: judge the layout")
        self.assertIn("run the human-only items", humanOnly)
        self.assertNotIn("spot-check", humanOnly)

    def test_an_ask_that_repeats_one_text_in_finding_and_question_shows_it_once(self):
        self.coder_round()
        self.hook("review-loop", 'status: converged\niter: 1\nfixed: []\nask: [{"finding": "Is the cap right?", '
                  '"file_line": "backend/src/orders.ts:2", "gate": "code-reviewer", "class": "correctness"}]')
        out = self.step("after-review")
        self.assertIn("Is the cap right?", out + self.said())
        self.assertNotIn("Is the cap right? - Is the cap right?", out + self.said())

    def test_an_ask_with_a_finding_and_a_different_question_shows_both(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        out = self.step("after-review")
        self.assertIn("f - keep?", out + self.said())

    def leave_unreadable_packet(self):
        self.coder_round()
        self.hook("review-loop", "status: deferred\niter: 1\nfindings_remaining: []")
        return self.step("after-review")

    def test_an_unreadable_review_packet_stops_with_the_raw_packet_and_one_resume_command(self):
        out = self.leave_unreadable_packet()
        self.assertIn("ACTION: stop", out)
        self.assertIn("status: deferred", out)
        self.assertIn("invoke Skill code with `review-again`", out)
        self.assertNotIn("python3", out.split("invoke Skill code with `review-again`")[0].splitlines()[-1])
        self.assertEqual("stopped", self.state()["stage"])
        self.assertEqual("invalid-packet", self.state()["stopReason"])

    def test_review_again_after_an_unreadable_packet_dispatches_the_review_loop_on_the_same_diff(self):
        self.leave_unreadable_packet()
        out = self.step("review-again")
        self.assertIn("ACTION: dispatch", out)
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual("review", self.state()["stage"])
        self.hook("review-loop", self.LOOP_OK, agentId="a2")
        self.assertIn("ACTION: stop-block-B", self.step("after-review"))

    def test_review_again_after_a_failed_first_review_runs_the_structure_pass(self):
        first = self.leave_unreadable_packet()
        self.assertNotIn(self.SKIP_LINE, first)
        self.assertNotIn(self.SKIP_LINE, self.step("review-again"))

    def test_review_again_after_a_failed_re_review_keeps_the_structure_pass_skip(self):
        out = self.asks_follow_up(lambda: (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n"))
        self.assertIn(self.SKIP_LINE, out)
        self.hook("review-loop", "status: deferred\niter: 1\nfindings_remaining: []", agentId="a2")
        self.assertIn("review-again", self.step("after-review"))
        self.assertEqual("invalid-packet", self.state()["stopReason"])
        again = self.step("review-again")
        self.assertIn("AGENT: review-loop", again)
        self.assertIn(self.SKIP_LINE, again)

    def test_review_again_with_no_unreadable_packet_pending_stops(self):
        self.start_phase_one()
        self.assertIn("ACTION: stop", self.step("review-again"))
        self.assertEqual("coder", self.state()["stage"])

    def mark_phases_done(self, *numbers):
        text = self.plan_text()
        for n in numbers:
            text = text.replace(f"- [ ] Phase {n}:", f"- [x] Phase {n}:")
        (self.repo / self.plan).write_text(text)

    def test_skill_done_fail_stops_without_marking(self):
        self.mark_phases_done(1, 2, 3)
        self.step("start", self.plan)
        out = self.step("skill-done", "fail")
        self.assertIn("ACTION: stop", out)
        self.assertIn("- [ ] Phase 4:", self.plan_text())
        self.assertEqual("stopped", self.state()["stage"])

    def test_closing_phase_block_has_no_derive_placeholder(self):
        self.mark_phases_done(1, 2, 3)
        self.step("start", self.plan)
        self.step("skill-done", "pass")
        self.assertNotIn("<derive from the diff>", self.said())
        self.assertNotIn("Behavior delta", self.said())

    def test_restarting_an_unfinished_phase_keeps_the_first_baseline(self):
        self.start_phase_one()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        out = self.coder_round()
        self.assertIn("- path: backend/src/orders.ts", out)

    def test_failed_verification_can_be_rerun_with_verify(self):
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("after-review"))
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        out = self.step("verify")
        self.assertIn("Phase 1 marked done", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_start_does_not_inherit_the_fast_modifier(self):
        self.assertIn("MODEL: haiku", self.start_phase_one("+fast"))
        out = self.step("start")
        self.assertNotIn("MODEL: haiku", out)
        self.assertIn("AGENT: coder", out)

    def test_auto_advance_names_the_modifier(self):
        self.finish_phase_one()
        self.step("start", "+fast")
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: auto-advance", out)
        self.assertIn("code-step.py start +fast", out)

    def test_ticket_id_and_directory_arguments_resolve_the_plan(self):
        shutil.copytree(self.repo / "docs/plans/orders", self.repo / "docs/plans/ABC-400-x")
        out = self.step("start", "ABC-400")
        self.assertIn("Implement Phase 1 of `docs/plans/ABC-400-x/spec.md`", out)
        out = self.step("start", "docs/plans/orders")
        self.assertIn("Implement Phase 1 of `docs/plans/orders/spec.md`", out)

    def test_free_text_arguments_become_the_task(self):
        out = self.step("start", "fix", "the", "export", "button")
        self.assertIn("Implement: fix the export button", out)
        self.assertNotIn("No plan file", out)

    def test_plan_outside_the_repo_asks_for_one_inside(self):
        outside = self.tmp / "outside.md"
        outside.write_text(PLAN)
        result = run(self.repo, self.env, "start", str(outside))
        self.assertIn("ACTION: ask-user", result.stdout)
        self.assertIn("outside the repo", self.said())
        self.assertEqual("", result.stderr)

    def test_missing_plan_at_the_phase_gates_stops(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        (self.repo / self.plan).unlink()
        self.assertIn("ACTION: stop", self.step("after-review"))

    def test_missing_plan_at_decide_stops(self):
        self.coder_round("PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes")
        (self.repo / self.plan).unlink()
        self.assertIn("ACTION: stop", self.step("decide", "keep", "--ruling", "keep it"))

    def test_unreadable_state_file_stops_with_its_name(self):
        self.start_phase_one()
        (self.repo / ".git/code-step/state.json").write_text("{")
        result = run(self.repo, self.env, "after-coder")
        self.assertIn("ACTION: stop", result.stdout)
        self.assertIn("state.json", result.stdout)

    def test_torn_report_line_is_skipped(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: orders exist")
        with (self.repo / ".git/code-step/reports.jsonl").open("a") as reportsFile:
            reportsFile.write('{"agent_type": "cod\n')
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

    def test_plan_impact_survives_a_retry_that_sends_only_the_fix(self):
        self.begin_coder()
        self.hook("coder", "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes")
        self.hook("coder", "fixed the lint error")
        self.assertIn("ACTION: ask-user", self.step("after-coder"))

    def test_iter_with_a_budget_suffix_reads_the_first_number(self):
        self.coder_round()
        self.hook("review-loop", "status: converged\niter: 2 of 2\nfixed: []\nask: []")
        self.step("after-review")
        self.assertEqual(2, self.state()["iter"])

    def test_plan_impact_status_with_no_description_stops(self):
        self.coder_round()
        self.hook("review-loop", "status: plan-impact\niter: 1\nplan_impact:\n")
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("ACTION: ask-user", out)

    def test_no_ambiguity_line_does_not_force_block_b(self):
        self.finish_phase_one()
        self.step("start")
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals\nNo ambiguities found.\nThe spec was unambiguous.")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("ACTION: auto-advance", self.step("after-review"))

    def test_slow_verification_command_times_out(self):
        self.env["CODE_STEP_VERIFY_TIMEOUT"] = "1"
        self.set_verification('- [ ] **Slow**: `python3 -c "import time; time.sleep(20)"`')
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        started = time.time()
        out = self.step("after-review")
        self.assertLess(time.time() - started, 15)
        self.assertIn("timed out after 1 seconds", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def test_other_test_scripts_are_run_not_skipped(self):
        for command in ("npm run test:e2e", "npm run lint:fix", "npx vitest run src/a.test.ts"):
            self.assertIsNone(code_step.WHOLE_SUITE.match(command), command)
        for command in ("cd backend && npm test", "npm run lint", "npx vitest run", "pytest", "ruff check"):
            self.assertIsNotNone(code_step.WHOLE_SUITE.match(command), command)
        self.env["CODE_STEP_VERIFY_TIMEOUT"] = "5"
        self.set_verification("- [ ] **E2E**: `bash -c 'exit 3'`")
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("after-review"))

    def test_prohibition_that_errors_fails_instead_of_passing(self):
        self.set_verification("- [ ] **Prohibition**: bad pattern - `git grep -nE '(foo' -- backend`")
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("after-review"))
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def test_prohibition_pipe_form_is_judged_by_its_output(self):
        self.set_verification("- [ ] **Prohibition**: none - `git grep -n console.log -- backend/src/orders.ts | wc -l`")
        self.finish_phase_one()
        self.assertIn("- [x] Phase 1:", self.plan_text())


    # ---------- defects from the second code review ----------

    def apply_first_ask(self, outcome="accepted", *extra):
        self.coder_round()
        self.hook("review-loop", self.ASK.replace("iter: 1", "iter: 2"))
        self.step("after-review")
        return self.step("asks-done", outcome, *extra)

    def test_re_review_after_the_asks_coder_starts_the_loop_count_again(self):
        self.apply_first_ask()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("iter: 0", out)
        self.assertNotIn("iter: 2", out)

    def test_re_review_after_the_asks_coder_covers_only_the_files_it_changed(self):
        self.begin_coder()
        (self.repo / "backend/src/extra.ts").write_text("export const e = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist")
        self.step("after-coder")
        self.hook("review-loop", self.ASK.replace("iter: 1", "iter: 2"))
        self.step("after-review")
        self.step("asks-done", "accepted")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("path: backend/src/orders.ts", out)
        self.assertNotIn("backend/src/extra.ts", out)
        self.assertIn("prior-issues:", out)

    SKIP_LINE = "structure-pass: skip"
    IMPACT_REPORT = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes"

    def asks_follow_up(self, writeFiles):
        self.apply_first_ask()
        writeFiles()
        self.hook("coder", "BEHAVIOR: applied the ask")
        return self.step("after-coder")

    def test_the_first_review_of_a_phase_never_skips_the_structure_pass(self):
        out = self.coder_round()
        self.assertIn("AGENT: review-loop", out)
        self.assertNotIn(self.SKIP_LINE, out)

    def test_small_asks_follow_up_re_review_skips_the_structure_pass(self):
        out = self.asks_follow_up(lambda: (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n"))
        self.assertIn("AGENT: review-loop", out)
        self.assertIn(self.SKIP_LINE, out)
        self.assertIn("iter: 0", out)

    def test_asks_follow_up_of_forty_added_lines_keeps_the_structure_pass(self):
        big = "".join(f"export const v{i} = {i}\n" for i in range(41))
        out = self.asks_follow_up(lambda: (self.repo / "backend/src/orders.ts").write_text(big))
        self.assertIn("AGENT: review-loop", out)
        self.assertNotIn(self.SKIP_LINE, out)
        self.assertIn("iter: 0", out)

    def test_asks_follow_up_with_a_new_source_file_keeps_the_structure_pass(self):
        def write():
            (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
            (self.repo / "backend/src/helper.ts").write_text("export const h = 1\n")
        out = self.asks_follow_up(write)
        self.assertNotIn(self.SKIP_LINE, out)

    def test_asks_follow_up_counts_only_its_own_lines_not_the_first_coders(self):
        big = "".join(f"export const v{i} = {i}\n" for i in range(60))
        self.begin_coder(big)
        self.hook("coder", "BEHAVIOR: orders exist")
        self.step("after-coder")
        self.hook("review-loop", self.ASK.replace("iter: 1", "iter: 2"))
        self.step("after-review")
        self.step("asks-done", "accepted")
        (self.repo / "backend/src/orders.ts").write_text(big + "export const extra = 1\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        out = self.step("after-coder")
        self.assertIn(self.SKIP_LINE, out)

    def test_asks_follow_up_that_only_adds_a_large_test_and_lockfile_stays_small(self):
        def write():
            (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
            (self.repo / "backend/src/orders.test.ts").write_text("t\n" * 80)
            (self.repo / "package-lock.json").write_text("{}\n" * 80)
        out = self.asks_follow_up(write)
        self.assertIn(self.SKIP_LINE, out)

    def test_ruling_that_keeps_the_plan_after_a_review_skips_the_structure_pass(self):
        self.coder_round()
        self.hook("review-loop", "status: plan-impact\niter: 1\nplan_impact: |\n    PLAN-IMPACT:\n      found: B\n")
        self.step("after-review")
        out = self.step("decide", "keep", "--ruling", "keep it")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn(self.SKIP_LINE, out)
        self.assertIn("iter: 0", out)

    def test_ruling_raised_by_the_coder_before_any_review_gets_a_full_first_review(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "keep", "--ruling", "keep it")
        self.assertIn("AGENT: review-loop", out)
        self.assertNotIn(self.SKIP_LINE, out)

    def test_adopted_plan_change_after_a_review_refreshes_the_phase_text_and_reviews_once(self):
        self.coder_round()
        self.hook("review-loop", "status: plan-impact\niter: 1\nplan_impact: |\n    PLAN-IMPACT:\n      found: B\n")
        self.step("after-review")
        out = self.step("decide", "adopt", "--ruling", "adopt it")
        self.assertIn("AGENT: coder", out)
        (self.repo / self.plan).write_text(self.plan_text().replace(
            "## Phase 2", "Adopted step: drop the header.\n\n## Phase 2", 1))
        out = self.step("after-plan-edit")
        self.assertIn("AGENT: review-loop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn(self.SKIP_LINE, out)
        self.assertIn("Adopted step: drop the header.", self.state()["phaseText"])
        repeated = self.step("after-plan-edit")
        self.assertIn("ACTION: stop", repeated)
        self.assertNotIn("AGENT:", repeated)
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertNotIn("AGENT: coder", out)
        self.assertNotIn("gained lines", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_asks_coder_that_changed_only_docs_sends_no_review_and_finishes_the_phase(self):
        self.apply_first_ask()
        (self.repo / "backend/README.md").write_text("orders\n")
        self.hook("coder", "BEHAVIOR: documented the ask")
        out = self.step("after-coder")
        self.assertNotIn("AGENT: review-loop", out)
        self.assertIn("Phase 1 marked done", out)
        self.assertMarkedClean(out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_first_coder_run_lists_every_file_the_phase_changed(self):
        self.begin_coder()
        (self.repo / "backend/src/extra.ts").write_text("export const e = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist")
        out = self.step("after-coder")
        self.assertIn("path: backend/src/orders.ts", out)
        self.assertIn("path: backend/src/extra.ts", out)

    def test_asks_coder_that_changed_nothing_stops_instead_of_reviewing(self):
        self.apply_first_ask()
        self.hook("coder", "Could not apply the rename; left as is.")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: review-loop", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_re_review_after_the_asks_coder_gets_the_accepted_asks_as_prior_issues(self):
        self.apply_first_ask()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        out = self.step("after-coder")
        self.assertIn("prior-issues:", out)
        self.assertIn("issue: f - keep?", out)
        self.assertIn("file: backend/src/orders.ts", out)

    def test_modified_ask_carries_the_user_change_into_the_asks_coder_prompt(self):
        out = self.apply_first_ask("modified", "--change", "rename it to orderCount")
        self.assertIn("AGENT: coder", out)
        self.assertIn("[modified] f - keep?", out)
        self.assertIn("The user's change: rename it to orderCount", out)
        self.assertNotIn("add the user's exact change", out)

    def test_modified_ask_without_a_change_text_stops(self):
        out = self.apply_first_ask("modified")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertEqual("asks", self.state()["stage"])

    def test_preset_outcome_does_not_swallow_a_new_ask_from_the_second_review(self):
        self.env["CODE_STEP_ASKS_OUTCOME"] = "accepted"
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        self.step("after-coder")
        self.hook("review-loop", self.ASK.replace("keep?", "extract a helper?"))
        out = self.step("after-review")
        self.assertIn("ACTION: ask-user", out)
        self.assertIn("extract a helper?", self.said())
        self.assertNotIn("Phase 1 marked done", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        self.assertEqual("asks", self.state()["stage"])

    def test_bare_start_after_a_single_phase_plan_resolved_through_the_branch_answers_complete(self):
        subprocess.run(["git", "checkout", "-q", "-b", "ABC-1-x"], cwd=self.repo, check=True, env=self.env)
        self.plan = "docs/plans/ABC-1-x/spec.md"
        (self.repo / "docs/plans/ABC-1-x").mkdir()
        (self.repo / self.plan).write_text(self.SINGLE_PLAN)
        for command in (["git", "add", "-A"], ["git", "commit", "-qm", "plan"]):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True, env=self.env)
        self.finish_phase_one()
        out = self.step("start")
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("plan", out)
        self.assertIn("is complete", out)

    def test_ambiguous_wording_is_flagged_but_unambiguous_is_not(self):
        self.assertEqual(["The plan is ambiguous about rounding."],
                         code_step.coder_flags("The plan is ambiguous about rounding."))
        self.assertEqual(["Two ambiguities remain."], code_step.coder_flags("Two ambiguities remain."))
        self.assertEqual([], code_step.coder_flags("The spec was unambiguous."))
        self.assertEqual([], code_step.coder_flags("No ambiguities found."))

    def test_start_clears_say_text_left_by_a_finished_phase_but_keeps_the_auto_advance_text(self):
        self.finish_phase_one()
        self.assertIn("Phase 1 complete", self.said())
        self.step("start")
        self.assertEqual("", self.said())
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("ACTION: auto-advance", self.step("after-review"))
        self.step("start")
        self.assertIn("Auto-advancing to Phase 3", self.said())


    # ---------- plan grammar: fences and duplicate sections ----------

    def test_a_hash_line_inside_a_code_fence_does_not_end_a_phase_section(self):
        lines = ("# T\n## Phase Status\n- [ ] Phase 1: A\n- [ ] Phase 2: B\n## Phase 1: A\n```bash\n# install\nnpm i\n"
                 "```\nmore text\n## Phase 2: B\n").split("\n")
        plan = code_step.parse_plan(lines)
        self.assertEqual((4, 10), (plan["sections"]["1"]["start"], plan["sections"]["1"]["end"]))
        self.assertIn("# install", code_step.phase_text(lines, "1"))
        self.assertIn("more text", code_step.phase_text(lines, "1"))

    def test_a_tilde_fence_and_an_indented_fence_hide_headings_too(self):
        lines = ("## Phase Status\n- [ ] Phase 1: A\n## Phase 1: A\n~~~\n## Not a section\n~~~\n  - step\n"
                 "    ```sh\n    # comment\n    ```\ntail\n").split("\n")
        plan = code_step.parse_plan(lines)
        self.assertEqual(len(lines), plan["sections"]["1"]["end"])
        self.assertEqual([], plan["failures"])

    def test_phase_headings_and_status_lines_inside_a_fence_are_not_sections_or_entries(self):
        lines = ("# T\n## Phase Status\n- [ ] Phase 1: A\n```\n## Phase 9: fake\n- [ ] Phase 8: fake\n```\n"
                 "## Phase 1: A\n").split("\n")
        plan = code_step.parse_plan(lines)
        self.assertEqual(["1"], list(plan["sections"]))
        self.assertEqual(["1"], [entry["number"] for entry in plan["entries"]])
        self.assertEqual([], plan["failures"])

    def test_two_sections_with_the_same_phase_id_are_a_duplicate_id_failure(self):
        lines = "# T\n## Phase Status\n- [ ] Phase 1: A\n## Phase 1: A\nx\n## Phase 1: A again\n".split("\n")
        failures = code_step.parse_plan(lines)["failures"]
        self.assertEqual([(6, "duplicate-id")], [(f["line"], f["kind"]) for f in failures])
        self.assertIn("line 4", failures[0]["detail"])
        result = self.plan_check("\n".join(lines))
        self.assertEqual(1, result.returncode)
        self.assertIn(":6: duplicate-id", result.stdout)

    # ---------- the addendum coder fires only on added lines ----------

    def added_lines_after(self, edit):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = pathlib.Path(directory.name)
        plan = ("# P\n## Phase Status\n- [ ] Phase 1: A (risk: low)\n## Phase 1: A\nDo a.\n\n#### Manual Verification:\n"
                "- [ ] check it\n## Phase 2: B\nx\n")
        (root / "plan.md").write_text(edit(plan))
        state = {"plan": "plan.md", "phase": "1", "phaseText": code_step.phase_text(plan.split("\n"), "1")}
        return code_step.added_phase_lines(root, state)

    def test_ticking_a_checkbox_is_not_an_added_line(self):
        self.assertIsNone(self.added_lines_after(lambda p: p.replace("- [ ] check it", "- [x] check it")))

    def test_an_added_blank_line_or_trailing_space_is_not_an_added_line(self):
        self.assertIsNone(self.added_lines_after(lambda p: p.replace("Do a.\n", "Do a.\n\n")))
        self.assertIsNone(self.added_lines_after(lambda p: p.replace("Do a.", "Do a. ")))

    def test_a_real_added_step_is_still_an_added_line(self):
        found = self.added_lines_after(lambda p: p.replace("Do a.\n", "Do a.\nAlso do b.\n"))
        self.assertEqual(["Also do b."], found["added"])

    # ---------- plan-hook ignores malformed input ----------

    def test_plan_hook_exits_zero_and_silent_on_every_malformed_input(self):
        self.start_phase_one()
        cases = ["[1]", "null", "7", '"text"', "not json", "", "{}", json.dumps({"cwd": str(self.repo), "tool_input": []}),
                 json.dumps({"cwd": str(self.repo), "tool_input": "x"}),
                 json.dumps({"cwd": str(self.repo), "tool_input": {"file_path": 5}}),
                 json.dumps({"cwd": 5, "tool_input": {"file_path": "a"}})]
        for stdin in cases:
            with self.subTest(stdin=stdin):
                result = run(self.repo, self.env, "plan-hook", stdin=stdin)
                self.assertEqual((0, "", ""), (result.returncode, result.stdout, result.stderr))

    # ---------- start flags ----------

    def test_start_help_prints_usage_and_writes_no_state(self):
        result = run(self.repo, self.env, "start", "--help")
        self.assertEqual(0, result.returncode)
        self.assertIn("usage: code-step.py start", result.stdout)
        self.assertNotIn("ACTION: dispatch", result.stdout)
        self.assertFalse((self.repo / ".git/code-step").exists())

    def test_start_with_an_unknown_flag_exits_two_with_usage_and_writes_no_state(self):
        result = run(self.repo, self.env, "start", self.plan, "--bogus")
        self.assertEqual(2, result.returncode)
        self.assertIn("usage: code-step.py start", result.stderr)
        self.assertIn("--bogus", result.stderr)
        self.assertFalse((self.repo / ".git/code-step").exists())

    def test_start_phase_flag_starts_the_named_phase(self):
        out = self.step("start", self.plan, "--phase", "2")
        self.assertIn("Implement Phase 2 of `docs/plans/orders/spec.md`", out)
        self.assertEqual("2", self.state()["phase"])

    def test_start_phase_flag_with_an_unlisted_id_stops_and_names_it(self):
        out = self.step("start", self.plan, "--phase", "9")
        self.assertIn("ACTION: stop", out)
        self.assertIn("Phase 9", out)
        self.assertNotIn("AGENT: coder", out)

    def test_start_phase_flag_without_an_id_exits_two(self):
        result = run(self.repo, self.env, "start", self.plan, "--phase")
        self.assertEqual(2, result.returncode)
        self.assertIn("usage: code-step.py start", result.stderr)

    def test_start_task_text_after_the_task_flag_may_hold_dashes(self):
        out = self.step("start", "--task", "fix the --verbose flag")
        self.assertIn("AGENT: coder", out)
        self.assertIn("fix the --verbose flag", out)

    # ---------- blocking wait for the hand-back row ----------

    def own_command(self, verb):
        # Printed commands name the running script by its real path.
        return f"python3 {SCRIPT.resolve()} {verb}"

    def wait_env(self, seconds, interval="0.1"):
        self.env.update(CODE_STEP_WAIT_SECONDS=str(seconds), CODE_STEP_POLL_SECONDS=interval)

    def late_hook(self, delay, agentType, message):
        timer = threading.Timer(delay, self.hook, args=(agentType, message))
        self.addCleanup(timer.cancel)
        timer.start()
        return timer

    CODER_REPORT = "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters\nREVIEW: recommended"

    def test_after_coder_waits_for_the_coder_row_written_a_second_later(self):
        self.begin_coder()
        self.wait_env(20)
        self.late_hook(1, "coder", self.CODER_REPORT)
        started = time.monotonic()
        out = self.step("after-coder")
        self.assertGreaterEqual(time.monotonic() - started, 0.9)
        self.assertIn("AGENT: review-loop", out)

    def test_after_coder_with_no_row_times_out_and_says_to_run_the_same_command_again(self):
        self.begin_coder()
        self.wait_env(1, "0.2")
        started = time.monotonic()
        out = self.step("after-coder")
        self.assertLess(time.monotonic() - started, 10)
        self.assertIn("ACTION: wait", out)
        self.assertIn(f"run the same command again: `{self.own_command('after-coder')}`", out)
        self.assertNotIn("AGENT:", out)
        self.assertEqual("coder", self.state()["stage"])
        self.hook("coder", self.CODER_REPORT)
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

    def test_a_coder_row_from_before_the_dispatch_does_not_end_the_wait(self):
        self.begin_coder()
        self.hook("coder", self.CODER_REPORT)
        time.sleep(0.05)
        self.start_phase_one()
        self.wait_env(1, "0.2")
        self.assertIn("ACTION: wait", self.step("after-coder"))

    def test_after_review_waits_for_a_review_loop_row_newer_than_the_review_dispatch(self):
        self.coder_round()
        self.wait_env(1, "0.2")
        out = self.step("after-review")
        self.assertIn("ACTION: wait", out)
        self.assertIn(f"`{self.own_command('after-review')}`", out)
        self.wait_env(20)
        self.late_hook(1, "review-loop", self.LOOP_OK)
        self.assertIn("ACTION: stop-block-B", self.step("after-review"))

    def test_a_zero_wait_limit_skips_the_wait_and_reports_the_missing_row(self):
        self.begin_coder()
        out = self.step("after-coder")
        self.assertIn("No coder report was saved", out)

    # ---------- the fork's own hand-back ----------

    def fork_handback(self, session=SESSION):
        return self.hook("general-purpose", "waiting", agentId="fork", session=session)

    def test_fork_handback_while_the_coder_is_out_is_denied_once_naming_the_wait_command(self):
        self.start_phase_one()
        first = json.loads(self.fork_handback().stdout)["hookSpecificOutput"]
        self.assertEqual("deny", first["permissionDecision"])
        self.assertIn(self.own_command("after-coder"), first["permissionDecisionReason"])
        self.assertEqual("", self.fork_handback().stdout)

    def test_fork_handback_names_after_review_while_the_review_loop_is_out(self):
        self.coder_round()
        reason = json.loads(self.fork_handback().stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn(self.own_command("after-review"), reason)

    def test_a_new_dispatch_arms_the_fork_denial_again(self):
        self.start_phase_one()
        self.fork_handback()
        self.assertEqual("", self.fork_handback().stdout)
        self.start_phase_one()
        self.assertIn("deny", self.fork_handback().stdout)

    def test_fork_handback_passes_once_the_dispatched_agent_has_a_row(self):
        self.start_phase_one()
        self.set_gate_result("pass")
        self.hook("coder", self.CODER_REPORT)
        self.assertEqual("", self.fork_handback().stdout)

    def test_coder_and_review_loop_handbacks_are_never_denied(self):
        self.start_phase_one()
        self.assertEqual("", self.hook("coder", self.CODER_REPORT).stdout)
        self.assertEqual("", self.hook("review-loop", "status: converged").stdout)

    def test_fork_handback_passes_with_no_run_open_or_from_another_session(self):
        self.assertEqual("", self.fork_handback().stdout)
        self.begin_coder()
        self.hook("coder", self.CODER_REPORT)
        self.step("after-coder")
        self.assertEqual("", self.fork_handback(session="other").stdout)
        self.assertIn("deny", self.fork_handback().stdout)

    # ---------- the script marks the review gate clean itself ----------

    def test_finishing_a_phase_writes_the_pinned_sessions_gate_file_and_prints_no_mark_command(self):
        self.begin_coder()
        self.hook("coder", self.CODER_REPORT, session="sess-1")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK, session="sess-1")
        self.assertIsNone(self.gate_mark("sess-1"))
        out = self.step("after-review")
        self.assertMarkedClean(out, "sess-1")
        self.assertEqual({"sess-1"}, {p.name for p in (self.home / ".claude/state/review-gate").iterdir()})

    def test_a_failed_verification_still_marks_the_gate_clean_and_prints_no_mark_command(self):
        self.set_verification('- [ ] **Check**: fails - `bash -c "exit 1"`')
        out = self.finish_phase_one()
        self.assertIn("Automated Verification failed", out)
        self.assertMarkedClean(out)

    def test_a_closing_skill_phase_leaves_the_gate_unmarked(self):
        self.mark_phases_done(1, 2, 3)
        self.step("start", self.plan)
        self.step("skill-done", "pass")
        self.assertIsNone(self.gate_mark())

    # ---------- the phase-end commit command ----------

    def commit_lines(self):
        return [line for line in self.said().splitlines() if line.startswith("git add -- ")]

    def test_phase_end_says_the_diff_stat_and_one_commit_command_for_the_phases_own_files(self):
        self.finish_phase_one()
        said = self.said()
        self.assertIn("backend/src/orders.ts | +1 -0", said)
        self.assertIn("docs/plans/orders/spec.md | +1 -1", said)
        self.assertEqual(["git add -- backend/src/orders.ts docs/plans/orders/spec.md && git commit -m 'orders exist' -- "
                          "backend/src/orders.ts docs/plans/orders/spec.md"],
                         self.commit_lines())

    def test_the_commit_command_leaves_out_files_that_were_dirty_before_the_phase(self):
        (self.repo / "backend/src/existing.ts").write_text("export const a = 2\n")
        self.coder_round()
        (self.repo / "backend/src/existing.ts").write_text("export const a = 3\n")
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        self.assertEqual(1, len(self.commit_lines()))
        self.assertNotIn("existing.ts", self.commit_lines()[0])
        self.assertIn("Dirty before the phase and left out of the commit: backend/src/existing.ts", self.said())

    def test_the_script_never_commits_or_stages(self):
        before = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=self.repo, capture_output=True,
                                text=True).stdout
        self.finish_phase_one()
        after = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=self.repo, capture_output=True,
                               text=True).stdout
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.repo, capture_output=True,
                                text=True).stdout
        self.assertEqual((before, ""), (after, staged))

    def test_a_planless_task_end_says_the_commit_command_too(self):
        self.step("start", "--task", "add orders")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", self.CODER_REPORT)
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("Planless task reviewed", out)
        self.assertEqual(["git add -- backend/src/orders.ts && git commit -m 'orders exist' -- backend/src/orders.ts"],
                         self.commit_lines())

    # ---------- the wait ends only on the right agent's report ----------

    def set_state(self, **changes):
        stateFile = self.repo / ".git/code-step/state.json"
        state = json.loads(stateFile.read_text())
        for key, value in changes.items():
            if value is None:
                state.pop(key, None)
            else:
                state[key] = value
        stateFile.write_text(json.dumps(state))

    def set_gate_result(self, result):
        gatePath = self.repo / ".git/coder-gate.json"
        gate = json.loads(gatePath.read_text())
        gate["coders"] = {} if result is None else {"a1": {"runs": 1, "denies": 0, "failed": [], "skipped": [],
                                                           "result": result}}
        gatePath.write_text(json.dumps(gate))

    def test_a_fix_coders_row_during_the_review_does_not_end_the_review_wait(self):
        self.coder_round()
        self.hook("coder", "a fix coder handing back", agentId="fix1")
        self.wait_env(1, "0.2")
        self.assertIn("ACTION: wait", self.step("after-review"))

    def test_a_coder_row_without_a_passing_gate_result_does_not_end_the_coder_wait(self):
        for result in (None, "deny", "none"):
            with self.subTest(result=result):
                self.start_phase_one()
                self.set_gate_result(result)
                (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
                self.hook("coder", self.CODER_REPORT)
                self.wait_env(1, "0.2")
                self.assertIn("ACTION: wait", self.step("after-coder"))

    def test_a_coder_row_with_a_cap_gate_result_ends_the_coder_wait(self):
        self.start_phase_one()
        self.set_gate_result("cap")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", self.CODER_REPORT)
        self.wait_env(1, "0.2")
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

    def test_a_hook_that_pins_the_session_late_keeps_the_pin_after_the_wait(self):
        self.begin_coder()
        self.set_state(sessionId=None)
        self.wait_env(20)
        self.late_hook(1, "coder", self.CODER_REPORT)
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual(self.SESSION, self.state()["sessionId"])

    def test_start_pins_the_session_from_the_environment(self):
        self.start_phase_one()
        self.assertEqual(self.SESSION, self.state()["sessionId"])
        self.step("start", "--task", "add orders")
        self.assertEqual(self.SESSION, self.state()["sessionId"])

    def leave_dispatch_of(self, session, ageSeconds=60):
        self.start_phase_one()
        self.set_state(sessionId=session, dispatchAt=time.time() - ageSeconds)

    def test_start_stops_when_another_live_session_has_an_open_dispatch(self):
        self.leave_dispatch_of("other-session")
        before = (self.repo / ".git/code-step/state.json").read_text()
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertIn(self.plan, out)
        self.assertIn("Phase 1", out)
        self.assertIn("worktree", out)
        self.assertIn("--take-over", out)
        self.assertEqual(before, (self.repo / ".git/code-step/state.json").read_text())

    def test_take_over_starts_over_the_other_sessions_run(self):
        self.leave_dispatch_of("other-session")
        out = self.step("start", self.plan, "--take-over")
        self.assertIn("ACTION: dispatch", out)
        self.assertEqual(self.SESSION, self.state()["sessionId"])

    def leave_asks_of(self, session, ageSeconds=60):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")
        self.assertEqual("asks", self.state()["stage"])
        self.set_state(sessionId=session)
        stateFile = self.repo / ".git/code-step/state.json"
        past = time.time() - ageSeconds
        os.utime(stateFile, (past, past))

    def test_start_stops_when_another_session_waits_at_asks(self):
        self.leave_asks_of("other-session")
        out = self.step("start", self.plan, "+fast")
        self.assertIn("ACTION: stop", out)
        self.assertIn("in another session; this block lifts at", out)
        self.assertIn("invoke Skill code with `--take-over " + self.plan + " +fast`", out)
        self.assertEqual("asks", self.state()["stage"])

    def test_a_wait_at_asks_older_than_two_hours_is_lifted(self):
        self.leave_asks_of("other-session", ageSeconds=2 * 60 * 60 + 60)
        self.assertIn("ACTION: dispatch", self.step("start", self.plan))

    def test_take_over_starts_over_a_wait_at_asks(self):
        self.leave_asks_of("other-session")
        out = self.step("start", self.plan, "--take-over")
        self.assertIn("ACTION: dispatch", out)
        self.assertEqual(self.SESSION, self.state()["sessionId"])

    GUARDED_RUNS = [
        ("coder", None, "dispatch"), ("review", None, "dispatch"), ("asks-coder", None, "dispatch"),
        ("stopped", "invalid-packet", "state-file"),
        ("asks", None, "state-file"), ("impact-coder", None, "state-file"), ("impact-review", None, "state-file"),
        ("skill", None, "state-file"), ("plan-coder", None, "state-file"),
        ("stopped", "verification", "state-file"), ("stopped", "plan-format", "state-file"),
    ]

    def leave_run_of_another_session(self, stage, stopReason, ageKind, ageSeconds):
        self.start_phase_one()
        changes = {"stage": stage, "stopReason": stopReason, "sessionId": "other-session"}
        if ageKind == "dispatch":
            changes["dispatchAt"] = time.time() - ageSeconds
        self.set_state(**changes)
        stateFile = self.repo / ".git/code-step/state.json"
        past = time.time() - ageSeconds
        os.utime(stateFile, (past, past))

    def test_every_guarded_stage_blocks_a_live_run_lifts_after_two_hours_and_yields_to_take_over(self):
        for stage, stopReason, ageKind in self.GUARDED_RUNS:
            with self.subTest(stage=stage, stopReason=stopReason):
                self.leave_run_of_another_session(stage, stopReason, ageKind, 60)
                blocked = self.step("start", self.plan)
                self.assertIn("ACTION: stop", blocked)
                self.assertIn("Last active", blocked)
                self.assertIn("--take-over", blocked)
                self.assertEqual(stage, self.state()["stage"])

                self.leave_run_of_another_session(stage, stopReason, ageKind, 2 * 60 * 60 + 60)
                self.assertIn("ACTION: dispatch", self.step("start", self.plan))

                self.leave_run_of_another_session(stage, stopReason, ageKind, 60)
                self.assertIn("ACTION: dispatch", self.step("start", self.plan, "--take-over"))

    def test_a_stop_for_a_verification_failure_in_another_session_does_not_block_the_same_session(self):
        self.leave_run_of_another_session("stopped", "verification", "state-file", 60)
        self.set_state(sessionId=self.SESSION)
        self.assertIn("ACTION: dispatch", self.step("start", self.plan))

    def test_the_closing_skill_stage_pins_the_session(self):
        self.mark_phases_done(1, 2, 3)
        self.assertIn("ACTION: invoke-skill", self.step("start", self.plan))
        self.assertEqual(self.SESSION, self.state()["sessionId"])

    def test_the_same_session_starts_over_its_own_open_dispatch(self):
        self.leave_dispatch_of(self.SESSION)
        self.assertIn("ACTION: dispatch", self.step("start", self.plan))

    def test_an_open_dispatch_older_than_two_hours_is_abandoned(self):
        self.leave_dispatch_of("other-session", ageSeconds=2 * 60 * 60 + 60)
        self.assertIn("ACTION: dispatch", self.step("start", self.plan))

    def test_an_open_dispatch_with_no_pinned_session_is_abandoned(self):
        self.leave_dispatch_of(None)
        self.assertIn("ACTION: dispatch", self.step("start", self.plan))

    def test_a_state_with_no_pinned_session_claims_no_handbacks(self):
        self.begin_coder()
        self.set_state(sessionId=None)
        (self.repo / ".git/code-step/reports.jsonl").write_text(json.dumps(
            {"ts": time.time() + 5, "agent_type": "coder", "agent_id": "a1", "stage": "coder",
             "message": self.CODER_REPORT}) + "\n")
        self.wait_env(1, "0.2")
        self.assertIn("ACTION: wait", self.step("after-coder"))

    def test_the_wait_stops_once_the_dispatch_is_older_than_three_waits(self):
        self.begin_coder()
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(10, "0.2")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("coder dispatched at", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_a_wait_past_the_cap_still_takes_a_row_that_arrived(self):
        self.begin_coder()
        self.set_state(dispatchAt=time.time() - 100)
        self.hook("coder", self.CODER_REPORT)
        self.wait_env(10, "0.2")
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

    def test_a_long_wait_ends_with_run_the_same_command_again_so_the_checks_start_fresh(self):
        self.coder_round()
        self.wait_env(20)
        self.env["CODE_STEP_FRESH_CALL_SECONDS"] = "0.5"
        self.late_hook(1, "review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: wait", out)
        self.assertIn("The report arrived", out)
        self.assertIn(self.own_command("after-review"), out)
        self.assertIn("ACTION: stop-block-B", self.step("after-review"))

    # ---------- start: abandoned runs, arguments, the commit line ----------

    def test_an_early_return_in_start_clears_the_open_dispatch(self):
        self.start_phase_one()
        out = self.step("start", "docs/plans/orders/missing.md")
        self.assertIn("ACTION: ask-user", out)
        state = self.state()
        self.assertEqual("stopped", state["stage"])
        self.assertNotIn("dispatchAt", state)

    def test_start_takes_flag_like_words_after_the_task_start_as_task_text(self):
        out = self.step("start", "add", "a", "--dry-run", "flag")
        self.assertIn("Implement: add a --dry-run flag", out)

    def test_start_with_a_plan_and_an_unknown_flag_exits_two(self):
        result = run(self.repo, self.env, "start", self.plan, "--bogus")
        self.assertEqual(2, result.returncode)
        self.assertIn("usage: code-step.py start", result.stderr + result.stdout)

    def test_the_commit_line_commits_only_the_phases_files_and_handles_non_ascii_names(self):
        (self.repo / "backend/src/mine.ts").write_text("export const m = 1\n")
        subprocess.run(["git", "add", "backend/src/mine.ts"], cwd=self.repo, check=True, env=self.env)
        self.step("start", "--task", "add orders")
        (self.repo / "backend/src/ordérs.ts").write_text("export const o = 1\n")
        self.hook("coder", self.CODER_REPORT)
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        line = self.commit_lines()[0]
        self.assertIn("ordérs.ts", line)
        subprocess.run(line, shell=True, cwd=self.repo, check=True, env=self.env, capture_output=True)
        committed = subprocess.run(["git", "-c", "core.quotepath=false", "show", "--name-only", "--format=", "HEAD"],
                                   cwd=self.repo, capture_output=True, text=True, env=self.env).stdout.split("\n")
        self.assertIn("backend/src/ordérs.ts", committed)
        self.assertNotIn("backend/src/mine.ts", committed)
        staged = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=self.repo, capture_output=True,
                                text=True, env=self.env).stdout
        self.assertEqual("backend/src/mine.ts", staged.strip())

    def finish_phase_two_as_auto_advance(self):
        self.advance_to_phase_two()
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        return self.step("after-review")

    def test_auto_advance_prints_the_commit_line_before_the_next_start(self):
        out = self.finish_phase_two_as_auto_advance()
        self.assertIn("ACTION: auto-advance", out)
        self.assertIn("First run this commit command", out)
        self.assertIn("git add -- backend/src/totals.ts", out)

    def test_the_next_start_after_an_auto_advance_stops_while_the_phases_files_are_uncommitted(self):
        self.finish_phase_two_as_auto_advance()
        out = self.step("start")
        self.assertIn("ACTION: stop", out)
        self.assertIn("not committed", out)
        self.assertIn("git add -- backend/src/totals.ts", out)
        self.assertNotIn("AGENT: coder", out)
        self.commit_all()
        self.assertIn("AGENT: coder", self.step("start"))

    # ---------- tick ----------

    def test_tick_marks_the_phase_done_and_records_who_said_so(self):
        self.start_phase_one()
        out = self.step("tick", "1")
        self.assertIn("ACTION: stop", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())
        self.assertIn("marked done by the user", self.plan_text())
        self.assertEqual("done", self.state()["stage"])

    def test_tick_refuses_an_unknown_phase_a_done_phase_and_a_missing_state(self):
        self.assertIn("no saved plan state", self.step("tick", "1"))
        self.start_phase_one()
        self.assertIn("Phase 9 is not in the Phase Status", self.step("tick", "9"))
        self.step("tick", "1")
        self.assertIn("already marked done", self.step("tick", "1"))
        self.assertIn("usage: code-step.py tick", self.step("tick"))

    def test_the_no_change_stop_names_the_tick_command(self):
        self.start_phase_one()
        self.hook("coder", "BEHAVIOR: none")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("tick 1", out)

    # ---------- the fork's stop ----------

    def stop_hook(self, session=SESSION, agentType="general-purpose"):
        event = {"agent_type": agentType, "cwd": str(self.repo), "session_id": session}
        return run(self.repo, self.env, "stop-hook", stdin=json.dumps(event)).stdout

    def test_the_stop_hook_blocks_the_fork_twice_while_a_dispatch_is_open(self):
        self.start_phase_one()
        first = json.loads(self.stop_hook())
        self.assertEqual("block", first["decision"])
        self.assertIn(self.own_command("after-coder"), first["reason"])
        self.assertEqual("block", json.loads(self.stop_hook())["decision"])
        self.assertEqual("", self.stop_hook())

    def test_the_stop_hook_leaves_other_sessions_other_agents_and_answered_dispatches_alone(self):
        self.start_phase_one()
        self.assertEqual("", self.stop_hook(session="other"))
        self.assertEqual("", self.stop_hook(agentType="coder"))
        self.set_gate_result("pass")
        self.hook("coder", self.CODER_REPORT)
        self.assertEqual("", self.stop_hook())

    def test_a_new_dispatch_resets_the_stop_hook_count(self):
        self.start_phase_one()
        self.stop_hook()
        self.stop_hook()
        self.start_phase_one()
        self.assertEqual("block", json.loads(self.stop_hook())["decision"])

    # ---------- the shared hand-back record backs the clean mark ----------

    def test_a_false_clean_reason_stops_the_run_and_writes_no_gate_file(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        shutil.rmtree(self.tmp / "handback-store")
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("no review-loop hand-back is stored", out)
        self.assertIsNone(self.gate_mark())
        self.assertNotIn("- [x] Phase 1:", self.plan_text())

    def test_missing_handback_module_stops_the_run_and_writes_no_gate_file(self):
        bare = self.tmp / "bare"
        bare.mkdir()
        for name in (SCRIPT.name, "script_utils.py", "plan_format.py"):
            shutil.copy(SCRIPT.parent / name, bare / name)
        env = dict(self.env, PYTHONPATH="")
        script = str(bare / SCRIPT.name)

        def bare_step(*args, stdin=None):
            return subprocess.run([sys.executable, script, *args], cwd=self.repo, env=env, input=stdin,
                                  capture_output=True, text=True).stdout

        bare_step("start", "--task", "add orders")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        event = {"agent_type": "coder", "agent_id": "a1", "cwd": str(self.repo), "session_id": self.SESSION,
                 "tool_input": {"message": self.CODER_REPORT}}
        bare_step("hook", stdin=json.dumps(event))
        bare_step("after-coder")
        event.update(agent_type="review-loop", tool_input={"message": self.LOOP_OK})
        bare_step("hook", stdin=json.dumps(event))
        out = bare_step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("handback.py could not be imported", out)
        self.assertIsNone(self.gate_mark())

    def test_the_clean_mark_asks_about_the_environments_session_not_the_stored_pin(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.set_state(sessionId="a-stale-pin")
        self.step("after-review")
        self.assertEqual("clean\n", self.gate_mark(self.SESSION))


if __name__ == "__main__":
    unittest.main()
