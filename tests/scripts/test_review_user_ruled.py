import os
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import finding_record
import handback_store
import plan_format
import review_user_ruled
from handback_store import NO_RULINGS, AdoptedRuling, Rulings

REAL_ASK = {"question": "keep the retry?", "file_line": "src/retry.ts:10", "class": "bug", "gate": "none"}


def leave_out(*args):
    """The kept findings, user-ruled numbers, session-ruled numbers and dropped findings of the leave-out."""
    return tuple(review_user_ruled.leave_out_ruled_impacts(*args)[:4])


def given(item, **fields):
    return {"item": item, "reason": "coder reason", "file_line": "x.py:1", "class": "other", "given": True, **fields}


class SkippedEntryAsAskTest(unittest.TestCase):
    def test_an_ask_takes_its_location_class_and_proposed_change_from_the_entry_fields(self):
        entry = {"item": "the greeting is wrong", "reason": "a fixture", "file_line": "README.md:1", "class": "bug"}
        ask = review_user_ruled.skipped_entry_as_ask(entry)
        self.assertEqual(ask["file_line"], "README.md:1")
        self.assertEqual(ask["class"], "bug")
        self.assertEqual(ask["change"], "the greeting is wrong")
        self.assertIs(ask["user_ruled"], True)

    def test_an_unclassed_unlocated_entry_asks_with_the_default_class_and_one_line_text(self):
        entry = {"item": "plain\ntext", "reason": "two\nlines", "file_line": "unlocated", "class": None}
        ask = review_user_ruled.skipped_entry_as_ask(entry)
        self.assertEqual(ask["class"], "other")
        self.assertEqual(ask["file_line"], review_user_ruled.handback.UNLOCATED)
        self.assertEqual(ask["change"], "plain text")
        self.assertIn("two lines", ask["question"])
        self.assertNotIn("\n", ask["question"])

    def test_a_reason_ending_in_sentence_punctuation_leaves_one_terminal_mark(self):
        for ending in [".", "?", "!", ":", ";", " ?"]:
            entry = {"item": "x", "reason": f"not needed{ending}", "file_line": "x.py:1", "class": "other"}
            ask = review_user_ruled.skipped_entry_as_ask(entry)
            self.assertIn("not needed. Apply it anyway?", ask["question"], f"ending {ending!r}")


class ReaskedFindingsTest(unittest.TestCase):
    def test_a_question_naming_a_findings_file_and_line_marks_only_that_finding(self):
        texts = ["a.py:3 Proposed change: deny it", "a.py:9 Proposed change: log it", "plain text with no location"]
        findings = [finding_record.parse_finding(text) for text in texts]
        reasked = review_user_ruled.reasked_findings(findings, ["unrelated?", "a.py:3 deny or reword?"], texts)
        self.assertEqual(list(reasked), [1])
        self.assertTrue(reasked[1].startswith("SKIPPED 1: "))
        self.assertIn("a.py:3 deny or reword?", reasked[1])

    def test_a_ruled_finding_with_no_path_is_not_marked_by_a_question_naming_a_location(self):
        text = "plain text with no location"
        findings = [finding_record.parse_finding(text)]
        self.assertEqual(review_user_ruled.reasked_findings(findings, ["a.py:3 deny or reword?"], [text]), {})

    def test_a_question_naming_two_locations_marks_the_finding_when_one_matches(self):
        text = "a.py:3 Proposed change: deny it"
        findings = [finding_record.parse_finding(text)]
        reasked = review_user_ruled.reasked_findings(findings, ["b.py:7 and a.py:3 conflict?"], [text])
        self.assertEqual(list(reasked), [1])

    def test_a_question_naming_a_longer_line_or_path_does_not_mark_the_finding(self):
        text = "a.py:3 Proposed change: deny it"
        findings = [finding_record.parse_finding(text)]
        for question in ["a.py:30 deny or reword?", "a.py:31 deny or reword?", "src/a.py:31 deny or reword?",
                         "lib/a.py:3 deny or reword?"]:
            self.assertEqual(review_user_ruled.reasked_findings(findings, [question], [text]), {}, question)

    def test_no_open_question_marks_nothing(self):
        text = "a.py:3 Proposed change: deny it"
        findings = [finding_record.parse_finding(text)]
        self.assertEqual(review_user_ruled.reasked_findings(findings, [], [text]), {})

    def test_a_finding_the_user_did_not_rule_on_is_not_marked_and_keeps_its_number(self):
        texts = ["a.py:3 Proposed change: deny it", "a.py:9 Proposed change: log it"]
        findings = [finding_record.parse_finding(text) for text in texts]
        questions = ["a.py:3 deny or reword?", "a.py:9 log or drop?"]
        reasked = review_user_ruled.reasked_findings(findings, questions, [texts[1]])
        self.assertEqual(list(reasked), [2])
        self.assertTrue(reasked[2].startswith("SKIPPED 2: "))


