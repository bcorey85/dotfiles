"""Checks for handback.py: the one reader of the review-loop hand-back packet and the per-session store."""
import ast
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

import receipt_repo
import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HANDBACK_SCRIPT") or toolkit_paths.REVIEW_DIR / "handback.py")
SESSION = "sess-1"

spec = importlib.util.spec_from_file_location("handback_under_test", str(SCRIPT))
handback = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handback)
import handback_hook  # noqa: E402
import handback_store  # noqa: E402
import loop_transcript  # noqa: E402
import reviewed_tree  # noqa: E402


def packet_text(fields, **changes):
    """The JSON packet of `fields` with `changes` laid over them; a change to None drops that key."""
    merged = {**fields, **changes}
    kept = {key: value for key, value in merged.items() if value is not None}
    return json.dumps(kept)


def json_packet(**fields):
    """A hand-back packet as the review loop sends it: one JSON object."""
    return json.dumps({"status": "converged", "iter": 1, "fixed": [], **fields})


def ask_packet(*asks):
    """A converged packet whose ask list holds `asks`."""
    return json_packet(ask=list(asks))


CONVERGED_FIELDS = {"status": "converged", "iter": 1,
                    "fixed": [{"finding": "orders query lacked a tenant filter", "file_line": "src/orders.ts:42",
                               "blocker": True}],
                    "skipped_fp": [], "ask": [], "class_closure": "enumerated every query",
                    "files_touched": ["src/orders.ts"]}
CONVERGED = json.dumps(CONVERGED_FIELDS)
CAP_REACHED = json.dumps({"status": "cap-reached", "iter": 0,
                          "findings_remaining": [{"finding": "NOT REVIEWED", "file_line": "a.ts:1"}]})

RETRY_ASK = {"finding": "cap on retries", "file_line": "src/retry.ts:10", "question": "cap at 3?",
             "change": "stop the retry loop after 3 tries", "gate": "code-reviewer", "class": "smell"}
INDEX_ASK = {"finding": "add index", "file_line": "src/db.ts:5", "question": "index tenant_id?",
             "change": "add an index on orders.tenant_id", "gate": "perf-reviewer", "class": "perf"}
TWO_ASKS_FIELDS = {"status": "converged", "iter": 1, "fixed": [], "ask": [RETRY_ASK, INDEX_ASK],
                   "loop_note": "Closing note from the loop."}
TWO_ASKS = json.dumps(TWO_ASKS_FIELDS)


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
    def test_a_plain_text_entry_is_refused_not_read_as_free_text(self):
        for packet_with_text, problem in ((ask_packet("which cache holds the session?"),
                                           "ask[0] must be a JSON object"),
                                          (json_packet(fixed=["removed the dead branch"]),
                                           "fixed[0] must be a JSON object")):
            with self.subTest(problem=problem), self.assertRaises(handback.PacketError) as raised:
                handback.load(packet_with_text)
            self.assertIn(problem, raised.exception.problems[0])

    def test_an_ask_with_an_empty_question_asks_its_change(self):
        packet = handback.load(ask_packet({"question": "", "file_line": "unlocated",
                                           "change": "read the limit from settings", "gate": "code-reviewer",
                                           "class": "bug"}))

        self.assertEqual(packet["ask"][0]["question"], "read the limit from settings")

    def test_an_ask_with_no_question_finding_or_change_is_a_problem(self):
        good_ask = {"question": "cap at 3?", "file_line": "src/a.ts:4", "change": "cap retries at 3",
                    "gate": "code-reviewer", "class": "bug"}
        bad_asks = (({"question": "", "file_line": "unlocated", "gate": "code-reviewer", "class": "bug"},
                     "ask[0] has no question"),
                    (None, "ask[0] must be a JSON object, not null"),
                    (["q"], "ask[0] must be a JSON object, not a list"))
        for bad_ask, problem in bad_asks:
            with self.subTest(bad_ask=bad_ask), self.assertRaises(handback.PacketError) as raised:
                handback.load(ask_packet(bad_ask, good_ask))
            self.assertIn(problem, raised.exception.problems[0])

    def test_check_prints_each_dropped_ask_warning_after_the_ok_line(self):
        pointer_ask = {"text": "the ask above stands", "file_line": "a.ts:1",
                       "drop_reason": "ask only points back to another ask"}
        code, out, _err = self.run_cli(["check"], ask_packet(pointer_ask))

        self.assertEqual(code, 0)
        self.assertEqual(out.splitlines()[1:],
                         ["DROPPED ASKS (tell the user; the review went on without them):",
                          "- ask only points back to another ask, so it was dropped: 'the ask above stands'"])

    def test_a_fixed_entry_that_is_not_a_mapping_is_a_problem(self):
        for fixed, problem in (([None], "fixed[0] must be a JSON object, not null"),
                               ([5], "fixed[0] must be a JSON object, not a number")):
            with self.subTest(fixed=fixed), self.assertRaises(handback.PacketError) as raised:
                handback.load(json_packet(fixed=fixed))
            self.assertIn(problem, raised.exception.problems[0])

    def test_missing_spec_iter_is_none_and_missing_iter_is_a_problem(self):
        self.assertIsNone(handback.load(CONVERGED)["spec_iter"])
        with self.assertRaises(handback.PacketError) as raised:
            handback.load(packet_text(CONVERGED_FIELDS, iter=None))
        self.assertIn("iter is missing", raised.exception.problems[0])


JSON_ASK = {"question": "cap at 3?", "file_line": "src/retry.ts:10", "change": "stop the retry loop after 3 tries",
            "gate": "code-reviewer", "class": "smell"}


