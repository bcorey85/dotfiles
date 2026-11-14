"""A reviewer's pass note in the Ask section is no ask, and an ask that repeats an earlier ask is dropped."""
import pathlib
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import finding_record
import handback
import review_fix_asks
import review_loop_findings

FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"
REAL_ASKS = {
    "a tagged gap with no change line": "[test-gap] `lib/reviewed_tree.py:315` — no test pins the zero-parent branch.",
    "a question to the user": "Should the retry cap be 3 or 5?",
    "a plain proposed change": "`app.py:3` [bug] the limit is wrong. Change: raise it to 20.",
    "a backticked change marker": ("[plan-drift] `tests/test_gate.py:34` — the reword needs the user. "
                                   "Change if `accepted`: add the sign-off to the plan."),
}


def ask_section(*lines):
    return "## Fix\nNone\n\n## Ask\n" + "\n".join(lines) + "\n\n## Nit\nNone\n"


def parsed_asks(text):
    return [ask.text for ask in review_loop_findings.parse_review(text)["ask"]]


def kept_asks(text):
    review = review_loop_findings.parse_review(text)
    kept, _notes = review_loop_findings.pass_note_split(review["ask"])
    return [ask.text for ask in kept]


class PassNotesAreNoAskTest(unittest.TestCase):
    def test_the_real_report_with_a_none_new_opening_has_no_ask_at_all(self):
        report = (FIXTURES / "review_ask_pass_notes_report.md").read_text()

        self.assertEqual(parsed_asks(report), [])

    def test_a_pass_note_in_any_wording_is_no_ask(self):
        wordings = {
            "none new, full stop": ["None new."],
            "none new, no stop": ["None new"],
            "none further": ["None further."],
            "parenthesised none new": ["(none new; the open ask is left as it was)"],
            "a lead-in and bullets": ["Checks run (no defects found):", "- I checked the claim and it holds.",
                                      "- The ids are already used."],
            "a plain claim line": ["I checked every claim against the code, and each one holds."],
            "a bullet with a location": ["- The file list matches `REVIEWED_SUFFIX` in `lib/reviewed_tree.py:37-42`."],
            "a command result": ["- `python3 tests/parallel_tests.py x.py` gave 36 tests, 0 failed."],
        }
        for label, lines in wordings.items():
            with self.subTest(label):
                self.assertEqual(kept_asks(ask_section(*lines)), [], label)

    def test_a_real_ask_survives_next_to_a_pass_note(self):
        for label, ask in REAL_ASKS.items():
            with self.subTest(label):
                text = ask_section(f"- {ask}", "- I checked the other claims and each one holds.")

                self.assertEqual(kept_asks(text), [ask], label)

    def test_a_dropped_note_is_returned_for_the_packet_not_lost(self):
        text = ask_section("- I checked the claim and it holds.", f"- {REAL_ASKS['a question to the user']}")
        review = review_loop_findings.parse_review(text)

        kept, notes = review_loop_findings.pass_note_split(review["ask"])

        self.assertEqual([ask.text for ask in kept], [REAL_ASKS["a question to the user"]])
        self.assertEqual([note.text for note in notes], ["I checked the claim and it holds."])


