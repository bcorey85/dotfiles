"""Checks that a /code phase stays open when its review loop did not converge, and that ask outcomes reach later passes.

run: python3 tests/scripts/test_code_step_open_phase.py
"""
import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = pathlib.Path(os.environ.get("CODE_STEP_SCRIPTS_DIR") or REPO_ROOT / "claude" / ".claude" / "scripts")
for folder in ("lib", "review", "code"):
    sys.path.insert(0, str(SCRIPTS_DIR / folder))
loaded = importlib.util.spec_from_file_location("code_step", SCRIPTS_DIR / "code" / "code_step.py")
code_step = importlib.util.module_from_spec(loaded)
loaded.loader.exec_module(code_step)
import code_step_boundary
import code_step_core
import code_step_review
import code_step_start

PLAN = "docs/plans/orders.md"


def stored_handback_that_says_clean():
    # The shared hand-back store still holds an earlier converged hand-back for the session.
    return types.SimpleNamespace(CLEAN_STATUSES=("converged", "deferred"), false_clean_reason=lambda session: None)


def stored_handback_reader():
    return stored_handback_that_says_clean(), None


class TempRepo(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "--template=", str(self.repo)], check=True, capture_output=True)
        self.home = pathlib.Path(temp_dir.name) / "home"
        self.home.mkdir()
        home_patch = mock.patch.object(pathlib.Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def run_quietly(self, function, *args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = function(*args)
        return result, out.getvalue()


class PhaseStaysOpenWhenTheReviewDidNotConverge(TempRepo):
    def mark(self, review_status):
        state = {"stage": "review", "plan": None, "phase": None, "sessionId": "s1"}
        if review_status:
            state["reviewStatus"] = review_status
        recorded = []
        with mock.patch.object(code_step_boundary, "load_handback", stored_handback_reader), \
                mock.patch.object(code_step_boundary.reviewed_tree, "record_reviewed",
                                  lambda session, repo: recorded.append(session)), \
                mock.patch.object(code_step_boundary, "session_pin", lambda: "s1"):
            marked, out = self.run_quietly(code_step_boundary.mark_review_gate_clean, self.repo, state)
        return marked, out, state, recorded

    def gate_files(self):
        gate_dir = self.home / ".claude" / "state" / "review-gate"
        return list(gate_dir.glob("*")) if gate_dir.exists() else []

    def test_a_loop_that_ended_on_a_plan_impact_question_marks_nothing_and_records_no_fingerprint(self):
        marked, out, state, recorded = self.mark("plan-impact")

        self.assertFalse(marked)
        self.assertEqual([], recorded)
        self.assertEqual([], self.gate_files())
        self.assertIn("ACTION: stop", out)
        self.assertIn("phase stays open", out)
        self.assertIn("plan-impact", out)
        self.assertEqual("stopped", state["stage"])

    def test_a_loop_that_hit_its_cap_marks_nothing(self):
        marked, _out, _state, recorded = self.mark("cap-reached")

        self.assertFalse(marked)
        self.assertEqual([], recorded)

    def test_a_converged_loop_still_marks_the_gate_and_records_the_fingerprint(self):
        marked, _out, _state, recorded = self.mark("converged")

        self.assertTrue(marked)
        self.assertEqual(["s1"], recorded)
        self.assertEqual(["s1"], [path.name for path in self.gate_files()])

    def test_finish_phase_stops_and_commits_nothing_after_a_non_converged_loop(self):
        state = {"stage": "review", "plan": None, "phase": None, "sessionId": "s1", "reviewStatus": "plan-impact"}
        with mock.patch.object(code_step_boundary, "load_handback", stored_handback_reader), \
                mock.patch.object(code_step_boundary, "finish_planless") as finish_planless, \
                mock.patch.object(code_step_boundary, "save_state"):
            _result, out = self.run_quietly(code_step_boundary.finish_phase, self.repo, state)

        finish_planless.assert_not_called()
        self.assertIn("phase stays open", out)
        self.assertNotEqual("done", state["stage"])


class AskOutcomesReachLaterPasses(TempRepo):
    ASK = types.MappingProxyType({
        "finding": "the retry loop has no cap", "file_line": "src/queue.py:40", "question": "cap it?",
        "gate": "code-reviewer", "class": "bug"})

    def rule(self, outcome, change=None):
        state = {"stage": "asks", "plan": PLAN, "phase": "2", "asks": [dict(self.ASK)], "lane": "code", "iter": 1}
        change_args = ["--change", change] if change else []
        with mock.patch.object(code_step_review, "log_ask_outcomes"), \
                mock.patch.object(code_step_review, "apply_asks_or_finish") as apply:
            code_step_review.command_asks_done(self.repo, state, [outcome, *change_args])
        apply.assert_called_once()

    def handoff(self, plan=PLAN):
        state = {"plan": plan, "phase": "4", "files": [], "changes": {}, "why": {}, "testsRun": "none",
                 "flagged": [], "iter": 0}
        return code_step_review.handoff_block(self.repo, state)

    def test_a_ruled_ask_is_in_the_review_handoff_of_a_later_phase(self):
        self.rule("rejected")

        handoff = self.handoff()

        self.assertIn("ruled-asks:", handoff)
        self.assertIn("the retry loop has no cap", handoff)
        self.assertIn("src/queue.py:40", handoff)
        self.assertIn("rejected", handoff)

    def test_a_modified_ask_carries_the_users_change(self):
        self.rule("modified", change="cap it at five tries")

        self.assertIn("cap it at five tries", self.handoff())

    def test_a_multi_line_ask_is_one_ruled_asks_entry_with_its_outcome(self):
        self.ASK = {**self.ASK, "question": "which cap holds?\nthe plan says three\nthe ruling says five"}
        self.rule("rejected")

        ruled_block = self.handoff().split("  ruled-asks:\n", 1)[1].split("\n  tests-run:", 1)[0]

        self.assertEqual(["    - the retry loop has no cap - which cap holds? the plan says three the ruling says five "
                          "(src/queue.py:40): rejected, Phase 2"], ruled_block.splitlines())

    def test_the_question_for_the_user_indents_a_multi_line_asks_folded_lines_under_its_number(self):
        ask = {**self.ASK, "question": "which cap holds?\nthe plan says three"}

        self.assertEqual(["1. the retry loop has no cap - which cap holds?", "   the plan says three"],
                         code_step_review.numbered_ask_lines([ask]))

    def test_the_proposed_change_indents_its_later_lines_under_the_number(self):
        ask = {**self.ASK, "change": "cap at 3\nlog the cap"}

        self.assertEqual(["1. the retry loop has no cap - cap it?", "   Proposed change: cap at 3", "   log the cap"],
                         code_step_review.numbered_ask_lines([ask]))

    def test_the_closing_refactor_phase_prompt_lists_the_ruled_ask(self):
        self.rule("rejected")

        _result, out = self.run_quietly(code_step_start.emit_closing_skill, self.repo, PLAN, "4", "Refactor",
                                        "refactor", "", None)

        self.assertIn("Asks already ruled in this run", out)
        self.assertIn("the retry loop has no cap", out)

    def test_a_run_with_no_ruled_ask_prints_no_ruled_asks_section(self):
        self.assertNotIn("ruled-asks", self.handoff())
        _result, out = self.run_quietly(code_step_start.emit_closing_skill, self.repo, PLAN, "4", "Refactor",
                                        "refactor", "", None)
        self.assertNotIn("already ruled", out)

    def test_another_plan_does_not_see_the_ruling(self):
        self.rule("rejected")

        self.assertNotIn("ruled-asks", self.handoff(plan="docs/plans/other.md"))

    def test_the_outcome_is_kept_in_the_code_step_state_directory(self):
        self.rule("accepted")

        self.assertTrue((code_step_core.state_dir(self.repo) / "ruled-asks.json").is_file())


if __name__ == "__main__":
    unittest.main()
