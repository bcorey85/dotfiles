"""A relayed ask outcome (`--by user --relayed-by <name>`) on `review_fix.py asks-done` and `phase_asks.py rule`:
checked in process against the relaying session's transcript, with no row or plan line holding the user's words."""
import json
import os
import sys
import time
import unittest
import unittest.mock
from datetime import datetime, timezone

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import approval_asks_store
import handback_store
import human_turn_lookup
import review_fix_names
import ruling_relay
import script_utils
import test_phase_asks as phase_fixture  # the module, never its class: a class imported by name reruns its tests
import test_review_fix_script as fix_fixture
from human_turn_lookup import HumanTurnRefusedError
from review_fix_names import FILED_AT_KEY

RELAY_NAME = "relay-session"
RELAY_SESSION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
TYPED = "approve the CLAUDE.md edit"
USER_ONLY_PATH = "CLAUDE.md"
USER_ONLY_ID = "a1b2c3d4e5f60051"
ORDINARY_ID = "a1b2c3d4e5f60052"


def iso(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class RelayTranscriptMixin:
    """A fake `~/.claude` holding one live session row and its transcript. `home` is where both are written."""

    def make_home(self):
        self.claude_home = self.temp_root / "fake-home" / ".claude"
        (self.claude_home / "sessions").mkdir(parents=True)
        (self.claude_home / "projects" / "-elsewhere").mkdir(parents=True)
        row = {"pid": os.getpid(), "name": RELAY_NAME, "sessionId": RELAY_SESSION_ID}
        (self.claude_home / "sessions" / "1.json").write_text(json.dumps(row))
        self.home_env = {"HOME": str(self.claude_home.parent), "CLAUDE_CONFIG_DIR": str(self.claude_home)}

    def say(self, content, origin=None, when=None, **extra):
        """Appends a user row to the relaying session's transcript; `when` defaults to an hour from now."""
        row = {"type": "user", "message": {"role": "user", "content": content},
               "timestamp": iso(time.time() + 3600 if when is None else when)}
        if origin is not None:
            row["origin"] = origin
        row.update(extra)
        transcript = self.claude_home / "projects" / "-elsewhere" / f"{RELAY_SESSION_ID}.jsonl"
        with transcript.open("a") as handle:
            handle.write(json.dumps(row) + "\n")


HUMAN = {"kind": "human"}


class RelayOptionsTest(unittest.TestCase):
    def test_the_relayed_by_option_is_popped_into_a_request(self):
        rest, request = ruling_relay.pop_relay_options(["--relayed-by", "a", "accepted"])
        self.assertEqual(rest, ["accepted"])
        self.assertEqual(request, ruling_relay.RelayRequest("a"))

    def test_no_option_is_no_request(self):
        self.assertEqual(ruling_relay.pop_relay_options(["accepted"]), (["accepted"], None))

    def test_an_empty_session_name_or_the_retired_quote_option_is_refused(self):
        with self.assertRaises(HumanTurnRefusedError):
            ruling_relay.pop_relay_options(["--relayed-by", "", "accepted"])
        with self.assertRaises(HumanTurnRefusedError) as caught:
            ruling_relay.pop_relay_options(["--relayed-by", "a", "--quote", "words", "accepted"])
        self.assertIn("retired", str(caught.exception))

    def test_a_relay_under_by_session_is_refused(self):
        request = ruling_relay.RelayRequest("a")
        with self.assertRaises(HumanTurnRefusedError):
            ruling_relay.refuse_relay_without_user(request, "session")
        ruling_relay.refuse_relay_without_user(request, "user")

    def test_the_latest_filed_time_is_taken_from_the_user_only_asks_alone(self):
        asks = [{"user_only": True, FILED_AT_KEY: 5}, {FILED_AT_KEY: 99},
                {"user_only": True, FILED_AT_KEY: 7}]
        self.assertEqual(ruling_relay.latest_filed_at(asks), 7)

    def test_a_batch_with_no_user_only_ask_or_a_user_only_ask_without_a_filed_time_is_refused(self):
        with self.assertRaises(HumanTurnRefusedError):
            ruling_relay.latest_filed_at([{FILED_AT_KEY: 1}])
        with self.assertRaises(HumanTurnRefusedError):
            ruling_relay.latest_filed_at([{"user_only": True}])


class UnstampedAskRefusalTest(unittest.TestCase):
    def test_the_refusal_for_an_ask_with_no_filed_time_names_the_recovery(self):
        with self.assertRaises(HumanTurnRefusedError) as caught:
            ruling_relay.latest_filed_at([{"user_only": True}])
        self.assertIn("no filed time", str(caught.exception))
        self.assertIn("--by user from the user's own session", str(caught.exception))


class RecordRelayGuardTest(unittest.TestCase):
    def test_asks_with_no_user_only_ask_record_no_relay_row(self):
        relayed = ruling_relay.RelayedRuling("a",
                                             human_turn_lookup.HumanTurn("2026-11-15T06:22:12.305Z", 1.0))
        with unittest.mock.patch.object(handback_store, "record_relayed_ruling") as record:
            recorded = ruling_relay.record_relay("session-id", "/repo", relayed, [{"finding_id": "f1"}])
        self.assertIsNone(recorded)
        record.assert_not_called()


class AsksDoneRelayCase(RelayTranscriptMixin, unittest.TestCase):
    """The asks-done fixture: a packet of `entries()` and the saved approval paths. Holds no test."""
    stop_launched_loops = fix_fixture.ReviewFixScriptTest.stop_launched_loops
    fake_command = fix_fixture.ReviewFixScriptTest.fake_command
    environment = fix_fixture.ReviewFixScriptTest.environment
    git = fix_fixture.ReviewFixScriptTest.git
    run_script = fix_fixture.ReviewFixScriptTest.run_script
    packet = fix_fixture.ReviewFixScriptTest.packet
    ledger_writes = fix_fixture.ReviewFixScriptTest.ledger_writes

    def setUp(self):
        fix_fixture.ReviewFixScriptTest.setUp(self)
        self.make_home()
        self.packet_message = fix_fixture.packet_text(fix_fixture.CLEAN_EMPTY_FIELDS, ask=self.entries())
        self.packet(self.packet_message)
        approval_asks_store.write_saved_asks(self.repo, {USER_ONLY_PATH: None, "AGENTS.md": None}, [])

    def entries(self):
        return [self.user_only_entry()]

    def relay(self, *outcome_words, name=RELAY_NAME, by="user", **env):
        return self.run_script(["asks-done", "--by", by, "--relayed-by", name, *outcome_words],
                               **self.home_env, **env)

    def user_only_entry(self):
        entry = fix_fixture.ask_entry("edit", f"{USER_ONLY_PATH}:1", finding_id=USER_ONLY_ID, question="approve?",
                                      change=approval_asks_store.approval_change(USER_ONLY_PATH))
        return {**entry, "user_only": True}

    def ordinary_entry(self):
        return fix_fixture.ask_entry("cap", "src/a.ts:1", finding_id=ORDINARY_ID)

    def saved_paths(self):
        return list(approval_asks_store.read_approval_paths(self.repo))

    def relay_rows(self):
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store_dir)}):
            return handback_store.session_rows(fix_fixture.SESSION, handback_store.ASK_RULING_RELAYED)

    def assert_refused_with_nothing_changed(self, code, output, *needles):
        self.assertEqual(code, 2, output)
        for needle in needles:
            self.assertIn(needle, output)
        self.assertEqual(self.saved_paths(), [USER_ONLY_PATH, "AGENTS.md"])
        self.assertEqual(self.logged_outcome_rows(), [])
        self.assertEqual(self.relay_rows(), [])

    def correct_relay(self, *outcome_words):
        return self.run_script(["asks-done", "--correct", "--by", "user", "--relayed-by", RELAY_NAME,
                                *outcome_words], **self.home_env)

    def logged_outcome_rows(self):
        return [row for row in self.ledger_writes() if "ask_outcome" in row]


