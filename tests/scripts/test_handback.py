"""Checks for handback.py: the one reader of the review-loop hand-back packet and the per-session store."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = pathlib.Path(os.environ.get("HANDBACK_SCRIPT") or pathlib.Path.home() / ".claude" / "scripts" / "handback.py")
SESSION = "sess-1"

spec = importlib.util.spec_from_file_location("handback_under_test", str(SCRIPT))
handback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handback)

CONVERGED = """status: converged
iter: 1
fixed: [{finding: "orders query lacked a tenant filter", file_line: src/orders.ts:42, blocker: true}]
skipped_fp: []
ask: []
class_closure: enumerated every query
files_touched: [src/orders.ts]
"""

NUMBERED = """status: converged
iter: 1
fixed: []
ask:
1. finding: cap on retries | file_line: src/retry.ts:10 | question: cap at 3? | gate: code-reviewer | class: smell
2) finding: add index | file_line: src/db.ts:5 | question: index tenant_id? | gate: perf-reviewer | class: perf
Closing note from the loop.
"""


class HandbackTestBase(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.tmp = pathlib.Path(directory.name)
        self.store = self.tmp / "store"
        self.previous = os.environ.get("HANDBACK_STORE_DIR")
        os.environ["HANDBACK_STORE_DIR"] = str(self.store)
        self.addCleanup(self.restore_environment)

    def restore_environment(self):
        if self.previous is None:
            os.environ.pop("HANDBACK_STORE_DIR", None)
        else:
            os.environ["HANDBACK_STORE_DIR"] = self.previous

    def run_cli(self, arguments, stdin=""):
        env = {**os.environ, "HANDBACK_STORE_DIR": str(self.store)}
        done = subprocess.run([sys.executable, "-I", str(SCRIPT), *arguments], input=stdin, text=True,
                              capture_output=True, env=env)
        return done.returncode, done.stdout, done.stderr


class ParseTest(HandbackTestBase):
    def test_numbered_asks_split_into_items_and_closing_prose_goes_to_the_trailer(self):
        packet = handback.load(NUMBERED)
        self.assertEqual([item["file_line"] for item in packet["ask"]], ["src/retry.ts:10", "src/db.ts:5"])
        self.assertEqual(packet["trailer"], "Closing note from the loop.")

    def test_indented_sub_bullets_stay_inside_their_parent_fixed_entry(self):
        text = ("status: converged\niter: 1\nfixed:\n- tests added:\n  - retry case\n  - timeout case\n"
                "- renamed the helper\nnit: []\n")
        packet = handback.load(text)
        self.assertEqual(len(packet["fixed"]), 2)
        self.assertIn("timeout case", packet["fixed"][0]["finding"])

    def test_every_marker_of_an_indented_list_is_top_level(self):
        text = ("status: converged\niter: 1\nfixed:\n  - {finding: a, file_line: a.ts:1}\n"
                "  - {finding: b, file_line: b.ts:2}\nnit: []\n")
        self.assertEqual(len(handback.load(text)["fixed"]), 2)

    def test_lead_prose_before_the_first_item_marker_is_a_trailer_not_an_ask(self):
        text = NUMBERED.replace("ask:\n1.", "ask: two questions follow\n1.")
        packet = handback.load(text)
        self.assertEqual(len(packet["ask"]), 2)
        self.assertIn("two questions follow", packet["trailer"])

    def test_empty_list_key_does_not_swallow_the_next_unindented_line(self):
        packet = handback.parse("status: converged\niter: 1\nfixed: []\nask: []\nclass_closure: done\nnit: []\n")
        self.assertEqual(packet["class_closure"], "done")
        self.assertEqual(packet["trailer"], "")

    def test_none_list_followed_by_indented_text_keeps_the_indented_text_in_the_list(self):
        packet = handback.parse("status: converged\niter: 1\nfixed: []\nask: none\n  more words\nnit: []\n")
        self.assertIn("more words", packet["ask"])

    def test_empty_list_key_followed_by_a_dash_item_reads_the_items(self):
        packet = handback.parse("status: converged\niter: 1\nfixed:\n- {finding: x, file_line: a.ts:1}\nnit: []\n")
        self.assertIn("finding: x", packet["fixed"])

    def test_a_field_name_after_a_bare_space_is_part_of_the_value(self):
        pairs = handback.parse_inline_pairs("finding: guard the read then class: fix it. file_line: a.ts:1")
        self.assertEqual(pairs["finding"], "guard the read then class: fix it")
        self.assertEqual(pairs["file_line"], "a.ts:1")

    def test_a_field_name_after_punctuation_and_space_starts_a_field_and_a_question_mark_stays(self):
        pairs = handback.parse_inline_pairs("finding: x. question: cap it? gate: code-reviewer; class: smell | file_line: a.ts:1")
        self.assertEqual(pairs["question"], "cap it?")
        self.assertEqual((pairs["gate"], pairs["class"], pairs["file_line"]), ("code-reviewer", "smell", "a.ts:1"))

    def test_key_with_a_note_in_brackets_is_still_a_key(self):
        packet = handback.parse("status (final): converged\niter: 1\nfixed: []\n")
        self.assertEqual(packet["status"], "converged")

    def test_perf_smell_files_touched_and_principle_are_packet_keys(self):
        packet = handback.parse("status: converged\niter: 1\nfixed: []\nperf:\n- {finding: n+1}\nsmell: []\n"
                                "files_touched: []\nprinciple: batch\n")
        self.assertEqual(packet["principle"], "batch")
        self.assertIn("n+1", packet["perf"])

    def test_flow_list_split_over_lines_parses(self):
        packet = handback.load("status: converged\niter: 1\nfixed: [{finding: a, file_line: a.ts:1},\n {finding: b, file_line: b.ts:2}]\n")
        self.assertEqual([item["finding"] for item in packet["fixed"]], ["a", "b"])

    def test_json_style_list_parses(self):
        packet = handback.load('status: converged\niter: 1\nfixed: [{"finding": "x", "file_line": "a.ts:1"}]\n')
        self.assertEqual(packet["fixed"][0]["finding"], "x")

    def test_multi_line_quoted_item_is_unquoted(self):
        packet = handback.load('status: converged\niter: 1\nfixed:\n  - "first part\n    second part"\n')
        self.assertIn("first part", packet["fixed"][0]["finding"])
        self.assertNotIn('"', packet["fixed"][0]["finding"])

    def test_plain_text_fixed_entry_becomes_a_mapping_with_its_path(self):
        packet = handback.load("status: converged\niter: 1\nfixed:\n  - removed the dead branch | src/a.ts:4 | blocker: no\n")
        self.assertEqual(packet["fixed"][0]["file_line"], "src/a.ts:4")
        self.assertEqual(packet["fixed"][0]["blocker"], "no")

    def test_missing_spec_iter_is_none_and_missing_iter_is_a_problem(self):
        self.assertIsNone(handback.load(CONVERGED)["spec_iter"])
        with self.assertRaises(handback.PacketError) as raised:
            handback.load(CONVERGED.replace("iter: 1\n", ""))
        self.assertIn("iter is missing", raised.exception.problems[0])


class ValidateTest(HandbackTestBase):
    def test_unknown_ask_class_becomes_other_and_the_raw_class_is_kept(self):
        packet = handback.load(NUMBERED.replace("class: smell", "class: ops"))
        self.assertEqual((packet["ask"][0]["class"], packet["ask"][0]["class_raw"]), ("other", "ops"))
        self.assertNotIn("class_raw", packet["ask"][1])

    def test_gate_is_cut_to_its_first_token_and_defaults_when_missing(self):
        packet = handback.load(NUMBERED.replace("gate: code-reviewer", "gate: code-reviewer / robustness"))
        self.assertEqual(packet["ask"][0]["gate"], "code-reviewer")
        packet = handback.load(NUMBERED.replace(" | gate: perf-reviewer", ""))
        self.assertEqual(packet["ask"][1]["gate"], "code-reviewer")

    def test_every_status_word_validates_with_its_required_fields(self):
        cases = {"converged": CONVERGED,
                 "deferred": "status: deferred\niter: 1\nfixed: []\nfindings_remaining:\n- {finding: x, file_line: a.ts:1}\n",
                 "critical-blocker": "status: critical-blocker\niter: 1\nblockers:\n- bad thing\n",
                 "cap-reached": "status: cap-reached\niter: 2\nfindings_remaining:\n- {finding: x, file_line: a.ts:1}\n",
                 "plan-impact": "status: plan-impact\niter: 1\nspec_iter: 0\nplan_impact: assumed a, found b\n"}
        for status, text in cases.items():
            self.assertEqual(handback.load(text)["status"], status)

    def test_each_stop_condition_is_a_problem(self):
        cases = ["status: done\niter: 1\n",
                 "status: converged\niter: x\nfixed: []\n",
                 "status: converged\niter: 1\n",
                 "status: converged\niter: 1\nspec_iter: many\nfixed: []\n",
                 "status: converged\niter: 1\nfixed: [{blocker: true}]\n",
                 "status: converged\niter: 1\nfixed: []\nask:\n- {finding: x, question: y?}\n",
                 "status: plan-impact\niter: 1\nplan_impact:\n",
                 "status: critical-blocker\niter: 1\nblockers: []\n",
                 "status: cap-reached\niter: 2\n",
                 "status: cap-reached\niter: 2\nfindings_remaining: []\n",
                 "status: deferred\niter: 1\nfixed: []\nfindings_remaining: []\n"]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(handback.PacketError):
                handback.load(text)

    def test_cap_reached_with_a_key_present_but_empty_is_a_problem_and_a_missing_key_is_another(self):
        for text in ("status: cap-reached\niter: 2\nfindings_remaining: [] (none open)\n", "status: cap-reached\niter: 2\n"):
            with self.assertRaises(handback.PacketError) as raised:
                handback.load(text)
            self.assertIn("findings_remaining", raised.exception.problems[0])

    def test_pending_report_is_not_a_packet(self):
        with self.assertRaises(handback.PacketError):
            handback.load("status: pending. The verification pass has not reported.\n\nDone so far:\n- fixed\n")


class RenderTest(HandbackTestBase):
    def test_findings_remaining_show_on_converged(self):
        text = CONVERGED.replace("ask: []", 'ask: []\nfindings_remaining: [{disposition: fix, finding: left over, file_line: a.ts:1}]')
        self.assertIn("### Findings remaining", handback.render(handback.load(text), "review"))

    def test_bare_not_applicable_closure_with_empty_fixed_prints_one_line(self):
        packet = handback.load("status: converged\niter: 0\nfixed: []\nclass_closure: n/a\n")
        rendered = handback.render(packet, "review")
        self.assertEqual(rendered.count("Class closure"), 1)
        self.assertNotIn("receipt is missing", rendered)

    def test_missing_closure_with_fixed_entries_says_the_receipt_is_missing(self):
        packet = handback.load(CONVERGED.replace("class_closure: enumerated every query\n", ""))
        self.assertIn("receipt is missing", handback.render(packet, "review"))

    def test_sections_print_before_the_trailer(self):
        packet = handback.load(NUMBERED)
        rendered = handback.render(packet, "fix", [("Aikido replies", ["- a.ts:1: Fixed"])])
        self.assertLess(rendered.index("### Aikido replies"), rendered.index("Closing note"))

    def test_blockers_sort_first_and_are_labelled(self):
        text = CONVERGED.replace("fixed: [", "fixed: [{finding: small, file_line: a.ts:1, blocker: false}, ")
        rendered = handback.render(handback.load(text), "review")
        self.assertLess(rendered.index("[blocker]"), rendered.index("small"))


class StoreTest(HandbackTestBase):
    def test_latest_reports_dispatch_handback_and_pending(self):
        self.assertEqual(handback.latest(SESSION),
                         {"dispatch": None, "handback": None, "unanswered": 0, "pending": False})
        handback.record(SESSION, "dispatch")
        self.assertTrue(handback.latest(SESSION)["pending"])
        handback.record(SESSION, "handback", status="converged", message="m")
        seen = handback.latest(SESSION)
        self.assertEqual((seen["handback"]["status"], seen["pending"]), ("converged", False))
        handback.record(SESSION, "dispatch")
        self.assertTrue(handback.latest(SESSION)["pending"])

    def test_latest_counts_dispatches_since_the_last_hand_back(self):
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "dispatch")
        self.assertEqual(handback.latest(SESSION)["unanswered"], 2)
        handback.record(SESSION, "handback", status="converged", message="m")
        self.assertEqual(handback.latest(SESSION)["unanswered"], 0)
        handback.record(SESSION, "dispatch")
        seen = handback.latest(SESSION)
        self.assertEqual((seen["unanswered"], seen["pending"]), (1, True))

    def test_a_dispatch_another_hook_denied_blocks_nothing_once_a_later_dispatch_hands_back(self):
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "handback", status="converged", message="m")
        seen = handback.latest(SESSION)
        self.assertFalse(seen["pending"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_hand_back_gap_names_why_there_is_no_current_hand_back(self):
        seen = handback.latest(SESSION)
        self.assertEqual(handback.hand_back_gap(seen), handback.NO_DISPATCH)
        handback.record(SESSION, "dispatch")
        seen = handback.latest(SESSION)
        self.assertEqual(handback.hand_back_gap(seen), handback.NO_HANDBACK)
        handback.record(SESSION, "handback", status="converged", message="m")
        seen = handback.latest(SESSION)
        self.assertIsNone(handback.hand_back_gap(seen))
        handback.record(SESSION, "dispatch")
        seen = handback.latest(SESSION)
        self.assertEqual(handback.hand_back_gap(seen), handback.REDISPATCHED)

    def test_a_stored_hand_back_with_no_dispatch_row_has_its_own_reason(self):
        handback.record(SESSION, "handback", status="converged", message="m")
        reason = handback.false_clean_reason(SESSION)
        self.assertIn("no review-loop dispatch on record", reason)

    def test_false_clean_reason_allows_only_a_current_converged_or_deferred_hand_back(self):
        self.assertIn("no review-loop hand-back", handback.false_clean_reason(SESSION))
        self.assertIn("no review-loop hand-back", handback.false_clean_reason(""))
        handback.record(SESSION, "dispatch")
        self.assertIn("no review-loop hand-back", handback.false_clean_reason(SESSION))
        handback.record(SESSION, "handback", status="critical-blocker", message="m")
        self.assertIn("critical-blocker", handback.false_clean_reason(SESSION))
        handback.record(SESSION, "dispatch")
        self.assertIn("dispatched again", handback.false_clean_reason(SESSION))
        handback.record(SESSION, "handback", status="deferred", message="m")
        self.assertIsNone(handback.false_clean_reason(SESSION))
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "handback", status="converged", message="m")
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_sessions_never_see_or_overwrite_each_other(self):
        handback.record("a", "dispatch")
        handback.record("a", "handback", status="converged", message="m")
        handback.record("b", "dispatch")
        self.assertEqual(handback.latest("a")["handback"]["status"], "converged")
        self.assertIsNone(handback.latest("b")["handback"])
        self.assertEqual(len((self.store / "a.jsonl").read_text().splitlines()), 2)

    def test_records_only_append(self):
        handback.record(SESSION, "dispatch")
        first = (self.store / (SESSION + ".jsonl")).read_text()
        handback.record(SESSION, "handback", status="converged", message="m")
        self.assertTrue((self.store / (SESSION + ".jsonl")).read_text().startswith(first))

    def test_session_ids_cannot_escape_the_store(self):
        handback.record("../../evil", "dispatch")
        self.assertEqual([path.name for path in self.store.iterdir()], [".._.._evil.jsonl"])

    def test_empty_session_has_no_rows_and_is_not_an_error(self):
        self.assertEqual(handback.latest("")["handback"], None)
        self.assertEqual(handback.latest(None)["dispatch"], None)

    def test_stale_session_files_are_pruned_on_the_next_record(self):
        handback.record("old", "dispatch")
        old = self.store / "old.jsonl"
        stale = time.time() - 30 * 86400
        os.utime(str(old), (stale, stale))
        handback.record("new", "dispatch")
        self.assertFalse(old.exists())
        self.assertTrue((self.store / "new.jsonl").exists())


class CliTest(HandbackTestBase):
    def test_check_accepts_a_good_packet_and_names_the_status(self):
        code, out, err = self.run_cli(["check"], CONVERGED)
        self.assertEqual(code, 0, err)
        self.assertIn("ok: status=converged", out)

    def test_check_rejects_a_bad_packet_with_the_reason_on_stderr(self):
        code, out, err = self.run_cli(["check"], "status: nope\niter: 1\n")
        self.assertEqual(code, 1)
        self.assertIn("status is 'nope'", err)

    def test_check_rejects_empty_input(self):
        self.assertEqual(self.run_cli(["check"], "")[0], 1)

    def test_no_arguments_prints_usage_and_exits_2(self):
        code, out, err = self.run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("handback.py", err)

    def test_latest_prints_the_session_rows_as_json(self):
        handback.record(SESSION, "dispatch")
        code, out, err = self.run_cli(["latest", SESSION])
        self.assertEqual(json.loads(out)["pending"], True)


class HookTest(HandbackTestBase):
    def event(self, tool, session=SESSION, agent="review-loop", message=CONVERGED, agent_id="a1"):
        if tool == "Agent":
            return {"session_id": session, "tool_name": "Agent", "tool_input": {"subagent_type": agent}}
        return {"session_id": session, "tool_name": "SubagentHandback", "agent_type": agent, "agent_id": agent_id,
                "tool_input": {"message": message}}

    def fire(self, event, *arguments):
        return self.run_cli(["hook", *arguments], json.dumps(event))

    def test_review_loop_dispatch_and_good_hand_back_are_stored_without_output(self):
        self.assertEqual(self.fire(self.event("Agent"))[:2], (0, ""))
        self.assertEqual(self.fire(self.event("SubagentHandback"))[:2], (0, ""))
        seen = handback.latest(SESSION)
        self.assertEqual(seen["handback"]["status"], "converged")
        self.assertFalse(seen["pending"])

    def test_other_agents_are_not_stored(self):
        self.fire(self.event("Agent", agent="coder"))
        self.fire(self.event("SubagentHandback", agent="coder"))
        self.assertFalse(self.store.exists())

    def test_bad_packet_is_denied_once_per_agent_then_stored_as_invalid(self):
        bad = self.event("SubagentHandback", message="status: pending")
        code, out, err = self.fire(bad)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual((code, decision["permissionDecision"]), (0, "deny"))
        self.assertIn("status is", decision["permissionDecisionReason"])
        self.assertIsNone(handback.latest(SESSION)["handback"])
        code, out, err = self.fire(bad)
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(handback.latest(SESSION)["handback"]["status"], "invalid")

    def test_a_different_agent_id_is_denied_afresh(self):
        self.fire(self.event("SubagentHandback", message="junk"))
        code, out, err = self.fire(self.event("SubagentHandback", message="junk", agent_id="a2"))
        self.assertIn("deny", out)

    def test_an_unknown_kind_argument_does_nothing_and_never_acts_as_handback(self):
        code, out, err = self.fire(self.event("SubagentHandback"), "other")
        self.assertEqual((code, out), (0, ""))
        self.assertIn("unknown kind", err)
        self.assertFalse(self.store.exists())

    def test_an_explicit_kind_overrides_the_tool_name(self):
        self.fire(self.event("Agent"), "dispatch")
        self.assertIsNotNone(handback.latest(SESSION)["dispatch"])

    def test_event_without_a_session_id_records_nothing(self):
        event = self.event("Agent")
        del event["session_id"]
        self.assertEqual(self.fire(event)[:2], (0, ""))
        self.assertFalse(self.store.exists())

    def test_unreadable_event_exits_zero_and_blocks_nothing(self):
        code, out, err = self.run_cli(["hook"], "not json")
        self.assertEqual((code, out), (0, ""))


if __name__ == "__main__":
    unittest.main()
