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

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HANDBACK_SCRIPT") or toolkit_paths.REVIEW_DIR / "handback.py")
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
1. finding: cap on retries | file_line: src/retry.ts:10 | question: cap at 3? | \
change: stop the retry loop after 3 tries | gate: code-reviewer | class: smell
2) finding: add index | file_line: src/db.ts:5 | question: index tenant_id? | \
change: add an index on orders.tenant_id | gate: perf-reviewer | class: perf
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

    def dispatch(self, agent_type, calling_agent_id=None, prompt=""):
        """A PreToolUse Agent event: from the main session, or from the subagent `calling_agent_id`."""
        event = {"session_id": SESSION, "tool_name": "Agent",
                 "tool_input": {"subagent_type": agent_type, "prompt": prompt}}
        if calling_agent_id:
            event.update({"agent_type": "review-loop", "agent_id": calling_agent_id})
        self.assertEqual(self.run_cli(["hook", "dispatch"], json.dumps(event))[:2], (0, ""))


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

    def test_fixed_entries_keep_their_whole_text_in_every_real_shape(self):
        cases = [
            ('fixed: [{"finding": "x", "file_line": "a.ts:1", "blocker": false}]', ["x"], "JSON style"),
            ('fixed: [{finding: "guard the read, then class: fix it", file_line: a.ts:1, blocker: false}]',
             ["guard the read, then class: fix it"], "a comma and a key word in the text"),
            ("fixed:\n- {smell: literals extracted to constants, file_line: a.py:397-530, blocker: no}\n"
             "- {blank lines between steps in two helpers, file_line: a.py:346-474, blocker: no}\n"
             "- {summary overwrote the per-project total, serve.go summary, blocker: true}",
             ["blank lines between steps in two helpers", "summary overwrote the per-project total"],
             "keyed by smell, or starting with bare text"),
        ]
        for fixed_field, kept_texts, label in cases:
            packet = handback.load(f"status: converged\niter: 0\n{fixed_field}\nask: []\nnit: []\n")
            fixed_texts = " | ".join(handback.item_text(item, "finding", "item") for item in packet["fixed"])
            for kept in kept_texts:
                self.assertIn(kept, fixed_texts, label)

    def test_extra_whitespace_and_a_code_fence_around_the_packet_still_parse(self):
        padded = "```\n" + "\n".join("   " + line + "   " if line else line for line in CONVERGED.splitlines())
        packet = handback.load(padded + "\n\n\n```\n")
        self.assertEqual("orders query lacked a tenant filter", packet["fixed"][0]["finding"])
        self.assertEqual("src/orders.ts:42", packet["fixed"][0]["file_line"])

    def test_every_marker_of_an_indented_list_is_top_level(self):
        text = ("status: converged\niter: 1\nfixed:\n  - {finding: a, file_line: a.ts:1}\n"
                "  - {finding: b, file_line: b.ts:2}\nnit: []\n")
        self.assertEqual(len(handback.load(text)["fixed"]), 2)

    def test_lead_prose_before_the_first_item_marker_is_a_trailer_not_an_ask(self):
        text = NUMBERED.replace("ask:\n1.", "ask: two questions follow\n1.")
        packet = handback.load(text)
        self.assertEqual(len(packet["ask"]), 2)
        self.assertIn("two questions follow", packet["trailer"])

    def test_bullets_after_a_mapping_ask_stay_inside_that_ask(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- {finding: jobs count changed, file_line: plan.md:12, change: restore -j8}\n"
                "- the plan says -j8\n- the ruling says -j2\n- which one holds?\n"
                "- if the plan: restore -j8\n- if the ruling: keep -j2\nnit: []\n")
        packet = handback.load(text)
        self.assertEqual(len(packet["ask"]), 1)
        self.assertIn("which one holds?", packet["ask"][0]["question"])
        self.assertIn("if the ruling: keep -j2", packet["ask"][0]["question"])

    def test_fact_bullets_citing_a_location_mid_sentence_stay_inside_the_mapping_ask(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- {finding: jobs count changed, file_line: plan.md:12, change: restore -j8}\n"
                "- the plan says -j8 at plan.md:12\n- the ruling says -j2 at docs/ruling.md:4\n"
                "- which one holds?\nnit: []\n")
        packet = handback.load(text)
        self.assertEqual(len(packet["ask"]), 1)
        self.assertIn("which one holds?", packet["ask"][0]["question"])

    def test_a_bullet_naming_its_own_location_after_a_mapping_ask_is_a_separate_ask(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- {finding: jobs count changed, file_line: plan.md:12, change: restore -j8}\n"
                "- should tenant_id get an index? | src/db.ts:5\nnit: []\n")
        packet = handback.load(text)
        self.assertEqual(len(packet["ask"]), 2)
        self.assertEqual(packet["ask"][1]["file_line"], "src/db.ts:5")

    def test_a_fact_bullet_leading_with_a_location_stays_inside_the_mapping_ask(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- {finding: jobs count changed, file_line: plan.md:12, change: restore -j8}\n"
                "- docs/ruling.md:4 says -j2\n- which one holds?\nnit: []\n")
        packet = handback.load(text)
        self.assertEqual(len(packet["ask"]), 1)
        self.assertIn("docs/ruling.md:4 says -j2", packet["ask"][0]["question"])

    def test_a_mapping_bullet_with_no_location_or_finding_adds_its_fields_to_the_lead_ask(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- {finding: jobs count changed, file_line: plan.md:12, change: restore -j8}\n"
                "- {question: which one holds?}\nnit: []\n")
        packet = handback.load(text)
        self.assertEqual(len(packet["ask"]), 1)
        self.assertEqual(packet["ask"][0]["question"], "which one holds?")

    def test_a_continuation_mapping_keeps_the_lead_ask_blocker_and_class(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- {finding: jobs count changed, file_line: plan.md:12, blocker: yes, class: plan-drift, "
                "change: restore -j8}\n"
                "- {question: which one holds?, blocker: no, class: test-gap}\nnit: []\n")
        ask = handback.load(text)["ask"][0]
        self.assertIn(str(ask["blocker"]).lower(), ("true", "yes"))
        self.assertEqual(ask["class"], "plan-drift")
        self.assertEqual(ask["question"], "which one holds?")

    def test_bullets_after_a_text_ask_ending_in_a_colon_stay_inside_that_ask(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- the retry count disagrees with the plan: | src/retry.py:4\n"
                "- the plan says 3\n- the code says 5\n- which one holds?\n"
                "- should tenant_id get an index? | src/db.ts:5\nnit: []\n")
        asks = handback.load(text)["ask"]
        self.assertEqual(len(asks), 2)
        self.assertEqual(asks[0]["file_line"], "src/retry.py:4")
        self.assertIn("- the code says 5", asks[0]["question"])
        self.assertIn("which one holds?", asks[0]["question"])
        self.assertEqual(asks[1]["file_line"], "src/db.ts:5")

    def test_a_mapping_bullet_after_a_text_ask_ending_in_a_colon_adds_its_change_to_that_ask(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- the retry count disagrees with the plan: | src/retry.py:4\n"
                "- which one holds?\n- change: set it to 3\nnit: []\n")
        asks = handback.load(text)["ask"]
        self.assertEqual(len(asks), 1)
        self.assertEqual(asks[0]["file_line"], "src/retry.py:4")
        self.assertEqual(asks[0]["change"], "set it to 3")
        self.assertIn("which one holds?", asks[0]["question"])

    def test_a_text_bullet_after_a_mapping_bullet_stays_a_dash_line_in_a_text_ask(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- the retry count disagrees: | src/retry.py:4\n"
                "- the plan says 3\n- change: set it to 3\n- the code says 5\nnit: []\n")
        asks = handback.load(text)["ask"]
        self.assertEqual(len(asks), 1)
        self.assertIn("- the code says 5", asks[0]["question"])

    def test_a_text_ask_not_ending_in_a_colon_takes_no_bullets(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- which cache holds the session?\n- should tenant_id get an index?\nnit: []\n")
        self.assertEqual(len(handback.load(text)["ask"]), 2)

    def test_a_blocker_text_bullet_after_a_mapping_bullet_marks_the_text_ask_a_blocker(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- the retry count disagrees with the plan: | src/retry.py:4\n"
                "- {change: set it to 3}\n- [blocker] data loss\nnit: []\n")
        asks = handback.load(text)["ask"]
        self.assertEqual(len(asks), 1)
        self.assertTrue(handback.is_blocker(asks[0]))

    def test_a_blocker_text_bullet_marks_a_mapping_lead_with_no_blocker_field_a_blocker(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- {finding: the retry count disagrees with the plan, file_line: src/r.py:4, "
                "question: which one holds?, change: set it to 3}\n- [blocker] data loss\nnit: []\n")
        asks = handback.load(text)["ask"]
        self.assertEqual(len(asks), 1)
        self.assertTrue(handback.is_blocker(asks[0]))

    def test_a_mapping_bullet_with_blocker_yes_marks_the_text_ask_a_blocker(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "- the retry count disagrees with the plan: | src/retry.py:4\n"
                "- {change: set it to 3, blocker: yes}\nnit: []\n")
        asks = handback.load(text)["ask"]
        self.assertEqual(len(asks), 1)
        self.assertTrue(handback.is_blocker(asks[0]))

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
        pairs = handback.parse_inline_pairs(
            "finding: x. question: cap it? gate: code-reviewer; class: smell | file_line: a.ts:1"
        )
        self.assertEqual(pairs["question"], "cap it?")
        self.assertEqual((pairs["gate"], pairs["class"], pairs["file_line"]), ("code-reviewer", "smell", "a.ts:1"))

    def test_key_with_a_note_in_brackets_is_still_a_key(self):
        packet = handback.parse("status (final): converged\niter: 1\nfixed: []\n")
        self.assertEqual(packet["status"], "converged")

    def test_files_touched_is_a_packet_key_and_perf_smell_principle_are_trailer(self):
        packet = handback.parse("status: converged\niter: 1\nfixed: []\nfiles_touched: [a.py]\n\nperf: n+1\n"
                                "smell: []\nprinciple: batch\n")
        self.assertEqual(packet["files_touched"], "[a.py]")
        self.assertFalse({"perf", "smell", "principle"} & set(packet))
        self.assertIn("principle: batch", packet["trailer"])

    def test_flow_list_split_over_lines_parses(self):
        packet = handback.load(
            "status: converged\niter: 1\nfixed: [{finding: a, file_line: a.ts:1},\n {finding: b, file_line: b.ts:2}]\n"
        )
        self.assertEqual([item["finding"] for item in packet["fixed"]], ["a", "b"])

    def test_json_style_list_parses(self):
        packet = handback.load('status: converged\niter: 1\nfixed: [{"finding": "x", "file_line": "a.ts:1"}]\n')
        self.assertEqual(packet["fixed"][0]["finding"], "x")

    def test_multi_line_quoted_item_is_unquoted(self):
        packet = handback.load('status: converged\niter: 1\nfixed:\n  - "first part\n    second part"\n')
        self.assertIn("first part", packet["fixed"][0]["finding"])
        self.assertNotIn('"', packet["fixed"][0]["finding"])

    def test_one_multi_line_ask_with_numbered_lines_inside_it_is_one_ask(self):
        text = ('status: converged\niter: 1\nfixed: []\nask:\n'
                '- {finding: "f", file_line: "a.ts:1", question: "which one?", change: "do it"}\n'
                '1. the first option reads the cache\n'
                '2. the second option reads the table\n')
        packet = handback.load(text)
        self.assertEqual(len(packet["ask"]), 1)
        self.assertIn("which one?", packet["ask"][0]["question"])
        self.assertIn("the second option reads the table", packet["ask"][0]["question"])
        self.assertEqual(packet["ask"][0]["change"], "do it")

    def test_bullet_lines_inside_a_numbered_ask_stay_in_that_ask(self):
        numbered_first = ('status: converged\niter: 1\nfixed: []\nask:\n'
                          '1. which cache? change: pick one\n'
                          '- the first option reads the cache\n'
                          '2. which table? change: pick one\n')
        packet = handback.load(numbered_first)
        self.assertEqual(len(packet["ask"]), 2)
        self.assertIn("the first option reads the cache", packet["ask"][0]["question"])

    def test_numbered_lines_after_a_blocker_mapping_stay_in_its_finding_text(self):
        packet = handback.load(
            'status: critical-blocker\niter: 1\nblockers:\n'
            '- {finding: "bad", file_line: "a.ts:1"}\n'
            '1. first detail\n2. second detail\n'
        )
        self.assertIn("second detail", packet["blockers"][0]["finding"])

    def test_plain_text_fixed_entry_becomes_a_mapping_with_its_path(self):
        packet = handback.load(
            "status: converged\niter: 1\nfixed:\n  - removed the dead branch | src/a.ts:4 | blocker: no\n"
        )
        self.assertEqual(packet["fixed"][0]["file_line"], "src/a.ts:4")
        self.assertEqual(packet["fixed"][0]["blocker"], "no")

    def test_an_ask_with_an_empty_question_asks_its_change(self):
        packet = handback.load(
            'status: converged\niter: 1\nfixed: []\nask: [{"question": "", "file_line": "unlocated", '
            '"change": "read the limit from settings", "gate": "code-reviewer", "class": "bug"}]\n'
        )

        self.assertEqual(packet["ask"][0]["question"], "read the limit from settings")

    def test_an_ask_with_no_question_finding_or_change_is_dropped_with_a_warning_and_the_rest_survive(self):
        good_ask = ('{"question": "cap at 3?", "file_line": "src/a.ts:4", "change": "cap retries at 3", '
                    '"gate": "code-reviewer", "class": "bug"}')
        bad_asks = (('{"question": "", "file_line": "unlocated", "gate": "code-reviewer", "class": "bug"}',
                     "file_line unlocated, gate code-reviewer"),
                    ("null", "'None'"), ('["q"]', '''"['q']"'''))
        for bad_ask, named in bad_asks:
            with self.subTest(bad_ask=bad_ask):
                packet = handback.load(f"status: converged\niter: 1\nfixed: []\nask: [{bad_ask}, {good_ask}]\n")

                self.assertEqual([item["question"] for item in packet["ask"]], ["cap at 3?"])
                self.assertEqual(len(packet["dropped_asks"]), 1)
                self.assertIn(f"ask entry has no question, finding or change, so it was dropped: {named}",
                              packet["dropped_asks"][0])

    def test_check_prints_each_dropped_ask_warning_after_the_ok_line(self):
        code, out, _err = self.run_cli(
            ["check"], 'status: converged\niter: 1\nfixed: []\nask: [{"question": "", "file_line": "a.ts:1", '
            '"gate": "code-reviewer", "class": "bug"}]\n')

        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[1:],
                         ["DROPPED ASKS (tell the user; the review went on without them):",
                          "- ask entry has no question, finding or change, so it was dropped: "
                          "file_line a.ts:1, gate code-reviewer"])

    def test_an_entry_that_is_neither_text_nor_a_mapping_is_a_problem(self):
        for text, problem in (("status: converged\niter: 1\nfixed: [null]\n", "fixed entry has no finding: 'None'"),
                              ("status: converged\niter: 1\nfixed: [5]\n", "fixed entry has no finding: '5'")):
            with self.subTest(text=text), self.assertRaises(handback.PacketError) as raised:
                handback.load(text)
            self.assertTrue([found for found in raised.exception.problems if found.startswith(problem)],
                            raised.exception.problems)

    def test_missing_spec_iter_is_none_and_missing_iter_is_a_problem(self):
        self.assertIsNone(handback.load(CONVERGED)["spec_iter"])
        with self.assertRaises(handback.PacketError) as raised:
            handback.load(CONVERGED.replace("iter: 1\n", ""))
        self.assertIn("iter is missing", raised.exception.problems[0])


class ValidateTest(HandbackTestBase):
    def test_an_ask_carries_its_one_proposed_change_as_its_own_field(self):
        packet = handback.load(NUMBERED)

        self.assertEqual("cap at 3?", packet["ask"][0]["question"])
        self.assertEqual("stop the retry loop after 3 tries", packet["ask"][0]["change"])

    def test_an_either_or_ask_with_no_proposed_change_is_refused(self):
        either_or = NUMBERED.replace(" | change: stop the retry loop after 3 tries", "").replace(
            "question: cap at 3?", "question: cap at 3, or keep retrying with backoff?")

        with self.assertRaises(handback.PacketError) as raised:
            handback.load(either_or)

        self.assertIn("ask entry has no change", raised.exception.problems[0])

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
        cases = {
            "converged": CONVERGED,
            "deferred": "status: deferred\niter: 1\nfixed: []\nfindings_remaining:\n- {finding: x, file_line: "
                        "a.ts:1}\n",
            "critical-blocker": "status: critical-blocker\niter: 1\nblockers:\n- bad thing\n",
            "setup-fault": "status: setup-fault\niter: 1\nblockers:\n- full check could not run\n",
            "cap-reached": "status: cap-reached\niter: 2\nfindings_remaining:\n- {finding: x, file_line: a.ts:1}\n",
            "plan-impact": "status: plan-impact\niter: 1\nspec_iter: 0\nplan_impact: assumed a, found b\n",
        }
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
                 "status: setup-fault\niter: 1\nblockers: []\n",
                 "status: cap-reached\niter: 2\n",
                 "status: cap-reached\niter: 2\nfindings_remaining: []\n",
                 "status: deferred\niter: 1\nfixed: []\nfindings_remaining: []\n"]
        for text in cases:
            with self.subTest(text=text), self.assertRaises(handback.PacketError):
                handback.load(text)

    def test_cap_reached_with_a_key_present_but_empty_is_a_problem_and_a_missing_key_is_another(self):
        for text, absence in (
            ("status: cap-reached\niter: 2\nfindings_remaining: [] (none open)\n", "empty"),
            ("status: cap-reached\niter: 2\n", "missing"),
        ):
            with self.subTest(text=text), self.assertRaises(handback.PacketError) as raised:
                handback.load(text)
            self.assertIn(f"status is cap-reached but findings_remaining is {absence}", raised.exception.problems)

    def test_pending_report_is_not_a_packet(self):
        with self.assertRaises(handback.PacketError):
            handback.load("status: pending. The verification pass has not reported.\n\nDone so far:\n- fixed\n")


class AskFindingIdTest(unittest.TestCase):
    def test_a_16_char_lowercase_hex_id_is_returned(self):
        self.assertEqual(handback.ask_finding_id({"finding_id": "a1b2c3d4e5f60001"}), "a1b2c3d4e5f60001")

    def test_surrounding_whitespace_is_stripped_from_a_valid_id(self):
        self.assertEqual(handback.ask_finding_id({"finding_id": "  a1b2c3d4e5f60001\t"}), "a1b2c3d4e5f60001")

    def test_a_placeholder_or_damaged_id_is_none(self):
        not_ids = ["none logged", "none", "-", "n/a", "", "   ", "a1b2c3d4e5f6000", "a1b2c3d4e5f600011",
                  "A1B2C3D4E5F60001", "a1b2c3d4e5f6000g", "a1b2c3d4 e5f60001", "a1b2c3d4e5f60001\nx"]
        for not_id in not_ids:
            with self.subTest(finding_id=not_id):
                self.assertIsNone(handback.ask_finding_id({"finding_id": not_id}))

    def test_a_missing_or_non_string_id_is_none(self):
        for entry in [{}, {"finding_id": None}, {"finding_id": 1234567890123456}, {"finding_id": ["a1b2c3d4e5f60001"]},
                      handback.entry_from_text("a1b2c3d4e5f60001 in plain text", "question")]:
            with self.subTest(entry=entry):
                self.assertIsNone(handback.ask_finding_id(entry))


class AskParsedFindingIdTest(unittest.TestCase):
    def test_a_finding_id_the_loop_wrote_survives_parsing_in_block_and_flow_style(self):
        text = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "  - finding: x\n    finding_id: a1b2c3d4e5f60001\n    file_line: a.ts:1\n    question: q?\n"
                "    change: c\n"
                "  - {finding: y, finding_id: a1b2c3d4e5f60002, file_line: b.ts:2, question: q?, change: c}\n")
        packet = handback.load(text)
        self.assertEqual([handback.ask_finding_id(item) for item in packet["ask"]],
                         ["a1b2c3d4e5f60001", "a1b2c3d4e5f60002"])