class AsksDoneMixedBatchTest(AsksDoneRelayCase):
    def entries(self):
        return [self.user_only_entry(), self.ordinary_entry()]

    def test_a_relay_credits_every_ask_to_the_user_and_records_only_the_user_only_finding(self):
        self.say(TYPED, HUMAN)

        code, output = self.relay("accepted", "accepted")

        self.assertEqual(code, 0, output)
        self.assertEqual([row["ask_decided_by"] for row in self.logged_outcome_rows()], ["user", "user"])
        self.assertEqual(self.relay_rows()[0]["finding_ids"], [USER_ONLY_ID])

    def test_a_relay_by_the_id_of_one_of_two_same_named_rows_records_the_row_name(self):
        other_row = {"pid": os.getpid(), "name": RELAY_NAME, "sessionId": "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"}
        (self.claude_home / "sessions" / "2.json").write_text(json.dumps(other_row))
        self.say(TYPED, HUMAN)

        code, output = self.relay("accepted", "accepted", name=RELAY_NAME)
        self.assertEqual(code, 2, output)
        self.assertIn("--relayed-by <sessionId>", output)
        self.assertEqual(self.relay_rows(), [])

        code, output = self.relay("accepted", "accepted", name=RELAY_SESSION_ID)
        self.assertEqual(code, 0, output)
        self.assertEqual([row["relayed_by"] for row in self.relay_rows()], [RELAY_NAME])

    def test_a_relayed_correct_records_only_the_corrected_user_only_finding(self):
        code, output = self.run_script(
            ["asks-done", "--by", "user", f"modified:tighten the check in {USER_ONLY_PATH}", "accepted"],
            **self.home_env)
        self.assertEqual(code, 0, output)
        self.say(TYPED, HUMAN)

        code, output = self.correct_relay("rejected:the user changed their mind", "accepted")

        self.assertEqual(code, 0, output)
        relayed = self.relay_rows()
        self.assertEqual([row["finding_ids"] for row in relayed], [[USER_ONLY_ID]])
        self.assertEqual(relayed[0]["relayed_by"], RELAY_NAME)
        self.assertNotIn(TYPED, json.dumps(relayed))
        corrected = self.logged_outcome_rows()[-1]
        self.assertEqual((corrected["ask_outcome"], corrected["ask_decided_by"]), ("rejected", "user"))

    def test_a_failed_ordinary_row_does_not_hold_back_the_relay_of_the_logged_user_only_ask(self):
        self.say(TYPED, HUMAN)

        # The user-only row is write call 1 and the ordinary row is call 2.
        code, output = self.run_script(
            ["asks-done", "--by", "user", "--relayed-by", RELAY_NAME, "accepted", "accepted"],
            FAKE_LEDGER_FAIL_WRITE_CALL="2", **self.home_env)

        self.assertEqual(code, 0, output)
        self.assertIn("Failures", output)
        self.assertEqual([row["finding_ids"] for row in self.relay_rows()], [[USER_ONLY_ID]])

    def test_a_relayed_correct_whose_ordinary_row_fails_still_records_the_user_only_finding(self):
        code, output = self.run_script(
            ["asks-done", "--by", "user", f"modified:tighten the check in {USER_ONLY_PATH}", "accepted"],
            **self.home_env)
        self.assertEqual(code, 0, output)
        self.say(TYPED, HUMAN)

        # The correction writes the user-only row first and the ordinary row second.
        first_run_writes = len(self.ledger_writes())
        ordinary_write_call = first_run_writes + 2
        code, output = self.run_script(
            ["asks-done", "--correct", "--by", "user", "--relayed-by", RELAY_NAME,
             "rejected:changed my mind", "rejected:changed my mind"],
            FAKE_LEDGER_FAIL_WRITE_CALL=str(ordinary_write_call), **self.home_env)

        self.assertEqual(code, 2, output)
        self.assertIn("did not log", output)
        self.assertEqual([row["finding_ids"] for row in self.relay_rows()], [[USER_ONLY_ID]])

    def test_a_failed_user_only_row_records_no_relay(self):
        self.say(TYPED, HUMAN)

        # The user-only row is write call 1: it fails, so no user-only ask is logged to relay.
        code, output = self.run_script(
            ["asks-done", "--by", "user", "--relayed-by", RELAY_NAME, "accepted", "accepted"],
            FAKE_LEDGER_FAIL_WRITE_CALL="1", **self.home_env)

        self.assertIn("Failures", output, f"exit {code}")
        self.assertEqual(self.relay_rows(), [])

    def test_a_correction_whose_user_only_row_fails_records_no_relay(self):
        code, output = self.run_script(["asks-done", "--by", "user", "accepted", "accepted"], **self.home_env)
        self.assertEqual(code, 0, output)
        self.say(TYPED, HUMAN)

        # The correction writes the user-only row first.
        user_only_write_call = len(self.ledger_writes()) + 1
        code, output = self.run_script(
            ["asks-done", "--correct", "--by", "user", "--relayed-by", RELAY_NAME,
             "rejected:changed my mind", "accepted"],
            FAKE_LEDGER_FAIL_WRITE_CALL=str(user_only_write_call), **self.home_env)

        self.assertEqual(code, 2, f"exit {code}: {output}")
        self.assertEqual(self.relay_rows(), [])

    def test_a_retry_after_a_failed_row_and_a_packet_rerun_records_each_relay_once(self):
        self.say(TYPED, HUMAN)
        code, output = self.run_script(
            ["asks-done", "--by", "user", "--relayed-by", RELAY_NAME, "accepted", "accepted"],
            FAKE_LEDGER_FAIL_WRITE_CALL="2", **self.home_env)
        self.assertEqual(code, 0, output)
        self.assertEqual(len(self.relay_rows()), 1)

        self.packet(self.packet_message)
        code, output = self.relay("accepted", "accepted")

        self.assertEqual(code, 0, output)
        self.assertEqual([row["finding_ids"] for row in self.relay_rows()], [[USER_ONLY_ID]])


