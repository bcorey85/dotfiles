"""Checks for how code-step logs ask outcomes: the argv it hands log-review-finding.

run: python3 tests/scripts/test_code_step_asks.py
"""
import contextlib
import importlib.util
import io
import os
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = pathlib.Path(os.environ.get("CODE_STEP_SCRIPTS_DIR") or REPO_ROOT / "claude" / ".claude" / "scripts")
for folder in ("lib", "review", "code"):
    sys.path.insert(0, str(SCRIPTS_DIR / folder))
loaded = importlib.util.spec_from_file_location("code_step", SCRIPTS_DIR / "code" / "code_step.py")
code_step = importlib.util.module_from_spec(loaded)
loaded.loader.exec_module(code_step)
loaded_review_fix = importlib.util.spec_from_file_location("review_fix", SCRIPTS_DIR / "review" / "review_fix.py")
review_fix = importlib.util.module_from_spec(loaded_review_fix)
loaded_review_fix.loader.exec_module(review_fix)
import code_step_review
import review_asks

# log-review-finding mints ids as 16 lowercase hex chars; review-fix logs no other shape.
MINTED_FINDING_ID = "0123456789abcdef"
OTHER_MINTED_FINDING_ID = "fedcba9876543210"


def ask_item(**overrides):
    item = {"finding": "a finding", "file_line": "src/widget.py:12", "question": "keep it?",
            "gate": "code-reviewer", "class": "bug", "finding_id": MINTED_FINDING_ID}
    item.update(overrides)
    return item