class JsonPacketTest(HandbackTestBase):
    def test_a_message_that_is_not_one_json_object_is_a_packet_error(self):
        for message in ("status: converged\niter: 1\nfixed: []\n", "prose with no packet", ""):
            with self.subTest(message=message), self.assertRaises(handback.PacketError) as raised:
                handback.load(message)
            self.assertIn("must be one JSON object", raised.exception.problems[0])

    def test_a_fence_and_whitespace_around_the_json_object_are_removed(self):
        for wrapper in ("  \n{}\n  ", "```\n{}\n```", "```json\n{}\n```\n\n", "~~~json\n{}\n~~~",
                        "````json\n{}\n````"):
            with self.subTest(wrapper=wrapper):
                packet = handback.load(wrapper.format(json_packet(class_closure="done")))
                self.assertEqual(packet["class_closure"], "done")

    def test_a_fence_closer_of_another_char_or_a_shorter_run_leaves_the_packet_not_valid_json(self):
        for wrapper in ("````json\n{}\n```", "~~~json\n{}\n```"):
            with self.subTest(wrapper=wrapper), self.assertRaises(handback.PacketError) as raised:
                handback.load(wrapper.format(json_packet(class_closure="done")))
            self.assertIn("not valid JSON", raised.exception.problems[0])

    def test_an_ask_whose_text_holds_dash_lines_colons_and_a_path_stays_one_ask(self):
        long_ask = {"question": "the plan says -j8 at plan.md:12:\n- the ruling says -j2\n- which one holds?",
                    "file_line": "plan.md:12", "change": "restore -j8", "gate": "code-reviewer", "class": "plan-drift"}
        packet = handback.load(json_packet(ask=[long_ask, JSON_ASK]))
        self.assertEqual([item["file_line"] for item in packet["ask"]], ["plan.md:12", "src/retry.ts:10"])
        self.assertEqual(packet["ask"][0]["question"], long_ask["question"])
        self.assertEqual(packet["dropped_asks"], [])

    def test_blockers_keep_every_entry_whole_with_their_multi_line_text(self):
        first = "full check failed:\n- test_a\n- test_b"
        second = "setup fault: no package.json"
        packet = handback.load(json_packet(status="critical-blocker", blockers=[first, second]))
        self.assertEqual(packet["blockers"], [first, second])

    def test_a_blocker_flag_on_a_remaining_finding_refuses_a_clean_status(self):
        remaining = [{"disposition": "fix", "finding": "x", "file_line": "a.ts:1", "blocker": True}]
        with self.assertRaises(handback.PacketError) as raised:
            handback.load(json_packet(findings_remaining=remaining))
        self.assertIn("findings_remaining holds a blocker", raised.exception.problems[0])

    def test_a_wrong_shaped_value_is_a_packet_error_that_names_the_key(self):
        cases = [
            ({"fixed": "removed the dead branch"}, "fixed must be a JSON list, not a string"),
            ({"ask": {"question": "q?"}}, "ask must be a JSON list, not an object"),
            ({"blockers": None}, "blockers must be a JSON list, not null"),
            ({"status": ["converged"]}, "status must be a JSON string, not a list"),
            ({"iter": 1.5}, "iter must be a JSON string or integer, not a number"),
            ({"iter": True}, "iter must be a JSON string or integer, not a boolean"),
            ({"plan_impact": None}, "plan_impact must be a JSON string, not null"),
        ]
        for fields, problem in cases:
            with self.subTest(fields=fields), self.assertRaises(handback.PacketError) as raised:
                handback.load(json_packet(**fields))
            self.assertIn(problem, raised.exception.problems)

    def test_an_unknown_key_goes_to_the_trailer_as_a_key_value_line(self):
        packet = handback.load(json_packet(surprise="x", principle=["a", 1]))
        self.assertEqual(packet["trailer"], 'surprise: x\nprinciple: ["a",1]')

    def test_text_that_opens_a_brace_but_is_not_json_is_a_packet_error(self):
        with self.assertRaises(handback.PacketError) as raised:
            handback.load('{"status": "converged", "iter": 1,')
        self.assertIn("not valid JSON", raised.exception.problems[0])

    def test_a_json_object_that_breaks_the_packet_rules_names_each_broken_rule(self):
        cases = {
            "status is plan-impact but plan_impact is empty": json_packet(status="plan-impact", plan_impact=""),
            "status is cap-reached but findings_remaining is missing": json_packet(status="cap-reached", fixed=[]),
            "status is critical-blocker but blockers is empty": json_packet(status="critical-blocker", blockers=[]),
            "fixed is missing": json.dumps({"status": "converged", "iter": 1}),
            "ask entry has no change": json_packet(ask=[{**JSON_ASK, "change": ""}]),
            "ask entry has no file_line": json_packet(ask=[{**JSON_ASK, "file_line": ""}]),
            "status is 'done'": json_packet(status="done"),
            "iter is missing": json.dumps({"status": "converged", "fixed": []}),
            "fixed[0] has no finding": json_packet(fixed=[{"blocker": True}]),
        }
        for problem, message in cases.items():
            with self.subTest(problem), self.assertRaises(handback.PacketError) as raised:
                handback.load(message)
            self.assertTrue([found for found in raised.exception.problems if found.startswith(problem)],
                            raised.exception.problems)

    def test_a_json_packet_with_n_asks_some_without_file_line_yields_n_asks(self):
        asks = [{**JSON_ASK, "question": f"question {number}?"} for number in range(4)]
        del asks[1]["file_line"]
        del asks[3]["file_line"]
        packet = handback.load(json_packet(ask=asks))
        self.assertEqual([item["question"] for item in packet["ask"]], [f"question {number}?" for number in range(4)])
        self.assertEqual([item["file_line"] for item in packet["ask"]],
                         ["src/retry.ts:10", handback.UNLOCATED, "src/retry.ts:10", handback.UNLOCATED])
        self.assertEqual(packet["dropped_asks"], [])

    def test_a_json_ask_with_no_question_asks_its_finding_or_change_and_gets_the_defaults(self):
        asks = [{"finding": "retries never stop", "file_line": "a.ts:1", "change": "cap at 3"},
                {"file_line": "b.ts:2", "change": "read the limit from settings", "class": "ops"}]
        packet = handback.load(json_packet(ask=asks))
        self.assertEqual([item["question"] for item in packet["ask"]],
                         ["retries never stop", "read the limit from settings"])
        self.assertEqual(packet["ask"][1]["gate"], handback.DEFAULT_GATE)
        self.assertEqual((packet["ask"][1]["class"], packet["ask"][1]["class_raw"]), ("other", "ops"))

    def test_a_json_list_entry_that_is_not_a_mapping_or_lacks_its_text_field_is_a_problem_that_names_it(self):
        cases = {
            "ask[1] must be a JSON object, not a string": json_packet(ask=[JSON_ASK, "cap at 3? | a.ts:1"]),
            "ask[0] has no question": json_packet(ask=[{"file_line": "a.ts:1"}]),
            "fixed[0] must be a JSON object, not a string": json_packet(fixed=["removed the dead branch"]),
            "findings_remaining[0] has no finding": json_packet(status="cap-reached", findings_remaining=[{}]),
            "skipped_fp[0] has no item": json_packet(skipped_fp=[{"reason": "r"}]),
            "open_classes must be a JSON list of strings": json_packet(open_classes=[{"class": "x"}]),
        }
        for problem, message in cases.items():
            with self.subTest(problem), self.assertRaises(handback.PacketError) as raised:
                handback.load(message)
            self.assertTrue([found for found in raised.exception.problems if found.startswith(problem)],
                            raised.exception.problems)

    def test_a_json_packet_carries_its_open_classes_as_a_list(self):
        packet = handback.load(json_packet(open_classes=["log with a trailing blank line"]))
        self.assertEqual(packet["open_classes"], ["log with a trailing blank line"])
        self.assertEqual(handback.load(json_packet())["open_classes"], [])

    def test_check_accepts_a_json_packet(self):
        code, out, _err = self.run_cli(["check"], json_packet(ask=[JSON_ASK]))
        self.assertEqual((code, out.splitlines()[0]), (0, "ok: status=converged fixed=0 ask=1"))

    def test_the_agent_doc_template_is_one_json_object_with_every_packet_key(self):
        doc = (toolkit_paths.CLAUDE_DIR / "agents" / "review-loop.md").read_text()
        section = doc.split("## Return packet", 1)[1]
        template = re.search(r"```json\n(.*?)\n```", section, re.S).group(1)
        self.assertEqual(set(json.loads(template)), set(handback.PACKET_KEYS))


class ValidateTest(HandbackTestBase):
    def test_an_ask_carries_its_one_proposed_change_as_its_own_field(self):
        packet = handback.load(TWO_ASKS)

        self.assertEqual("cap at 3?", packet["ask"][0]["question"])
        self.assertEqual("stop the retry loop after 3 tries", packet["ask"][0]["change"])

    def test_an_either_or_ask_with_no_proposed_change_is_refused(self):
        either_or = {key: value for key, value in RETRY_ASK.items() if key != "change"}
        either_or["question"] = "cap at 3, or keep retrying with backoff?"

        with self.assertRaises(handback.PacketError) as raised:
            handback.load(ask_packet(either_or, INDEX_ASK))

        self.assertIn("ask entry has no change", raised.exception.problems[0])

    def test_unknown_ask_class_becomes_other_and_the_raw_class_is_kept(self):
        packet = handback.load(ask_packet({**RETRY_ASK, "class": "ops"}, INDEX_ASK))
        self.assertEqual((packet["ask"][0]["class"], packet["ask"][0]["class_raw"]), ("other", "ops"))
        self.assertNotIn("class_raw", packet["ask"][1])

    def test_gate_is_cut_to_its_first_token_and_defaults_when_missing(self):
        packet = handback.load(ask_packet({**RETRY_ASK, "gate": "code-reviewer / robustness"}, INDEX_ASK))
        self.assertEqual(packet["ask"][0]["gate"], "code-reviewer")
        index_ask_without_gate = {key: value for key, value in INDEX_ASK.items() if key != "gate"}
        packet = handback.load(ask_packet(RETRY_ASK, index_ask_without_gate))
        self.assertEqual(packet["ask"][1]["gate"], "code-reviewer")

    def test_every_status_word_validates_with_its_required_fields(self):
        remaining = [{"finding": "x", "file_line": "a.ts:1"}]
        cases = {
            "converged": CONVERGED,
            "deferred": json_packet(status="deferred", findings_remaining=remaining),
            "critical-blocker": json.dumps({"status": "critical-blocker", "iter": 1, "blockers": ["bad thing"]}),
            "setup-fault": json.dumps({"status": "setup-fault", "iter": 1, "blockers": ["full check could not run"]}),
            "fix-removed-change": json.dumps({"status": "fix-removed-change", "iter": 1,
                                              "blockers": ["the fix passes removed 9 of 10"]}),
            "cap-reached": json.dumps({"status": "cap-reached", "iter": 2, "findings_remaining": remaining}),
            "plan-impact": json.dumps({"status": "plan-impact", "iter": 1, "spec_iter": 0,
                                       "plan_impact": "assumed a, found b"}),
        }
        for status, text in cases.items():
            self.assertEqual(handback.load(text)["status"], status)

    def test_each_stop_condition_is_a_problem(self):
        cases = [{"status": "done", "iter": 1},
                 {"status": "converged", "iter": "x", "fixed": []},
                 {"status": "converged", "iter": 1},
                 {"status": "converged", "iter": 1, "spec_iter": "many", "fixed": []},
                 {"status": "converged", "iter": 1, "fixed": [{"blocker": True}]},
                 {"status": "converged", "iter": 1, "fixed": [], "ask": [{"finding": "x", "question": "y?"}]},
                 {"status": "plan-impact", "iter": 1, "plan_impact": ""},
                 {"status": "critical-blocker", "iter": 1, "blockers": []},
                 {"status": "setup-fault", "iter": 1, "blockers": []},
                 {"status": "fix-removed-change", "iter": 1, "blockers": []},
                 {"status": "cap-reached", "iter": 2},
                 {"status": "cap-reached", "iter": 2, "findings_remaining": []},
                 {"status": "deferred", "iter": 1, "fixed": [], "findings_remaining": []}]
        for fields in cases:
            with self.subTest(fields=fields), self.assertRaises(handback.PacketError):
                handback.load(json.dumps(fields))

    def test_cap_reached_with_a_key_present_but_empty_is_a_problem_and_a_missing_key_is_another(self):
        for fields, absence in (
            ({"status": "cap-reached", "iter": 2, "findings_remaining": []}, "empty"),
            ({"status": "cap-reached", "iter": 2}, "missing"),
        ):
            with self.subTest(fields=fields), self.assertRaises(handback.PacketError) as raised:
                handback.load(json.dumps(fields))
            self.assertIn(f"status is cap-reached but findings_remaining is {absence}", raised.exception.problems)

    def test_pending_report_is_not_a_packet(self):
        with self.assertRaises(handback.PacketError) as raised:
            handback.load("status: pending. The verification pass has not reported.\n\nDone so far:\n- fixed\n")
        self.assertIn("must be one JSON object", raised.exception.problems[0])


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
        for entry in [{}, {"finding_id": None}, {"finding_id": 1234567890123456}, {"finding_id": ["a1b2c3d4e5f60001"]}]:
            with self.subTest(entry=entry):
                self.assertIsNone(handback.ask_finding_id(entry))