class AsksDoneEarlierCallWithoutRelayTest(AsksDoneRelayCase):
    def entries(self):
        return [self.user_only_entry(), self.ordinary_entry()]

    def test_a_retry_with_a_relay_does_not_credit_a_user_only_ask_an_earlier_call_logged(self):
        self.say(TYPED, HUMAN)

        # The user-only row is write call 1 and logs; the ordinary row is call 2 and fails.
        code, output = self.run_script(["asks-done", "--by", "user", "accepted", "accepted"],
                                       FAKE_LEDGER_FAIL_WRITE_CALL="2", **self.home_env)
        self.assertEqual(code, 0, output)
        self.assertIn("Failures", output)
        self.assertEqual(self.relay_rows(), [])

        code, output = self.relay("accepted", "accepted")

        self.assertEqual(code, 0, output)
        self.assertEqual(self.relay_rows(), [])


class AsksDoneRepeatedPacketTest(AsksDoneRelayCase):
    def test_a_turn_typed_between_two_packet_runs_still_rules_the_asks(self):
        # Turn times have whole-second precision: the gap keeps the turn after the first filing.
        time.sleep(1.1)
        self.say(TYPED, HUMAN, when=time.time())

        self.packet(self.packet_message)
        code, output = self.relay("accepted")

        self.assertEqual(code, 0, output)
        self.assertEqual(len(self.relay_rows()), 1)

    def test_a_turn_typed_between_two_packet_runs_is_accepted_whatever_the_second_run_time(self):
        time.sleep(1.1)
        self.say(TYPED, HUMAN, when=time.time())
        time.sleep(1.1)

        code, output = self.packet(self.packet_message)
        self.assertEqual(code, 0, output)
        code, output = self.relay("accepted")

        self.assertEqual(code, 0, output)
        self.assertEqual(len(self.relay_rows()), 1)


