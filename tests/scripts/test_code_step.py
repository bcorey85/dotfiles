import datetime
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
import unittest.mock
from typing import ClassVar

import toolkit_paths

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = pathlib.Path(os.environ.get("CODE_STEP_REAL_CLAUDE") or REPO_ROOT / "claude" / ".claude")
SCRIPT = pathlib.Path(os.environ.get("CODE_STEP_SCRIPT") or REAL_CLAUDE / "scripts" / "code" / "code_step.py")
HANDBACK_SCRIPT = pathlib.Path(os.environ.get("HANDBACK_SCRIPT") or REAL_CLAUDE / "scripts" / "review" / "handback.py")
SCRIPTS_ROOT = SCRIPT.parent.parent
sys.path.insert(0, str(SCRIPT.parent))
sys.path.insert(0, str(SCRIPTS_ROOT / "lib"))


def stage_script(source_root, name, destination_root):
    """Copy `name` from its folder under source_root into the same folder under destination_root."""
    source = toolkit_paths.script_in(source_root, name)
    destination = destination_root / source.parent.name / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, destination)
module_spec = importlib.util.spec_from_file_location("code_step", SCRIPT)
code_step = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(code_step)
import code_step_boundary  # noqa: E402
import code_step_core  # noqa: E402
import code_step_gates  # noqa: E402
import code_step_report  # noqa: E402
import plan_format  # noqa: E402

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


def run(cwd, env, *args, stdin=None, interpreter=sys.executable):
    return subprocess.run([interpreter, str(SCRIPT), *args], cwd=cwd, env=env, input=stdin,
                          capture_output=True, text=True)


