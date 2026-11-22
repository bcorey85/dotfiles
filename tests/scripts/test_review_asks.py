import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_asks
import review_fix_asks


class IsConditionalChangeTest(unittest.TestCase):
    def test_a_change_that_depends_on_a_missing_answer_is_conditional(self):
        conditional = [
            "If not confirmed, revert X",
            "  unless the user objects, drop the cache",
            "Otherwise remove the retry",
            "Revert X if not confirmed",
            "Keep the guard; remove it if the user confirms",
            "Keep X if yes",
            "Remove it if no, keep it",
            "If the user agrees, drop the column",
            "If not accepted, keep X",
        ]
        for change in conditional:
            with self.subTest(change):
                self.assertTrue(review_asks.is_conditional_change(change))

    def test_a_plain_change_is_not_conditional(self):
        plain = [
            "cap retries at 3",
            "add an index on tenant_id",
            "Revert X",
            "Notify the user, then restore -j8",
            "whenever it runs, log the count",
            "When the list is empty, return []",
            "raise ValueError if not found",
            "When the flag is unset, restore -j8",
            "If no-op, skip",
            "Keep the loop if no caller depends on it",
            "Show the banner if the user is an admin",
            "Return 202 if accepted by the queue",
            "if accepted, return `[]` when the list is empty",
            "if accepted as a cut, build `COMMIT` and `GIT_THEN_COMMIT` from `commit\\b(?!-)` again and leave "
            "`COMMITTING_CALL` only in `UNREADABLE_GIT_THEN_COMMIT`.",
            "",
        ]
        for change in plain:
            with self.subTest(change):
                self.assertFalse(review_asks.is_conditional_change(change))