class AsksDoneOrdinaryBatchTest(AsksDoneRelayCase):
    def entries(self):
        return [self.ordinary_entry()]

    def test_a_relay_on_a_batch_with_no_user_only_ask_is_refused(self):
        self.say(TYPED, HUMAN)

        code, output = self.relay("accepted")

        self.assertEqual(code, 2, output)
        self.assertIn("no ask of this batch is user_only", output)
        self.assertEqual(self.logged_outcome_rows(), [])
        self.assertEqual(self.relay_rows(), [])


class AsksDoneUnstampedAskTest(AsksDoneRelayCase):
    """Asks saved before filed times were stamped: the bound is the saved state's modification time."""

    def save_state_without_filed_times(self):
        review_fix_folder = script_utils.git_path(self.repo, review_fix_names.REVIEW_FIX_FOLDER)
        state_file = review_fix_folder / review_fix_names.STATE_FILE_NAME
        saved = json.loads(state_file.read_text())
        for item in saved["asks"]:
            item.pop(FILED_AT_KEY, None)
        state_file.write_text(json.dumps(saved))
        self.assertNotIn(FILED_AT_KEY, state_file.read_text())
        return state_file

    def test_a_turn_after_the_state_was_written_rules_an_ask_with_no_filed_time(self):
        state_file = self.save_state_without_filed_times()
        os.utime(state_file, (time.time() - 7200, time.time() - 7200))
        self.say(TYPED, HUMAN, when=time.time() - 3600)

        code, output = self.relay("accepted")

        self.assertEqual(code, 0, output)
        self.assertEqual(len(self.relay_rows()), 1)

    def test_a_turn_before_the_state_was_written_is_refused_as_older_than_the_ask(self):
        self.save_state_without_filed_times()
        self.say(TYPED, HUMAN, when=time.time() - 3600)

        code, output = self.relay("accepted")

        self.assert_refused_with_nothing_changed(code, output, "older than the ask")


