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
import handback

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
        self.original_run_command = code_step.run_command
        self.original_git_output = code_step.git_output
        code_step.run_command = lambda command, cwd, **_: self.calls.append(command) or self.logger_result
        code_step.git_output = lambda *_: "some-branch"

    def tearDown(self):
        code_step.run_command = self.original_run_command
        code_step.git_output = self.original_git_output

    def log(self, asks, outcomes, phase="1"):
        state = {"asks": asks, "lane": "code", "phase": phase, "iter": 2}
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code_step.log_ask_outcomes(pathlib.Path("/tmp/some-repo"), state, outcomes)
        return stderr.getvalue()

    def test_argv_carries_finding_id_and_no_free_text(self):
        self.log([ask_item()], ["accepted"])

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

    def test_asks_whose_finding_id_is_the_word_none_each_get_their_own_new_id(self):
        stderr = self.log([ask_item(finding_id="none"), ask_item(finding_id="none"),
                           ask_item(finding_id=OTHER_MINTED_FINDING_ID)], ["accepted", "rejected", "accepted"])

        first_new_id, second_new_id, kept_finding_id = self.logged_finding_ids()
        self.assertNotEqual(first_new_id, second_new_id)
        self.assertNotIn("none", (first_new_id, second_new_id))
        self.assertEqual(kept_finding_id, OTHER_MINTED_FINDING_ID)
        self.assertEqual(stderr.count("ignored 'none'"), 2)

    def test_an_ask_whose_finding_id_is_prose_with_a_space_is_logged_under_a_new_id(self):
        stderr = self.log([ask_item(finding_id="not logged (no id was printed)")], ["accepted"])

        [new_finding_id] = self.logged_finding_ids()
        self.assertRegex(new_finding_id, r"^[0-9a-f]{16}$")
        self.assertIn("ignored 'not logged (no id was printed)'", stderr)

    def test_a_short_or_upper_case_hex_finding_id_is_not_an_id(self):
        stderr = self.log([ask_item(finding_id="abc123"), ask_item(finding_id=MINTED_FINDING_ID.upper())],
                          ["accepted", "accepted"])

        self.assertNotIn("abc123", self.logged_finding_ids())
        self.assertNotIn(MINTED_FINDING_ID.upper(), self.logged_finding_ids())
        self.assertEqual(stderr.count("logged under new finding_id"), 2)

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

    def test_a_logger_that_succeeds_prints_nothing(self):
        stderr = self.log([ask_item()], ["accepted"])

        self.assertEqual(1, len(self.calls))
        self.assertEqual("", stderr)

    def test_a_missing_hand_back_reader_logs_nothing_and_says_why(self):
        original = code_step.load_handback
        code_step.load_handback = lambda: (None, "handback.py could not be imported (boom)")
        try:
            stderr = self.log([ask_item()], ["accepted"])
        finally:
            code_step.load_handback = original

        self.assertEqual(self.calls, [])
        self.assertIn("ask outcomes not logged", stderr)
        self.assertIn("boom", stderr)


class ReviewFixLogAskOutcome(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.original_run_command = review_fix.run_command
        review_fix.run_command = lambda command, cwd=None: self.calls.append(command) or (0, "")
        self.state = {"branch": "some-branch", "lane": "fix", "scope": "diff", "iter": 1}

    def tearDown(self):
        review_fix.run_command = self.original_run_command

    def test_argv_carries_finding_id_and_no_free_text(self):
        review_fix.log_ask_outcome(self.state, ask_item(), "accepted", MINTED_FINDING_ID)

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
        original = (review_fix.load_fix_state, review_fix.save_fix_state)
        review_fix.load_fix_state = lambda: self.state
        review_fix.save_fix_state = lambda state: None
        out, err = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                review_fix.command_asks_done(outcomes)
        finally:
            review_fix.load_fix_state, review_fix.save_fix_state = original
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

        review_fix.run_command = run_command
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

    def test_handback_item_keys_include_finding_id(self):
        self.assertIn("finding_id", handback.ITEM_KEYS)


if __name__ == "__main__":
    unittest.main()