class CodeStepTest(unittest.TestCase):
    SESSION = "sess-1"
    GIT_IDENTITY: ClassVar[dict[str, str]] = {
        "GIT_AUTHOR_NAME": "t",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "t",
        "GIT_COMMITTER_EMAIL": "t@t",
    }

    @classmethod
    def setUpClass(cls):
        # Every test starts from a copy of this repo: the work tree and the one base commit, built once.
        class_directory = tempfile.TemporaryDirectory()
        cls.addClassCleanup(class_directory.cleanup)
        class_home = pathlib.Path(class_directory.name) / "home"
        class_home.mkdir()
        cls.base_repo = pathlib.Path(class_directory.name) / "repo"
        (cls.base_repo / "backend/src").mkdir(parents=True)
        (cls.base_repo / "docs/plans/orders").mkdir(parents=True)
        (cls.base_repo / "backend/package.json").write_text(json.dumps({
            "scripts": {"typecheck": "tsc --noEmit", "lint": "eslint ."},
            "devDependencies": {"vitest": "1", "eslint": "9"}}))
        (cls.base_repo / "backend/src/existing.ts").write_text("export const a = 1\n")
        (cls.base_repo / "docs/plans/orders/spec.md").write_text(PLAN)
        (cls.base_repo / "docs/plans/orders/acceptance-criteria.md").write_text("AC-1 orders exist\n")
        git_env = dict(os.environ, HOME=str(class_home), **cls.GIT_IDENTITY)
        for command in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "base"]):
            subprocess.run(command, cwd=cls.base_repo, check=True, capture_output=True, env=git_env)

    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.tmp = pathlib.Path(temp_directory.name)
        self.claude = self.tmp / "claude"
        (self.claude / "scripts").mkdir(parents=True)
        (self.claude / "skills/review").mkdir(parents=True)
        for name in ("coder_gate.py", "resolve-task-dir.sh"):
            stage_script(REAL_CLAUDE / "scripts", name, self.claude / "scripts")
        for name in ("coder_packet.py", "plan_format.py", "script_utils.py", *toolkit_paths.CODE_STEP_MODULES,
                     "shell_command.py", "makefile_text.py", "test_run_output.py"):
            stage_script(SCRIPTS_ROOT, name, self.claude / "scripts")
        self.log = self.tmp / "calls.log"
        (self.claude / "scripts" / "telemetry").mkdir()
        for name in ("scripts/telemetry/log-scan", "skills/review/log-review-finding"):
            stub = self.claude / name
            stub.write_text(f'#!/usr/bin/env bash\necho "{name} $@" >> {self.log}\n'
                            'case "$*" in *finding_id=*) ;; '
                            f"*kind=finding*) echo finding_id={self.MINTED_FINDING_ID};; esac\n")
            stub.chmod(0o755)
        self.repo = self.tmp / "repo"
        shutil.copytree(self.base_repo, self.repo, symlinks=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.jump_log = self.tmp / "jump.log"
        self.nvim_jump = self.tmp / "nvim-jump"
        self.nvim_jump.write_text(f'#!/usr/bin/env bash\necho "$@" >> {self.jump_log}\n')
        self.nvim_jump.chmod(0o755)
        self.env = dict(os.environ, CODE_STEP_CLAUDE_DIR=str(self.claude), **self.GIT_IDENTITY,
                        CODE_STEP_NVIM_JUMP=str(self.nvim_jump),
                        HOME=str(self.home), CODE_STEP_WAIT_SECONDS="0", CLAUDE_CODE_SESSION_ID=self.SESSION,
                        CODE_STEP_REVIEW_LOOP="agent",
                        HANDBACK_STORE_DIR=str(self.tmp / "handback-store"),
                        PYTHONPATH=str(HANDBACK_SCRIPT.parent))
        self.env.pop("CODE_STEP_IMPACT_DECISION", None)
        self.env.pop("CODE_STEP_ASKS_OUTCOME", None)
        self.env.pop("CLAUDE_FORMAT_HOOK_OFF", None)
        self.plan = "docs/plans/orders/spec.md"
        self.gate_commands = ["true"]

    def step(self, *args, stdin=None):
        return run(self.repo, self.env, *args, stdin=stdin).stdout

    def handback_hook(self, kind, event):
        return subprocess.run([sys.executable, str(HANDBACK_SCRIPT), "hook", kind], env=self.env,
                              input=json.dumps(event), capture_output=True, text=True)

    def launch_the_pending_dispatch(self, agent_id, agent_type, session=SESSION):
        # A hand-back counts only from the agent the pending dispatch launched, so a test launches its agent first, as
        # the Agent call's log hook records it, from the session that hands back. A dispatch already launched keeps its
        # launch.
        run_id = self.state().get("runId")
        events_file = self.repo / ".git/code-step/runs" / str(run_id) / "events.jsonl"
        if not run_id or not events_file.exists():
            return
        events = [json.loads(line) for line in events_file.read_text().splitlines()]
        dispatches = [event for event in events if event["event"] == "dispatch"]
        if not dispatches or dispatches[-1]["agent_type"] != agent_type:
            return
        dispatch_id = dispatches[-1]["id"]
        if any(event["event"] == "launch" and event.get("dispatch") == dispatch_id for event in events):
            return
        self.launch_agent(f"code-step-dispatch: {run_id}/{dispatch_id}", agent_id=agent_id, subagent_type=agent_type,
                          session=session)

    def launch_the_pending_review(self, agent_id):
        self.launch_the_pending_dispatch(agent_id, "review-loop")

    def run_the_coder_gate(self, event):
        # The real gate hook of the coder, with the gate's commands swapped for self.gate_commands so that no test runs
        # npm. Returns the hook's decision, or None when the gate does not look at the call.
        gate_path = self.repo / ".git/coder-gate.json"
        if event["agent_type"] != "coder" or not gate_path.exists():
            return None

        gate = json.loads(gate_path.read_text())
        gate["commands"] = self.gate_commands
        gate_path.write_text(json.dumps(gate))
        gate_script = str(self.claude / "scripts/code/coder_gate.py")
        finished = subprocess.run([sys.executable, gate_script, "hook"], env=self.env,
                                  input=json.dumps(event), capture_output=True, text=True)
        if not finished.stdout.strip():
            return None
        return json.loads(finished.stdout)["hookSpecificOutput"]

    def hook(self, agent_type, message, agent_id="a1", session=SESSION, launched=True, cwd=None):
        # The fork hands back. The PreToolUse hooks of settings.json see the call: the coder gate may deny it or stamp
        # its message, the hand-back packet hook may deny it, and so may the code-step hook. A hand-back that goes
        # through is logged by the PostToolUse log hook with the message as stamped; a denied one never reaches it.
        event = {"agent_type": agent_type, "agent_id": agent_id, "cwd": cwd or str(self.repo),
                 "tool_input": {"message": message}}
        if session:
            event["session_id"] = session
        if launched:
            self.launch_the_pending_dispatch(agent_id, agent_type, session or self.SESSION)

        gate_decision = self.run_the_coder_gate(event)
        packet_hook_denies = False
        if agent_type == "review-loop" and session:
            # The shared hand-back store sees the review-loop's dispatch and hand-back, as its own hooks record them.
            self.handback_hook("dispatch", {"session_id": session, "tool_input": {"subagent_type": "review-loop"}})
            self.handback_hook("dispatch", {"session_id": session, "agent_type": agent_type, "agent_id": agent_id,
                                            "tool_input": {"subagent_type": "code-reviewer"}})
            packet_result = self.handback_hook("handback", event)
            packet_hook_denies = "permissionDecision" in packet_result.stdout
        result = run(self.repo, self.env, "hook", stdin=json.dumps(event))

        gate_denies = gate_decision is not None and gate_decision["permissionDecision"] == "deny"
        if gate_denies or packet_hook_denies or "permissionDecision" in result.stdout:
            return result

        stamped_message = message
        if gate_decision is not None:
            stamped_message = gate_decision["updatedInput"]["message"]
        self.hand_back(stamped_message, agent_type, agent_id, session=session, cwd=cwd or str(self.repo))
        return result

    def commit_all(self):
        for command in (["git", "add", "-A"], ["git", "commit", "-qm", "phase"]):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True, env=self.env)

    def state(self):
        out = self.step("status")
        return json.loads(out) if out.startswith("{") else {}

    def gate_mark(self, session=SESSION):
        mark_file = self.home / ".claude/state/review-gate" / session
        return mark_file.read_text() if mark_file.exists() else None

    def assert_marked_clean(self, out, session=SESSION):
        # The script writes the review-commit-gate state file itself, so the output no longer tells the model to.
        self.assertNotIn("review-gate-mark", out)
        self.assertEqual("clean\n", self.gate_mark(session))

    def assert_first_phase_ticked(self):
        plan_lines = self.plan_text().split("\n")
        entries = plan_format.parse_plan_with_closing_phases(plan_lines)["entries"]
        self.assertTrue(entries[0]["done"])

    def said(self):
        # The say text, then the question for the user: the two files the /code skill hands back.
        state_folder = self.repo / ".git/code-step"
        saved_files = [state_folder / "say.md", state_folder / "question.md"]
        return "".join(saved_file.read_text() for saved_file in saved_files if saved_file.exists())

    def plan_text(self):
        return (self.repo / self.plan).read_text()

    def start_phase_one(self, *extra):
        return self.step("start", self.plan, *extra)

    def pass_coder_gate(self):
        gate_path = self.repo / ".git/coder-gate.json"
        if gate_path.exists():
            gate = json.loads(gate_path.read_text())
            gate["coders"]["a1"] = {"runs": 1, "denies": 0, "failed": [], "skipped": [], "result": "pass"}
            gate_path.write_text(json.dumps(gate))

    def begin_coder(self, source="export const o = 1\n", start_options=()):
        self.start_phase_one(*start_options)
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text(source)

    def coder_round(self, report=None, source="export const o = 1\n", start_options=()):
        report = report or "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters\nREVIEW: recommended"
        self.begin_coder(source, start_options)
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
    # The id the stand-in log helper prints for a finding row it is not given an id for.
    MINTED_FINDING_ID = "aaaaaaaaaaaaaaaa"
    LOGGED_FINDING_ID = "bbbbbbbbbbbbbbbb"
    ASK = ('status: converged\niter: 1\nfixed: []\nask: [{"finding": "f", "file_line": "backend/src/orders.ts:2", '
           '"question": "keep?", "change": "export o as a const", "gate": "code-reviewer", "class": "correctness", '
           '"finding_id": "0123456789abcdef"}]')

    ASK_WITHOUT_FINDING_ID = ASK.replace(', "finding_id": "0123456789abcdef"', "")

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

    def stored_gate_commands(self):
        return json.loads((self.repo / ".git/coder-gate.json").read_text())["commands"]

    def test_gate_ends_with_the_stale_prose_check_from_the_base_commit_of_the_step(self):
        self.start_phase_one()

        stale_prose_script = SCRIPT.resolve().parent / "stale_prose.py"
        expected = f"python3 {stale_prose_script} --base {self.state()['baseHead']}"
        self.assertEqual(expected, self.stored_gate_commands()[-1])
        self.assertRegex(self.state()["baseHead"], "^[0-9a-f]{40}$")

    def test_start_after_abort_begins_a_fresh_run(self):
        self.start_phase_one()

        self.step("abort")
        out = self.start_phase_one()

        self.assertNotIn("a /code run is open here", out)
        self.assertIn("ACTION: dispatch", out)
        self.assertIn("AGENT: coder", out)

    def test_abort_with_no_open_run_says_so_and_writes_no_file(self):
        out = self.step("abort")

        self.assertIn("No /code run is open here. Nothing was dropped.", out)
        self.assertFalse((self.repo / ".git/code-step").exists())

    def test_abort_archives_the_state_and_keeps_the_ruled_asks_and_names_the_open_dispatch(self):
        self.start_phase_one()
        self.launch_the_pending_dispatch("agent-9", "coder")
        state_folder = self.repo / ".git/code-step"
        (state_folder / "ruled-asks.json").write_text("[]")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")

        out = self.step("abort")

        self.assertIn("ACTION: stop", out)
        self.assertIn("agent agent-9", out)
        self.assertIn("backend/src/orders.ts", out)
        self.assertFalse((state_folder / "state.json").exists())
        archives = list(state_folder.glob("aborted-*.json"))
        self.assertEqual(1, len(archives))
        self.assertIn(str(archives[0]), out)
        self.assertEqual("coder", json.loads(archives[0].read_text())["stage"])
        self.assertTrue((state_folder / "ruled-asks.json").exists())
        self.assertTrue((self.repo / "backend/src/orders.ts").exists())

    def test_abort_refuses_extra_arguments_and_keeps_the_run(self):
        self.start_phase_one()

        out = self.step("abort", "now")

        self.assertIn("Refused: abort takes no arguments.", out)
        self.assertEqual("coder", self.state()["stage"])

    def test_start_names_the_abort_verb_when_given_it_as_task_text(self):
        out = self.step("start", "abort")

        self.assertIn("`abort` is a verb, not task text.", out)
        self.assertIn("code_step.py abort", out)

    def test_gate_of_a_restarted_unfinished_phase_uses_the_first_base_commit(self):
        self.start_phase_one()
        first_base_head = self.state()["baseHead"]
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.commit_all()

        self.step("start", "--restart")

        stale_prose_script = SCRIPT.resolve().parent / "stale_prose.py"
        self.assertEqual(f"python3 {stale_prose_script} --base {first_base_head}", self.stored_gate_commands()[-1])
        self.assertEqual(first_base_head, self.state()["baseHead"])

    def test_planless_start_keeps_no_stale_prose_gate(self):
        self.step("start", "fix the typo in the orders page")

        self.assertFalse((self.repo / ".git/coder-gate.json").exists())

    def test_gate_skips_a_package_in_a_sibling_repo(self):
        sibling = self.tmp / "sibling/evals"
        (sibling / "truth").mkdir(parents=True)
        (sibling / "package.json").write_text(json.dumps({"devDependencies": {"vitest": "1"}}))
        (sibling / "tsconfig.json").write_text("{}")
        sibling_file = "**File**: `backend/src/orders.test.ts`\n**File**: `../sibling/evals/truth/context.json`"
        (self.repo / self.plan).write_text(
            self.plan_text().replace("**File**: `backend/src/orders.test.ts`", sibling_file)
        )

        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        joined = " | ".join(gate["commands"])
        self.assertNotIn("sibling", joined)
        self.assertIn("cd backend && npm run typecheck", joined)

    def test_gate_runs_clippy_with_warnings_denied_in_the_cargo_package_that_holds_a_named_rust_file(self):
        (self.repo / "crate/src").mkdir(parents=True)
        (self.repo / "crate/Cargo.toml").write_text('[package]\nname = "crate"\n')
        (self.repo / "crate/src/lib.rs").write_text("pub fn a() {}\n")
        rust_file = "**File**: `backend/src/orders.test.ts`\n**File**: `crate/src/lib.rs`\n**File**: `crate/Cargo.toml`"
        (self.repo / self.plan).write_text(
            self.plan_text().replace("**File**: `backend/src/orders.test.ts`", rust_file)
        )

        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual(1, gate["commands"].count("cd crate && cargo clippy --all-targets -- -D warnings"))
        self.assertEqual(["cd crate && cargo test --lib --bins"],
                         [command for command in gate["commands"] if "cargo test" in command])
        self.assertIn("cd backend && npm run typecheck", gate["commands"])

    def test_gate_runs_clippy_without_a_cd_prefix_when_the_phase_names_only_the_root_cargo_manifest(self):
        (self.repo / "Cargo.toml").write_text('[package]\nname = "root-crate"\n')
        root_manifest = "**File**: `backend/src/orders.test.ts`\n**File**: `Cargo.toml`"
        (self.repo / self.plan).write_text(
            self.plan_text().replace("**File**: `backend/src/orders.test.ts`", root_manifest)
        )

        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual(1, gate["commands"].count("cargo clippy --all-targets -- -D warnings"))

    def test_gate_runs_only_the_rust_tests_of_the_named_files_and_sets_no_cargo_variable(self):
        (self.repo / "crate/src").mkdir(parents=True)
        (self.repo / "crate/tests").mkdir()
        (self.repo / "crate/Cargo.toml").write_text('[package]\nname = "crate"\n')
        (self.repo / "crate/src/lib.rs").write_text("")
        rust_files = "**File**: `crate/src/store/query.rs`\n**File**: `crate/tests/side_streams.rs`"
        (self.repo / self.plan).write_text(
            self.plan_text().replace("**File**: `backend/src/orders.test.ts`", rust_files)
        )

        self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual(["cd crate && cargo clippy --all-targets -- -D warnings",
                          "cd crate && cargo test --lib --bins",
                          "cd crate && cargo test --test side_streams"],
                         [command for command in gate["commands"] if "cargo" in command])

    def make_helper_phase_with_verification(self, verification_line, start_arguments=()):
        (self.repo / "crate/src").mkdir(parents=True)
        (self.repo / "crate/tests/common").mkdir(parents=True)
        (self.repo / "crate/Cargo.toml").write_text('[package]\nname = "crate"\n')
        (self.repo / "crate/src/lib.rs").write_text("")
        (self.repo / "crate/tests/common/mod.rs").write_text("")
        helper_file = "**File**: `backend/src/orders.test.ts`\n**File**: `crate/tests/common/mod.rs`"
        plan_text = self.plan_text().replace("**File**: `backend/src/orders.test.ts`", helper_file)
        old = "- [ ] **Prohibition**: no console.log - `git grep -n --untracked console.log -- backend/src/orders.ts`"
        self.assertIn(old, plan_text)
        (self.repo / self.plan).write_text(plan_text.replace(old, verification_line))
        self.start_phase_one(*start_arguments)
        return json.loads((self.repo / ".git/coder-gate.json").read_text())["commands"]

    def test_gate_takes_the_cargo_commands_the_phase_lists_in_place_of_the_derived_ones(self):
        commands = self.make_helper_phase_with_verification("- [ ] Orders test passes: `cargo test --test orders`")

        self.assertIn("cargo test --test orders", commands)
        self.assertEqual([], [command for command in commands if "cargo test --tests" in command])
        self.assertEqual([], [command for command in commands if "cargo clippy" in command])

    def test_gate_takes_the_listed_cargo_commands_when_the_phase_is_started_with_the_phase_option(self):
        listed_rows = ("- [ ] Orders test passes: `cargo test --test orders`\n"
                       "- [ ] Orders test passes under nextest: `cargo nextest run --test orders`")
        commands = self.make_helper_phase_with_verification(listed_rows,
                                                            start_arguments=("--phase", "1"))

        self.assertIn("cargo test --test orders", commands)
        self.assertIn("cargo nextest run --test orders", commands)
        self.assertEqual([], [command for command in commands if "cargo test --tests" in command])
        self.assertEqual([], [command for command in commands if "cargo clippy" in command])

    def test_gate_keeps_the_derived_cargo_commands_when_the_phase_lists_no_cargo_command(self):
        commands = self.make_helper_phase_with_verification("- [ ] No stray logging: `git grep -n TODO -- crate/src`")

        self.assertIn("cd crate && cargo test --tests", commands)
        self.assertIn("cd crate && cargo clippy --all-targets -- -D warnings", commands)

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

                self.assertEqual(wanted, code_step_gates.cargo_commands(self.repo, [path]))

    def test_cargo_commands_are_merged_per_crate_without_duplicates_and_never_run_a_whole_crate(self):
        for crate in ("one", "two"):
            (self.repo / crate / "src").mkdir(parents=True)
            (self.repo / crate / "src/lib.rs").write_text("")
            (self.repo / crate / "Cargo.toml").write_text(f'[package]\nname = "{crate}"\n')
        paths = ["one/src/a.rs", "two/src/b.rs", "one/src/a.rs", "one/src/lib.rs", "one/Cargo.toml", "one/src/c.rs"]

        commands = code_step_gates.cargo_commands(self.repo, paths)

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

        commands = code_step_gates.cargo_commands(self.repo, paths)

        self.assertEqual(["cd crate && cargo clippy --all-targets -- -D warnings", "cd crate && cargo test --tests"],
                         commands)
        self.assertNotIn("cd crate && cargo test --lib --bins", commands)

    def test_two_modules_of_one_library_crate_give_one_lib_test_command(self):
        (self.repo / "lib/src/store").mkdir(parents=True)
        (self.repo / "lib/src/lib.rs").write_text("")
        (self.repo / "lib/Cargo.toml").write_text('[package]\nname = "lib"\n')

        commands = code_step_gates.cargo_commands(self.repo, ["lib/src/store/query.rs", "lib/src/orders.rs"])

        self.assertEqual(["cd lib && cargo clippy --all-targets -- -D warnings", "cd lib && cargo test --lib --bins"],
                         commands)

    def test_a_change_to_the_library_root_runs_the_lib_tests(self):
        (self.repo / "lib/src").mkdir(parents=True)
        (self.repo / "lib/src/lib.rs").write_text("")
        (self.repo / "lib/Cargo.toml").write_text('[package]\nname = "lib"\n')

        commands = code_step_gates.cargo_commands(self.repo, ["lib/src/lib.rs"])

        self.assertEqual(["cd lib && cargo clippy --all-targets -- -D warnings", "cd lib && cargo test --lib --bins"],
                         commands)

    def test_a_named_binary_file_in_a_library_crate_runs_only_that_binary(self):
        (self.repo / "both/src/bin").mkdir(parents=True)
        (self.repo / "both/src/lib.rs").write_text("")
        (self.repo / "both/Cargo.toml").write_text('[package]\nname = "both"\n')

        commands = code_step_gates.cargo_commands(self.repo, ["both/src/bin/tool.rs"])

        self.assertEqual(["cd both && cargo clippy --all-targets -- -D warnings", "cd both && cargo test --bin tool"],
                         commands)

    def test_a_crate_with_no_library_runs_every_file_under_src_with_bins_once(self):
        (self.repo / "tool/src/store").mkdir(parents=True)
        (self.repo / "tool/src/main.rs").write_text("")
        (self.repo / "tool/Cargo.toml").write_text('[package]\nname = "tool"\n')

        commands = code_step_gates.cargo_commands(self.repo, ["tool/src/store/query.rs", "tool/src/store/mod.rs",
                                                              "tool/src/main.rs"])

        self.assertEqual(["cd tool && cargo clippy --all-targets -- -D warnings", "cd tool && cargo test --bins"],
                         commands)

    def test_a_crate_with_a_library_and_a_binary_runs_a_src_file_with_lib_and_bins(self):
        (self.repo / "both/src").mkdir(parents=True)
        (self.repo / "both/src/lib.rs").write_text("")
        (self.repo / "both/src/main.rs").write_text("")
        (self.repo / "both/Cargo.toml").write_text('[package]\nname = "both"\n')

        commands = code_step_gates.cargo_commands(self.repo, ["both/src/store.rs", "both/src/main.rs"])

        self.assertEqual(["cd both && cargo clippy --all-targets -- -D warnings", "cd both && cargo test --lib --bins"],
                         commands)

    def test_a_manifest_alone_or_a_file_outside_src_and_tests_gives_clippy_and_no_test(self):
        (self.repo / "Cargo.toml").write_text('[package]\nname = "root-crate"\n')
        (self.repo / "src").mkdir()

        commands = code_step_gates.cargo_commands(self.repo, ["Cargo.toml", "benches/speed.rs", "build.rs"])

        self.assertEqual(["cargo clippy --all-targets -- -D warnings"], commands)

    def test_a_verification_item_may_start_with_an_environment_setting(self):
        item = "- [ ] **Tests**: the streams pass - `CARGO_BUILD_JOBS=4 cargo test --test side_streams`"

        command = code_step_boundary.verification_command(item)
        self.assertEqual("CARGO_BUILD_JOBS=4 cargo test --test side_streams", command)
        self.assertIsNone(code_step_boundary.verification_item_problem(item, self.repo))

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

    def test_empty_criteria_file_stops_whatever_the_wording_of_the_criteria_heading(self):
        (self.repo / "docs/plans/orders/acceptance-criteria.md").write_text("")
        for heading in ("### Acceptance criteria", "## ACCEPTANCE CRITERIA (orders)", "## Acceptance"):
            with self.subTest(heading=heading):
                (self.repo / self.plan).write_text(PLAN.replace("## Acceptance Criteria", heading))
                out = self.start_phase_one()
                self.assertIn("ACTION: stop", out)
                self.assertIn("acceptance-criteria.md is missing or empty", out)
                self.step("start", self.plan, "--restart")

    def test_the_log_hook_logs_the_hand_backs_of_any_agent_type_and_only_the_awaited_coders_counts(self):
        self.hook("coder", "early")
        self.assertFalse((self.repo / ".git/code-step").exists())
        self.begin_coder()
        self.hook("Explore", "another agent's report", agent_id="e1")
        self.hook("coder", self.CODER_REPORT)
        handbacks = self.events_named("handback")
        self.assertEqual([("Explore", "e1"), ("coder", "a1")],
                         [(event["agent_type"], event["agent_id"]) for event in handbacks])
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

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

    def test_after_coder_does_not_read_the_gate_stamp_as_the_coders_report(self):
        stamp = ('\n\nHAND-BACK GATE: timeout after 1 run(s), failed: none, skipped (no changed files): none.\n'
                 'HAND-BACK GATE TIMEOUT: these commands timed out after 1200 s with no test result:\n'
                 '  `cargo test --tests`, output tail:\nERROR: column reference "id" is ambiguous')
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended" + stamp)

        out = self.step("after-coder")

        self.assertIn("flagged: none", out)
        self.assertNotIn("ambiguous", out)

    def test_the_handoff_takes_no_file_change_from_the_gate_stamp_output_tail(self):
        stamp = ('\n\nHAND-BACK GATE: timeout after 1 run(s), failed: none, skipped (no changed files): none.\n'
                 'HAND-BACK GATE TIMEOUT: these commands timed out after 1200 s with no test result:\n'
                 '  `cargo test --tests`, output tail:\n- backend/src/orders.ts: 1 failed')
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended" + stamp)

        out = self.step("after-coder")

        self.assertIn("path: backend/src/orders.ts", out)
        self.assertNotIn("change: 1 failed", out)

    def test_after_coder_reports_a_gate_command_that_timed_out_as_timed_out_not_exit_0(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        gate_path = self.repo / ".git/coder-gate.json"
        gate = json.loads(gate_path.read_text())
        timed_out_command = gate["commands"][0]
        gate["coders"]["a1"] = {"runs": 1, "denies": 0, "failed": [], "skipped": [],
                                "timed_out": [timed_out_command], "result": "timeout"}
        gate_path.write_text(json.dumps(gate))

        out = self.step("after-coder")

        self.assertIn(f"{timed_out_command} -> timed out at the hand-back gate, no test result", out)
        self.assertNotIn(f"{timed_out_command} -> exit 0", out)

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
        self.assert_dispatch_logged(out, "d2", "coder", "plan-coder", "resume")
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
        self.assertIn(
            f"Do not edit {self.CRITERIA}. Only the user's own sign-off changes an acceptance criterion.", out
        )
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
        plan_impact = self.state()["planImpact"]
        self.assertIn("RESOLVED: the session ruled on this disagreement, not the user.", plan_impact)
        self.assertNotIn("the user ruled", plan_impact)
        self.assertNotIn("user's words", plan_impact)

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
        copy_path = self.replaced_copies()[0]
        self.assertIn(f"The text it replaced is in {copy_path}.", self.said())
        self.assertNotIn(self.CRITERIA, self.state()["files"])
        self.assertEqual([], self.state()["flagged"])
        self.assertEqual(original + "AC-1 orders may be empty\nSigned off by someone\n", copy_path.read_text())
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
        state_text = json.dumps(self.state())
        self.assertNotIn("replaced-criteria", state_text)
        status = subprocess.run(["git", "status", "--porcelain"], cwd=self.repo, capture_output=True, text=True,
                                env=self.env).stdout
        self.assertNotIn("replaced-criteria", status)

    def check_start_restores_the_criteria(self, start_arguments):
        original = self.criteria_text()
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "plan edited")
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten by the coder\n")
        self.step("start", "--restart", "docs/plans/nope.md")
        self.assertNotIn("criteriaGuard", self.state())
        self.assertEqual(original, self.criteria_text())
        (self.repo / self.CRITERIA).write_text("AC-1 the user's own edit\n")
        self.step(*start_arguments)
        self.assertEqual("AC-1 the user's own edit\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())

    def test_start_keeps_the_replaced_text_in_the_git_dir_and_names_it(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 changed by someone\n")
        out = self.step("start", "--restart")
        copy_path = self.replaced_copies()[0]
        self.assertTrue(copy_path.is_absolute())
        self.assertIn(f"The text it replaced is in {copy_path}.", self.said())
        self.assertNotIn("coder", self.said())
        self.assertEqual("AC-1 changed by someone\n", copy_path.read_text())
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assert_copy_is_not_phase_work(out)

    def test_two_restores_with_different_text_leave_two_copies(self):
        for text in ("AC-1 first change\n", "AC-1 second change\n"):
            self.coder_round(self.IMPACT_REPORT, start_options=("--restart",))
            self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
            self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
            (self.repo / self.CRITERIA).write_text(text)
            self.step("start", "--restart")
        copies = sorted(path.read_text() for path in self.replaced_copies())
        self.assertEqual(["AC-1 first change\n", "AC-1 second change\n"], copies)

    def test_a_criteria_file_the_coder_created_is_deleted_and_its_text_kept(self):
        self.coder_round(self.IMPACT_REPORT)
        (self.repo / self.CRITERIA).unlink()
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 invented\n")
        out = self.step("start", "--restart")
        copy_path = self.replaced_copies()[0]
        self.assertFalse((self.repo / self.CRITERIA).exists())
        self.assertEqual("AC-1 invented\n", copy_path.read_text())
        self.assertIn(f"The text it deleted is in {copy_path}.", self.said())
        self.assert_copy_is_not_phase_work(out)

    def test_after_plan_edit_deletes_a_criteria_file_the_coder_created(self):
        self.coder_round(self.IMPACT_REPORT)
        (self.repo / self.CRITERIA).unlink()
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        (self.repo / self.CRITERIA).write_text("AC-1 invented\n")
        out = self.step("after-plan-edit")
        copy_path = self.replaced_copies()[0]
        self.assertFalse((self.repo / self.CRITERIA).exists())
        self.assertEqual("AC-1 invented\n", copy_path.read_text())
        self.assertTrue(copy_path.is_absolute())
        self.assertIn(f"The text it deleted is in {copy_path}.", self.said())
        self.assertNotIn(self.CRITERIA, self.state()["files"])
        self.assertEqual([], self.state()["flagged"])
        self.assert_copy_is_not_phase_work(out)

    def test_after_plan_edit_keeps_a_criteria_file_the_coder_created_on_a_user_ruling(self):
        self.coder_round(self.IMPACT_REPORT)
        (self.repo / self.CRITERIA).unlink()
        self.step("decide", "adopt", "--by", "user", "--ruling", "add the criteria")
        (self.repo / self.CRITERIA).write_text("AC-1 added\n")
        self.step("after-plan-edit")
        self.assertEqual("AC-1 added\n", self.criteria_text())
        self.assertEqual([], self.replaced_copies())
        self.assertNotIn("deleted it", self.said())

    def commit_on_new_branch(self, criteria_text):
        subprocess.run(["git", "checkout", "-q", "-b", "other-branch"], cwd=self.repo, check=True, env=self.env)
        (self.repo / self.CRITERIA).write_text(criteria_text)
        subprocess.run(["git", "add", self.CRITERIA], cwd=self.repo, check=True, env=self.env)
        subprocess.run(["git", "commit", "-q", "-m", "criteria on the other branch"], cwd=self.repo, check=True,
                       env=self.env)

    def test_a_start_restore_that_then_stops_early_leaves_the_message_and_the_question_in_say(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 changed by someone\n")
        out = self.step("start", "--restart", "docs/plans/nope.md")
        copy_path = self.replaced_copies()[0]
        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"The text it replaced is in {copy_path}.", self.said())
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

    def check_a_planless_start_keeps_the_restore_message(self, start_arguments, done_phases=()):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 changed by someone\n")
        self.mark_phases_done(*done_phases)
        self.step(*start_arguments)
        copy_path = self.replaced_copies()[0]
        self.assertIn(f"The text it replaced is in {copy_path}.", self.said())

    def test_start_task_keeps_the_restore_message_in_say(self):
        self.check_a_planless_start_keeps_the_restore_message(["start", "--restart", "--task", "add a small thing"])

    def test_start_with_task_text_keeps_the_restore_message_in_say(self):
        self.check_a_planless_start_keeps_the_restore_message(["start", "--restart", "fix the typo"], (1, 2, 3, 4))

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

    def test_start_after_the_plan_edit_wait_gave_up_restores_the_saved_criteria(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten by the plan coder\n")
        self.set_state(dispatchAt=time.time())
        time.sleep(0.7)
        self.wait_env(0.2, "0.05", waits=3)
        gave_up = self.step("after-plan-edit")
        self.assertIn("ACTION: stop", gave_up)
        self.assertEqual("stopped", self.state()["stage"])
        self.assertIn("criteriaGuard", self.state())
        self.step("start", "--restart")
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        copy_path = self.replaced_copies()[0]
        self.assertIn(f"The text it replaced is in {copy_path}.", self.said())

    def test_tick_during_the_plan_edit_restores_the_saved_criteria(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten by the plan coder\n")
        self.step("tick", "1")
        self.assertEqual("done", self.state()["stage"])
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        copy_path = self.replaced_copies()[0]
        self.assertIn(f"The text it replaced is in {copy_path}.", self.said())

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

    def check_a_verb_stops_while_the_plan_edit_coder_is_out(self, verb_arguments):
        self.open_plan_edit_with_a_late_criteria_write()
        before = self.state()
        said = self.said()
        out = self.step(*verb_arguments)
        self.assertIn("ACTION: stop", out)
        self.assertIn("`! python3 ", out)
        self.assertIn("code_step.py resume` from the repo root first", out)
        self.assertTrue(out.rstrip().endswith("Tell the user."))
        self.assertEqual("AC-1 rewritten late by the plan coder\n", self.criteria_text())
        self.assertEqual(before, self.state())
        self.assertEqual(said, self.said())
        self.assertEqual([], self.replaced_copies())

    def test_tick_stops_while_the_plan_edit_coder_is_out(self):
        self.check_a_verb_stops_while_the_plan_edit_coder_is_out(["tick", "1"])

    def test_start_stops_while_the_plan_edit_coder_is_out(self):
        self.check_a_verb_stops_while_the_plan_edit_coder_is_out(["start", "--restart"])

    def check_the_stop_leads_through_after_plan_edit_to_a_restore(self, verb_arguments, other_session):
        self.open_plan_edit_with_a_late_criteria_write()
        if other_session:
            self.set_state(sessionId="other-session")
        self.assertIn("ACTION: stop", self.step(*verb_arguments))
        self.hook(
            "coder",
            "docs/plans/orders/spec.md:3: Add orders.",
            session="other-session" if other_session else self.SESSION,
        )
        (self.repo / self.CRITERIA).write_text("AC-1 rewritten after the stop\n")
        out = self.step("after-plan-edit")
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        self.assertEqual(self.SESSION, self.state()["sessionId"])
        copy_path = self.replaced_copies()[0]
        self.assertEqual("AC-1 rewritten after the stop\n", copy_path.read_text())

    def test_a_tick_stop_then_after_plan_edit_restores_a_late_coder_write(self):
        self.check_the_stop_leads_through_after_plan_edit_to_a_restore(["tick", "1"], False)

    def test_a_start_stop_then_after_plan_edit_restores_a_late_coder_write(self):
        self.check_the_stop_leads_through_after_plan_edit_to_a_restore(["start", "--restart"], False)

    def test_after_plan_edit_before_the_coder_reports_waits_and_restores_a_later_criteria_write(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.wait_env(1, "0.2")
        early = self.step("after-plan-edit")
        self.assertIn("ACTION: wait", early)
        self.assertIn(f"`{self.own_command('resume')}`", early)
        self.assertNotIn("AGENT:", early)
        self.assertEqual("plan-coder", self.state()["stage"])
        self.assertIn("criteriaGuard", self.state())
        (self.repo / self.CRITERIA).write_text("AC-1 signed by the coder\n")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        out = self.step("after-plan-edit")
        self.assertEqual("AC-1 orders exist\n", self.criteria_text())
        self.assertNotIn("criteriaGuard", self.state())
        self.assertIn("AGENT: review-loop", out)

    def test_copies_made_in_the_same_second_get_a_counter_and_overwrite_nothing(self):
        folder = self.repo / ".git/code-step-replaced-criteria"
        folder.mkdir()
        now = datetime.datetime.now(datetime.UTC)
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
        self.step("start", "--restart")
        for name, text in existing.items():
            self.assertEqual(text, (folder / name).read_text())
        new_copies = [path for path in self.replaced_copies() if path.name not in existing]
        self.assertEqual(["AC-1 the new change\n"], [path.read_text() for path in new_copies])

    def test_start_after_the_plan_folder_moved_drops_the_saved_criteria_and_does_not_crash(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        self.hook("coder", "docs/plans/orders/spec.md:3: Add orders.")
        shutil.move(self.repo / "docs/plans/orders", self.repo / "docs/plans/orders-v2")
        for _attempt in range(2):
            out = self.step("start", "--restart", "docs/plans/orders-v2/spec.md")
            self.assertNotIn("Traceback", out)
            self.assertIn("ACTION:", out)
            self.assertNotIn("criteriaGuard", self.state())
        self.assertEqual("AC-1 orders exist\n", (self.repo / "docs/plans/orders-v2/acceptance-criteria.md").read_text())

    def test_start_restores_the_criteria_the_coder_edited_during_a_session_plan_edit(self):
        self.check_start_restores_the_criteria(["start", "--restart"])

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
        self.step("start", "--restart", "docs/plans/nope.md")
        self.assertIn("belong to a plan edit on another branch", self.said())
        self.assertNotIn("criteriaGuard", self.state())
        out = self.step("start", "--restart", "docs/plans/b/plan.md")
        self.assertNotIn("Traceback", out)
        self.assertIn("ACTION:", out, out)
        self.assertFalse((self.repo / self.CRITERIA).exists())
        self.assertNotIn("criteriaGuard", self.state(), out)

    def test_session_adopt_headline_does_not_say_the_user_adopted_or_rewrite_the_criteria(self):
        self.coder_round(self.IMPACT_REPORT)
        out = self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        outside_the_prompt = out.split("-----BEGIN PROMPT-----")[0]
        self.assertNotIn("The user adopted", outside_the_prompt)
        self.assertNotIn("acceptance criteria it contradicts", outside_the_prompt)
        self.assertIn("The plan change was adopted by the session, not the user. Dispatch a coder to rewrite the plan "
                      "steps it contradicts. The acceptance criteria do not change.", outside_the_prompt)

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
        outside_the_prompt = out.split("-----BEGIN PROMPT-----")[0]
        self.assertNotIn("The user adopted", outside_the_prompt)
        self.assertNotIn("acceptance criteria it contradicts", outside_the_prompt)
        self.assertIn("The plan change was adopted by the pre-set decision. Dispatch a coder to rewrite the plan "
                      "steps it contradicts. The acceptance criteria do not change.", outside_the_prompt)
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

    PLAN_IMPACT_WITH_LEFTOVERS = (
        "status: plan-impact\niter: 1\nplan_impact: |\n    PLAN-IMPACT:\n      found: B\n"
        "pending_fix_findings_not_dispatched: three test gaps need a coder once the plan-impact is settled\n"
        'ask: [{"finding": "second", "file_line": "backend/src/orders.ts:2", "question": "second ask?", '
        '"change": "c", "gate": "code-reviewer", "class": "correctness", "finding_id": "0123456789abcdef"}]')

    def test_a_plan_impact_round_s_other_asks_and_pending_findings_reach_the_question_and_the_next_review(self):
        self.coder_round()
        self.hook("review-loop", self.PLAN_IMPACT_WITH_LEFTOVERS)
        self.step("after-review")
        question = self.said()
        self.assertIn("ask: second - second ask?", question)
        self.assertIn("three test gaps need a coder", question)
        out = self.step("decide", "keep", "--by", "user", "--ruling", "keep it")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("carried-findings:", out)
        self.assertIn("ask: second - second ask?", out)
        self.assertIn("three test gaps need a coder", out)
        self.assertNotIn("carriedFindings", self.state())

    def test_phase_one_converged_stops_with_block_b_and_marks_done(self):
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: stop-block-B", out)
        self.assert_marked_clean(out)
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
        bad_line = self.break_manual_section()
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertEqual("plan-format", self.state()["stopReason"])
        self.assertIn(f"{self.plan}:{bad_line}:", out)
        self.assertIn("code_step.py verify", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())
        (self.repo / self.plan).write_text(
            self.plan_text().replace(self.FENCED_MANUAL_ITEM, "- [ ] **Manual-verified** (agent-verified): hit /orders")
        )
        out = self.step("verify")
        self.assertIn("ACTION: stop-block-B", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_start_stops_on_a_manual_verification_section_that_does_not_parse(self):
        bad_line = self.break_manual_section()
        out = self.start_phase_one()
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn(f"{self.plan}:{bad_line}:", out)

    def test_plan_check_reports_a_manual_verification_section_that_does_not_parse(self):
        bad_line = self.break_manual_section()
        result = run(self.repo, self.env, "plan", "check", self.plan)
        self.assertEqual(1, result.returncode)
        self.assertIn(f"{self.plan}:{bad_line}:", result.stdout)

    def test_a_converged_packet_with_a_labelled_ask_list_asks_the_user(self):
        self.coder_round()
        asks = "\n".join(f'  - {{question: "q{n}", change: "c{n}", file_line: "backend/src/orders.ts:{n}", '
                         'gate: code-reviewer}}' for n in (1, 2, 3))
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
        self.hook(
            "review-loop", "status: cap-reached\niter: 2\nfindings_remaining:\n  - finding: x\n    file_line: a.ts:1"
        )
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("- [ ] Phase 1:", self.plan_text())

    def test_the_question_for_the_user_names_each_asks_proposed_change_and_what_each_answer_does(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)

        self.step("after-review")

        self.assertIn("   Proposed change: export o as a const", self.said())
        self.assertIn("accepted (make the proposed change), rejected (leave the code as it stands)", self.said())

    def test_an_accepted_ask_sends_its_proposed_change_to_the_asks_coder(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")

        out = self.step("asks-done", "accepted")

        self.assertIn("   The proposed change: export o as a const", out)

    def logged_stop_row(self, ask_rows, agent_id="a1", blocked=False):
        row = {"kind": "stop", "ts": time.time(), "session_id": self.SESSION, "agent_id": agent_id,
               "open_dispatches": 0, "ask_rows": ask_rows, "blocked": blocked}
        store = self.tmp / "handback-store"
        store.mkdir(exist_ok=True)
        with open(store / f"{self.SESSION}.jsonl", "a", encoding="utf-8") as rows:
            rows.write(json.dumps(row) + "\n")

    def late_stop_row(self, delay, ask_rows, **row_fields):
        timer = threading.Timer(delay, self.logged_stop_row, args=(ask_rows,), kwargs=row_fields)
        self.addCleanup(timer.cancel)
        timer.start()
        return timer

    def finding_log_lines(self):
        return [line for line in self.log.read_text().splitlines() if "log-review-finding" in line]

    def test_an_ask_the_loop_logged_without_writing_its_id_gets_its_outcome_under_the_logged_id(self):
        self.coder_round()
        self.hook("review-loop", self.ASK_WITHOUT_FINDING_ID)
        self.logged_stop_row([{"file": "backend/src/orders.ts", "line": 2, "finding_id": self.LOGGED_FINDING_ID}])
        self.step("after-review")

        self.step("asks-done", "accepted")

        [outcome_line] = self.finding_log_lines()
        self.assertIn(f"finding_id={self.LOGGED_FINDING_ID}", outcome_line)
        self.assertIn("ask_outcome=accepted", outcome_line)

    def test_an_ask_the_loop_never_logged_gets_one_ask_row_and_one_outcome_under_the_same_id(self):
        self.coder_round()
        self.hook("review-loop", self.ASK_WITHOUT_FINDING_ID)
        self.step("after-review")

        self.step("asks-done", "accepted")

        ask_line, outcome_line = self.finding_log_lines()
        self.assertNotIn("ask_outcome=", ask_line)
        self.assertNotIn("finding_id=", ask_line)
        self.assertIn(f"finding_id={self.MINTED_FINDING_ID}", outcome_line)
        self.assertIn("ask_outcome=accepted", outcome_line)

    LOGGED_ASK_ROW: ClassVar[dict[str, object]] = {"file": "backend/src/orders.ts", "line": 2,
                                                   "finding_id": LOGGED_FINDING_ID}

    def test_an_ask_waits_for_the_stop_row_that_lands_after_the_hand_back_row(self):
        self.coder_round()
        self.hook("review-loop", self.ASK_WITHOUT_FINDING_ID)
        self.wait_env(10)
        self.late_stop_row(1, [self.LOGGED_ASK_ROW])
        self.step("after-review")

        self.step("asks-done", "accepted")

        [outcome_line] = self.finding_log_lines()
        self.assertIn(f"finding_id={self.LOGGED_FINDING_ID}", outcome_line)

    def test_an_ask_skips_a_stop_row_the_gate_blocked_and_takes_the_one_that_follows(self):
        self.coder_round()
        self.hook("review-loop", self.ASK_WITHOUT_FINDING_ID)
        self.wait_env(10)
        self.logged_stop_row([], blocked=True)
        self.late_stop_row(0.6, [self.LOGGED_ASK_ROW])
        self.step("after-review")

        self.step("asks-done", "accepted")

        [outcome_line] = self.finding_log_lines()
        self.assertIn(f"finding_id={self.LOGGED_FINDING_ID}", outcome_line)

    def test_an_ask_with_no_settled_stop_row_in_time_is_logged_here_and_says_so_on_stderr(self):
        self.coder_round()
        self.hook("review-loop", self.ASK_WITHOUT_FINDING_ID)
        self.wait_env(1, "0.2")
        self.logged_stop_row([], blocked=True)

        result = run(self.repo, self.env, "after-review")

        self.assertIn("no settled stop row", result.stderr)
        [ask_line] = self.finding_log_lines()
        self.assertNotIn("ask_outcome=", ask_line)

    def test_the_same_hand_back_read_twice_logs_one_ask_row(self):
        self.coder_round()
        self.hook("review-loop", self.ASK_WITHOUT_FINDING_ID)

        self.step("after-review")
        self.step("after-review")

        self.assertEqual(len(self.finding_log_lines()), 1)

    def test_a_later_hand_back_with_an_ask_at_the_same_place_gets_its_own_ask_row(self):
        self.coder_round()
        self.hook("review-loop", self.ASK_WITHOUT_FINDING_ID)
        self.step("after-review")
        self.step("asks-done", "accepted")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        self.step("after-coder")
        self.hook("review-loop", self.ASK_WITHOUT_FINDING_ID)

        self.step("after-review")

        ask_lines = [line for line in self.finding_log_lines() if "ask_outcome=" not in line]
        self.assertEqual(len(ask_lines), 2)

    def test_asks_flow_logs_outcomes(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        out = self.step("after-review")
        self.assertIn("ACTION: ask-user", out)
        self.assert_marked_clean(out)
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
        self.assert_dispatch_logged(out, "d3", "coder", "asks-coder", "resume")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: applied the ask")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("applied the ask", self.said())
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("Phase 1 marked done", out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_an_ask_fix_coder_s_behavior_stays_off_the_phase_implemented_line(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")
        self.step("asks-done", "accepted")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n")
        self.hook("coder", "BEHAVIOR: tests only, schema unchanged")
        self.step("after-coder")
        said = self.said()
        self.assertIn("Implemented: orders exist\n", said)
        self.assertIn("Ask-fix: tests only, schema unchanged", said)
        self.assertNotIn("orders exist; tests only", said)
        self.assertEqual(["orders exist"], self.state()["behavior"])
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        self.assertNotIn("tests only", self.said().split("Behavior delta")[-1])

    def test_rejected_asks_finish_the_phase_without_a_coder(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")
        out = self.step("asks-done", "rejected")
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("Phase 1 marked done", out)

    def test_review_asks_jump_through_the_set_nvim_jump_and_never_the_one_on_path(self):
        path_folder = self.tmp / "bin"
        path_folder.mkdir()
        path_jump_log = self.tmp / "path-jump.log"
        path_jump = path_folder / "nvim-jump"
        path_jump.write_text(f'#!/usr/bin/env bash\necho "$@" >> {path_jump_log}\n')
        path_jump.chmod(0o755)
        self.env["PATH"] = f"{path_folder}{os.pathsep}{self.env['PATH']}"
        self.coder_round()
        self.hook("review-loop", self.ASK)

        self.step("after-review")

        self.assertIn("--note keep? backend/src/orders.ts:2", self.jump_log.read_text())
        self.assertFalse(path_jump_log.exists())

    def asks_done_logged_text(self, *by_words):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")
        self.step("asks-done", "accepted", *by_words)
        return self.log.read_text()

    def test_asks_done_by_session_logs_the_session_as_the_one_who_ruled(self):
        self.assertIn("ask_decided_by=session", self.asks_done_logged_text("--by", "session"))

    def test_asks_done_without_by_logs_the_user_as_the_one_who_ruled(self):
        self.assertIn("ask_decided_by=user", self.asks_done_logged_text())

    def test_asks_done_with_a_bad_by_value_stops_and_logs_nothing(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")

        out = self.step("asks-done", "accepted", "--by", "robot")

        self.assertIn("--by session", out)
        self.assertFalse(self.log.exists() and "ask_outcome=" in self.log.read_text())

    def test_the_ask_prompt_names_the_by_session_path(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        self.step("after-review")

        self.assertIn("--by session", self.said())

    def test_preset_ask_outcome_logs_the_session_as_the_one_who_ruled(self):
        self.env["CODE_STEP_ASKS_OUTCOME"] = "accepted"
        self.coder_round()
        self.hook("review-loop", self.ASK)

        self.step("after-review")

        self.assertIn("ask_decided_by=session", self.log.read_text())

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
        self.assert_marked_clean(out)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_say_hook_relays_and_empties_the_file(self):
        self.coder_round()
        expected = self.said().strip()
        self.assertTrue(expected)
        result = run(
            self.repo, self.env, "say-hook", stdin=json.dumps({"cwd": str(self.repo), "hook_event_name": "Stop"})
        )
        self.assertEqual(0, result.returncode)
        self.assertEqual({"systemMessage": expected}, json.loads(result.stdout))
        self.assertEqual("", self.said())
        self.assertIn(expected, (self.repo / ".git/code-step/say.log").read_text())
        again = run(self.repo, self.env, "say-hook", stdin=json.dumps({"cwd": str(self.repo)}))
        self.assertEqual("", again.stdout)

    def test_say_hook_of_a_child_session_leaves_the_text_for_the_main_session(self):
        self.coder_round()
        expected = self.said().strip()
        child_env = {**self.env, "CLAUDE_FORMAT_HOOK_OFF": "1"}
        result = run(
            self.repo, child_env, "say-hook", stdin=json.dumps({"cwd": str(self.repo), "hook_event_name": "Stop"})
        )
        self.assertEqual(("", 0), (result.stdout, result.returncode))
        self.assertEqual(expected, self.said().strip())

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
        self.start_phase_one("--restart")
        self.assertEqual("", self.said())

    def test_say_hook_drops_text_older_than_six_hours(self):
        self.coder_round()
        say_file = self.repo / ".git/code-step/say.md"
        long_ago = time.time() - 7 * 3600
        os.utime(say_file, (long_ago, long_ago))
        result = run(self.repo, self.env, "say-hook", stdin=json.dumps({"cwd": str(self.repo)}))
        self.assertEqual("", result.stdout)
        self.assertEqual("", self.said())

    def test_hook_saves_nothing_once_the_phase_is_done(self):
        self.finish_phase_one()
        before = len(self.events_named("handback"))
        self.hook("coder", "from another session")
        self.assertEqual(before, len(self.events_named("handback")))

    def test_hook_ignores_a_session_other_than_the_one_that_started_the_coder(self):
        self.start_phase_one()
        self.hook("coder", "mine")
        self.hook("coder", "theirs", agent_id="a2", session="s2")
        handbacks = self.events_named("handback")
        self.assertEqual(1, len(handbacks))
        self.assertTrue(handbacks[0]["message"].startswith("mine"))

    def test_bare_start_on_another_branch_resolves_the_plan_again(self):
        self.finish_phase_one()
        subprocess.run(["git", "checkout", "-q", "-b", "ABC-2"], cwd=self.repo, check=True, env=self.env)
        out = self.step("start")
        self.assertNotIn("AGENT: coder", out)
        self.assertIn("ACTION: ask-user", out)
        self.assertIn("no task or plan resolves", self.said())

    SINGLE_PLAN = (
        "# Single\n\n**File**: `backend/src/orders.ts`\n\n#### Automated Verification:\n\n"
        "- [ ] **Prohibition**: no console.log - `git grep -n --untracked console.log -- backend/src/orders.ts`\n"
    )

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
            found = next((skill for pattern, skill in plan_format.CLOSING_PHASES if pattern.search(title)), None)
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
        (self.repo / self.plan).write_text(
            self.plan_text().replace(
                "Refactor pass - /refactor cleanup sweep", "Verify pass. Branch-wide deep review plus /verify-branch"
            )
        )
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
        self.assertEqual("## Phase 6: y\nb", plan_format.phase_text(lines, "6"))
        self.assertEqual("## Phase 6A: x\na", plan_format.phase_text(lines, "6A"))

    def test_phase_status_line_formats_a_real_plan_can_use(self):
        lines = ["## Phase Status", "",
                 "- [ ] Phase 6C2: Deep id (risk: low).",
                 "- [X] Phase 7 — capital X and em dash (risk: high)",
                 "- [ ] Phase 8. Period after number (risk: Low)",
                 "-  [ ]  Phase  9:  Extra spaces (risk: low)",
                 "* [ ] Phase 10 – En dash and star bullet",
                 "- [ ] Phase 11: No risk tag"]
        entries = plan_format.parse_plan_with_closing_phases(lines)["entries"]
        self.assertEqual(["6C2", "7", "8", "9", "10", "11"], [e["number"] for e in entries])
        self.assertEqual(["low", "high", "low", "low", "high", "high"], [e["risk"] for e in entries])
        self.assertEqual([False, True, False, False, False, False], [e["done"] for e in entries])

    def test_logged_phase_id_shapes_parse_look_up_and_mark_done(self):
        ids = ["10.5", "8.6b", "4.6", "7.5", "8.6", "P4", "P9", "1-2", "6A-6D", "P9-slice-1"]
        status_lines = [f"- [ ] Phase {i}: Title {i} (risk: low)" for i in ids]
        sections = [f"## Phase {i}: Title {i}\nbody {i}" for i in ids]
        plan_path = self.repo / "ids.md"
        plan_path.write_text("\n".join(["## Phase Status", "", *status_lines, "", *sections, ""]))
        plan_lines = plan_path.read_text().splitlines()
        self.assertEqual(ids, [e["number"] for e in plan_format.parse_plan_with_closing_phases(plan_lines)["entries"]])
        for i in ids:
            self.assertEqual(f"## Phase {i}: Title {i}\nbody {i}", plan_format.phase_text(plan_lines, i))
            plan_format.mark_phase_done(plan_path, i)
        self.assertEqual([True] * len(ids), [e["done"] for e in plan_format.parse_plan_with_closing_phases(
            plan_path.read_text().splitlines())["entries"]])

    def test_dotted_phase_section_is_not_the_whole_number_section(self):
        lines = ["## Phase 10.5: x", "a", "## Phase 10: y", "b"]
        self.assertEqual("## Phase 10: y\nb", plan_format.phase_text(lines, "10"))

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
        plan_path = self.repo / "check.md"
        plan_path.write_text(text)
        return run(self.repo, self.env, "plan", "check", str(plan_path))

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
        plan_path = self.repo / "check.md"
        plan_path.write_text("## Phase Status\n\n- [x] Phase P9-slice-1: A (risk: low)\n\n## Phase P9-slice-1: A\n")
        parsed = json.loads(run(self.repo, self.env, "plan", "parse", str(plan_path), "--json").stdout)
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
        ok_line = "- [ ] **Manual-verified** (agent-verified): hit /orders"
        (self.repo / self.plan).write_text(self.plan_text().replace(ok_line, ok_line + "\n> a quoted line"))
        bad_line_number = self.plan_text().splitlines().index("> a quoted line") + 1
        self.assertEqual("coder", self.state()["stage"])
        event = {"cwd": str(self.repo), "tool_input": {"file_path": str(self.repo / self.plan)}}
        result = run(self.repo, self.env, "plan-hook", stdin=json.dumps(event))
        self.assertEqual(2, result.returncode)
        self.assertIn(f"spec.md:{bad_line_number}:", result.stderr)

    def test_manual_items_are_listed_as_verified_not_yet_run_and_human_only(self):
        ok_line = "- [ ] **Manual-verified** (agent-verified): hit /orders"
        (self.repo / self.plan).write_text(self.plan_text().replace(
            ok_line, ok_line + "\n- [x] ticked by the coder\n- [ ] run the export\n- [ ] human-only: judge the layout"
            "\n- [x] human-only: ticked layout"))
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        said = self.said()
        verified_list = said.split("Verified (checked, or marked agent-verified in the plan):")[1].split("Agent-run")[0]
        self.assertIn("hit /orders", verified_list)
        self.assertIn("ticked by the coder", verified_list)
        self.assertNotIn("run the export", verified_list)
        self.assertIn("ticked layout", verified_list)
        self.assertNotIn("ticked layout", said.split("Human-only verification remaining:")[1])
        self.assertIn("Verified (checked, or marked agent-verified in the plan):", said)
        self.assertIn("Agent-run, not yet run (/verify-branch runs these at the end of the branch):", said)
        self.assertIn("Human-only verification remaining:", said)
        not_run_list = said.split("not yet run (/verify-branch runs these at the end of the branch):")[1]
        self.assertIn("run the export", not_run_list.split("Human-only verification remaining:")[0])
        self.assertNotIn("run the export", said.split("Agent-run, not yet run")[0])
        self.assertNotIn("evidence in the plan", said)

    def phase_one_next_step_after(self, manual_line):
        ok_line = "- [ ] **Manual-verified** (agent-verified): hit /orders"
        (self.repo / self.plan).write_text(self.plan_text().replace(ok_line, manual_line))
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        return next(line for line in self.said().splitlines() if line.startswith("  1. "))

    def test_the_next_step_names_only_the_kinds_of_manual_item_the_phase_has(self):
        checked_only = self.phase_one_next_step_after("- [x] human-only: ticked layout")
        self.assertIn("spot-check the verified items", checked_only)
        self.assertNotIn("run the human-only items", checked_only)

    def test_the_next_step_for_an_unticked_human_only_item_does_not_ask_for_a_spot_check(self):
        human_only = self.phase_one_next_step_after("- [ ] human-only: judge the layout")
        self.assertIn("run the human-only items", human_only)
        self.assertNotIn("spot-check", human_only)

    def test_an_ask_that_repeats_one_text_in_finding_and_question_shows_it_once(self):
        self.coder_round()
        self.hook("review-loop", 'status: converged\niter: 1\nfixed: []\nask: [{"finding": "Is the cap right?", '
                  '"change": "cap at 3", "file_line": "backend/src/orders.ts:2", "gate": "code-reviewer", '
                  '"class": "correctness"}]')
        out = self.step("after-review")
        self.assertIn("Is the cap right?", out + self.said())
        self.assertNotIn("Is the cap right? - Is the cap right?", out + self.said())

    def test_an_ask_with_a_finding_and_a_different_question_shows_both(self):
        self.coder_round()
        self.hook("review-loop", self.ASK)
        out = self.step("after-review")
        self.assertIn("f - keep?", out + self.said())

    def hand_back_an_unreadable_packet(self, agent_id="a1"):
        # The packet hook denies an unreadable packet the first time its agent hands it back; the second goes through.
        packet = "status: deferred\niter: 1\nfindings_remaining: []"
        self.hook("review-loop", packet, agent_id=agent_id)
        denied_handbacks = [event for event in self.events_named("handback") if event["agent_id"] == agent_id
                            and event["agent_type"] == "review-loop" and event["message"] == packet]
        self.assertEqual([], denied_handbacks)
        self.hook("review-loop", packet, agent_id=agent_id)

    def leave_unreadable_packet(self):
        self.coder_round()
        self.hand_back_an_unreadable_packet()
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
        self.hook("review-loop", self.LOOP_OK, agent_id="a2")
        self.assertIn("ACTION: stop-block-B", self.step("after-review"))

    def test_review_again_after_a_failed_first_review_runs_the_structure_pass(self):
        first = self.leave_unreadable_packet()
        self.assertNotIn(self.SKIP_LINE, first)
        self.assertNotIn(self.SKIP_LINE, self.step("review-again"))

    def test_review_again_after_a_failed_re_review_keeps_the_structure_pass_skip(self):
        out = self.asks_follow_up(lambda: (self.repo / "backend/src/orders.ts").write_text("export const o = 2\n"))
        self.assertIn(self.SKIP_LINE, out)
        self.hand_back_an_unreadable_packet(agent_id="a2")
        self.assertIn("review-again", self.step("after-review"))
        self.assertEqual("invalid-packet", self.state()["stopReason"])
        again = self.step("review-again")
        self.assertIn("AGENT: review-loop", again)
        self.assertIn(self.SKIP_LINE, again)

    def test_review_again_with_no_unreadable_packet_pending_stops(self):
        self.start_phase_one()
        out = self.step("review-again")
        self.assertIn("Refused: ", out)
        self.assertIn("ACTION: rerun", out)
        self.assertIn(f"COMMAND: {self.own_command('resume')}", out)
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

    CLOSING_CRITERIA = (
        "\nSweep.\n\n### Success Criteria\n\n#### Automated Verification\n\n"
        "- [ ] Quality checks green\n"
        "- [ ] Concentration gate evaluated; both counts stated\n"
        "  and the module named\n"
        "- [ ] **CI-verified**: the pipeline is green\n"
        "- [x] Already checked\n\n"
        "#### Manual Verification\n\n"
        "- [ ] Look at the page\n\n"
    )

    def refactor_status_line(self, text):
        return next(line for line in text.splitlines() if "Refactor pass - /refactor cleanup sweep" in line)

    def start_closing_phase_with_criteria(self, criteria=None):
        self.mark_phases_done(1, 2, 3)
        text = self.plan_text().replace("\nSweep.\n\n", criteria or self.CLOSING_CRITERIA, 1)
        (self.repo / self.plan).write_text(text)
        return self.step("start", self.plan)

    def test_skill_done_pass_without_evidence_stops_and_changes_nothing(self):
        self.start_closing_phase_with_criteria()
        plan_before = self.plan_text()
        state_before = self.state()

        out = self.step("skill-done", "pass")

        self.assertIn("ACTION: stop", out)
        self.assertIn("1. Quality checks green", out)
        self.assertIn("2. Concentration gate evaluated; both counts stated and the module named", out)
        self.assertNotIn("3.", out)
        self.assertIn('skill-done pass --evidence "<item 1 evidence>" --evidence "<item 2 evidence>"', out)
        self.assertEqual(plan_before, self.plan_text())
        self.assertEqual(state_before, self.state())

    def test_skill_done_pass_with_a_wrong_evidence_count_changes_nothing(self):
        self.start_closing_phase_with_criteria()
        plan_before = self.plan_text()

        out = self.step("skill-done", "pass", "--evidence", "only one")

        self.assertIn("ACTION: stop", out)
        self.assertEqual(plan_before, self.plan_text())

    def test_skill_done_pass_writes_each_evidence_under_its_box(self):
        self.start_closing_phase_with_criteria()

        self.step("skill-done", "pass", "--evidence", "ruff and pytest green",
                  "--evidence", "largest module 120 added lines; branch 340")

        text = self.plan_text()
        self.assertIn("- [x] Quality checks green\n  - Done: ruff and pytest green\n"
                      "- [x] Concentration gate evaluated; both counts stated\n  and the module named\n"
                      "  - Done: largest module 120 added lines; branch 340\n", text)
        self.assertTrue(self.refactor_status_line(text).startswith("- [x]"))

    def test_skill_done_pass_leaves_manual_and_ci_verified_items_alone(self):
        self.start_closing_phase_with_criteria()

        self.step("skill-done", "pass", "--evidence", "a", "--evidence", "b")

        text = self.plan_text()
        self.assertIn("- [ ] **CI-verified**: the pipeline is green\n", text)
        self.assertIn("- [ ] Look at the page\n", text)
        self.assertEqual(2, text.count("  - Done:"))

    def test_skill_done_pass_with_no_open_items_needs_no_evidence(self):
        self.start_closing_phase_with_criteria("\nSweep.\n\n### Success Criteria\n\n- [x] Done already\n\n")

        self.step("skill-done", "pass")

        self.assertTrue(self.refactor_status_line(self.plan_text()).startswith("- [x]"))

    def test_closing_phase_prompt_names_the_open_items_and_the_command(self):
        out = self.start_closing_phase_with_criteria()

        self.assertIn("ACTION: invoke-skill", out)
        self.assertIn("1. Quality checks green", out)
        self.assertIn("2. Concentration gate evaluated; both counts stated and the module named", out)
        self.assertIn('skill-done pass --evidence "<item 1 evidence>" --evidence "<item 2 evidence>"', out)

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
        out = self.step("start", "--restart")
        self.assertNotIn("MODEL: haiku", out)
        self.assertIn("AGENT: coder", out)

    def test_auto_advance_resumes_with_the_modifier_the_run_started_with(self):
        self.finish_phase_one()
        self.step("start", "+fast")
        (self.repo / "backend/src/totals.ts").write_text("export const t = 1\n")
        self.hook("coder", "BEHAVIOR: totals")
        self.step("after-coder")
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: auto-advance", out)
        self.assertIn("code_step.py resume", out)
        self.assertIn("+fast", self.state().get("modifier") or "")
        self.commit_all()
        self.assertIn("MODEL: haiku", self.step("resume"))

    def test_ticket_id_and_directory_arguments_resolve_the_plan(self):
        shutil.copytree(self.repo / "docs/plans/orders", self.repo / "docs/plans/ABC-400-x")
        out = self.step("start", "ABC-400")
        self.assertIn("Implement Phase 1 of `docs/plans/ABC-400-x/spec.md`", out)
        out = self.step("start", "--restart", "docs/plans/orders")
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

    LONG_TASK_TEXT = "\n\n".join(
        ["Show the owner name and the due date on each row of the list view, and sort the rows by due date. " * 4] * 3)

    @unittest.skipUnless(toolkit_paths.PRE_314_PYTHON, "needs a Python older than 3.14")
    def test_long_task_text_reaches_the_coder_whole(self):
        for args in (["start", self.LONG_TASK_TEXT], ["start", "+fast", self.LONG_TASK_TEXT],
                     ["start", "--task", self.LONG_TASK_TEXT]):
            with self.subTest(args=args[:-1]):
                shutil.rmtree(self.repo / ".git/code-step", ignore_errors=True)

                completed = run(self.repo, self.env, *args, interpreter=toolkit_paths.PRE_314_PYTHON)

                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertIn(f"Implement: {self.LONG_TASK_TEXT}", completed.stdout)

    def test_a_positional_argument_with_whitespace_that_starts_with_a_real_plan_folder_is_task_text(self):
        text = "docs/plans/orders needs its parity table updated"
        out = self.step("start", text)
        self.assertIn(f"Implement: {text}", out)
        self.assertNotIn("Phase 1 of", out)

    def test_a_positional_argument_that_starts_with_a_real_plan_file_and_holds_text_is_refused_with_both_commands(self):
        out = self.step("start", f"{self.plan} fix the typo")
        self.assertIn("Refused: ", out)
        self.assertIn("ACTION: stop", out)
        self.assertIn(self.own_command(f"start {self.plan}"), out)
        self.assertIn(self.own_command("start --task 'fix the typo'"), out)
        self.assertNotIn("AGENT:", out)

    def test_a_positional_argument_with_whitespace_that_is_a_real_plan_file_is_a_plan_path(self):
        spaced_plan = "docs/plans/orders/spec copy.md"
        (self.repo / spaced_plan).write_text(self.plan_text())
        out = self.step("start", spaced_plan)
        self.assertIn(f"Implement Phase 1 of `{spaced_plan}`", out)
        self.assertNotIn(f"Implement: {spaced_plan}", out)

    def test_a_positional_argument_with_whitespace_that_is_not_a_file_is_task_text(self):
        not_a_file = "docs/plans/orders/spec copy.md"
        out = self.step("start", not_a_file)
        self.assertIn(f"Implement: {not_a_file}", out)
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
        events_file = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        with events_file.open("a") as events_stream:
            events_stream.write('{"event": "hand\n')
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

    def test_plan_impact_survives_a_retry_that_sends_only_the_fix(self):
        self.begin_coder()
        self.gate_commands = ["echo lint broke; exit 1"]
        self.hook("coder", "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes")
        self.assertEqual([], self.events_named("handback"))
        self.assertEqual(1, len(self.events_named("handback-attempt")))
        self.gate_commands = ["true"]
        self.hook("coder", "fixed the lint error")
        self.assertIn("ACTION: ask-user", self.step("after-coder"))

    def test_iter_with_a_budget_suffix_reads_the_first_number(self):
        self.coder_round()
        self.hook("review-loop", "status: converged\niter: 2 of 2\nfixed: []\nask: []")
        self.step("after-review")
        self.assertEqual(2, self.state()["iter"])

    def test_plan_impact_status_with_no_description_stops(self):
        self.coder_round()
        packet = "status: plan-impact\niter: 1\nplan_impact:\n"
        self.hook("review-loop", packet)
        self.hook("review-loop", packet)
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
            self.assertIsNone(code_step_boundary.WHOLE_SUITE.match(command), command)
        for command in ("cd backend && npm test", "npm run lint", "npx vitest run", "pytest", "ruff check"):
            self.assertIsNotNone(code_step_boundary.WHOLE_SUITE.match(command), command)
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

    def test_a_grep_ban_with_no_match_holds(self):
        self.set_verification("- [ ] **Prohibition**: no console.log - `grep -n console.log backend/src/orders.ts`")
        outcome = self.finish_phase_one()
        self.assertNotIn("Automated Verification failed", outcome)

    def test_an_rg_ban_with_no_match_holds(self):
        self.set_verification("- [ ] **Prohibition**: no console.log - `rg -n console.log backend/src/orders.ts`")
        outcome = self.finish_phase_one()
        self.assertNotIn("Automated Verification failed", outcome)

    def test_an_rg_presence_check_passes_on_a_hit(self):
        self.set_verification("- [ ] **Presence**: the export exists - `rg -q 'export const o' backend/src/orders.ts`")
        outcome = self.finish_phase_one()
        self.assertNotIn("Automated Verification failed", outcome)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_an_rg_line_with_no_wording_is_a_ban_and_fails_on_a_hit(self):
        self.set_verification("- [ ] **Rename**: the old name is gone - `rg -n 'export const o' backend/src/orders.ts`")
        outcome = self.finish_phase_one()
        self.assertIn("Automated Verification failed", outcome)
        self.assertIn("unless its text says it checks presence", outcome)

    def test_a_negated_rg_ban_runs_and_holds_on_no_match(self):
        self.set_verification("- [ ] **Prohibition**: no console.log - `! rg -n console.log backend/src/orders.ts`")
        outcome = self.finish_phase_one()
        self.assertNotIn("cannot run", outcome)
        self.assertNotIn("Automated Verification failed", outcome)

    def test_a_negated_rg_ban_passes_plan_check(self):
        self.set_verification("- [ ] **Prohibition**: no console.log - `! rg -n console.log backend/src/orders.ts`")
        result = subprocess.run([sys.executable, str(SCRIPT), "plan", "check", self.plan],
                                cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_cd_then_rg_line_that_prints_nothing_passes_verify(self):
        self.set_verification("- [ ] the migration is purely additive. "
                              "`cd backend && rg -n 'ALTER COLUMN|DROP ' src/orders.ts` prints nothing.")
        outcome = self.finish_phase_one()
        self.assertNotIn("Automated Verification failed", outcome)
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_a_cd_then_rg_line_that_prints_nothing_fails_on_a_hit(self):
        self.set_verification("- [ ] the migration is purely additive. "
                              "`cd backend && rg -n 'DROP ' src/orders.ts` prints nothing.")
        self.coder_round(source="DROP TABLE o\n")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("after-review"))

    def test_a_cd_then_negated_rg_is_a_ban(self):
        line = "- [ ] **Check**: `cd backend && ! rg -n x src/orders.ts`"
        command = code_step_boundary.verification_command(line)
        self.assertEqual(command, "cd backend && rg -n x src/orders.ts")
        self.assertTrue(code_step_boundary.is_search_ban(command, line + " exists"))

    def test_an_rg_ban_with_a_match_fails(self):
        self.set_verification("- [ ] **Prohibition**: no console.log - `rg -n console.log backend/src/orders.ts`")
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("after-review"))

    def test_a_grep_ban_with_a_match_fails(self):
        self.set_verification("- [ ] **Prohibition**: no console.log - `grep -n console.log backend/src/orders.ts`")
        self.coder_round(source="console.log(1)\n")
        self.hook("review-loop", self.LOOP_OK)
        self.assertIn("Automated Verification failed", self.step("after-review"))

    def test_prohibition_pipe_form_is_judged_by_its_output(self):
        self.set_verification(
            "- [ ] **Prohibition**: none - `git grep -n console.log -- backend/src/orders.ts | wc -l`"
        )
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

    def asks_follow_up(self, write_files):
        self.apply_first_ask()
        write_files()
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
        self.assertIn("- [x] Phase 1:", self.plan_text())

    def test_asks_coder_that_changed_only_docs_sends_no_review_and_finishes_the_phase(self):
        self.apply_first_ask()
        (self.repo / "backend/README.md").write_text("orders\n")
        self.hook("coder", "BEHAVIOR: documented the ask")
        out = self.step("after-coder")
        self.assertNotIn("AGENT: review-loop", out)
        self.assertIn("Phase 1 marked done", out)
        self.assert_marked_clean(out)
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
        self.assert_marked_clean(out)
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
        second_ask = ('{"finding": "g", "file_line": "backend/src/orders.ts:3", "question": "rename?", '
                      '"change": "rename o to orderCount", "gate": "code-reviewer", "class": "correctness", '
                      '"finding_id": "fedcba9876543210"}')
        two_asks = self.ASK.replace("}]", "}, " + second_ask + "]")
        self.coder_round()
        self.hook("review-loop", two_asks.replace("iter: 1", "iter: 2"))
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
                         code_step_report.coder_flags("The plan is ambiguous about rounding."))
        self.assertEqual(["Two ambiguities remain."], code_step_report.coder_flags("Two ambiguities remain."))
        self.assertEqual([], code_step_report.coder_flags("The spec was unambiguous."))
        self.assertEqual([], code_step_report.coder_flags("No ambiguities found."))

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
        lines = [
            "# T",
            "## Phase Status",
            "- [ ] Phase 1: A",
            "- [ ] Phase 2: B",
            "## Phase 1: A",
            "```bash",
            "# install",
            "npm i",
            "```",
            "more text",
            "## Phase 2: B",
            "",
        ]
        plan = plan_format.parse_plan_with_closing_phases(lines)
        self.assertEqual((4, 10), (plan["sections"]["1"]["start"], plan["sections"]["1"]["end"]))
        self.assertIn("# install", plan_format.phase_text(lines, "1"))
        self.assertIn("more text", plan_format.phase_text(lines, "1"))

    def test_a_tilde_fence_and_an_indented_fence_hide_headings_too(self):
        lines = [
            "## Phase Status",
            "- [ ] Phase 1: A",
            "## Phase 1: A",
            "~~~",
            "## Not a section",
            "~~~",
            "  - step",
            "    ```sh",
            "    # comment",
            "    ```",
            "tail",
            "",
        ]
        plan = plan_format.parse_plan_with_closing_phases(lines)
        self.assertEqual(len(lines), plan["sections"]["1"]["end"])
        self.assertEqual([], plan["failures"])

    def test_phase_headings_and_status_lines_inside_a_fence_are_not_sections_or_entries(self):
        lines = [
            "# T",
            "## Phase Status",
            "- [ ] Phase 1: A",
            "```",
            "## Phase 9: fake",
            "- [ ] Phase 8: fake",
            "```",
            "## Phase 1: A",
            "",
        ]
        plan = plan_format.parse_plan_with_closing_phases(lines)
        self.assertEqual(["1"], list(plan["sections"]))
        self.assertEqual(["1"], [entry["number"] for entry in plan["entries"]])
        self.assertEqual([], plan["failures"])

    def test_two_sections_with_the_same_phase_id_are_a_duplicate_id_failure(self):
        lines = ["# T", "## Phase Status", "- [ ] Phase 1: A", "## Phase 1: A", "x", "## Phase 1: A again", ""]
        failures = plan_format.parse_plan_with_closing_phases(lines)["failures"]
        self.assertEqual([(6, "duplicate-id")], [(f["line"], f["kind"]) for f in failures])
        self.assertIn("line 4", failures[0]["detail"])
        result = self.plan_check("\n".join(lines))
        self.assertEqual(1, result.returncode)
        self.assertIn(":6: duplicate-id", result.stdout)

    # ---------- the addendum coder fires only on added lines ----------

    # ---------- plan-hook ignores malformed input ----------

    def test_plan_hook_exits_zero_and_silent_on_every_malformed_input(self):
        self.start_phase_one()
        cases = [
            "[1]",
            "null",
            "7",
            '"text"',
            "not json",
            "",
            "{}",
            json.dumps({"cwd": str(self.repo), "tool_input": []}),
            json.dumps({"cwd": str(self.repo), "tool_input": "x"}),
            json.dumps({"cwd": str(self.repo), "tool_input": {"file_path": 5}}),
            json.dumps({"cwd": 5, "tool_input": {"file_path": "a"}}),
        ]
        for stdin in cases:
            with self.subTest(stdin=stdin):
                result = run(self.repo, self.env, "plan-hook", stdin=stdin)
                self.assertEqual((0, "", ""), (result.returncode, result.stdout, result.stderr))

    # ---------- start flags ----------

    def test_start_help_prints_usage_and_writes_no_state(self):
        result = run(self.repo, self.env, "start", "--help")
        self.assertEqual(0, result.returncode)
        self.assertIn("usage: code_step.py start", result.stdout)
        self.assertNotIn("ACTION: dispatch", result.stdout)
        self.assertFalse((self.repo / ".git/code-step").exists())

    def test_start_with_an_unknown_flag_exits_two_with_usage_and_writes_no_state(self):
        result = run(self.repo, self.env, "start", self.plan, "--bogus")
        self.assertEqual(2, result.returncode)
        self.assertIn("usage: code_step.py start", result.stderr)
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
        self.assertIn("usage: code_step.py start", result.stderr)

    def test_start_task_text_after_the_task_flag_may_hold_dashes(self):
        out = self.step("start", "--task", "fix the --verbose flag")
        self.assertIn("AGENT: coder", out)
        self.assertIn("fix the --verbose flag", out)

    # ---------- blocking wait for the hand-back row ----------

    def own_command(self, verb):
        # Printed commands name the running script by its real path.
        return f"python3 {SCRIPT.resolve()} {verb}"

    def wait_env(self, seconds, interval="0.1", waits=60):
        # The cap is `waits` waits from the dispatch. The default keeps a slow setup under suite load from reaching it;
        # a test of the stop at the cap passes waits=3, the script's own multiple.
        self.env.update(CODE_STEP_WAIT_SECONDS=str(seconds), CODE_STEP_POLL_SECONDS=interval,
                        CODE_STEP_WAIT_MULTIPLE=str(waits))

    def late_hook(self, delay, agent_type, message):
        timer = threading.Timer(delay, self.hook, args=(agent_type, message))
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
        self.assertIn(f"run the same command again: `{self.own_command('resume')}`", out)
        self.assertNotIn("AGENT:", out)
        self.assertEqual("coder", self.state()["stage"])
        self.hook("coder", self.CODER_REPORT)
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

    def test_a_coder_row_from_before_the_dispatch_does_not_end_the_wait(self):
        self.begin_coder()
        self.hook("coder", self.CODER_REPORT)
        time.sleep(0.05)
        self.start_phase_one("--restart")
        self.wait_env(1, "0.2")
        self.assertIn("ACTION: wait", self.step("after-coder"))

    def test_after_review_waits_for_a_review_loop_row_newer_than_the_review_dispatch(self):
        self.coder_round()
        self.wait_env(1, "0.2")
        out = self.step("after-review")
        self.assertIn("ACTION: wait", out)
        self.assertIn(f"`{self.own_command('resume')}`", out)
        self.wait_env(20)
        self.late_hook(1, "review-loop", self.LOOP_OK)
        self.assertIn("ACTION: stop-block-B", self.step("after-review"))

    def test_a_zero_wait_limit_skips_the_wait_and_reports_the_missing_row(self):
        self.begin_coder()
        out = self.step("after-coder")
        self.assertIn("No coder report was saved", out)

    # ---------- the fork's own hand-back ----------

    def fork_handback(self, session=SESSION, agent_type=code_step_core.FORK_AGENT_TYPE):
        return self.hook(agent_type, "waiting", agent_id="fork", session=session)

    def test_a_general_purpose_handback_while_the_coder_is_out_is_not_the_forks(self):
        self.start_phase_one()
        self.assertEqual("", self.fork_handback(agent_type="general-purpose").stdout)

    def test_fork_handback_while_the_coder_is_out_is_denied_once_naming_the_wait_command(self):
        self.start_phase_one()
        first = json.loads(self.fork_handback().stdout)["hookSpecificOutput"]
        self.assertEqual("deny", first["permissionDecision"])
        self.assertIn(self.own_command("resume"), first["permissionDecisionReason"])
        self.assertEqual("", self.fork_handback().stdout)

    def test_fork_handback_names_after_plan_edit_while_the_plan_edit_coder_is_out(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        reason = json.loads(self.fork_handback().stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn(self.own_command("resume"), reason)

    def test_fork_handback_names_after_review_while_the_review_loop_is_out(self):
        self.coder_round()
        reason = json.loads(self.fork_handback().stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn(self.own_command("resume"), reason)

    def test_a_new_dispatch_arms_the_fork_denial_again(self):
        self.start_phase_one()
        self.fork_handback()
        self.assertEqual("", self.fork_handback().stdout)
        self.start_phase_one("--restart")
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
        self.assert_marked_clean(out, "sess-1")
        self.assertEqual({"sess-1", "sess-1.reviewed"},
                         {p.name for p in (self.home / ".claude/state/review-gate").iterdir()})
        reviewed = json.loads((self.home / ".claude/state/review-gate/sess-1.reviewed").read_text())
        self.assertEqual([str(self.repo.resolve())], [str(pathlib.Path(top).resolve()) for top in reviewed])

    def test_a_failed_verification_still_marks_the_gate_clean_and_prints_no_mark_command(self):
        self.set_verification('- [ ] **Check**: fails - `bash -c "exit 1"`')
        out = self.finish_phase_one()
        self.assertIn("Automated Verification failed", out)
        self.assert_marked_clean(out)

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
        self.assertEqual(
            [
                "git add -- backend/src/orders.ts docs/plans/orders/spec.md && git commit -m 'orders exist' -- "
                "backend/src/orders.ts docs/plans/orders/spec.md"
            ],
            self.commit_lines(),
        )

    def test_the_commit_command_leaves_out_files_that_were_dirty_before_the_phase_and_untouched_by_it(self):
        (self.repo / "backend/src/existing.ts").write_text("export const a = 2\n")
        self.finish_phase_one()
        self.assertEqual(1, len(self.commit_lines()))
        self.assertNotIn("existing.ts", self.commit_lines()[0])
        self.assertIn("Dirty before the phase and left out of the commit: backend/src/existing.ts", self.said())
        self.assertNotIn("Edited by this phase", self.said())

    def test_the_commit_command_includes_a_file_that_was_dirty_before_the_phase_and_edited_by_it(self):
        (self.repo / "backend/src/existing.ts").write_text("export const a = 2\n")
        self.coder_round()
        (self.repo / "backend/src/existing.ts").write_text("export const a = 3\n")
        self.hook("review-loop", self.LOOP_OK)
        self.step("after-review")
        self.assertEqual(1, len(self.commit_lines()))
        self.assertIn(" backend/src/existing.ts", self.commit_lines()[0])
        self.assertIn("Edited by this phase, was dirty before", self.said())
        self.assertIn("backend/src/existing.ts", self.said().split("Edited by this phase, was dirty before")[1])
        self.assertNotIn("left out of the commit: backend/src/existing.ts", self.said())

    def test_the_commit_command_includes_the_plan_when_it_was_dirty_before_the_phase_and_says_so(self):
        (self.repo / self.plan).write_text(self.plan_text().replace("Add orders.", "Add orders and returns."))
        self.finish_phase_one()
        self.assertEqual(1, len(self.commit_lines()))
        self.assertIn(f" {self.plan}", self.commit_lines()[0])
        self.assertIn(f"{self.plan} had uncommitted edits before the phase", self.said())
        self.assertNotIn(f"left out of the commit: {self.plan}", self.said())
        subprocess.run(self.commit_lines()[0], shell=True, cwd=self.repo, check=True, env=self.env, capture_output=True)
        left_dirty = subprocess.run(["git", "status", "--porcelain", "--", self.plan], cwd=self.repo,
                                   capture_output=True, text=True, env=self.env).stdout
        self.assertEqual("", left_dirty)

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
        state_file = self.repo / ".git/code-step/state.json"
        state = json.loads(state_file.read_text())
        for key, value in changes.items():
            if value is None:
                state.pop(key, None)
            else:
                state[key] = value
        state_file.write_text(json.dumps(state))

    def set_gate_result(self, result):
        gate_path = self.repo / ".git/coder-gate.json"
        gate = json.loads(gate_path.read_text())
        gate["coders"] = {} if result is None else {"a1": {"runs": 1, "denies": 0, "failed": [], "skipped": [],
                                                           "result": result}}
        gate_path.write_text(json.dumps(gate))

    def test_a_fix_coders_row_during_the_review_does_not_end_the_review_wait(self):
        self.coder_round()
        self.hook("coder", "a fix coder handing back", agent_id="fix1")
        self.wait_env(1, "0.2")
        self.assertIn("ACTION: wait", self.step("after-review"))

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

    def leave_run_of_another_session(self, stage, stop_reason, age_kind, age_seconds):
        self.start_phase_one()
        changes = {"stage": stage, "stopReason": stop_reason, "sessionId": "other-session"}
        if age_kind == "dispatch":
            changes["dispatchAt"] = time.time() - age_seconds
        self.set_state(**changes)
        state_file = self.repo / ".git/code-step/state.json"
        past = time.time() - age_seconds
        os.utime(state_file, (past, past))

    def test_a_stop_for_a_verification_failure_in_another_session_does_not_block_the_same_session(self):
        self.leave_run_of_another_session("stopped", "verification", "state-file", 60)
        self.set_state(sessionId=self.SESSION)
        self.assertIn("ACTION: dispatch", self.step("start", "--restart", self.plan))

    def test_the_closing_skill_stage_pins_the_session(self):
        self.mark_phases_done(1, 2, 3)
        self.assertIn("ACTION: invoke-skill", self.step("start", self.plan))
        self.assertEqual(self.SESSION, self.state()["sessionId"])

    def test_the_wait_stops_once_the_dispatch_is_older_than_three_waits(self):
        self.begin_coder()
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(10, "0.2", waits=3)
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("coder has not handed back in", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_a_wait_past_the_cap_still_takes_a_row_that_arrived(self):
        self.begin_coder()
        self.set_state(dispatchAt=time.time() - 100)
        self.hook("coder", self.CODER_REPORT)
        self.wait_env(10, "0.2", waits=3)
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

    # ---------- start: abandoned runs, arguments, the commit line ----------

    def test_an_early_return_in_start_clears_the_open_dispatch(self):
        self.start_phase_one()
        out = self.step("start", "--restart", "docs/plans/orders/missing.md")
        self.assertIn("ACTION: ask-user", out)
        state = self.state()
        self.assertIsNone(state.get("stage"))
        self.assertNotIn("dispatchAt", state)

    def test_start_takes_flag_like_words_after_the_task_start_as_task_text(self):
        out = self.step("start", "add", "a", "--dry-run", "flag")
        self.assertIn("Implement: add a --dry-run flag", out)

    def test_start_with_a_plan_and_an_unknown_flag_exits_two(self):
        result = run(self.repo, self.env, "start", self.plan, "--bogus")
        self.assertEqual(2, result.returncode)
        self.assertIn("usage: code_step.py start", result.stderr + result.stdout)

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
        self.assertIn("usage: code_step.py tick", self.step("tick"))

    def test_the_no_change_stop_names_the_tick_command(self):
        self.start_phase_one()
        self.hook("coder", "BEHAVIOR: none")
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("tick 1", out)

    # ---------- the fork's stop ----------

    def stop_hook(self, session=SESSION, agent_type=code_step_core.FORK_AGENT_TYPE, cwd=None):
        event = {"agent_type": agent_type, "cwd": cwd or str(self.repo), "session_id": session}
        return run(self.repo, self.env, "stop-hook", stdin=json.dumps(event)).stdout

    def test_the_stop_hook_blocks_the_fork_twice_while_a_dispatch_is_open(self):
        self.start_phase_one()
        first = json.loads(self.stop_hook())
        self.assertEqual("block", first["decision"])
        self.assertIn(self.own_command("resume"), first["reason"])
        self.assertEqual("block", json.loads(self.stop_hook())["decision"])
        self.assertEqual("", self.stop_hook())

    def test_the_stop_hook_blocks_the_fork_naming_after_plan_edit_while_the_plan_edit_coder_is_out(self):
        self.coder_round(self.IMPACT_REPORT)
        self.step("decide", "adopt", "--by", "session", "--ruling", "my own call")
        first = json.loads(self.stop_hook())
        self.assertEqual("block", first["decision"])
        self.assertIn(self.own_command("resume"), first["reason"])

    def test_the_stop_hook_leaves_other_sessions_other_agents_and_answered_dispatches_alone(self):
        self.start_phase_one()
        self.assertEqual("", self.stop_hook(session="other"))
        self.assertEqual("", self.stop_hook(agent_type="coder"))
        self.set_gate_result("pass")
        self.hook("coder", self.CODER_REPORT)
        self.assertEqual("", self.stop_hook())

    def test_a_new_dispatch_resets_the_stop_hook_count(self):
        self.start_phase_one()
        self.stop_hook()
        self.stop_hook()
        self.start_phase_one("--restart")
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
        for name in (SCRIPT.name, "script_utils.py", "plan_format.py", "reviewed_tree.py",
                     *toolkit_paths.CODE_STEP_MODULES, "test_run_output.py", "shell_command.py"):
            shutil.copy(toolkit_paths.script_in(SCRIPTS_ROOT, name), bare / name)
        env = dict(self.env, PYTHONPATH="")
        script = str(bare / SCRIPT.name)

        def bare_step(*args, stdin=None):
            return subprocess.run([sys.executable, script, *args], cwd=self.repo, env=env, input=stdin,
                                  capture_output=True, text=True).stdout

        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        out = bare_step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("handback.py could not be imported", out)
        self.assertIsNone(self.gate_mark())

    # ---------- reported defects ----------

    def replace_phase_one_verification(self, lines):
        text = self.plan_text()
        start = text.index("- [ ] **Test-verified**")
        end = text.index("#### Manual Verification:")
        (self.repo / self.plan).write_text(text[:start] + lines + "\n\n" + text[end:])

    def test_a_cargo_verification_item_is_read_as_a_command(self):
        item = "- [ ] **Tests**: the streams pass - `cargo test --test side_streams && cargo clippy -- -D warnings`"
        self.assertEqual("cargo test --test side_streams && cargo clippy -- -D warnings",
                         code_step_boundary.verification_command(item))

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
        self.hook("coder", "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters", agent_id="a1")
        self.hook("coder", "BEHAVIOR: superseded change\nWHY: backend/src/superseded.ts 1-2 — superseded reason",
                  agent_id="a0")
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertIn("order matters", out)
        self.assertNotIn("superseded", out)
        self.assertNotIn("superseded", self.said())
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
        plan = plan_format.parse_plan_with_closing_phases(self.plan_text().splitlines())
        self.assertEqual([], plan["failures"])
        self.assertEqual({"1", "2", "3", "4"}, set(plan["sections"]))
        self.assertIn("Done by hand.", plan_format.phase_text(self.plan_text().splitlines(), "2"))
        event = {"cwd": str(self.repo), "tool_input": {"file_path": str(self.repo / self.plan)}}
        self.assertEqual(0, run(self.repo, self.env, "plan-hook", stdin=json.dumps(event)).returncode)

    def test_the_closing_phase_commit_line_names_only_the_files_the_phase_changed(self):
        self.mark_phases_done(1, 2, 3)
        self.commit_all()
        (self.repo / "docs/plans/other").mkdir()
        (self.repo / "docs/plans/other/spec.md").write_text("another ticket's plan\n")
        self.step("start", self.plan)
        self.step("skill-done", "pass")
        commit_line = self.state()["commitLine"]
        self.assertNotIn("other", commit_line)
        self.assertIn("docs/plans/orders/spec.md", commit_line)

    def test_the_commit_subject_carries_the_ticket_id_of_the_plan_folder_or_branch(self):
        self.assertEqual("LED-15: ", code_step_boundary.ticket_prefix({"plan": "docs/plans/LED-15-recap/spec.md"}))
        self.assertEqual("LED-15: ", code_step_boundary.ticket_prefix({"plan": "docs/plans/orders/spec.md",
                                                               "branch": "brandon/LED-15-recap"}))
        self.assertEqual("", code_step_boundary.ticket_prefix({"plan": "docs/plans/orders/spec.md", "branch": "main"}))
        self.assertEqual("", code_step_boundary.ticket_prefix({"plan": None, "branch": "main"}))

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
        dispatch_at = self.state()["dispatchAt"]
        self.launch_the_pending_dispatch("a1", "coder")
        stale_row = {"v": 1, "ts": dispatch_at - 100, "event": "handback", "session_id": self.SESSION,
                     "agent_id": "a1", "agent_type": "coder", "message": "PLAN-IMPACT: yes\nBEHAVIOR: stale"}
        events_file = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        with events_file.open("a") as events_stream:
            events_stream.write(json.dumps(stale_row) + "\n")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        out = self.step("after-coder")
        self.assertIn("No coder report was saved", out)
        self.assertNotIn("ask-user", out)

    def allow_coder_at_the_gate(self, agent_id):
        gate_path = self.repo / ".git/coder-gate.json"
        gate = json.loads(gate_path.read_text())
        gate["coders"][agent_id] = {"runs": 1, "denies": 0, "failed": [], "skipped": [], "result": "pass"}
        gate_path.write_text(json.dumps(gate))

    def add_a_line_to_phase_one(self):
        (self.repo / self.plan).write_text(
            self.plan_text().replace(
                "**File**: `backend/src/orders.test.ts`\n",
                "**File**: `backend/src/orders.test.ts`\nAlso total the orders.\n",
                1,
            )
        )

    def test_a_coder_that_is_not_the_stopped_one_does_not_revive_the_run(self):
        self.stop_the_coder_on_a_blocked_report()
        self.hook("coder", "BEHAVIOR: another coder\nREVIEW: recommended", agent_id="other")
        self.send_message("a1")
        self.assertIn("has not handed back", self.step("after-coder"))
        self.assertEqual("stopped", self.state()["stage"])
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended", agent_id="a1")
        self.assertIn("AGENT: review-loop", self.step("after-coder"))

    def test_the_stop_on_a_blocked_coder_says_to_resume_it_with_send_message_then_run_resume(self):
        self.start_phase_one()
        self.hook("coder", "BEHAVIOR: none\nblocked on two steps")
        out = self.step("after-coder")
        self.assertIn("SendMessage", out)
        self.assertIn(self.own_command("resume"), out)

    def test_a_word_dash_number_in_a_plan_folder_or_branch_is_not_a_ticket_id(self):
        for name in ("upgrade-node-20", "oauth-2", "fix-1", "phase-2", "python-3", "led-15"):
            with self.subTest(name=name):
                self.assertEqual("", code_step_boundary.ticket_prefix({"plan": f"work/{name}/spec.md", "branch": name}))
        self.assertEqual("ABC2-7: ", code_step_boundary.ticket_prefix({"plan": "work/upgrade-node-20/spec.md",
                                                               "branch": "brandon/ABC2-7-upgrade"}))

    def test_an_automated_verification_section_of_only_not_applicable_items_is_empty(self):
        for item in ("- [ ] N/A — docs only", "- [ ] **N/A**: nothing to run", "- [x] none"):
            with self.subTest(item=item):
                self.assertEqual(([], [], []), code_step_boundary.run_verification_commands(
                    self.repo, f"#### Automated Verification:\n\n{item}\n\n#### Manual Verification:\n"))

    def test_a_phase_with_only_a_not_applicable_automated_item_is_marked_done(self):
        self.replace_phase_one_verification("- [ ] N/A — docs only")
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertNotIn("no command could be read", out)
        self.assertEqual("done", self.state()["stage"])

    def test_a_script_path_or_sh_command_is_read_as_a_verification_command(self):
        self.assertEqual("./scripts/check.sh --fast", code_step_boundary.verification_command(
            "- [ ] **Check**: passes - `./scripts/check.sh --fast`"))
        self.assertEqual(
            "sh scripts/check.sh", code_step_boundary.verification_command("- [ ] **Check**: `sh scripts/check.sh`")
        )

    def test_a_command_with_leading_variable_assignments_runs_with_them_set(self):
        self.set_verification("- [ ] **Env**: `VERIFY_SEEN=yes bash -c 'test \"$VERIFY_SEEN\" = yes'`")
        self.coder_round()
        self.hook("review-loop", self.LOOP_OK)

        out = self.step("after-review")

        self.assertNotIn("no command could be read", out)
        self.assertEqual("done", self.state()["stage"])

    def test_the_prefixed_command_wins_over_a_later_span_without_a_prefix(self):
        item = "- [ ] **Env**: `PARITY_PATH=/x/y.py cargo test --test watch_parity`, not `cargo test`"

        command = code_step_boundary.verification_command(item)
        self.assertEqual("PARITY_PATH=/x/y.py cargo test --test watch_parity", command)

    def test_a_quoted_assignment_value_with_spaces_is_kept_in_the_command(self):
        item = "- [ ] **Env**: `GREETING=\"a b\" bash -c 'echo hi'`"

        self.assertEqual("GREETING=\"a b\" bash -c 'echo hi'", code_step_boundary.verification_command(item))

    def test_an_assignment_followed_by_no_command_or_by_a_program_that_is_not_installed_is_not_a_verification_command(
        self,
    ):
        for item in (
            "- [ ] **Env**: set `PARITY_PATH=/x/y.py` first",
            "- [ ] **Env**: `PARITY_PATH=/x/y.py nosuchprogram hi`",
        ):
            with self.subTest(item=item):
                self.assertIsNone(code_step_boundary.verification_command(item))

    def test_an_assignment_that_expands_a_variable_or_runs_a_command_still_leads_to_the_command(self):
        for command in ("LEDGER_REAL_DOTFILES=$HOME/dotfiles cargo test --test watch_parity",
                        "PATH=/x/bin:$PATH cargo test", 'DATABASE_URL="$TEST_DB" pytest -q',
                        "T=$(find . -name x) cargo test", "A=1 B=$HOME/x make all"):
            with self.subTest(command=command):
                self.assertTrue(code_step_boundary.COMMAND_START.match(command))
                item = f"- [ ] **Check**: passes - `{command}`"
                self.assertEqual(command, code_step_boundary.verification_command(item))

    def test_an_assignment_followed_by_a_control_operator_is_not_a_command_start(self):
        for span in ("A=1 && cargo test", "A=1 ; cargo test", "A=1 | cat", "A=1 # note"):
            with self.subTest(span=span):
                self.assertIsNone(code_step_boundary.COMMAND_START.match(span))

    def test_a_whole_suite_command_with_a_variable_prefix_is_still_skipped(self):
        section = "#### Automated Verification:\n\n- [ ] **All**: `CI=1 npm test`\n\n#### Manual Verification:\n"

        results, skipped, unparsed = code_step_boundary.run_verification_commands(self.repo, section)

        self.assertEqual(([], ["CI=1 npm test"], []), (results, skipped, unparsed))

    @staticmethod
    def verification_section(command):
        return (f"#### Automated Verification:\n\n- [ ] **New test**: passes - `{command}`\n\n"
                "#### Manual Verification:\n")

    def test_a_filtered_test_run_that_matches_no_test_fails_the_verification(self):
        command = """python3 -c "print('vitest: no tests found')" -t nomatch"""

        results, _, _ = code_step_boundary.run_verification_commands(self.repo, self.verification_section(command))

        (ran_command, code, output), = results
        self.assertEqual(command, ran_command)
        self.assertNotEqual(0, code)
        self.assertIn("test filter matched no test", output)

    def test_a_filtered_test_run_that_reports_a_passed_test_stays_green(self):
        command = """python3 -c "print('vitest: 2 passed')" -t match"""

        results, _, _ = code_step_boundary.run_verification_commands(self.repo, self.verification_section(command))

        (_, code, _), = results
        self.assertEqual(0, code)

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
                found = code_step_report.plan_impact_block(report)
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

    def test_resume_with_no_dispatch_time_asks_for_the_saved_state_and_dispatches_nothing(self):
        self.begin_coder()
        self.set_state(dispatchAt=None)
        self.wait_env(1, "0.2")
        saved_state = self.state()
        out = self.step("resume")
        self.assertIn("ACTION: ask-user", out)
        self.assertNotIn("AGENT:", out)
        self.assertIn("The run is at stage coder.", self.said())
        self.assertIn(f"`{self.own_command('status')}`", self.said())
        self.assertIn("start --restart", self.said())
        self.assertEqual(saved_state, self.state())

    def test_resume_with_no_dispatch_time_does_not_read_an_old_row_as_the_report(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: none\nPLAN-IMPACT: yes")
        self.set_state(dispatchAt=None)
        self.wait_env(1, "0.2")
        out = self.step("resume")
        self.assertIn("ACTION: ask-user", out)
        self.assertNotIn("PLAN-IMPACT", self.said())
        self.assertIn("The run is at stage coder.", self.said())

    def test_a_final_report_that_names_a_plan_impact_still_asks_the_user(self):
        self.begin_coder()
        self.hook("coder", "BEHAVIOR: orders exist\nPLAN-IMPACT: yes")
        self.assertIn("ACTION: ask-user", self.step("after-coder"))

    def test_after_coder_waits_for_a_coder_resumed_after_a_stop_instead_of_saying_to_start(self):
        self.stop_the_coder_on_a_blocked_report()
        self.send_message("a1")
        self.wait_env(1, "0.2")
        out = self.step("after-coder")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("Run `start` first", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_the_wait_cap_for_a_resumed_coder_counts_from_the_first_wait_not_from_the_old_stop(self):
        self.stop_the_coder_on_a_blocked_report()
        self.send_message("a1")
        self.set_state(resumableCoderAt=time.time() - 100)
        events_file = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        kept_lines = [line for line in events_file.read_text().splitlines() if json.loads(line)["event"] != "handback"]
        events_file.write_text("\n".join(kept_lines) + "\n")
        self.wait_env(1, "0.2", waits=3)
        out = self.step("after-coder")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("has not handed back in", out)
        self.assertIsNotNone(self.state().get("resumeWaitAt"))

    def test_repeated_waits_on_a_resumed_coder_end_in_the_cap_stop(self):
        self.stop_the_coder_on_a_blocked_report()
        self.send_message("a1")
        self.wait_env(1, "0.2", waits=3)
        self.step("after-coder")
        self.set_state(resumeWaitAt=time.time() - 100)
        out = self.step("after-coder")
        self.assertIn("ACTION: stop", out)
        self.assertIn("has not handed back in", out)

    def test_the_first_wait_time_of_a_resumed_coder_is_saved_once(self):
        self.stop_the_coder_on_a_blocked_report()
        self.send_message("a1")
        self.wait_env(1, "0.2")
        self.step("after-coder")
        first_wait_at = self.state()["resumeWaitAt"]
        self.step("after-coder")
        self.assertEqual(first_wait_at, self.state()["resumeWaitAt"])

    def test_the_hand_back_of_a_resumed_coder_clears_the_saved_first_wait_time(self):
        self.stop_the_coder_on_a_blocked_report()
        self.send_message("a1")
        self.wait_env(1, "0.2")
        self.step("after-coder")
        self.assertIsNotNone(self.state().get("resumeWaitAt"))
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        self.assertIn("AGENT: review-loop", self.step("after-coder"))
        state = self.state()
        self.assertEqual("review", state["stage"])
        self.assertNotIn("resumeWaitAt", state)
        self.assertNotIn("resumableCoderAt", state)
        self.assertNotIn("resumableCoderId", state)

    def test_after_coder_says_the_resumed_coder_has_not_handed_back_when_it_runs_with_no_wait(self):
        self.stop_the_coder_on_a_blocked_report()
        self.send_message("a1")
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

    def test_after_coder_goes_to_review_when_the_resumed_coder_hands_back_while_it_waits(self):
        self.stop_the_coder_on_a_blocked_report()
        self.send_message("a1")
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.wait_env(20)
        self.late_hook(1, "coder", self.CODER_REPORT)
        out = self.step("after-coder")
        self.assertIn("AGENT: review-loop", out)
        self.assertEqual("review", self.state()["stage"])

    def test_save_state_leaves_the_old_state_file_whole_when_the_write_fails_midway(self):
        code_step.save_state(self.repo, {"stage": "coder", "filler": "x" * 1000})
        state_file = code_step.state_dir(self.repo) / "state.json"
        old_text = state_file.read_text()

        with unittest.mock.patch("os.replace", side_effect=OSError("disk full")), self.assertRaises(OSError):
            code_step.save_state(self.repo, {"stage": "review"})

        self.assertEqual(old_text, state_file.read_text())
        self.assertEqual([state_file.name], sorted(path.name for path in state_file.parent.glob("state.json*")))

    def test_a_reader_polling_the_state_file_never_sees_a_partial_write(self):
        big_state = {"stage": "coder", "filler": "x" * 2_000_000}
        code_step.save_state(self.repo, big_state)
        state_file = code_step.state_dir(self.repo) / "state.json"
        stop_polling = threading.Event()
        unreadable = []

        def poll():
            while not stop_polling.is_set():
                try:
                    json.loads(state_file.read_text())
                except ValueError as error:
                    unreadable.append(error)

        reader = threading.Thread(target=poll)
        reader.start()
        for _ in range(30):
            code_step.save_state(self.repo, big_state)
        stop_polling.set()
        reader.join()

        self.assertEqual([], unreadable)

    def adopt_plan_change_with_the_plan_coder_out(self):
        report = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes"
        self.coder_round(report)
        out = self.step("decide", "adopt", "--by", "user", "--ruling", "adopt it, drop the header")
        self.assertIn("AGENT: coder", out)
        self.assertEqual("plan-coder", self.state()["stage"])

    def test_resume_in_the_plan_edit_with_no_dispatch_time_asks_for_the_saved_state_instead_of_dispatching_the_review(
        self,
    ):
        self.adopt_plan_change_with_the_plan_coder_out()
        self.set_state(dispatchAt=None)
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        self.wait_env(1, "0.2")
        out = self.step("resume")
        self.assertIn("ACTION: ask-user", out)
        self.assertNotIn("AGENT:", out)
        self.assertIn("The run is at stage plan-coder.", self.said())
        self.assertEqual("plan-coder", self.state()["stage"])

    def test_after_plan_edit_with_a_dispatch_waits_for_the_plan_coder_row_before_the_review(self):
        self.adopt_plan_change_with_the_plan_coder_out()
        (self.repo / self.plan).write_text(self.plan_text() + "\nadopted step\n")
        self.wait_env(1, "0.2")
        self.assertIn("ACTION: wait", self.step("after-plan-edit"))
        self.hook("coder", "BEHAVIOR: plan rewritten", agent_id="plan-edit")
        self.assertIn("AGENT: review-loop", self.step("after-plan-edit"))

    # ---------- a review-loop resumed after the wait cap is the pending review ----------

    def stop_the_review_at_the_wait_cap(self):
        self.coder_round()
        self.launch_the_pending_review("r1")
        self.age_dispatches(100)
        self.set_state(dispatchAt=time.time() - 100)
        self.wait_env(1, "0.2", waits=3)
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertEqual("stopped", self.state()["stage"])
        return out

    def test_the_review_wait_cap_counts_from_the_launch_not_from_the_printed_dispatch(self):
        self.coder_round()
        self.set_state(dispatchAt=time.time() - 100)
        self.launch_the_pending_review("r1")
        self.wait_env(1, "0.2", waits=3)

        out = self.step("resume")

        self.assertIn("ACTION: wait", out)
        self.assertNotIn("has not handed back in", out)
        self.assertNotEqual("stopped", self.state()["stage"])

    def test_the_stop_at_the_review_wait_cap_says_to_run_after_review_when_the_loop_is_resumed(self):
        out = self.stop_the_review_at_the_wait_cap()
        self.assertIn("SendMessage", out)
        self.assertIn(self.own_command("resume"), out)

    def test_after_review_waits_for_a_review_loop_resumed_after_the_cap(self):
        self.stop_the_review_at_the_wait_cap()
        self.send_message("r1")
        out = self.step("after-review")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("no review pending", out)
        self.assertEqual("stopped", self.state()["stage"])

    def test_repeated_waits_on_a_review_loop_resumed_after_the_cap_end_in_the_cap_stop(self):
        self.stop_the_review_at_the_wait_cap()
        self.send_message("r1")
        self.wait_env(2, "0.2", waits=3)
        self.assertIn("ACTION: wait", self.step("after-review"))
        first_wait_at = self.state()["resumeWaitAt"]
        self.assertIn("ACTION: wait", self.step("after-review"))
        self.assertEqual(first_wait_at, self.state()["resumeWaitAt"])
        self.set_state(resumeWaitAt=time.time() - 100)
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("has not handed back in", out)

    def test_after_review_says_the_resumed_review_loop_has_not_handed_back_when_it_runs_with_no_wait(self):
        self.stop_the_review_at_the_wait_cap()
        self.send_message("r1")
        self.wait_env(0)
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("resumed review-loop has not handed back yet", out)
        self.assertNotIn("no review pending", out)
        self.assertNotIn("Run `start` first", out)

    def test_the_hand_back_of_a_resumed_review_loop_clears_the_resume_mark_and_the_saved_first_wait_time(self):
        self.stop_the_review_at_the_wait_cap()
        self.send_message("r1")
        self.step("after-review")
        self.assertIsNotNone(self.state().get("resumeWaitAt"))
        self.hook("review-loop", self.ASK, agent_id="r1")
        self.step("after-review")
        state = self.state()
        self.assertEqual("asks", state["stage"])
        self.assertNotIn("resumableReview", state)
        self.assertNotIn("resumeWaitAt", state)

    def test_the_coder_reports_of_an_asks_round_hold_only_the_agents_of_its_newest_dispatch(self):
        self.start_phase_one()
        self.launch_the_pending_dispatch("a1", "coder")
        self.hook("coder", "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C")
        state = self.state()
        run_id = state["runId"]
        for dispatch_id, agent_id in (("d2", "ask1"), ("d3", "ask2")):
            code_step_core.log_event(self.repo, run_id, "dispatch", self.SESSION, id=dispatch_id,
                                     agent_type="coder", stage="asks-coder")
            code_step_core.log_event(self.repo, run_id, "launch", self.SESSION, agent_id=agent_id,
                                     dispatch=dispatch_id)
            code_step_core.log_event(self.repo, run_id, "handback", self.SESSION, agent_id=agent_id,
                                     agent_type="coder", message=f"report of {agent_id}")

        reports = code_step_core.phase_coder_reports(self.repo, state)

        self.assertEqual([("a1", "coder"), ("ask2", "asks-coder")],
                         [(report["agent_id"], report["stage"]) for report in reports])
        self.assertEqual(["report of ask2"], reports[1]["messages"])

    def test_a_dispatch_opened_on_a_state_with_no_run_id_starts_a_new_run_at_its_first_dispatch(self):
        state = {"stage": "coder"}
        code_step_core.open_dispatch(state)
        run_id = state["runId"]
        self.assertTrue(run_id)
        self.assertIsNotNone(state["dispatchAt"])

        marked_prompt, _prompt_file = code_step_core.record_dispatch(self.repo, state, "after-coder", "coder", None,
                                                                     "the prompt")
        self.assertTrue(marked_prompt.endswith(f"code-step-dispatch: {run_id}/d1"))

        code_step_core.open_dispatch(state)
        self.assertEqual(run_id, state["runId"])

    def test_a_review_loop_resumed_after_the_cap_that_hands_back_is_the_pending_review(self):
        self.stop_the_review_at_the_wait_cap()
        self.send_message("r1")
        self.hook("review-loop", self.LOOP_OK, agent_id="r1")
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
        out = self.step("start", "--restart", self.plan)
        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT:", out)
        for number in (1, 2, 3, 4):
            self.assertIn(f"Phase {number} (gate: the data team signs off)", out)
        state = self.state()
        self.assertNotIn("dispatchAt", state)
        self.assertIsNone(state.get("stage"))

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

    def move_phases(self, *numbers, with_deviation=True):
        text = self.plan_text()
        for number in numbers:
            line = next(line for line in text.splitlines() if line.startswith(f"- [ ] Phase {number}:"))
            moved_line = line.replace("- [ ]", "- [-]", 1) + " — moved to LED-16, per the user 2026-10-20"
            text = text.replace(line, moved_line)
        if with_deviation:
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
        moved_plan = self.plan_text()
        self.assertNotEqual(before, moved_plan)
        self.hook("review-loop", self.LOOP_OK)
        out = self.step("after-review")
        self.assertIn("ACTION: stop", out)
        self.assertIn("Phase 1 is moved to LED-16", out)
        self.assertIn("The coder ran, and its work is not marked done or committed.", out)
        self.assertNotIn("No coder was dispatched", out)
        self.assertEqual("stopped", self.state()["stage"])
        self.assertEqual(moved_plan, self.plan_text())
        self.assertNotIn("Phase 1 marked done", out + self.said())
        self.assertNotIn("Commit command", self.said())

    def test_a_moved_line_with_no_plan_deviations_entry_stops_start_with_the_fix(self):
        self.move_phases(2, with_deviation=False)
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
        status_line = "- [ ] Phase 4: Refactor pass - /refactor cleanup sweep (risk: low)\n"
        closing_section = "## Phase 4: Refactor pass\n\nSweep.\n\n"
        (self.repo / self.plan).write_text(self.plan_text().replace(status_line, "").replace(closing_section, ""))
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
        self.send_message("a1")
        self.wait_env(1, "0.2", waits=3)
        self.step("after-coder")
        self.set_state(resumeWaitAt=time.time() - 100)
        self.assertIn("has not handed back in", self.step("after-coder"))
        self.assertNotIn("resumeWaitAt", self.state())
        self.send_message("a1")
        out = self.step("after-coder")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("has not handed back in", out)

    def test_the_wait_after_a_cap_stop_on_a_resumed_review_loop_waits_again(self):
        self.stop_the_review_at_the_wait_cap()
        self.send_message("r1")
        self.step("after-review")
        self.set_state(resumeWaitAt=time.time() - 100)
        self.assertIn("has not handed back in", self.step("after-review"))
        self.assertNotIn("resumeWaitAt", self.state())
        self.send_message("r1")
        out = self.step("after-review")
        self.assertIn("ACTION: wait", out)
        self.assertNotIn("has not handed back in", out)

    # ---------- a stale save that undid the hook's flip does not lose the resumed coder's report ----------

    def test_after_coder_still_waits_when_the_resumed_coder_has_saved_no_row(self):
        self.stop_the_coder_on_a_blocked_report()
        self.send_message("a1")
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
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        out = self.step("after-coder")
        self.assertIn("ACTION: ask-user", out)

    # ---------- the event log: dispatch events, prompt files, the log hook and the dispatch hook ----------

    HOOK_FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"

    def run_events(self):
        events_file = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        return [json.loads(line) for line in events_file.read_text().splitlines()] if events_file.exists() else []

    def events_named(self, event_name):
        return [event for event in self.run_events() if event["event"] == event_name]

    def printed_prompt(self, out):
        return out.split("-----BEGIN PROMPT-----\n", 1)[1].split("\n-----END PROMPT-----", 1)[0]

    def hook_fixture(self, name):
        # One event of its kind as the tool call and its result were recorded in a transcript: the tool_name, the
        # tool_input and the tool_response, with the prompt and message text cut to a placeholder.
        fixture_file = self.HOOK_FIXTURES / f"hook_event_{name}.json"
        return json.loads(fixture_file.read_text())

    def log_hook(self, tool_name, tool_input, tool_response=None, **extra):
        event = {"tool_name": tool_name, "tool_input": tool_input, "cwd": str(self.repo), "session_id": self.SESSION,
                 **extra}
        if tool_response is not None:
            event["tool_response"] = tool_response
        return run(self.repo, self.env, "log-hook", stdin=json.dumps(event))

    def log_fixture(self, name, tool_input=None, tool_response=None, **extra):
        # Feeds the log hook the recorded event of this kind, with the given fields laid over the recorded ones.
        fixture = self.hook_fixture(name)
        fixture["tool_input"].update(tool_input or {})
        fixture["tool_response"].update(tool_response or {})
        return self.log_hook(fixture["tool_name"], fixture["tool_input"], fixture["tool_response"], **extra)

    def launch_agent(self, prompt, agent_id="a1", subagent_type="coder", session=SESSION, **extra):
        return self.log_fixture("agent_launch", {"subagent_type": subagent_type, "prompt": prompt},
                                {"agentId": agent_id}, session_id=session, **extra)

    def send_message(self, to, **extra):
        return self.log_fixture("send_message", {"to": to, "recipient": to}, **extra)

    def hand_back(self, message, agent_type, agent_id, session=SESSION, **extra):
        return self.log_fixture("subagent_handback", {"message": message}, agent_type=agent_type, agent_id=agent_id,
                                session_id=session, **extra)

    def dispatch_hook(self, prompt, subagent_type="coder", session=SESSION, cwd=None):
        event = {"tool_name": "Agent", "tool_input": {"subagent_type": subagent_type, "prompt": prompt},
                 "cwd": cwd or str(self.repo)}
        if session:
            event["session_id"] = session
        return run(self.repo, self.env, "dispatch-hook", stdin=json.dumps(event)).stdout

    def denial_reason(self, hook_output):
        return json.loads(hook_output)["hookSpecificOutput"]["permissionDecisionReason"]

    def assert_dispatch_logged(self, out, dispatch_id, agent_type, stage, verb):
        # The printed dispatch is the logged one: same agent, stage and verb, the saved prompt file named, and the
        # prompt ending with the marker line of its id.
        dispatch = next((event for event in self.events_named("dispatch") if event["id"] == dispatch_id), None)
        self.assertIsNotNone(dispatch, f"no dispatch event {dispatch_id}")
        self.assertEqual((agent_type, stage, verb), (dispatch["agent_type"], dispatch["stage"], dispatch["verb"]))
        self.assertIn(f"PROMPT FILE: {dispatch['prompt_file']}\n", out)
        printed_lines = self.printed_prompt(out).splitlines()
        self.assertEqual(f"code-step-dispatch: {self.state()['runId']}/{dispatch_id}", printed_lines[-1])

    def test_dispatch_event_writes_prompt_file(self):
        out = self.start_phase_one()

        run_id = self.state()["runId"]
        dispatches = self.events_named("dispatch")
        self.assertEqual(1, len(dispatches))
        dispatch = dispatches[0]
        dispatch_keys = {"v", "ts", "event", "session_id", "id", "agent_type", "stage", "verb", "model", "prompt_file"}
        self.assertEqual(dispatch_keys, set(dispatch))
        self.assertEqual((1, "d1", self.SESSION), (dispatch["v"], dispatch["id"], dispatch["session_id"]))
        self.assertEqual(("coder", "coder", "resume", None),
                         (dispatch["agent_type"], dispatch["stage"], dispatch["verb"], dispatch["model"]))
        prompt_file = self.repo / ".git/code-step/runs" / run_id / "prompt-d1.txt"
        self.assertEqual(str(prompt_file), dispatch["prompt_file"])
        self.assertIn(f"PROMPT FILE: {prompt_file}\n", out)
        saved_prompt = prompt_file.read_text()
        self.assertIn("Implement Phase 1 of `docs/plans/orders/spec.md`", saved_prompt)
        self.assertIn("Packet for Phase 1", saved_prompt)
        self.assertEqual(f"code-step-dispatch: {run_id}/d1", saved_prompt.rstrip().splitlines()[-1])
        self.assertEqual(saved_prompt.rstrip(), self.printed_prompt(out))

    def test_every_dispatch_kind_logs_an_event_with_its_agent_verb_and_model(self):
        self.coder_round()

        review_dispatch = self.events_named("dispatch")[-1]
        self.assertEqual(("d2", "review-loop", "review", "resume", "sonnet"),
                         (review_dispatch["id"], review_dispatch["agent_type"], review_dispatch["stage"],
                          review_dispatch["verb"], review_dispatch["model"]))
        review_prompt = pathlib.Path(review_dispatch["prompt_file"]).read_text()
        self.assertIn("mode: review-first", review_prompt)
        self.assertEqual(f"code-step-dispatch: {self.state()['runId']}/d2", review_prompt.rstrip().splitlines()[-1])

    def test_planless_start_logs_its_dispatch_and_saves_its_prompt(self):
        out = self.step("start", "+fast", "--task", "fix the typo")

        dispatch = self.events_named("dispatch")[0]
        self.assertEqual(("d1", "coder", "haiku"), (dispatch["id"], dispatch["agent_type"], dispatch["model"]))
        self.assertIn(f"PROMPT FILE: {dispatch['prompt_file']}", out)
        self.assertIn("Implement: fix the typo", pathlib.Path(dispatch["prompt_file"]).read_text())

    def test_a_new_start_deletes_the_older_run_folders(self):
        self.start_phase_one()
        first_run = self.state()["runId"]

        self.start_phase_one("--restart")

        run_folders = [folder.name for folder in (self.repo / ".git/code-step/runs").iterdir()]
        self.assertNotEqual(first_run, self.state()["runId"])
        self.assertEqual([self.state()["runId"]], run_folders)

    def test_launch_binds_marker(self):
        out = self.start_phase_one()
        run_id = self.state()["runId"]

        self.launch_agent(self.printed_prompt(out), agent_id="agent-7")

        launches = self.events_named("launch")
        self.assertEqual(1, len(launches))
        self.assertEqual((1, "launch", self.SESSION, "agent-7", "d1"),
                         (launches[0]["v"], launches[0]["event"], launches[0]["session_id"], launches[0]["agent_id"],
                          launches[0]["dispatch"]))
        self.launch_agent("An Agent call with no marker line", agent_id="agent-8")
        self.launch_agent(f"text\ncode-step-dispatch: {run_id}-old/d1", agent_id="agent-9")
        launches = self.events_named("launch")
        self.assertEqual(["agent-7"], [launch["agent_id"] for launch in launches])

    def test_launch_binds_a_marker_that_is_folded_into_one_line_or_followed_by_text(self):
        out = self.start_phase_one()
        whole_prompt = self.printed_prompt(out)
        one_line_prompt = " ".join(whole_prompt.split())
        prompt_with_trailing_text = whole_prompt + " Thank you."

        self.assertEqual("", self.dispatch_hook(one_line_prompt))
        self.assertEqual("", self.dispatch_hook(prompt_with_trailing_text))
        self.launch_agent(one_line_prompt, agent_id="agent-1")
        self.launch_agent(prompt_with_trailing_text, agent_id="agent-2")

        launches = self.events_named("launch")
        self.assertEqual([("agent-1", "d1"), ("agent-2", "d1")],
                         [(launch["agent_id"], launch["dispatch"]) for launch in launches])

    def test_a_launch_without_an_agent_id_is_logged_and_the_wait_stops_on_it_without_a_second_dispatch(self):
        out = self.start_phase_one()
        launch = self.hook_fixture("agent_launch")
        launch["tool_input"]["prompt"] = self.printed_prompt(out)
        del launch["tool_response"]["agentId"]

        result = self.log_hook("Agent", launch["tool_input"], launch["tool_response"])

        self.assertEqual([None], [event["agent_id"] for event in self.events_named("launch")])
        self.assertEqual("", result.stdout)
        self.assertEqual("", result.stderr)
        self.wait_env(20)
        self.env["CODE_STEP_LAUNCH_SECONDS"] = "0"
        stopped = self.step("after-coder")
        self.assertIn("ACTION: stop", stopped)
        self.assertIn("launch has no agent id", stopped)
        self.assertNotIn("ACTION: dispatch", stopped)
        self.assertEqual(1, len(self.events_named("dispatch")))

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
        pre_call = {"agent_type": "coder", "agent_id": "a7", "cwd": str(self.repo), "session_id": self.SESSION,
                    "tool_input": {"message": message}}
        run(self.repo, self.env, "hook", stdin=json.dumps(pre_call))
        self.assertEqual([], self.events_named("handback"))
        self.hand_back(message, "coder", "a7")

        handbacks = self.events_named("handback")
        self.assertEqual([("a7", "coder", message)],
                         [(handback["agent_id"], handback["agent_type"], handback["message"])
                          for handback in handbacks])

    def test_the_hooks_leave_a_state_without_a_run_id_alone(self):
        self.start_phase_one()
        old_run_id = self.state()["runId"]
        old_events = self.run_events()
        state_path = self.repo / ".git/code-step/state.json"
        legacy_state = json.loads(state_path.read_text())
        legacy_state["runId"] = None
        state_path.write_text(json.dumps(legacy_state))
        agent_call = {"tool_name": "Agent", "cwd": str(self.repo), "session_id": self.SESSION,
                     "tool_input": {"subagent_type": "coder", "prompt": "thin"}}

        launch_result = self.launch_agent(f"code-step-dispatch: {old_run_id}/d1", agent_id="agent-7")
        resume_result = self.send_message("agent-7")
        deny_result = run(self.repo, self.env, "dispatch-hook", stdin=json.dumps(agent_call))

        for result in (launch_result, resume_result, deny_result):
            self.assertEqual(("", ""), (result.stdout, result.stderr))
        events_file = self.repo / ".git/code-step/runs" / old_run_id / "events.jsonl"
        self.assertEqual(old_events, [json.loads(line) for line in events_file.read_text().splitlines()])

    def test_log_hook_writes_nothing_for_another_session_or_a_finished_run(self):
        out = self.start_phase_one()
        whole_prompt = self.printed_prompt(out)

        self.send_message("agent-7", session_id="sess-other")
        self.assertEqual([], self.events_named("resume"))
        self.send_message("agent-7")
        resumes = self.events_named("resume")
        self.assertEqual(1, len(resumes))

        self.finish_phase_one()
        event_count = len(self.run_events())
        self.assertEqual("done", self.state()["stage"])
        self.send_message("agent-7")
        self.launch_agent(whole_prompt, agent_id="agent-8")

        events_after_done = self.run_events()
        self.assertEqual(event_count, len(events_after_done))

    def test_dispatch_hook_denies_missing_packet(self):
        out = self.start_phase_one()
        whole_prompt = self.printed_prompt(out)
        prompt_file = self.events_named("dispatch")[0]["prompt_file"]
        thin_prompt = "Implement Phase 1 of `docs/plans/orders/spec.md`. Read the plan phase-scoped."

        reason = self.denial_reason(self.dispatch_hook(thin_prompt))

        fork_blocks = self.events_named("fork-block")
        self.assertIn(f"Read {prompt_file} and pass its whole text.", reason)
        self.assertEqual([("d1", "prompt-deny")], [(block["dispatch"], block["kind"]) for block in fork_blocks])
        self.assertEqual("", self.dispatch_hook(whole_prompt))

    def test_dispatch_hook_accepts_the_whole_prompt_with_changed_whitespace(self):
        out = self.start_phase_one()
        reflowed = "Task for you:\n\n   " + self.printed_prompt(out).replace("\n", "\n\n  ").replace(" ", "  ")

        self.assertEqual("", self.dispatch_hook(reflowed))
        self.assertEqual([], self.events_named("fork-block"))

    def test_dispatch_hook_stops_the_fork_after_three_denials(self):
        self.start_phase_one()
        prompt_file = self.events_named("dispatch")[0]["prompt_file"]

        reasons = [self.denial_reason(self.dispatch_hook("thin")) for _ in range(4)]

        for reason in reasons[:3]:
            self.assertIn("pass its whole text", reason)
        self.assertNotIn("pass its whole text", reasons[3])
        self.assertIn("Stop.", reasons[3])
        self.assertIn(prompt_file, reasons[3])

    def test_dispatch_hook_denies_a_second_launch_of_the_same_dispatch(self):
        out = self.start_phase_one()
        whole_prompt = self.printed_prompt(out)
        self.assertEqual("", self.dispatch_hook(whole_prompt))
        self.launch_agent(whole_prompt, agent_id="agent-7")

        reason = self.denial_reason(self.dispatch_hook(whole_prompt))

        self.assertIn("already launched", reason)
        self.assertIn("agent-7", reason)
        self.assertIn(f"`{code_step_core.SELF_COMMAND} resume` as a Bash call with timeout", reason)
        fork_blocks = self.events_named("fork-block")
        self.assertEqual([("d1", "relaunch")], [(block["dispatch"], block["kind"]) for block in fork_blocks])

    def test_dispatch_hook_denies_a_one_line_copy_of_a_launched_prompt(self):
        out = self.start_phase_one()
        whole_prompt = self.printed_prompt(out)
        one_line_prompt = " ".join(whole_prompt.split())
        self.launch_agent(whole_prompt, agent_id="agent-7")

        reason = self.denial_reason(self.dispatch_hook(one_line_prompt))

        fork_blocks = self.events_named("fork-block")
        self.assertIn("already launched", reason)
        self.assertEqual([("d1", "relaunch")], [(block["dispatch"], block["kind"]) for block in fork_blocks])

    def test_dispatch_hook_relaunch_denials_never_reach_the_prompt_denial_cap(self):
        out = self.start_phase_one()
        whole_prompt = self.printed_prompt(out)
        self.launch_agent(whole_prompt, agent_id="agent-7")

        reasons = [self.denial_reason(self.dispatch_hook(whole_prompt)) for _ in range(4)]

        for reason in reasons:
            self.assertIn("already launched", reason)
            self.assertIn("code_step.py resume", reason)
            self.assertNotIn("Stop.", reason)
        fork_blocks = self.events_named("fork-block")
        self.assertEqual(["relaunch"] * 4, [block["kind"] for block in fork_blocks])

    def test_dispatch_hook_lets_a_coder_call_without_the_marker_pass_after_the_coder_launch(self):
        out = self.start_phase_one()
        self.launch_agent(self.printed_prompt(out), agent_id="agent-7")

        result = self.dispatch_hook("Explore the orders module.")

        self.assertEqual("", result)
        self.assertEqual([], self.events_named("fork-block"))

    def test_dispatch_hook_lets_a_call_without_the_marker_pass_while_a_launched_dispatch_is_open(self):
        self.start_phase_one()
        self.launch_agent("code-step-dispatch: " + self.state()["runId"] + "/d1")
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        review_out = self.step("after-coder")
        self.launch_agent(self.printed_prompt(review_out), agent_id="agent-9", subagent_type="review-loop")

        self.assertEqual("", self.dispatch_hook("Review this branch for the user.", subagent_type="review-loop"))
        self.assertEqual([], self.events_named("fork-block"))

    def test_dispatch_hook_lets_a_review_loop_relaunch_with_its_marker_pass(self):
        self.start_phase_one()
        self.launch_agent("code-step-dispatch: " + self.state()["runId"] + "/d1")
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        review_out = self.step("after-coder")
        review_prompt = self.printed_prompt(review_out)
        self.launch_agent(review_prompt, agent_id="agent-9", subagent_type="review-loop")

        self.assertEqual("", self.dispatch_hook(review_prompt, subagent_type="review-loop"))
        self.assertEqual([], self.events_named("fork-block"))

    def test_dispatch_hook_denies_a_thin_review_loop_prompt_while_the_review_dispatch_is_pending(self):
        self.start_phase_one()
        self.launch_agent("code-step-dispatch: " + self.state()["runId"] + "/d1")
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.hook("coder", "BEHAVIOR: orders exist\nREVIEW: recommended")
        review_out = self.step("after-coder")
        review_prompt = self.printed_prompt(review_out)
        review_prompt_file = self.events_named("dispatch")[-1]["prompt_file"]

        reason = self.denial_reason(self.dispatch_hook("Review the branch.", subagent_type="review-loop"))

        fork_blocks = self.events_named("fork-block")
        self.assertIn(f"Read {review_prompt_file} and pass its whole text.", reason)
        self.assertEqual([("d2", "prompt-deny")], [(block["dispatch"], block["kind"]) for block in fork_blocks])
        self.assertEqual("", self.dispatch_hook(review_prompt, subagent_type="review-loop"))

    def test_dispatch_hook_denies_the_whole_prompt_with_its_marker_line_removed(self):
        out = self.start_phase_one()
        marker_line = f"code-step-dispatch: {self.state()['runId']}/d1"
        prompt_without_marker = self.printed_prompt(out).replace(marker_line, "").rstrip()
        self.assertNotIn("code-step-dispatch", prompt_without_marker)

        reason = self.denial_reason(self.dispatch_hook(prompt_without_marker))

        fork_blocks = self.events_named("fork-block")
        self.assertIn("pass its whole text", reason)
        self.assertEqual([("d1", "prompt-deny")], [(block["dispatch"], block["kind"]) for block in fork_blocks])

    def test_dispatch_hook_leaves_other_agents_other_sessions_and_finished_runs_alone(self):
        self.assertEqual("", self.dispatch_hook("thin"))
        self.start_phase_one()
        self.assertEqual("", self.dispatch_hook("thin", subagent_type="Explore"))
        self.assertEqual("", self.dispatch_hook("thin", subagent_type="review-loop"))
        self.assertEqual("", self.dispatch_hook("thin", session="sess-other"))
        self.assertEqual([], self.events_named("fork-block"))

        self.finish_phase_one()

        self.assertEqual("done", self.state()["stage"])
        self.assertEqual("", self.dispatch_hook("thin"))

    def test_a_start_run_again_opens_a_new_run_and_after_coder_without_a_report_stops_as_before(self):
        first_out = self.start_phase_one()
        first_run = self.state()["runId"]

        rerun_out = self.start_phase_one("--restart")

        self.assertNotEqual(first_run, self.state()["runId"])
        dispatch_ids = [dispatch["id"] for dispatch in self.events_named("dispatch")]
        self.assertEqual(["d1"], dispatch_ids)
        self.assertIn("ACTION: dispatch", rerun_out)
        first_body = self.printed_prompt(first_out).rsplit("\n", 1)[0]
        rerun_body = self.printed_prompt(rerun_out).rsplit("\n", 1)[0]
        self.assertEqual(first_body, rerun_body)

        after_out = self.step("after-coder")

        self.assertIn("No coder report was saved", after_out)
        self.assertNotIn("ACTION: dispatch", after_out)

    def test_a_start_from_another_session_opens_a_new_run(self):
        self.start_phase_one()
        first_run = self.state()["runId"]
        state_path = self.repo / ".git/code-step/state.json"
        old_state = json.loads(state_path.read_text())
        old_state["dispatchAt"] = time.time() - 3 * 60 * 60
        state_path.write_text(json.dumps(old_state))
        self.env["CLAUDE_CODE_SESSION_ID"] = "sess-2"

        self.start_phase_one("--restart")

        dispatches = self.events_named("dispatch")
        self.assertNotEqual(first_run, self.state()["runId"])
        self.assertEqual([("d1", "sess-2")], [(dispatch["id"], dispatch["session_id"]) for dispatch in dispatches])

    # ---------- the ask-user action names the real question file ----------

    def real_question_file(self):
        return (self.repo / ".git/code-step/question.md").resolve()

    def test_the_ask_user_action_for_a_plan_impact_names_the_real_question_file(self):
        report = "PLAN-IMPACT:\n  assumed: A\n  found: B\n  changes: C\nPLAN-IMPACT: yes"

        out = self.coder_round(report)

        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"The question for the user is in {self.real_question_file()}. Hand back.", out)
        self.assertIn("## Question for the user", self.real_question_file().read_text())

    def test_the_ask_user_action_for_review_asks_names_the_real_question_file(self):
        self.coder_round()
        asks = '  - {question: "q1", change: "c1", file_line: "backend/src/orders.ts:1", gate: code-reviewer}'
        self.hook("review-loop", f"status: converged\niter: 1\nfixed: []\nask (for the user):\n{asks}")

        out = self.step("after-review")

        self.assertIn("ACTION: ask-user", out)
        self.assertIn(f"The question for the user is in {self.real_question_file()}. Hand back.", out)

    # ---------- a dispatch whose Agent call never left ----------

    def age_dispatches(self, seconds):
        events_file = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        rows = [json.loads(line) for line in events_file.read_text().splitlines()]
        for row in rows:
            row["ts"] -= seconds
        events_file.write_text("".join(json.dumps(row) + "\n" for row in rows))

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

    def test_a_launch_and_hand_back_from_a_session_whose_cwd_is_another_checkout_reach_the_run(self):
        # /code runs in a worktree while the session's cwd stays in another checkout, so the fork's Agent and
        # SubagentHandback hook events carry a cwd outside the run's repo.
        session_cwd = self.home / "session-checkout"
        self.make_other_checkout(session_cwd)
        out = self.start_phase_one()
        self.pass_coder_gate()
        (self.repo / "backend/src/orders.ts").write_text("export const o = 1\n")
        self.launch_agent(self.printed_prompt(out), cwd=str(session_cwd))
        self.age_dispatches(120)
        self.wait_env(1, "0.2")

        waited = self.step("after-coder")

        self.assertIn("ACTION: wait", waited)
        self.assertNotIn("no Agent call for it was launched", waited)
        report = "BEHAVIOR: orders exist\nWHY: backend/src/orders.ts 3-5 — order matters\nREVIEW: recommended"
        self.hand_back(report, "coder", "a1", cwd=str(session_cwd))
        reviewed = self.step("after-coder")
        self.assertIn("AGENT: review-loop", reviewed)

    def make_other_checkout(self, session_cwd):
        # A git checkout that holds the state of a finished run of this session, as the session's own cwd can.
        session_cwd.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=session_cwd, check=True)
        state_folder = session_cwd / ".git/code-step"
        state_folder.mkdir()
        (state_folder / "state.json").write_text(
            json.dumps({"stage": "done", "sessionId": self.SESSION, "runId": "old-run"}))

    def pin_session_repo(self, session=SESSION):
        pinned_sessions = self.home / ".claude/state/code-step-sessions"
        pinned_sessions.mkdir(parents=True, exist_ok=True)
        (pinned_sessions / session).write_text(str(self.repo) + "\n")

    def test_the_stop_hook_of_a_session_whose_cwd_is_another_checkout_blocks_the_fork(self):
        session_cwd = self.home / "session-checkout"
        self.make_other_checkout(session_cwd)
        self.start_phase_one()

        first = json.loads(self.stop_hook(cwd=str(session_cwd)))

        self.assertEqual("block", first["decision"])

    def test_an_early_fork_hand_back_from_a_session_whose_cwd_is_another_checkout_is_denied(self):
        session_cwd = self.home / "session-checkout"
        self.make_other_checkout(session_cwd)
        self.start_phase_one()

        self.hook("code-fork", "done", cwd=str(session_cwd), launched=False)

        blocks = self.events_named("fork-block")
        self.assertEqual(["handback-deny"], [block["kind"] for block in blocks])

    def test_a_thin_prompt_from_a_session_whose_cwd_is_another_checkout_is_denied(self):
        session_cwd = self.home / "session-checkout"
        self.make_other_checkout(session_cwd)
        self.start_phase_one()

        result = self.dispatch_hook("do the thing", cwd=str(session_cwd))

        self.assertIn("pass its whole text", self.denial_reason(result))

    def test_the_say_hook_of_a_session_whose_cwd_is_another_checkout_relays_the_run_text(self):
        session_cwd = self.home / "session-checkout"
        self.make_other_checkout(session_cwd)
        self.coder_round()
        expected = self.said().strip()
        event = {"cwd": str(session_cwd), "session_id": self.SESSION, "hook_event_name": "Stop"}

        result = run(self.repo, self.env, "say-hook", stdin=json.dumps(event))

        self.assertEqual({"systemMessage": expected}, json.loads(result.stdout))
        self.assertEqual("", self.said())

    def test_the_plan_hook_of_a_session_whose_cwd_is_another_checkout_checks_the_run_plan(self):
        session_cwd = self.home / "session-checkout"
        self.make_other_checkout(session_cwd)
        self.start_phase_one()
        item = "- [ ] **Check**: the orders pass - `RUN npx vitest run`"
        (self.repo / self.plan).write_text(self.bad_item_plan(item))
        bad_line = self.plan_text().splitlines().index(item) + 1
        plan_path = str(self.repo / self.plan)
        event = {"cwd": str(session_cwd), "session_id": self.SESSION, "tool_input": {"file_path": plan_path}}

        result = run(self.repo, self.env, "plan-hook", stdin=json.dumps(event))

        self.assertEqual(2, result.returncode)
        self.assertIn(f"{self.plan}:{bad_line}:", result.stderr)

    def test_a_launch_from_another_session_whose_cwd_is_another_checkout_is_not_logged(self):
        session_cwd = self.home / "session-checkout"
        session_cwd.mkdir()
        out = self.start_phase_one()
        self.pin_session_repo("sess-other")

        self.launch_agent(self.printed_prompt(out), session="sess-other", cwd=str(session_cwd))

        self.assertEqual([], self.events_named("launch"))

    def test_dispatch_hook_leaves_a_call_carrying_another_runs_marker_alone(self):
        self.start_phase_one()
        other_run_prompt = "code-step-dispatch: other-run/d1\nNot the saved prompt."

        result = self.dispatch_hook(other_run_prompt)

        self.assertEqual("", result)
        self.assertEqual([], self.events_named("fork-block"))

    def test_a_wait_on_a_fresh_dispatch_with_no_launch_keeps_waiting(self):
        self.begin_coder()
        self.wait_env(1, "0.2")

        out = self.step("after-coder")

        self.assertIn("ACTION: wait", out)

    def test_a_wait_past_the_cap_on_a_dispatch_with_no_launch_stops_and_does_not_print_it_again(self):
        self.begin_coder()
        self.age_dispatches(5000)
        self.set_state(dispatchAt=time.time() - 5000)
        self.wait_env(1, "0.2", waits=3)

        out = self.step("after-coder")

        self.assertIn("ACTION: stop", out)

    def test_a_wait_does_not_print_again_a_dispatch_made_for_another_agent(self):
        self.begin_coder()
        events_file = self.repo / ".git/code-step/runs" / self.state()["runId"] / "events.jsonl"
        rows = [json.loads(line) for line in events_file.read_text().splitlines()]
        for row in rows:
            if row["event"] == "dispatch":
                row["agent_type"] = "review-loop"
        events_file.write_text("".join(json.dumps(row) + "\n" for row in rows))
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
        self.wait_env(10, "0.2", waits=3)
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
        bad_line = text.splitlines().index("- [ ] **Check**: the orders pass - `RUN npx vitest run`") + 1

        result = self.plan_check(text)

        self.assertEqual(1, result.returncode)
        self.assertIn(f":{bad_line}:", result.stdout)
        self.assertIn("it starts with `RUN`", result.stdout)
        self.assertIn("one of three shapes", result.stdout)

    def test_plan_check_fails_a_misworded_automated_verification_heading_with_its_line(self):
        text = self.plan_text().replace("#### Automated Verification:", "#### Automated Checks (verification):", 1)
        bad_line = text.splitlines().index("#### Automated Checks (verification):") + 1

        result = self.plan_check(text)

        self.assertEqual(1, result.returncode)
        self.assertIn(f":{bad_line}:", result.stdout)
        self.assertIn("#### Automated Verification", result.stdout)

    def test_plan_check_fails_an_item_with_no_backticked_command(self):
        text = self.bad_item_plan("- [ ] **Check**: the orders pass, see the log")

        result = self.plan_check(text)

        self.assertEqual(1, result.returncode)
        self.assertIn("it has no backticked command and is not marked N/A", result.stdout)

    def test_plan_check_fails_a_box_that_diffs_a_moving_branch_name(self):
        for span in ("main...HEAD", "origin/master..HEAD", "main..feature"):
            with self.subTest(span=span):
                item = f"- [ ] **Scope-verified**: the branch changed files - `git diff --name-only {span}`"
                text = self.bad_item_plan(item)
                bad_line = text.splitlines().index(item) + 1

                result = self.plan_check(text)

                self.assertEqual(1, result.returncode)
                self.assertIn(f":{bad_line}:", result.stdout)
                self.assertIn("moving branch name", result.stdout)

    def test_plan_check_fails_a_closing_phase_box_that_diffs_a_moving_branch_name(self):
        item = "- [ ] **Scope-verified**: files changed - `git diff --name-only main...HEAD`"
        text = self.plan_text().replace("\nSweep.\n", f"\n**Success Criteria**:\n\n{item}\n")
        bad_line = text.splitlines().index(item) + 1

        result = self.plan_check(text)

        self.assertEqual(1, result.returncode)
        self.assertIn(f":{bad_line}:", result.stdout)

    def test_plan_check_passes_a_box_that_diffs_recorded_commits_and_fails_on_an_empty_diff(self):
        item = ("- [ ] **Scope-verified**: files changed - "
                "`test -n \"$(git diff --name-only abc1234..def5678)\"`")

        self.assertEqual(0, self.plan_check(self.bad_item_plan(item)).returncode)

    def test_plan_check_passes_items_marked_n_a_and_commands_on_the_path_or_in_the_repo(self):
        for item in (
            "- [ ] N/A - docs only",
            "- [ ] **Test-verified**: N/A on the machines; the suites stand.",
            "- [ ] **Check**: passes - `test -d backend`",
            "- [ ] **Check**: passes - `bash backend/package.json`",
        ):
            with self.subTest(item=item):
                self.assertEqual(0, self.plan_check(self.bad_item_plan(item)).returncode)

    def make_repo_script(self, relative_path, mode=0o755):
        script_file = self.repo / relative_path
        script_file.parent.mkdir(parents=True, exist_ok=True)
        script_file.write_text("#!/bin/sh\n")
        script_file.chmod(mode)
        return script_file

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

        self.assertFalse(code_step_boundary.starts_like_a_program_here("check-orders --all", self.repo))
        self.assertEqual(1, self.plan_check(text).returncode)

    def test_a_line_that_names_a_path_program_and_then_holds_the_real_command_gives_the_real_command(self):
        item = "- [ ] **Check**: with `ls -la` listing the files, `npm run build` exits 0."

        self.assertEqual("npm run build", code_step_boundary.verification_command(item))

    def test_a_program_of_the_path_needs_an_argument_to_be_a_fallback_command(self):
        self.assertIsNone(code_step_boundary.verification_command("- [ ] **Check**: the `ls` program lists them"))
        self.assertEqual("ls -la", code_step_boundary.verification_command("- [ ] **Check**: lists them - `ls -la`"))

    def test_claude_and_yes_are_never_a_fallback_command(self):
        for span in ("claude -p hello", "yes please", "FOO=1 claude --version"):
            with self.subTest(span=span):
                self.assertIsNone(code_step_boundary.verification_command(f"- [ ] **Check**: runs `{span}`"))

    def test_a_program_that_never_ends_or_waits_for_input_is_never_a_fallback_command(self):
        spans = ("watch -n 1 date", "top -b", "htop -d 5", "less notes.txt", "more notes.txt", "vi notes.txt",
                 "vim notes.txt", "nano notes.txt", "sleep 5", "tail -f app.log", "tail -F app.log",
                 "tail -n 5 -f app.log", "tail --follow app.log", "FOO=1 sleep 5", "/usr/bin/watch ls",
                 "tail -Fn5 app.log", "tail -fn20 x")

        with unittest.mock.patch.object(shutil, "which", return_value="/usr/bin/anything"):
            for span in spans:
                with self.subTest(span=span):
                    self.assertFalse(code_step_boundary.starts_like_a_program_here(span, self.repo))

    def test_tail_without_follow_is_a_fallback_command(self):
        with unittest.mock.patch.object(shutil, "which", return_value="/usr/bin/tail"):
            for span in ("tail -n 5 app.log", "tail app.log", "tail -c 20 app.log"):
                with self.subTest(span=span):
                    self.assertTrue(code_step_boundary.starts_like_a_program_here(span, self.repo))

    def test_claude_and_yes_are_refused_by_a_path_to_them_too(self):
        for span in ("/usr/bin/yes y", "/home/u/.local/bin/claude -p hi", "FOO=1 /usr/bin/yes y"):
            with self.subTest(span=span):
                self.assertFalse(code_step_boundary.starts_like_a_program_here(span, self.repo))
                self.assertIsNone(code_step_boundary.verification_command(f"- [ ] **Check**: runs `{span}`", self.repo))

    def test_a_file_outside_the_repo_is_not_a_repo_file_command(self):
        outside = self.repo.parent / "outside-tool"
        outside.write_text("#!/bin/sh\n")
        outside.chmod(0o755)
        self.addCleanup(outside.unlink)
        inside_link = self.repo / "link-tool"
        inside_link.symlink_to(outside)

        for span in (f"../{outside.name} --x", "./link-tool --x"):
            with self.subTest(span=span):
                self.assertFalse(code_step_boundary.starts_like_a_program_here(span, self.repo))

    def test_a_relative_path_is_never_looked_up_from_the_working_directory_as_a_path_program(self):
        with unittest.mock.patch.object(shutil, "which", return_value="/anywhere/tool"):
            self.assertFalse(code_step_boundary.starts_like_a_program_here("../tool --x", self.repo))
            self.assertFalse(code_step_boundary.starts_like_a_program_here("sub/tool --x", self.repo))
            self.assertTrue(code_step_boundary.starts_like_a_program_here("tool --x", self.repo))
            self.assertTrue(code_step_boundary.starts_like_a_program_here("/opt/bin/tool --x", self.repo))

    def test_a_file_inside_the_repo_by_a_path_that_goes_through_a_folder_is_a_repo_file_command(self):
        (self.repo / "bin").mkdir()
        tool = self.repo / "bin" / "tool"
        tool.write_text("#!/bin/sh\n")
        tool.chmod(0o755)

        for span in ("bin/tool --x", "./bin/tool --x", "bin/../bin/tool --x", f"{tool} --x"):
            with self.subTest(span=span):
                self.assertTrue(code_step_boundary.starts_like_a_program_here(span, self.repo))

    def test_the_write_time_check_applies_the_argument_and_program_rules_of_the_fallback(self):
        for item in ("- [ ] **Check**: the `ls` program lists them", "- [ ] **Check**: asks `claude -p hello`",
                     "- [ ] **Check**: runs `/usr/bin/yes y`"):
            with self.subTest(item=item):
                self.assertEqual(1, self.plan_check(self.bad_item_plan(item)).returncode)

    def test_a_repo_file_is_a_command_only_when_it_is_executable(self):
        check_file = self.make_repo_script("scripts/check-orders", 0o644)
        item = "- [ ] **Check**: the orders pass - `scripts/check-orders --all`"
        not_executable = code_step_boundary.verification_command(item, self.repo)
        check_file.chmod(0o755)
        executable = code_step_boundary.verification_command(item, self.repo)

        self.assertEqual((None, "scripts/check-orders --all"), (not_executable, executable))

    def test_the_item_problem_names_the_command_word_after_the_variable_assignments(self):
        item = "- [ ] **Check**: the orders pass - `FOO=1 RUN x`"
        problem = code_step_boundary.verification_item_problem(item, self.repo)

        self.assertIn("it starts with `RUN`", problem)
        self.assertNotIn("FOO=1", problem)

    # ---------- an item that CI or a person runs ----------

    def test_an_item_tagged_ci_verified_or_human_only_is_a_third_shape_in_any_case_or_markup(self):
        for item in ("- [ ] CI-verified: push and watch the pipeline", "- [ ] **CI-verified**: the pipeline runs it",
                     "- [ ] **ci-verified** - `gh run watch`", "- [ ] Human-only: look at the page",
                     "- [x] **Human-only:** open it", "- [ ] **Test-verified**: HUMAN-ONLY, a person looks"):
            with self.subTest(item=item):
                self.assertIsNotNone(code_step.plan_format.deferred_verification_tag(item))
                self.assertIsNone(code_step_boundary.verification_item_problem(item, self.repo))
                self.assertEqual(0, self.plan_check(self.bad_item_plan(item)).returncode)

    def test_an_item_that_only_mentions_ci_verified_after_other_words_is_not_tagged(self):
        item = "- [ ] **Check**: the orders pass, not CI-verified yet"

        self.assertIsNone(code_step.plan_format.deferred_verification_tag(item))
        self.assertIsNotNone(code_step_boundary.verification_item_problem(item, self.repo))

    def test_an_item_tagged_for_ci_or_a_person_is_never_run_even_with_a_command_in_it(self):
        section = ("#### Automated Verification:\n\n- [ ] **CI-verified**: the pipeline runs `touch ran-by-code-step`\n"
                   "- [ ] Human-only: look at the page\n\n#### Manual Verification:\n")

        self.assertEqual(([], [], []), code_step_boundary.run_verification_commands(self.repo, section))
        self.assertFalse((self.repo / "ran-by-code-step").exists())

    def test_a_not_applicable_item_is_never_run_even_with_a_command_in_it(self):
        section = (
            "#### Automated Verification:\n\n- [ ] N/A — nothing to run, not `touch ran-na-item`\n\n#### Manual "
            "Verification:\n"
        )

        self.assertEqual(([], [], []), code_step_boundary.run_verification_commands(self.repo, section))
        self.assertFalse((self.repo / "ran-na-item").exists())

    def test_deferred_items_are_listed_with_their_tag_in_file_order(self):
        section = ("#### Automated Verification:\n\n- [ ] **CI-verified**: the pipeline runs it\n"
                   "- [ ] **Check**: runs - `true now`\n- [ ] Human-only: look at the page\n")

        self.assertEqual([("CI-verified", "**CI-verified**: the pipeline runs it"),
                          ("human-only", "Human-only: look at the page")],
                         code_step_boundary.deferred_verification_items(section))

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
        shape = code_step_boundary.VERIFICATION_ITEM_SHAPE

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
        bad_line = self.plan_text().splitlines().index(item) + 1

        out = self.start_phase_one()

        self.assertIn("ACTION: stop", out)
        self.assertNotIn("AGENT: coder", out)
        self.assertIn(f"{self.plan}:{bad_line}:", out)

    def test_the_plan_hook_exits_two_on_an_item_that_cannot_run(self):
        self.start_phase_one()
        item = "- [ ] **Check**: the orders pass - `RUN npx vitest run`"
        (self.repo / self.plan).write_text(self.bad_item_plan(item))
        bad_line = self.plan_text().splitlines().index(item) + 1
        event = {"cwd": str(self.repo), "tool_input": {"file_path": str(self.repo / self.plan)}}

        result = run(self.repo, self.env, "plan-hook", stdin=json.dumps(event))

        self.assertEqual(2, result.returncode)
        self.assertIn(f"{self.plan}:{bad_line}:", result.stderr)

    def coder_round_then_edit_verification(self, lines):
        # The plan is edited after the phase starts, as a coder would: `start` stops on an item that cannot run. The
        # edit is taken as the phase text the coder worked from, so it does not send a second coder for added lines.
        self.begin_coder()
        self.replace_phase_one_verification(lines)
        self.set_state(phaseText=plan_format.phase_text(self.plan_text().splitlines(), "1"))
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
        plan_dir = self.repo / "docs/plans" / folder
        plan_dir.mkdir(parents=True)
        (plan_dir / "spec.md").write_text(
            f"# Other\n\n## Phase 1: X\n\n#### Automated Verification:\n\n"
            f"- [ ] **Test-verified**: passes - `{command}`\n\n#### Manual Verification:\n"
        )

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

    def test_the_coder_gate_runs_its_commands_with_the_gate_variables_of_the_plan_alone(self):
        self.set_verification("- [ ] **Env**: passes - `GATE_X=1 npx vitest run`")
        self.add_plan_with_gate("other", 'GATE_Y="two words" cargo test')

        out = self.start_phase_one()

        gate = json.loads((self.repo / ".git/coder-gate.json").read_text())
        self.assertEqual({"GATE_X": "1"}, gate["env"])
        self.assertIn("With: GATE_X=1.", out)

    def test_a_plan_dispatch_names_only_its_own_gate_values_and_none_another_plan_sets(self):
        self.set_verification("- [ ] **Env**: passes - `GATE_PORT=5001 npx vitest run`")
        self.add_plan_with_gate("other", "GATE_PORT=6002 GATE_PROJECT=other cargo test")

        out = self.start_phase_one()

        prompt = self.printed_prompt(out)
        self.assertIn("gate-env: GATE_PORT=5001", prompt)
        self.assertNotIn("6002", prompt)
        self.assertNotIn("GATE_PROJECT", prompt)

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
        review_out = self.step("after-coder")

        self.assertIn("AGENT: review-loop", review_out)
        self.assertIn("gate-env: GATE_X=1", self.printed_prompt(review_out))


def frontmatter_value(markdown_path, key):
    """The value of `key:` in the frontmatter of a skill or agent file, or None when the frontmatter has no such key."""
    frontmatter = markdown_path.read_text().split("---")[1]
    for line in frontmatter.splitlines():
        name, _, value = line.partition(":")
        if name.strip() == key:
            return value.strip()
    return None


class CodeForkToolsTest(unittest.TestCase):
    # `allowed-tools` in a skill only pre-approves tools; the forked agent's own definition decides which it has.

    def test_the_code_skill_forks_into_the_agent_the_hooks_watch(self):
        skill = REAL_CLAUDE / "skills" / "code" / "SKILL.md"

        self.assertEqual(code_step_core.FORK_AGENT_TYPE, frontmatter_value(skill, "agent"))

    def test_the_code_fork_agent_has_no_tool_that_edits_a_file(self):
        agent = REAL_CLAUDE / "agents" / f"{code_step_core.FORK_AGENT_TYPE}.md"
        disallowed = frontmatter_value(agent, "disallowedTools") or ""

        disallowed_tools = {tool.strip() for tool in disallowed.split(",")}
        self.assertLessEqual({"Edit", "Write", "NotebookEdit"}, disallowed_tools)


if __name__ == "__main__":
    unittest.main()