class ClaimLoggedAskIdTest(unittest.TestCase):
    def logged_rows(self):
        return [{"file": "src/retry.ts", "line": 10, "finding_id": "a1b2c3d4e5f60001"},
                {"file": "src/db.ts", "line": 5, "finding_id": "a1b2c3d4e5f60002"}]

    def test_an_ask_takes_the_id_of_the_logged_row_at_its_file_and_line(self):
        logged_rows = self.logged_rows()
        ask = {"file_line": "src/db.ts:5"}
        self.assertEqual(handback.claim_logged_ask_id(ask, logged_rows), "a1b2c3d4e5f60002")

    def test_a_logged_row_is_claimed_once(self):
        logged_rows = self.logged_rows()
        ask = {"file_line": "src/db.ts:5"}
        handback.claim_logged_ask_id(ask, logged_rows)
        self.assertIsNone(handback.claim_logged_ask_id(ask, logged_rows))
        self.assertEqual(len(logged_rows), 1)

    def test_a_row_logged_with_a_shorter_path_still_matches_the_ask_path(self):
        logged_rows = [{"file": "spec.md", "line": 314, "finding_id": "a1b2c3d4e5f60003"}]
        ask = {"file_line": "docs/guide/spec.md:314"}
        self.assertEqual(handback.claim_logged_ask_id(ask, logged_rows), "a1b2c3d4e5f60003")

    def test_another_line_or_file_or_a_partial_name_is_no_match(self):
        for file_line in ["src/db.ts:6", "src/other.ts:5", "mydb.ts:5", "", "-"]:
            with self.subTest(file_line=file_line):
                self.assertIsNone(handback.claim_logged_ask_id({"file_line": file_line}, self.logged_rows()))


