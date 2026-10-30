"""code_step_state.py: the record of one /code run loads from state.json only as a code-step of this version wrote it,
and writes back what it loaded.

run: python3 -m unittest test_code_step_state
"""
import json
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

for folder in (toolkit_paths.LIB_DIR, toolkit_paths.REVIEW_DIR, toolkit_paths.CODE_DIR):
    sys.path.insert(0, str(folder))
import code_step_core  # noqa: E402
import code_step_state  # noqa: E402

# The state file of a run in progress, with every key the code-step before the typed record wrote.
CURRENT_STATE = {
    "stage": "stopped",
    "stop": {"kind": "coder-resumable", "at": 1761800000.5, "agentId": "a1", "coderStage": "asks-coder",
             "waitAt": 1761800100.25},
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
    "askIds": ["f1"],
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
        return code_step_core.read_state_file(self.state_dir)

    def test_the_state_file_of_a_run_in_progress_loads_and_writes_back_unchanged(self):
        state = self.load(CURRENT_STATE)

        self.assertEqual(code_step_state.Stage.STOPPED, state.stage)
        self.assertEqual(code_step_state.StopKind.CODER_RESUMABLE, state.stop.kind)
        self.assertEqual(("a1", "asks-coder", 1761800100.25),
                         (state.stop.agent_id, state.stop.coder_stage, state.stop.wait_at))
        self.assertEqual((2, 1, 4242), (state.iter, state.spec_iter, state.review_script_pid))
        written_text = json.dumps(state.to_json())
        self.assertEqual(CURRENT_STATE, json.loads(written_text))

    def test_a_stop_record_with_no_kind_loads_and_writes_its_kind_back(self):
        state = self.load({"stage": "stopped", "stop": {"kind": None, "at": 1.5}})

        self.assertIsNone(code_step_core.stop_kind(state))
        self.assertEqual({"kind": None, "at": 1.5}, state.to_json()["stop"])

    def test_a_key_the_record_does_not_name_stops_the_load_and_is_named(self):
        old_format = {**CURRENT_STATE, "stopReason": "coder-cap"}

        with self.assertRaises(code_step_state.StateFileError) as raised:
            self.load(old_format)

        self.assertIn("does not know: stopReason", str(raised.exception))

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


if __name__ == "__main__":
    unittest.main()