class DropPacketUserRuledMarksTest(unittest.TestCase):
    def test_a_mark_the_packet_carries_is_dropped_and_the_ask_kept(self):
        packet = {"ask": [{**REAL_ASK, "user_ruled": True}, dict(REAL_ASK)]}
        review_user_ruled.drop_packet_user_ruled_marks(packet)
        self.assertEqual(packet["ask"], [REAL_ASK, REAL_ASK])

    def test_a_packet_with_no_ask_key_is_left_alone(self):
        packet = {}
        review_user_ruled.drop_packet_user_ruled_marks(packet)
        self.assertEqual(packet, {})


class SkippedBecomeAsksTest(unittest.TestCase):
    def test_given_skips_join_the_existing_asks_after_them(self):
        packet = {"ask": [REAL_ASK], "skipped_fp": [given("one", file_line="a.py:1"), given("two", file_line="b.py:2")]}
        review_user_ruled.skipped_become_asks(packet, ["one", "two"])
        self.assertEqual(len(packet["ask"]), 3)
        self.assertEqual(packet["ask"][0], REAL_ASK)
        self.assertEqual([ask["file_line"] for ask in packet["ask"][1:]], ["a.py:1", "b.py:2"])
        self.assertEqual(packet["skipped_fp"], [])

    def test_a_skip_not_given_by_the_caller_stays_a_skip(self):
        reviewer_skip = {"item": "c.py:3 three", "reason": "round two", "file_line": "c.py:3", "class": "other"}
        packet = {"ask": [], "skipped_fp": [given("a.py:1 one"), reviewer_skip]}
        review_user_ruled.skipped_become_asks(packet, ["a.py:1 one", "c.py:3 three"])
        self.assertEqual(len(packet["ask"]), 1)
        self.assertEqual(packet["skipped_fp"], [reviewer_skip])

    def test_only_a_skip_of_a_finding_the_user_ruled_on_becomes_an_ask(self):
        session_ruled = given("a.py:1 one", file_line="a.py:1")
        user_ruled = given("b.py:2 two", file_line="b.py:2")
        packet = {"ask": [], "skipped_fp": [session_ruled, user_ruled]}
        review_user_ruled.skipped_become_asks(packet, ["b.py:2 two"])
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["b.py:2"])
        self.assertEqual(packet["skipped_fp"], [session_ruled])

    def test_skips_with_the_same_text_as_a_user_ruled_finding_all_become_asks(self):
        # A skip names its finding by text alone, so two findings with one text cannot be told apart.
        twins = [given("a.py:1 one"), given("a.py:1 one")]
        packet = {"ask": [], "skipped_fp": twins}
        review_user_ruled.skipped_become_asks(packet, ["a.py:1 one"])
        self.assertEqual(len(packet["ask"]), 2)
        self.assertEqual(packet["skipped_fp"], [])

    def test_no_user_ruled_finding_leaves_every_skip_in_place(self):
        packet = {"ask": [], "skipped_fp": [given("a.py:1 one")]}
        review_user_ruled.skipped_become_asks(packet, [])
        self.assertEqual(packet["ask"], [])
        self.assertEqual(len(packet["skipped_fp"]), 1)

    def test_a_skip_of_a_ruled_plan_impact_stays_a_skip_and_an_ordinary_one_becomes_an_ask(self):
        impact = "a.py:1 [plan-drift] does AC2 hold? acceptance_criteria: AC2"
        ordinary = "b.py:2 [bug] off by one"
        packet = {"ask": [], "skipped_fp": [given(impact), given(ordinary, file_line="b.py:2")]}
        ruled = ["a.py:1 [plan-drift] does AC2 hold? acceptance_criteria: AC2 (ruled)"]

        review_user_ruled.skipped_become_asks(packet, [impact, ordinary], Rulings(ruled, []))

        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["b.py:2"])
        self.assertEqual([entry["item"] for entry in packet["skipped_fp"]], [impact])