class AsksDoneRelayTest(AsksDoneRelayCase):
    def test_a_human_turn_credits_the_user_clears_the_path_and_records_the_relay(self):
        self.say(TYPED, HUMAN)

        code, output = self.relay("accepted")

        self.assertEqual(code, 0, output)
        self.assertEqual(self.saved_paths(), ["AGENTS.md"])
        outcome_rows = self.logged_outcome_rows()
        self.assertEqual([(row["ask_outcome"], row["ask_decided_by"]) for row in outcome_rows], [("accepted", "user")])
        relayed = self.relay_rows()
        self.assertEqual(len(relayed), 1)
        self.assertEqual((relayed[0]["relayed_by"], relayed[0]["ruler"]), (RELAY_NAME, "user"))
        self.assertIn("turn_ts", relayed[0])
        self.assertNotIn(TYPED, json.dumps(relayed))
        self.assertEqual(relayed[0]["finding_ids"], ["a1b2c3d4e5f60051"])

    def test_a_retry_after_a_logging_failure_records_the_relay_once(self):
        self.say(TYPED, HUMAN)

        code, output = self.relay("accepted", FAKE_LEDGER_WRITE_EXIT="2")
        self.assertEqual(code, 0, output)
        self.assertIn("Failures", output)
        code, output = self.relay("accepted")

        self.assertEqual(code, 0, output)
        self.assertEqual(len(self.relay_rows()), 1)

    def test_a_relayed_correct_with_no_human_turn_is_refused_and_logs_nothing(self):
        code, output = self.run_script(["asks-done", "--by", "user", f"modified:tighten the check in {USER_ONLY_PATH}"],
                                       **self.home_env)
        self.assertEqual(code, 0, output)
        rows_before = self.logged_outcome_rows()
        self.say(TYPED, {"kind": "peer", "from": "orchestrator"})

        code, output = self.correct_relay("rejected:changed my mind")

        self.assertEqual(code, 2, output)
        self.assertIn("relayed ruling refused", output)
        self.assertEqual(self.logged_outcome_rows(), rows_before)
        self.assertEqual(self.relay_rows(), [])

    def test_a_relaying_session_with_only_a_peer_message_is_refused(self):
        self.say(TYPED, {"kind": "peer", "from": "orchestrator"})
        code, output = self.relay("accepted")
        self.assert_refused_with_nothing_changed(code, output, "relayed ruling refused", "no human turn")

    def test_a_turn_typed_before_the_ask_was_filed_is_refused(self):
        self.say(TYPED, HUMAN, when=time.time() - 3600)
        code, output = self.relay("accepted")
        self.assert_refused_with_nothing_changed(code, output, "older than the ask")

    def test_an_unknown_session_name_is_refused(self):
        self.say(TYPED, HUMAN)
        code, output = self.relay("accepted", name="nobody")
        self.assert_refused_with_nothing_changed(code, output, "no live session has the id or the name")

    def test_a_relay_under_by_session_is_refused(self):
        self.say(TYPED, HUMAN)
        code, output = self.relay("accepted", by="session")
        self.assert_refused_with_nothing_changed(code, output, "--by user")

    def test_the_retired_quote_option_is_refused(self):
        self.say(TYPED, HUMAN)
        code, output = self.run_script(["asks-done", "--by", "user", "--relayed-by", RELAY_NAME, "--quote", TYPED,
                                        "accepted"], **self.home_env)
        self.assert_refused_with_nothing_changed(code, output, "--quote is retired")

    def test_a_session_ruling_with_no_relay_on_a_user_only_ask_is_still_refused(self):
        code, output = self.run_script(["asks-done", "--by", "session", "accepted"], **self.home_env)
        self.assert_refused_with_nothing_changed(code, output, "only the user rules them")