class RepeatedAskTest(unittest.TestCase):
    def test_an_ask_naming_the_same_file_and_claim_repeats_the_earlier_one(self):
        earlier = finding_record.parse_finding("`app.py:3` [bug] should the window be pinned?")
        again = finding_record.parse_finding("`app.py:9` [bug] should the window be pinned?")

        self.assertTrue(review_loop_findings.repeats_an_ask(again, [earlier], []))

    def test_an_ask_in_another_file_or_on_another_claim_is_new(self):
        earlier = finding_record.parse_finding("`app.py:3` [bug] should the window be pinned?")
        other_file = finding_record.parse_finding("`util.py:3` [bug] should the window be pinned?")
        other_claim = finding_record.parse_finding("`app.py:3` [bug] drop the cache key entirely, please")

        self.assertFalse(review_loop_findings.repeats_an_ask(other_file, [earlier], []))
        self.assertFalse(review_loop_findings.repeats_an_ask(other_claim, [earlier], []))

    def test_a_plan_drift_ask_on_the_same_criterion_repeats_a_plan_impact(self):
        impact = "PLAN-IMPACT: the reword is narrower than the ticket. acceptance_criteria: AC2."
        ask = finding_record.parse_finding("[plan-drift] `tests/test_gate.py:34` — these tests pin the reworded AC2.")
        other_criterion = finding_record.parse_finding("[plan-drift] `tests/test_gate.py:34` — pins the reworded AC5.")
        no_drift = finding_record.parse_finding("[bug] `tests/test_gate.py:34` — AC2 is read twice.")

        self.assertTrue(review_loop_findings.repeats_an_ask(ask, [], [impact]))
        self.assertFalse(review_loop_findings.repeats_an_ask(other_criterion, [], [impact]))
        self.assertFalse(review_loop_findings.repeats_an_ask(no_drift, [], [impact]))