class LeaveOutRuledImpactsTest(unittest.TestCase):
    def test_a_ruled_plan_impact_is_dropped_and_the_user_ruled_numbers_follow_the_rest(self):
        impact = "a.py:1 [plan-drift] does AC2 hold? acceptance_criteria: AC2"
        findings = ["x.py:1 [bug] one", impact, "y.py:2 [bug] two"]
        ruled = ["a.py:1 [plan-drift] does AC2 hold? acceptance_criteria: AC2 (ruled)"]

        rulings = Rulings(ruled, [])
        kept, numbers, _session, dropped = leave_out(findings, [2, 3], rulings)

        self.assertEqual((kept, numbers, dropped), ([findings[0], findings[2]], [2], [impact]))

    def test_an_accepted_finding_on_a_ruled_criterion_stays_unless_it_is_the_ruled_change_itself(self):
        accepted = ("app.py:9 [plan-drift] purge() skips deletes that AC2 requires "
                    "Proposed change: handle deletes in purge()")
        ruled = ["PLAN-IMPACT: AC2 says 30 days but the code keeps 7 acceptance_criteria: AC2 "
                 "— change: reword AC2 to 7 days"]

        rulings = Rulings(ruled, [])
        self.assertEqual(leave_out([accepted], [1], rulings), ([accepted], [1], [], []))

    def test_the_exact_accepted_finding_is_left_out_and_a_different_one_on_the_same_criterion_stays(self):
        exact = "app.py:9 [plan-drift] does AC2 hold for deletes? Proposed change: keep the narrower AC2"
        different = "b.py:3 [plan-drift] purge() skips deletes that AC2 requires Proposed change: handle deletes"
        ruled = ["[plan-drift] does AC2 hold for deletes? acceptance_criteria: AC2 — change: keep the narrower AC2"]
        stored_finding = "app.py:9 [plan-drift] does AC2 hold for deletes?   Proposed change: keep the narrower AC2"

        rulings = Rulings(ruled, [stored_finding])
        result = leave_out([exact, different], [1, 2], rulings)

        self.assertEqual(result, ([different], [1], [], [exact]))

    def test_a_skipped_entry_of_the_exact_accepted_finding_stays_a_skip_and_a_different_one_becomes_an_ask(self):
        exact = "app.py:9 [plan-drift] does AC2 hold for deletes? Proposed change: keep the narrower AC2"
        different = "b.py:3 [plan-drift] purge() skips deletes that AC2 requires Proposed change: handle deletes"
        packet = {"ask": [], "skipped_fp": [given(exact), given(different, file_line="b.py:3")]}

        review_user_ruled.skipped_become_asks(packet, [exact, different], Rulings([], [exact]))

        self.assertEqual([entry["item"] for entry in packet["skipped_fp"]], [exact])
        self.assertEqual([ask["file_line"] for ask in packet["ask"]], ["b.py:3"])

    def test_an_accepted_finding_that_is_a_near_title_of_a_ruled_impact_is_left_out(self):
        accepted = "a.py:1 [plan-drift] the reword of AC2 is narrower than the ticket acceptance_criteria: AC2"
        ruled = ["a.py:1 [plan-drift] the reword of AC2 is narrower than the ticket! acceptance_criteria: AC2"]

        rulings = Rulings(ruled, [])
        self.assertEqual(leave_out([accepted], [1], rulings), ([], [], [], [accepted]))

    def test_a_finding_the_user_did_not_accept_is_left_out_by_criterion_ids(self):
        other = "a.py:1 [plan-drift] does AC2 hold? acceptance_criteria: AC2"
        ruled = ["PLAN-IMPACT: AC2 reworded. acceptance_criteria: AC2"]

        rulings = Rulings(ruled, [])
        self.assertEqual(leave_out([other, "y.py:2 [bug] two"], [2], rulings),
                         (["y.py:2 [bug] two"], [1], [], [other]))

    def test_the_session_ruled_number_follows_the_drop_of_an_earlier_finding(self):
        settled = "a.py:1 [plan-drift] does AC2 hold? Proposed change: keep AC2"
        other = "b.py:3 [plan-drift] purge() skips deletes Proposed change: handle deletes"
        rulings = Rulings(["PLAN-IMPACT: unrelated cache change. acceptance_criteria: none"], [settled])

        result = leave_out([settled, other], [1], rulings, [2])

        self.assertEqual(result, ([other], [], [1], [settled]))

    def test_a_session_ruled_number_stays_as_named_when_nothing_is_dropped(self):
        twin = "a.py:1 [plan-drift] does AC2 hold? Proposed change: keep AC2"

        result = leave_out([twin, twin], [], NO_RULINGS, [2])

        self.assertEqual(result, ([twin, twin], [], [2], []))

    def test_a_session_accepted_finding_sharing_a_criterion_id_with_a_ruling_stays_in_the_fix_run(self):
        different = "b.py:3 [plan-drift] purge() skips deletes that AC2 requires Proposed change: handle deletes"
        ruled = ["PLAN-IMPACT: AC2 reworded. acceptance_criteria: AC2"]

        result = leave_out([different], [], Rulings(ruled, []), [1])

        self.assertEqual(result, ([different], [], [1], []))

    def test_nothing_is_dropped_when_no_ruling_is_recorded(self):
        findings = ["a.py:1 [plan-drift] does AC2 hold? acceptance_criteria: AC2"]

        self.assertEqual(leave_out(findings, [1], NO_RULINGS),
                         (findings, [1], [], []))