class PhaseRuleRelayTest(RelayTranscriptMixin, phase_fixture.ScriptRunCase):
    def setUp(self):
        super().setUp()
        self.make_home()
        # Rules the fixture's own open asks, so the user-only ask opened below is the only one left to rule.
        self.run_script("rule", "accepted:a", "rejected:b")
        open_ask = phase_fixture.user_only_ask(USER_ONLY_PATH, "7ee295856f1a9fff", 1)
        open_ask["change"] = approval_asks_store.approval_change(USER_ONLY_PATH)
        handback_store.record_phase_asks_open(phase_fixture.SESSION, self.repo_top, [open_ask], phase_fixture.CONTEXT,
                                              "loop-r:6")
        approval_asks_store.write_saved_asks(self.repo_top, {USER_ONLY_PATH: None, "AGENTS.md": None}, [])
        self.rows_before = self.outcome_rows()

    def relay(self, *outcome_words, name=RELAY_NAME, by="user", **env):
        return self.run_script("rule", "--by", by, "--relayed-by", name, *outcome_words,
                               **self.home_env, **env)

    def test_an_ask_whose_outcome_row_did_not_log_leaves_no_relay_row(self):
        self.say(TYPED, HUMAN)

        code, _, error = self.relay("accepted:the user agreed", FAKE_LEDGER_WRITE_EXIT="2")

        self.assertEqual(code, 0, error)
        self.assertEqual(self.store_rows(handback_store.ASK_RULING_RELAYED), [])

    def test_a_human_turn_credits_the_user_clears_the_path_and_records_the_relay(self):
        self.say(TYPED, HUMAN)

        code, _, error = self.relay("accepted:the user agreed")

        self.assertEqual(code, 0, error)
        self.assertEqual(list(approval_asks_store.read_approval_paths(self.repo_top)), ["AGENTS.md"])
        row = self.outcome_rows()[-1]
        self.assertEqual((row["ask_outcome"], row["ask_decided_by"]), ("accepted", "user"))
        relayed = self.store_rows(handback_store.ASK_RULING_RELAYED)
        self.assertEqual([item["relayed_by"] for item in relayed], [RELAY_NAME])
        self.assertNotIn(TYPED, json.dumps(relayed))
        self.assertEqual(relayed[0]["finding_ids"], ["7ee295856f1a9fff"])

    def test_a_turn_typed_after_the_ask_was_filed_but_before_the_call_is_accepted(self):
        # Turn times have whole-second precision: the gap keeps the turn after the filing.
        time.sleep(1.1)
        self.say(TYPED, HUMAN, when=time.time())

        code, _, error = self.relay("accepted:the user agreed")

        self.assertEqual(code, 0, error)

    def test_a_relay_credits_the_user_only_ask_to_the_user_and_the_other_to_the_session(self):
        code, _, error = self.run_script("rule", "--by", "user", "accepted:the user agreed")
        self.assertEqual(code, 0, error)
        mixed_asks = [phase_fixture.user_only_ask(USER_ONLY_PATH, "7ee295856f1a9fff", 1),
                      phase_fixture.ask("Should the cap be 3?", "7ee295856f1a9ffe", 9)]
        handback_store.record_phase_asks_open(phase_fixture.SESSION, self.repo_top, mixed_asks,
                                              phase_fixture.CONTEXT, "loop-r:7")
        self.say(TYPED, HUMAN)
        rows_before = len(self.outcome_rows())

        code, _, error = self.relay("accepted:the user agreed", "accepted:fine")

        self.assertEqual(code, 0, error)
        ruled = self.outcome_rows()[rows_before:]
        self.assertEqual([row["ask_decided_by"] for row in ruled], ["user", "session"])
        relayed = self.store_rows(handback_store.ASK_RULING_RELAYED)
        self.assertEqual([item["finding_ids"] for item in relayed], [["7ee295856f1a9fff"]])

    def test_a_relaying_session_with_no_human_turn_is_refused_and_logs_nothing(self):
        self.say(TYPED, {"kind": "peer", "from": "orchestrator"})

        code, _, error = self.relay("accepted")

        self.assertEqual(code, 2)
        self.assertIn("relayed ruling refused", error)
        self.assertEqual(self.outcome_rows(), self.rows_before)
        self.assertEqual(self.store_rows(handback_store.ASK_RULING_RELAYED), [])
        self.assertIsNotNone(handback_store.unruled_phase_asks(self.repo_top))
        self.assertEqual(list(approval_asks_store.read_approval_paths(self.repo_top)), [USER_ONLY_PATH, "AGENTS.md"])

    def test_a_relay_on_a_batch_with_no_user_only_ask_is_refused_and_logs_nothing(self):
        code, _, error = self.run_script("rule", "--by", "user", "accepted:the user agreed")
        self.assertEqual(code, 0, error)
        handback_store.record_phase_asks_open(phase_fixture.SESSION, self.repo_top,
                                              [phase_fixture.ask("Should the cap be 3?", "7ee295856f1a9ffe", 9)],
                                              phase_fixture.CONTEXT, "loop-r:7")
        self.say(TYPED, HUMAN)
        rows_before = self.outcome_rows()

        code, _, error = self.relay("accepted")

        self.assertEqual(code, 2)
        self.assertIn("no ask of this batch is user_only", error)
        self.assertEqual(self.outcome_rows(), rows_before)
        self.assertEqual(self.store_rows(handback_store.ASK_RULING_RELAYED), [])

    def test_a_turn_typed_before_the_ask_opened_is_refused(self):
        self.say(TYPED, HUMAN, when=time.time() - 3600)

        code, _, error = self.relay("accepted")

        self.assertEqual(code, 2)
        self.assertIn("older than the ask", error)
        self.assertEqual(self.outcome_rows(), self.rows_before)

    def test_a_relay_under_by_session_is_refused(self):
        self.say(TYPED, HUMAN)

        code, _, error = self.relay("accepted", by="session")

        self.assertEqual(code, 2)
        self.assertEqual(self.outcome_rows(), self.rows_before)
        self.assertIn("--by takes only", error)


