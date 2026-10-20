import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = REPO_ROOT / "claude" / ".claude"
SCRIPT = pathlib.Path(os.environ.get("CODE_STEP_SCRIPT") or REAL_CLAUDE / "scripts" / "code-step.py")
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
        self.env = dict(os.environ, CODE_STEP_CLAUDE_DIR=str(self.claude), GIT_AUTHOR_NAME="t",
                        GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        self.env.pop("CODE_STEP_IMPACT_DECISION", None)
        self.env.pop("CODE_STEP_ASKS_OUTCOME", None)
        for command in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "base"]):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True, env=self.env)
        self.plan = "docs/plans/orders/spec.md"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def step(self, *args, stdin=None):
        return run(self.repo, self.env, *args, stdin=stdin).stdout

    def hook(self, agentType, message, agentId="a1", session=None):
        event = {"agent_type": agentType, "agent_id": agentId, "cwd": str(self.repo),
                 "tool_input": {"message": message}}
        if session:
            event["session_id"] = session
        return run(self.repo, self.env, "hook", stdin=json.dumps(event))

    def state(self):
        return json.loads(self.step("status"))

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
        self.assertIn("review-gate-mark clean", out)
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
        self.assertIn("review-gate-mark clean", out)
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
        self.assertIn("review-gate-mark clean", out)
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
        self.hook("coder", "mine", session="s1")
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

    def test_verify_pass_dispatches_the_branch_wide_reviewer_first(self):
        self.mark_phases_done(1, 2, 3)
        (self.repo / self.plan).write_text(self.plan_text().replace("Refactor pass - /refactor cleanup sweep",
                                                                    "Verify pass — deep review + /verify-branch"))
        out = self.step("start", self.plan)
        self.assertIn("AGENT: code-reviewer", out)
        self.assertIn("MODEL: omit the model argument", out)
        self.assertIn("`/verify-branch`", out)

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

    def test_asks_coder_that_changed_only_docs_sends_no_review_and_finishes_the_phase(self):
        self.apply_first_ask()
        (self.repo / "backend/README.md").write_text("orders\n")
        self.hook("coder", "BEHAVIOR: documented the ask")
        out = self.step("after-coder")
        self.assertNotIn("AGENT: review-loop", out)
        self.assertIn("Phase 1 marked done", out)
        self.assertIn("review-gate-mark clean", out)
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


if __name__ == "__main__":
    unittest.main()
