import importlib.util
import os
import pathlib
import sys
import unittest

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("SIGNOFF_LINES_MODULE") or toolkit_paths.LIB_DIR / "signoff_lines.py")
sys.path.insert(0, str(toolkit_paths.LIB_DIR))
plan_format = importlib.import_module("plan_format")
module_spec = importlib.util.spec_from_file_location("signoff_lines", MODULE)
signoff_lines = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(signoff_lines)

SESSION_THEN_USER = ("- 2026-11-11: Keep plan. Ruled by the session, not the user at 2026-11-11 03:17.\n\n"
                     "  The ruling: kept.\n\n"
                     "- 2026-11-12: Cut AC2. Ruled by Brandon Corey at 2026-11-12 09:00.\n\n"
                     "  The ruling: cut.\n")


SESSION_RULED_WITH_USER_SIGNOFF = (
    "- AC1 narrowed to `pipe_shell_check.py`; the live deny is logged for the work machine. Ruled by the "
    "orchestrating session agent-evals-5e (plan author), not the user, 2026-11-10. User sign-off: Alex Doe, "
    "2026-11-10 (decision log: Alex Doe's sign-off given to agent-evals-5e).\n")
LANE_SESSION_RECORDS_USER_SIGNED = (
    "- 2026-11-10: The 21:27 and 21:33 lane-session rulings above predate the user's sign-off entry at the top of "
    "this log, which answers both questions they left open: the AC2 shells-only narrowing and the dropped AC1 "
    "quoted-text case are now user-signed. Recorded by the queue-fixes lane session.\n")
SESSION_ADOPTED_LINE = ("- 2026-11-10: Phase 2 lookup is `git ls-remote`. No criterion changed. Adopted by the /code "
                        "run, ruled by orchestrating session agent-evals-5e, not the user.\n")