class AskOutcomeFindingIdTest(unittest.TestCase):
    def test_a_valid_id_is_kept_with_no_note(self):
        self.assertEqual(handback.ask_outcome_finding_id({"finding_id": " a1b2c3d4e5f60001 "}),
                         ("a1b2c3d4e5f60001", None))

    def test_a_placeholder_id_gets_a_new_id_in_the_writer_shape_and_a_note_naming_both(self):
        new_finding_id, note = handback.ask_outcome_finding_id({"finding_id": "not logged (no id was printed)"})

        self.assertEqual(handback.ask_finding_id({"finding_id": new_finding_id}), new_finding_id)
        self.assertIn("ignored 'not logged (no id was printed)'", note)
        self.assertIn(f"logged under new finding_id {new_finding_id}", note)

    def test_a_missing_id_gets_a_fresh_id_on_every_call(self):
        first_new_id, first_note = handback.ask_outcome_finding_id({})
        second_new_id, _ = handback.ask_outcome_finding_id({})

        self.assertNotEqual(first_new_id, second_new_id)
        self.assertIn("(no finding_id)", first_note)


class RenderTest(HandbackTestBase):
    def test_findings_remaining_show_on_converged(self):
        text = CONVERGED.replace(
            "ask: []", "ask: []\nfindings_remaining: [{disposition: fix, finding: left over, file_line: a.ts:1}]"
        )
        self.assertIn("### Findings remaining", handback.render(handback.load(text), "review"))

    def test_bare_not_applicable_closure_with_empty_fixed_prints_one_line(self):
        packet = handback.load("status: converged\niter: 0\nfixed: []\nclass_closure: n/a\n")
        rendered = handback.render(packet, "review")
        self.assertEqual(rendered.count("Class closure"), 1)
        self.assertNotIn("receipt is missing", rendered)

    def test_missing_closure_with_fixed_entries_says_the_receipt_is_missing(self):
        packet = handback.load(CONVERGED.replace("class_closure: enumerated every query\n", ""))
        self.assertIn("receipt is missing", handback.render(packet, "review"))

    def test_a_full_check_that_did_not_run_or_failed_before_the_diff_says_so_and_a_passed_one_prints_nothing(self):
        for full_check in ("not run (CI)", "not run (timeout)", "not run (environment gap: No module named 'ruff')",
                           "not run (check-command error: fatal: ambiguous argument 'web/schema.json')",
                           "pre-existing failure (the check fails the same way without this diff, so it did not "
                           "verify this diff)"):
            with self.subTest(full_check=full_check):
                packet = handback.load(CONVERGED + f"full_check: {full_check}\n")

                self.assertIn(f"Full check: {full_check}", handback.render(packet, "review"))
        passed = handback.load(CONVERGED + "full_check: passed\n")
        self.assertNotIn("Full check", handback.render(passed, "review"))

    def test_the_unverified_full_check_and_its_new_fields_parse_and_the_created_files_render(self):
        packet = handback.load(
            CONVERGED + "full_check: unverified (exit 0, no runner summary)\n"
            "full_check_command: make test\nfull_check_summary: not found\n"
            'check_changed: ["gen.ts"]\ncheck_created: ["dist/out.js"]\n')

        self.assertEqual("unverified (exit 0, no runner summary)", packet["full_check"])
        self.assertEqual(("make test", "not found"), (packet["full_check_command"], packet["full_check_summary"]))
        self.assertEqual((["gen.ts"], ["dist/out.js"]), (packet["check_changed"], packet["check_created"]))
        rendered = handback.render(packet, "review")
        self.assertIn("Full check: unverified (exit 0, no runner summary)", rendered)
        self.assertIn("Changed by the full check, not by the coder (restore with `git checkout --` or keep): gen.ts",
                      rendered)
        self.assertIn("Created by the full check, not by the coder (delete or keep): dist/out.js", rendered)

    def test_files_the_check_rewrote_after_the_coder_edited_them_parse_and_render_a_review_warning(self):
        packet = handback.load(CONVERGED + 'check_rewrote_edited: ["edited.ts"]\n')

        self.assertEqual(["edited.ts"], packet["check_rewrote_edited"])
        rendered = handback.render(packet, "review")
        self.assertIn("Hold coder edits and a full check rewrite, so review them (do not restore): edited.ts", rendered)

    def test_sections_print_before_the_trailer(self):
        packet = handback.load(NUMBERED)
        rendered = handback.render(packet, "fix", [("Aikido replies", ["- a.ts:1: Fixed"])])
        self.assertLess(rendered.index("### Aikido replies"), rendered.index("Closing note"))

    def test_fixed_findings_show_as_a_count_and_never_as_a_list(self):
        text = CONVERGED.replace("fixed: [", "fixed: [{finding: small, file_line: a.ts:1, blocker: false}, ")
        rendered = handback.render(handback.load(text), "review")
        self.assertIn("Fixed 2, nits 0, skipped 0", rendered)
        self.assertNotIn("small", rendered)
        self.assertNotIn("orders query lacked", rendered)

    def test_a_blocked_agent_and_the_step_it_skipped_print_under_their_own_heading(self):
        blocked_line = "test-reviewer: Step 1 test map skipped (credential hook denied a bulk cp)"
        packet = handback.load(CONVERGED + f"blocked_agents:\n- {blocked_line}\n")

        rendered = handback.render(packet, "review")

        self.assertIn(f"### Blocked agents (not reviewed)\n- {blocked_line}", rendered)
        self.assertNotIn("Blocked agents", handback.render(handback.load(CONVERGED), "review"))