class AskParsedFindingIdTest(unittest.TestCase):
    def test_a_finding_id_the_loop_wrote_survives_parsing(self):
        first_ask = {"finding": "x", "finding_id": "a1b2c3d4e5f60001", "file_line": "a.ts:1", "question": "q?",
                     "change": "c"}
        second_ask = {"finding": "y", "finding_id": "a1b2c3d4e5f60002", "file_line": "b.ts:2", "question": "q?",
                      "change": "c"}
        packet = handback.load(ask_packet(first_ask, second_ask))
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
        remaining = [{"disposition": "fix", "finding": "left over", "file_line": "a.ts:1"}]
        text = packet_text(CONVERGED_FIELDS, findings_remaining=remaining)
        self.assertIn("### Findings remaining", handback.render(handback.load(text), "review"))

    def test_bare_not_applicable_closure_with_empty_fixed_prints_one_line(self):
        packet = handback.load(json_packet(iter=0, class_closure="n/a"))
        rendered = handback.render(packet, "review")
        self.assertEqual(rendered.count("Class closure"), 1)
        self.assertNotIn("receipt is missing", rendered)

    def test_missing_closure_with_fixed_entries_says_the_receipt_is_missing(self):
        packet = handback.load(packet_text(CONVERGED_FIELDS, class_closure=None))
        self.assertIn("receipt is missing", handback.render(packet, "review"))

    def test_a_full_check_that_did_not_run_or_failed_before_the_diff_says_so_and_a_passed_one_prints_nothing(self):
        for full_check in ("not run (CI)", "not run (timeout)", "not run (environment gap: No module named 'ruff')",
                           "not run (check-command error: fatal: ambiguous argument 'web/schema.json')",
                           "pre-existing failure (the check fails the same way without this diff, so it did not "
                           "verify this diff)", "passed (check only; CI runs the full suite)"):
            with self.subTest(full_check=full_check):
                packet = handback.load(packet_text(CONVERGED_FIELDS, full_check=full_check))

                self.assertIn(f"Full check: {full_check}", handback.render(packet, "review"))
        passed = handback.load(packet_text(CONVERGED_FIELDS, full_check="passed"))
        self.assertNotIn("Full check", handback.render(passed, "review"))

    def test_the_unverified_full_check_and_its_new_fields_parse_and_the_created_files_render(self):
        packet = handback.load(packet_text(
            CONVERGED_FIELDS, full_check="unverified (exit 0, no runner summary)", full_check_command="make test",
            full_check_summary="not found", check_changed=["gen.ts"], check_created=["dist/out.js"]))

        self.assertEqual("unverified (exit 0, no runner summary)", packet["full_check"])
        self.assertEqual(("make test", "not found"), (packet["full_check_command"], packet["full_check_summary"]))
        self.assertEqual((["gen.ts"], ["dist/out.js"]), (packet["check_changed"], packet["check_created"]))
        rendered = handback.render(packet, "review")
        self.assertIn("Full check: unverified (exit 0, no runner summary)", rendered)
        self.assertIn("Changed by the full check, not by the coder (restore with `git checkout --` or keep): gen.ts",
                      rendered)
        self.assertIn("Created by the full check, not by the coder (delete or keep): dist/out.js", rendered)

    def test_files_the_check_rewrote_after_the_coder_edited_them_parse_and_render_a_review_warning(self):
        packet = handback.load(packet_text(CONVERGED_FIELDS, check_rewrote_edited=["edited.ts"]))

        self.assertEqual(["edited.ts"], packet["check_rewrote_edited"])
        rendered = handback.render(packet, "review")
        self.assertIn("Hold coder edits and a full check rewrite, so review them (do not restore): edited.ts", rendered)

    def test_sections_print_before_the_trailer(self):
        packet = handback.load(TWO_ASKS)
        rendered = handback.render(packet, "fix", [("Aikido replies", ["- a.ts:1: Fixed"])])
        self.assertLess(rendered.index("### Aikido replies"), rendered.index("Closing note"))

    def test_fixed_findings_show_as_a_count_and_never_as_a_list(self):
        small_fix = {"finding": "small", "file_line": "a.ts:1", "blocker": False}
        text = packet_text(CONVERGED_FIELDS, fixed=[small_fix, *CONVERGED_FIELDS["fixed"]])
        rendered = handback.render(handback.load(text), "review")
        self.assertIn("Fixed 2, nits 0, skipped 0", rendered)
        self.assertNotIn("small", rendered)
        self.assertNotIn("orders query lacked", rendered)

    def test_a_blocked_agent_and_the_step_it_skipped_print_under_their_own_heading(self):
        blocked_line = "test-reviewer: Step 1 test map skipped (credential hook denied a bulk cp)"
        packet = handback.load(packet_text(CONVERGED_FIELDS, blocked_agents=[blocked_line]))

        rendered = handback.render(packet, "review")

        self.assertIn(f"### Blocked agents (not reviewed)\n- {blocked_line}", rendered)
        self.assertNotIn("Blocked agents", handback.render(handback.load(CONVERGED), "review"))