class DecideRelayTest(RelayTranscriptMixin, unittest.TestCase):
    """`review_fix.py decide` against a plan the user owns: a relayed user ruling backed by a user turn passes, a
    bare `--by session` call is refused."""
    stop_launched_loops = fix_fixture.ReviewFixScriptTest.stop_launched_loops
    fake_command = fix_fixture.ReviewFixScriptTest.fake_command
    environment = fix_fixture.ReviewFixScriptTest.environment
    git = fix_fixture.ReviewFixScriptTest.git
    run_script = fix_fixture.ReviewFixScriptTest.run_script
    false_clean_reason = fix_fixture.ReviewFixScriptTest.false_clean_reason
    plant_held_hand_back = fix_fixture.ReviewFixScriptTest.plant_held_hand_back

    def setUp(self):
        fix_fixture.ReviewFixScriptTest.setUp(self)
        self.make_home()
        self.plant_held_hand_back()
        self.user_plan = self.temp_root / "plan.md"
        self.user_plan.write_text("# Plan\n")

    def decide(self, by="user", relay=True, relayed_by=RELAY_NAME):
        relay_words = ["--relayed-by", relayed_by] if relay else []
        return self.run_script(["decide", "keep", "--by", by, *relay_words, "--ruling", "keep the retry",
                                "--plan", str(self.user_plan)], **self.home_env)

    def relay_rows(self):
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store_dir)}):
            return handback_store.session_rows(fix_fixture.SESSION, handback_store.PLAN_RULING_RELAYED)

    def assert_refused_with_nothing_logged(self, code, output, needle):
        self.assertEqual(code, 2, output)
        self.assertIn(needle, output)
        self.assertEqual(self.user_plan.read_text(), "# Plan\n")
        self.assertEqual(self.relay_rows(), [])
        self.assertIsNotNone(self.false_clean_reason())

    def test_a_relayed_user_ruling_on_a_user_owned_plan_is_logged_with_the_relayer_and_no_user_words(self):
        self.say(TYPED, HUMAN)

        code, output = self.decide()

        self.assertEqual(code, 0, output)
        plan_text = self.user_plan.read_text()
        self.assertIn(f"relayed by session {RELAY_NAME}", plan_text)
        self.assertIn("(user turn at ", plan_text)
        self.assertNotIn(TYPED, plan_text)
        self.assertIsNone(self.false_clean_reason())
        rows = self.relay_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["ruler"], rows[0]["relayed_by"]), ("user", RELAY_NAME))
        self.assertNotIn(TYPED, json.dumps(rows))

    def test_a_plan_ruling_relayed_by_session_id_records_the_session_name_in_the_plan_and_the_row(self):
        self.say(TYPED, HUMAN)

        code, output = self.decide(relayed_by=RELAY_SESSION_ID)

        self.assertEqual(code, 0, output)
        plan_text = self.user_plan.read_text()
        self.assertIn(f"relayed by session {RELAY_NAME}", plan_text)
        self.assertNotIn(RELAY_SESSION_ID, plan_text)
        rows = self.relay_rows()
        self.assertEqual([row["relayed_by"] for row in rows], [RELAY_NAME])
        self.assertNotIn(RELAY_SESSION_ID, json.dumps(rows))

    def test_a_bare_session_ruling_on_a_user_owned_plan_is_refused(self):
        code, output = self.decide(by="session", relay=False)
        self.assert_refused_with_nothing_logged(code, output, "--by user")

    def test_a_relay_under_by_session_is_refused(self):
        self.say(TYPED, HUMAN)
        code, output = self.decide(by="session")
        self.assert_refused_with_nothing_logged(code, output, "--by user")

    def test_a_relaying_session_with_no_human_turn_is_refused(self):
        self.say(TYPED, {"kind": "peer", "from": "orchestrator"})
        code, output = self.decide()
        self.assert_refused_with_nothing_logged(code, output, "no human turn")

    def test_a_turn_typed_before_the_impact_was_handed_back_is_refused(self):
        self.say(TYPED, HUMAN, when=time.time() - 3600)
        code, output = self.decide()
        self.assert_refused_with_nothing_logged(code, output, "older than")


if __name__ == "__main__":
    unittest.main()
