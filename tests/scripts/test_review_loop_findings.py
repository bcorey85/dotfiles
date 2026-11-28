"""A reviewer's pass note in the Ask section is no ask, and an ask that repeats an earlier ask is dropped."""
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import finding_record
import handback
import review_asks
import review_loop_findings
import standing_rulings

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


class DottedSymbolIsNotALocationTest(unittest.TestCase):
    def test_a_called_dotted_symbol_before_the_real_location_is_not_the_location(self):
        cases = [
            ("[bug] calls lib/file_lock.acquire() before review/x.py:40", ("review/x.py", 40)),
            ("[bug] calls lib/x.py.run() before review/x.py:40", ("review/x.py", 40)),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                found = finding_record.parse_finding(text)
                self.assertEqual((found.path, found.line), expected)

    def test_a_bare_path_with_any_extension_or_case_is_a_location_with_line_zero(self):
        cases = [
            ("[nit] docs/guide.mdx is stale", ("docs/guide.mdx", 0)),
            ("[nit] docs/README.MD is stale", ("docs/README.MD", 0)),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                found = finding_record.parse_finding(text)
                self.assertEqual((found.path, found.line), expected)


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

    ACCEPTED_DRIFT = "src/a.py:3 [plan-drift] Proposed change: reword AC2 acceptance_criteria: AC2"

    def test_a_refiled_plan_drift_finding_on_the_same_line_and_ids_as_an_accepted_one_is_ruled(self):
        refiled = ("src/a.py:3 [plan-drift] the reworded criterion now drops deletes, which the ticket asks for, so "
                   "the wording needs another look before it ships. acceptance_criteria: AC2")

        self.assertTrue(review_loop_findings.ruled_plan_impact(refiled, [], [self.ACCEPTED_DRIFT]))

    def test_a_plan_drift_finding_on_another_line_or_with_other_ids_is_not_ruled_by_an_accepted_one(self):
        other_line = "src/a.py:9 [plan-drift] the criterion drops deletes, so look again. acceptance_criteria: AC2"
        other_ids = "src/a.py:3 [plan-drift] the criterion drops deletes, so look again. acceptance_criteria: AC2, AC3"

        self.assertFalse(review_loop_findings.ruled_plan_impact(other_line, [], [self.ACCEPTED_DRIFT]))
        self.assertFalse(review_loop_findings.ruled_plan_impact(other_ids, [], [self.ACCEPTED_DRIFT]))

    def test_two_plan_drift_findings_on_one_line_that_name_no_criterion_are_not_ruled(self):
        accepted = "src/a.py:3 [plan-drift] Proposed change: reword the criterion"
        refiled = "src/a.py:3 [plan-drift] the criterion drops deletes, so look again."

        self.assertFalse(review_loop_findings.ruled_plan_impact(refiled, [], [accepted]))

    def test_a_finding_of_another_class_on_the_accepted_line_with_the_same_ids_is_not_ruled(self):
        bug = "src/a.py:3 [bug] the criterion drops deletes. acceptance_criteria: AC2"
        refiled_drift = ("src/a.py:3 [plan-drift] the reworded criterion now drops deletes, which the ticket asks "
                         "for, so the wording needs another look before it ships. acceptance_criteria: AC2")
        bug_accepted = "src/a.py:3 [bug] Proposed change: cap the retries acceptance_criteria: AC2"

        self.assertFalse(review_loop_findings.ruled_plan_impact(bug, [], [self.ACCEPTED_DRIFT]))
        self.assertFalse(review_loop_findings.ruled_plan_impact(refiled_drift, [], [bug_accepted]))

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


class ImpactHeadingSectionTest(unittest.TestCase):
    IMPACT = ("PLAN-IMPACT: `app.py:3` — the diff drops the 30 day cap the plan's AC2 names. "
              "acceptance_criteria: AC2")

    def test_a_plan_impact_line_under_its_own_heading_is_taken_in_as_an_ask(self):
        text = f"## Fix\nNone\n\n## Ask\nNone\n\n### Plan impact\n- {self.IMPACT}\n\n## Nit\nNone\n"

        asks = parsed_asks(text)

        self.assertEqual(len(asks), 1, asks)
        self.assertTrue(asks[0].startswith("PLAN-IMPACT:"), asks)

    def test_a_review_with_only_a_plan_impact_section_is_still_a_findings_layout(self):
        asks = parsed_asks(f"### Plan impact\n{self.IMPACT}\n")

        self.assertEqual(len(asks), 1, asks)

    def test_an_ask_and_a_plan_impact_line_in_one_review_are_both_kept_in_order(self):
        text = (f"## Fix\nNone\n\n## Ask\n- `app.py:9` [bug] Should the cap be 3? — change: set it to 3\n\n"
                f"### Plan impact\n- {self.IMPACT}\n\n## Nit\nNone\n")

        asks = parsed_asks(text)

        self.assertEqual(len(asks), 2, asks)
        self.assertIn("Should the cap be 3?", asks[0])
        self.assertTrue(asks[1].startswith("PLAN-IMPACT:"), asks)

    def test_two_unbulleted_plan_impact_lines_are_two_asks(self):
        text = ("### Plan impact\n"
                "`PLAN-IMPACT:` app.py:3 — the cap differs — `acceptance_criteria: none`\n"
                "`PLAN-IMPACT:` app.py:9 — the age differs — `acceptance_criteria: AC2`\n")

        asks = parsed_asks(text)

        self.assertEqual(len(asks), 2, asks)
        self.assertIn("app.py:3", asks[0])
        self.assertIn("acceptance_criteria: none", asks[0])
        self.assertNotIn("AC2", asks[0])
        self.assertIn("app.py:9", asks[1])
        self.assertIn("acceptance_criteria: AC2", asks[1])

    def test_bold_and_backtick_unbulleted_plan_impact_lines_each_start_an_ask(self):
        for prefix in ("`PLAN-IMPACT:`", "**PLAN-IMPACT:**"):
            with self.subTest(prefix=prefix):
                text = f"### Plan impact\n{prefix} app.py:3 — x\n{prefix} app.py:9 — y\n"

                self.assertEqual(len(parsed_asks(text)), 2)

    def test_unbulleted_plan_impact_lines_after_a_lead_in_line_are_two_asks(self):
        text = ("### Plan impact\n"
                "Two plan changes:\n"
                "PLAN-IMPACT: app.py:3 — the cap differs — acceptance_criteria: none\n"
                "PLAN-IMPACT: app.py:9 — the age differs — acceptance_criteria: AC2\n")

        asks = parsed_asks(text)

        self.assertEqual(len(asks), 2, asks)
        self.assertIn("app.py:3", asks[0])
        self.assertIn("acceptance_criteria: none", asks[0])
        self.assertNotIn("app.py:9", asks[0])
        self.assertIn("app.py:9", asks[1])
        self.assertNotIn("app.py:3", asks[1])

    def test_an_unbulleted_plan_impact_line_in_a_fix_section_stays_in_its_item(self):
        text = "## Fix\napp.py:3 [bug] x — fix: y\nPLAN-IMPACT: app.py:9 — z — acceptance_criteria: none\n"

        fixes = review_loop_findings.parse_review(text)["fix"]

        self.assertEqual(len(fixes), 1, fixes)

    def test_a_plan_impact_section_reading_none_adds_no_ask(self):
        self.assertEqual(parsed_asks("## Fix\nNone\n### Plan impact\nNone\n"), [])

    def test_a_wrapped_plan_impact_line_is_split_out_as_a_plan_change(self):
        text = "### Plan impact\n- `PLAN-IMPACT:` app.py:3 — x\n"

        items = review_loop_findings.parse_review(text)["ask"]

        self.assertEqual(len(review_loop_findings.plan_change_items(items)), 1, items)


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
        stored = review_asks.rejected_ask_text(item)

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


class ReviewerImpactKindTest(unittest.TestCase):
    """A reviewer's plan-change ask spans lines; parsing joins them, and the kind field must survive the join."""

    def impact_ask(self, *kind_lines):
        lines = ["- `docs/plans/p/plan.md:4` PLAN-IMPACT: the plan words AC1 loosely; the code is stricter.",
                 "  acceptance_criteria: AC1", *kind_lines]
        return parsed_asks(ask_section(*lines))[0]

    def test_a_kind_line_on_its_own_line_still_reads_after_the_ask_lines_are_joined(self):
        text = self.impact_ask("  kind: reword")

        self.assertTrue(standing_rulings.impact_rewords_criterion(text), text)

    def test_a_kind_field_after_a_dash_separator_reads_too(self):
        text = self.impact_ask("  — kind: reword")

        self.assertTrue(standing_rulings.impact_rewords_criterion(text), text)

    def test_a_cut_kind_is_no_reword_and_no_kind_is_no_reword(self):
        self.assertFalse(standing_rulings.impact_rewords_criterion(self.impact_ask("  kind: cut")))
        self.assertFalse(standing_rulings.impact_rewords_criterion(self.impact_ask()))

class AskChangeMarkShapesTest(unittest.TestCase):
    """A reviewer writes `Change if <condition>:` in many forms; each one splits the question from the change."""
    QUESTION = "Is it acceptable that a commit run through a script given a quoted argument no longer counts?"
    CHANGE = "remove the quoted-argument exemption, so that a script-file run counts."

    def test_every_change_if_condition_splits_the_question_from_the_change(self):
        conditions = ["accepted", "yes", "not", "moved", "not accepted", "dropped", "no", "declined", "delete",
                      "`accepted`", "**not accepted**"]
        for condition in conditions:
            for label in (f"Change if {condition}:", f"change if {condition}:"):
                with self.subTest(label):
                    ask = f"`gates/x.py:12` [security]: The run no longer counts. {self.QUESTION} {label} {self.CHANGE}"
                    parts = review_loop_findings.ask_parts(ask)

                    self.assertEqual(parts.change, self.CHANGE)
                    self.assertTrue(parts.question.endswith(self.QUESTION), parts.question)
                    self.assertNotIn("hange if", parts.question)

    def test_a_four_word_change_if_label_is_not_a_mark(self):
        ask = f"{self.QUESTION} Change if the user declines it: {self.CHANGE}"

        parts = review_loop_findings.ask_parts(ask)

        self.assertEqual(parts.change, ask)

    def test_a_branch_label_split_over_a_newline_or_spaces_is_still_a_branch(self):
        for second_mark in ("Change if no:", "Change\nif no:", "Change  if  no:"):
            with self.subTest(second_mark):
                ask = f"{self.QUESTION} Change if yes: drop it. {second_mark} keep it."
                parts = review_loop_findings.ask_parts(ask)

                self.assertEqual(parts.question, self.QUESTION)
                self.assertTrue(parts.change.startswith("drop it."), parts.change)

    def test_an_ask_with_two_branches_keeps_both_in_its_change(self):
        ask = f"`a.py:1` [bug]: {self.QUESTION} Change if yes: drop the cache. Change if no: keep the cache."
        parts = review_loop_findings.ask_parts(ask)

        self.assertTrue(parts.question.endswith(self.QUESTION), parts.question)
        self.assertEqual(parts.change, "drop the cache. Change if no: keep the cache.")
        self.assertTrue(review_asks.is_conditional_change(parts.change))

    def test_a_single_change_if_accepted_ask_is_not_conditional(self):
        parts = review_loop_findings.ask_parts(f"{self.QUESTION} Change if accepted: {self.CHANGE}")

        self.assertEqual(parts.change, self.CHANGE)
        self.assertFalse(review_asks.is_conditional_change(parts.change))

    def test_a_plain_change_then_a_conditional_branch_is_refused_not_split_to_the_branch(self):
        ask = "Is it fine to drop the cache? change: drop it. Change if no: keep it."

        parts = review_loop_findings.ask_parts(ask)

        self.assertEqual(parts.question, "Is it fine to drop the cache?")
        self.assertEqual(parts.change, "drop it. Change if no: keep it.")
        self.assertTrue(review_asks.is_conditional_change(parts.change))

    def test_a_plain_change_alone_still_splits(self):
        parts = review_loop_findings.ask_parts(f"{self.QUESTION} change: {self.CHANGE}")

        self.assertEqual(parts.change, self.CHANGE)
        self.assertFalse(review_asks.is_conditional_change(parts.change))

    def test_a_change_if_not_accepted_ask_states_an_ask(self):
        self.assertTrue(review_loop_findings.states_an_ask(f"Remove it. Change if not accepted: {self.CHANGE}"))


class ColonEndedFindingTest(unittest.TestCase):
    LOCATION = "lib/a.py:10"
    LEAD = f"{LOCATION} [bug] the parser mishandles these cases:"
    NEXT = "lib/b.py:20 [bug] a separate finding"

    def assert_one_finding_with_cases(self, items):
        self.assertEqual(items, [f"{self.LEAD} first case second case", self.NEXT])
        located = finding_record.parse_finding(items[0])
        self.assertEqual((located.path, located.line), ("lib/a.py", 10))

    def test_section_format_keeps_case_bullets_at_the_lead_indent_and_nested(self):
        cases = {
            "same indent": ["- first case", "- second case"],
            "nested": ["  - first case", "  - second case"],
        }
        for name, case_lines in cases.items():
            with self.subTest(name):
                text = "## Fix\n" + "\n".join([f"- {self.LEAD}", *case_lines, f"- {self.NEXT}"]) + "\n"

                fixes = review_loop_findings.parse_review_texts(text)["fix"]

                self.assert_one_finding_with_cases(fixes)

    def test_tagged_format_keeps_untagged_case_bullets_at_the_lead_indent_and_nested(self):
        cases = {
            "same indent": ["- first case", "- second case"],
            "nested": ["  - first case", "  - second case"],
        }
        for name, case_lines in cases.items():
            with self.subTest(name):
                text = "\n".join([f"- fix: {self.LEAD}", *case_lines, f"- fix: {self.NEXT}"]) + "\n"

                fixes = review_loop_findings.parse_tagged_bullets(text)["fix"]

                self.assert_one_finding_with_cases(fixes)

    def test_a_tagged_bullet_without_a_colon_drops_untagged_bullets_at_its_indent(self):
        text = "- fix: lib/a.py:10 [bug] wrong\n- stray note\n- fix: lib/b.py:2 [bug] other\n"

        fixes = review_loop_findings.parse_tagged_bullets(text)["fix"]

        self.assertEqual(fixes, ["lib/a.py:10 [bug] wrong", "lib/b.py:2 [bug] other"])

    def test_a_plain_line_at_the_top_indent_ends_the_tagged_continuation(self):
        text = f"- fix: {self.LEAD}\n- first case\nSummary line\n- second case\n- fix: {self.NEXT}\n"

        fixes = review_loop_findings.parse_tagged_bullets(text)["fix"]

        self.assertEqual(fixes, [f"{self.LEAD} first case", self.NEXT])

    def test_nested_cases_do_not_swallow_an_unlocated_bullet_at_the_item_indent(self):
        unlocated = "unrelated nit about wording"
        for section_name in ("Fix", "Nit"):
            with self.subTest(section_name):
                text = f"## {section_name}\n- {self.LEAD}\n  - first case\n  - second case\n- {unlocated}\n"

                items = review_loop_findings.parse_review_texts(text)[section_name.lower()]

                self.assertEqual(items, [f"{self.LEAD} first case second case", unlocated])

    def test_sub_bullets_and_plain_lead_ins_keep_the_notes_list_open_to_the_next_located_item(self):
        plain = "The other claims check out:"
        cases = {
            "plain lead-in, nested notes, then a note": (
                f"- {self.LOCATION} [bug] x\n{plain}\n  - note one\n- note two\n",
                [f"{self.LOCATION} [bug] x {plain} note one note two"],
            ),
            "plain lead-in, sub-bullet under a note": (
                f"- {self.LOCATION} [bug] x\n{plain}\n- note one\n  - detail\n- note two\n",
                [f"{self.LOCATION} [bug] x {plain} note one detail note two"],
            ),
            "colon item, sub-bullet under a case": (
                f"- {self.LEAD}\n- case1\n  - detail\n- case2\n- {self.NEXT}\n",
                [f"{self.LEAD} case1 detail case2", self.NEXT],
            ),
        }
        for name, (body, expected) in cases.items():
            with self.subTest(name):
                fixes = review_loop_findings.parse_review_texts("## Fix\n" + body)["fix"]

                self.assertEqual(fixes, expected)

    def test_a_stated_ask_closes_the_notes_list_of_a_located_colon_ask(self):
        text = "## Ask\n- lib/a.py:1 [bug] Two questions:\n- Should X? Change if accepted: do y\n- plain note\n"

        asks = review_loop_findings.parse_review_texts(text)["ask"]

        self.assertEqual(asks, ["lib/a.py:1 [bug] Two questions:", "Should X? Change if accepted: do y",
                                "plain note"])

    def test_a_tagged_bullet_without_a_colon_takes_a_deeper_untagged_bullet_as_its_detail(self):
        text = "- fix: lib/a.py:10 [bug] wrong\n  - detail\n- fix: lib/b.py:2 [bug] other\n"

        fixes = review_loop_findings.parse_tagged_bullets(text)["fix"]

        self.assertEqual(fixes, ["lib/a.py:10 [bug] wrong detail", "lib/b.py:2 [bug] other"])

    def test_a_tilde_range_parses_whole_with_its_path_and_line_zero(self):
        text = "## Fix\n- lib/a.py:~441-452 [bug] the range is approximate\n- lib/b.py:3 [bug] other\n"

        fixes = review_loop_findings.parse_review_texts(text)["fix"]
        located = finding_record.parse_finding(fixes[0])

        self.assertEqual(len(fixes), 2, fixes)
        self.assertEqual((located.path, located.line), ("lib/a.py", 0))


class FindingLocationTest(unittest.TestCase):
    QUOTED_FIXTURE = ('— the test passes with the bug in place. FINDING ("a.py:1 [plan-drift] PLAN-IMPACT: the '
                      'plan changes")')

    def test_a_bare_path_first_is_the_location_not_a_quoted_path_line_after_it(self):
        text = f"[test-gap] /home/u/repo/tests/scripts/test_x.py (test_name) {self.QUOTED_FIXTURE}"

        finding = finding_record.parse_finding(text)

        self.assertEqual((finding.path, finding.line), ("/home/u/repo/tests/scripts/test_x.py", 0))
        self.assertEqual(finding.finding_class, "test-gap")

    def test_a_class_tag_inside_a_backtick_span_is_not_the_class(self):
        finding = finding_record.parse_finding("lib/a.py:3 [bug] the doc says `[plan-drift]` is routed")

        self.assertEqual(finding.finding_class, "bug")

    def test_a_class_tag_before_the_location_is_the_class(self):
        finding = finding_record.parse_finding("[bug] lib/a.py:3 wrong")

        self.assertEqual(finding.finding_class, "bug")

    def test_a_path_line_before_an_approximate_pointer_is_the_location(self):
        finding = finding_record.parse_finding("lib/a.py:5 [bug] see `tests/x.py:~40`")

        self.assertEqual((finding.path, finding.line), ("lib/a.py", 5))

    def test_a_path_line_inside_a_multi_line_backtick_span_is_no_location(self):
        finding = finding_record.parse_finding("the snippet `run(\n a.py:1)` is wrong")

        self.assertEqual((finding.path, finding.line), ("", 0))

    def test_a_leading_pointer_with_a_spaced_line_list_or_an_approximate_line_is_the_location(self):
        cases = {
            "spaced list": ("- fix: [weak-assertion] `frontend/app/utils/markdown.test.ts:8-12, 20-31` — gap",
                            ("frontend/app/utils/markdown.test.ts", 8)),
            "spaced list then a later path": (
                "`features/imports/ImportForm.vue:92-93, 101` [duplication]: dup (features/imports/limits.ts:2)",
                ("features/imports/ImportForm.vue", 92)),
            "approximate line": ("[test-gap] `tests/a/test_x.py:~40` — the helper at lib/y.py:30",
                                 ("tests/a/test_x.py", 0)),
            "approximate line, no directory": ("[test-gap] `test_x.py:~40` — the helper at lib/y.py:30",
                                               ("test_x.py", 0)),
            "closing backtick before the line": ("`/abs/dir/markdown.test.ts`:4-48 — gap",
                                                 ("/abs/dir/markdown.test.ts", 4)),
        }
        for name, (text, expected) in cases.items():
            with self.subTest(name):
                finding = finding_record.parse_finding(text)

                self.assertEqual((finding.path, finding.line), expected, name)

    def test_a_path_line_first_beats_a_bare_path_of_another_file_after_it(self):
        finding = finding_record.parse_finding("src/a.py:5 is wrong, see also docs/other.md")

        self.assertEqual((finding.path, finding.line), ("src/a.py", 5))

    def test_a_bare_path_guards_leave_route_paths_and_paths_with_a_trailing_part_alone(self):
        cases = {
            "preceding bracket": "the route [id]/page/edit.vue is wrong",
            "path followed by a slash": "see src/a.py/extra for it",
            "preceding colon": "key:src/a.py is wrong",
            "preceding closing bracket": "x]src/a.py is wrong",
            "home-relative path": "[docs] ~/x/y.md — stale",
            "home-relative path with a line": "see ~/x/y.md:12 — stale",
        }
        for name, text in cases.items():
            with self.subTest(name):
                finding = finding_record.parse_finding(text)

                self.assertEqual((finding.path, finding.line), ("", 0), name)

    def test_a_bare_path_in_a_backtick_span_without_a_line_is_the_location(self):
        cases = {
            "alone": "`src/a.py` is wrong",
            "before a path line of another file": "`src/a.py` is wrong, see lib/b.py:3",
        }
        for name, text in cases.items():
            with self.subTest(name):
                finding = finding_record.parse_finding(text)

                self.assertEqual((finding.path, finding.line), ("src/a.py", 0), name)

    def test_a_bare_path_with_a_further_extension_is_not_cut_at_the_first_one(self):
        finding = finding_record.parse_finding("see src/a.py.bak for it")

        self.assertEqual((finding.path, finding.line), ("src/a.py.bak", 0))

    def test_an_apostrophe_in_a_word_does_not_open_a_quote(self):
        finding = finding_record.parse_finding("I don't see a.py:1 here, and it isn't wrong")

        self.assertEqual((finding.path, finding.line), ("a.py", 1))

    def test_a_dotted_file_name_with_a_line_is_not_cut_at_its_first_extension(self):
        finding = finding_record.parse_finding("src/services/user-status.service.ts:862 — the call is wrong")

        self.assertEqual((finding.path, finding.line), ("src/services/user-status.service.ts", 862))

    def test_the_loop_does_not_skip_that_finding_as_absent_from_the_tree(self):
        with tempfile.TemporaryDirectory() as repo:
            test_file = pathlib.Path(repo) / "tests" / "scripts" / "test_x.py"
            finding = finding_record.parse_finding(f"[test-gap] {test_file} (test_name) {self.QUOTED_FIXTURE}")

            absent = review_loop_findings.names_absent_file(repo, [], finding)

        self.assertEqual(finding.line, 0)
        self.assertFalse(absent)

    def test_a_path_with_a_dollar_or_plus_parses_whole_and_its_file_is_kept_by_the_intake(self):
        cases = [
            ("src/routes/$postId.test.tsx", 12),
            ("src/routes/+page.svelte", 3),
        ]
        with tempfile.TemporaryDirectory() as repo:
            for path, line in cases:
                with self.subTest(path=path):
                    file = pathlib.Path(repo) / path
                    file.parent.mkdir(parents=True, exist_ok=True)
                    file.write_text("x\n")
                    text = f"`{path}:{line}` [bug] the handler is wrong"
                    review = review_loop_findings.parse_review(f"## Fix\n- {text}\n\n## Ask\nNone\n\n## Nit\nNone\n")

                    kept, absent = review_loop_findings.absent_file_split(repo, [], review)

                    self.assertEqual([(item.path, item.line) for item in kept["fix"]], [(path, line)])
                    self.assertEqual(absent, [])

    def test_a_bare_path_of_a_file_the_finding_asks_for_is_not_absent(self):
        with tempfile.TemporaryDirectory() as repo:
            text = "[test-gap] tests/scripts/test_new.py (new test needed; source lib/new.py:73) — no test"
            finding = finding_record.parse_finding(text)

            absent = review_loop_findings.names_absent_file(repo, [], finding)

        self.assertFalse(absent)

    def test_an_absent_file_is_skipped_for_a_path_line_and_an_approximate_line_but_not_a_bare_path(self):
        cases = [
            ("lib/gone.py:7 [bug] wrong", True),
            ("`lib/gone.py:~7` [bug] wrong", True),
            ("lib/gone.py:~7 [bug] wrong", True),
            ("lib/gone.py is wrong at lib/gone.py:7 [bug]", True),
            ("[test-gap] lib/gone.py has no test", False),
        ]
        with tempfile.TemporaryDirectory() as repo:
            for text, expected in cases:
                with self.subTest(text=text):
                    finding = finding_record.parse_finding(text)

                    absent = review_loop_findings.names_absent_file(repo, [], finding)

                    self.assertEqual(absent, expected)

    def test_a_merged_finding_keeps_the_bare_flag_of_its_first_part(self):
        cases = [
            ("[test-gap] lib/gone.py has no test", False),
            ("lib/gone.py:7 [bug] wrong", True),
        ]
        with tempfile.TemporaryDirectory() as repo:
            for first_text, expected in cases:
                with self.subTest(text=first_text):
                    parts = [finding_record.parse_finding(first_text), finding_record.parse_finding("[bug] other")]
                    merged = finding_record.combine(parts)

                    absent = review_loop_findings.names_absent_file(repo, [], merged)

                    self.assertEqual(absent, expected)

    def test_a_path_line_inside_quotes_or_a_longer_backtick_span_is_no_location(self):
        cases = {
            "double quotes": 'the message says "see a.py:1 for it" and nothing else',
            "single quotes": "the message says 'see a.py:1 for it' and nothing else",
            "a longer backtick span": "the call `run(a.py:1)` is wrong",
        }
        for name, text in cases.items():
            with self.subTest(name):
                finding = finding_record.parse_finding(text)

                self.assertEqual((finding.path, finding.line), ("", 0), name)

    def test_a_path_line_after_a_quoted_one_is_the_location(self):
        finding = finding_record.parse_finding('"a.py:1" is quoted, the bug is at `b/c.py:7` [bug] wrong')

        self.assertEqual((finding.path, finding.line), ("b/c.py", 7))

    def test_a_leading_backticked_path_line_is_still_the_location(self):
        finding = finding_record.parse_finding(f"`lib/reviewed_tree.py:315` [test-gap] gap {self.QUOTED_FIXTURE}")

        self.assertEqual((finding.path, finding.line), ("lib/reviewed_tree.py", 315))

    def test_a_bare_path_then_a_path_line_of_the_same_file_keeps_the_line(self):
        finding = finding_record.parse_finding("tests/x.py is wrong at tests/x.py:12 [bug] it fails")

        self.assertEqual((finding.path, finding.line), ("tests/x.py", 12))


if __name__ == "__main__":
    unittest.main()
