"""Tests for protected_lines.py and its use by the review loop's sign-off put-back."""
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import protected_lines
import review_loop_signoffs

BEFORE = "# D\n\n- Ruled by the session.\n\n- plain note\n"


class RestoreProtectedLinesTest(unittest.TestCase):
    def test_a_changed_protected_line_goes_back_and_other_edits_stay(self):
        after = "# D\n\n- Ruled by the user.\n\n- plain note, edited\n"

        restored = protected_lines.restore_protected_lines(BEFORE, after, [3])

        self.assertEqual(restored, "# D\n\n- Ruled by the session.\n\n- plain note, edited\n")

    def test_a_removed_protected_line_goes_back_and_a_line_added_elsewhere_stays(self):
        after = "# D\n\n- plain note\n- Ruled by someone else.\n"

        restored = protected_lines.restore_protected_lines(BEFORE, after, [3])

        self.assertEqual(restored, "# D\n\n- Ruled by the session.\n\n- plain note\n- Ruled by someone else.\n")

    def test_an_unprotected_removal_stays_removed(self):
        restored = protected_lines.restore_protected_lines(BEFORE, "# D\n\n- Ruled by the session.\n\n", [3])

        self.assertEqual(restored, "# D\n\n- Ruled by the session.\n\n")


class SignoffHost(review_loop_signoffs.SignoffRuns):
    """The two members undo_signoff_pass reads: the repo and the ask list."""

    def __init__(self, repo):
        self.repo = repo
        self.asks = []

    def add_ask(self, _gate, item):
        self.asks.append(item)


class UndoSignoffPassTest(unittest.TestCase):
    def test_a_sign_off_another_session_added_during_the_pass_is_not_erased(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            log = repo / "docs" / "plans" / "x" / "03-decisions.md"
            log.parent.mkdir(parents=True)
            original = "# D\n\n- Ruled by the session, 2026-11-11.\n"
            log.write_text(original)
            host = SignoffHost(str(repo))
            snapshot = review_loop_signoffs.snapshot_signoffs(repo, [])
            # The coder rewrites the first ruling; the orchestrator appends its own during the pass.
            log.write_text("# D\n\n- Ruled by the user, 2026-11-11.\n\n- Ruled by the orchestrator, 2026-11-12.\n")

            put_back = host.undo_signoff_pass(snapshot, [], set())

            self.assertEqual([entry.path for entry in put_back], ["docs/plans/x/03-decisions.md"])
            self.assertEqual(log.read_text(), original + "\n- Ruled by the orchestrator, 2026-11-12.\n")


if __name__ == "__main__":
    unittest.main()
