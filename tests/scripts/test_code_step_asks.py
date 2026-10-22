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
sys.path.insert(0, str(SCRIPTS_DIR))
loaded = importlib.util.spec_from_file_location("code_step", SCRIPTS_DIR / "code-step.py")
code_step = importlib.util.module_from_spec(loaded)
loaded.loader.exec_module(code_step)
loaded_review_fix = importlib.util.spec_from_file_location("review_fix", SCRIPTS_DIR / "review-fix.py")
review_fix = importlib.util.module_from_spec(loaded_review_fix)
loaded_review_fix.loader.exec_module(review_fix)
import handback  # noqa: E402

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
        self.loggerResult = (0, "")
        self.original_run_command = code_step.run_command
        self.original_git_output = code_step.git_output
        code_step.run_command = lambda command, cwd, **_: self.calls.append(command) or self.loggerResult
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

    def test_ask_without_finding_id_writes_nothing_and_says_so(self):
        stderr = self.log([ask_item(finding_id=None), ask_item(finding_id=OTHER_MINTED_FINDING_ID)],
                          ["rejected", "modified"])

        self.assertEqual(stderr.count("ask outcome without a valid finding_id (no finding_id), not logged"), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertIn(f"finding_id={OTHER_MINTED_FINDING_ID}", self.calls[0])

    def test_asks_whose_finding_id_is_the_word_none_write_no_row_and_are_named(self):
        stderr = self.log([ask_item(finding_id="none"), ask_item(finding_id="none"),
                           ask_item(finding_id=OTHER_MINTED_FINDING_ID)], ["accepted", "rejected", "accepted"])

        self.assertEqual(stderr.count("ignored 'none'"), 2)
        self.assertEqual(len(self.calls), 1)
        self.assertIn(f"finding_id={OTHER_MINTED_FINDING_ID}", self.calls[0])
        self.assertFalse([call for call in self.calls if "finding_id=none" in call])

    def test_an_ask_whose_finding_id_is_prose_with_a_space_writes_no_row_and_is_named(self):
        stderr = self.log([ask_item(finding_id="none logged")], ["accepted"])

        self.assertEqual(self.calls, [])
        self.assertIn("ignored 'none logged'", stderr)
        self.assertIn("not logged", stderr)

    def test_a_short_or_upper_case_hex_finding_id_is_not_an_id(self):
        stderr = self.log([ask_item(finding_id="abc123"), ask_item(finding_id=MINTED_FINDING_ID.upper())],
                          ["accepted", "accepted"])

        self.assertEqual(self.calls, [])
        self.assertEqual(stderr.count("not logged"), 2)

    def test_a_logger_that_fails_is_named_on_stderr_with_the_id_and_its_output(self):
        self.loggerResult = (1, "log-review-finding: field finding_id has a space")

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
        review_fix.log_ask_outcome(self.state, ask_item(), "accepted")

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

    def test_ask_without_finding_id_calls_nothing_and_is_marked_skipped(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            (code, _), _, _ = review_fix.log_ask_outcome(self.state, ask_item(finding_id=None), "rejected")

        self.assertEqual(self.calls, [])
        self.assertIsNone(code)
        self.assertIn("ask outcome without a valid finding_id (no finding_id), not logged", stderr.getvalue())

    def test_asks_done_retry_does_not_count_skipped_asks_as_logged(self):
        self.state.update({"stage": "asks", "asks": [ask_item(finding_id=None),
                                                      ask_item(finding_id="1111111111111111"),
                                                      ask_item(finding_id="2222222222222222")]})
        original = (review_fix.load_state, review_fix.save_state)
        review_fix.load_state = lambda: self.state
        review_fix.save_state = lambda state: None
        outputs = []
        try:
            for _ in range(2):
                self.state["stage"] = "asks"
                out = io.StringIO()
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
                    review_fix.command_asks_done(["accepted", "accepted", "accepted"])
                outputs.append(out.getvalue())
        finally:
            review_fix.load_state, review_fix.save_state = original

        self.assertIn("Logged 2 of 3", outputs[0])
        self.assertIn("Logged 2 of 3", outputs[1])

    def test_handback_item_keys_include_finding_id(self):
        self.assertIn("finding_id", handback.ITEM_KEYS)


if __name__ == "__main__":
    unittest.main()