class RecordsUserSignoffTest(unittest.TestCase):
    def test_a_session_ruling_that_records_a_user_signoff_clause_is_the_users(self):
        for text, label in [(SESSION_RULED_WITH_USER_SIGNOFF, "session ruled, then user sign-off clause"),
                            (LANE_SESSION_RECORDS_USER_SIGNED, "lane session recorded a user-signed entry")]:
            with self.subTest(label):
                self.assertTrue(signoff_lines.records_user_signoff(text, 1))

    def test_a_pure_session_ruling_stays_the_sessions(self):
        self.assertFalse(signoff_lines.records_user_signoff(SESSION_ADOPTED_LINE, 1))

    def test_each_line_takes_the_ruler_of_the_nearest_by_line_above_it(self):
        cases = [(1, False, "session entry's own line"), (3, False, "session entry's ruling line"),
                 (5, True, "user entry's own line"), (7, True, "user entry's ruling line")]
        for line_number, expected, label in cases:
            with self.subTest(label):
                self.assertEqual(signoff_lines.records_user_signoff(SESSION_THEN_USER, line_number), expected)

    def test_a_line_above_every_by_line_reads_the_first_one_below(self):
        text = "# Decisions\n\n- Ruled by Brandon Corey.\n"

        self.assertTrue(signoff_lines.records_user_signoff(text, 1))

    def test_line_zero_records_a_user_signoff_when_any_by_line_does(self):
        self.assertTrue(signoff_lines.records_user_signoff(SESSION_THEN_USER, 0))
        self.assertFalse(signoff_lines.records_user_signoff(SESSION_THEN_USER.split("- 2026-11-12")[0], 0))

    def test_a_signed_off_line_without_the_session_names_the_user(self):
        self.assertTrue(signoff_lines.records_user_signoff("- Signed off by the user.\n", 1))

    def test_a_user_heading_with_no_by_form_does_not_take_the_ruler_of_the_entry_above(self):
        text = ("- D4: cut AC1. Ruled by the session, not the user at 2026-10-09.\n\n"
                "### Damage-path ruling (user, 2026-10-09)\n")

        self.assertTrue(signoff_lines.records_user_signoff(text, 3))
        self.assertFalse(signoff_lines.records_user_signoff(text, 1))

    def test_line_zero_counts_a_user_ruling_heading_with_no_by_form(self):
        text = ("- D4: cut AC1. Ruled by the session, not the user at 2026-10-09.\n\n"
                "### Damage-path ruling (user, 2026-10-09)\n")

        self.assertTrue(signoff_lines.records_user_signoff(text, 0))

    def test_an_unmarked_entry_reads_as_the_user_when_the_file_has_a_user_marker(self):
        text = ("- D4: cut AC1. Ruled by the session, not the user at 2026-10-09.\n"
                "- D5: plain line\n"
                "- D6: cut AC2. Signed off by Brandon.\n")

        self.assertTrue(signoff_lines.records_user_signoff(text, 2))

    def test_an_unmarked_entry_reads_as_no_user_signoff_when_the_only_marker_names_the_session(self):
        text = "- D4: cut AC1. Ruled by the session, not the user at 2026-10-09.\n- D5: plain line\n"

        self.assertFalse(signoff_lines.records_user_signoff(text, 2))

    def test_an_entry_with_a_session_and_a_user_marker_reads_as_the_user(self):
        text = "- D4: cut. Ruled by the session, not the user.\n  Signed off by Brandon.\n"

        self.assertTrue(signoff_lines.records_user_signoff(text, 1))

    def test_the_opening_line_of_a_wrapped_user_entry_does_not_take_the_ruler_of_the_entry_above(self):
        text = ("- D4: cut AC1. Ruled by the session, not the user at 2026-11-11.\n"
                "- D5: reword AC3.\n"
                "  Signed off by Brandon at 2026-11-12.\n")

        self.assertTrue(signoff_lines.records_user_signoff(text, 2))
        self.assertTrue(signoff_lines.records_user_signoff(text, 3))
        self.assertFalse(signoff_lines.records_user_signoff(text, 1))

    def test_a_line_with_signed_off_and_the_session_phrase_reads_as_a_session_ruling(self):
        text = "- D4: reword AC3. Signed off by the session, not the user.\n"

        self.assertFalse(signoff_lines.records_user_signoff(text, 1))

    def test_each_session_ruler_form_reads_as_a_session_ruling(self):
        forms = ["- D4: cut AC1. Ruled by agent-evals-c3-owner (orchestrating session), 2026-11-23.\n",
                 "- D4: cut AC1. Ruled by the lane session, 2026-11-23.\n",
                 "- D4: cut AC1. Ruled by this lane session, 2026-11-23.\n"]
        for text in forms:
            with self.subTest(text):
                self.assertFalse(signoff_lines.records_user_signoff(text, 1))
                self.assertFalse(signoff_lines.records_user_signoff(text, 0))

    def test_line_zero_counts_a_plural_user_rulings_heading(self):
        text = ("- D4: cut AC1. Ruled by the session, not the user at 2026-10-09.\n\n"
                "### Damage-path rulings (user, 2026-10-09)\n")

        self.assertTrue(signoff_lines.records_user_signoff(text, 0))
        self.assertTrue(signoff_lines.records_user_signoff(text, 3))

    def test_a_plan_body_marker_outside_plan_deviations_is_not_a_user_signoff(self):
        text = ("# Plan\n\nPhase 2 needs the user's sign-off before merge.\n\n"
                "## Plan Deviations\n\n"
                "- D1: kept. Ruled by the session, not the user at 2026-11-11 03:17.\n\n"
                "- D2: no marker here.\n")

        self.assertFalse(signoff_lines.records_user_signoff(text, 0, "plan.md"))
        self.assertFalse(signoff_lines.records_user_signoff(text, 9, "plan.md"))

    def test_signoff_lines_lists_a_plural_rulings_heading(self):
        text = "# Decisions\n\n### Damage-path rulings (user, 2026-10-09)\n"

        listed = signoff_lines.signoff_lines(text, "03-decisions.md")

        self.assertIn((3, "### Damage-path rulings (user, 2026-10-09)"), listed)

    def test_a_text_with_no_marker_line_records_no_user_signoff(self):
        self.assertFalse(signoff_lines.records_user_signoff("- D4: reword AC3.\n", 1))

    def test_a_disagreement_block_that_quotes_ruling_words_does_not_read_as_a_user_signoff(self):
        entry = plan_format.ruling_deviation(2, "Keep plan", plan_format.SESSION_RULING_OWNER, "2026-11-11 03:17",
                                             "kept.", "The reviewer says this ruling drops AC2.")
        text = f"## Plan Deviations\n\n{chr(10).join(entry)}\n"
        disagreement_start = text.splitlines().index("  The disagreement:") + 1

        self.assertFalse(signoff_lines.records_user_signoff(text, 0), "line 0")
        for line_number in (disagreement_start, disagreement_start + 1):
            with self.subTest(line_number=line_number):
                self.assertFalse(signoff_lines.records_user_signoff(text, line_number))


if __name__ == "__main__":
    unittest.main()