class RuledImpactTest(unittest.TestCase):
    RULED = ("docs/criteria.md:4 [plan-drift] — PLAN-IMPACT: the reword is narrower than the "
             "ticket. acceptance_criteria: AC2.",)

    def test_a_plan_impact_on_a_ruled_criterion_is_ruled(self):
        impact = "PLAN-IMPACT:\n  assumed: AC2 as written\n  found: the code differs\n  acceptance_criteria: AC2"

        self.assertTrue(review_loop_findings.ruled_plan_impact(impact, self.RULED))

    def test_a_plan_impact_that_also_changes_an_unruled_criterion_is_not_ruled(self):
        impact = "PLAN-IMPACT:\n  assumed: AC2 as written\n  found: the code differs\n  acceptance_criteria: AC2, AC3"

        self.assertFalse(review_loop_findings.ruled_plan_impact(impact, self.RULED))

    def test_an_ordinary_accepted_finding_settles_no_plan_impact(self):
        impact = "PLAN-IMPACT: widen AC2 to cover deletes. acceptance_criteria: AC2"
        test_gap = "app.py:4 [test-gap] the AC2 test misses the empty case"

        self.assertFalse(review_loop_findings.ruled_plan_impact(impact, [test_gap]))

    def test_a_criterion_id_alone_in_an_accepted_finding_settles_no_plan_impact_of_a_different_change(self):
        accepted = ("tests/test_gate.py:34 [plan-drift] these tests pin the old AC2 wording "
                    "Proposed change: update the tests to the reworded AC2")
        impact = ("PLAN-IMPACT: assumed: AC2 keeps 30 days / found: storage cap forces 7 days / cause: plan / "
                  "acceptance_criteria: AC2")

        self.assertFalse(review_loop_findings.ruled_plan_impact(impact, [], [accepted]))

    def test_an_accepted_finding_still_settles_a_plan_impact_that_is_a_near_title_of_it(self):
        accepted = "PLAN-IMPACT: the reword of AC2 is narrower than the ticket. acceptance_criteria: AC2"
        impact = "PLAN-IMPACT: the reword of AC2 is narrower than the ticket!! acceptance_criteria: AC2"

        self.assertTrue(review_loop_findings.ruled_plan_impact(impact, [], [accepted]))

    def test_a_decide_resolved_text_still_settles_by_criterion_ids_next_to_accepted_findings(self):
        impact = "PLAN-IMPACT: widen AC2 to cover deletes. acceptance_criteria: AC2"

        self.assertTrue(review_loop_findings.ruled_plan_impact(impact, list(self.RULED), ["x.py:1 [bug] other"]))

    def test_a_test_gap_that_names_a_criterion_settles_no_plan_impact(self):
        impact = "PLAN-IMPACT: widen AC2. acceptance_criteria: AC2"
        test_gap = "app.py:4 [test-gap] the AC2 test misses the empty case. acceptance_criteria: AC2"

        self.assertFalse(review_loop_findings.ruled_plan_impact(impact, [test_gap]))

    def test_a_plan_impact_mark_or_a_plan_drift_tag_alone_makes_a_ruled_text_a_plan_item(self):
        impact = "PLAN-IMPACT: widen AC2. acceptance_criteria: AC2"
        ruled_texts = {
            "plan-impact mark without a class tag": "PLAN-IMPACT: the reword is narrower. acceptance_criteria: AC2",
            "plan-drift tag without the mark": "app.py:4 [plan-drift] the reword needs sign-off. "
                                               "acceptance_criteria: AC2",
        }
        for label, ruled_text in ruled_texts.items():
            with self.subTest(label):
                self.assertTrue(review_loop_findings.ruled_plan_impact(impact, [ruled_text]), label)

    def test_a_plan_drift_tag_after_another_class_does_not_make_a_plan_item(self):
        impact = "PLAN-IMPACT: widen AC2. acceptance_criteria: AC2"
        text = "app.py:3 [test-gap] the AC2 test misses deletes; see the [plan-drift] ask. acceptance_criteria: AC2"

        self.assertFalse(review_loop_findings.ruled_plan_impact(impact, [text]))

    def test_a_plan_impact_with_a_near_title_is_ruled(self):
        impact = "docs/criteria.md:4 [plan-drift] — PLAN-IMPACT: the reword is narrower than the ticket."

        self.assertTrue(review_loop_findings.ruled_plan_impact(impact, self.RULED))

    def test_a_plan_drift_finding_with_no_criteria_line_is_ruled_by_the_ids_it_names(self):
        drift = "app.py:9 [plan-drift] the reworded AC2 drops deletes"

        self.assertTrue(review_loop_findings.ruled_plan_impact(drift, self.RULED))

    def test_a_plan_impact_names_only_the_ids_on_its_answer_line(self):
        impact = "PLAN-IMPACT: the reworded AC2 drops deletes"

        self.assertFalse(review_loop_findings.ruled_plan_impact(impact, self.RULED))

    def test_an_ask_that_opens_with_the_mark_repeats_only_by_its_answer_line_ids(self):
        ask = finding_record.parse_finding(
            "src/a.py:3 [plan-drift] — PLAN-IMPACT: AC2 reads 5 but the code caps at 3 — change: reword AC2")
        ruled = "PLAN-IMPACT: cap rule\nacceptance_criteria: AC2"

        self.assertFalse(review_loop_findings.repeats_an_ask(ask, [], [], [ruled]))

    def test_a_plan_impact_on_another_criterion_or_none_is_not_ruled(self):
        other = "PLAN-IMPACT:\n  assumed: a\n  found: b\n  acceptance_criteria: AC7"
        none = "PLAN-IMPACT:\n  assumed: a\n  found: b\n  acceptance_criteria: none"

        self.assertFalse(review_loop_findings.ruled_plan_impact(other, self.RULED))
        self.assertFalse(review_loop_findings.ruled_plan_impact(none, self.RULED))
        self.assertFalse(review_loop_findings.ruled_plan_impact(other, []))