class StoreTest(HandbackTestBase):
    def test_a_dispatch_row_names_the_repo_its_prompt_or_cwd_holds(self):
        with tempfile.TemporaryDirectory() as folder:
            named, cwd_repo, outside = (os.path.join(folder, name) for name in ("named", "cwd", "outside"))
            for repo in (named, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            os.mkdir(outside)
            self.assertEqual(handback.reviewed_repo("mode: review-first\nrepo: ../named\n", cwd_repo),
                             os.path.realpath(named))
            self.assertEqual(handback.reviewed_repo("mode: review-first\n", cwd_repo), os.path.realpath(cwd_repo))
            self.assertIsNone(handback.reviewed_repo("mode: review-first\n", outside))
            handoff_prompt = f"mode: review-first\nUncommitted changes in {named}/src/a.py (branch b)\n"
            self.assertEqual(handback.reviewed_repo(handoff_prompt, cwd_repo), os.path.realpath(named))

    def test_the_dispatch_hook_stores_the_repo_a_review_loop_dispatch_reviews(self):
        with tempfile.TemporaryDirectory() as folder:
            named, cwd_repo = (os.path.join(folder, name) for name in ("named", "cwd"))
            for repo in (named, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            cases = (("repo: ../named\n", named), ("mode: review-first\n", cwd_repo))
            for prompt, expected_repo in cases:
                with self.subTest(prompt=prompt):
                    event = {"session_id": SESSION, "cwd": cwd_repo,
                             "tool_input": {"subagent_type": "review-loop", "prompt": prompt}}
                    code, _, _ = self.run_cli(["hook", "dispatch"], json.dumps(event))
                    self.assertEqual(code, 0)
                    self.assertEqual(handback.latest(SESSION)["dispatch"]["repo"], os.path.realpath(expected_repo))

    def test_latest_reports_dispatch_handback_and_pending(self):
        self.assertEqual(handback.latest(SESSION),
                         {"dispatch": None, "handback": None, "stop": None, "unanswered": 0, "pending": False})
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

    def test_a_stop_with_an_open_background_agent_is_a_wait_until_a_later_stop_or_a_hand_back(self):
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "stop", agent_id="a1", open_dispatches=1)
        self.assertEqual(handback.hand_back_gap(handback.latest(SESSION)), handback.LOOP_WAITING)
        handback.record(SESSION, "stop", agent_id="a1", open_dispatches=0)
        self.assertEqual(handback.hand_back_gap(handback.latest(SESSION)), handback.NO_HANDBACK)
        handback.record(SESSION, "stop", agent_id="a1", open_dispatches=2)
        handback.record(SESSION, "handback", status="converged", message="m")
        self.assertIsNone(handback.hand_back_gap(handback.latest(SESSION)))

    def test_a_stop_the_gate_blocked_is_not_the_standing_stop(self):
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "stop", agent_id="a1", open_dispatches=0, ask_rows=[{"file": "a", "line": 1}])
        handback.record(SESSION, "stop", agent_id="a1", open_dispatches=0, ask_rows=[], blocked=True)
        self.assertEqual(handback.latest(SESSION)["stop"]["ask_rows"], [{"file": "a", "line": 1}])

    def test_the_settled_stop_is_the_awaited_agents_unblocked_stop_at_or_after_the_hand_back(self):
        before = handback.record(SESSION, "stop", agent_id="a1", open_dispatches=0)["ts"]
        handback.record(SESSION, "stop", agent_id="a2", open_dispatches=0)
        handback.record(SESSION, "stop", agent_id="a1", open_dispatches=0, blocked=True)
        self.assertIsNone(handback.settled_stop_row(SESSION, "a1", before + 0.0001))
        settled = handback.record(SESSION, "stop", agent_id="a1", open_dispatches=0, ask_rows=[])
        self.assertEqual(handback.settled_stop_row(SESSION, "a1", before + 0.0001), settled)

    def test_a_wait_after_a_redispatch_is_not_redispatched_and_a_new_dispatch_clears_an_old_stop(self):
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "handback", status="converged", message="m")
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "stop", agent_id="a2", open_dispatches=1)
        self.assertEqual(handback.hand_back_gap(handback.latest(SESSION)), handback.LOOP_WAITING)
        handback.record(SESSION, "dispatch")
        self.assertEqual(handback.hand_back_gap(handback.latest(SESSION)), handback.REDISPATCHED)

    def test_false_clean_reason_refuses_clean_while_the_loop_waits(self):
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "stop", agent_id="a1", open_dispatches=1)
        self.assertIn("waiting on a background agent or shell", handback.false_clean_reason(SESSION))
        handback.record(SESSION, "handback", status="converged", message="m")
        handback.record(SESSION, "dispatch")
        handback.record(SESSION, "stop", agent_id="a2", open_dispatches=1)
        self.assertIn("waiting on a background agent or shell", handback.false_clean_reason(SESSION))

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
        code, _out, err = self.run_cli(["check"], "status: nope\niter: 1\n")
        self.assertEqual(code, 1)
        self.assertIn("status is 'nope'", err)

    def test_check_rejects_empty_input(self):
        self.assertEqual(self.run_cli(["check"], "")[0], 1)

    def test_no_arguments_prints_usage_and_exits_2(self):
        code, _out, err = self.run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("handback.py", err)