class LogAskOutcomes(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.logger_result = (0, "")
        self.original_run_command = review_asks.run_command
        self.original_git_output = code_step_review.git_output
        review_asks.run_command = lambda command, cwd, **_: self.calls.append(command) or self.logger_result
        code_step_review.git_output = lambda *_: "some-branch"

    def tearDown(self):
        review_asks.run_command = self.original_run_command
        code_step_review.git_output = self.original_git_output

    def log(self, asks, outcomes, phase="1"):
        state = {"asks": asks, "lane": "code", "phase": phase, "iter": 2}
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code_step_review.log_ask_outcomes(pathlib.Path("/tmp/some-repo"), state, outcomes)
        return stderr.getvalue()

    def test_argv_carries_finding_id_and_no_free_text(self):
        stderr = self.log([ask_item()], ["accepted"])

        self.assertEqual("", stderr)
        self.assertEqual(len(self.calls), 1)
        argv = self.calls[0]
        self.assertIn(f"finding_id={MINTED_FINDING_ID}", argv)
        self.assertIn("ask_outcome=accepted", argv)
        self.assertIn("actioned=ask", argv)
        self.assertIn("disposition=ask", argv)
        for expected in ("gate=code-reviewer", "class=bug", "lane=code", "scope=phase", "phase=1", "iter=2",
                         "file=src/widget.py", "line=12"):
            self.assertIn(expected, argv)
        self.assertFalse([word for word in argv if word.startswith("desc=")])
        self.assertFalse([word for word in argv if word.startswith("repo=")])

    def test_run_with_no_phase_sends_no_phase(self):
        self.log([ask_item()], ["accepted"], phase=None)

        self.assertEqual(len(self.calls), 1)
        self.assertFalse([word for word in self.calls[0] if word.startswith("phase=")])
        self.assertIn("iter=2", self.calls[0])

    def logged_finding_ids(self):
        return [word.removeprefix("finding_id=") for call in self.calls for word in call
                if word.startswith("finding_id=")]

    def test_ask_without_finding_id_logs_its_outcome_under_a_new_id_and_says_so(self):
        stderr = self.log([ask_item(finding_id=None), ask_item(finding_id=OTHER_MINTED_FINDING_ID)],
                          ["rejected", "modified"])

        new_finding_id, kept_finding_id = self.logged_finding_ids()
        self.assertRegex(new_finding_id, r"^[0-9a-f]{16}$")
        self.assertEqual(kept_finding_id, OTHER_MINTED_FINDING_ID)
        self.assertIn("ask_outcome=rejected", self.calls[0])
        self.assertIn(f"ask outcome without a valid finding_id (no finding_id), logged under new finding_id "
                      f"{new_finding_id}", stderr)

    def test_an_ask_whose_finding_id_is_not_a_minted_id_is_logged_under_a_new_id(self):
        not_ids = [
            ("the word none", "none"),
            ("prose with a space", "not logged (no id was printed)"),
            ("a short hex id", "abc123"),
            ("an upper case hex id", MINTED_FINDING_ID.upper()),
        ]
        for label, not_an_id in not_ids:
            with self.subTest(label):
                self.calls.clear()
                stderr = self.log([ask_item(finding_id=not_an_id), ask_item(finding_id=OTHER_MINTED_FINDING_ID)],
                                  ["accepted", "rejected"])

                new_finding_id, kept_finding_id = self.logged_finding_ids()
                self.assertRegex(new_finding_id, r"^[0-9a-f]{16}$")
                self.assertNotEqual(not_an_id, new_finding_id)
                self.assertEqual(OTHER_MINTED_FINDING_ID, kept_finding_id)
                self.assertEqual(1, stderr.count("logged under new finding_id"))
                self.assertIn(f"ignored {not_an_id!r}", stderr)

    def test_asks_whose_finding_id_is_the_word_none_each_get_their_own_new_id(self):
        stderr = self.log([ask_item(finding_id="none"), ask_item(finding_id="none")], ["accepted", "rejected"])

        first_new_id, second_new_id = self.logged_finding_ids()
        self.assertNotEqual(first_new_id, second_new_id)
        self.assertEqual(stderr.count("ignored 'none'"), 2)

    def test_a_new_id_whose_log_call_fails_is_named_as_not_logged(self):
        self.logger_result = (1, "ledger write refused")

        stderr = self.log([ask_item(finding_id=None)], ["accepted"])

        self.assertIn("not logged: log-review-finding exited 1", stderr)
        self.assertNotIn("logged under new finding_id", stderr)

    def test_a_logger_that_fails_is_named_on_stderr_with_the_id_and_its_output(self):
        self.logger_result = (1, "log-review-finding: field finding_id has a space")

        stderr = self.log([ask_item()], ["accepted"])

        self.assertEqual(len(self.calls), 1)
        self.assertIn(f"ask outcome for finding_id {MINTED_FINDING_ID} not logged", stderr)
        self.assertIn("exited 1", stderr)
        self.assertIn("field finding_id has a space", stderr)

    def test_a_missing_hand_back_reader_logs_nothing_and_says_why(self):
        original = code_step_review.load_handback
        code_step_review.load_handback = lambda: (None, "handback.py could not be imported (boom)")
        try:
            stderr = self.log([ask_item()], ["accepted"])
        finally:
            code_step_review.load_handback = original

        self.assertEqual(self.calls, [])
        self.assertIn("ask outcomes not logged", stderr)
        self.assertIn("boom", stderr)

    def test_a_plan_impact_ask_logs_no_outcome_row_as_review_does(self):
        plan_impact_ask = ask_item(finding="PLAN-IMPACT: the plan names the wrong table", finding_id=None)

        stderr = self.log([plan_impact_ask, ask_item()], ["accepted", "rejected"])

        self.assertEqual([MINTED_FINDING_ID], self.logged_finding_ids())
        self.assertIn("ask_outcome=rejected", self.calls[0])
        self.assertEqual("", stderr)


class ReviewFixLogAskOutcome(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.original_run_command = review_asks.run_command
        review_asks.run_command = lambda command, cwd=None: self.calls.append(command) or (0, "")
        self.state = {"branch": "some-branch", "lane": "fix", "scope": "diff", "iter": 1, "packet_id": "stdin:test"}

    def tearDown(self):
        review_asks.run_command = self.original_run_command

    def test_argv_carries_finding_id_and_no_free_text(self):
        review_asks.log_ask_outcome(review_fix.ASK_LOGGER, self.state, ask_item(), "accepted", "user")

        self.assertEqual(len(self.calls), 1)
        argv = self.calls[0]
        self.assertIn(f"finding_id={MINTED_FINDING_ID}", argv)
        self.assertIn("ask_outcome=accepted", argv)
        for expected in ("actioned=ask", "disposition=ask", "gate=code-reviewer", "class=bug", "lane=fix",
                         "scope=diff", "iter=1", "file=src/widget.py", "line=12"):
            self.assertIn(expected, argv)
        self.assertFalse([word for word in argv if word.startswith("phase=")])
        self.assertFalse([word for word in argv if word.startswith("desc=")])
        self.assertFalse([word for word in argv if word.startswith("repo=")])

    def asks_done(self, asks, outcomes):
        """(stdout, stderr) of one asks-done call on asks waiting in self.state."""
        self.state.update({"stage": "asks", "asks": asks})
        original = (review_fix.load_fix_state, review_fix.save_fix_state, review_fix.record_asks_logged)
        review_fix.load_fix_state = lambda: self.state
        review_fix.save_fix_state = lambda state: None
        review_fix.record_asks_logged = lambda packet_id: None
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                review_fix.command_asks_done(outcomes)
        finally:
            review_fix.load_fix_state, review_fix.save_fix_state, review_fix.record_asks_logged = original
        return out.getvalue(), err.getvalue()

    def test_ask_without_finding_id_is_logged_under_a_new_id_and_marked_logged(self):
        out, err = self.asks_done([ask_item(finding_id=None)], ["rejected"])

        [argv] = self.calls
        self.assertIn("ask_outcome=rejected", argv)
        self.assertEqual(self.state["asks_logged"], [0])
        self.assertIn("Logged 1 of 1", out)
        self.assertIn("ask outcome without a valid finding_id (no finding_id), logged under new finding_id", err)

    def test_asks_done_retry_logs_a_new_id_ask_only_once(self):
        asks = [ask_item(finding_id=None), ask_item(finding_id="1111111111111111"),
                ask_item(finding_id="2222222222222222")]
        outputs = [self.asks_done(asks, ["accepted", "accepted", "accepted"])[0] for _ in range(2)]

        self.assertIn("Logged 3 of 3", outputs[0])
        self.assertIn("Logged 3 of 3", outputs[1])
        self.assertEqual(len(self.calls), 3)

    def test_a_failed_row_keeps_the_stage_and_the_retry_logs_only_that_row(self):
        failing_id = "finding_id=2222222222222222"
        failed = []

        def run_command(command, cwd=None):
            self.calls.append(command)
            if failing_id in command and not failed:
                failed.append(command)
                return 1, "boom"
            return 0, ""

        review_asks.run_command = run_command
        asks = [ask_item(finding_id="1111111111111111"), ask_item(finding_id="2222222222222222")]

        first, _ = self.asks_done(asks, ["accepted", "rejected"])
        self.assertIn("Logged 1 of 2", first)
        self.assertIn("Failures", first)
        self.assertIn("- src/widget.py:12: boom", first)
        self.assertEqual(self.state["stage"], "asks")

        self.calls.clear()
        second, _ = self.asks_done(asks, ["accepted", "rejected"])
        self.assertEqual(len(self.calls), 1)
        self.assertIn(failing_id, self.calls[0])
        self.assertIn("Logged 2 of 2", second)
        self.assertNotIn("Failures", second)
        self.assertEqual(self.state["stage"], "done")


class AskListingAndJump(unittest.TestCase):
    def test_jump_anchor_args_keep_only_one_well_formed_anchor_per_ask(self):
        asks = [
            {"file_line": "src/a.ts:10", "question": "cap\nit?"},
            {"file_line": "src/b.ts:3-9", "question": "q2"},
            {"file_line": "src/c.ts:1,188", "question": "list"},
            {"file_line": "src/d.ts", "question": "bare"},
            {"question": "none"},
        ]

        self.assertEqual(["--note", "cap it?", "src/a.ts:10", "--note", "q2", "src/b.ts:3-9"],
                         review_asks.jump_anchor_args(asks))

    def test_jump_anchor_args_cut_the_note_at_160_characters(self):
        arguments = review_asks.jump_anchor_args([{"file_line": "a.py:1", "question": "x" * 200}])

        self.assertEqual("x" * 160, arguments[1])

    def test_run_nvim_jump_says_nothing_to_jump_to_without_an_anchor_and_when_not_installed(self):
        self.assertIn("nothing to jump to", review_asks.run_nvim_jump("true", [{"question": "q"}]))
        self.assertIn("not installed", review_asks.run_nvim_jump("/nonexistent/nvim-jump",
                                                                  [{"file_line": "a.py:1", "question": "q"}]))

    def test_numbered_ask_lines_list_the_ask_and_its_change_for_code(self):
        ask = {"finding": "no cap", "question": "cap it?", "change": "cap at 3\nlog it", "gate": "g", "class": "bug"}

        self.assertEqual(["1. no cap - cap it?", "   Proposed change: cap at 3", "   log it"],
                         review_asks.numbered_ask_lines([ask]))

    def test_numbered_ask_lines_with_detail_add_location_gate_and_class(self):
        asks = [{"file_line": "a.py:1", "question": "q1", "gate": "code-reviewer", "class": "smell",
                 "class_raw": "nit", "change": "c1"},
                {"question": "q2\nmore", "gate": "perf-reviewer", "class": "perf"}]

        self.assertEqual(["1. a.py:1  [code-reviewer/smell (was nit)]", "   q1", "   Proposed change: c1",
                          "2. no file:line  [perf-reviewer/perf]", "   q2", "   more"],
                         review_asks.numbered_ask_lines(asks, detail=True))


if __name__ == "__main__":
    unittest.main()
