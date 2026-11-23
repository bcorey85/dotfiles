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


class StretchHelpersTest(unittest.TestCase):
    def test_entries_missing_counts_repeats(self):
        missing = protected_lines.entries_missing([(1, "a"), (2, "a"), (3, "b")], [(1, "a"), (2, "b")])

        self.assertEqual(missing, [(2, "a")])

    def test_changed_stretches_name_removed_and_rewritten_lines_of_the_first_text(self):
        stretches = protected_lines.changed_stretches("a\nb\nc\nd\n", "a\nc\nD\n")

        self.assertEqual(stretches, [(2, 2), (4, 4)])

    def test_old_line_whose_best_match_is_a_later_line_is_not_an_update_in_place(self):
        plan_line = "- Plan text: `lib/plan_format.py` reads every plan file."
        longer_line = "- Plan text: `lib/plan_format.py` reads every plan file, too."
        after_lines = [plan_line.replace("every", "each"), plan_line]
        self.assertFalse(protected_lines.lines_rewritten_in_place([plan_line, longer_line], after_lines, after_lines))

    def test_two_old_lines_never_share_one_new_line_and_each_match_starts_after_the_previous_one(self):
        first = "- Plan text: `lib/plan_format.py` reads every plan file."
        second = "- Review text: `review/handback.py` reads every hand-back row."
        cases = {
            "two similar old lines, one new line": ([first, first + " Twice."], [first + " Once."]),
            "the new lines come in the reverse order": ([first, second], [second + " Edited.", first + " Edited."]),
        }
        for name, (before_lines, after_lines) in cases.items():
            with self.subTest(name):
                rewritten = protected_lines.lines_rewritten_in_place(before_lines, after_lines, after_lines)

                self.assertFalse(rewritten, name)

    def test_an_old_line_with_a_better_match_among_the_rivals_is_not_an_update_in_place(self):
        before = "- Plan text: `lib/plan_format.py`."
        own = before + " Changed a lot more than this."
        rival = before + " `read`."
        self.assertFalse(protected_lines.lines_rewritten_in_place([before], [own], [own, rival]))

    def test_changed_line_ranges_name_both_sides_and_are_empty_for_equal_texts(self):
        self.assertEqual(protected_lines.changed_line_ranges("a\nb\n", "a\nx\ny\n"), [("replace", 1, 2, 1, 3)])
        self.assertEqual(protected_lines.changed_line_ranges("a\nb\n", "a\nb\n"), [])
        self.assertEqual(protected_lines.changed_line_ranges("a\n", "a\nb\n"), [("insert", 1, 1, 1, 2)])
        self.assertEqual(protected_lines.changed_line_ranges("a\nb\n", "a\n"), [("delete", 1, 2, 1, 1)])

    def test_a_removed_stretch_comes_back_only_at_its_protected_lines_when_not_whole(self):
        restored = protected_lines.restore_protected_lines("a\nb\nc\nd\n", "a\nd\n", [2], whole_stretch=False)

        self.assertEqual(restored, "a\nb\nd\n")


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

    def test_an_absolute_scope_path_is_keyed_repo_relative_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = pathlib.Path(tmp)
            log = repo / "docs" / "plans" / "x" / "03-decisions.md"
            log.parent.mkdir(parents=True)
            log.write_text("# D\n\n- Ruled by the session, 2026-11-11.\n")

            snapshot = review_loop_signoffs.snapshot_signoffs(repo, [str(log)])

            self.assertEqual(list(snapshot.texts), ["docs/plans/x/03-decisions.md"])


if __name__ == "__main__":
    unittest.main()