class HookTest(HandbackTestBase):
    def event(self, tool, session=SESSION, agent="review-loop", message=CONVERGED, agent_id="a1"):
        if tool == "Agent":
            return {"session_id": session, "tool_name": "Agent", "tool_input": {"subagent_type": agent}}
        return {"session_id": session, "tool_name": "SubagentHandback", "agent_type": agent, "agent_id": agent_id,
                "tool_input": {"message": message}}

    def fire(self, event, *arguments):
        kind = {"Agent": "dispatch", "SubagentHandback": "handback"}[event["tool_name"]]
        return self.run_cli(["hook", *(arguments or [kind])], json.dumps(event))

    def test_review_loop_dispatch_and_good_hand_back_are_stored_without_output(self):
        self.assertEqual(self.fire(self.event("Agent"))[:2], (0, ""))
        reviewer = {"session_id": SESSION, "tool_name": "Agent", "agent_type": "review-loop", "agent_id": "a1",
                    "tool_input": {"subagent_type": "code-reviewer"}}
        self.assertEqual(self.fire(reviewer)[:2], (0, ""))
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
        code, out, _ = self.fire(bad)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual((code, decision["permissionDecision"]), (0, "deny"))
        self.assertIn("status is", decision["permissionDecisionReason"])
        self.assertIsNone(handback.latest(SESSION)["handback"])
        code, out, _err = self.fire(bad)
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(handback.latest(SESSION)["handback"]["status"], "invalid")

    def test_a_different_agent_id_is_denied_afresh(self):
        self.fire(self.event("SubagentHandback", message="junk"))
        _code, out, _err = self.fire(self.event("SubagentHandback", message="junk", agent_id="a2"))
        self.assertIn("deny", out)

    def test_an_unknown_kind_argument_does_nothing_and_never_acts_as_handback(self):
        code, out, err = self.fire(self.event("SubagentHandback"), "other")
        self.assertEqual((code, out), (0, ""))
        self.assertIn("unknown kind", err)
        self.assertFalse(self.store.exists())

    def test_no_kind_argument_does_nothing(self):
        code, out, err = self.run_cli(["hook"], json.dumps(self.event("Agent")))
        self.assertEqual((code, out), (0, ""))
        self.assertIn("unknown kind", err)
        self.assertFalse(self.store.exists())

    def test_event_without_a_session_id_records_nothing(self):
        event = self.event("Agent")
        del event["session_id"]
        self.assertEqual(self.fire(event)[:2], (0, ""))
        self.assertFalse(self.store.exists())

    def test_unreadable_event_exits_zero_and_blocks_nothing(self):
        code, out, err = self.run_cli(["hook", "handback"], "not json")
        self.assertEqual((code, out), (0, ""))
        self.assertIn("handback hook:", err)
        self.assertNotIn("unknown kind", err)
        self.assertFalse(self.store.exists())