class QuestionAndAnswerNotesTest(unittest.TestCase):
    def test_a_fix_section_notes_list_with_answered_questions_is_not_three_findings(self):
        text = ("## Fix\n- [fix] a.py:10 — off by one — use <=\nThe other claims check out:\n"
                "- Is the loop bounded? Yes, by n.\n- Does the cache key include the repo? Yes.\n\n"
                "## Ask\nNone\n\n## Nit\nNone\n")

        fixes = [fix.text for fix in review_loop_findings.parse_review(text)["fix"]]

        self.assertEqual(len(fixes), 1, fixes)

    def test_an_ask_section_checks_run_list_of_answered_questions_is_no_ask(self):
        text = ask_section("Checks run:", "- Is the loop bounded? Yes, by n.",
                           "- Does the cache key include the repo? Yes.")

        self.assertEqual(kept_asks(text), [])

    def test_a_question_followed_by_its_answer_is_a_pass_note_and_a_trailing_question_is_an_ask(self):
        answered = finding_record.parse_finding("Is X bounded? Yes.")
        asked = finding_record.parse_finding("Is X bounded?")

        self.assertTrue(review_loop_findings.is_pass_note(answered))
        self.assertFalse(review_loop_findings.is_pass_note(asked))

    def test_a_trailing_question_bullet_in_an_ask_notes_list_starts_an_ask(self):
        asks = parsed_asks(ask_section("Checks run:", "- The ids are already used.", "- Should the cap be 3?"))

        self.assertEqual(len(asks), 2, asks)


class MixedCriteriaCoverageTest(unittest.TestCase):
    def test_a_plan_drift_ask_on_two_criteria_stays_when_an_impact_holds_only_one(self):
        ask = finding_record.parse_finding("[plan-drift] `docs/p.md:2` — AC1 and AC3 both fail for deletes.")
        impact = "PLAN-IMPACT: reword. acceptance_criteria: AC1"

        self.assertFalse(review_loop_findings.repeats_an_ask(ask, [], [impact]))
        self.assertFalse(review_loop_findings.repeats_an_ask(ask, [], [], [impact]))

    def test_a_plan_drift_ask_whose_criteria_are_all_covered_is_a_repeat(self):
        ask = finding_record.parse_finding("[plan-drift] `docs/p.md:2` — AC1 and AC3 both fail for deletes.")
        impact = "PLAN-IMPACT: reword. acceptance_criteria: AC1, AC3"

        self.assertTrue(review_loop_findings.repeats_an_ask(ask, [], [impact]))


class AskParsingTest(unittest.TestCase):
    def test_a_lead_in_line_does_not_merge_the_asks_under_it(self):
        asks = parsed_asks(ask_section(
            "Two questions for the user:",
            "- PLAN-IMPACT: the fix needs a new column. acceptance_criteria: AC2",
            "- [plan-drift] Should the retry budget be 3? change: set it to 3"))

        self.assertEqual(len(asks), 2, asks)
        self.assertTrue(asks[0].startswith("PLAN-IMPACT:"))
        self.assertTrue(asks[1].startswith("[plan-drift] Should the retry budget"))
        self.assertFalse(any(ask.startswith("Two questions") for ask in asks), asks)

    def test_a_lead_in_with_note_bullets_parses_as_one_item(self):
        asks = parsed_asks(ask_section("Checks run (no defects found):", "- I checked the claim and it holds.",
                                       "- The ids are already used."))

        self.assertEqual(len(asks), 1, asks)
        self.assertTrue(asks[0].startswith("Checks run"), asks)
        self.assertIn("I checked the claim and it holds.", asks[0])
        self.assertIn("The ids are already used.", asks[0])


