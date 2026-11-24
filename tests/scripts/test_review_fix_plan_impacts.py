import contextlib
import io
import os
import sys
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import human_turn_lookup
import plan_format
import review_fix_plan_impacts
import ruling_relay


class SessionAdoptionLinesTest(unittest.TestCase):
    def test_entry_opens_with_the_adopt_decision_words(self):
        impacts = [{"text": "assumed A, found B"}]
        lines = review_fix_plan_impacts.session_adoption_lines(impacts, lambda impact: "words", "2026-01-02 03:04")
        self.assertEqual(lines[0], f"- 2026-01-02: Adopt plan change. Ruled by {plan_format.SESSION_RULING_OWNER} "
                                   "at 2026-01-02 03:04.")

    def test_each_impact_gets_its_own_entry_with_its_text_and_ruling_words_in_order(self):
        impacts = [{"text": "assumed A, found B"}, {"text": "assumed C, found D"}]
        words = {"assumed A, found B": "words one", "assumed C, found D": "words two"}

        lines = review_fix_plan_impacts.session_adoption_lines(
            impacts, lambda impact: words[impact["text"]], "2026-01-02 03:04")

        joined = "\n".join(lines)
        positions = [joined.find(piece) for piece in ("words one", "assumed A, found B", "words two",
                                                      "assumed C, found D")]
        self.assertNotIn(-1, positions)
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(joined.count("Adopt plan change."), 2)


class RelayedOwnerTest(unittest.TestCase):
    def test_the_owner_line_names_the_session_name_of_a_relay_by_id(self):
        turn = human_turn_lookup.HumanTurn("2026-11-15T06:22:12.305Z", 1.0)
        relayed = ruling_relay.RelayedRuling("relay-session", turn)

        owner = review_fix_plan_impacts.relayed_owner("user", relayed)

        self.assertEqual(owner, "user, relayed by session relay-session (user turn at 2026-11-15T06:22:12.305Z)")

    def test_the_relay_row_of_a_plan_ruling_holds_the_session_name_not_the_id(self):
        turn = human_turn_lookup.HumanTurn("2026-11-15T06:22:12.305Z", 1.0)
        relayed = ruling_relay.RelayedRuling("relay-session", turn)
        handback_store = review_fix_plan_impacts.handback_store

        with mock.patch.object(handback_store, "record_ruled_impact"), \
                mock.patch.object(handback_store, "record_relayed_plan_ruling") as record:
            review_fix_plan_impacts.write_ruling_entry("adopt", "user", "ruling", None, "impact text", "/repo",
                                                       relayed=relayed)

        self.assertEqual(record.call_args.args[3], "relay-session")


class SettleStandingRewordsTest(unittest.TestCase):
    def test_without_a_session_id_the_rewords_are_named_as_not_recorded(self):
        rewords = [{"text": "AC2 reworded"}]
        output = io.StringIO()

        with mock.patch.dict(os.environ, {}, clear=False), contextlib.redirect_stdout(output):
            os.environ.pop("CLAUDE_CODE_SESSION_ID", None)
            review_fix_plan_impacts.settle_standing_rewords({}, rewords, {}, "2026-01-02 03:04")

        self.assertIn("not recorded", output.getvalue())
        self.assertIn("still counts the review as dirty", output.getvalue())
        self.assertIn("AC2 reworded", output.getvalue())


if __name__ == "__main__":
    unittest.main()