IMPACT = "PLAN-IMPACT: AC2 reworded. acceptance_criteria: AC2"
FINDING = "a.py:1 [plan-drift] PLAN-IMPACT: AC2 reworded. acceptance_criteria: AC2"
ADOPTED = AdoptedRuling(IMPACT, FINDING, "the user", "2026-11-19 10:00")


class AdoptedRulingTest(unittest.TestCase):
    def test_an_adopted_ruling_keeps_its_finding_marked_and_user_ruled_and_a_keep_ruling_drops_it(self):
        adopted = Rulings([], [], (ADOPTED,))
        keep = Rulings([IMPACT], [FINDING])

        kept_result = leave_out([FINDING], [], adopted)
        dropped_result = leave_out([FINDING], [1], keep)

        marked = review_user_ruled.adopted_issue(FINDING, ADOPTED)
        self.assertEqual(kept_result, ([marked], [1], [], []))
        self.assertIn("the user, ruled 2026-11-19 10:00", marked)
        self.assertEqual(dropped_result, ([], [], [], [FINDING]))

    def test_the_left_out_names_the_ruling_of_each_adopted_finding_by_its_number(self):
        other = "b.py:2 [bug] unrelated finding"

        result = review_user_ruled.leave_out_ruled_impacts([other, FINDING], [], Rulings([], [], (ADOPTED,)))

        self.assertEqual(result.adopted, {2: ADOPTED})

    def test_a_second_ruling_for_a_matched_change_adds_no_finding(self):
        again = AdoptedRuling(IMPACT, FINDING, "the user", "2026-11-19 11:00")

        result = review_user_ruled.leave_out_ruled_impacts([FINDING], [], Rulings([], [], (ADOPTED, again)))

        self.assertEqual(len(result.kept), 1)

    def test_an_unaccepted_finding_that_is_the_ruling_text_adds_no_second_finding(self):
        text = "PLAN-IMPACT: AC2 reworded."
        finding = f"app.py:2 [plan-drift] {text}"
        ruling = AdoptedRuling(text, None, "the user", "2026-11-19 10:00")

        result = review_user_ruled.leave_out_ruled_impacts([finding], [], Rulings([], [], (ruling,)))

        self.assertEqual(result.kept, [review_user_ruled.adopted_issue(finding, ruling)])

    def test_an_adopted_ruling_with_no_matching_finding_adds_its_text_as_a_user_ruled_finding(self):
        other = "b.py:2 [bug] unrelated finding"
        adopted = Rulings([], [], (ADOPTED,))

        result = leave_out([other], [], adopted)

        marked = review_user_ruled.adopted_issue(IMPACT, ADOPTED)
        self.assertEqual(result, ([other, marked], [2], [], []))

    def test_the_numbers_follow_a_drop_beside_an_adopted_finding(self):
        kept_impact = "PLAN-IMPACT: AC5 dropped. acceptance_criteria: AC5"
        kept_finding = "c.py:3 [plan-drift] PLAN-IMPACT: AC5 dropped. acceptance_criteria: AC5"
        rulings = Rulings([kept_impact], [kept_finding], (ADOPTED,))

        result = leave_out([kept_finding, FINDING], [1], rulings)

        self.assertEqual(result, ([review_user_ruled.adopted_issue(FINDING, ADOPTED)], [1], [], [kept_finding]))
        full = review_user_ruled.leave_out_ruled_impacts([kept_finding, FINDING], [1], rulings)
        self.assertEqual(full.adopted, {1: ADOPTED})