class RejectedAskRepeatTest(unittest.TestCase):
    REJECTED = "app.py:3 should the window be pinned?"

    def repeats(self, ask_text, rejected_texts):
        rejected = [finding_record.parse_finding(text) for text in rejected_texts]
        return review_loop_findings.repeats_a_rejected_ask(finding_record.parse_finding(ask_text), rejected)

    def test_the_same_title_in_another_file_is_not_dropped(self):
        self.assertFalse(self.repeats("`util.py:3` [bug] should the window be pinned?", [self.REJECTED]))

    def test_another_claim_in_the_same_file_is_not_dropped(self):
        self.assertFalse(self.repeats("`app.py:3` [bug] drop the cache key entirely, please", [self.REJECTED]))

    def test_a_reworded_near_title_in_the_same_file_is_dropped(self):
        self.assertTrue(self.repeats("`app.py:9` [bug] should the window be pinned now?", [self.REJECTED]))

    def test_no_rejected_asks_drops_nothing(self):
        self.assertFalse(self.repeats("`app.py:3` [bug] should the window be pinned?", []))

    def test_a_rejected_ask_with_no_path_does_not_swallow_every_pathless_ask(self):
        self.assertFalse(self.repeats("Which tenant owns the shard key?", ["should the window be pinned?"]))

    def test_a_repeat_that_carries_a_change_part_is_dropped_on_its_question_alone(self):
        ask = ("`app.py:3` [bug] the retry window is never pinned — should the window be pinned to the config "
               "value? — change: read RETRY_WINDOW from config and pass it to retry()")
        question = review_loop_findings.ask_parts(ask).question

        self.assertTrue(self.repeats(ask, [f"app.py:3 {question}"]))

    def test_a_short_pathless_ask_is_dropped_when_raised_again_word_for_word(self):
        ask_text = "[bug] Should the cap be 3? — change: set the cap to 3"
        item = {"file_line": handback.UNLOCATED, "question": "Should the cap be 3?", "change": "set the cap to 3"}
        stored = review_fix_asks.rejected_ask_text(item)

        self.assertTrue(self.repeats(ask_text, [stored]))


class PassNoteExitsTest(unittest.TestCase):
    def test_each_exit_keeps_an_item_as_an_ask(self):
        items = {
            "a class tag alone": "`app.py:3` [test-gap] no test pins the zero case.",
            "a plan change alone": "PLAN-IMPACT: the fix needs a new column.",
            "a pointer to another ask": "The open ask about pinning the window still stands.",
            "a question": "Should the cap be 3?",
            "a change marker": "The cap is wrong. Change: raise it to 20.",
        }
        for label, text in items.items():
            with self.subTest(label):
                ask = finding_record.parse_finding(text)
                self.assertFalse(review_loop_findings.is_pass_note(ask), label)

    def test_a_bare_claim_is_a_pass_note(self):
        ask = finding_record.parse_finding("I checked every claim and each one holds.")

        self.assertTrue(review_loop_findings.is_pass_note(ask))


class RepeatedPathlessAskTest(unittest.TestCase):
    def test_two_pathless_asks_of_different_text_both_survive(self):
        earlier = finding_record.parse_finding("Should the retry cap be 3?")
        other = finding_record.parse_finding("Which tenant owns the shard key?")

        self.assertFalse(review_loop_findings.repeats_an_ask(other, [earlier], []))

    def test_two_pathless_asks_of_the_same_text_repeat(self):
        earlier = finding_record.parse_finding("Should the retry cap be 3?")
        same = finding_record.parse_finding("Should the retry cap be 3?")

        self.assertTrue(review_loop_findings.repeats_an_ask(same, [earlier], []))

    def test_a_plan_drift_ask_repeats_only_an_impact_with_the_criterion_line(self):
        ask = finding_record.parse_finding("`docs/p.md:2` [plan-drift] AC2 fails for deletes?")
        with_line = "PLAN-IMPACT: reword. acceptance_criteria: AC2"
        without_line = "PLAN-IMPACT: AC2 is mentioned in prose"

        self.assertTrue(review_loop_findings.repeats_an_ask(ask, [], [with_line]))
        self.assertFalse(review_loop_findings.repeats_an_ask(ask, [], [without_line]))

    def test_a_ruled_plan_drift_finding_without_a_criterion_line_names_every_id_in_it(self):
        ask = finding_record.parse_finding("`docs/p.md:2` [plan-drift] AC2 fails for deletes?")
        ruled = "[plan-drift] `docs/p.md:9` — AC2 is reworded narrower than the ticket."
        ruled_test_gap = "[test-gap] `docs/p.md:9` — AC2 has no test."

        self.assertTrue(review_loop_findings.repeats_an_ask(ask, [], [], [ruled]))
        self.assertFalse(review_loop_findings.repeats_an_ask(ask, [], [], [ruled_test_gap]))


if __name__ == "__main__":
    unittest.main()