class RefuseUnlocatedChangesTest(unittest.TestCase):
    def refuse(self, file_line, change, outcome, note="", **extra):
        item = {"question": "q?", "change": change, "file_line": file_line, **extra}
        review_asks.refuse_unlocated_changes([item], [outcome], [note], "asks-done ...")

    def test_accepted_with_no_location_and_no_file_in_the_change_is_refused(self):
        for file_line in ("", "unlocated"):
            with self.subTest(file_line=file_line), self.assertRaises(review_fix_asks.UsageError):
                self.refuse(file_line, "tighten the check", review_asks.ACCEPTED)

    def test_the_refusal_names_the_rerun_command_it_was_given(self):
        item = {"question": "q?", "change": "tighten the check", "file_line": "unlocated"}
        with self.assertRaises(review_fix_asks.UsageError) as raised:
            review_asks.refuse_unlocated_changes([item], [review_asks.ACCEPTED], [""], "asks-done --correct ...")
        self.assertIn("run `asks-done --correct ...` again", str(raised.exception))

    def test_a_leading_dotted_symbol_is_not_a_file(self):
        with self.assertRaises(review_fix_asks.UsageError):
            self.refuse("unlocated", "config.timeout should be 30", review_asks.ACCEPTED)
        with self.assertRaises(review_fix_asks.UsageError):
            self.refuse("unlocated", "tighten the check", review_asks.MODIFIED, note="config.timeout should be 30")

    def test_the_refusal_says_a_root_file_is_written_with_a_dot_slash(self):
        with self.assertRaises(review_fix_asks.UsageError) as raised:
            self.refuse("unlocated", "tighten the check", review_asks.ACCEPTED)
        self.assertIn("write a root or extensionless file as `./name`", str(raised.exception))

    def test_an_extensionless_file_written_with_a_dot_slash_is_taken(self):
        for change in ("Edit ./Makefile to add X", "Edit `./install/deps` to add X"):
            with self.subTest(change=change):
                self.refuse("unlocated", change, review_asks.ACCEPTED)
        self.refuse("unlocated", "tighten the check", review_asks.MODIFIED, note="edit ./Makefile")

    def test_a_parent_relative_extensionless_file_is_not_a_file(self):
        with self.assertRaises(review_fix_asks.UsageError):
            self.refuse("unlocated", "Edit ../Makefile to add X", review_asks.ACCEPTED)

    def test_the_refusal_gives_the_steps_for_an_ask_with_no_known_file(self):
        with self.assertRaises(review_fix_asks.UsageError) as raised:
            self.refuse("unlocated", "tighten the check", review_asks.ACCEPTED)
        self.assertIn("'modified:<change naming the file>'", str(raised.exception))

    def test_modified_with_no_file_in_the_note_is_refused(self):
        with self.assertRaises(review_fix_asks.UsageError):
            self.refuse("unlocated", "tighten the check", review_asks.MODIFIED, note="make it faster")

    def test_a_located_ask_a_change_naming_a_file_and_other_outcomes_are_taken(self):
        self.refuse("a.py:3", "tighten the check", review_asks.ACCEPTED)
        self.refuse("unlocated", "src/gate.py:12 tighten the check", review_asks.ACCEPTED)
        self.refuse("a.py:3", "tighten the check", review_asks.MODIFIED, note="make it faster")
        self.refuse("unlocated", "tighten the check", review_asks.REJECTED)
        self.refuse("unlocated", "tighten the check", review_asks.MODIFIED, note="edit src/gate.py")
        for note in ("edit ./setup.py", "edit `./setup.py`", "edit ./name.ext", 'edit "src/gate.py"'):
            with self.subTest(note=note):
                self.refuse("unlocated", "tighten the check", review_asks.MODIFIED, note=note)

    def test_a_bare_home_path_with_no_line_is_not_a_file(self):
        with self.assertRaises(review_fix_asks.UsageError):
            self.refuse("unlocated", "edit ~/x/y.md", review_asks.ACCEPTED)

    def test_a_modified_refusal_calls_the_note_the_modified_change(self):
        with self.assertRaises(review_fix_asks.UsageError) as raised:
            self.refuse("unlocated", "tighten the check", review_asks.MODIFIED, note="make it faster")
        self.assertIn("the modified change names no file: make it faster", str(raised.exception))

    def test_a_change_naming_a_file_with_no_line_is_taken(self):
        changes = [
            "Edit src/gate.py to add X",
            "Add a guard in claude/.claude/scripts/review/foo.py",
            "Edit `lib/x.py` to add y",
            'Edit "tests/x.py" to add y',
            "Edit 'tests/x.py' to add y",
            "Edit ./name.ext to add X",
            "Edit ./README.md to add X",
        ]
        for change in changes:
            with self.subTest(change):
                self.refuse("unlocated", change, review_asks.ACCEPTED)

    def test_a_plan_impact_ask_is_taken_with_no_file(self):
        plan_impact = "PLAN-IMPACT: the plan assumed X"
        self.refuse("unlocated", plan_impact, review_asks.ACCEPTED, question=plan_impact)


class AcceptRejectLinesTest(unittest.TestCase):
    def test_a_change_that_ends_in_a_question_or_exclamation_mark_gets_no_period(self):
        for change in ("Revert X?", "Revert X!"):
            with self.subTest(change):
                self.assertEqual(
                    review_asks.accept_reject_lines(change),
                    [f"   Accept = make this change: {change} Reject = leave the code as it is."])

    def test_trailing_dots_collapse_to_one_period(self):
        self.assertEqual(
            review_asks.accept_reject_lines("Wait..."),
            ["   Accept = make this change: Wait. Reject = leave the code as it is."])

    def test_a_change_that_ends_in_a_period_gets_one_period_before_reject(self):
        for change in ("Revert X", "Revert X.", "Revert X. "):
            with self.subTest(change):
                self.assertEqual(
                    review_asks.accept_reject_lines(change),
                    ["   Accept = make this change: Revert X. Reject = leave the code as it is."])


class ReadOutcomesTest(unittest.TestCase):
    def test_an_unknown_outcome_word_error_says_rejected_is_the_leave_it_outcome(self):
        with self.assertRaises(review_fix_asks.UsageError) as raised:
            review_fix_asks.read_outcomes(["leave-it"], [{}])
        message = str(raised.exception)
        self.assertIn(f"{review_asks.REJECTED}: {review_asks.REJECT_MEANS}", message)
        self.assertIn(f"{review_asks.ACCEPTED}: {review_asks.ACCEPT_MEANS}", message)
        self.assertIn("'leave it'", message)


if __name__ == "__main__":
    unittest.main()
