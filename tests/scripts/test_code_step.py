import datetime
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = pathlib.Path(os.environ.get("CODE_STEP_REAL_CLAUDE") or REPO_ROOT / "claude" / ".claude")
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
    GIT_IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                    "GIT_COMMITTER_EMAIL": "t@t"}

    @classmethod
    def setUpClass(cls):
        # Every test starts from a copy of this repo: the work tree and the one base commit, built once.
        classDirectory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(classDirectory.cleanup)
        classHome = pathlib.Path(classDirectory.name) / "home"
        classHome.mkdir()
        cls.baseRepo = pathlib.Path(classDirectory.name) / "repo"
        (cls.baseRepo / "backend/src").mkdir(parents=True)
        (cls.baseRepo / "docs/plans/orders").mkdir(parents=True)
        (cls.baseRepo / "backend/package.json").write_text(json.dumps({
            "scripts": {"typecheck": "tsc --noEmit", "lint": "eslint ."},
            "devDependencies": {"vitest": "1", "eslint": "9"}}))
        (cls.baseRepo / "backend/src/existing.ts").write_text("export const a = 1\n")
        (cls.baseRepo / "docs/plans/orders/spec.md").write_text(PLAN)
        (cls.baseRepo / "docs/plans/orders/acceptance-criteria.md").write_text("AC-1 orders exist\n")
        gitEnv = dict(os.environ, HOME=str(classHome), **cls.GIT_IDENTITY)
        for command in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "base"]):
            subprocess.run(command, cwd=cls.baseRepo, check=True, capture_output=True, env=gitEnv)

    def setUp(self):
        tempDirectory = tempfile.TemporaryDirectory()
        self.addCleanup(tempDirectory.cleanup)
        self.tmp = pathlib.Path(tempDirectory.name)
        self.claude = self.tmp / "claude"
        (self.claude / "scripts").mkdir(parents=True)
        (self.claude / "skills/review").mkdir(parents=True)
        for name in ("coder-gate.py", "resolve-task-dir.sh"):
            shutil.copy(REAL_CLAUDE / "scripts" / name, self.claude / "scripts" / name)
        for name in ("coder-packet.py", "plan_format.py", "script_utils.py"):
            shutil.copy(SCRIPT.parent / name, self.claude / "scripts" / name)
        self.log = self.tmp / "calls.log"
        for name in ("scripts/log-scan", "skills/review/log-review-finding"):
            stub = self.claude / name
            stub.write_text(f'#!/usr/bin/env bash\necho "{name} $@" >> {self.log}\n')
            stub.chmod(0o755)
        self.repo = self.tmp / "repo"
        shutil.copytree(self.baseRepo, self.repo, symlinks=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.env = dict(os.environ, CODE_STEP_CLAUDE_DIR=str(self.claude), **self.GIT_IDENTITY,
                        HOME=str(self.home), CODE_STEP_WAIT_SECONDS="0", CLAUDE_CODE_SESSION_ID=self.SESSION,
                        HANDBACK_STORE_DIR=str(self.tmp / "handback-store"),
                        PYTHONPATH=str(HANDBACK_SCRIPT.parent))
        self.env.pop("CODE_STEP_IMPACT_DECISION", None)
        self.env.pop("CODE_STEP_ASKS_OUTCOME", None)
        self.plan = "docs/plans/orders/spec.md"

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

    def pass_coder_gate(self):
        gatePath = self.repo / ".git/coder-gate.json"
        if gatePath.exists():
            gate = json.loads(gatePath.read_text())
            gate["coders"]["a1"] = {"runs": 1, "denies": 0, "failed": [], "skipped": [], "result": "pass"}
            gatePath.write_text(json.dumps(gate))

    def begin_coder(self, source="export const o = 1\n"):
        self.start_phase_one()
        self.pass_coder_gate()
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

    # The ledger writer mints finding ids as 16 lowercase hex characters; code-step logs no other shape.
    ASK_FINDING_ID = "0123456789abcdef"
    ASK = ('status: converged\niter: 1\nfixed: []\nask: [{"finding": "f", "file_line": "backend/src/orders.ts:2", '
           '"question": "keep?", "gate": "code-reviewer", "class": "correctness", "finding_id": "0123456789abcdef"}]')

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

    def test_gate_runs_clippy_with_warnings_denied_in_the_cargo_package_that_holds_a_named_rust_file(self):
        (self.repo / "crate/src").mkdir(parents=True)
        (self.repo / "crate/Cargo.toml").write_text('[package]\nname = "crate"\n')
        (self.repo / "crate/src/lib.rs").write_text("pub fn a() {}\n")
        rustFile = "**File**: `backend/src/orders.test.ts`\n**File**: `crate/src/lib.rs`\n**File**: `crate/Cargo.toml`"
        (self.repo / self.plan).write_text(self.plan_text().replace("**File**: `backend/src/orders.test.ts`", rustFile))

        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual(1, gate["commands"].count("cd crate && cargo clippy --all-targets -- -D warnings"))
        self.assertEqual(["cd crate && cargo test --lib --bins"],
                         [command for command in gate["commands"] if "cargo test" in command])
        self.assertIn("cd backend && npm run typecheck", gate["commands"])

    def test_gate_runs_clippy_without_a_cd_prefix_when_the_phase_names_only_the_root_cargo_manifest(self):
        (self.repo / "Cargo.toml").write_text('[package]\nname = "root-crate"\n')
        rootManifest = "**File**: `backend/src/orders.test.ts`\n**File**: `Cargo.toml`"
        (self.repo / self.plan).write_text(self.plan_text().replace("**File**: `backend/src/orders.test.ts`", rootManifest))

        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual(1, gate["commands"].count("cargo clippy --all-targets -- -D warnings"))

    def test_gate_runs_only_the_rust_tests_of_the_named_files_and_sets_no_cargo_variable(self):
        (self.repo / "crate/src").mkdir(parents=True)
        (self.repo / "crate/tests").mkdir()
        (self.repo / "crate/Cargo.toml").write_text('[package]\nname = "crate"\n')
        (self.repo / "crate/src/lib.rs").write_text("")
        rustFiles = "**File**: `crate/src/store/query.rs`\n**File**: `crate/tests/side_streams.rs`"
        (self.repo / self.plan).write_text(self.plan_text().replace("**File**: `backend/src/orders.test.ts`", rustFiles))

        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual(["cd crate && cargo clippy --all-targets -- -D warnings",
                          "cd crate && cargo test --lib --bins",
                          "cd crate && cargo test --test side_streams"],
                         [command for command in gate["commands"] if "cargo" in command])

    def test_cargo_tests_are_the_test_target_binary_or_library_of_each_named_rust_file(self):
        (self.repo / "crate/src/a").mkdir(parents=True)
        (self.repo / "crate/tests/common").mkdir(parents=True)
        (self.repo / "crate/Cargo.toml").write_text('[package]\nname = "crate"\n')
        (self.repo / "crate/tests/side_streams").mkdir()
        (self.repo / "crate/src/lib.rs").write_text("")
        (self.repo / "crate/tests/side_streams/main.rs").write_text("")
        cases = {
            "crate/tests/side_streams.rs": "cargo test --test side_streams",
            "crate/tests/side_streams/main.rs": "cargo test --test side_streams",
            "crate/tests/side_streams/helper.rs": "cargo test --test side_streams",
            "crate/tests/side_streams/deep/helper.rs": "cargo test --test side_streams",
            "crate/tests/common/mod.rs": "cargo test --tests",
            "crate/tests/common/deep/helper.rs": "cargo test --tests",
            "crate/src/a/b.rs": "cargo test --lib --bins",
            "crate/src/a/mod.rs": "cargo test --lib --bins",
            "crate/src/a.rs": "cargo test --lib --bins",
            "crate/src/a/b/c.rs": "cargo test --lib --bins",
            "crate/src/bin.rs": "cargo test --lib --bins",
            "crate/src/lib.rs": "cargo test --lib --bins",
            "crate/src/main.rs": "cargo test --lib --bins",
            "crate/src/bin/tool.rs": "cargo test --bin tool",
            "crate/src/bin/tool/main.rs": "cargo test --bin tool",
            "crate/src/bin/tool/helper.rs": "cargo test --bin tool",
            "crate/src/bin/tool/deep/main.rs": "cargo test --bin tool",
            "crate/benches/speed.rs": None,
        }
        for path, expected in cases.items():
            with self.subTest(path=path):
                clippy = "cd crate && cargo clippy --all-targets -- -D warnings"
                wanted = [clippy] + ([f"cd crate && {expected}"] if expected else [])

                self.assertEqual(wanted, code_step.cargo_commands(self.repo, [path]))

    def test_cargo_commands_are_merged_per_crate_without_duplicates_and_never_run_a_whole_crate(self):
        for crate in ("one", "two"):
            (self.repo / crate / "src").mkdir(parents=True)
            (self.repo / crate / "src/lib.rs").write_text("")
            (self.repo / crate / "Cargo.toml").write_text(f'[package]\nname = "{crate}"\n')
        paths = ["one/src/a.rs", "two/src/b.rs", "one/src/a.rs", "one/src/lib.rs", "one/Cargo.toml", "one/src/c.rs"]

        commands = code_step.cargo_commands(self.repo, paths)

        clippy = "cargo clippy --all-targets -- -D warnings"
        self.assertEqual([f"cd one && {clippy}", "cd one && cargo test --lib --bins",
                          f"cd two && {clippy}", "cd two && cargo test --lib --bins"], commands)

    def test_a_shared_test_helper_change_runs_only_clippy_and_the_all_targets_test(self):
        (self.repo / "crate/src").mkdir(parents=True)
        (self.repo / "crate/tests/common").mkdir(parents=True)
        (self.repo / "crate/Cargo.toml").write_text('[package]\nname = "crate"\n')
        (self.repo / "crate/src/lib.rs").write_text("")
        paths = ["crate/tests/side_streams.rs", "crate/src/a.rs", "crate/tests/common/mod.rs", "crate/src/bin/tool.rs",
                 "crate/tests/orders.rs"]

        commands = code_step.cargo_commands(self.repo, paths)

        self.assertEqual(["cd crate && cargo clippy --all-targets -- -D warnings", "cd crate && cargo test --tests"],
                         commands)
        self.assertNotIn("cd crate && cargo test --lib --bins", commands)

    def test_two_modules_of_one_library_crate_give_one_lib_test_command(self):
        (self.repo / "lib/src/store").mkdir(parents=True)
        (self.repo / "lib/src/lib.rs").write_text("")
        (self.repo / "lib/Cargo.toml").write_text('[package]\nname = "lib"\n')

        commands = code_step.cargo_commands(self.repo, ["lib/src/store/query.rs", "lib/src/orders.rs"])

        self.assertEqual(["cd lib && cargo clippy --all-targets -- -D warnings", "cd lib && cargo test --lib --bins"],
                         commands)

    def test_a_change_to_the_library_root_runs_the_lib_tests(self):
        (self.repo / "lib/src").mkdir(parents=True)
        (self.repo / "lib/src/lib.rs").write_text("")
        (self.repo / "lib/Cargo.toml").write_text('[package]\nname = "lib"\n')

        commands = code_step.cargo_commands(self.repo, ["lib/src/lib.rs"])

        self.assertEqual(["cd lib && cargo clippy --all-targets -- -D warnings", "cd lib && cargo test --lib --bins"],
                         commands)

    def test_a_named_binary_file_in_a_library_crate_runs_only_that_binary(self):
        (self.repo / "both/src/bin").mkdir(parents=True)
        (self.repo / "both/src/lib.rs").write_text("")
        (self.repo / "both/Cargo.toml").write_text('[package]\nname = "both"\n')

        commands = code_step.cargo_commands(self.repo, ["both/src/bin/tool.rs"])

        self.assertEqual(["cd both && cargo clippy --all-targets -- -D warnings", "cd both && cargo test --bin tool"],
                         commands)

    def test_a_crate_with_no_library_runs_every_file_under_src_with_bins_once(self):
        (self.repo / "tool/src/store").mkdir(parents=True)
        (self.repo / "tool/src/main.rs").write_text("")
        (self.repo / "tool/Cargo.toml").write_text('[package]\nname = "tool"\n')

        commands = code_step.cargo_commands(self.repo, ["tool/src/store/query.rs", "tool/src/store/mod.rs",
                                                        "tool/src/main.rs"])

        self.assertEqual(["cd tool && cargo clippy --all-targets -- -D warnings", "cd tool && cargo test --bins"],
                         commands)

    def test_a_crate_with_a_library_and_a_binary_runs_a_src_file_with_lib_and_bins(self):
        (self.repo / "both/src").mkdir(parents=True)
        (self.repo / "both/src/lib.rs").write_text("")
        (self.repo / "both/src/main.rs").write_text("")
        (self.repo / "both/Cargo.toml").write_text('[package]\nname = "both"\n')

        commands = code_step.cargo_commands(self.repo, ["both/src/store.rs", "both/src/main.rs"])

        self.assertEqual(["cd both && cargo clippy --all-targets -- -D warnings", "cd both && cargo test --lib --bins"],
                         commands)

    def test_a_manifest_alone_or_a_file_outside_src_and_tests_gives_clippy_and_no_test(self):
        (self.repo / "Cargo.toml").write_text('[package]\nname = "root-crate"\n')
        (self.repo / "src").mkdir()

        commands = code_step.cargo_commands(self.repo, ["Cargo.toml", "benches/speed.rs", "build.rs"])

        self.assertEqual(["cargo clippy --all-targets -- -D warnings"], commands)

    def test_a_verification_item_may_start_with_an_environment_setting(self):
        item = "- [ ] **Tests**: the streams pass - `CARGO_BUILD_JOBS=4 cargo test --test side_streams`"

        self.assertEqual("CARGO_BUILD_JOBS=4 cargo test --test side_streams", code_step.verification_command(item))
        self.assertIsNone(code_step.verification_item_problem(item, self.repo))

    def test_gate_runs_no_cargo_command_when_the_phase_names_no_rust_file(self):
        (self.repo / "crate").mkdir()
        (self.repo / "crate/Cargo.toml").write_text('[package]\nname = "crate"\n')
        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual([], [command for command in gate["commands"] if "cargo" in command])

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
                       "`decide adopt --by user --ruling \"<the decision in one line>\"`",
                       "`decide keep --by user --ruling \"<the decision in one line>\"`",
                       "pass `--by session`", "never changes the acceptance criteria",
                       "with the ruling in one line, in your own words, as the --ruling text. Do not quote the user."):
            self.assertIn(option, self.said())
        self.assertNotIn("AskUserQuestion", out + self.said())
        self.assertNotIn("AGENT: review-loop", out)
        out = self.step("decide", "keep", "--by", "user", "--ruling", "keep it, the importer is right")
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
        out = self.step("decide", "adopt", "--by", "user", "--ruling", "adopt it, drop the header")
        self.assertIn("AGENT: coder", out)
        self.assertNotIn("AGENT: review-loop", out)
        self.assertEqual("plan-coder", self.state()["stage"])
        self.assert_dispatch_logged(out, "d2", "coder", "plan-coder", "after-plan-edit")
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        out = self.step("after-plan-edit")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("flagged: none", out)
        self.assertIn("now states the ruling", self.said())

    CRITERIA = "docs/plans/orders/acceptance-criteria.md"
    DECIDE_USAGE = 'decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"'

    def criteria_text(self):
        return (self.repo / self.CRITERIA).read_text()

    def set_git_user(self, name):
        subprocess.run(["git", "config", "user.name", name], cwd=self.repo, check=True, capture_output=True)

    def test_decide_without_by_stops_with_the_usage_line_and_leaves_the_state(self):
        for word in ("adopt", "keep"):
            self.coder_round(self.IMPACT_REPORT)
            before = self.state()
            out = self.step("decide", word, "--ruling", "my call")
            self.assertIn("ACTION: stop", out)
            self.assertIn(self.DECIDE_USAGE, out)
            self.assertEqual(before, self.state())
            self.assertNotIn("## Plan Deviations", self.plan_text())

    def test_decide_with_another_by_value_stops_with_the_usage_line(self):
        self.coder_round(self.IMPACT_REPORT)
        before = self.state()
        out = self.step("decide", "adopt", "--by", "maybe", "--ruling", "my call")
        self.assertIn("ACTION: stop", out)
        self.assertIn(self.DECIDE_USAGE, out)
        self.assertEqual(before, self.state())

    def test_decide_by_with_no_value_before_the_ruling_stops(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "adopt", "--by", "--ruling", "my call")
        self.assertIn("ACTION: stop", out)
        self.assertIn(self.DECIDE_USAGE, out)

    def test_decide_discuss_needs_no_by(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "discuss")
        self.assertIn("ACTION: ask-user", out)
        self.assertIn("decide adopt --by user --ruling", self.said())
        self.assertIn("pass `--by session`", self.said())

    def test_decide_without_ruling_words_names_the_by_form(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "keep", "--by", "user")
        self.assertIn("ACTION: stop", out)
        self.assertIn("decide keep --by user --ruling", out)

    def test_user_adopt_signs_with_the_git_user_and_lets_the_coder_rewrite_the_criteria(self):
        self.set_git_user("Pat Signer")
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "adopt", "--by", "user", "--ruling", "drop the header")
        ruling = self.state()["ruling"]
        self.assertTrue(ruling["byUser"])
        self.assertEqual("Pat Signer", ruling["by"])
        self.assertIn(f"`Signed off by Pat Signer, {ruling['at']}: <the change in one line>`", out)
        self.assertIn(f"and its acceptance criteria file {self.CRITERIA}", out)
        self.assertIn("The user adopted the plan change. Dispatch a coder to rewrite the plan steps and acceptance "
                      "criteria it contradicts.", out.split("-----BEGIN PROMPT-----")[0])
        self.assertNotIn("Do not edit", out)
        self.assertNotIn("stay as written", out)
        self.assertIn("  The ruling: drop the header\n\n  The disagreement:", self.plan_text())
        self.assertNotIn("  > ", self.plan_text())
        self.assertNotIn("user's words", self.plan_text())
        self.assertNotIn("user's words", out)
        self.assertIn("The user ruled (Pat Signer, ", out)
        self.assertIn("):\n\ndrop the header", out)
        self.assertIn("The ruling:\n  drop the header", self.state()["planImpact"])
        self.assertIn("RESOLVED: the user ruled on this disagreement.", self.state()["planImpact"])

    def test_a_ruling_of_several_lines_is_recorded_on_one_line_without_a_quote_block(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "keep", "--by", "session", "--ruling", "keep the header\n  as it is")

        self.assertIn("  The ruling: keep the header as it is\n", self.plan_text())
        self.assertNotIn(">", self.plan_text().split("## Plan Deviations", 1)[1].split("The disagreement:", 1)[0])

    def test_session_adopt_keeps_the_criteria_out_of_the_edit_scope(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        ruling = self.state()["ruling"]
        self.assertFalse(ruling["byUser"])
        self.assertEqual("the session, not the user", ruling["by"])
        self.assertIn("AGENT: coder", out)
        self.assertIn(f"Do not edit {self.CRITERIA}. Only the user's own sign-off changes an acceptance criterion.", out)
        self.assertIn(f"Edit only the plan file {self.plan}. ", out)
        self.assertNotIn("Signed off by", out)
        self.assertNotIn("and its acceptance criteria file", out)
        self.assertNotIn("Rewrite each criterion", out)
        self.assertIn("The acceptance criteria stay as written", out)
        self.assertIn("The ruling (the session, not the user, ", out)
        self.assertNotIn("The user ruled", out)
        self.assertIn("Ruled by the session, not the user", self.plan_text())
        self.assertIn("  The ruling: my own call", self.plan_text())
        self.assertNotIn("The user's words:", self.plan_text())
        planImpact = self.state()["planImpact"]
        self.assertIn("RESOLVED: the session ruled on this disagreement, not the user.", planImpact)
        self.assertNotIn("the user ruled", planImpact)
        self.assertNotIn("user's words", planImpact)

    def test_session_keep_with_a_criteria_file_prints_the_stay_as_written_line(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "keep", "--by", "session", "--ruling", "my own call")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("The acceptance criteria stay as written", out)
        self.assertIn("RESOLVED: the session ruled", out)

    def test_session_adopt_with_no_criteria_file_has_no_criteria_line(self):
        self.coder_round(self.IMPACT_REPORT)
        (self.repo / self.CRITERIA).unlink()
        out = self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.assertIn("AGENT: coder", out)
        self.assertNotIn("Do not edit", out)
        self.assertNotIn("stay as written", out)

    def test_after_plan_edit_restores_criteria_the_coder_changed_on_a_session_ruling(self):
        original = self.criteria_text()
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        (self.repo / self.CRITERIA).write_text(original + "AC-1 orders may be empty\nSigned off by someone\n")
        (self.repo / self.plan).write_text(self.plan_text().replace(
            "## Phase 2", "Adopted step: drop the header.\n\n## Phase 2", 1))
        out = self.step("after-plan-edit")
        self.assertEqual(original, self.criteria_text())
        self.assertIn("changed after a ruling the user did not make, and the script restored them.", self.said())
        copyPath = self.replaced_copies()[0]
        self.assertIn(f"The text it replaced is in {copyPath}.", self.said())
        self.assertNotIn(self.CRITERIA, self.state()["files"])
        self.assertEqual([], self.state()["flagged"])
        self.assertEqual(original + "AC-1 orders may be empty\nSigned off by someone\n", copyPath.read_text())
        self.assert_copy_is_not_phase_work(out)
        self.assertIn("AGENT: review-loop", out)
        self.assertNotIn("Traceback", out)
        self.assertNotIn("changed too", self.said())
        self.assertNotIn("criteriaGuard", self.state())

    def test_after_plan_edit_restores_criteria_the_coder_deleted_on_a_session_ruling(self):
        original = self.criteria_text()
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        (self.repo / self.CRITERIA).unlink()
        out = self.step("after-plan-edit")
        self.assertEqual(original, self.criteria_text())
        self.assertIn("the script restored them.", self.said())
        self.assertNotIn(self.CRITERIA, self.state()["files"])
        self.assertEqual([], self.state()["flagged"])
        self.assertNotIn("Traceback", out)

    def replaced_copies(self):
        folder = self.repo / ".git/code-step-replaced-criteria"
        return sorted(folder.glob("*")) if folder.is_dir() else []

    def assert_copy_is_not_phase_work(self, out):
        # The saved copy sits in the git dir, so no phase list, flag or commit line may name it.
        stateText = json.dumps(self.state())
        self.assertNotIn("replaced-criteria", stateText)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True,
                                env=self.env).stdout
        self.assertNotIn("replaced-criteria", status)

    def check_start_restores_the_criteria(self, startArguments):
        original = self.criteria_text()
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "plan edited")
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten by the coder\n")
        self.step("start", "docs/plans/nope.md")
        self.assertNotIn("criteriaGuard", self.state())
        self.assertEqual(original, self.criteria_text())
        (self.repo / self.CRITERIA).write_text("AC-1 the user's own edit\n")
        self.step(*startArguments)
        self.assertEqual("AC-1 the user's own edit\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())

    def test_start_keeps_the_replaced_text_in_the_git_dir_and_names_it(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 changed by someone\n")
        out = self.step("start")
        copyPath = self.replaced_copies()[0]
        self.assertTrue(copyPath.is_absolute())
        self.assertIn(f"The text it replaced is in {copyPath}.", self.said())
        self.assertNotIn("coder", self.said())
        self.assertEqual("AC-1 changed by someone\n", copyPath.read_text())
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assert_copy_is_not_phase_work(out)

    def test_two_restores_with_different_text_leave_two_copies(self):
        for text in ("AC-1 first change\n", "AC-1 second change\n"):
            self.coder_round(self.IMPACT_REPORT)
            self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
            self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
            (self.repo / self.CRITERIA).write_text(text)
            self.step("start")
        copies = sorted(path.read_text() for path in self.replaced_copies())
        self.assertEqual(["AC-1 first change\n", "AC-1 second change\n"], copies)

    def test_a_criteria_file_the_coder_created_is_deleted_and_its_text_kept(self):
        self.coder_round(self.IMPACT_REPORT)
        (self.repo / self.CRITERIA).unlink()
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 invented\n")
        out = self.step("start")
        copyPath = self.replaced_copies()[0]
        self.assertFalse((self.repo / self.CRITERIA).exists())
        self.assertEqual("AC-1 invented\n", copyPath.read_text())
        self.assertIn(f"The text it deleted is in {copyPath}.", self.said())
        self.assert_copy_is_not_phase_work(out)

    def test_after_plan_edit_deletes_a_criteria_file_the_coder_created(self):
        self.coder_round(self.IMPACT_REPORT)
        (self.repo / self.CRITERIA).unlink()
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        (self.repo / self.CRITERIA).write_text("AC-1 invented\n")
        out = self.step("after-plan-edit")
        copyPath = self.replaced_copies()[0]
        self.assertFalse((self.repo / self.CRITERIA).exists())
        self.assertEqual("AC-1 invented\n", copyPath.read_text())
        self.assertTrue(copyPath.is_absolute())
        self.assertIn(f"The text it deleted is in {copyPath}.", self.said())
        self.assertNotIn(self.CRITERIA, self.state()["files"])
        self.assertEqual([], self.state()["flagged"])
        self.assert_copy_is_not_phase_work(out)

    def test_after_plan_edit_keeps_a_criteria_file_the_coder_created_on_a_user_ruling(self):
        self.coder_round(self.IMPACT_REPORT)
        (self.repo / self.CRITERIA).unlink()
        self.step("decide", "adopt", "--by", "user", "--ruling", "add the criteria")
        (self.repo / self.CRITERIA).write_text("AC-1 added\n")
        out = self.step("after-plan-edit")
        self.assertEqual("AC-1 added\n", self.criteria_text())
        self.assertEqual([], self.replaced_copies())
        self.assertNotIn("deleted it", self.said())

    def commit_on_new_branch(self, criteriaText):
        subprocess.run(["git", "checkout", "-q", "-b", "other-branch"], cwd=self.repo, check=True, env=self.env)
        (self.repo / self.CRITERIA).write_text(criteriaText)
        subprocess.run(["git", "add", self.CRITERIA], cwd=self.repo, check=True, env=self.env)
        subprocess.run(["git", "commit", "-q", "-m", "criteria on the other branch"], cwd=self.repo, check=True,
                       env=self.env)

    def check_another_branch_stops_before_the_settle(self):
        before = self.state()
        said = self.said()
        out = self.step("after-plan-edit")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT:", out)
        self.assertIn("Switch back to branch master, then run `! python3 ", out)
        self.assertIn("Tell the user.", out)
        self.assertEqual("AC-1 the other branch\n", self.criteria_text())
        self.assertEqual(said, self.said())
        self.assertEqual(before, self.state())
        self.assertIn("criteriaGuard", self.state())
        self.assertEqual([], self.replaced_copies())

    def test_after_plan_edit_on_another_branch_stops_and_keeps_the_guard_when_a_file_existed_at_the_save(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.commit_on_new_branch("AC-1 the other branch\n")
        self.check_another_branch_stops_before_the_settle()

    def test_after_plan_edit_on_another_branch_stops_and_keeps_the_guard_when_no_file_existed_at_the_save(self):
        self.coder_round(self.IMPACT_REPORT)
        (self.repo / self.CRITERIA).unlink()
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.commit_on_new_branch("AC-1 the other branch\n")
        self.check_another_branch_stops_before_the_settle()

    def test_a_start_restore_that_then_stops_early_leaves_the_message_and_the_question_in_say(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 changed by someone\n")
        out = self.step("start", "docs/plans/nope.md")
        copyPath = self.replaced_copies()[0]
        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"The text it replaced is in {copyPath}.", self.said())
        self.assertIn("## Question for the user", self.said())

    def test_start_task_with_no_run_clears_text_an_earlier_command_left(self):
        said = self.repo / ".git/code-step/say.md"
        said.parent.mkdir(parents=True, exist_ok=True)
        said.write_text("## Question for the user\n\nMain session: no plan file is at docs/nope.md.\n")
        out = self.step("start", "--task", "add a flag")
        self.assertIn("Implement: add a flag", out)
        self.assertEqual("", self.said())

    def test_start_task_after_an_auto_advance_drops_the_auto_advance_text(self):
        self.finish_phase_one()
        self.step("start")
        (self.repo / "backend/src/totals.ts").write_text("export const total = 1;\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("ACTION: auto-advance", self.step("after-review"))
        self.assertIn("Auto-advancing to Phase 3", self.said())
        self.commit_all()
        out = self.step("start", "--task", "fix the typo")
        self.assertIn("Implement: fix the typo", out)
        self.assertNotIn("Auto-advancing", self.said())

    def check_a_planless_start_keeps_the_restore_message(self, startArguments):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 changed by someone\n")
        self.step(*startArguments)
        copyPath = self.replaced_copies()[0]
        self.assertIn(f"The text it replaced is in {copyPath}.", self.said())

    def test_start_task_keeps_the_restore_message_in_say(self):
        self.check_a_planless_start_keeps_the_restore_message(["start", "--task", "add a small thing"])

    def test_start_with_task_text_keeps_the_restore_message_in_say(self):
        self.check_a_planless_start_keeps_the_restore_message(["start", "fix the typo"])

    def git(self, *arguments):
        return subprocess.run(["git", *arguments], cwd=self.repo, check=True, env=self.env, capture_output=True,
                              text=True).stdout

    def set_aside(self):
        # The user shelves the uncommitted work by hand: keep each changed or untracked file's text, then reset it.
        kept = {}
        for line in self.git("status", "--porcelain", "-uall").splitlines():
            name = line[3:]
            path = self.repo / name
            kept[name] = path.read_text() if path.exists() else None
            if line.startswith("??"):
                path.unlink()
                continue
            path.write_text(self.git("show", f"HEAD:{name}"))
        return kept

    def put_back(self, kept):
        for name, text in kept.items():
            path = self.repo / name
            if text is None:
                path.unlink(missing_ok=True)
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)

    def leave_for_a_branch_without_the_plan(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        (self.repo / self.CRITERIA).write_text("AC-1 signed by the coder\n")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        home = self.git("branch", "--show-current").strip()
        kept = self.set_aside()
        self.git("checkout", "-q", "--orphan", "bare-branch")
        self.git("rm", "-rfq", ".")
        return home, kept

    def test_after_plan_edit_on_a_branch_without_the_plan_stops_and_changes_no_state(self):
        home, kept = self.leave_for_a_branch_without_the_plan()
        before = self.state()
        said = self.said()
        outputs = [self.step("after-plan-edit"), self.step("after-plan-edit")]
        for out in outputs:
            self.assertNotIn("Traceback", out)
            self.assertIn("ACTION: stop", out)
            self.assertIn(f"Switch back to branch {home}, then run `! python3 ", out)
            self.assertIn("code-step.py after-plan-edit` from the repo root, "
                          "and tell the session to follow its ACTION line. Tell the user.", out)
        self.assertEqual(said, self.said())
        self.assertEqual(before, self.state())
        self.assertIn("criteriaGuard", self.state())
        self.assertIn("planEditBaseline", self.state())

    def test_after_plan_edit_with_the_plan_deleted_on_the_right_branch_names_the_plan_and_changes_no_state(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.plan).unlink()
        before = self.state()
        said = self.said()
        out = self.step("after-plan-edit")
        self.assertIn("ACTION: stop", out)
        self.assertIn(f"The plan {self.plan} is missing from this checkout", out)
        self.assertIn(f"Restore {self.plan}, then run `! python3 ", out)
        self.assertIn("Tell the user.", out)
        self.assertNotIn("Switch back", out)
        self.assertEqual(before, self.state())
        self.assertEqual(said, self.said())

    def test_after_plan_edit_with_no_recorded_branch_says_to_check_out_the_branch_where_it_started(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        stateFile = self.repo / ".git/code-step/state.json"
        recorded = json.loads(stateFile.read_text())
        recorded["branch"] = "-"
        stateFile.write_text(json.dumps(recorded))
        out = self.step("after-plan-edit")
        self.assertIn("Check out the branch or commit where the plan edit started, then run", out)
        self.assertIn("Tell the user.", out)
        self.assertNotIn("branch -", out)

    def test_start_after_the_plan_edit_wait_gave_up_restores_the_saved_criteria(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten by the plan coder\n")
        self.set_state(dispatchAt=time.time())
        time.sleep(0.7)
        self.wait_env(0.2, "0.05")
        gaveUp = self.step("after-plan-edit")
        self.assertIn("ACTION: stop", gaveUp)
        self.assertEqual("stopped", self.state()["stage"])
        self.assertIn("criteriaGuard", self.state())
        self.step("start")
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        copyPath = self.replaced_copies()[0]
        self.assertIn(f"The text it replaced is in {copyPath}.", self.said())

    def test_tick_during_the_plan_edit_restores_the_saved_criteria(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten by the plan coder\n")
        self.step("tick", "1")
        self.assertEqual("done", self.state()["stage"])
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        copyPath = self.replaced_copies()[0]
        self.assertIn(f"The text it replaced is in {copyPath}.", self.said())

    def test_a_criteria_edit_the_user_makes_after_a_tick_survives_the_next_start(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        self.step("tick", "1")
        (self.repo / self.CRITERIA).write_text("AC-1 the user's own edit\n")
        self.step("start")
        self.assertEqual("AC-1 the user's own edit\n", self.criteria_text())
        self.assertEqual([], self.replaced_copies())
        self.assertNotIn("did not make", self.said())

    def test_tick_on_another_branch_drops_the_guard_and_says_so(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        self.commit_on_new_branch("AC-1 the other branch\n")
        self.step("tick", "1")
        self.assertEqual("AC-1 the other branch\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        self.assertIn("belong to a plan edit on another branch", self.said())

    def open_plan_edit_with_a_late_criteria_write(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten late by the plan coder\n")

    def check_a_verb_stops_while_the_plan_edit_coder_is_out(self, verbArguments):
        self.open_plan_edit_with_a_late_criteria_write()
        before = self.state()
        said = self.said()
        out = self.step(*verbArguments)
        self.assertIn("ACTION: stop", out)
        self.assertIn("`! python3 ", out)
        self.assertIn("code-step.py after-plan-edit` from the repo root first", out)
        self.assertTrue(out.rstrip().endswith("Tell the user."))
        self.assertEqual("AC-1 rewritten late by the plan coder\n", self.criteria_text())
        self.assertEqual(before, self.state())
        self.assertEqual(said, self.said())
        self.assertEqual([], self.replaced_copies())

    def test_tick_stops_while_the_plan_edit_coder_is_out(self):
        self.check_a_verb_stops_while_the_plan_edit_coder_is_out(["tick", "1"])

    def test_start_stops_while_the_plan_edit_coder_is_out(self):
        self.check_a_verb_stops_while_the_plan_edit_coder_is_out(["start"])

    def check_the_stop_leads_through_after_plan_edit_to_a_restore(self, verbArguments, otherSession):
        self.open_plan_edit_with_a_late_criteria_write()
        if otherSession:
            self.set_state(sessionId="other-session")
        self.assertIn("ACTION: stop", self.step(*verbArguments))
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.", session="other-session" if otherSession else self.SESSION)
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten after the stop\n")
        out = self.step("after-plan-edit")
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        self.assertEqual(self.SESSION, self.state()["sessionId"])
        copyPath = self.replaced_copies()[0]
        self.assertEqual("AC-1 rewritten after the stop\n", copyPath.read_text())

    def test_a_tick_stop_then_after_plan_edit_restores_a_late_coder_write(self):
        self.check_the_stop_leads_through_after_plan_edit_to_a_restore(["tick", "1"], False)

    def test_a_start_stop_then_after_plan_edit_restores_a_late_coder_write(self):
        self.check_the_stop_leads_through_after_plan_edit_to_a_restore(["start"], False)

    def test_a_take_over_stop_then_after_plan_edit_under_the_new_session_restores_a_late_coder_write(self):
        self.check_the_stop_leads_through_after_plan_edit_to_a_restore(["start", "--take-over"], True)

    def test_after_plan_edit_before_the_coder_reports_waits_and_restores_a_later_criteria_write(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.wait_env(1, "0.2")
        early = self.step("after-plan-edit")
        self.assertIn("ACTION: wait", early)
        self.assertIn(f"`{self.own_command('after-plan-edit')}`", early)
        self.assertNotIn("AGENT:", early)
        self.assertEqual("plan-coder", self.state()["stage"])
        self.assertIn("criteriaGuard", self.state())
        (self.repo / self.CRITERIA).write_text("AC-1 signed by the coder\n")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        out = self.step("after-plan-edit")
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        self.assertIn("AGENT: review-loop", out)

    def test_after_plan_edit_rerun_on_the_plans_branch_restores_the_criteria_and_dispatches_the_review(self):
        home, kept = self.leave_for_a_branch_without_the_plan()
        self.step("after-plan-edit")
        self.git("checkout", "-q", "-f", home)
        self.put_back(kept)
        out = self.step("after-plan-edit")
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn(self.CRITERIA, self.state()["files"])
        self.assertEqual([], self.state()["flagged"])
        self.assertIn("AGENT: review-loop", out)

    def test_copies_made_in_the_same_second_get_a_counter_and_overwrite_nothing(self):
        folder = self.repo / ".git/code-step-replaced-criteria"
        folder.mkdir()
        now = datetime.datetime.now(datetime.timezone.utc)
        existing = {}
        for offset in range(61):
            stamp = (now + datetime.timedelta(seconds=offset)).strftime("%Y%m%dT%H%M%SZ")
            name = f"{stamp}-01-acceptance-criteria.md"
            (folder / name).write_text(f"old {offset}\n")
            existing[name] = f"old {offset}\n"
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 the new change\n")
        self.step("start")
        for name, text in existing.items():
            self.assertEqual(text, (folder / name).read_text())
        newCopies = [path for path in self.replaced_copies() if path.name not in existing]
        self.assertEqual(["AC-1 the new change\n"], [path.read_text() for path in newCopies])

    def check_a_stale_run_of_an_ended_session_does_not_lock_the_next_start(self, by):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", by, "--ruling", "my own call")
        stateFile = self.repo / ".git/code-step/state.json"
        state = json.loads(stateFile.read_text())
        state["sessionId"] = "an-ended-session"
        state["dispatchAt"] = time.time() - 3 * 60 * 60
        stateFile.write_text(json.dumps(state))
        threeHoursAgo = time.time() - 3 * 60 * 60
        os.utime(stateFile, (threeHoursAgo, threeHoursAgo))
        first = self.step("start", "docs/plans/typo/spec.md")
        self.assertIn("ACTION: ask-user", first)
        second = self.step("start", self.plan)
        self.assertNotIn("Another Claude session", second)
        self.assertIn("ACTION: dispatch", second)

    def test_a_stale_session_ruling_run_does_not_lock_the_next_start(self):
        self.check_a_stale_run_of_an_ended_session_does_not_lock_the_next_start("session")

    def test_a_stale_user_ruling_run_does_not_lock_the_next_start(self):
        self.check_a_stale_run_of_an_ended_session_does_not_lock_the_next_start("user")

    def test_start_after_the_plan_folder_moved_drops_the_saved_criteria_and_does_not_crash(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        shutil.move(self.repo / "docs/plans/orders", self.repo / "docs/plans/orders-v2")
        for attempt in range(2):
            out = self.step("start", "docs/plans/orders-v2/spec.md")
            self.assertNotIn("Traceback", out)
            self.assertIn("ACTION:", out)
            self.assertNotIn("criteriaGuard", self.state())
        self.assertEqual("AC-1 orders exist\n", (self.repo / "docs/plans/orders-v2/acceptance-criteria.md").read_text())

    def test_start_restores_the_criteria_the_coder_edited_during_a_session_plan_edit(self):
        self.check_start_restores_the_criteria(["start"])

    def test_start_on_another_branch_drops_the_saved_criteria_instead_of_restoring_them(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        self.assertIn("criteriaGuard", self.state())
        subprocess.run(["git", "checkout", "-q", "-b", "other-branch"], cwd=self.repo, check=True, env=self.env)
        shutil.rmtree(self.repo / "docs/plans/orders")
        (self.repo / "docs/plans/b").mkdir(parents=True)
        (self.repo / "docs/plans/b/plan.md").write_text(PLAN)
        (self.repo / "docs/plans/b/acceptance-criteria.md").write_text("AC-1 b exists\n")
        early = self.step("start", "docs/plans/nope.md")
        self.assertIn("belong to a plan edit on another branch", self.said())
        self.assertNotIn("criteriaGuard", self.state())
        out = self.step("start", "docs/plans/b/plan.md")
        self.assertNotIn("Traceback", out)
        self.assertIn("ACTION:", out, out)
        self.assertFalse((self.repo / self.CRITERIA).exists())
        self.assertNotIn("criteriaGuard", self.state(), out)

    def test_session_adopt_headline_does_not_say_the_user_adopted_or_rewrite_the_criteria(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        outsideThePrompt = out.split("-----BEGIN PROMPT-----")[0]
        self.assertNotIn("The user adopted", outsideThePrompt)
        self.assertNotIn("acceptance criteria it contradicts", outsideThePrompt)
        self.assertIn("The plan change was adopted by the session, not the user. Dispatch a coder to rewrite the plan "
                      "steps it contradicts. The acceptance criteria do not change.", outsideThePrompt)

    def test_after_plan_edit_leaves_unchanged_criteria_alone_on_a_session_ruling(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        out = self.step("after-plan-edit")
        self.assertNotIn("script restored", out)
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertEqual([], self.replaced_copies())

    def test_after_plan_edit_keeps_the_criteria_the_coder_rewrote_on_a_user_ruling(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "user", "--ruling", "drop the header")
        (self.repo / self.CRITERIA).write_text("AC-1 orders exist, no header\n")
        out = self.step("after-plan-edit")
        self.assertNotIn("script restored", out)
        self.assertEqual("AC-1 orders exist, no header\n", self.criteria_text())
        self.assertIn("changed too", self.said())

    def test_preset_decision_keeps_the_criteria_out_of_the_edit_scope_and_restores_them(self):
        self.env["CODE_STEP_IMPACT_DECISION"] = "adopt"
        original = self.criteria_text()
        out = self.coder_round(self.IMPACT_REPORT)
        ruling = self.state()["ruling"]
        self.assertFalse(ruling["byUser"])
        self.assertEqual("the pre-set decision", ruling["by"])
        self.assertIn(f"Do not edit {self.CRITERIA}.", out)
        self.assertNotIn("Signed off by", out)
        self.assertIn("The acceptance criteria stay as written", out)
        outsideThePrompt = out.split("-----BEGIN PROMPT-----")[0]
        self.assertNotIn("The user adopted", outsideThePrompt)
        self.assertNotIn("acceptance criteria it contradicts", outsideThePrompt)
        self.assertIn("The plan change was adopted by the pre-set decision. Dispatch a coder to rewrite the plan "
                      "steps it contradicts. The acceptance criteria do not change.", outsideThePrompt)
        self.assertIn("  The ruling: pre-set decision 'adopt'; no user was asked", self.plan_text())
        self.assertIn("RESOLVED: the pre-set decision ruled on this disagreement, not the user.",
                      self.state()["planImpact"])
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten\n")
        out = self.step("after-plan-edit")
        self.assertEqual(original, self.criteria_text())
        self.assertIn("the script restored them.", self.said())

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
        self.assertIn(f"finding_id={self.ASK_FINDING_ID}", self.log.read_text())
        self.assertNotIn("desc=", self.log.read_text())
        self.assertIn("ACTION: dispatch", out)
        self.assertIn("AGENT: coder", out)
        self.assertIn("[accepted] f - keep? (backend/src/orders.ts:2)", out)
        self.assertNotIn("marked done", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        self.assertEqual("asks-coder", self.state()["stage"])
        self.assert_dispatch_logged(out, "d3", "coder", "asks-coder", "after-coder")
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
        entries = code_step.parse_plan(lines)["entries"]
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
        self.assertEqual(ids, [e["number"] for e in code_step.parse_plan(planLines)["entries"]])
        for i in ids:
            self.assertEqual(f"## Phase {i}: Title {i}\nbody {i}", code_step.phase_text(planLines, i))
            code_step.mark_phase_done(planPath, i)
        self.assertEqual([True] * len(ids), [e["done"] for e in code_step.parse_plan(
            planPath.read_text().splitlines())["entries"]])

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
        self.assert_dispatch_logged(out, "d2", "coder", "coder", "after-coder")
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

    TASK_TEXT_NAMING_FILES = ("Close gap X: add rules in registry/rules/x.toml, add cases in src/x.rs, "
                              "update docs/plans/<slug>/parity.md")

    def assert_started_planless_with_the_file_naming_text(self, out):
        self.assertIn(f"Implement: {self.TASK_TEXT_NAMING_FILES}", out)
        self.assertNotIn("No plan file", out)
        self.assertNotIn("no plan", out.lower())
        self.assertFalse(self.state().get("plan"))

    def test_task_flag_text_that_names_files_is_task_text(self):
        out = self.step("start", "--task", self.TASK_TEXT_NAMING_FILES)
        self.assert_started_planless_with_the_file_naming_text(out)

    def test_a_positional_argument_with_whitespace_that_names_files_is_task_text(self):
        out = self.step("start", self.TASK_TEXT_NAMING_FILES)
        self.assert_started_planless_with_the_file_naming_text(out)

    def test_a_positional_argument_with_whitespace_that_starts_with_a_real_plan_folder_is_task_text(self):
        text = "docs/plans/orders needs its parity table updated"
        out = self.step("start", text)
        self.assertIn(f"Implement: {text}", out)
        self.assertNotIn("Phase 1 of", out)

    def test_a_positional_argument_with_whitespace_that_is_a_real_plan_file_is_a_plan_path(self):
        spacedPlan = "docs/plans/orders/spec copy.md"
        (self.repo / spacedPlan).write_text(self.plan_text())
        out = self.step("start", spacedPlan)
        self.assertIn(f"Implement Phase 1 of `{spacedPlan}`", out)
        self.assertNotIn(f"Implement: {spacedPlan}", out)

    def test_a_positional_argument_with_whitespace_that_is_not_a_file_is_task_text(self):
        notAFile = "docs/plans/orders/spec copy.md"
        out = self.step("start", notAFile)
        self.assertIn(f"Implement: {notAFile}", out)
        self.assertNotIn("Phase 1 of", out)

    def test_a_positional_argument_without_whitespace_is_still_a_plan_path(self):
        out = self.step("start", self.plan)
        self.assertIn(f"Implement Phase 1 of `{self.plan}`", out)

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
        self.assertIn("ACTION: stop", self.step("decide", "keep", "--by", "user", "--ruling", "keep it"))

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
        out = self.step("decide", "keep", "--by", "user", "--ruling", "keep it")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn(self.SKIP_LINE, out)
        self.assertIn("iter: 0", out)

    def test_ruling_raised_by_the_coder_before_any_review_gets_a_full_first_review(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "keep", "--by", "user", "--ruling", "keep it")
        self.assertIn("AGENT: review-loop", out)
        self.assertNotIn(self.SKIP_LINE, out)

    def test_adopted_plan_change_after_a_review_refreshes_the_phase_text_and_reviews_once(self):
        self.coder_round()
        self.hook("review-loop", "status: plan-impact\niter: 1\nplan_impact: |\n    PLAN-IMPACT:\n      found: B\n")
        self.step("after-review")
        out = self.step("decide", "adopt", "--by", "user", "--ruling", "adopt it")
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

    ALREADY_DONE_REPORT = "ALREADY-DONE: 1 — backend/src/orders.ts:2\nThe ask was already built; nothing to change."

    def test_asks_coder_prompt_asks_for_an_already_done_line_for_each_ask_that_needs_no_edit(self):
        out = self.apply_first_ask()
        self.assertIn("ALREADY-DONE: <ask number> — <file:line>", out)

    def test_asks_coder_that_changed_nothing_runs_the_verification_and_finishes_the_phase(self):
        self.apply_first_ask()
        self.hook("coder", self.ALREADY_DONE_REPORT)
        out = self.step("after-coder")
        self.assertNotIn("AGENT: review-loop", out)
        self.assertIn("Phase 1 marked done", out)
        self.assertMarkedClean(out)
        self.assertIn("- [x] Phase 1:", self.plan_text())
        self.assertIn("already in the code", self.said())
        self.assertIn("The ask was already built", self.said())

    def test_asks_coder_that_changed_nothing_stops_when_the_verification_fails(self):
        self.set_verification('- [ ] **Check**: fails - `bash -c "exit 1"`')
        self.apply_first_ask()
        self.hook("coder", self.ALREADY_DONE_REPORT)
        out = self.step("after-coder")
        self.assertIn("Automated Verification failed", out)
        self.assertEqual("verification", self.state()["stopReason"])
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def assert_unchanged_asks_coder_stops(self, report):
        self.apply_first_ask()
        self.hook("coder", report)
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: review-loop", out)
        self.assertNotIn("marked done", out)
        self.assertEqual("stopped", self.state()["stage"])
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def test_asks_coder_that_changed_nothing_and_has_an_open_question_stops(self):
        self.assert_unchanged_asks_coder_stops("Open question: which name should the rename use?")

    def test_asks_coder_that_changed_nothing_and_recommends_eng_spec_stops(self):
        self.assert_unchanged_asks_coder_stops("This is architectural; run /eng-spec.")

    def test_asks_coder_that_changed_nothing_and_could_not_apply_the_ask_stops(self):
        self.assert_unchanged_asks_coder_stops("Could not apply the rename; left as is.")

    def test_asks_coder_that_changed_nothing_because_a_hook_blocked_the_edit_stops(self):
        self.assert_unchanged_asks_coder_stops(
            "The Edit on backend/src/orders.ts was blocked by a hook, so I could not apply ask 1.")

    def test_asks_coder_that_changed_nothing_and_calls_the_ask_ambiguous_stops(self):
        self.assert_unchanged_asks_coder_stops("Ask 1 is ambiguous, so I made no change.")

    def test_asks_coder_that_changed_nothing_and_recommends_eng_spec_before_any_change_stops(self):
        self.assert_unchanged_asks_coder_stops("I recommend running eng-spec before any change.")

    def test_asks_coder_that_changed_nothing_with_no_already_done_line_stops_even_when_it_says_done(self):
        self.assert_unchanged_asks_coder_stops("The ask was already built; nothing to change.")

    def test_asks_coder_already_done_line_without_a_file_and_line_does_not_count(self):
        self.assert_unchanged_asks_coder_stops("ALREADY-DONE: 1 —")

    def test_asks_coder_already_done_line_with_n_a_as_its_location_stops(self):
        self.assert_unchanged_asks_coder_stops("ALREADY-DONE: 1 — n/a")

    def test_asks_coder_already_done_line_with_the_placeholder_location_stops(self):
        self.assert_unchanged_asks_coder_stops("ALREADY-DONE: 1 — <file:line>")

    def test_asks_coder_already_done_line_with_prose_as_its_location_stops(self):
        self.assert_unchanged_asks_coder_stops("ALREADY-DONE: 1 — could not apply it, the edit failed")

    def test_asks_coder_already_done_line_naming_a_real_file_without_a_line_stops(self):
        self.assert_unchanged_asks_coder_stops("ALREADY-DONE: 1 — backend/src/orders.ts")

    def test_asks_coder_already_done_line_naming_a_file_that_does_not_exist_stops(self):
        self.assert_unchanged_asks_coder_stops("ALREADY-DONE: 1 — backend/src/nope.ts:9")

    def test_asks_coder_already_done_line_with_text_after_a_real_file_and_line_stops(self):
        self.assert_unchanged_asks_coder_stops(
            "ALREADY-DONE: 1 — backend/src/orders.ts:2 not done, the Edit was blocked.")

    def assert_already_done_line_finishes_the_phase(self, line):
        self.apply_first_ask()
        self.hook("coder", line)
        out = self.step("after-coder")
        self.assertIn("Phase 1 marked done", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_asks_coder_already_done_line_naming_a_real_file_and_line_finishes_the_phase(self):
        self.assert_already_done_line_finishes_the_phase("ALREADY-DONE: 1 — backend/src/orders.ts:2")

    def test_asks_coder_already_done_line_with_backticks_and_a_line_range_finishes_the_phase(self):
        self.assert_already_done_line_finishes_the_phase("ALREADY-DONE: 1 — `backend/src/orders.ts:1-2`")

    def test_asks_coder_already_done_line_with_a_closing_period_finishes_the_phase(self):
        self.assert_already_done_line_finishes_the_phase("ALREADY-DONE: 1 — backend/src/orders.ts:2.")

    def test_asks_coder_already_done_line_for_another_ask_number_does_not_count(self):
        self.assert_unchanged_asks_coder_stops("ALREADY-DONE: 2 — backend/src/orders.ts:2")

    def test_an_asks_coder_state_without_its_accepted_asks_does_not_tick_the_phase(self):
        self.apply_first_ask()
        self.set_state(acceptedAsks=None)
        self.hook("coder", "Nothing to report.")
        result = run(self.repo, self.env, "after-coder")
        self.assertNotIn("marked done", result.stdout)
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def test_asks_coder_already_done_line_with_an_open_question_stops(self):
        self.assert_unchanged_asks_coder_stops(self.ALREADY_DONE_REPORT + "\nOpen question: which name should it use?")

    def test_asks_coder_already_done_line_with_an_eng_spec_recommendation_stops(self):
        self.assert_unchanged_asks_coder_stops(self.ALREADY_DONE_REPORT + "\nThe rest needs /eng-spec.")

    def test_asks_coder_already_done_line_with_a_plan_impact_report_stops(self):
        self.assert_unchanged_asks_coder_stops(self.ALREADY_DONE_REPORT + "\n" + self.IMPACT_REPORT)

    def accept_two_asks(self):
        secondAsk = ('{"finding": "g", "file_line": "backend/src/orders.ts:3", "question": "rename?", '
                     '"gate": "code-reviewer", "class": "correctness", "finding_id": "fedcba9876543210"}')
        twoAsks = self.ASK.replace("}]", "}, " + secondAsk + "]")
        self.coder_round()
        self.hook("review-loop", twoAsks.replace("iter: 1", "iter: 2"))
        self.step("after-review")
        self.step("asks-done", "accepted", "accepted")

    def test_asks_coder_that_changed_nothing_covers_only_some_of_two_asks_stops(self):
        self.accept_two_asks()
        self.hook("coder", "ALREADY-DONE: 1 — backend/src/orders.ts:2")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertEqual("stopped", self.state()["stage"])
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def test_asks_coder_that_changed_nothing_names_every_one_of_two_asks_finishes_the_phase(self):
        self.accept_two_asks()
        self.hook("coder", "ALREADY-DONE: 1 — backend/src/orders.ts:2\nALREADY-DONE: 2 - backend/src/orders.ts:3")
        out = self.step("after-coder")
        self.assertIn("Phase 1 marked done", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_asks_coder_that_changed_nothing_and_reports_a_plan_impact_stops(self):
        self.assert_unchanged_asks_coder_stops(self.IMPACT_REPORT)

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

    def test_fork_handback_names_after_plan_edit_while_the_plan_edit_coder_is_out(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        reason = json.loads(self.fork_handback().stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn(self.own_command("after-plan-edit"), reason)

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

    def test_the_commit_command_includes_the_plan_when_it_was_dirty_before_the_phase_and_says_so(self):
        (self.repo / self.plan).write_text(self.plan_text().replace("Add orders.", "Add orders and returns."))
        self.finish_phase_one()
        self.assertEqual(1, len(self.commit_lines()))
        self.assertIn(f" {self.plan}", self.commit_lines()[0])
        self.assertIn(f"{self.plan} had uncommitted edits before the phase", self.said())
        self.assertNotIn(f"left out of the commit: {self.plan}", self.said())
        subprocess.run(self.commit_lines()[0], shell=True, cwd=self.repo, check=True, env=self.env, capture_output=True)
        leftDirty = subprocess.run(["git", "status", "--porcelain", "--", self.plan], cwd=self.repo,
                                   capture_output=True, text=True, env=self.env).stdout
        self.assertEqual("", leftDirty)

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

    def leave_dispatch_of(self, session):
        self.start_phase_one()
        self.set_state(sessionId=session, dispatchAt=time.time() - 60)

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

    def leave_asks_of(self, session):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")
        self.assertEqual("asks", self.state()["stage"])
        self.set_state(sessionId=session)
        stateFile = self.repo / ".git/code-step/state.json"
        past = time.time() - 60
        os.utime(stateFile, (past, past))

    def test_start_stops_when_another_session_waits_at_asks(self):
        self.leave_asks_of("other-session")
        out = self.step("start", self.plan, "+fast")
        self.assertIn("ACTION: stop", out)
        self.assertIn("in another session; this block lifts at", out)
        self.assertIn("invoke Skill code with `--take-over " + self.plan + " +fast`", out)
        self.assertEqual("asks", self.state()["stage"])

    GUARDED_RUNS = [
        ("coder", None, "dispatch"), ("review", None, "dispatch"), ("asks-coder", None, "dispatch"),
        ("plan-coder", None, "dispatch"),
        ("stopped", "invalid-packet", "state-file"),
        ("asks", None, "state-file"), ("impact-coder", None, "state-file"), ("impact-review", None, "state-file"),
        ("skill", None, "state-file"),
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
                lifted = self.step("start", self.plan)
                if stage == "plan-coder":
                    self.assertIn("code-step.py after-plan-edit` from the repo root first", lifted)
                else:
                    self.assertIn("ACTION: dispatch", lifted)

                self.leave_run_of_another_session(stage, stopReason, ageKind, 60)
                takenOver = self.step("start", self.plan, "--take-over")
                if stage == "plan-coder":
                    self.assertIn("code-step.py after-plan-edit` from the repo root first", takenOver)
                    continue
                self.assertIn("ACTION: dispatch", takenOver)

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
        self.assertIn("(Phase 1): marked done with `tick`", self.plan_text())
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

    def test_the_stop_hook_blocks_the_fork_naming_after_plan_edit_while_the_plan_edit_coder_is_out(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        first = json.loads(self.stop_hook())
        self.assertEqual("block", first["decision"])
        self.assertIn(self.own_command("after-plan-edit"), first["reason"])

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

    # ---------- reported defects ----------

    def replace_phase_one_verification(self, lines):
        text = self.plan_text()
        start = text.index("- [ ] **Test-verified**")
        end = text.index("#### Manual Verification:")
        (self.repo / self.plan).write_text(text[:start] + lines + "\n\n" + text[end:])

    def test_a_cargo_verification_item_is_read_as_a_command(self):
        item = "- [ ] **Tests**: the streams pass - `cargo test --test side_streams && cargo clippy -- -D warnings`"
        self.assertEqual("cargo test --test side_streams && cargo clippy -- -D warnings",
                         code_step.verification_command(item))

    def test_a_phase_whose_verification_items_yield_no_command_is_not_marked_done(self):
        self.coder_round_then_edit_verification("- [ ] **Check**: the streams pass, see the log")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("nothing was run", out)
        self.assertIn("see the log - it has no backticked command", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        self.assertEqual("stopped", self.state()["stage"])

    def test_the_review_prompt_is_built_from_the_latest_coder_only(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: stale change\nWHY: backend/src/stale.ts 1-2 — stale reason", agentId="a0")
        self.hook("coder", "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters", agentId="a1")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("order matters", out)
        self.assertNotIn("stale", out)
        self.assertNotIn("stale", self.said())
        self.assertEqual(["orders exist"], self.state()["behavior"])

    def stop_the_coder_on_a_blocked_report(self):
        self.start_phase_one()
        self.hook("coder", "BEHAVIOR: none\nblocked on two steps")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_a_coder_resumed_after_a_stop_goes_to_review_even_when_it_committed(self):
        self.stop_the_coder_on_a_blocked_report()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.commit_all()
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        out = self.step("after-coder")
        self.assertNotIn("no coder dispatch pending", out)
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("- path: backend/src/orders.ts", out)
        self.assertEqual("review", self.state()["stage"])

    def test_a_resumed_coder_that_changed_nothing_stops_again(self):
        self.stop_the_coder_on_a_blocked_report()
        self.hook("coder", "BEHAVIOR: none\nstill blocked")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: review-loop", out)

    def test_start_phase_on_a_done_phase_dispatches_no_coder(self):
        self.mark_phases_done(2)
        out = self.step("start", self.plan, "--phase", "2")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("already marked done", out)
        self.assertNotIn('"stage": "coder"', self.step("status"))

    def test_tick_claims_neither_the_users_word_nor_a_missing_review(self):
        self.start_phase_one()
        out = self.step("tick", "1")
        self.assertNotIn("user's word", out)
        deviation = [line for line in self.plan_text().splitlines() if "(Phase 1): marked done" in line]
        self.assertEqual(1, len(deviation))
        self.assertNotIn("by the user", deviation[0])
        self.assertNotIn("No review ran", deviation[0])
        self.assertNotIn("no gate ran", deviation[0])

    def test_a_deeper_phase_heading_inside_a_phase_is_a_note_not_a_section(self):
        record = "\n#### Phase 2 record (2026-10-21):\n\nDone by hand.\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(
            "**File**: `backend/src/totals.ts`\n", "**File**: `backend/src/totals.ts`\n" + record))
        plan = code_step.parse_plan(self.plan_text().splitlines())
        self.assertEqual([], plan["failures"])
        self.assertEqual({"1", "2", "3", "4"}, set(plan["sections"]))
        self.assertIn("Done by hand.", code_step.phase_text(self.plan_text().splitlines(), "2"))
        event = {"cwd": str(self.repo), "tool_input": {"file_path": str(self.repo / self.plan)}}
        self.assertEqual(0, run(self.repo, self.env, "plan-hook", stdin=json.dumps(event)).returncode)

    def test_the_closing_phase_commit_line_names_only_the_files_the_phase_changed(self):
        self.mark_phases_done(1, 2, 3)
        self.commit_all()
        (self.repo / "docs/plans/other").mkdir()
        (self.repo / "docs/plans/other/spec.md").write_text("another ticket's plan\n")
        self.step("start", self.plan)
        self.step("skill-done", "pass")
        commitLine = self.state()["commitLine"]
        self.assertNotIn("other", commitLine)
        self.assertIn("docs/plans/orders/spec.md", commitLine)

    def test_the_commit_subject_carries_the_ticket_id_of_the_plan_folder_or_branch(self):
        self.assertEqual("LED-15: ", code_step.ticket_prefix({"plan": "docs/plans/LED-15-recap/spec.md"}))
        self.assertEqual("LED-15: ", code_step.ticket_prefix({"plan": "docs/plans/orders/spec.md",
                                                               "branch": "brandon/LED-15-recap"}))
        self.assertEqual("", code_step.ticket_prefix({"plan": "docs/plans/orders/spec.md", "branch": "main"}))
        self.assertEqual("", code_step.ticket_prefix({"plan": None, "branch": "main"}))

    def test_a_phase_flag_run_ends_after_that_phase_even_with_an_earlier_phase_open(self):
        self.step("start", self.plan, "--phase", "2")
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals add up\nREVIEW: recommended")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertNotIn("ACTION: auto-advance", out)
        self.assertNotIn("start +fast", out)
        self.assertFalse(self.state()["autoAdvance"])
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        self.assertIn("- [x] Phase 2:", self.plan_text())

    def test_a_hand_back_saved_before_the_latest_dispatch_is_not_read(self):
        self.start_phase_one()
        dispatchAt = self.state()["dispatchAt"]
        staleRow = {"ts": dispatchAt - 100, "agent_type": "coder", "agent_id": "old", "stage": "coder",
                    "message": "PLAN-IMPACT: yes\nBEHAVIOR: stale"}
        (self.repo / ".git/code-step/reports.jsonl").write_text(json.dumps(staleRow) + "\n")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        out = self.step("after-coder")
        self.assertIn("No coder report was saved", out)
        self.assertNotIn("ask-user", out)

    def allow_coder_at_the_gate(self, agentId):
        gatePath = self.repo / ".git/coder-gate.json"
        gate = json.loads(gatePath.read_text())
        gate["coders"][agentId] = {"runs": 1, "denies": 0, "failed": [], "skipped": [], "result": "pass"}
        gatePath.write_text(json.dumps(gate))

    def add_a_line_to_phase_one(self):
        (self.repo / self.plan).write_text(self.plan_text().replace(
            "**File**: `backend/src/orders.test.ts`\n", "**File**: `backend/src/orders.test.ts`\nAlso total the orders.\n", 1))

    def test_an_addendum_coders_report_joins_the_first_coders_report(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters", agentId="a1")
        self.add_a_line_to_phase_one()
        out = self.step("after-coder")
        self.assertIn("gained lines", out)
        self.assertIn("AGENT: coder", out)
        self.allow_coder_at_the_gate("a2")
        self.hook("coder", "BEHAVIOR: totals added\nWHY: backend/src/orders.ts 8-9 — totals line", agentId="a2")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("order matters", out)
        self.assertIn("totals line", out)
        self.assertEqual(["orders exist", "totals added"], self.state()["behavior"])

    def test_an_addendum_coder_that_recommends_eng_spec_stops_with_both_reports(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: orders exist", agentId="a1")
        self.add_a_line_to_phase_one()
        self.step("after-coder")
        self.allow_coder_at_the_gate("a2")
        self.hook("coder", "BEHAVIOR: none\nthe totals need /eng-spec", agentId="a2")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("orders exist", out)
        self.assertIn("the totals need /eng-spec", out)

    def test_a_coder_that_is_not_the_stopped_one_does_not_revive_the_run(self):
        self.stop_the_coder_on_a_blocked_report()
        self.hook("coder", "BEHAVIOR: another coder\nREVIEW: recommended", agentId="other")
        self.assertEqual("stopped", self.state()["stage"])
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended", agentId="a1")
        self.assertEqual("coder", self.state()["stage"])

    def test_the_stop_on_a_blocked_coder_says_to_resume_it_with_send_message_then_run_after_coder(self):
        self.start_phase_one()
        self.hook("coder", "BEHAVIOR: none\nblocked on two steps")
        out = self.step("after-coder")
        self.assertIn("SendMessage", out)
        self.assertIn(self.own_command("after-coder"), out)

    def test_a_word_dash_number_in_a_plan_folder_or_branch_is_not_a_ticket_id(self):
        for name in ("upgrade-node-20", "oauth-2", "fix-1", "phase-2", "python-3", "led-15"):
            with self.subTest(name=name):
                self.assertEqual("", code_step.ticket_prefix({"plan": f"work/{name}/spec.md", "branch": name}))
        self.assertEqual("ABC2-7: ", code_step.ticket_prefix({"plan": "work/upgrade-node-20/spec.md",
                                                               "branch": "brandon/ABC2-7-upgrade"}))

    def test_an_automated_verification_section_of_only_not_applicable_items_is_empty(self):
        for item in ("- [ ] N/A — docs only", "- [ ] **N/A**: nothing to run", "- [x] none"):
            with self.subTest(item=item):
                self.assertEqual(([], [], []), code_step.run_verification_commands(
                    self.repo, f"#### Automated Verification:\n\n{item}\n\n#### Manual Verification:\n"))

    def test_a_phase_with_only_a_not_applicable_automated_item_is_marked_done(self):
        self.replace_phase_one_verification("- [ ] N/A — docs only")
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertNotIn("no command could be read", out)
        self.assertEqual("done", self.state()["stage"])

    def test_a_script_path_or_sh_command_is_read_as_a_verification_command(self):
        self.assertEqual("./scripts/check.sh --fast", code_step.verification_command(
            "- [ ] **Check**: passes - `./scripts/check.sh --fast`"))
        self.assertEqual("sh scripts/check.sh", code_step.verification_command("- [ ] **Check**: `sh scripts/check.sh`"))

    def test_a_command_with_leading_variable_assignments_runs_with_them_set(self):
        self.set_verification("- [ ] **Env**: `VERIFY_SEEN=yes bash -c 'test \"$VERIFY_SEEN\" = yes'`")
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)

        out = self.step("after-review")

        self.assertNotIn("no command could be read", out)
        self.assertEqual("done", self.state()["stage"])

    def test_the_prefixed_command_wins_over_a_later_span_without_a_prefix(self):
        item = "- [ ] **Env**: `PARITY_PATH=/x/y.py cargo test --test watch_parity`, not `cargo test`"

        self.assertEqual("PARITY_PATH=/x/y.py cargo test --test watch_parity", code_step.verification_command(item))

    def test_a_quoted_assignment_value_with_spaces_is_kept_in_the_command(self):
        item = "- [ ] **Env**: `GREETING=\"a b\" bash -c 'echo hi'`"

        self.assertEqual("GREETING=\"a b\" bash -c 'echo hi'", code_step.verification_command(item))

    def test_an_assignment_followed_by_no_command_or_by_a_program_that_is_not_installed_is_not_a_verification_command(self):
        for item in ("- [ ] **Env**: set `PARITY_PATH=/x/y.py` first", "- [ ] **Env**: `PARITY_PATH=/x/y.py nosuchprogram hi`"):
            with self.subTest(item=item):
                self.assertIsNone(code_step.verification_command(item))

    def test_an_assignment_that_expands_a_variable_or_runs_a_command_still_leads_to_the_command(self):
        for command in ("LEDGER_REAL_DOTFILES=$HOME/dotfiles cargo test --test watch_parity",
                        "PATH=/x/bin:$PATH cargo test", 'DATABASE_URL="$TEST_DB" pytest -q',
                        "T=$(find . -name x) cargo test", "A=1 B=$HOME/x make all"):
            with self.subTest(command=command):
                self.assertTrue(code_step.COMMAND_START.match(command))
                self.assertEqual(command, code_step.verification_command(f"- [ ] **Check**: passes - `{command}`"))

    def test_an_assignment_followed_by_a_control_operator_is_not_a_command_start(self):
        for span in ("A=1 && cargo test", "A=1 ; cargo test", "A=1 | cat", "A=1 # note"):
            with self.subTest(span=span):
                self.assertIsNone(code_step.COMMAND_START.match(span))

    def test_a_whole_suite_command_with_a_variable_prefix_is_still_skipped(self):
        section = "#### Automated Verification:\n\n- [ ] **All**: `CI=1 npm test`\n\n#### Manual Verification:\n"

        results, skipped, unparsed = code_step.run_verification_commands(self.repo, section)

        self.assertEqual(([], ["CI=1 npm test"], []), (results, skipped, unparsed))

    def test_the_unparsed_verification_stop_names_tick_for_checks_that_cannot_be_automated(self):
        self.coder_round_then_edit_verification("- [ ] **Check**: the streams pass, see the log")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("`tick 1`", out)

    def test_a_plan_impact_block_is_found_in_each_shape_a_report_writes_it(self):
        block = "assumed: the table has a key\nfound: it has none\nchanges: add a migration"
        shapes = {
            "indented": "BEHAVIOR: none\nPLAN-IMPACT:\n  " + block.replace("\n", "\n  ") + "\nPLAN-IMPACT: yes",
            "keys at column 0": "BEHAVIOR: none\nPLAN-IMPACT:\n" + block + "\nPLAN-IMPACT: yes",
            "bold header and a blank line": "PLAN-IMPACT:**\n\n  " + block.replace("\n", "\n  "),
            "bold keys": "**PLAN-IMPACT:**\n- **assumed:** a\n- **found:** b\n- **changes:** c",
        }
        for name, report in shapes.items():
            with self.subTest(name):
                found = code_step.plan_impact_block(report)
                self.assertIsNotNone(found)
                self.assertNotIn("block not found", found)
                self.assertIn("assumed", found)
                self.assertIn("changes", found)

    def test_a_run_without_the_phase_flag_still_advances(self):
        self.mark_phases_done(1)
        self.step("start", self.plan)
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals add up\nREVIEW: recommended")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("ACTION: auto-advance", self.step("after-review"))

    # ---------- after-coder never reads a report before the dispatched coder's final hand-back ----------

    def set_coder_gate_result(self, result, agentId):
        gatePath = self.repo / ".git/coder-gate.json"
        gate = json.loads(gatePath.read_text())
        gate["coders"][agentId] = {"runs": 1, "denies": 0, "failed": [], "skipped": [], "result": result}
        gatePath.write_text(json.dumps(gate))

    def test_after_coder_stops_when_the_state_has_no_dispatch_time_and_says_to_start_the_phase_again(self):
        self.begin_coder()
        self.set_state(dispatchAt=None)
        self.wait_env(1, "0.2")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("records no dispatch time", out)
        self.assertIn("start --phase 1", out)
        self.assertNotIn("ACTION: ask-user", out)
        self.assertNotIn("AGENT: review-loop", out)
        self.assertEqual("coder", self.state()["stage"])

    def test_after_coder_with_no_dispatch_time_does_not_read_an_old_row_as_the_report(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: none\nPLAN-IMPACT: yes")
        self.set_state(dispatchAt=None)
        self.wait_env(1, "0.2")
        out = self.step("after-coder")
        self.assertNotIn("ACTION: ask-user", out)
        self.assertIn("records no dispatch time", out)

    def test_a_plan_impact_in_the_row_of_a_coder_the_gate_has_not_passed_is_not_raised(self):
        self.begin_coder()
        self.set_coder_gate_result("deny", "a0")
        self.hook("coder", "BEHAVIOR: still working\nPLAN-IMPACT: yes", agentId="a0")
        self.hook("coder", self.CODER_REPORT)
        out = self.step("after-coder")
        self.assertNotIn("ACTION: ask-user", out)
        self.assertIn("AGENT: review-loop", out)

    def test_a_final_report_that_names_a_plan_impact_still_asks_the_user(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: orders exist\nPLAN-IMPACT: yes")
        self.assertIn("ACTION: ask-user", self.step("after-coder"))

    def test_after_coder_waits_for_a_coder_resumed_after_a_stop_instead_of_saying_to_start(self):
        self.stop_the_coder_on_a_blocked_report()
        self.wait_env(1, "0.2")
        out = self.step("after-coder")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("Run `start` first", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_the_wait_cap_for_a_resumed_coder_counts_from_the_first_wait_not_from_the_old_stop(self):
        self.stop_the_coder_on_a_blocked_report()
        self.set_state(resumableCoderAt=time.time() - 100)
        (self.repo / ".git/code-step/reports.jsonl").write_text("")
        self.wait_env(1, "0.2")
        out = self.step("after-coder")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("has not handed back in", out)
        self.assertIsNotNone(self.state().get("resumeWaitAt"))

    def test_repeated_waits_on_a_resumed_coder_end_in_the_cap_stop(self):
        self.stop_the_coder_on_a_blocked_report()
        self.wait_env(1, "0.2")
        self.step("after-coder")
        self.set_state(resumeWaitAt=time.time() - 100)
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("has not handed back in", out)

    def test_the_first_wait_time_of_a_resumed_coder_is_saved_once(self):
        self.stop_the_coder_on_a_blocked_report()
        self.wait_env(1, "0.2")
        self.step("after-coder")
        firstWaitAt = self.state()["resumeWaitAt"]
        self.step("after-coder")
        self.assertEqual(firstWaitAt, self.state()["resumeWaitAt"])

    def test_the_hand_back_of_a_resumed_coder_clears_the_saved_first_wait_time(self):
        self.stop_the_coder_on_a_blocked_report()
        self.wait_env(1, "0.2")
        self.step("after-coder")
        self.hook("coder", "BEHAVIOR: orders exist")
        self.assertNotIn("resumeWaitAt", self.state())

    def test_after_coder_says_the_resumed_coder_has_not_handed_back_when_it_runs_with_no_wait(self):
        self.stop_the_coder_on_a_blocked_report()
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("resumed coder has not handed back yet", out)
        self.assertNotIn("Run `start` first", out)

    def test_a_plan_impact_of_a_coder_that_stopped_on_no_reviewable_change_is_raised_after_the_resume(self):
        self.start_phase_one()
        self.hook("coder", "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes")
        self.assertIn("ACTION: stop", self.step("after-coder"))
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        out = self.step("after-coder")
        self.assertIn("ACTION: ask-user", out)
        self.assertNotIn("stoppedCoderReport", self.state())

    def test_after_coder_goes_to_review_when_the_resumed_coder_hands_back_while_it_waits(self):
        self.stop_the_coder_on_a_blocked_report()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.wait_env(20)
        self.late_hook(1, "coder", self.CODER_REPORT)
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual("review", self.state()["stage"])

    def adopt_plan_change_with_the_plan_coder_out(self):
        report = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes"
        self.coder_round(report)
        out = self.step("decide", "adopt", "--by", "user", "--ruling", "adopt it, drop the header")
        self.assertIn("AGENT: coder", out)
        self.assertEqual("plan-coder", self.state()["stage"])

    def test_after_plan_edit_stops_when_the_state_has_no_dispatch_time_instead_of_dispatching_the_review(self):
        self.adopt_plan_change_with_the_plan_coder_out()
        self.set_state(dispatchAt=None)
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        self.wait_env(1, "0.2")
        out = self.step("after-plan-edit")
        self.assertIn("ACTION: stop", out)
        self.assertIn("records no dispatch time", out)
        self.assertIn("start --phase 1", out)
        self.assertNotIn("AGENT: review-loop", out)
        self.assertEqual("plan-coder", self.state()["stage"])

    def test_after_plan_edit_with_a_dispatch_waits_for_the_plan_coder_row_before_the_review(self):
        self.adopt_plan_change_with_the_plan_coder_out()
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        self.wait_env(1, "0.2")
        self.assertIn("ACTION: wait", self.step("after-plan-edit"))
        self.hook("coder", "BEHAVIOR: plan rewritten", agentId="plan-edit")
        self.assertIn("AGENT: review-loop", self.step("after-plan-edit"))

    # ---------- a review-loop resumed after the wait cap is the pending review ----------

    def stop_the_review_at_the_wait_cap(self):
        self.coder_round()
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2")
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertEqual("stopped", self.state()["stage"])
        return out

    def test_the_stop_at_the_review_wait_cap_says_to_run_after_review_when_the_loop_is_resumed(self):
        out = self.stop_the_review_at_the_wait_cap()
        self.assertIn("SendMessage", out)
        self.assertIn(self.own_command("after-review"), out)

    def test_after_review_waits_for_a_review_loop_resumed_after_the_cap(self):
        self.stop_the_review_at_the_wait_cap()
        out = self.step("after-review")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("no review pending", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_repeated_waits_on_a_review_loop_resumed_after_the_cap_end_in_the_cap_stop(self):
        self.stop_the_review_at_the_wait_cap()
        self.assertIn("ACTION: wait", self.step("after-review"))
        firstWaitAt = self.state()["resumeWaitAt"]
        self.assertIn("ACTION: wait", self.step("after-review"))
        self.assertEqual(firstWaitAt, self.state()["resumeWaitAt"])
        self.set_state(resumeWaitAt=time.time() - 100)
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("has not handed back in", out)

    def test_after_review_says_the_resumed_review_loop_has_not_handed_back_when_it_runs_with_no_wait(self):
        self.stop_the_review_at_the_wait_cap()
        self.wait_env(0)
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("resumed review-loop has not handed back yet", out)
        self.assertNotIn("no review pending", out)
        self.assertNotIn("Run `start` first", out)

    def test_the_hand_back_of_a_review_loop_resumed_after_the_cap_puts_the_stage_back_to_review(self):
        self.stop_the_review_at_the_wait_cap()
        self.step("after-review")
        self.hook("review-loop", self.LOOP_OK)
        state = self.state()
        self.assertEqual("review", state["stage"])
        self.assertNotIn("resumableReview", state)
        self.assertNotIn("resumeWaitAt", state)

    def test_a_review_loop_resumed_after_the_cap_that_hands_back_is_the_pending_review(self):
        self.stop_the_review_at_the_wait_cap()
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertNotIn("no review pending", out)
        self.assertIn("Phase 1 marked done", out)
        self.assertNotEqual("stopped", self.state()["stage"])

    # ---------- start on a finished plan names the follow-up command ----------

    def test_start_on_a_plan_with_every_phase_done_names_the_task_command_for_a_follow_up(self):
        self.mark_phases_done(1, 2, 3, 4)
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn('start --task "<text>"', out)

    def test_bare_start_on_a_finished_single_phase_plan_names_the_task_command_for_a_follow_up(self):
        subprocess.run(["git", "checkout", "-q", "-b", "ABC-1-x"], cwd=self.repo, check=True, env=self.env)
        self.plan = "docs/plans/ABC-1-x/spec.md"
        (self.repo / "docs/plans/ABC-1-x").mkdir()
        (self.repo / self.plan).write_text(self.SINGLE_PLAN)
        for command in (["git", "add", "-A"], ["git", "commit", "-qm", "plan"]):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True, env=self.env)
        self.finish_phase_one()
        out = self.step("start")
        self.assertNotIn("AGENT: coder", out)
        self.assertIn('start --task "<text>"', out)

    # ---------- start skips an open phase whose status line carries a gate clause ----------

    def gate_phases(self, *numbers, condition="LED-5 merged"):
        text = self.plan_text()
        for number in numbers:
            line = next(line for line in text.splitlines() if line.startswith(f"- [ ] Phase {number}:"))
            text = text.replace(line, f"{line} — gate: {condition}")
        (self.repo / self.plan).write_text(text)

    def test_start_stops_at_a_gated_open_phase_and_names_it_its_gate_and_the_next_ungated_phase(self):
        self.gate_phases(1)
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT:", out)
        self.assertIn("Phase 1 (gate: LED-5 merged)", out)
        self.assertIn("The next open phase without a gate is Phase 2.", out)
        self.assertIn("`start --phase <id>` runs one anyway.", out)
        self.assertIn("no coder was dispatched", out)
        self.assertEqual("no code-step state", self.step("status").strip())

    def test_start_with_a_phase_id_runs_a_gated_phase(self):
        self.gate_phases(1)
        out = self.step("start", self.plan, "--phase", "1")
        self.assertIn("AGENT: coder", out)
        self.assertNotIn("gate clause", out)
        self.assertEqual("1", self.state()["phase"])

    def test_start_with_the_id_of_an_ungated_phase_past_a_gated_one_runs_it(self):
        self.gate_phases(1)
        out = self.step("start", self.plan, "--phase", "2")
        self.assertIn("AGENT: coder", out)
        self.assertEqual("2", self.state()["phase"])

    def test_start_names_only_the_gated_phases_ahead_of_the_next_ungated_phase(self):
        self.gate_phases(1, 3)
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertIn("Phase 1 (gate: LED-5 merged)", out)
        self.assertNotIn("Phase 3 (gate", out)
        self.assertIn("The next open phase without a gate is Phase 2.", out)

    def test_start_runs_an_ungated_phase_that_comes_before_a_gated_one(self):
        self.gate_phases(2)
        out = self.step("start", self.plan)
        self.assertIn("AGENT: coder", out)
        self.assertEqual("1", self.state()["phase"])

    def test_a_moved_phase_ahead_of_an_ungated_one_is_not_an_open_gate(self):
        self.move_phases(1)
        self.gate_phases(3)
        out = self.step("start", self.plan)
        self.assertIn("AGENT: coder", out)
        self.assertEqual("2", self.state()["phase"])

    def test_start_stops_and_opens_no_dispatch_when_every_open_phase_is_gated(self):
        self.start_phase_one()
        self.gate_phases(1, 2, 3, 4, condition="the data team signs off")
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT:", out)
        for number in (1, 2, 3, 4):
            self.assertIn(f"Phase {number} (gate: the data team signs off)", out)
        state = self.state()
        self.assertNotIn("dispatchAt", state)
        self.assertEqual("stopped", state["stage"])

    def test_a_gated_phase_that_is_done_is_not_named_when_start_stops_at_an_open_one(self):
        self.mark_phases_done(1)
        self.gate_phases(2)
        out = self.step("start", self.plan)
        self.assertNotIn("Phase 1 (gate", out)
        self.assertIn("Phase 2 (gate: LED-5 merged)", out)
        self.assertIn("The next open phase without a gate is Phase 3.", out)
        self.assertNotIn("AGENT:", out)

    # ---------- the phase a run advances to is never past a gated one ----------

    def test_the_boundary_does_not_auto_advance_past_a_gated_phase_and_names_it_and_the_next_ungated_one(self):
        self.finish_phase_one()
        self.gate_phases(3)
        self.step("start", self.plan)
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertNotIn("ACTION: auto-advance", out)
        self.assertFalse(self.state()["autoAdvance"])
        said = self.said()
        self.assertNotIn("Auto-advancing", said)
        self.assertNotIn("(last phase)", said)
        self.assertIn("Phase 3 (gate: LED-5 merged)", said)
        self.assertIn("The next open phase without a gate is Phase 4.", said)
        self.assertIn("The plan is not complete.", said)

    def test_the_boundary_does_not_auto_advance_when_every_open_phase_is_gated(self):
        self.finish_phase_one()
        self.gate_phases(3, 4, condition="the data team signs off")
        self.step("start", self.plan)
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertNotIn("ACTION: auto-advance", out)
        self.assertFalse(self.state()["autoAdvance"])
        said = self.said()
        self.assertNotIn("Auto-advancing", said)
        self.assertNotIn("All phases complete", said)
        self.assertIn("Phase 3 (gate: the data team signs off)", said)
        self.assertIn("Phase 4 (gate: the data team signs off)", said)

    # ---------- a phase marked [-] is moved to another ticket: never started, never done ----------

    def move_phases(self, *numbers, withDeviation=True):
        text = self.plan_text()
        for number in numbers:
            line = next(line for line in text.splitlines() if line.startswith(f"- [ ] Phase {number}:"))
            movedLine = line.replace("- [ ]", "- [-]", 1) + " — moved to LED-16, per the user 2026-10-20"
            text = text.replace(line, movedLine)
        if withDeviation:
            entries = "".join(f"- 2026-10-20: Phase {number} moves to LED-16. User, 2026-10-20: \"defer it\".\n"
                              for number in numbers)
            text = text.replace("## References", f"## Plan Deviations\n\n{entries}\n## References")
        (self.repo / self.plan).write_text(text)

    def test_start_never_picks_a_moved_phase_as_the_next_phase(self):
        self.move_phases(1)
        out = self.step("start", self.plan)
        self.assertIn("AGENT: coder", out)
        self.assertEqual("2", self.state()["phase"])

    def test_a_plan_whose_only_open_phases_are_moved_is_complete(self):
        self.mark_phases_done(1, 4)
        self.move_phases(2, 3)
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT:", out)
        self.assertIn("plan is complete", out)
        self.assertIn("Phase 2 to LED-16", out)
        self.assertIn("Phase 3 to LED-16", out)

    def test_start_with_the_id_of_a_moved_phase_refuses_and_names_the_ticket(self):
        self.move_phases(2)
        out = self.step("start", self.plan, "--phase", "2")
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT:", out)
        self.assertIn("Phase 2 is moved to LED-16", out)
        self.assertIn("No coder was dispatched", out)
        self.assertNotIn("The coder ran", out)

    def test_tick_refuses_a_moved_phase_and_leaves_its_line_alone(self):
        self.move_phases(2)
        self.step("start", self.plan)
        before = self.plan_text()
        out = self.step("tick", "2")
        self.assertIn("Phase 2 is moved to LED-16", out)
        self.assertEqual(before, self.plan_text())

    def test_finishing_the_last_open_phase_ends_the_plan_when_the_rest_are_moved(self):
        self.move_phases(2, 3, 4)
        out = self.finish_phase_one()
        said = self.said()
        self.assertIn("ACTION: stop-block-C", out)
        self.assertIn("complete or moved to another ticket (Phase 2 to LED-16, Phase 3 to LED-16, Phase 4 to LED-16)",
                      said)
        self.assertNotIn("All phases complete", said)
        self.assertNotIn("Auto-advancing", said)

    def test_a_phase_moved_while_it_runs_stops_the_finish_without_marking_or_committing(self):
        self.coder_round()
        before = self.plan_text()
        self.move_phases(1)
        movedPlan = self.plan_text()
        self.assertNotEqual(before, movedPlan)
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("Phase 1 is moved to LED-16", out)
        self.assertIn("The coder ran, and its work is not marked done or committed.", out)
        self.assertNotIn("No coder was dispatched", out)
        self.assertEqual("stopped", self.state()["stage"])
        self.assertEqual(movedPlan, self.plan_text())
        self.assertNotIn("Phase 1 marked done", out + self.said())
        self.assertNotIn("Commit command", self.said())

    def test_a_moved_line_with_no_plan_deviations_entry_stops_start_with_the_fix(self):
        self.move_phases(2, withDeviation=False)
        out = self.step("start", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT:", out)
        self.assertIn("moved-without-deviation", out)
        self.assertIn("(who and when), and name Phase 2 and LED-16 in the same line.", out)

    # ---------- the phase-done line and the last-phase wording ----------

    def finish_phase_two(self):
        self.step("start", self.plan)
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")

    def test_a_phase_that_lists_no_verification_commands_says_so_instead_of_zero_green(self):
        self.finish_phase_one()
        self.finish_phase_two()
        done = next(line for line in self.said().splitlines() if line.startswith("Phase 2 marked done"))
        self.assertIn("lists no verification commands", done)
        self.assertNotIn("0 command(s) green", done)

    def test_a_phase_that_lists_commands_keeps_the_green_count_in_the_done_line(self):
        self.finish_phase_one()
        done = next(line for line in self.said().splitlines() if line.startswith("Phase 1 marked done"))
        self.assertIn("Verification run: 1 command(s) green (git grep -n --untracked console.log", done)
        self.assertIn("skipped as covered by the review loop: 1.", done)
        self.assertNotIn("lists no verification commands", done)

    def test_the_last_open_phase_is_called_the_last_phase_when_no_gated_phase_remains(self):
        self.mark_phases_done(1, 3)
        statusLine = "- [ ] Phase 4: Refactor pass - /refactor cleanup sweep (risk: low)\n"
        closingSection = "## Phase 4: Refactor pass\n\nSweep.\n\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(statusLine, "").replace(closingSection, ""))
        self.finish_phase_two()
        self.assertIn("Phase 2 complete (last phase).", self.said())

    def test_a_phase_is_not_called_the_last_when_only_gated_phases_remain(self):
        self.finish_phase_one()
        self.gate_phases(3, 4, condition="the data team signs off")
        self.finish_phase_two()
        said = self.said()
        self.assertIn("Phase 2 complete.", said)
        self.assertNotIn("(last phase)", said)
        self.assertIn("The plan is not complete.", said)

    def test_a_sign_off_block_does_not_start_a_phase_past_a_gated_one_and_names_both(self):
        self.gate_phases(2)
        out = self.finish_phase_one()
        said = self.said()
        self.assertIn("ACTION: stop-block-C", out)
        self.assertNotIn("fresh", said)
        self.assertIn("Phase 2 (gate: LED-5 merged)", said)
        self.assertIn("The next open phase without a gate is Phase 3.", said)

    def test_a_sign_off_block_starts_the_next_phase_when_a_gated_phase_comes_after_it(self):
        self.gate_phases(3)
        self.finish_phase_one()
        said = self.said()
        self.assertIn("start Phase 2 fresh", said)
        self.assertNotIn("gate clause", said)

    # ---------- a spent wait cap does not make the next wait stop at once ----------

    def test_the_wait_after_a_cap_stop_on_a_resumed_coder_waits_again(self):
        self.stop_the_coder_on_a_blocked_report()
        self.wait_env(1, "0.2")
        self.step("after-coder")
        self.set_state(resumeWaitAt=time.time() - 100)
        self.assertIn("has not handed back in", self.step("after-coder"))
        self.assertNotIn("resumeWaitAt", self.state())
        out = self.step("after-coder")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("has not handed back in", out)

    def test_the_wait_after_a_cap_stop_on_a_resumed_review_loop_waits_again(self):
        self.stop_the_review_at_the_wait_cap()
        self.step("after-review")
        self.set_state(resumeWaitAt=time.time() - 100)
        self.assertIn("has not handed back in", self.step("after-review"))
        self.assertNotIn("resumeWaitAt", self.state())
        out = self.step("after-review")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("has not handed back in", out)

    # ---------- a stale save that undid the hook's flip does not lose the resumed coder's report ----------

    def test_after_coder_goes_to_review_when_a_stale_save_overwrote_the_hook_flip(self):
        self.stop_the_coder_on_a_blocked_report()
        stateFile = self.repo / ".git/code-step/state.json"
        staleState = stateFile.read_text()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", self.CODER_REPORT)
        self.assertEqual("coder", self.state()["stage"])
        stateFile.write_text(staleState)
        self.assertEqual("stopped", self.state()["stage"])
        self.wait_env(1, "0.2")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual("review", self.state()["stage"])
        self.assertNotIn("resumableCoderAt", self.state())

    def test_after_coder_still_waits_when_the_resumed_coder_has_saved_no_row(self):
        self.stop_the_coder_on_a_blocked_report()
        self.wait_env(1, "0.2")
        out = self.step("after-coder")
        self.assertIn("ACTION: wait", out)
        self.assertEqual("stopped", self.state()["stage"])
        self.assertIn("resumableCoderAt", self.state())

    # ---------- a second no-reviewable-change stop keeps the first one's PLAN-IMPACT ----------

    def test_a_second_stop_on_no_reviewable_change_keeps_the_plan_impact_of_the_first(self):
        self.start_phase_one()
        self.hook("coder", "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes")
        self.assertIn("ACTION: stop", self.step("after-coder"))
        self.hook("coder", "BEHAVIOR: none\nstill blocked")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("PLAN-IMPACT:", self.state()["stoppedCoderReport"])
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        out = self.step("after-coder")
        self.assertIn("ACTION: ask-user", out)
        self.assertNotIn("stoppedCoderReport", self.state())

    # ---------- the event log: dispatch events, prompt files, the log hook and the dispatch hook ----------

    HOOK_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

    def run_events(self):
        eventsFile = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        return [json.loads(line) for line in eventsFile.read_text().splitlines()] if eventsFile.exists() else []

    def events_named(self, eventName):
        return [event for event in self.run_events() if event["event"] == eventName]

    def printed_prompt(self, out):
        return out.split("-----BEGIN PROMPT-----\n", 1)[1].split("\n-----END PROMPT-----", 1)[0]

    def hook_fixture(self, name):
        # One event of its kind as the tool call and its result were recorded in a transcript: the tool_name, the
        # tool_input and the tool_response, with the prompt and message text cut to a placeholder.
        fixtureFile = self.HOOK_FIXTURES / f"hook_event_{name}.json"
        return json.loads(fixtureFile.read_text())

    def log_hook(self, toolName, toolInput, toolResponse=None, **extra):
        event = {"tool_name": toolName, "tool_input": toolInput, "cwd": str(self.repo), "session_id": self.SESSION,
                 **extra}
        if toolResponse is not None:
            event["tool_response"] = toolResponse
        return run(self.repo, self.env, "log-hook", stdin=json.dumps(event))

    def log_fixture(self, name, toolInput=None, toolResponse=None, **extra):
        # Feeds the log hook the recorded event of this kind, with the given fields laid over the recorded ones.
        fixture = self.hook_fixture(name)
        fixture["tool_input"].update(toolInput or {})
        fixture["tool_response"].update(toolResponse or {})
        return self.log_hook(fixture["tool_name"], fixture["tool_input"], fixture["tool_response"], **extra)

    def launch_agent(self, prompt, agentId="a1", subagentType="coder"):
        return self.log_fixture("agent_launch", {"subagent_type": subagentType, "prompt": prompt},
                                {"agentId": agentId})

    def send_message(self, to, **extra):
        return self.log_fixture("send_message", {"to": to, "recipient": to}, **extra)

    def hand_back(self, message, agentType, agentId):
        return self.log_fixture("subagent_handback", {"message": message}, agent_type=agentType, agent_id=agentId)

    def dispatch_hook(self, prompt, subagentType="coder", session=SESSION):
        event = {"tool_name": "Agent", "tool_input": {"subagent_type": subagentType, "prompt": prompt},
                 "cwd": str(self.repo)}
        if session:
            event["session_id"] = session
        return run(self.repo, self.env, "dispatch-hook", stdin=json.dumps(event)).stdout

    def denial_reason(self, hookOutput):
        return json.loads(hookOutput)["hookSpecificOutput"]["permissionDecisionReason"]

    def assert_dispatch_logged(self, out, dispatchId, agentType, stage, verb):
        # The printed dispatch is the logged one: same agent, stage and verb, the saved prompt file named, and the
        # prompt ending with the marker line of its id.
        dispatch = next((event for event in self.events_named("dispatch") if event["id"] == dispatchId), None)
        self.assertIsNotNone(dispatch, f"no dispatch event {dispatchId}")
        self.assertEqual((agentType, stage, verb), (dispatch["agent_type"], dispatch["stage"], dispatch["verb"]))
        self.assertIn(f"PROMPT FILE: {dispatch['prompt_file']}\n", out)
        printedLines = self.printed_prompt(out).splitlines()
        self.assertEqual(f"code-step-dispatch: {self.state()['runId']}/{dispatchId}", printedLines[-1])

    def test_dispatch_event_writes_prompt_file(self):
        out = self.start_phase_one()

        runId = self.state()["runId"]
        dispatches = self.events_named("dispatch")
        self.assertEqual(1, len(dispatches))
        dispatch = dispatches[0]
        dispatchKeys = {"v", "ts", "event", "session_id", "id", "agent_type", "stage", "verb", "model", "prompt_file"}
        self.assertEqual(dispatchKeys, set(dispatch))
        self.assertEqual((1, "d1", self.SESSION), (dispatch["v"], dispatch["id"], dispatch["session_id"]))
        self.assertEqual(("coder", "coder", "after-coder", None),
                         (dispatch["agent_type"], dispatch["stage"], dispatch["verb"], dispatch["model"]))
        promptFile = self.repo / ".git/code-step/runs" / runId / "prompt-d1.txt"
        self.assertEqual(str(promptFile), dispatch["prompt_file"])
        self.assertIn(f"PROMPT FILE: {promptFile}\n", out)
        savedPrompt = promptFile.read_text()
        self.assertIn("Implement Phase 1 of `docs/plans/orders/spec.md`", savedPrompt)
        self.assertIn("Packet for Phase 1", savedPrompt)
        self.assertEqual(f"code-step-dispatch: {runId}/d1", savedPrompt.rstrip().splitlines()[-1])
        self.assertEqual(savedPrompt.rstrip(), self.printed_prompt(out))

    def test_every_dispatch_kind_logs_an_event_with_its_agent_verb_and_model(self):
        self.coder_round()

        reviewDispatch = self.events_named("dispatch")[-1]
        self.assertEqual(("d2", "review-loop", "review", "after-review", "sonnet"),
                         (reviewDispatch["id"], reviewDispatch["agent_type"], reviewDispatch["stage"],
                          reviewDispatch["verb"], reviewDispatch["model"]))
        reviewPrompt = pathlib.Path(reviewDispatch["prompt_file"]).read_text()
        self.assertIn("mode: review-first", reviewPrompt)
        self.assertEqual(f"code-step-dispatch: {self.state()['runId']}/d2", reviewPrompt.rstrip().splitlines()[-1])

    def test_planless_start_logs_its_dispatch_and_saves_its_prompt(self):
        out = self.step("start", "+fast", "--task", "fix the typo")

        dispatch = self.events_named("dispatch")[0]
        self.assertEqual(("d1", "coder", "haiku"), (dispatch["id"], dispatch["agent_type"], dispatch["model"]))
        self.assertIn(f"PROMPT FILE: {dispatch['prompt_file']}", out)
        self.assertIn("Implement: fix the typo", pathlib.Path(dispatch["prompt_file"]).read_text())

    def test_a_new_start_deletes_the_older_run_folders(self):
        self.start_phase_one()
        firstRun = self.state()["runId"]

        self.start_phase_one()

        runFolders = [folder.name for folder in (self.repo / ".git/code-step/runs").iterdir()]
        self.assertNotEqual(firstRun, self.state()["runId"])
        self.assertEqual([self.state()["runId"]], runFolders)

    def test_launch_binds_marker(self):
        out = self.start_phase_one()
        runId = self.state()["runId"]

        self.launch_agent(self.printed_prompt(out), agentId="agent-7")

        launches = self.events_named("launch")
        self.assertEqual(1, len(launches))
        self.assertEqual((1, "launch", self.SESSION, "agent-7", "d1"),
                         (launches[0]["v"], launches[0]["event"], launches[0]["session_id"], launches[0]["agent_id"],
                          launches[0]["dispatch"]))
        self.launch_agent("An Agent call with no marker line", agentId="agent-8")
        self.launch_agent(f"text\ncode-step-dispatch: {runId}-old/d1", agentId="agent-9")
        launches = self.events_named("launch")
        self.assertEqual(["agent-7"], [launch["agent_id"] for launch in launches])

    def test_launch_binds_a_marker_that_is_folded_into_one_line_or_followed_by_text(self):
        out = self.start_phase_one()
        wholePrompt = self.printed_prompt(out)
        oneLinePrompt = " ".join(wholePrompt.split())
        promptWithTrailingText = wholePrompt + " Thank you."

        self.assertEqual("", self.dispatch_hook(oneLinePrompt))
        self.assertEqual("", self.dispatch_hook(promptWithTrailingText))
        self.launch_agent(oneLinePrompt, agentId="agent-1")
        self.launch_agent(promptWithTrailingText, agentId="agent-2")

        launches = self.events_named("launch")
        self.assertEqual([("agent-1", "d1"), ("agent-2", "d1")],
                         [(launch["agent_id"], launch["dispatch"]) for launch in launches])

    def test_launch_without_an_agent_id_in_the_tool_response_logs_nothing_and_names_the_field(self):
        out = self.start_phase_one()
        launch = self.hook_fixture("agent_launch")
        launch["tool_input"]["prompt"] = self.printed_prompt(out)
        del launch["tool_response"]["agentId"]

        result = self.log_hook("Agent", launch["tool_input"], launch["tool_response"])

        self.assertEqual([], self.events_named("launch"))
        self.assertEqual("", result.stdout)
        stderrLines = result.stderr.splitlines()
        self.assertEqual(1, len(stderrLines))
        self.assertIn("agentId", result.stderr)

    def test_sendmessage_writes_resume(self):
        self.start_phase_one()

        self.send_message("agent-7")

        resumes = self.events_named("resume")
        self.assertEqual([("agent-7", self.SESSION)],
                         [(resume["agent_id"], resume["session_id"]) for resume in resumes])

    def test_denied_handback_not_logged(self):
        self.start_phase_one()
        message = "BEHAVIOR: orders exist\nREVIEW: recommended"

        # The PreToolUse hook sees every hand-back call, also one that the hand-back gate denies. Only a call that went
        # through reaches PostToolUse.
        self.hook("coder", message, agentId="a7")
        self.assertEqual([], self.events_named("handback"))
        self.hand_back(message, "coder", "a7")

        handbacks = self.events_named("handback")
        self.assertEqual([("a7", "coder", message)],
                         [(handback["agent_id"], handback["agent_type"], handback["message"])
                          for handback in handbacks])

    def test_a_state_without_a_run_id_gets_one_at_its_next_dispatch_and_the_hooks_leave_it_alone(self):
        self.start_phase_one()
        oldRunId = self.state()["runId"]
        oldEvents = self.run_events()
        statePath = self.repo / ".git/code-step/state.json"
        legacyState = json.loads(statePath.read_text())
        legacyState["runId"] = None
        statePath.write_text(json.dumps(legacyState))
        agentCall = {"tool_name": "Agent", "cwd": str(self.repo), "session_id": self.SESSION,
                     "tool_input": {"subagent_type": "coder", "prompt": "thin"}}

        launchResult = self.launch_agent(f"code-step-dispatch: {oldRunId}/d1", agentId="agent-7")
        resumeResult = self.send_message("agent-7")
        denyResult = run(self.repo, self.env, "dispatch-hook", stdin=json.dumps(agentCall))

        for result in (launchResult, resumeResult, denyResult):
            self.assertEqual(("", ""), (result.stdout, result.stderr))
        eventsFile = self.repo / ".git/code-step/runs" / oldRunId / "events.jsonl"
        self.assertEqual(oldEvents, [json.loads(line) for line in eventsFile.read_text().splitlines()])

        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        out = self.step("after-coder")

        self.assertIn("AGENT: review-loop", out)
        newRunId = self.state()["runId"]
        self.assertTrue(newRunId)
        self.assertNotEqual(oldRunId, newRunId)
        dispatches = self.events_named("dispatch")
        self.assertEqual(["d1"], [dispatch["id"] for dispatch in dispatches])
        self.assert_dispatch_logged(out, "d1", "review-loop", "review", "after-review")

    def test_log_hook_writes_nothing_for_another_session_or_a_finished_run(self):
        out = self.start_phase_one()
        wholePrompt = self.printed_prompt(out)

        self.send_message("agent-7", session_id="sess-other")
        self.assertEqual([], self.events_named("resume"))
        self.send_message("agent-7")
        resumes = self.events_named("resume")
        self.assertEqual(1, len(resumes))

        self.finish_phase_one()
        eventCount = len(self.run_events())
        self.assertEqual("done", self.state()["stage"])
        self.send_message("agent-7")
        self.launch_agent(wholePrompt, agentId="agent-8")

        eventsAfterDone = self.run_events()
        self.assertEqual(eventCount, len(eventsAfterDone))

    def test_dispatch_hook_denies_missing_packet(self):
        out = self.start_phase_one()
        wholePrompt = self.printed_prompt(out)
        promptFile = self.events_named("dispatch")[0]["prompt_file"]
        thinPrompt = "Implement Phase 1 of `docs/plans/orders/spec.md`. Read the plan phase-scoped."

        reason = self.denial_reason(self.dispatch_hook(thinPrompt))

        forkBlocks = self.events_named("fork-block")
        self.assertIn(f"Read {promptFile} and pass its whole text.", reason)
        self.assertEqual([("d1", "prompt-deny")], [(block["dispatch"], block["kind"]) for block in forkBlocks])
        self.assertEqual("", self.dispatch_hook(wholePrompt))

    def test_dispatch_hook_accepts_the_whole_prompt_with_changed_whitespace(self):
        out = self.start_phase_one()
        reflowed = "Task for you:\n\n   " + self.printed_prompt(out).replace("\n", "\n\n  ").replace(" ", "  ")

        self.assertEqual("", self.dispatch_hook(reflowed))
        self.assertEqual([], self.events_named("fork-block"))

    def test_dispatch_hook_stops_the_fork_after_three_denials(self):
        self.start_phase_one()
        promptFile = self.events_named("dispatch")[0]["prompt_file"]

        reasons = [self.denial_reason(self.dispatch_hook("thin")) for _ in range(4)]

        for reason in reasons[:3]:
            self.assertIn("pass its whole text", reason)
        self.assertNotIn("pass its whole text", reasons[3])
        self.assertIn("Stop.", reasons[3])
        self.assertIn(promptFile, reasons[3])

    def test_dispatch_hook_denies_a_second_launch_of_the_same_dispatch(self):
        out = self.start_phase_one()
        wholePrompt = self.printed_prompt(out)
        self.assertEqual("", self.dispatch_hook(wholePrompt))
        self.launch_agent(wholePrompt, agentId="agent-7")

        reason = self.denial_reason(self.dispatch_hook(wholePrompt))

        self.assertIn("already launched", reason)
        self.assertIn("agent-7", reason)
        self.assertIn(f"`{code_step.SELF_COMMAND} after-coder` as a Bash call with timeout", reason)
        forkBlocks = self.events_named("fork-block")
        self.assertEqual([("d1", "relaunch")], [(block["dispatch"], block["kind"]) for block in forkBlocks])

    def test_dispatch_hook_denies_a_one_line_copy_of_a_launched_prompt(self):
        out = self.start_phase_one()
        wholePrompt = self.printed_prompt(out)
        oneLinePrompt = " ".join(wholePrompt.split())
        self.launch_agent(wholePrompt, agentId="agent-7")

        reason = self.denial_reason(self.dispatch_hook(oneLinePrompt))

        forkBlocks = self.events_named("fork-block")
        self.assertIn("already launched", reason)
        self.assertEqual([("d1", "relaunch")], [(block["dispatch"], block["kind"]) for block in forkBlocks])

    def test_dispatch_hook_relaunch_denials_never_reach_the_prompt_denial_cap(self):
        out = self.start_phase_one()
        wholePrompt = self.printed_prompt(out)
        self.launch_agent(wholePrompt, agentId="agent-7")

        reasons = [self.denial_reason(self.dispatch_hook(wholePrompt)) for _ in range(4)]

        for reason in reasons:
            self.assertIn("already launched", reason)
            self.assertIn("after-coder", reason)
            self.assertNotIn("Stop.", reason)
        forkBlocks = self.events_named("fork-block")
        self.assertEqual(["relaunch"] * 4, [block["kind"] for block in forkBlocks])

    def test_dispatch_hook_lets_a_coder_call_without_the_marker_pass_after_the_coder_launch(self):
        out = self.start_phase_one()
        self.launch_agent(self.printed_prompt(out), agentId="agent-7")

        result = self.dispatch_hook("Explore the orders module.")

        self.assertEqual("", result)
        self.assertEqual([], self.events_named("fork-block"))

    def test_dispatch_hook_lets_a_call_without_the_marker_pass_while_a_launched_dispatch_is_open(self):
        self.start_phase_one()
        self.launch_agent("code-step-dispatch: " + self.state()["runId"] + "/d1")
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        reviewOut = self.step("after-coder")
        self.launch_agent(self.printed_prompt(reviewOut), agentId="agent-9", subagentType="review-loop")

        self.assertEqual("", self.dispatch_hook("Review this branch for the user.", subagentType="review-loop"))
        self.assertEqual([], self.events_named("fork-block"))

    def test_dispatch_hook_lets_a_review_loop_relaunch_with_its_marker_pass(self):
        self.start_phase_one()
        self.launch_agent("code-step-dispatch: " + self.state()["runId"] + "/d1")
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        reviewOut = self.step("after-coder")
        reviewPrompt = self.printed_prompt(reviewOut)
        self.launch_agent(reviewPrompt, agentId="agent-9", subagentType="review-loop")

        self.assertEqual("", self.dispatch_hook(reviewPrompt, subagentType="review-loop"))
        self.assertEqual([], self.events_named("fork-block"))

    def test_dispatch_hook_denies_a_thin_review_loop_prompt_while_the_review_dispatch_is_pending(self):
        self.start_phase_one()
        self.launch_agent("code-step-dispatch: " + self.state()["runId"] + "/d1")
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        reviewOut = self.step("after-coder")
        reviewPrompt = self.printed_prompt(reviewOut)
        reviewPromptFile = self.events_named("dispatch")[-1]["prompt_file"]

        reason = self.denial_reason(self.dispatch_hook("Review the branch.", subagentType="review-loop"))

        forkBlocks = self.events_named("fork-block")
        self.assertIn(f"Read {reviewPromptFile} and pass its whole text.", reason)
        self.assertEqual([("d2", "prompt-deny")], [(block["dispatch"], block["kind"]) for block in forkBlocks])
        self.assertEqual("", self.dispatch_hook(reviewPrompt, subagentType="review-loop"))

    def test_dispatch_hook_denies_the_whole_prompt_with_its_marker_line_removed(self):
        out = self.start_phase_one()
        markerLine = f"code-step-dispatch: {self.state()['runId']}/d1"
        promptWithoutMarker = self.printed_prompt(out).replace(markerLine, "").rstrip()
        self.assertNotIn("code-step-dispatch", promptWithoutMarker)

        reason = self.denial_reason(self.dispatch_hook(promptWithoutMarker))

        forkBlocks = self.events_named("fork-block")
        self.assertIn("pass its whole text", reason)
        self.assertEqual([("d1", "prompt-deny")], [(block["dispatch"], block["kind"]) for block in forkBlocks])

    def test_dispatch_hook_leaves_other_agents_other_sessions_and_finished_runs_alone(self):
        self.assertEqual("", self.dispatch_hook("thin"))
        self.start_phase_one()
        self.assertEqual("", self.dispatch_hook("thin", subagentType="Explore"))
        self.assertEqual("", self.dispatch_hook("thin", subagentType="review-loop"))
        self.assertEqual("", self.dispatch_hook("thin", session="sess-other"))
        self.assertEqual([], self.events_named("fork-block"))

        self.finish_phase_one()

        self.assertEqual("done", self.state()["stage"])
        self.assertEqual("", self.dispatch_hook("thin"))

    def test_a_start_run_again_opens_a_new_run_and_after_coder_without_a_report_stops_as_before(self):
        firstOut = self.start_phase_one()
        firstRun = self.state()["runId"]

        rerunOut = self.start_phase_one()

        self.assertNotEqual(firstRun, self.state()["runId"])
        dispatchIds = [dispatch["id"] for dispatch in self.events_named("dispatch")]
        self.assertEqual(["d1"], dispatchIds)
        self.assertIn("ACTION: dispatch", rerunOut)
        firstBody = self.printed_prompt(firstOut).rsplit("\n", 1)[0]
        rerunBody = self.printed_prompt(rerunOut).rsplit("\n", 1)[0]
        self.assertEqual(firstBody, rerunBody)

        afterOut = self.step("after-coder")

        self.assertIn("No coder report was saved", afterOut)
        self.assertNotIn("ACTION: dispatch", afterOut)

    def test_a_start_from_another_session_opens_a_new_run(self):
        self.start_phase_one()
        firstRun = self.state()["runId"]
        statePath = self.repo / ".git/code-step/state.json"
        oldState = json.loads(statePath.read_text())
        oldState["dispatchAt"] = time.time() - 3 * 60 * 60
        statePath.write_text(json.dumps(oldState))
        self.env["CLAUDE_CODE_SESSION_ID"] = "sess-2"

        self.start_phase_one()

        dispatches = self.events_named("dispatch")
        self.assertNotEqual(firstRun, self.state()["runId"])
        self.assertEqual([("d1", "sess-2")], [(dispatch["id"], dispatch["session_id"]) for dispatch in dispatches])

    # ---------- the ask-user action names the real say file ----------

    def real_say_file(self):
        return (self.repo / ".git/code-step/say.md").resolve()

    def test_the_ask_user_action_for_a_plan_impact_names_the_real_say_file(self):
        report = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes"

        out = self.coder_round(report)

        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"The question for the user is in {self.real_say_file()}. Hand back.", out)
        self.assertIn("## Question for the user", self.real_say_file().read_text())

    def test_the_ask_user_action_for_review_asks_names_the_real_say_file(self):
        self.coder_round()
        asks = '  - {question: "q1", file_line: "backend/src/orders.ts:1", gate: code-reviewer}'
        self.hook("review-loop", f"status: converged\niter: 1\nfixed: []\nask (for the user):\n{asks}")

        out = self.step("after-review")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"The question for the user is in {self.real_say_file()}. Hand back.", out)

    # ---------- a dispatch whose Agent call never left ----------

    def age_dispatches(self, seconds):
        eventsFile = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        rows = [json.loads(line) for line in eventsFile.read_text().splitlines()]
        for row in rows:
            row["ts"] -= seconds
        eventsFile.write_text("".join(json.dumps(row) + "\n" for row in rows))

    def test_a_wait_on_a_dispatch_with_no_launch_prints_the_dispatch_again(self):
        self.begin_coder()
        self.age_dispatches(120)
        self.wait_env(5, "0.2")
        started = time.monotonic()

        out = self.step("after-coder")

        self.assertLess(time.monotonic() - started, 3)
        self.assertIn("ACTION: dispatch", out)
        self.assertIn("AGENT: coder", out)
        self.assertIn("Dispatch d1 was logged", out)
        self.assertIn("no Agent call for it was launched", out)
        self.assertEqual(1, len(self.events_named("dispatch")))
        self.assertEqual(self.printed_prompt(out).rstrip(), pathlib.Path(
            self.events_named("dispatch")[0]["prompt_file"]).read_text().rstrip())

    def test_a_wait_on_a_review_dispatch_with_no_launch_prints_the_review_dispatch_again(self):
        self.coder_round()
        self.age_dispatches(120)
        self.wait_env(5, "0.2")

        out = self.step("after-review")

        self.assertIn("ACTION: dispatch", out)
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual(2, len(self.events_named("dispatch")))

    def test_a_wait_on_a_launched_dispatch_keeps_waiting(self):
        out = self.start_phase_one()
        self.pass_coder_gate()
        self.launch_agent(self.printed_prompt(out))
        self.age_dispatches(120)
        self.wait_env(1, "0.2")

        waited = self.step("after-coder")

        self.assertIn("ACTION: wait", waited)

    def test_a_wait_on_a_fresh_dispatch_with_no_launch_keeps_waiting(self):
        self.begin_coder()
        self.wait_env(1, "0.2")

        out = self.step("after-coder")

        self.assertIn("ACTION: wait", out)

    def test_a_wait_past_the_cap_on_a_dispatch_with_no_launch_stops_and_does_not_print_it_again(self):
        self.begin_coder()
        self.age_dispatches(5000)
        self.set_state(dispatchAt=time.time() - 5000)
        self.wait_env(1, "0.2")

        out = self.step("after-coder")

        self.assertIn("ACTION: stop", out)

    def test_a_wait_does_not_print_again_a_dispatch_made_for_another_agent(self):
        self.begin_coder()
        eventsFile = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        rows = [json.loads(line) for line in eventsFile.read_text().splitlines()]
        for row in rows:
            if row["event"] == "dispatch":
                row["agent_type"] = "review-loop"
        eventsFile.write_text("".join(json.dumps(row) + "\n" for row in rows))
        self.age_dispatches(120)
        self.wait_env(1, "0.2")

        out = self.step("after-coder")

        self.assertIn("ACTION: wait", out)

    def test_a_dispatch_output_repeats_the_action_and_the_agent_after_the_prompt(self):
        out = self.start_phase_one()

        tail = out.split("-----END PROMPT-----", 1)[1]

        self.assertIn("ACTION: dispatch", tail)
        self.assertIn("AGENT: coder", tail)
        self.assertIn("MODEL:", tail)
        self.assertIn("NEXT: right after the Agent call", tail)

    def test_the_wait_ends_at_the_cap_and_not_at_the_end_of_the_wait_that_passes_it(self):
        self.begin_coder()
        self.set_state(dispatchAt=time.time() - 28)
        self.wait_env(10, "0.2")
        started = time.monotonic()

        out = self.step("after-coder")

        self.assertLess(time.monotonic() - started, 6)
        self.assertIn("ACTION: stop", out)
        self.assertEqual("stopped", self.state()["stage"])

    # ---------- an Automated Verification item that cannot run ----------

    def bad_item_plan(self, item):
        old = "- [ ] **Prohibition**: no console.log - `git grep -n --untracked console.log -- backend/src/orders.ts`"
        return self.plan_text().replace(old, item)

    def test_plan_check_fails_an_item_that_starts_with_a_word_that_is_no_program(self):
        text = self.bad_item_plan("- [ ] **Check**: the orders pass - `RUN npx vitest run`")
        badLine = text.splitlines().index("- [ ] **Check**: the orders pass - `RUN npx vitest run`") + 1

        result = self.plan_check(text)

        self.assertEqual(1, result.returncode)
        self.assertIn(f":{badLine}:", result.stdout)
        self.assertIn("it starts with `RUN`", result.stdout)
        self.assertIn("one of three shapes", result.stdout)

    def test_plan_check_fails_an_item_with_no_backticked_command(self):
        text = self.bad_item_plan("- [ ] **Check**: the orders pass, see the log")

        result = self.plan_check(text)

        self.assertEqual(1, result.returncode)
        self.assertIn("it has no backticked command and is not marked N/A", result.stdout)

    def test_plan_check_passes_items_marked_n_a_and_commands_on_the_path_or_in_the_repo(self):
        for item in ("- [ ] N/A - docs only", "- [ ] **Test-verified**: N/A on the machines; the suites stand.",
                     "- [ ] **Check**: passes - `test -d backend`", "- [ ] **Check**: passes - `bash backend/package.json`"):
            with self.subTest(item=item):
                self.assertEqual(0, self.plan_check(self.bad_item_plan(item)).returncode)

    def make_repo_script(self, relativePath, mode=0o755):
        scriptFile = self.repo / relativePath
        scriptFile.parent.mkdir(parents=True, exist_ok=True)
        scriptFile.write_text("#!/bin/sh\n")
        scriptFile.chmod(mode)
        return scriptFile

    def test_plan_check_passes_an_item_that_starts_with_an_executable_file_of_the_repo(self):
        self.make_repo_script("check-orders")
        self.make_repo_script("scripts/check-orders")

        for span in ("./check-orders --all", "scripts/check-orders --all"):
            with self.subTest(span=span):
                text = self.bad_item_plan(f"- [ ] **Check**: the orders pass - `{span}`")

                self.assertEqual(0, self.plan_check(text).returncode)

    def test_plan_check_fails_an_item_that_starts_with_a_file_of_the_repo_that_is_not_executable(self):
        self.make_repo_script("scripts/check-orders", 0o644)
        text = self.bad_item_plan("- [ ] **Check**: the orders pass - `scripts/check-orders --all`")

        self.assertEqual(1, self.plan_check(text).returncode)

    def test_a_bare_word_is_never_a_file_of_the_repo(self):
        self.make_repo_script("check-orders")
        text = self.bad_item_plan("- [ ] **Check**: the orders pass - `check-orders --all`")

        self.assertFalse(code_step.starts_like_a_program_here("check-orders --all", self.repo))
        self.assertEqual(1, self.plan_check(text).returncode)

    def test_a_line_that_names_a_path_program_and_then_holds_the_real_command_gives_the_real_command(self):
        item = "- [ ] **Check**: with `ls -la` listing the files, `npm run build` exits 0."

        self.assertEqual("npm run build", code_step.verification_command(item))

    def test_a_program_of_the_path_needs_an_argument_to_be_a_fallback_command(self):
        self.assertIsNone(code_step.verification_command("- [ ] **Check**: the `ls` program lists them"))
        self.assertEqual("ls -la", code_step.verification_command("- [ ] **Check**: lists them - `ls -la`"))

    def test_claude_and_yes_are_never_a_fallback_command(self):
        for span in ("claude -p hello", "yes please", "FOO=1 claude --version"):
            with self.subTest(span=span):
                self.assertIsNone(code_step.verification_command(f"- [ ] **Check**: runs `{span}`"))

    def test_a_program_that_never_ends_or_waits_for_input_is_never_a_fallback_command(self):
        spans = ("watch -n 1 date", "top -b", "htop -d 5", "less notes.txt", "more notes.txt", "vi notes.txt",
                 "vim notes.txt", "nano notes.txt", "sleep 5", "tail -f app.log", "tail -F app.log",
                 "tail -n 5 -f app.log", "tail --follow app.log", "FOO=1 sleep 5", "/usr/bin/watch ls",
                 "tail -Fn5 app.log", "tail -fn20 x")

        with unittest.mock.patch.object(code_step.shutil, "which", return_value="/usr/bin/anything"):
            for span in spans:
                with self.subTest(span=span):
                    self.assertFalse(code_step.starts_like_a_program_here(span, self.repo))

    def test_tail_without_follow_is_a_fallback_command(self):
        with unittest.mock.patch.object(code_step.shutil, "which", return_value="/usr/bin/tail"):
            for span in ("tail -n 5 app.log", "tail app.log", "tail -c 20 app.log"):
                with self.subTest(span=span):
                    self.assertTrue(code_step.starts_like_a_program_here(span, self.repo))

    def test_claude_and_yes_are_refused_by_a_path_to_them_too(self):
        for span in ("/usr/bin/yes y", "/home/u/.local/bin/claude -p hi", "FOO=1 /usr/bin/yes y"):
            with self.subTest(span=span):
                self.assertFalse(code_step.starts_like_a_program_here(span, self.repo))
                self.assertIsNone(code_step.verification_command(f"- [ ] **Check**: runs `{span}`", self.repo))

    def test_a_file_outside_the_repo_is_not_a_repo_file_command(self):
        outside = self.repo.parent / "outside-tool"
        outside.write_text("#!/bin/sh\n")
        outside.chmod(0o755)
        self.addCleanup(outside.unlink)
        insideLink = self.repo / "link-tool"
        insideLink.symlink_to(outside)

        for span in (f"../{outside.name} --x", "./link-tool --x"):
            with self.subTest(span=span):
                self.assertFalse(code_step.starts_like_a_program_here(span, self.repo))

    def test_a_relative_path_is_never_looked_up_from_the_working_directory_as_a_path_program(self):
        with unittest.mock.patch.object(code_step.shutil, "which", return_value="/anywhere/tool"):
            self.assertFalse(code_step.starts_like_a_program_here("../tool --x", self.repo))
            self.assertFalse(code_step.starts_like_a_program_here("sub/tool --x", self.repo))
            self.assertTrue(code_step.starts_like_a_program_here("tool --x", self.repo))
            self.assertTrue(code_step.starts_like_a_program_here("/opt/bin/tool --x", self.repo))

    def test_a_file_inside_the_repo_by_a_path_that_goes_through_a_folder_is_a_repo_file_command(self):
        (self.repo / "bin").mkdir()
        tool = self.repo / "bin" / "tool"
        tool.write_text("#!/bin/sh\n")
        tool.chmod(0o755)

        for span in ("bin/tool --x", "./bin/tool --x", "bin/../bin/tool --x", f"{tool} --x"):
            with self.subTest(span=span):
                self.assertTrue(code_step.starts_like_a_program_here(span, self.repo))

    def test_the_write_time_check_applies_the_argument_and_program_rules_of_the_fallback(self):
        for item in ("- [ ] **Check**: the `ls` program lists them", "- [ ] **Check**: asks `claude -p hello`",
                     "- [ ] **Check**: runs `/usr/bin/yes y`"):
            with self.subTest(item=item):
                self.assertEqual(1, self.plan_check(self.bad_item_plan(item)).returncode)

    def test_a_repo_file_is_a_command_only_when_it_is_executable(self):
        checkFile = self.make_repo_script("scripts/check-orders", 0o644)
        item = "- [ ] **Check**: the orders pass - `scripts/check-orders --all`"
        notExecutable = code_step.verification_command(item, self.repo)
        checkFile.chmod(0o755)
        executable = code_step.verification_command(item, self.repo)

        self.assertEqual((None, "scripts/check-orders --all"), (notExecutable, executable))

    def test_the_item_problem_names_the_command_word_after_the_variable_assignments(self):
        problem = code_step.verification_item_problem("- [ ] **Check**: the orders pass - `FOO=1 RUN x`", self.repo)

        self.assertIn("it starts with `RUN`", problem)
        self.assertNotIn("FOO=1", problem)

    # ---------- an item that CI or a person runs ----------

    def test_an_item_tagged_ci_verified_or_human_only_is_a_third_shape_in_any_case_or_markup(self):
        for item in ("- [ ] CI-verified: push and watch the pipeline", "- [ ] **CI-verified**: the pipeline runs it",
                     "- [ ] **ci-verified** - `gh run watch`", "- [ ] Human-only: look at the page",
                     "- [x] **Human-only:** open it", "- [ ] **Test-verified**: HUMAN-ONLY, a person looks"):
            with self.subTest(item=item):
                self.assertIsNotNone(code_step.plan_format.deferred_verification_tag(item))
                self.assertIsNone(code_step.verification_item_problem(item, self.repo))
                self.assertEqual(0, self.plan_check(self.bad_item_plan(item)).returncode)

    def test_an_item_that_only_mentions_ci_verified_after_other_words_is_not_tagged(self):
        item = "- [ ] **Check**: the orders pass, not CI-verified yet"

        self.assertIsNone(code_step.plan_format.deferred_verification_tag(item))
        self.assertIsNotNone(code_step.verification_item_problem(item, self.repo))

    def test_an_item_tagged_for_ci_or_a_person_is_never_run_even_with_a_command_in_it(self):
        section = ("#### Automated Verification:\n\n- [ ] **CI-verified**: the pipeline runs `touch ran-by-code-step`\n"
                   "- [ ] Human-only: look at the page\n\n#### Manual Verification:\n")

        self.assertEqual(([], [], []), code_step.run_verification_commands(self.repo, section))
        self.assertFalse((self.repo / "ran-by-code-step").exists())

    def test_a_not_applicable_item_is_never_run_even_with_a_command_in_it(self):
        section = "#### Automated Verification:\n\n- [ ] N/A — nothing to run, not `touch ran-na-item`\n\n#### Manual Verification:\n"

        self.assertEqual(([], [], []), code_step.run_verification_commands(self.repo, section))
        self.assertFalse((self.repo / "ran-na-item").exists())

    def test_deferred_items_are_listed_with_their_tag_in_file_order(self):
        section = ("#### Automated Verification:\n\n- [ ] **CI-verified**: the pipeline runs it\n"
                   "- [ ] **Check**: runs - `true now`\n- [ ] Human-only: look at the page\n")

        self.assertEqual([("CI-verified", "**CI-verified**: the pipeline runs it"),
                          ("human-only", "Human-only: look at the page")],
                         code_step.deferred_verification_items(section))

    def test_start_accepts_a_plan_with_an_item_tagged_ci_verified(self):
        (self.repo / self.plan).write_text(self.bad_item_plan("- [ ] **CI-verified**: the pipeline runs it"))

        out = self.start_phase_one()

        self.assertIn("AGENT: coder", out)

    def test_finish_phase_lists_the_items_it_did_not_run_and_marks_the_phase_done(self):
        self.coder_round_then_edit_verification("- [ ] **Check**: runs - `test -d backend`\n"
                                                "- [ ] **CI-verified**: push and watch the pipeline\n"
                                                "- [ ] Human-only: look at the page")
        self.hook("review-loop", self.LOOP_OK)

        out = self.step("after-review")

        self.assertNotIn("could not be run", out)
        self.assertEqual("done", self.state()["stage"])
        self.assertIn("not run here: CI-verified - **CI-verified**: push and watch the pipeline", out)
        self.assertIn("not run here: human-only - Human-only: look at the page", out)
        self.assertIn("1 command(s) green (test -d backend)", out)

    def test_an_untagged_item_without_a_command_still_stops_even_when_others_are_tagged(self):
        self.coder_round_then_edit_verification("- [ ] **CI-verified**: push and watch the pipeline\n"
                                                "- [ ] **Check**: the streams pass, see the log")
        self.hook("review-loop", self.LOOP_OK)

        out = self.step("after-review")

        self.assertIn("ACTION: stop", out)
        self.assertIn("could not be run", out)
        self.assertNotIn("CI-verified**: push and watch the pipeline - ", out)

    def test_the_item_shape_text_names_the_three_shapes(self):
        shape = code_step.VERIFICATION_ITEM_SHAPE

        for text in ("one of three shapes", "N/A", "CI-verified", "Human-only", "executable file in the repo",
                     "'- [ ] **Name**: what it checks - `npm test`'"):
            self.assertIn(text, shape)
        self.assertNotIn("``", shape)

    def test_plan_check_leaves_a_done_phase_item_without_a_command_alone(self):
        text = self.bad_item_plan("- [ ] **Check**: the orders pass, see the log").replace(
            "- [ ] Phase 1: Walking skeleton", "- [x] Phase 1: Walking skeleton")

        self.assertEqual(0, self.plan_check(text).returncode)

    def test_plan_check_leaves_a_closing_phase_item_without_a_command_alone(self):
        text = self.plan_text().replace("## Phase 4: Refactor pass\n\nSweep.", "## Phase 4: Refactor pass\n\nSweep.\n\n"
                                        "#### Automated Verification:\n\n- [ ] Recap produced.\n")

        self.assertEqual(0, self.plan_check(text).returncode)

    def test_start_stops_on_an_item_that_cannot_run_and_names_its_line(self):
        item = "- [ ] **Check**: the orders pass - `RUN npx vitest run`"
        (self.repo / self.plan).write_text(self.bad_item_plan(item))
        badLine = self.plan_text().splitlines().index(item) + 1

        out = self.start_phase_one()

        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn(f"{self.plan}:{badLine}:", out)

    def test_the_plan_hook_exits_two_on_an_item_that_cannot_run(self):
        self.start_phase_one()
        item = "- [ ] **Check**: the orders pass - `RUN npx vitest run`"
        (self.repo / self.plan).write_text(self.bad_item_plan(item))
        badLine = self.plan_text().splitlines().index(item) + 1
        event = {"cwd": str(self.repo), "tool_input": {"file_path": str(self.repo / self.plan)}}

        result = run(self.repo, self.env, "plan-hook", stdin=json.dumps(event))

        self.assertEqual(2, result.returncode)
        self.assertIn(f"{self.plan}:{badLine}:", result.stderr)

    def coder_round_then_edit_verification(self, lines):
        # The plan is edited after the phase starts, as a coder would: `start` stops on an item that cannot run. The
        # edit is taken as the phase text the coder worked from, so it does not send a second coder for added lines.
        self.begin_coder()
        self.replace_phase_one_verification(lines)
        self.set_state(phaseText=code_step.phase_text(self.plan_text().splitlines(), "1"))
        self.hook("coder", self.CODER_REPORT)
        self.step("after-coder")

    def test_a_stop_for_unrunnable_items_names_each_line_with_its_reason_when_other_commands_ran(self):
        self.coder_round_then_edit_verification("- [ ] **Check**: runs - `test -d backend`\n"
                                                "- [ ] **Check**: the streams pass, see the log\n"
                                                "- [ ] **Check**: the orders pass - `RUN npx vitest run`")
        self.hook("review-loop", self.LOOP_OK)

        out = self.step("after-review")

        self.assertIn("ACTION: stop", out)
        self.assertIn("1 other command(s) ran", out)
        self.assertIn("- [ ] **Check**: the streams pass, see the log - it has no backticked command", out)
        self.assertIn("- [ ] **Check**: the orders pass - `RUN npx vitest run` - no backticked span starts with", out)
        self.assertIn("one of three shapes", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    # ---------- the repo's gate environment variables ----------

    def add_plan_with_gate(self, folder, command):
        planDir = self.repo / "docs/plans" / folder
        planDir.mkdir(parents=True)
        (planDir / "spec.md").write_text(f"# Other\n\n## Phase 1: X\n\n#### Automated Verification:\n\n"
                                         f"- [ ] **Test-verified**: passes - `{command}`\n\n#### Manual Verification:\n")

    def test_a_planless_dispatch_carries_the_gate_variables_the_repo_plans_agree_on(self):
        self.add_plan_with_gate("other", "LEDGER_EDIT_WATCH_PY=/x/edit_watch.py cargo test")

        out = self.step("start", "--task", "add a flag")

        self.assertIn("gate-env: LEDGER_EDIT_WATCH_PY=/x/edit_watch.py", self.printed_prompt(out))

    def test_a_planless_dispatch_leaves_out_a_variable_the_repo_plans_give_two_values(self):
        self.add_plan_with_gate("one", "GATE_PATH=/a cargo test")
        self.add_plan_with_gate("two", "GATE_PATH=/b cargo test")
        self.add_plan_with_gate("three", "GATE_FLAG=1 cargo test")

        out = self.step("start", "--task", "add a flag")

        prompt = self.printed_prompt(out)
        self.assertIn("gate-env: GATE_FLAG=1", prompt)
        self.assertNotIn("GATE_PATH", prompt)

    def test_a_dispatch_with_no_gate_variables_in_the_plans_has_no_gate_env_line(self):
        out = self.start_phase_one()

        self.assertNotIn("gate-env:", self.printed_prompt(out))

    def test_the_coder_gate_runs_its_commands_with_the_gate_variables_of_the_repo(self):
        self.set_verification("- [ ] **Env**: passes - `GATE_X=1 npx vitest run`")
        self.add_plan_with_gate("other", 'GATE_Y="two words" cargo test')

        out = self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual({"GATE_X": "1", "GATE_Y": "two words"}, gate["env"])
        self.assertIn('With: GATE_X=1 GATE_Y="two words".', out)

    def test_the_coder_gate_given_no_gate_variables_stores_none_and_says_nothing_about_them(self):
        out = self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual({}, gate["env"])
        self.assertNotIn("With:", out)

    def test_a_plan_dispatch_and_its_review_dispatch_carry_the_plans_own_gate_variables(self):
        self.set_verification("- [ ] **Env**: passes - `GATE_X=1 npx vitest run`")

        out = self.start_phase_one()
        self.assertIn("gate-env: GATE_X=1", self.printed_prompt(out))
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", self.CODER_REPORT)
        reviewOut = self.step("after-coder")

        self.assertIn("AGENT: review-loop", reviewOut)
        self.assertIn("gate-env: GATE_X=1", self.printed_prompt(reviewOut))


if __name__ == "__main__":
    unittest.main()
