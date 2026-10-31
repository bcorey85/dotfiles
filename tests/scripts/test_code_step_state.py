"""code_step_state.py: the record of one /code run loads from state.json only as a code-step of this version wrote it,
and writes back what it loaded. A verb writes the record once, at its end, or not at all.

run: python3 -m unittest test_code_step_state
"""
import contextlib
import io
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

for folder in (toolkit_paths.LIB_DIR, toolkit_paths.REVIEW_DIR, toolkit_paths.CODE_DIR):
    sys.path.insert(0, str(folder))
import code_step_core  # noqa: E402
import code_step_state  # noqa: E402
import code_step_store  # noqa: E402

# The state file of a run in progress, with every key the code-step before the typed record wrote except the stop
# record's waitAt, which loads and is dropped.
CURRENT_STATE = {
    "stage": "stopped",
    "stop": {"kind": "coder-resumable", "at": 1761800000.5, "agentId": "a1", "coderStage": "asks-coder"},
    "plan": "docs/plans/ABC-1-orders/spec.md",
    "phase": "2",
    "title": "Totals add up",
    "lane": "code",
    "branch": "ABC-1-orders",
    "modifier": "+deep",
    "risk": "high",
    "headless": False,
    "onlyPhase": "2",
    "runNotes": "use the fake clock",
    "sessionId": "s1",
    "runId": "20261030-101500-ab12",
    "startedAt": 1761790000.0,
    "gateCommands": ["npx vitest run backend/src/orders.test.ts"],
    "baseline": {"backend/src/orders.ts": "3f2a"},
    "baseHead": "5a5307dd",
    "phaseText": "## Phase 2: totals\n\nAdd the totals.\n",
    "criteriaGuard": {"file": "docs/plans/ABC-1-orders/criteria.md", "hash": "9c1d"},
    "guidance": ["keep the fake clock"],
    "snapshot": {"asks": {"backend/src/orders.ts": "7e4b"}},
    "dispatchAt": 1761800000.0,
    "reviewScriptPid": 4242,
    "reviewScriptLog": ".git/code-step/review-loop-script.log",
    "lastReviewPrompt": "review phase 2",
    "files": ["backend/src/orders.ts"],
    "behavior": ["totals add up"],
    "why": {"backend/src/orders.ts": "adds the totals"},
    "summaryWhy": {"backend/src/orders.ts": "adds the totals"},
    "testsRun": "npx vitest run backend/src/orders.test.ts",
    "flagged": ["an open question"],
    "exception": False,
    "coderStage": "coder",
    "changes": {"backend/src/orders.ts": "+3 -1"},
    "gateLines": "hand-back gate: pass",
    "handledImpacts": ["the header stays"],
    "correctionCoder": False,
    "iter": 2,
    "spec_iter": 1,
    "reviewStatus": "converged",
    "reviewRan": True,
    "structurePassSkipped": False,
    "checkCreated": ["dist/out.js"],
    "checkChanged": ["generated.ts"],
    "checkRewroteEdited": ["edited.ts"],
    "carriedFindings": [{"finding": "an unchecked total", "file_line": "backend/src/orders.ts:4"}],
    "capCarried": False,
    "blockerCarried": False,
    "planImpact": "none",
    "priorIssues": ["an unchecked total"],
    "asks": [{"finding": "the retry loop has no cap", "file_line": "src/queue.py:40", "question": "cap it?"}],
    "askIds": {"ask-1": "f1"},
    "askIdsHandback": "h1",
    "acceptedAsks": [{"finding": "the retry loop has no cap", "outcome": "accepted"}],
    "asksAlso": "",
    "rulings": {"f1": "accepted"},
    "pendingCorrection": {"ask": "f1", "note": "undo it"},
    "askRounds": [["totals add up"]],
    "impact": "the header moves",
    "ruling": {"decision": "adopt", "by": "user", "at": "2026-10-30 10:15", "text": "adopt it"},
    "autoAdvance": True,
    "commitFiles": ["backend/src/orders.ts"],
    "commitLine": "git commit -m 'ABC-1: totals add up' -- backend/src/orders.ts",
}


class StateFileTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.state_dir = pathlib.Path(temp_dir.name)

    def load(self, saved_state):
        (self.state_dir / "state.json").write_text(json.dumps(saved_state))
        return code_step_store.read_state_file(self.state_dir)

    def test_the_state_file_of_a_run_in_progress_writes_back_with_the_no_review_key(self):
        state = self.load(CURRENT_STATE)

        self.assertEqual(code_step_state.Stage.STOPPED, state.stage)
        self.assertEqual(code_step_state.StopKind.CODER_RESUMABLE, state.stop.kind)
        self.assertEqual(("a1", "asks-coder"), (state.stop.agent_id, state.stop.coder_stage))
        self.assertEqual((2, 1, 4242), (state.iter, state.spec_iter, state.review_script_pid))
        written_text = json.dumps(state.to_json())
        self.assertEqual({**CURRENT_STATE, "noReview": False}, json.loads(written_text))

    def test_a_state_file_without_the_no_review_key_loads_with_review_on(self):
        state = self.load(CURRENT_STATE)

        self.assertIs(False, state.no_review)

    def test_a_state_file_this_code_step_cannot_read_stops_the_load(self):
        unreadable_states = [
            ("unknown stage", {**CURRENT_STATE, "stage": "paused"}),
            ("unknown stop kind", {**CURRENT_STATE, "stop": {"kind": "gone", "at": 1.5}}),
            ("unknown stop key", {**CURRENT_STATE, "stop": {"kind": "coder-cap", "at": 1.5, "reason": "x"}}),
            ("no stage", {"phase": "2"}),
            ("not an object", ["stopped"]),
        ]
        for label, saved_state in unreadable_states:
            with self.subTest(label), self.assertRaises(code_step_state.StateFileError):
                self.load(saved_state)

    def test_a_stage_set_on_the_record_is_a_stage_and_an_unknown_one_raises(self):
        state = code_step_state.RunState("coder")

        state.stage = "asks"

        self.assertIs(code_step_state.Stage.ASKS, state.stage)
        with self.assertRaises(ValueError):
            state.stage = "paused"

    def test_the_first_wait_on_a_resumed_coder_is_logged_at_the_time_the_cap_counts_from(self):
        subprocess.run(["git", "init", "-q", str(self.state_dir)], check=True)
        stop = code_step_state.Stop(code_step_state.StopKind.CODER_RESUMABLE, 100.0, agent_id="a1")
        state = code_step_state.RunState(code_step_state.Stage.STOPPED, stop=stop, run_id="r1", session_id="s1")

        cap_start = code_step_core.wait_clock_start(self.state_dir, state, since=150.0, wait_started=200.0)

        first_waits = code_step_core.read_events(self.state_dir, "r1")
        self.assertEqual([cap_start], [event["ts"] for event in first_waits])


class VerbTransactionTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)

        state_dirs = unittest.mock.patch.dict(code_step_store.STATE_DIRS, clear=True)
        state_dirs.start()
        self.addCleanup(state_dirs.stop)

        code_step_core.save_state(self.repo, code_step_state.RunState("coder"))
        self.state_path = code_step_store.state_file(self.repo)
        self.saved_text = self.state_path.read_text()
        self.printed = io.StringIO()

    def run_verb(self, verb_body, *args):
        with contextlib.redirect_stdout(self.printed), code_step_core.verb_transaction():
            verb_body(*args)

    def saved_stage(self):
        saved_state = json.loads(self.state_path.read_text())
        return saved_state["stage"]

    def save_review_stage(self):
        state = code_step_core.load_state(self.repo)
        state.stage = "review"
        code_step_core.save_state(self.repo, state)

    def save_then_exit(self, exit_code):
        self.save_review_stage()
        print("ACTION: wait")
        sys.exit(exit_code)

    def test_a_verb_that_fails_part_way_writes_nothing_and_prints_nothing_it_held(self):
        def save_then_fail():
            self.save_review_stage()
            print("ACTION: dispatch")
            raise RuntimeError("the verb broke")

        with self.assertRaises(RuntimeError):
            self.run_verb(save_then_fail)

        self.assertEqual(self.saved_text, self.state_path.read_text())
        self.assertEqual("", self.printed.getvalue())

    def test_a_load_inside_a_verb_sees_its_save_and_the_disk_changes_only_at_its_end(self):
        stages_inside = []

        def save_then_load():
            self.save_review_stage()
            loaded_state = code_step_core.load_state(self.repo)
            stages_inside.extend([loaded_state.stage, self.saved_stage()])
            print("ACTION: wait")

        self.run_verb(save_then_load)

        self.assertEqual([code_step_state.Stage.REVIEW, "coder"], stages_inside)
        self.assertEqual("review", self.saved_stage())
        self.assertEqual("ACTION: wait\n", self.printed.getvalue())

    def test_a_verb_that_exits_cleanly_writes_and_prints_and_one_that_exits_with_an_error_does_neither(self):
        exits = [(0, "review", "ACTION: wait\n"), (None, "review", "ACTION: wait\n"),
                 ("code-step: the packet broke", "coder", "")]
        for exit_code, stage_after, printed_after in exits:
            with self.subTest(exit_code=exit_code):
                code_step_core.save_state(self.repo, code_step_state.RunState("coder"))
                self.printed = io.StringIO()

                with self.assertRaises(SystemExit):
                    self.run_verb(self.save_then_exit, exit_code)

                self.assertEqual(stage_after, self.saved_stage())
                self.assertEqual(printed_after, self.printed.getvalue())

    def test_a_state_file_the_verb_drops_goes_only_at_its_end(self):
        seen_inside = []

        def drop():
            code_step_store.drop_state(self.repo)
            seen_inside.append(code_step_core.load_state(self.repo))
            seen_inside.append(self.state_path.exists())

        self.run_verb(drop)

        self.assertEqual([None, True], seen_inside)
        self.assertFalse(self.state_path.exists())

    def test_a_state_file_the_verb_drops_goes_even_when_another_verb_rewrote_it_meanwhile(self):
        def drop_across_a_rewrite():
            code_step_store.drop_state(self.repo)
            self.state_path.write_text(json.dumps({"stage": "review"}))
            print("ACTION: stop")

        self.run_verb(drop_across_a_rewrite)

        self.assertFalse(self.state_path.exists())
        self.assertEqual("ACTION: stop\n", self.printed.getvalue())

    def test_a_state_file_an_abort_removed_while_the_verb_ran_stays_removed_and_the_verb_stops(self):
        def save_across_an_abort():
            state = code_step_core.load_state(self.repo)
            self.state_path.unlink()
            state.stage = "review"
            code_step_core.save_state(self.repo, state)
            print("ACTION: dispatch")

        self.run_verb(save_across_an_abort)

        self.assertFalse(self.state_path.exists())
        self.assertIn("ACTION: stop", self.printed.getvalue())
        self.assertIn("changed while this verb ran", self.printed.getvalue())
        self.assertNotIn("ACTION: dispatch", self.printed.getvalue())


if __name__ == "__main__":
    unittest.main()