class RulingsReadTest(unittest.TestCase):
    def test_a_row_reads_as_adopted_only_with_the_adopt_decision(self):
        with tempfile.TemporaryDirectory() as store, mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
            handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text=FINDING, decision="adopt",
                                               owner="the user", ruled_at="2026-11-19 10:00")
            handback_store.record_ruled_impact("s1", "kept impact", "/r", decision=plan_format.KEEP_DECISION,
                                               owner="x", ruled_at="y")
            handback_store.record_ruled_impact("s1", "legacy impact", "/r")

            read = handback_store.rulings("s1", "/r")

        self.assertEqual(read.adopted, (ADOPTED,))
        self.assertEqual(read.impacts, ["kept impact", "legacy impact"])

    def test_an_adopt_row_with_no_owner_ruled_at_or_finding_text_reads_with_the_fallbacks(self):
        with tempfile.TemporaryDirectory() as store, mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
            handback_store.record_ruled_impact("s1", IMPACT, "/r", decision=plan_format.ADOPT_DECISION)

            read = handback_store.rulings("s1", "/r")

        unknown = handback_store.UNKNOWN_RULING_FIELD
        self.assertEqual(read.adopted, (AdoptedRuling(IMPACT, None, unknown, unknown),))

    def test_the_latest_ruling_on_an_impact_wins_in_either_order(self):
        adopt = plan_format.ADOPT_DECISION
        keep = plan_format.KEEP_DECISION
        cases = (("adopt then keep", (adopt, keep), 0, [IMPACT]),
                 ("keep then adopt", (keep, adopt), 1, []))
        for label, decisions, adopted_count, impacts in cases:
            with self.subTest(label), tempfile.TemporaryDirectory() as store, \
                    mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
                for decision in decisions:
                    handback_store.record_ruled_impact("s1", IMPACT, "/r", decision=decision, owner="u", ruled_at="t")

                read = handback_store.rulings("s1", "/r")

                self.assertEqual(len(read.adopted), adopted_count, label)
                self.assertEqual(read.impacts, impacts, label)

    def test_an_applied_ruling_is_left_out_of_adopted_and_adds_no_finding_on_a_later_launch(self):
        other = "b.py:2 [bug] unrelated finding"
        with tempfile.TemporaryDirectory() as store, mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
            handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text=FINDING, decision="adopt",
                                               owner="the user", ruled_at="2026-11-19 10:00")
            first = review_user_ruled.leave_out_ruled_impacts([other], [], handback_store.rulings("s1", "/r"))
            handback_store.record_applied_ruling("s1", ADOPTED, "/r")

            second = review_user_ruled.leave_out_ruled_impacts([other], [], handback_store.rulings("s1", "/r"))

        self.assertEqual(len(first.kept), 2)
        self.assertEqual(second.kept, [other])
        self.assertEqual(second.adopted, {})

    def test_the_finding_an_applied_ruling_came_from_is_dropped_when_passed_again(self):
        # Far from IMPACT in wording, so only the recorded finding text can settle it, not the impact text.
        distant = ("src/purge.py:40 [plan-drift] purge() leaves orphaned rows behind when a parent record is "
                   "removed during a nightly batch, which the plan never mentions. PLAN-IMPACT: AC2 reworded. "
                   "acceptance_criteria: AC2")
        ruling = AdoptedRuling(IMPACT, distant, "the user", "2026-11-19 10:00")
        with tempfile.TemporaryDirectory() as store, mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
            handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text=distant, decision="adopt",
                                               owner="the user", ruled_at="2026-11-19 10:00")
            handback_store.record_applied_ruling("s1", ruling, "/r")

            again = review_user_ruled.leave_out_ruled_impacts([distant], [1], handback_store.rulings("s1", "/r"))

        self.assertEqual(again.kept, [])

    def test_one_ruling_covering_two_findings_keeps_an_adopted_ruling_for_each(self):
        first = "a.py:1 one"
        second = "b.py:2 two"
        with tempfile.TemporaryDirectory() as store, mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
            for finding_text in (first, second):
                handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text=finding_text, decision="adopt",
                                                   owner="the user", ruled_at="2026-11-19 10:00")

            read = handback_store.rulings("s1", "/r")

        self.assertEqual([ruling.finding_text for ruling in read.adopted], [first, second])

    def test_a_keep_ruling_on_two_findings_keeps_both_finding_texts_and_an_older_ruling_is_dropped(self):
        with tempfile.TemporaryDirectory() as store, mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
            handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text="old.py:1 old", decision="keep",
                                               owner="u", ruled_at="2026-11-19 09:00")
            for finding_text in ("a.py:1 one", "b.py:2 two"):
                handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text=finding_text, decision="keep",
                                                   owner="u", ruled_at="2026-11-19 10:00")

            read = handback_store.rulings("s1", "/r")

        self.assertEqual(read.finding_texts, ["a.py:1 one", "b.py:2 two"])

    def test_an_applied_ruling_still_counts_as_a_ruled_impact_so_a_later_fix_run_skips_its_finding(self):
        with tempfile.TemporaryDirectory() as store, mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
            handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text=FINDING, decision="adopt",
                                               owner="the user", ruled_at="2026-11-19 10:00")
            handback_store.record_applied_ruling("s1", ADOPTED, "/r")

            read = handback_store.rulings("s1", "/r")
            left_out = review_user_ruled.leave_out_ruled_impacts([FINDING], [], read)

        self.assertEqual(read.adopted, ())
        self.assertIn(IMPACT, read.impacts)
        self.assertEqual(left_out.kept, [])
        self.assertEqual(left_out.dropped, [FINDING])

    def test_a_later_decision_on_an_applied_change_comes_back(self):
        with tempfile.TemporaryDirectory() as store, mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": store}):
            handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text=FINDING, decision="adopt",
                                               owner="the user", ruled_at="2026-11-19 10:00")
            handback_store.record_applied_ruling("s1", ADOPTED, "/r")
            handback_store.record_ruled_impact("s1", IMPACT, "/r", finding_text=FINDING, decision="adopt",
                                               owner="the user", ruled_at="2026-11-19 12:00")

            read = handback_store.rulings("s1", "/r")

        self.assertEqual(read.adopted, (AdoptedRuling(IMPACT, FINDING, "the user", "2026-11-19 12:00"),))


if __name__ == "__main__":
    unittest.main()