class StoreTest(HandbackTestBase):
    def test_reviewed_repo_names_the_repo_its_prompt_or_cwd_holds(self):
        with tempfile.TemporaryDirectory() as folder:
            named, cwd_repo, outside = (os.path.join(folder, name) for name in ("named", "cwd", "outside"))
            for repo in (named, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            os.mkdir(outside)
            reviewed_repo = loop_transcript.reviewed_repo
            self.assertEqual(reviewed_repo("mode: review-first\nrepo: ../named\n", cwd_repo), os.path.realpath(named))
            self.assertEqual(reviewed_repo("mode: review-first\n", cwd_repo), os.path.realpath(cwd_repo))
            self.assertIsNone(reviewed_repo("mode: review-first\n", outside))
            self.assertIsNone(reviewed_repo("mode: review-first\nrepo: ../outside\n", cwd_repo))
            handoff_prompt = f"mode: review-first\nUncommitted changes in {named}/src/a.py (branch b)\n"
            self.assertEqual(reviewed_repo(handoff_prompt, cwd_repo), os.path.realpath(named))

    def test_a_first_path_in_no_work_tree_falls_back_to_the_cwd_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd_repo, outside = (os.path.join(folder, name) for name in ("cwd", "outside"))
            subprocess.run(["git", "init", "-q", cwd_repo], check=True)
            os.mkdir(outside)
            prompt = f"mode: review-first\nRead the plan at {outside}/plan.md first.\n"
            self.assertEqual(loop_transcript.reviewed_repo(prompt, cwd_repo), os.path.realpath(cwd_repo))
            self.assertIsNone(loop_transcript.reviewed_repo(prompt, outside))

    def test_a_url_before_the_first_path_does_not_hide_the_path(self):
        with tempfile.TemporaryDirectory() as folder:
            named, cwd_repo = (os.path.join(folder, name) for name in ("named", "cwd"))
            for repo in (named, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            prompt = f"mode: review-first\nSee https://github.com/o/r/pull/3 then {named}/plan.md\n"
            self.assertEqual(loop_transcript.reviewed_repo(prompt, cwd_repo), os.path.realpath(named))

    def test_a_url_query_string_holding_a_path_does_not_name_the_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            named, cwd_repo = (os.path.join(folder, name) for name in ("named", "cwd"))
            for repo in (named, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            prompt = f"mode: review-first\nSee https://h/p?x={named}/inner.py and nothing\n"
            self.assertEqual(loop_transcript.reviewed_repo(prompt, cwd_repo), os.path.realpath(cwd_repo))

    def test_a_first_path_cut_at_a_space_falls_back_to_the_cwd_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            outer, cwd_repo = (os.path.join(folder, name) for name in ("outer", "cwd"))
            spaced = os.path.join(outer, "my repo")
            for repo in (outer, spaced, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            prompt = f"mode: review-first\nUncommitted changes in {spaced}/src/a.py\n"
            self.assertEqual(loop_transcript.reviewed_repo(prompt, cwd_repo), os.path.realpath(cwd_repo))

    def test_a_repo_line_with_a_trailing_parenthetical_names_the_repo_before_it(self):
        with tempfile.TemporaryDirectory() as folder:
            named, cwd_repo = (os.path.join(folder, name) for name in ("named", "cwd"))
            for repo in (named, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            prompt = "mode: review-first\nrepo: ../named (branch b)\n"
            self.assertEqual(loop_transcript.reviewed_repo(prompt, cwd_repo), os.path.realpath(named))

    def test_the_dispatch_row_and_the_loop_transcript_name_the_same_reviewed_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            named, cwd_repo, outside = (os.path.join(folder, name) for name in ("named", "cwd", "outside"))
            for repo in (named, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            os.mkdir(outside)
            linked = os.path.join(folder, "linked")
            os.symlink(named, linked)
            spaced = os.path.join(folder, "my repo")
            subprocess.run(["git", "init", "-q", spaced], check=True)
            cases = (("repo: ../named\n", cwd_repo, named),
                     (f"repo: {spaced}\n", cwd_repo, spaced),
                     ("repo: ../missing\n", cwd_repo, None),
                     ("mode: review-first\n", cwd_repo, cwd_repo),
                     ("mode: review-first\n", outside, None),
                     (f"repo: {linked}\n", cwd_repo, named),
                     (f"Uncommitted changes in {linked}/src/a.py\n", cwd_repo, named))
            for prompt, cwd, expected_repo in cases:
                with self.subTest(prompt=prompt, cwd=cwd):
                    shutil.rmtree(self.store, ignore_errors=True)
                    event = {"session_id": SESSION, "cwd": cwd,
                             "tool_input": {"subagent_type": "review-loop", "prompt": prompt}}
                    code, _, _ = self.run_cli(["hook", "dispatch"], json.dumps(event))
                    self.assertEqual(code, 0)

                    transcript_path = os.path.join(folder, "loop.jsonl")
                    prompt_record = {"type": "user", "message": {"role": "user", "content": prompt}}
                    pathlib.Path(transcript_path).write_text(json.dumps(prompt_record) + "\n")
                    transcript = loop_transcript.LoopTranscript(transcript_path)

                    dispatch_row = handback_store.latest(SESSION)["dispatch"]
                    if expected_repo is None:
                        self.assertIsNone(dispatch_row["repo"])
                        self.assertIsNone(transcript.reviewed_repo(cwd))
                        continue
                    expected = os.path.realpath(expected_repo)
                    self.assertEqual(dispatch_row["repo"], expected)
                    self.assertEqual(transcript.reviewed_repo(cwd), expected)

    def test_a_scope_root_in_no_work_tree_names_no_repo(self):
        with tempfile.TemporaryDirectory() as folder:
            cwd_repo, plain_folder = (os.path.join(folder, name) for name in ("cwd", "plain"))
            subprocess.run(["git", "init", "-q", cwd_repo], check=True)
            os.mkdir(plain_folder)
            self.assertIsNone(loop_transcript.reviewed_repo("mode: review-first\n", cwd_repo, scope_root=plain_folder))

    def test_the_scope_root_wins_over_the_prompt_repo_line(self):
        with tempfile.TemporaryDirectory() as folder:
            scoped, named, cwd_repo = (os.path.join(folder, name) for name in ("scoped", "named", "cwd"))
            for repo in (scoped, named, cwd_repo):
                subprocess.run(["git", "init", "-q", repo], check=True)
            repo_found = loop_transcript.reviewed_repo(f"repo: {named}\n", cwd_repo, scope_root=scoped)
            self.assertEqual(repo_found, os.path.realpath(scoped))

    def test_latest_reports_dispatch_handback_and_pending(self):
        self.assertEqual(handback_store.latest(SESSION),
                         {"dispatch": None, "handback": None, "stop": None, "unanswered": 0, "pending": False})
        handback_store.record(SESSION, "dispatch")
        self.assertTrue(handback_store.latest(SESSION)["pending"])
        handback_store.record(SESSION, "handback", status="converged", message="m")
        seen = handback_store.latest(SESSION)
        self.assertEqual((seen["handback"]["status"], seen["pending"]), ("converged", False))
        handback_store.record(SESSION, "dispatch")
        self.assertTrue(handback_store.latest(SESSION)["pending"])

    def test_latest_counts_dispatches_since_the_last_hand_back(self):
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "dispatch")
        self.assertEqual(handback_store.latest(SESSION)["unanswered"], 2)
        handback_store.record(SESSION, "handback", status="converged", message="m")
        self.assertEqual(handback_store.latest(SESSION)["unanswered"], 0)
        handback_store.record(SESSION, "dispatch")
        seen = handback_store.latest(SESSION)
        self.assertEqual((seen["unanswered"], seen["pending"]), (1, True))

    def test_a_dispatch_another_hook_denied_blocks_nothing_once_a_later_dispatch_hands_back(self):
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "handback", status="converged", message="m")
        seen = handback_store.latest(SESSION)
        self.assertFalse(seen["pending"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_hand_back_gap_names_why_there_is_no_current_hand_back(self):
        seen = handback_store.latest(SESSION)
        self.assertEqual(handback_store.hand_back_gap(seen), handback_store.NO_DISPATCH)
        handback_store.record(SESSION, "dispatch")
        seen = handback_store.latest(SESSION)
        self.assertEqual(handback_store.hand_back_gap(seen), handback_store.NO_HANDBACK)
        handback_store.record(SESSION, "handback", status="converged", message="m")
        seen = handback_store.latest(SESSION)
        self.assertIsNone(handback_store.hand_back_gap(seen))
        handback_store.record(SESSION, "dispatch")
        seen = handback_store.latest(SESSION)
        self.assertEqual(handback_store.hand_back_gap(seen), handback_store.REDISPATCHED)

    def test_a_stop_with_an_open_background_agent_is_a_wait_until_a_later_stop_or_a_hand_back(self):
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=1)
        self.assertEqual(handback_store.hand_back_gap(handback_store.latest(SESSION)), handback_store.LOOP_WAITING)
        handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=0)
        self.assertEqual(handback_store.hand_back_gap(handback_store.latest(SESSION)), handback_store.NO_HANDBACK)
        handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=2)
        handback_store.record(SESSION, "handback", status="converged", message="m")
        self.assertIsNone(handback_store.hand_back_gap(handback_store.latest(SESSION)))

    def test_a_stop_the_gate_blocked_is_not_the_standing_stop(self):
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=0, ask_rows=[{"file": "a", "line": 1}])
        handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=0, ask_rows=[], blocked=True)
        self.assertEqual(handback_store.latest(SESSION)["stop"]["ask_rows"], [{"file": "a", "line": 1}])

    def test_the_settled_stop_is_the_awaited_agents_unblocked_stop_at_or_after_the_hand_back(self):
        before = handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=0)["ts"]
        handback_store.record(SESSION, "stop", agent_id="a2", open_dispatches=0)
        handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=0, blocked=True)
        self.assertIsNone(handback.settled_stop_row(SESSION, "a1", before + 0.0001))
        settled = handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=0, ask_rows=[])
        self.assertEqual(handback.settled_stop_row(SESSION, "a1", before + 0.0001), settled)

    def test_a_wait_after_a_redispatch_is_not_redispatched_and_a_new_dispatch_clears_an_old_stop(self):
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "handback", status="converged", message="m")
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "stop", agent_id="a2", open_dispatches=1)
        self.assertEqual(handback_store.hand_back_gap(handback_store.latest(SESSION)), handback_store.LOOP_WAITING)
        handback_store.record(SESSION, "dispatch")
        self.assertEqual(handback_store.hand_back_gap(handback_store.latest(SESSION)), handback_store.REDISPATCHED)

    def test_false_clean_reason_refuses_clean_while_the_loop_waits(self):
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=1)
        self.assertIn("waiting on a background agent or shell", handback.false_clean_reason(SESSION))
        handback_store.record(SESSION, "handback", status="converged", message="m")
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "stop", agent_id="a2", open_dispatches=1)
        self.assertIn("waiting on a background agent or shell", handback.false_clean_reason(SESSION))

    def test_a_stored_hand_back_with_no_dispatch_row_has_its_own_reason(self):
        handback_store.record(SESSION, "handback", status="converged", message="m")
        reason = handback.false_clean_reason(SESSION)
        self.assertIn("no review-loop dispatch on record", reason)

    def test_false_clean_reason_allows_only_a_current_converged_or_deferred_hand_back(self):
        self.assertIn("no review-loop hand-back", handback.false_clean_reason(SESSION))
        self.assertIn("no review-loop hand-back", handback.false_clean_reason(""))
        handback_store.record(SESSION, "dispatch")
        self.assertIn("no review-loop hand-back", handback.false_clean_reason(SESSION))
        handback_store.record(SESSION, "handback", status="critical-blocker", message="m")
        self.assertIn("critical-blocker", handback.false_clean_reason(SESSION))
        handback_store.record(SESSION, "dispatch")
        self.assertIn("dispatched again", handback.false_clean_reason(SESSION))
        handback_store.record(SESSION, "handback", status="deferred", message="m")
        self.assertIsNone(handback.false_clean_reason(SESSION))
        handback_store.record(SESSION, "dispatch")
        handback_store.record(SESSION, "handback", status="converged", message="m")
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_sessions_never_see_or_overwrite_each_other(self):
        handback_store.record("a", "dispatch")
        handback_store.record("a", "handback", status="converged", message="m")
        handback_store.record("b", "dispatch")
        self.assertEqual(handback_store.latest("a")["handback"]["status"], "converged")
        self.assertIsNone(handback_store.latest("b")["handback"])
        self.assertEqual(len((self.store / "a.jsonl").read_text().splitlines()), 2)

    def test_records_only_append(self):
        handback_store.record(SESSION, "dispatch")
        first = (self.store / (SESSION + ".jsonl")).read_text()
        handback_store.record(SESSION, "handback", status="converged", message="m")
        self.assertTrue((self.store / (SESSION + ".jsonl")).read_text().startswith(first))

    def test_session_ids_cannot_escape_the_store(self):
        handback_store.record("../../evil", "dispatch")
        self.assertEqual([path.name for path in self.store.iterdir()], [".._.._evil.jsonl"])

    def test_a_session_id_with_no_name_left_after_sanitizing_is_refused(self):
        for session_id in ("", ".", "..", "_"):
            with self.subTest(session_id=session_id), self.assertRaises(ValueError):
                handback_store.session_file(session_id)

    def test_empty_session_has_no_rows_and_is_not_an_error(self):
        self.assertEqual(handback_store.latest("")["handback"], None)
        self.assertEqual(handback_store.latest(None)["dispatch"], None)

    def test_stale_session_files_are_pruned_on_the_next_record(self):
        handback_store.record("old", "dispatch")
        old = self.store / "old.jsonl"
        stale = time.time() - 30 * 86400
        os.utime(str(old), (stale, stale))
        handback_store.record("new", "dispatch")
        self.assertFalse(old.exists())
        self.assertTrue((self.store / "new.jsonl").exists())