class ReviewerRequiredTest(HandbackTestBase):
    def hand_back(self, agent_id="a1", message=CONVERGED):
        event = {"session_id": SESSION, "tool_name": "SubagentHandback", "agent_type": "review-loop",
                 "agent_id": agent_id, "tool_input": {"message": message}}
        return self.run_cli(["hook", "handback"], json.dumps(event))[:2]

    def assert_denied(self, result):
        code, out = result
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_clean_hand_back_with_no_reviewer_is_denied_once_then_stored_flagged_and_refused(self):
        self.dispatch("review-loop")
        self.dispatch("coder", "a1")
        self.assert_denied(self.hand_back())
        self.assertIsNone(handback.latest(SESSION)["handback"])
        self.assertEqual(self.hand_back(), (0, ""))
        self.assertIn("no reviewer", handback.false_clean_reason(SESSION))

    def test_reviewer_dispatched_after_the_coder_passes(self):
        self.dispatch("review-loop")
        self.dispatch("coder", "a1")
        self.dispatch("code-reviewer", "a1")
        self.assertEqual(self.hand_back(), (0, ""))
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_reviewer_with_no_coder_step_passes(self):
        self.dispatch("review-loop")
        self.dispatch("perf-reviewer-deep", "a1")
        self.assertEqual(self.hand_back(), (0, ""))
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_coder_dispatched_after_the_last_reviewer_passes_flagged_as_an_unreviewed_fix(self):
        self.dispatch("review-loop")
        self.dispatch("code-reviewer", "a1")
        self.dispatch("backend-coder-deep", "a1")
        self.assertEqual(self.hand_back(), (0, ""))
        self.assertTrue(handback.latest(SESSION)["handback"]["unreviewed_fix"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_no_review_mode_dispatch_passes_with_no_reviewer(self):
        self.dispatch("review-loop", prompt="scope: branch\nno-review\n")
        self.dispatch("coder", "a1")
        self.assertEqual(self.hand_back(), (0, ""))
        self.assertFalse(handback.latest(SESSION)["handback"]["unreviewed_fix"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_resolved_plan_impact_is_found_after_a_bullet_or_quote_marker(self):
        for line in ("plan_impact: RESOLVED - adopt.", "- plan_impact: RESOLVED - adopt.",
                     "> * plan_impact: RESOLVED - adopt."):
            prompt = f"scope: branch\n{line}\n"
            self.assertIsNotNone(handback.RESOLVED_PLAN_IMPACT.search(prompt), line)
        self.assertIsNone(handback.RESOLVED_PLAN_IMPACT.search("see plan_impact: RESOLVED"))

    def test_a_normal_loop_is_denied_after_a_later_no_review_loop_claimed_the_exemption(self):
        self.dispatch("review-loop")
        self.dispatch("review-loop", prompt="no-review")
        self.dispatch("coder", "a1")
        self.dispatch("coder", "a2")
        self.assertEqual(self.hand_back("a2"), (0, ""))
        self.assert_denied(self.hand_back("a1"))

    def test_a_no_review_loop_passes_though_a_normal_loop_was_dispatched_after_it(self):
        self.dispatch("review-loop", prompt="no-review")
        self.dispatch("review-loop")
        self.dispatch("coder", "a1")
        self.assertEqual(self.hand_back("a1"), (0, ""))
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_each_no_review_dispatch_exempts_one_hand_back(self):
        self.dispatch("review-loop", prompt="no-review")
        self.dispatch("review-loop", prompt="no-review")
        self.assertEqual(self.hand_back("a1"), (0, ""))
        self.assertEqual(self.hand_back("a2"), (0, ""))
        self.assert_denied(self.hand_back("a3"))

    def test_reviewer_dispatched_by_another_agent_id_does_not_count(self):
        self.dispatch("review-loop")
        self.dispatch("coder", "a1")
        self.dispatch("code-reviewer", "a2")
        self.assert_denied(self.hand_back())

    def two_rounds_ending_on_the_cap_exit_coder(self):
        self.dispatch("review-loop")
        self.dispatch("code-reviewer", "a1")
        self.dispatch("coder", "a1")
        self.dispatch("code-reviewer", "a1")
        self.dispatch("coder", "a1")

    def test_cap_exit_coder_passes_and_the_gate_accepts_it_when_converged(self):
        self.two_rounds_ending_on_the_cap_exit_coder()
        self.assertEqual(self.hand_back(message=CONVERGED.replace("iter: 1", "iter: 2")), (0, ""))
        self.assertTrue(handback.latest(SESSION)["handback"]["unreviewed_fix"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_cap_exit_coder_passes_and_the_gate_accepts_it_when_deferred(self):
        self.two_rounds_ending_on_the_cap_exit_coder()
        message = ("status: deferred\niter: 2\nfixed: []\n"
                   "findings_remaining:\n- {finding: x, file_line: a.ts:1}\n")
        self.assertEqual(self.hand_back(message=message), (0, ""))
        self.assertTrue(handback.latest(SESSION)["handback"]["unreviewed_fix"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_unreviewed_streak_counts_the_latest_flagged_hand_backs_and_a_reviewed_one_ends_it(self):
        self.dispatch("review-loop")
        self.dispatch("coder", "a1")
        self.hand_back("a1")
        self.hand_back("a1")
        self.assertEqual(handback.unreviewed_streak(SESSION), 1)

        self.dispatch("review-loop")
        self.dispatch("coder", "a2")
        self.hand_back("a2")
        self.hand_back("a2")
        self.assertEqual(handback.unreviewed_streak(SESSION), 2)

        self.dispatch("review-loop")
        self.dispatch("code-reviewer", "a3")
        self.hand_back("a3")
        self.assertEqual(handback.unreviewed_streak(SESSION), 0)

    def test_other_agent_types_are_not_steps(self):
        self.dispatch("review-loop")
        self.dispatch("Explore", "a1")
        self.assert_denied(self.hand_back())


def transcript_line(block, record_type="assistant"):
    return {"type": record_type, "message": {"role": record_type, "content": [block]}}


def coder_step(tool_use_id):
    return transcript_line({"type": "tool_use", "id": tool_use_id, "name": "Agent",
                            "input": {"subagent_type": "coder", "prompt": "go"}})


def full_check_run(tool_use_id):
    return transcript_line({"type": "tool_use", "id": tool_use_id, "name": "Bash",
                            "input": {"command": "npm test > /tmp/review-gate.log 2>&1"}})


def background_reviewer_launch(tool_use_id, agent_id):
    """A code-reviewer dispatch and the result that says it runs in the background."""
    launch = transcript_line({"type": "tool_use", "id": tool_use_id, "name": "Agent",
                              "input": {"subagent_type": "code-reviewer", "prompt": "review"}})
    launched = transcript_line({"type": "tool_result", "tool_use_id": tool_use_id,
                                "content": [{"type": "text", "text": f"Async agent launched\nagentId: {agent_id}"}]},
                               "user")
    return [launch, launched]


def task_notification(tool_use_id):
    prompt = (f"<task-notification>\n<task-id>t1</task-id>\n<tool-use-id>{tool_use_id}</tool-use-id>\n"
              "</task-notification>")
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": prompt}}


class OneCheckedHandBackTest(HandbackTestBase):
    def setUp(self):
        super().setUp()
        self.transcript = self.tmp / "loop.jsonl"
        for agent_type in ("review-loop", "coder", "code-reviewer"):
            self.dispatch(agent_type, None if agent_type == "review-loop" else "a1")

    def send_hand_back(self, agent_id="a1", message=CONVERGED, cwd=None):
        event = {"session_id": SESSION, "tool_name": "SubagentHandback", "agent_type": "review-loop",
                 "agent_id": agent_id, "agent_transcript_path": str(self.transcript), "cwd": cwd or str(self.tmp),
                 "tool_input": {"message": message}}
        return self.run_cli(["hook", "handback"], json.dumps(event))

    def hand_back(self, steps, agent_id="a1", message=CONVERGED, cwd=None):
        self.transcript.write_text("".join(json.dumps(step) + "\n" for step in steps), encoding="utf-8")
        _code, out, _err = self.send_hand_back(agent_id, message, cwd)
        return out

    def handback_rows(self):
        lines = (self.store / f"{SESSION}.jsonl").read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in lines]
        return [row for row in rows if row["kind"] == "handback"]

    def test_a_clean_hand_back_with_a_code_change_after_the_last_full_check_is_denied(self):
        out = self.hand_back([full_check_run("t1"), coder_step("t2")])
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Step 6 execution gate", decision["permissionDecisionReason"])
        self.assertEqual(self.handback_rows(), [])

    def test_a_cap_reached_hand_back_with_a_code_change_after_the_last_full_check_is_denied(self):
        message = ("status: cap-reached\niter: 2\n"
                   "findings_remaining:\n- {finding: x, file_line: a.ts:1}\n")
        out = self.hand_back([full_check_run("t1"), coder_step("t2")], message=message)
        self.assertIn("Step 6 execution gate", json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"])
        self.assertEqual(self.handback_rows(), [])

    def test_a_plan_impact_hand_back_with_a_code_change_after_the_last_full_check_passes(self):
        message = "status: plan-impact\niter: 1\nspec_iter: 0\nplan_impact: assumed a, found b\n"
        out = self.hand_back([full_check_run("t1"), coder_step("t2")], message=message)
        self.assertEqual(out, "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_hand_back_in_a_repo_whose_full_suite_runs_in_ci_passes_without_a_full_check(self):
        repo = self.tmp / "ci-repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "CLAUDE.md").write_text("# Repo\n\n- Full suite: CI\n", encoding="utf-8")

        self.assertEqual(self.hand_back([full_check_run("t1"), coder_step("t2")], cwd=str(repo)), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def make_repos(self, reviewed_claude_md, cwd_claude_md):
        reviewed, other = self.tmp / "reviewed-repo", self.tmp / "other-repo"
        for repo, claude_md in ((reviewed, reviewed_claude_md), (other, cwd_claude_md)):
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "CLAUDE.md").write_text(claude_md, encoding="utf-8")
        prompt = {"type": "user", "message": {"role": "user", "content": f"review loop\nrepo: {reviewed}"}}
        return prompt, str(other)

    def test_a_hand_back_for_a_reviewed_repo_whose_full_suite_runs_in_ci_passes_from_another_cwd(self):
        prompt, other = self.make_repos("- Full suite: CI\n", "# Other repo\n")

        self.assertEqual(self.hand_back([prompt, full_check_run("t1"), coder_step("t2")], cwd=other), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_hand_back_for_a_reviewed_repo_without_the_ci_line_is_denied_though_the_cwd_has_it(self):
        prompt, other = self.make_repos("# Repo\n", "- Full suite: CI\n")

        out = self.hand_back([prompt, full_check_run("t1"), coder_step("t2")], cwd=other)
        self.assertIn("Step 6 execution gate", json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"])

    def test_a_clean_hand_back_after_a_full_check_passes(self):
        self.assertEqual(self.hand_back([coder_step("t1"), full_check_run("t2")]), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_second_hand_back_on_the_same_unchecked_state_passes(self):
        steps = [full_check_run("t1"), coder_step("t2")]
        self.assertIn("deny", self.hand_back(steps))
        self.assertEqual(self.hand_back(steps), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_new_code_change_after_a_denial_is_denied_again(self):
        self.assertIn("deny", self.hand_back([full_check_run("t1"), coder_step("t2")]))
        self.assertIn("deny", self.hand_back([full_check_run("t1"), coder_step("t2"), full_check_run("t3"),
                                              coder_step("t4")]))

    def test_a_hand_back_while_a_background_reviewer_has_not_reported_is_denied_with_the_wait_reason(self):
        message = "status: critical-blocker\niter: 1\nblockers:\n  - \"returned before the reviewer\"\n"
        for agent_id, packet in (("a1", CONVERGED), ("a2", message)):
            with self.subTest(status=packet.splitlines()[0]):
                out = self.hand_back([full_check_run("t1"), *background_reviewer_launch("t2", "arev")],
                                     agent_id=agent_id, message=packet)

                decision = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertIn("background", decision["permissionDecisionReason"])
                self.assertEqual(self.handback_rows(), [])

    def test_a_hand_back_after_the_background_reviewer_reported_passes(self):
        steps = [*background_reviewer_launch("t1", "arev"), task_notification("t1"), full_check_run("t2")]

        self.assertEqual(self.hand_back(steps), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_an_unreadable_transcript_never_blocks(self):
        self.transcript.write_text("not json\n", encoding="utf-8")
        code, out, _err = self.send_hand_back()
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(len(self.handback_rows()), 1)

    def test_the_transcript_is_found_under_the_session_transcript_when_the_event_names_none(self):
        steps_file = self.tmp / "session" / "subagents" / "agent-a1.jsonl"
        steps_file.parent.mkdir(parents=True)
        steps_file.write_text(json.dumps(coder_step("t1")) + "\n", encoding="utf-8")
        event = {"session_id": SESSION, "tool_name": "SubagentHandback", "agent_type": "review-loop",
                 "agent_id": "a1", "transcript_path": str(self.tmp / "session.jsonl"),
                 "tool_input": {"message": CONVERGED}}
        self.assertIn("deny", self.run_cli(["hook", "handback"], json.dumps(event))[1])

    def test_a_hand_back_whose_files_touched_names_the_plan_file_is_denied_with_the_plan_edit_reason(self):
        steps = [{"type": "user", "message": {"role": "user", "content": "review loop\nplan: docs/plans/orders.md"}},
                 coder_step("t1"), full_check_run("t2")]
        plan_edit = CONVERGED.replace("files_touched: [src/orders.ts]",
                                      "files_touched: [src/orders.ts, docs/plans/orders.md]")
        cap_reached = ("status: cap-reached\niter: 2\nfindings_remaining:\n- {finding: x, file_line: a.ts:1}\n"
                       "files_touched: [docs/plans/orders.md]\n")

        for message in (plan_edit, cap_reached):
            with self.subTest(message=message.splitlines()[0]):
                out = self.hand_back(steps, message=message)

                reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertIn("never edits the plan", reason)
                self.assertEqual(self.handback_rows(), [])

        self.assertEqual(self.hand_back(steps), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_second_hand_back_from_an_agent_with_a_stored_report_is_denied_and_adds_no_row(self):
        steps = [coder_step("t1"), full_check_run("t2")]
        self.assertEqual(self.hand_back(steps), "")
        out = self.hand_back(steps)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("SendMessage", decision["permissionDecisionReason"])
        self.assertEqual(len(self.handback_rows()), 1)


if __name__ == "__main__":
    unittest.main()