class CliTest(HandbackTestBase):
    def test_check_accepts_a_good_packet_and_names_the_status(self):
        code, out, err = self.run_cli(["check"], CONVERGED)
        self.assertEqual(code, 0, err)
        self.assertIn("ok: status=converged", out)

    def test_check_rejects_a_bad_packet_with_the_reason_on_stderr(self):
        code, _out, err = self.run_cli(["check"], json_packet(status="nope"))
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

    def test_review_loop_dispatch_and_good_hand_back_are_stored_without_output_and_other_agents_are_not(self):
        self.assertEqual(self.fire(self.event("Agent"))[:2], (0, ""))
        reviewer = {"session_id": SESSION, "tool_name": "Agent", "agent_type": "review-loop", "agent_id": "a1",
                    "tool_input": {"subagent_type": "code-reviewer"}}
        self.assertEqual(self.fire(reviewer)[:2], (0, ""))
        self.assertEqual(self.fire(self.event("SubagentHandback"))[:2], (0, ""))
        seen = handback_store.latest(SESSION)
        self.assertEqual(seen["handback"]["status"], "converged")
        self.assertFalse(seen["pending"])

        self.fire(self.event("Agent", agent="coder"))
        self.fire(self.event("SubagentHandback", agent="coder"))
        self.assertEqual(handback_store.latest(SESSION), seen)

    def test_bad_packet_is_denied_once_per_agent_then_stored_as_invalid(self):
        bad = self.event("SubagentHandback", message=json_packet(status="pending"))
        code, out, _ = self.fire(bad)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual((code, decision["permissionDecision"]), (0, "deny"))
        self.assertIn("status is", decision["permissionDecisionReason"])
        self.assertIsNone(handback_store.latest(SESSION)["handback"])
        code, out, _err = self.fire(bad)
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(handback_store.latest(SESSION)["handback"]["status"], "invalid")

    def test_a_json_hand_back_is_stored_and_a_bad_json_one_is_denied_once_with_the_json_repair_text(self):
        self.fire(self.event("Agent"))
        reviewer = {"session_id": SESSION, "tool_name": "Agent", "agent_type": "review-loop", "agent_id": "a1",
                    "tool_input": {"subagent_type": "code-reviewer"}}
        self.fire(reviewer)
        bad = self.event("SubagentHandback", message=json_packet(status="plan-impact", plan_impact=""))
        _code, out, _err = self.fire(bad)
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("status is plan-impact but plan_impact is empty", reason)
        self.assertIn("one JSON object", reason)
        self.assertIsNone(handback_store.latest(SESSION)["handback"])

        good = self.event("SubagentHandback", message=json_packet(ask=[JSON_ASK]))
        self.assertEqual(self.fire(good)[:2], (0, ""))
        self.assertEqual(handback_store.latest(SESSION)["handback"]["status"], "converged")

    def loop_dispatch(self, tool_use_id):
        dispatch = self.event("Agent")
        dispatch["tool_use_id"] = tool_use_id
        return dispatch

    def hand_back_reviewed(self):
        reviewer = {"session_id": SESSION, "tool_name": "Agent", "agent_type": "review-loop", "agent_id": "a1",
                    "tool_input": {"subagent_type": "code-reviewer"}}
        self.fire(reviewer)
        return self.fire(self.event("SubagentHandback"))

    def test_a_denied_re_dispatch_leaves_the_good_hand_back_current(self):
        ran = self.loop_dispatch("toolu_ran")
        self.fire(ran)
        self.fire(ran, "ran")
        self.hand_back_reviewed()
        before = handback_store.latest(SESSION)

        self.fire(self.loop_dispatch("toolu_denied"))

        after = handback_store.latest(SESSION)
        self.assertEqual((after["dispatch"], after["handback"], after["unanswered"]),
                         (before["dispatch"], before["handback"], before["unanswered"]))
        self.assertEqual(after["dispatch"]["tool_use_id"], "toolu_ran")
        self.assertEqual(after["unanswered"], 0)
        self.assertFalse(after["pending"])

    def test_a_new_dispatch_that_never_ran_still_ends_the_last_loops_stop(self):
        ran = self.loop_dispatch("toolu_ran")
        self.fire(ran)
        self.fire(ran, "ran")
        handback_store.record(SESSION, "stop", agent_id="a1", open_dispatches=1)

        self.fire(self.loop_dispatch("toolu_new"))

        self.assertIsNone(handback_store.latest(SESSION)["stop"])

    def test_a_foreground_dispatch_counts_once_its_call_ran(self):
        dispatch = self.loop_dispatch("toolu_fg")
        self.fire(dispatch)

        self.assertEqual(self.hand_back_reviewed()[:2], (0, ""))
        self.fire(dispatch, "ran")

        seen = handback_store.latest(SESSION)
        self.assertEqual(seen["dispatch"]["tool_use_id"], "toolu_fg")
        self.assertEqual(seen["handback"]["status"], "converged")

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
        self.assertIsNone(handback_store.latest(SESSION)["handback"])
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
        self.assertTrue(handback_store.latest(SESSION)["handback"]["unreviewed_fix"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def capped_packet_on_a_fresh_repo(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
               "GIT_COMMITTER_EMAIL": "t@t"}
        for argv in (["init", "-q"], ["commit", "-q", "--allow-empty", "-m", "base"]):
            subprocess.run(["git", "-C", str(repo), *argv], check=True, capture_output=True, env=env)
        tree = reviewed_tree.fingerprint(str(repo))[1]
        capped = json_packet(status="cap-reached", findings_remaining=[{"finding": "x", "file_line": "a.ts:1"}],
                             full_check="passed", full_check_tree=tree)
        return repo, capped

    def test_a_capped_packet_that_reads_deferred_is_flagged_by_its_effective_status(self):
        repo, capped = self.capped_packet_on_a_fresh_repo()
        self.dispatch("review-loop", prompt=f"repo: {repo}\n")
        self.dispatch("code-reviewer", "a1")
        self.dispatch("backend-coder-deep", "a1")

        self.assertEqual(self.hand_back(message=capped), (0, ""))

        self.assertTrue(handback_store.latest(SESSION)["handback"]["unreviewed_fix"])

    def test_a_capped_packet_that_reads_deferred_with_no_reviewer_is_denied_once_then_flagged(self):
        repo, capped = self.capped_packet_on_a_fresh_repo()
        self.dispatch("review-loop", prompt=f"repo: {repo}\n")
        self.dispatch("backend-coder-deep", "a1")

        self.assert_denied(self.hand_back(message=capped))
        self.assertEqual(self.hand_back(message=capped), (0, ""))

        self.assertIn("no reviewer", handback.false_clean_reason(SESSION))

    def test_a_cap_after_a_handed_in_change_with_no_reviewer_is_denied_once(self):
        self.dispatch("review-loop", prompt="mode: review-first\naccepted change: rename the flag\n")
        self.dispatch("coder", "a1")
        self.assert_denied(self.hand_back(message=CAP_REACHED))
        self.assertIsNone(handback_store.latest(SESSION)["handback"])
        self.assertEqual(self.hand_back(message=CAP_REACHED), (0, ""))
        self.assertEqual(handback_store.latest(SESSION)["handback"]["status"], "cap-reached")

    def test_a_cap_with_a_coder_after_the_last_reviewer_is_denied_once(self):
        self.dispatch("review-loop")
        self.dispatch("code-reviewer", "a1")
        self.dispatch("coder", "a1")
        self.assert_denied(self.hand_back(message=CAP_REACHED))
        self.assertEqual(self.hand_back(message=CAP_REACHED), (0, ""))

    def test_a_cap_with_a_reviewer_after_the_last_coder_passes(self):
        self.dispatch("review-loop")
        self.dispatch("coder", "a1")
        self.dispatch("code-reviewer", "a1")
        self.assertEqual(self.hand_back(message=CAP_REACHED), (0, ""))

    def test_a_cap_in_no_review_mode_passes(self):
        self.dispatch("review-loop", prompt="scope: branch\nno-review\n")
        self.dispatch("coder", "a1")
        self.assertEqual(self.hand_back(message=CAP_REACHED), (0, ""))

    def test_no_review_mode_dispatch_passes_with_no_reviewer(self):
        self.dispatch("review-loop", prompt="scope: branch\nno-review\n")
        self.dispatch("coder", "a1")
        self.assertEqual(self.hand_back(), (0, ""))
        self.assertFalse(handback_store.latest(SESSION)["handback"]["unreviewed_fix"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_resolved_plan_impact_is_found_after_a_bullet_or_quote_marker(self):
        for line in ("plan_impact: RESOLVED - adopt.", "- plan_impact: RESOLVED - adopt.",
                     "> * plan_impact: RESOLVED - adopt."):
            prompt = f"scope: branch\n{line}\n"
            self.assertIsNotNone(handback_hook.RESOLVED_PLAN_IMPACT.search(prompt), line)
        self.assertIsNone(handback_hook.RESOLVED_PLAN_IMPACT.search("see plan_impact: RESOLVED"))

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

    def test_a_no_review_dispatch_that_never_ran_exempts_no_hand_back(self):
        handback_store.record(SESSION, "dispatch", no_review=True, tool_use_id="toolu_denied")
        self.dispatch("review-loop")
        self.dispatch("coder", "a1")
        self.assert_denied(self.hand_back())

    def test_a_foreground_no_review_loop_passes_before_its_call_is_proven(self):
        # A foreground loop hands back before PostToolUse writes its dispatch-ran row.
        handback_store.record(SESSION, "dispatch", no_review=True, tool_use_id="toolu_foreground")
        self.dispatch("coder", "a1")
        self.assertEqual(self.hand_back(), (0, ""))

    def test_a_foreground_capped_packet_reads_its_own_dispatch_repo_before_its_call_is_proven(self):
        repo, capped = self.capped_packet_on_a_fresh_repo()
        handback_store.record(SESSION, "dispatch", repo=str(repo.resolve()), tool_use_id="toolu_foreground")
        self.dispatch("code-reviewer", "a1")
        self.dispatch("coder", "a1")

        self.assertEqual(self.hand_back(message=capped), (0, ""))

        self.assertTrue(handback_store.latest(SESSION)["handback"]["unreviewed_fix"])

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
        self.assertEqual(self.hand_back(message=packet_text(CONVERGED_FIELDS, iter=2)), (0, ""))
        self.assertTrue(handback_store.latest(SESSION)["handback"]["unreviewed_fix"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_cap_exit_coder_passes_and_the_gate_accepts_it_when_deferred(self):
        self.two_rounds_ending_on_the_cap_exit_coder()
        message = json_packet(status="deferred", iter=2, findings_remaining=[{"finding": "x", "file_line": "a.ts:1"}])
        self.assertEqual(self.hand_back(message=message), (0, ""))
        self.assertTrue(handback_store.latest(SESSION)["handback"]["unreviewed_fix"])
        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_a_nit_fixed_at_the_cap_exit_commits_and_a_blocker_left_over_does_not(self):
        self.two_rounds_ending_on_the_cap_exit_coder()
        blocker_left = json_packet(status="deferred", iter=2,
                                   findings_remaining=[{"finding": "x", "file_line": "a.ts:1", "blocker": "yes"}])
        nit_fixed = json_packet(iter=2, fixed=[{"finding": "reword the error", "file_line": "a.ts:1", "blocker": "no"}],
                                findings_remaining=[])

        self.assert_denied(self.hand_back(message=blocker_left))
        self.assertEqual(self.hand_back(message=nit_fixed), (0, ""))

        self.assertIsNone(handback.false_clean_reason(SESSION))

    def test_a_clean_status_with_a_failed_full_check_is_refused(self):
        leftover = [{"finding": "x", "file_line": "a.ts:1", "blocker": False}]
        for status in handback.CLEAN_STATUSES:
            for full_check in ("failed (3 tests)", "setup fault (exit 2)"):
                with (
                    self.subTest(status=status, full_check=full_check),
                    self.assertRaisesRegex(handback.PacketError, "full_check is"),
                ):
                    handback.load(packet_text(CONVERGED_FIELDS, status=status, findings_remaining=leftover,
                                              full_check=full_check))

    def test_unreviewed_streak_counts_the_latest_flagged_hand_backs_and_a_reviewed_one_ends_it(self):
        self.dispatch("review-loop")
        self.dispatch("coder", "a1")
        self.hand_back("a1")
        self.hand_back("a1")
        self.assertEqual(handback_store.unreviewed_streak(SESSION), 1)

        self.dispatch("review-loop")
        self.dispatch("coder", "a2")
        self.hand_back("a2")
        self.hand_back("a2")
        self.assertEqual(handback_store.unreviewed_streak(SESSION), 2)

        self.dispatch("review-loop")
        self.dispatch("code-reviewer", "a3")
        self.hand_back("a3")
        self.assertEqual(handback_store.unreviewed_streak(SESSION), 0)

    def test_other_agent_types_are_not_steps(self):
        self.dispatch("review-loop")
        self.dispatch("Explore", "a1")
        self.assert_denied(self.hand_back())


def transcript_line(block, record_type="assistant"):
    return {"type": record_type, "message": {"role": record_type, "content": [block]}}


def coder_step(tool_use_id):
    return transcript_line({"type": "tool_use", "id": tool_use_id, "name": "Agent",
                            "input": {"subagent_type": "coder", "prompt": "go"}})


FINDING_ROW = ("~/.claude/skills/review/log-review-finding kind=finding lane=code scope=phase iter=1 "
               "gate=code-reviewer disposition=fix class=bug file=src/orders.ts line=42 actioned=fixed")
METRICS_ROW = "~/.claude/skills/review/log-review-metrics lane=code iter=1 fix=1 ask=0 nit=0 fixed=1 result=PASS"


def ledger_call(tool_use_id, command):
    return transcript_line({"type": "tool_use", "id": tool_use_id, "name": "Bash", "input": {"command": command}})


def refused_logger_result(tool_use_id):
    return transcript_line({"type": "tool_result", "tool_use_id": tool_use_id, "is_error": True,
                            "content": [{"type": "text", "text": "log-review-metrics: failed"}]}, "user")


def review_scope_run(tool_use_id, root):
    """A review-scope call: one record holds the shell call and the ROOT= line it printed."""
    call = {"type": "tool_use", "id": tool_use_id, "name": "Bash",
            "input": {"command": "~/.claude/skills/review/review-scope --base HEAD"}}
    printed = {"type": "tool_result", "tool_use_id": tool_use_id,
               "content": [{"type": "text", "text": f"ROOT={root}\nFILES=a.py"}]}
    return {"type": "assistant", "message": {"role": "assistant", "content": [call, printed]}}


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
        self.dispatch_loop_agents()

    def dispatch_loop_agents(self):
        for agent_type in ("review-loop", "coder", "code-reviewer"):
            self.dispatch(agent_type, None if agent_type == "review-loop" else "a1")

    def loop_repo(self, unchecked=False):
        """A throwaway repo that holds a valid full-check receipt, unless `unchecked`."""
        repo = receipt_repo.make_repo(self)
        if not unchecked:
            receipt_repo.plant_receipt(repo)
        return repo

    def send_hand_back(self, agent_id="a1", message=CONVERGED, cwd=None, unchecked=False):
        event = {"session_id": SESSION, "tool_name": "SubagentHandback", "agent_type": "review-loop",
                 "agent_id": agent_id, "agent_transcript_path": str(self.transcript),
                 "cwd": cwd or self.loop_repo(unchecked), "tool_input": {"message": message}}
        return self.run_cli(["hook", "handback"], json.dumps(event))

    def hand_back(self, steps, agent_id="a1", message=CONVERGED, cwd=None, unchecked=False, ledger=True):
        """Hand back after `steps`. The ledger rows CONVERGED owes (one finding row and a metrics line) follow them
        unless `ledger` is False."""
        if ledger:
            steps = [*steps, ledger_call("tl1", FINDING_ROW), ledger_call("tl2", METRICS_ROW)]
        self.transcript.write_text("".join(json.dumps(step) + "\n" for step in steps), encoding="utf-8")
        _code, out, _err = self.send_hand_back(agent_id, message, cwd, unchecked)
        return out

    def handback_rows(self):
        lines = (self.store / f"{SESSION}.jsonl").read_text(encoding="utf-8").splitlines()
        rows = [json.loads(line) for line in lines]
        return [row for row in rows if row["kind"] == "handback"]

    def test_a_clean_or_cap_reached_hand_back_with_a_code_change_after_the_last_full_check_is_denied(self):
        cap_reached = json.dumps({"status": "cap-reached", "iter": 2,
                                  "findings_remaining": [{"finding": "x", "file_line": "a.ts:1"}]})

        for status, message in (("converged", CONVERGED), ("cap-reached", cap_reached)):
            with self.subTest(status):
                shutil.rmtree(self.store, ignore_errors=True)
                self.dispatch_loop_agents()
                repo = self.loop_repo()
                pathlib.Path(repo, "app.py").write_text("x = 2\n", encoding="utf-8")
                out = self.hand_back([coder_step("t2")], message=message, cwd=repo)

                decision = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertIn("Step 6 execution gate", decision["permissionDecisionReason"])
                self.assertIn("changed after the latest full check", decision["permissionDecisionReason"])
                self.assertEqual(self.handback_rows(), [])

    def test_a_plan_impact_hand_back_with_no_full_check_passes(self):
        message = json.dumps({"status": "plan-impact", "iter": 1, "spec_iter": 0, "plan_impact": "assumed a, found b"})
        metrics = ledger_call("tl1", METRICS_ROW.replace("fixed=1", "fixed=0"))
        out = self.hand_back([coder_step("t2"), metrics], message=message, unchecked=True, ledger=False)
        self.assertEqual(out, "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_hand_back_whose_latest_full_check_verified_nothing_or_never_finished_is_denied(self):
        cases = {"did not verify": {"result": "failed (exit 1)", "satisfied": False},
                 "never finished": {"finish": False}}
        for expected, receipt in cases.items():
            with self.subTest(expected):
                shutil.rmtree(self.store, ignore_errors=True)
                self.dispatch_loop_agents()
                repo = receipt_repo.make_repo(self)
                receipt_repo.plant_receipt(repo, **receipt)

                out = self.hand_back([coder_step("t1")], cwd=repo)

                self.assertIn(expected, json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"])

    def make_repos(self, reviewed_has_receipt, cwd_has_receipt):
        reviewed, other = (self.loop_repo(unchecked=not has) for has in (reviewed_has_receipt, cwd_has_receipt))
        prompt = {"type": "user", "message": {"role": "user", "content": f"review loop\nrepo: {reviewed}"}}
        return prompt, other

    def test_a_hand_back_for_a_reviewed_repo_with_a_receipt_passes_from_another_cwd(self):
        prompt, other = self.make_repos(True, False)

        self.assertEqual(self.hand_back([prompt, coder_step("t2")], cwd=other), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_hand_back_for_a_reviewed_repo_without_a_receipt_is_denied_though_the_cwd_has_one(self):
        prompt, other = self.make_repos(False, True)

        out = self.hand_back([prompt, coder_step("t2")], cwd=other)
        self.assertIn("Step 6 execution gate", json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"])

    def test_a_root_line_in_another_repo_than_the_dispatch_names_one_repo_for_the_gate(self):
        import review_commit_gate

        other = self.loop_repo()
        reviewed = os.path.realpath(self.loop_repo())
        prompt_without_repo_line = {"type": "user", "message": {"role": "user", "content": "review loop\n"}}
        shutil.rmtree(self.store, ignore_errors=True)
        event = {"session_id": SESSION, "cwd": other,
                 "tool_input": {"subagent_type": "review-loop", "prompt": "review loop\n"}}
        self.run_cli(["hook", "dispatch"], json.dumps(event))
        self.dispatch("code-reviewer", "a1")
        self.assertEqual(handback_store.latest(SESSION)["dispatch"]["repo"], os.path.realpath(other))

        steps = [prompt_without_repo_line, review_scope_run("t1", reviewed)]
        self.assertEqual(self.hand_back(steps, cwd=other), "")

        self.assertEqual(handback_store.latest(SESSION)["dispatch"]["repo"], reviewed)
        self.assertTrue(review_commit_gate.review_handed_back_since(SESSION, 0, reviewed))
        self.assertFalse(review_commit_gate.review_handed_back_since(SESSION, 0, os.path.realpath(other)))

    def test_a_root_line_outside_any_work_tree_names_no_repo_for_the_gate(self):
        import review_commit_gate

        other = self.loop_repo()
        outside = self.tmp / "plain-folder"
        outside.mkdir()
        prompt_without_repo_line = {"type": "user", "message": {"role": "user", "content": "review loop\n"}}
        shutil.rmtree(self.store, ignore_errors=True)
        event = {"session_id": SESSION, "cwd": other,
                 "tool_input": {"subagent_type": "review-loop", "prompt": "review loop\n"}}
        self.run_cli(["hook", "dispatch"], json.dumps(event))
        self.dispatch("code-reviewer", "a1")
        self.assertEqual(handback_store.latest(SESSION)["dispatch"]["repo"], os.path.realpath(other))

        steps = [prompt_without_repo_line, review_scope_run("t1", outside)]
        self.assertEqual(self.hand_back(steps, cwd=other), "")

        self.assertIsNone(handback_store.latest(SESSION)["dispatch"]["repo"])
        self.assertFalse(review_commit_gate.review_handed_back_since(SESSION, 0, os.path.realpath(other)))

    def test_a_second_dispatch_of_another_repo_leaves_the_root_line_repo_its_credit_and_gives_itself_none(self):
        import review_commit_gate

        other = self.loop_repo()
        reviewed = os.path.realpath(self.loop_repo())
        prompt_without_repo_line = {"type": "user", "message": {"role": "user", "content": "review loop\n"}}
        shutil.rmtree(self.store, ignore_errors=True)
        event = {"session_id": SESSION, "cwd": other,
                 "tool_input": {"subagent_type": "review-loop", "prompt": "review loop\n"}}
        self.run_cli(["hook", "dispatch"], json.dumps(event))
        self.dispatch("code-reviewer", "a1")

        steps = [prompt_without_repo_line, review_scope_run("t1", reviewed)]
        self.assertEqual(self.hand_back(steps, cwd=other), "")

        second_event = {"session_id": SESSION, "cwd": other,
                        "tool_input": {"subagent_type": "review-loop", "prompt": f"review loop\nrepo: {other}\n"}}
        self.run_cli(["hook", "dispatch"], json.dumps(second_event))
        self.assertEqual(handback_store.latest(SESSION)["dispatch"]["repo"], os.path.realpath(other))
        self.assertTrue(review_commit_gate.review_handed_back_since(SESSION, 0, reviewed))
        self.assertFalse(review_commit_gate.review_handed_back_since(SESSION, 0, os.path.realpath(other)))

    def test_a_clean_hand_back_after_a_full_check_passes(self):
        self.assertEqual(self.hand_back([coder_step("t1")]), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_second_hand_back_on_the_same_unchecked_state_passes(self):
        steps = [coder_step("t2")]
        self.assertIn("deny", self.hand_back(steps, unchecked=True))
        self.assertEqual(self.hand_back(steps, unchecked=True), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_new_code_change_after_a_denial_is_denied_again(self):
        self.assertIn("deny", self.hand_back([coder_step("t2")], unchecked=True))
        self.assertIn("deny", self.hand_back([coder_step("t2"), coder_step("t4")], unchecked=True))

    def test_a_hand_back_while_a_background_reviewer_has_not_reported_is_denied_with_the_wait_reason(self):
        message = json.dumps({"status": "critical-blocker", "iter": 1, "blockers": ["returned before the reviewer"]})
        for agent_id, packet in (("a1", CONVERGED), ("a2", message)):
            with self.subTest(agent_id=agent_id):
                out = self.hand_back([*background_reviewer_launch("t2", "arev")],
                                     agent_id=agent_id, message=packet)

                decision = json.loads(out)["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertIn("background", decision["permissionDecisionReason"])
                self.assertEqual(self.handback_rows(), [])

    def test_a_hand_back_after_the_background_reviewer_reported_passes(self):
        steps = [*background_reviewer_launch("t1", "arev"), task_notification("t1")]

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
                 "cwd": self.loop_repo(unchecked=True), "tool_input": {"message": CONVERGED}}
        self.assertIn("deny", self.run_cli(["hook", "handback"], json.dumps(event))[1])

    def test_a_hand_back_whose_files_touched_names_the_plan_file_is_denied_with_the_plan_edit_reason(self):
        steps = [{"type": "user", "message": {"role": "user", "content": "review loop\nplan: docs/plans/orders.md"}},
                 coder_step("t1")]
        plan_edit = packet_text(CONVERGED_FIELDS, files_touched=["src/orders.ts", "docs/plans/orders.md"])
        cap_reached = json.dumps({"status": "cap-reached", "iter": 2,
                                  "findings_remaining": [{"finding": "x", "file_line": "a.ts:1"}],
                                  "files_touched": ["docs/plans/orders.md"]})

        for status, message in (("converged", plan_edit), ("cap-reached", cap_reached)):
            with self.subTest(status=status):
                out = self.hand_back(steps, message=message)

                reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
                self.assertIn("never edits the plan", reason)
                self.assertEqual(self.handback_rows(), [])

        self.assertEqual(self.hand_back(steps), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_fix_first_hand_back_with_fixed_entries_and_no_finding_rows_is_denied_until_the_rows_are_logged(self):
        prompt = {"type": "user", "message": {"role": "user", "content": "review loop\nmode: fix-first"}}
        steps = [prompt, coder_step("t1")]

        out = self.hand_back(steps, ledger=False)

        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("1 finding(s)", reason)
        self.assertIn("only 0 per-finding row(s)", reason)
        self.assertIn("no metrics line", reason)
        self.assertIn("then return the packet.", reason)
        self.assertEqual(self.handback_rows(), [])

        self.assertEqual(self.hand_back(steps), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_hand_back_with_three_of_five_rows_is_denied_when_the_transcript_repeats_each_call_in_a_blob(self):
        fixed = [{"finding": f"bug {number}", "file_line": f"a.py:{number}", "blocker": False} for number in range(5)]
        message = json.dumps({"status": "converged", "iter": 1, "fixed": fixed, "skipped_fp": [], "ask": []})
        metrics = METRICS_ROW.replace("fix=1", "fix=5").replace("fixed=1", "fixed=5")
        logged_calls = [ledger_call("tl1", FINDING_ROW), ledger_call("tl2", FINDING_ROW),
                        ledger_call("tl3", FINDING_ROW), ledger_call("tl4", metrics)]
        blob_copies = [{**call, "type": "api-request-blob"} for call in logged_calls]

        out = self.hand_back([*logged_calls, *blob_copies], message=message, ledger=False)

        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("5 finding(s)", reason)
        self.assertIn("only 3 per-finding row(s)", reason)

    def test_a_hand_back_that_dispatched_no_reviewer_and_logged_only_a_not_dispatched_metrics_line_passes(self):
        not_dispatched = ('~/.claude/skills/review/log-review-metrics lane=code iter=1 fix=0 ask=0 nit=0 fixed=0 '
                          'result="NOT DISPATCHED"')
        fix_first = {"type": "user", "message": {"role": "user", "content": "review loop\nmode: fix-first"}}
        cases = {
            "setup-fault": (json_packet(status="setup-fault", blockers=["no test runner installed"]), [], ""),
            "critical-blocker": (json_packet(status="critical-blocker", blockers=["migration drops a column"]), [], ""),
            "fix-first plan-impact": (json_packet(status="plan-impact", spec_iter=0,
                                                  plan_impact="assumed a, found b"), [fix_first], ""),
            "no-review converged": (json_packet(skipped_fp=[], ask=[], nit=[], findings_remaining=[]),
                                    [coder_step("t1")], "no-review"),
        }

        no_receipt_cases = {"setup-fault", "critical-blocker"}

        for name, (message, steps, loop_prompt) in cases.items():
            with self.subTest(name):
                shutil.rmtree(self.store, ignore_errors=True)
                self.dispatch("review-loop", prompt=loop_prompt)
                self.dispatch("coder", "a1")
                out = self.hand_back([*steps, ledger_call("tl1", not_dispatched)], message=message, ledger=False,
                                     unchecked=name in no_receipt_cases)

                self.assertEqual(out, "")
                self.assertEqual(len(self.handback_rows()), 1)

    def test_a_converged_hand_back_with_no_coder_step_and_no_full_check_is_still_denied(self):
        message = json_packet(skipped_fp=[], ask=[], nit=[], findings_remaining=[])
        not_dispatched = ('~/.claude/skills/review/log-review-metrics lane=code iter=1 fix=0 ask=0 nit=0 fixed=0 '
                          'result="NOT DISPATCHED"')
        self.dispatch("review-loop", prompt="")

        out = self.hand_back([ledger_call("tl1", not_dispatched)], message=message, ledger=False, unchecked=True)

        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("No valid full-check receipt exists", reason)

    def test_a_hand_back_whose_metrics_call_failed_is_denied_once_and_the_second_passes(self):
        steps = [coder_step("t1"), ledger_call("tl1", FINDING_ROW),
                 ledger_call("tl2", METRICS_ROW), refused_logger_result("tl2")]

        first = self.hand_back(steps, ledger=False)

        reason = json.loads(first)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn('result="NOT DISPATCHED"', reason)
        self.assertEqual(self.handback_rows(), [])

        self.assertEqual(self.hand_back(steps, ledger=False), "")
        self.assertEqual(len(self.handback_rows()), 1)

    def test_a_hand_back_is_denied_again_when_the_loop_made_another_logger_call_that_also_failed(self):
        steps = [coder_step("t1"), ledger_call("tl1", FINDING_ROW),
                 ledger_call("tl2", METRICS_ROW), refused_logger_result("tl2")]
        self.hand_back(steps, ledger=False)

        retry = [*steps, ledger_call("tl3", METRICS_ROW), refused_logger_result("tl3")]
        out = self.hand_back(retry, ledger=False)

        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("no metrics line", reason)
        self.assertEqual(self.handback_rows(), [])

    def test_a_hand_back_whose_metrics_line_has_other_counts_than_the_packet_is_denied(self):
        steps = [coder_step("t1"), ledger_call("tl1", FINDING_ROW),
                 ledger_call("tl2", METRICS_ROW.replace("fixed=1", "fixed=0"))]

        out = self.hand_back(steps, ledger=False)

        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("fixed=1, skipped_fp=0", reason)

    def test_a_failed_full_check_scan_skips_only_the_full_check_gate_and_the_plan_edit_gate_still_denies(self):
        steps = [{"type": "user", "message": {"role": "user", "content": "review loop\nplan: docs/plans/orders.md"}},
                 coder_step("t1")]
        self.transcript.write_text("".join(json.dumps(step) + "\n" for step in steps), encoding="utf-8")
        event = {"agent_transcript_path": str(self.transcript), "cwd": str(self.tmp)}
        packet = {"status": "converged", "files_touched": ["src/orders.ts", "docs/plans/orders.md"]}

        with unittest.mock.patch.object(handback_hook.loop_transcript, "scan", side_effect=RuntimeError("boom")), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            reason = handback_hook.transcript_gate_reason(event, SESSION, "a1", CONVERGED, packet)

        self.assertEqual(reason, handback_hook.loop_transcript.PLAN_EDIT_REASON.format(plan="docs/plans/orders.md"))
        self.assertIn("full-check gate skipped", stderr.getvalue())

    def test_a_second_hand_back_from_an_agent_with_a_stored_report_is_denied_and_adds_no_row(self):
        steps = [coder_step("t1")]
        self.assertEqual(self.hand_back(steps), "")
        out = self.hand_back(steps)
        decision = json.loads(out)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("SendMessage", decision["permissionDecisionReason"])
        self.assertEqual(len(self.handback_rows()), 1)


class NoStoreReExportTest(unittest.TestCase):
    def test_every_script_reads_only_names_handback_defines(self):
        handback_tree = ast.parse(SCRIPT.read_text())
        defined = set()
        for node in handback_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                defined.update(t.id for t in node.targets if isinstance(t, ast.Name))
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                defined.add(node.target.id)
            elif isinstance(node, ast.Import):
                defined.update((alias.asname or alias.name).split(".")[0] for alias in node.names)
        missing = []
        for path in sorted(toolkit_paths.SCRIPTS_DIR.rglob("*.py")):
            source = path.read_text()
            tree = ast.parse(source)
            # An `import handback` binds the name only in its own function, where other functions may use
            # `handback` for a plain dict; an unindented one binds it for the whole file.
            scopes = [(tree, {"handback"} if re.search(r"^import handback$", source, re.MULTILINE) else set())]
            for function in ast.walk(tree):
                if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                imports_handback = any(
                    isinstance(inner, ast.Import) and any(alias.name == "handback" for alias in inner.names)
                    for inner in ast.walk(function)
                )
                if imports_handback:
                    scopes.append((function, {"handback"}))
                # The code-step verbs pass the load_handback() module on as a parameter named `module`.
                takes_handback_module = path.name.startswith("code_step") and any(
                    argument.arg == "module" for argument in function.args.args)
                if takes_handback_module:
                    scopes.append((function, {"module"}))
            if "= load_handback()" in source:
                scopes.append((tree, {"module"}))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module == "handback":
                    missing.extend(f"{path.name}:{node.lineno} from handback import {alias.name}"
                                   for alias in node.names if alias.name not in defined)
            for scope, handback_aliases in scopes:
                for node in ast.walk(scope):
                    is_handback_read = (
                        isinstance(node, ast.Attribute)
                        and isinstance(node.value, ast.Name)
                        and node.value.id in handback_aliases
                    )
                    if is_handback_read and node.attr not in defined:
                        missing.append(f"{path.name}:{node.lineno} {node.value.id}.{node.attr}")
        self.assertEqual([], missing)


if __name__ == "__main__":
    unittest.main()
