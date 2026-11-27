"""The ask-findings file names who changed a modified ask: the user for `asks-done --by user`, the session for
`--by session`, and no one when the state does not say."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import approval_asks_store
import ask_outcome_words
import code_wait
import fake_ledger
import owner_lines
import review_asks
import review_fix
import review_fix_asks
import review_fix_names
import review_fix_state
import review_loop_findings
import script_utils
import test_review_fix_script as fixture  # the module, never its class: a class imported by name reruns its tests

ask_entry = fixture.ask_entry
packet_text = fixture.packet_text
CLEAN_EMPTY_FIELDS = fixture.CLEAN_EMPTY_FIELDS

USER_SENTENCE = "The user changed it; make this change in its place: "
SESSION_SENTENCE = "The session changed it, not the user; make this change in its place: "
NEUTRAL_SENTENCE = "It was changed at the ruling; make this change in its place: "

FIRST_ASK = ask_entry("first", "one.ts:1", finding_id="a1b2c3d4e5f60031", question="first?", change="c1")
SECOND_ASK = ask_entry("second", "two.ts:2", finding_id="a1b2c3d4e5f60032", question="second?", change="c2")
ONE_ASK = packet_text(CLEAN_EMPTY_FIELDS, ask=[FIRST_ASK])
TWO_ASKS = packet_text(CLEAN_EMPTY_FIELDS, ask=[FIRST_ASK, SECOND_ASK])
USER_ONLY_FIRST_ASK = {**FIRST_ASK, "user_only": True}


class LegacyFiledTimeTest(unittest.TestCase):
    def test_a_waiting_packet_ask_keeps_the_original_save_time_through_the_carry_and_a_resave(self):
        with tempfile.TemporaryDirectory() as folder:
            state_file = pathlib.Path(folder) / "state.json"
            legacy_ask = {"user_only": True}
            state_file.write_text(json.dumps({"packet_id": "old", "asks": [dict(legacy_ask)],
                                              "waiting_packets": [{"asks": [legacy_ask]}]}))
            os.utime(state_file, (1000, 1000))

            previous = review_fix_state.read_state(state_file)
            carried = review_fix.carried_waiting_packets(previous)
            review_fix_state.save_fix_state({"packet_id": "new", "waiting_packets": carried}, state_file)
            saved = json.loads(state_file.read_text())

        stamped = [ask[review_fix_names.FILED_AT_KEY] for packet in saved["waiting_packets"] for ask in packet["asks"]]
        self.assertEqual(stamped, [1000, 1000])


class ApprovalRestoreRulingTest(unittest.TestCase):
    """An accepted user-only approval ask puts its file back to the text it held before the pass, and the fix coder
    is not handed the ask."""
    setUp = fixture.ReviewFixScriptTest.setUp
    stop_launched_loops = fixture.ReviewFixScriptTest.stop_launched_loops
    fake_command = fixture.ReviewFixScriptTest.fake_command
    environment = fixture.ReviewFixScriptTest.environment
    git = fixture.ReviewFixScriptTest.git
    run_script = fixture.ReviewFixScriptTest.run_script
    packet = fixture.ReviewFixScriptTest.packet
    ledger_writes = fixture.ReviewFixScriptTest.ledger_writes
    findings_file = fixture.ReviewFixScriptTest.findings_file

    PRE_PASS_TEXT = "rules\nuser line\n"
    EDITED_TEXT = "rules\nuser line\ncoder line\n"

    def claude_md(self):
        return pathlib.Path(self.repo) / "CLAUDE.md"

    def packet_with_approval_ask(self, base):
        """CLAUDE.md holds the coder's edit; the saved paths name `base`, or the blob of the pre-pass text."""
        self.claude_md().write_text(self.PRE_PASS_TEXT)
        pre_pass_blob = script_utils.work_tree_blob(self.repo, "CLAUDE.md", keep_object=True)
        self.claude_md().write_text(self.EDITED_TEXT)
        approval_asks_store.write_saved_asks(self.repo, {"CLAUDE.md": base or pre_pass_blob}, [])
        change = approval_asks_store.approval_change("CLAUDE.md")
        entry = ask_entry("edit", "CLAUDE.md:1", finding_id="a1b2c3d4e5f60051", question="approve?", change=change)
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[{**entry, "user_only": True}, SECOND_ASK]))

    def test_the_user_lines_remain_the_coder_edit_is_gone_and_the_coder_gets_only_the_other_ask(self):
        self.packet_with_approval_ask(None)

        code, output = self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertIn("Restored `CLAUDE.md` to its text from before the fix pass; "
                      "commit it with the rest of the change.", output)
        self.assertIn("`git add CLAUDE.md`", output)
        self.assertEqual(self.claude_md().read_text(), self.PRE_PASS_TEXT)
        findings = self.findings_file().read_text().splitlines()
        self.assertEqual(len(findings), 1, findings)
        self.assertIn("two.ts:2", findings[0])
        self.assertEqual(approval_asks_store.read_approval_paths(self.repo), {})

    def test_an_unknown_base_leaves_the_file_and_still_hands_the_ask_to_the_coder(self):
        self.packet_with_approval_ask(approval_asks_store.UNKNOWN_BASE)

        code, output = self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertNotIn("Restored", output)
        self.assertEqual(self.claude_md().read_text(), self.EDITED_TEXT)
        findings = self.findings_file().read_text().splitlines()
        self.assertEqual(len(findings), 2, findings)
        claude_md_line = next(line for line in findings if "CLAUDE.md" in line)
        self.assertIn(approval_asks_store.approval_change("CLAUDE.md"), claude_md_line)

    def test_a_restore_that_fails_exits_non_zero_naming_the_file_and_logs_nothing(self):
        missing_blob = "0123456789abcdef0123456789abcdef01234567"
        self.packet_with_approval_ask(missing_blob)
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("CLAUDE.md", output)
        self.assertIn(missing_blob, output)
        self.assertIn("modified:", output)
        self.assertIn("Nothing was logged", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)
        self.assertEqual(self.claude_md().read_text(), self.EDITED_TEXT)

    def test_a_correction_to_accepted_after_the_base_was_released_is_refused_and_never_reverts_to_head(self):
        self.packet_with_approval_ask(None)
        self.run_script(["asks-done", "--by", "user", "rejected:keep the edit", "accepted"])
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "user", "accepted", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("CLAUDE.md", output)
        self.assertIn("by hand", output)
        self.assertIn("Nothing was logged", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)
        self.assertEqual(self.claude_md().read_text(), self.EDITED_TEXT)

    def test_a_retry_after_a_logging_failure_keeps_the_restored_ask_out_of_the_findings_file(self):
        self.packet_with_approval_ask(None)
        fail_call = fake_ledger.write_call_count(self.ledger_env) + 2
        words = ["asks-done", "--by", "user", "accepted", "accepted"]
        code, output = self.run_script(words, FAKE_LEDGER_FAIL_WRITE_CALL=str(fail_call))
        self.assertEqual(code, 0, output)
        # The retry below must be the case where the restore is done and the saved paths are already forgotten.
        self.assertEqual(self.claude_md().read_text(), self.PRE_PASS_TEXT)
        self.assertEqual(approval_asks_store.read_approval_paths(self.repo), {})

        code, output = self.run_script(words)
        self.assertEqual(code, 0, output)
        code, output = self.run_script(["asks-done", "--correct", "--by", "user", "accepted", "rejected:no"])

        self.assertEqual(code, 0, output)
        self.assertEqual(self.claude_md().read_text(), self.PRE_PASS_TEXT)
        findings_text = self.findings_file().read_text() if self.findings_file().exists() else ""
        self.assertNotIn("CLAUDE.md", findings_text)

    def test_the_modified_answer_the_refusal_suggests_is_accepted(self):
        self.packet_with_approval_ask(None)
        self.run_script(["asks-done", "--by", "user", "rejected:keep the edit", "accepted"])

        code, output = self.run_script(["asks-done", "--correct", "--by", "user",
                                       "modified:keep the coder line in `CLAUDE.md`", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertEqual(self.claude_md().read_text(), self.EDITED_TEXT)

    def assert_correction_after_accepted_is_refused(self, new_answer):
        self.packet_with_approval_ask(None)
        self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "user", new_answer, "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("already put the file back", output)
        self.assertIn("Nothing was logged", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)
        self.assertEqual(self.claude_md().read_text(), self.PRE_PASS_TEXT)

    def test_a_correction_after_an_accepted_ruling_is_refused_because_the_edit_is_already_gone(self):
        self.assert_correction_after_accepted_is_refused("rejected:keep the edit")

    def test_a_modified_correction_after_an_accepted_ruling_is_refused_too(self):
        self.assert_correction_after_accepted_is_refused("modified:keep the coder line in `CLAUDE.md`")

    def test_the_call_the_refusal_suggests_corrects_the_other_ask(self):
        self.packet_with_approval_ask(None)
        self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "user", "accepted", "rejected:no"])

        self.assertEqual(code, 0, output)
        self.assertEqual(self.claude_md().read_text(), self.PRE_PASS_TEXT)
        self.assertGreater(len(self.ledger_writes()), rows_before)
        # The second ask is rejected, so no ask is left for the coder and the findings file is gone.
        findings_text = self.findings_file().read_text() if self.findings_file().exists() else ""
        self.assertNotIn("CLAUDE.md", findings_text)
        self.assertNotIn("two.ts", findings_text)

    def test_a_correction_on_a_sibling_ask_keeps_the_restored_ask_out_of_the_findings(self):
        self.packet_with_approval_ask(None)
        self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])

        code, output = self.run_script(["asks-done", "--correct", "--by", "user", "accepted",
                                       "modified:do x in `two.ts`"])

        self.assertEqual(code, 0, output)
        self.assertNotIn("CLAUDE.md", self.findings_file().read_text())

    def test_an_unrestored_accepted_ask_can_be_corrected_to_rejected_and_keeps_the_edit(self):
        self.packet_with_approval_ask(approval_asks_store.UNKNOWN_BASE)
        self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])

        code, output = self.run_script(["asks-done", "--correct", "--by", "user", "rejected:keep the edit",
                                       "accepted"])

        self.assertEqual(code, 0, output)
        self.assertEqual(self.claude_md().read_text(), self.EDITED_TEXT)

    def test_a_saved_absent_base_for_a_tracked_file_is_not_restored(self):
        self.packet_with_approval_ask(None)
        self.git("add", "CLAUDE.md")
        self.git("commit", "-m", "track")
        self.claude_md().write_text(self.EDITED_TEXT)
        approval_asks_store.write_saved_asks(self.repo, {"CLAUDE.md": None}, [])

        code, output = self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertNotIn("Restored", output)
        self.assertEqual(self.claude_md().read_text(), self.EDITED_TEXT)

    def test_a_folder_name_with_a_space_is_restored(self):
        folder = pathlib.Path(self.repo) / "my dir"
        folder.mkdir()
        target = folder / "CLAUDE.md"
        target.write_text(self.PRE_PASS_TEXT)
        blob = script_utils.work_tree_blob(self.repo, "my dir/CLAUDE.md", keep_object=True)
        target.write_text(self.EDITED_TEXT)
        approval_asks_store.write_saved_asks(self.repo, {"my dir/CLAUDE.md": blob}, [])
        change = approval_asks_store.approval_change("my dir/CLAUDE.md")
        entry = ask_entry("edit", "my dir/CLAUDE.md:1", finding_id="a1b2c3d4e5f60052", question="approve?",
                          change=change)
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[{**entry, "user_only": True}, SECOND_ASK]))

        code, output = self.run_script(["asks-done", "--by", "user", "accepted", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertEqual(target.read_text(), self.PRE_PASS_TEXT)
        self.assertIn("`git add 'my dir/CLAUDE.md'`", output)


class AskRulerTest(unittest.TestCase):
    # The real asks-done runs against a temp repo, set up as the review-fix script tests set it up.
    setUp = fixture.ReviewFixScriptTest.setUp
    stop_launched_loops = fixture.ReviewFixScriptTest.stop_launched_loops
    fake_command = fixture.ReviewFixScriptTest.fake_command
    environment = fixture.ReviewFixScriptTest.environment
    git = fixture.ReviewFixScriptTest.git
    run_script = fixture.ReviewFixScriptTest.run_script
    packet = fixture.ReviewFixScriptTest.packet
    ledger_writes = fixture.ReviewFixScriptTest.ledger_writes
    findings_file = fixture.ReviewFixScriptTest.findings_file

    def asks_done(self, *words):
        code, output = self.run_script(["asks-done", *words])
        self.assertEqual(code, 0, output)
        return output

    def logged_outcomes(self):
        return [row["ask_outcome"] for row in self.ledger_writes() if "ask_outcome" in row]

    def findings_lines(self):
        return self.findings_file().read_text().splitlines()

    def state_file(self):
        review_fix_folder = script_utils.git_path(self.repo, review_fix_names.REVIEW_FIX_FOLDER)
        return review_fix_folder / review_fix_names.STATE_FILE_NAME

    def edit_state(self, **changes):
        state = json.loads(self.state_file().read_text())
        state.update(changes)
        self.state_file().write_text(json.dumps(state))

    def drop_state_key(self, key):
        state = json.loads(self.state_file().read_text())
        del state[key]
        self.state_file().write_text(json.dumps(state))

    def answered(self, packet, *words):
        self.packet(packet)
        return self.asks_done(*words)

    def test_a_modified_ask_ruled_by_the_user_says_the_user_changed_it(self):
        self.answered(ONE_ASK, "--by", "user", "modified:cap at 5")
        self.assertEqual(self.findings_lines(),
                         ["- one.ts:1 [smell] Proposed change: c1 " + USER_SENTENCE + "cap at 5"])

    def test_by_user_credits_every_ask_of_a_mixed_batch_to_the_user(self):
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[USER_ONLY_FIRST_ASK, SECOND_ASK]))
        self.asks_done("--by", "user", "modified:one", "modified:two")
        lines = self.findings_lines()
        self.assertTrue(lines[0].endswith(USER_SENTENCE + "one"), lines[0])
        self.assertTrue(lines[1].endswith(USER_SENTENCE + "two"), lines[1])
        state = json.loads(self.state_file().read_text())
        self.assertEqual(state[review_fix_asks.ASKS_DECIDED_BY_KEY], ["user", "user"])
        rulers = [row["ask_decided_by"] for row in self.ledger_writes() if "ask_decided_by" in row]
        self.assertEqual(rulers, ["user", "user"])

    def test_a_modified_ask_ruled_by_the_session_names_the_session_not_the_user(self):
        self.answered(ONE_ASK, "--by", "session", "modified:cap at 5")
        self.assertEqual(self.findings_lines(),
                         ["- one.ts:1 [smell] Proposed change: c1 " + SESSION_SENTENCE + "cap at 5"])

    def test_an_accepted_ask_with_no_location_and_no_file_in_its_change_is_refused_and_logs_nothing(self):
        unlocated = ask_entry("first", "unlocated", finding_id="a1b2c3d4e5f60033", question="keep it?",
                              change="tighten the check")
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[unlocated]))
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--by", "session", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("'modified:<the change, naming the file and the edit>'", output)
        self.assertIn("Nothing was logged", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)

        self.asks_done("--by", "session", "modified:tighten the check in src/gate.py")
        self.assertIn("src/gate.py", "\n".join(self.findings_lines()))

    def test_an_accepted_unlocated_ask_whose_change_names_a_file_gives_the_coder_that_path(self):
        unlocated = ask_entry("first", "unlocated", finding_id="a1b2c3d4e5f60035", question="keep it?",
                              change="tighten the check in src/gate.py")
        self.answered(packet_text(CLEAN_EMPTY_FIELDS, ask=[unlocated]), "--by", "session", "accepted")
        self.assertIn("src/gate.py", "\n".join(self.findings_lines()))

    def test_a_correction_to_accepted_on_an_unlocated_ask_with_no_file_is_refused_and_logs_nothing(self):
        unlocated = ask_entry("first", "unlocated", finding_id="a1b2c3d4e5f60034", question="keep it?",
                              change="tighten the check")
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[unlocated]))
        self.asks_done("--by", "session", "modified:tighten the check in src/gate.py")
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("Nothing was logged", output)
        self.assertIn("run `asks-done --correct ...` again", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)

    def conditional_ask_packet(self):
        conditional = ask_entry("first", "a.py:1", finding_id="a1b2c3d4e5f60036", question="keep it?",
                                change="if yes, drop it; if no, keep it")
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[conditional]))

    def test_a_correction_to_accepted_on_a_conditional_change_is_refused_with_the_correct_command(self):
        self.conditional_ask_packet()
        self.asks_done("--by", "session", "modified:drop it")
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("run `asks-done --correct ...` again", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)

    def test_an_accepted_conditional_change_is_refused_with_the_plain_command(self):
        self.conditional_ask_packet()
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--by", "session", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("run `asks-done ...` again", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)

    def test_a_session_ruling_on_a_user_only_ask_is_refused_and_logs_nothing(self):
        user_only_ask = {**FIRST_ASK, "user_only": True}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[user_only_ask]))
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--by", "session", "rejected:keep it"])

        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 1 are user_only: only the user rules them, never the session", output)
        self.assertIn("record the user's outcome with `--by user`: `asks-done --by user ...`", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)
        self.asks_done("--by", "user", "rejected:keep it")

    def test_a_session_rejection_of_a_wanted_change_is_logged_and_an_accept_or_revert_ask_is_refused(self):
        wanted_change = f"add it {approval_asks_store.wanted_edit_target('CLAUDE.md')}"
        wanted = {**FIRST_ASK, "user_only": True, "wanted_change": True, "change": wanted_change}
        revert = {**SECOND_ASK, "user_only": True, "change": approval_asks_store.approval_change("AGENTS.md")}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[wanted, revert]))
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--by", "session", "rejected:no", "rejected:no"])
        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 2 are user_only", output)
        self.assertNotIn("ask(s) 1", output)
        code, output = self.run_script(["asks-done", "--by", "session", "accepted", "held"])
        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 1 are user_only", output)
        self.assertIn("only the user accepts them", output)
        self.assertIn(f"Note: for ask(s) 1, {ask_outcome_words.SESSION_MAY_REJECT_WANTED}.", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)

        code, output = self.run_script(["asks-done", "--by", "session", "rejected:no", "held"])
        self.assertEqual(code, 0, output)
        self.assertEqual(self.logged_outcomes(), ["rejected"])
        self.assertEqual(len(self.ledger_writes()), rows_before + 1)

    def wanted_change_packet(self, beside=()):
        """A packet whose last ask is a wanted user-only change, after the plain asks in `beside`."""
        wanted_change = f"add it {approval_asks_store.wanted_edit_target('CLAUDE.md')}"
        base = SECOND_ASK if beside else FIRST_ASK
        wanted = {**base, "user_only": True, "wanted_change": True, "change": wanted_change}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[*beside, wanted]))

    def test_a_session_correction_of_a_wanted_change_to_accepted_or_modified_is_refused(self):
        self.wanted_change_packet(beside=[FIRST_ASK])
        self.asks_done("--by", "session", "accepted", "rejected:first")
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "accepted", "accepted"])
        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 2 are user_only", output)
        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "accepted", "modified:x"])
        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 2 are user_only", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)

    def test_a_session_correction_never_replaces_a_user_ruling_on_a_wanted_change(self):
        self.wanted_change_packet()
        self.asks_done("--by", "user", "accepted")
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "rejected:no"])

        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 1 are user_only", output)
        self.assertNotIn("only the user accepts", output)
        self.assertNotIn(ask_outcome_words.SESSION_MAY_REJECT_WANTED, output)
        self.assertEqual(len(self.ledger_writes()), rows_before)

    def test_the_printed_asks_mark_a_user_only_ask(self):
        user_only_ask = {**FIRST_ASK, "user_only": True}

        code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[user_only_ask, SECOND_ASK]))

        self.assertEqual(code, 0, output)
        self.assertIn("1. one.ts:1  [code-reviewer/smell] [user only]", output)
        self.assertNotIn("2. two.ts:2  [code-reviewer/smell] [user only]", output)

    def test_a_session_correction_of_a_user_only_ask_is_refused_and_changes_nothing(self):
        user_only_ask = {**FIRST_ASK, "user_only": True}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[user_only_ask]))
        self.asks_done("--by", "user", "accepted:keep it")
        state_before = self.state_file().read_bytes()
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "rejected:drop it"])

        self.assertEqual(code, 2, output)
        self.assertIn("only the user rules them", output)
        self.assertEqual(self.state_file().read_bytes(), state_before)
        self.assertEqual(len(self.ledger_writes()), rows_before)

    def rule_user_only_beside_ordinary_ask(self):
        user_only_ask = {**FIRST_ASK, "user_only": True}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[user_only_ask, SECOND_ASK]))
        self.asks_done("--by", "user", "modified:one", "modified:two")

    def test_a_session_correction_of_only_the_ordinary_ask_beside_a_user_only_ask_records_the_session(self):
        self.rule_user_only_beside_ordinary_ask()

        self.asks_done("--correct", "--by", "session", "modified:one", "modified:three")

        state = json.loads(self.state_file().read_text())
        self.assertEqual(state[review_fix_asks.ASKS_DECIDED_BY_KEY], ["user", "session"])

    def test_a_session_correction_that_changes_the_user_only_ask_in_a_mixed_batch_is_refused(self):
        self.rule_user_only_beside_ordinary_ask()
        state_before = self.state_file().read_bytes()
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "modified:uno", "modified:three"])

        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 1 are user_only", output)
        self.assertIn("`asks-done --correct --by user ...`", output)
        self.assertEqual(self.state_file().read_bytes(), state_before)
        self.assertEqual(len(self.ledger_writes()), rows_before)

    def test_the_refusal_names_the_listing_number_of_a_user_only_ask_in_second_place(self):
        user_only_second = {**SECOND_ASK, "user_only": True}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[FIRST_ASK, user_only_second]))
        self.asks_done("--by", "user", "modified:one", "modified:two")

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "modified:one", "modified:three"])

        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 2 are user_only", output)

    def test_an_accepted_ask_whose_change_follows_a_change_if_not_accepted_mark_carries_only_the_change(self):
        text = ("A script-file run given a quoted argument no longer counts as a commit. Is it acceptable that a "
                "commit run through a script given a quoted argument no longer counts? Change if not accepted: "
                "remove the quoted-argument exemption, so that a script-file run counts.")
        question, change = review_loop_findings.ask_parts(text)
        item = {"question": question, "change": change, "file_line": "gates/x.py:12", "class": "security"}

        self.assertEqual(review_asks.conditional_ask_numbers([item]), [])
        finding = review_fix_asks.ask_finding_text(item)

        self.assertEqual(finding, "gates/x.py:12 [security] Proposed change: remove the quoted-argument exemption, "
                                  "so that a script-file run counts.")

    def test_an_ask_with_two_change_if_branches_is_refused_as_conditional(self):
        question, change = review_loop_findings.ask_parts(
            "Drop the cache? Change if yes: drop it. Change if no: keep it.")
        item = {"question": question, "change": change, "file_line": "a.py:1", "class": "bug"}

        self.assertEqual(review_asks.conditional_ask_numbers([item]), [1])
        with self.assertRaises(review_fix_asks.UsageError):
            review_asks.refuse_conditional_changes([item], [review_fix_asks.ACCEPTED], "asks-done ...")

    def test_the_conditional_refusal_names_the_rerun_command_it_was_given(self):
        item = {"question": "Drop the cache?", "change": "If not confirmed, revert the cache", "file_line": "a.py:1"}
        with self.assertRaises(review_fix_asks.UsageError) as raised:
            review_asks.refuse_conditional_changes([item], [review_fix_asks.ACCEPTED], "asks-done --correct ...")
        self.assertIn("run `asks-done --correct ...` again", str(raised.exception))

    def test_every_outcome_but_modified_is_refused_on_a_conditional_change(self):
        item = {"question": "Drop the cache?", "change": "If not confirmed, revert the cache", "file_line": "a.py:1"}
        for outcome in (review_fix_asks.ACCEPTED, review_fix_asks.APPLIED, review_fix_asks.REJECTED):
            with self.subTest(outcome=outcome), self.assertRaises(review_fix_asks.UsageError):
                review_asks.refuse_conditional_changes([item], [outcome], "asks-done ...")
        review_asks.refuse_conditional_changes([item], [review_fix_asks.MODIFIED], "asks-done ...")

    def test_a_plain_change_mark_in_the_question_keeps_a_single_change_if_label_as_the_split(self):
        parts = review_loop_findings.ask_parts(
            "a.py:3 — Should the default change: 10 or 20? — Change if accepted: set it to 20")

        self.assertEqual(parts.change, "set it to 20")
        self.assertFalse(review_asks.is_conditional_change(parts.change))

    def test_a_converted_ask_names_its_ruler_in_both_branches(self):
        converted = {"question": "Apply it anyway?", "change": "src/a.py:3 [bug] cap it",
                     "file_line": "src/a.py:3", "class": "bug", review_fix_asks.USER_RULED_KEY: True}
        cases = [("user", USER_SENTENCE), ("session", SESSION_SENTENCE), (None, NEUTRAL_SENTENCE)]
        for decided_by, sentence in cases:
            with self.subTest(decided_by=decided_by):
                text = review_fix_asks.ask_finding_text(converted, "cap at 5", decided_by)
                self.assertEqual(text, "src/a.py:3 [bug] cap it " + sentence + "cap at 5")
                plain = review_fix_asks.ask_finding_text({**converted, review_fix_asks.USER_RULED_KEY: False,
                                                          "change": "cap it"}, "cap at 5", decided_by)
                self.assertEqual(plain, "src/a.py:3 [bug] Proposed change: cap it " + sentence + "cap at 5")

    def test_a_none_ruler_in_the_state_gets_the_neutral_sentence_never_the_user(self):
        self.answered(TWO_ASKS, "--by", "user", "modified:one", "modified:two")
        self.edit_state(asks_decided_by=[None, "user"])
        self.asks_done("--correct", "--by", "user", "modified:one", "modified:three")
        lines = self.findings_lines()
        self.assertTrue(lines[0].endswith(NEUTRAL_SENTENCE + "one"), lines[0])
        self.assertTrue(lines[1].endswith(USER_SENTENCE + "three"), lines[1])

    def assert_correction_stops_with_no_change(self, *outcome_words):
        """The correction exits 2, and the state file, the findings file and the ledger are as they were."""
        state_before = self.state_file().read_bytes()
        findings_before = self.findings_file().read_bytes()
        rows_before = len(self.ledger_writes())
        code, output = self.run_script(["asks-done", "--correct", "--by", "user", *outcome_words])
        self.assertEqual(code, 2, output)
        self.assertEqual(self.state_file().read_bytes(), state_before)
        self.assertEqual(self.findings_file().read_bytes(), findings_before)
        self.assertEqual(len(self.ledger_writes()), rows_before, "an outcome row was logged")
        return output

    def test_an_unknown_ruler_word_in_the_state_stops_the_correction_loudly(self):
        self.answered(TWO_ASKS, "--by", "user", "modified:one", "modified:two")
        self.edit_state(asks_decided_by=["robot", "user"])
        output = self.assert_correction_stops_with_no_change("modified:one", "modified:three")
        self.assertIn(review_fix_asks.ASKS_DECIDED_BY_KEY, output)
        self.assertIn("robot", output)

    def test_a_state_with_no_decider_field_gets_the_neutral_sentence_for_the_uncorrected_ask(self):
        self.answered(TWO_ASKS, "--by", "user", "modified:one", "modified:two")
        self.drop_state_key(review_fix_asks.ASKS_DECIDED_BY_KEY)
        self.asks_done("--correct", "--by", "session", "modified:one", "modified:three")
        lines = self.findings_lines()
        self.assertTrue(lines[0].endswith(NEUTRAL_SENTENCE + "one"), lines[0])
        self.assertTrue(lines[1].endswith(SESSION_SENTENCE + "three"), lines[1])

    def test_a_shorter_decider_list_in_the_state_stops_the_correction_loudly(self):
        self.answered(TWO_ASKS, "--by", "user", "modified:one", "modified:two")
        self.edit_state(asks_decided_by=["user"])
        output = self.assert_correction_stops_with_no_change("modified:one", "modified:three")
        self.assertIn(review_fix_asks.ASKS_DECIDED_BY_KEY, output)

    def test_an_applied_ask_logs_as_accepted_and_prints_no_fix_run(self):
        self.packet(TWO_ASKS)
        code, output = self.run_script(["asks-done", "--by", "user", "applied", "rejected:keep it"])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertNotIn("ACTION: redispatch", output)
        self.assertFalse(self.findings_file().exists())
        self.assertEqual(self.logged_outcomes(), ["accepted", "rejected"])
        deciders = [row["ask_decided_by"] for row in self.ledger_writes() if "ask_decided_by" in row]
        self.assertEqual(deciders, ["user", "user"])

    def test_an_applied_ask_stays_out_of_the_findings_file_beside_an_accepted_one(self):
        self.packet(TWO_ASKS)
        self.asks_done("--by", "user", "applied", "accepted")
        lines = self.findings_lines()
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("two.ts:2", lines[0])

    def test_an_unknown_outcome_error_lists_applied(self):
        self.packet(ONE_ASK)
        code, output = self.run_script(["asks-done", "--by", "user", "done"])
        self.assertEqual(code, 2, output)
        self.assertIn("|".join(review_asks.ASK_OUTCOMES), output)
        self.assertIn("applied", output)
        self.assertIn(review_asks.APPLIED_MEANS, output)

    def test_a_correction_from_applied_to_accepted_is_refused_because_no_fix_run_is_pending(self):
        self.packet(ONE_ASK)
        self.asks_done("--by", "user", "applied")
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "user", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("None is pending", output)
        self.assertEqual(len(self.ledger_writes()), rows_before, "an outcome row was logged")
        self.assertFalse(self.findings_file().exists())

    def test_a_correction_to_applied_logs_accepted_and_writes_no_findings_line(self):
        self.packet(ONE_ASK)
        self.asks_done("--by", "user", "accepted")
        self.assertEqual(len(self.findings_lines()), 1)

        outcomes_before = self.logged_outcomes()

        self.asks_done("--correct", "--by", "user", "applied")

        self.assertFalse(self.findings_file().exists())
        self.assertEqual(self.logged_outcomes()[len(outcomes_before):], ["accepted"])

    def test_a_change_that_only_mentions_if_is_not_conditional(self):
        not_split = [
            "Rename the helper; change if needed at call sites",
            "Change if branch at foo.py:12 to return early",
            "Change if-statement in parse: use match",
        ]
        for change in not_split:
            with self.subTest(change=change):
                self.assertFalse(review_asks.is_conditional_change(change))
                parts = review_loop_findings.ask_parts("Q? " + change)
                self.assertEqual(parts.question, parts.change, "the ask parser must not split it either")

    def test_a_leading_change_if_label_is_not_a_second_branch_once_the_ask_is_split(self):
        for text in ["Q? Change if guard: drop it", "Q? Change if the user " + "x" * 50 + ": drop it"]:
            with self.subTest(text=text):
                parts = review_loop_findings.ask_parts(text)
                self.assertFalse(review_asks.is_conditional_change(parts.change))

    def test_a_change_if_answer_label_is_conditional(self):
        for change in ["Do A. Change if yes: B", "Do A. Change if not accepted: B",
                       "A. Change if moved: B", "A. **Change if no**: B", "A. Change if *no*: B",
                       "A. Change if `no`: B"]:
            with self.subTest(change=change):
                self.assertTrue(review_asks.is_conditional_change(change))

    def test_a_second_branch_with_a_non_answer_label_is_refused_after_the_ask_split(self):
        for text in ["Q? Change if yes: A. Change if moved: B", "Q? Change if yes: A. Change if *no*: B",
                     "Q? Change if yes: A. Change if `no`: B"]:
            with self.subTest(text=text):
                parts = review_loop_findings.ask_parts(text)
                self.assertTrue(review_asks.is_conditional_change(parts.change))

    def test_the_state_time_is_stamped_once_into_each_legacy_user_only_ask(self):
        asks = [{"user_only": True}, {"user_only": False}]
        options = unittest.mock.Mock(relay=object())

        with unittest.mock.patch.object(review_fix_asks.ruling_relay, "verify_relay") as verify:
            review_fix_state.stamp_legacy_filed_at(asks, 1000.0)
            review_fix_state.stamp_legacy_filed_at(asks, 2000.0)
            review_fix_asks.verified_fix_relay(options, asks)

        self.assertEqual(asks[0][review_fix_names.FILED_AT_KEY], 1000.0)
        self.assertNotIn(review_fix_names.FILED_AT_KEY, asks[1])
        self.assertEqual(verify.call_args.args[1], 1000.0)

    def test_a_relayed_ruling_on_an_unstamped_user_only_ask_is_refused_with_nothing_logged(self):
        options = unittest.mock.Mock(relay=object())

        with self.assertRaises(review_fix_asks.UsageError) as raised:
            review_fix_asks.verified_fix_relay(options, [{"user_only": True}])

        self.assertIn("Nothing was logged", str(raised.exception))

    def test_a_correction_keeps_the_run_folder_findings_file_the_session_wrote(self):
        self.packet(ONE_ASK)
        self.asks_done("--by", "user", "accepted")
        written_file = self.run_folder_findings_file()
        written_file.parent.mkdir(parents=True, exist_ok=True)
        written_file.write_text("- one.ts:1 [smell] written for this run\n")

        output = self.asks_done("--correct", "--by", "user", "modified:x")

        self.assertTrue(written_file.exists())
        self.assertNotIn(review_fix_asks.STALE_RUN_FOLDER_FINDINGS_REMOVED, output)

    def test_an_all_applied_packet_leaves_a_stale_run_folder_findings_file_alone(self):
        self.packet(ONE_ASK)
        stale_file = self.run_folder_findings_file()
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_text("- old.ts:9 [smell] an earlier run's finding\n")

        output = self.asks_done("--by", "user", "applied")

        self.assertTrue(stale_file.exists())
        self.assertNotIn(review_fix_asks.STALE_RUN_FOLDER_FINDINGS_REMOVED, output)

    def test_an_applied_plan_impact_ask_writes_no_findings_line(self):
        plan_impact = {"question": "PLAN-IMPACT: one", "change": "c1"}

        self.assertEqual(review_fix_asks.finding_ask_indexes([plan_impact], ["applied"]), [])

    def test_an_unknown_by_word_is_a_usage_error(self):
        self.packet(ONE_ASK)
        code, output = self.run_script(["asks-done", "--by", "robot", "modified:cap at 5"])
        self.assertEqual(code, 2, output)
        self.assertIn("asks-done --by needs user or session, not 'robot'", output)

    def assert_note_stored_whole_for_each_ruler(self, note):
        """The user rules the note, then a session corrects it to the same note plus one word."""
        self.answered(ONE_ASK, "--by", "user", "modified:" + note)
        user_lines = self.findings_lines()
        self.assertEqual(len(user_lines), 1)
        self.assertTrue(user_lines[0].endswith(USER_SENTENCE + script_utils.one_line(note, None)), user_lines[0][-120:])

        self.asks_done("--correct", "--by", "session", "modified:" + note + " end")
        session_lines = self.findings_lines()
        self.assertEqual(len(session_lines), 1)
        expected_tail = SESSION_SENTENCE + script_utils.one_line(note + " end", None)
        self.assertTrue(session_lines[0].endswith(expected_tail), session_lines[0][-120:])

    def test_a_note_with_double_and_single_quotes_is_stored_whole_with_its_ruler(self):
        self.assert_note_stored_whole_for_each_ruler("use \"a\" and 'b'")

    def test_a_note_with_backticks_is_stored_whole_with_its_ruler(self):
        self.assert_note_stored_whole_for_each_ruler("run `make test` first")

    def test_a_note_with_a_newline_is_stored_on_one_line_with_its_ruler(self):
        self.assert_note_stored_whole_for_each_ruler("first line\nsecond line")

    def test_a_note_of_20000_characters_is_stored_whole_with_its_ruler(self):
        self.assert_note_stored_whole_for_each_ruler("x" * 20000)

    def test_a_session_correction_changes_only_the_corrected_ask_to_session(self):
        self.answered(TWO_ASKS, "--by", "user", "modified:one", "modified:two")
        self.asks_done("--correct", "--by", "session", "modified:one", "modified:three")
        lines = self.findings_lines()
        self.assertTrue(lines[0].endswith(USER_SENTENCE + "one"), lines[0])
        self.assertTrue(lines[1].endswith(SESSION_SENTENCE + "three"), lines[1])

    def test_a_session_correction_of_a_user_ruled_ask_says_session(self):
        self.answered(ONE_ASK, "--by", "user", "modified:cap at 5")
        self.asks_done("--correct", "--by", "session", "modified:cap at 6")
        lines = self.findings_lines()
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].endswith(SESSION_SENTENCE + "cap at 6"), lines[0])
        self.assertNotIn("The user changed it", lines[0])

    def test_an_accepted_ask_ruled_by_the_user_carries_no_ruler_sentence(self):
        self.answered(ONE_ASK, "--by", "user", "accepted")
        self.assertEqual(self.findings_lines(), ["- one.ts:1 [smell] Proposed change: c1"])

    def test_an_accepted_ask_ruled_by_the_session_carries_no_ruler_sentence(self):
        self.answered(ONE_ASK, "--by", "session", "accepted")
        self.assertEqual(self.findings_lines(), ["- one.ts:1 [smell] Proposed change: c1"])

    def run_folder_findings_file(self):
        return code_wait.phase_dir(self.repo) / review_fix_names.RUN_FOLDER_FINDINGS_NAME

    def test_asks_done_removes_a_stale_run_folder_findings_file_and_says_so(self):
        self.packet(ONE_ASK)
        stale_file = self.run_folder_findings_file()
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_text("- old.ts:9 [smell] an earlier run's finding\n")

        output = self.asks_done("--by", "user", "accepted:ok")

        self.assertFalse(stale_file.exists())
        self.assertIn(review_fix_asks.STALE_RUN_FOLDER_FINDINGS_REMOVED, output)
        self.assertTrue(self.findings_file().exists())

    @unittest.skipIf(os.geteuid() == 0, "root ignores the folder mode that makes the removal fail")
    def test_a_failed_stale_file_removal_latches_nothing_and_the_retry_removes_it(self):
        self.packet(ONE_ASK)
        stale_file = self.run_folder_findings_file()
        stale_file.parent.mkdir(parents=True, exist_ok=True)
        stale_file.write_text("- old.ts:9 [smell] an earlier run's finding\n")
        stale_file.parent.chmod(0o500)
        try:
            code, output = self.run_script(["asks-done", "--by", "user", "accepted:ok"])
        finally:
            stale_file.parent.chmod(0o700)

        self.assertNotEqual(code, 0, output)
        self.assertTrue(stale_file.exists())
        state = json.loads(self.state_file().read_text())
        self.assertFalse(state.get("asks_redispatched"), "the print latched before the removal")

        retry_output = self.asks_done("--by", "user", "accepted:ok")

        self.assertFalse(stale_file.exists())
        self.assertIn(review_fix_asks.STALE_RUN_FOLDER_FINDINGS_REMOVED, retry_output)

    def test_asks_done_with_no_stale_run_folder_findings_file_names_no_removal(self):
        output = self.answered(ONE_ASK, "--by", "user", "accepted:ok")

        self.assertNotIn(review_fix_asks.STALE_RUN_FOLDER_FINDINGS_REMOVED, output)


class DeviationLineOwnerTest(unittest.TestCase):
    """Under `--by user` the deviation line of every accepted ask is signed by the user."""

    def test_every_accepted_ask_is_signed_by_the_user_under_by_user(self):
        user_only = {"question": "PLAN-IMPACT: one", "change": "c1", "user_only": True}
        ordinary = {"question": "PLAN-IMPACT: two", "change": "c2"}
        with unittest.mock.patch.object(review_fix_asks.plan_format.script_utils, "git_output",
                                        return_value="Test User"):
            lines = review_fix_asks.accepted_ask_deviation_lines([user_only, ordinary], ["accepted", "accepted"],
                                                                 ["", ""], "user")
        signed = [line for line in lines if "Ruled by" in line]
        self.assertEqual(len(signed), 2)
        for line in signed:
            self.assertIn("Ruled by Test User at", line)


class ApprovalPathsRulingTest(unittest.TestCase):
    """A rejection of a user-only approval ask removes its path from the saved approval paths."""
    setUp = fixture.ReviewFixScriptTest.setUp
    stop_launched_loops = fixture.ReviewFixScriptTest.stop_launched_loops
    fake_command = fixture.ReviewFixScriptTest.fake_command
    environment = fixture.ReviewFixScriptTest.environment
    git = fixture.ReviewFixScriptTest.git
    run_script = fixture.ReviewFixScriptTest.run_script
    packet = fixture.ReviewFixScriptTest.packet

    PATH = "docs dir/CLAUDE.md"

    def approval_packet(self):
        change = approval_asks_store.approval_change(self.PATH)
        entry = ask_entry("edit", f"{self.PATH}:1", finding_id="a1b2c3d4e5f60041", question="approve?", change=change)
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[{**entry, "user_only": True}]))

    def save_paths(self):
        approval_asks_store.write_saved_asks(self.repo, {self.PATH: None, "AGENTS.md": None}, [])

    def assert_user_ruling_drops_the_path(self, outcome):
        self.approval_packet()
        self.save_paths()

        code, output = self.run_script(["asks-done", "--by", "user", outcome])

        self.assertEqual(code, 0, output)
        self.assertEqual(list(approval_asks_store.read_approval_paths(self.repo)), ["AGENTS.md"])

    def test_a_user_rejection_drops_the_path_even_with_a_space_in_a_folder_name(self):
        self.assert_user_ruling_drops_the_path("rejected:keep the edit")

    def test_an_accepted_user_ruling_drops_the_path(self):
        self.assert_user_ruling_drops_the_path("accepted")


    def test_a_damaged_saved_file_stops_a_rejection_with_nothing_logged(self):
        self.approval_packet()
        approval_asks_store.approval_paths_file(self.repo).parent.mkdir(parents=True, exist_ok=True)
        approval_asks_store.approval_paths_file(self.repo).write_text("{")

        code, output = self.run_script(["asks-done", "--by", "user", "rejected:keep the edit"])

        self.assertEqual(code, 2, output)
        self.assertIn("approval-asks.json", output)
        self.assertIn("Nothing was logged", output)

    def test_a_damaged_held_changes_file_stops_a_user_only_ruling_with_nothing_logged(self):
        self.approval_packet()
        held_file = approval_asks_store.held_changes_file(self.repo)
        held_file.parent.mkdir(parents=True, exist_ok=True)
        held_file.write_text("{")

        code, output = self.run_script(["asks-done", "--by", "user", "rejected:keep the edit"])

        self.assertEqual(code, 2, output)
        self.assertIn("held-approval-changes.json", output)
        self.assertIn("Nothing was logged", output)


THIRD_ASK = ask_entry("third", "three.ts:3", finding_id="a1b2c3d4e5f60033", question="third?", change="c3")
USER_ONLY_SECOND_ASK = {**SECOND_ASK, "user_only": True}
HELD_PACKET_ASKS = packet_text(CLEAN_EMPTY_FIELDS, ask=[FIRST_ASK, USER_ONLY_SECOND_ASK, THIRD_ASK])


class HeldAskTest(unittest.TestCase):
    """A session call holds a user-only ask: the plain asks log and print their fix run, the held ask waits in a kept
    packet for the user's own call."""
    setUp = AskRulerTest.setUp
    stop_launched_loops = AskRulerTest.stop_launched_loops
    fake_command = AskRulerTest.fake_command
    environment = AskRulerTest.environment
    git = AskRulerTest.git
    run_script = AskRulerTest.run_script
    packet = AskRulerTest.packet
    ledger_writes = AskRulerTest.ledger_writes
    findings_file = AskRulerTest.findings_file
    asks_done = AskRulerTest.asks_done
    logged_outcomes = AskRulerTest.logged_outcomes
    findings_lines = AskRulerTest.findings_lines
    state_file = AskRulerTest.state_file

    def stored_state(self):
        return json.loads(self.state_file().read_text())

    def hold_the_user_only_ask(self):
        self.packet(HELD_PACKET_ASKS)
        return self.asks_done("--by", "session", "accepted", "held", "accepted")

    def test_a_session_call_logs_the_plain_asks_prints_the_fix_run_and_keeps_the_held_ask_waiting(self):
        output = self.hold_the_user_only_ask()

        self.assertEqual(self.logged_outcomes(), ["accepted", "accepted"])
        self.assertIn("ACTION:", output)
        self.assertEqual(len(self.findings_lines()), 2)
        state = self.stored_state()
        self.assertEqual(state["stage"], "done")
        self.assertEqual([item["finding_id"] for item in state["asks"]],
                         ["a1b2c3d4e5f60031", "a1b2c3d4e5f60033"])
        [kept] = state["waiting_packets"]
        self.assertNotEqual(kept["packet_id"], state["packet_id"])
        self.assertEqual([item["finding_id"] for item in kept["asks"]], ["a1b2c3d4e5f60032"])
        self.assertIn(f"--by user --packet {kept['packet_id']}", output)

    def test_the_kept_packet_carries_the_parents_relaunch_args_and_its_own_id(self):
        repo_args = ["--repo", str(self.repo)]
        parent = {"packet_id": "p1", "relaunch_args": repo_args, "iter": 2, "asks": [{}], "asks_logged": [0]}
        state = {}

        kept = review_fix_asks.keep_held_packet(state, parent, [{"user_only": True, "change": "c"}])

        self.assertEqual(kept["relaunch_args"], repo_args)
        self.assertEqual(approval_asks_store.read_held_changes(self.repo), set(),
                         "the held changes are written after the state is saved, never while the packet is built")
        self.assertEqual(kept["iter"], 2)
        self.assertNotEqual(kept["packet_id"], "p1")
        self.assertNotIn("asks_logged", kept)
        self.assertEqual(state["waiting_packets"], [kept])

    def test_a_session_hold_call_writes_the_held_change_once_the_state_is_saved(self):
        self.hold_the_user_only_ask()

        self.assertEqual(approval_asks_store.read_held_changes(self.repo), {USER_ONLY_SECOND_ASK["change"]})

    def test_a_damaged_held_changes_file_stops_a_session_hold_call_with_nothing_logged(self):
        self.packet(HELD_PACKET_ASKS)
        held_file = approval_asks_store.held_changes_file(self.repo)
        held_file.parent.mkdir(parents=True, exist_ok=True)
        held_file.write_text("{")
        state_before = self.state_file().read_bytes()

        code, output = self.run_script(["asks-done", "--by", "session", "accepted", "held", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("held-approval-changes.json", output)
        self.assertIn("Nothing was logged", output)
        self.assertEqual(self.logged_outcomes(), [])
        self.assertEqual(self.state_file().read_bytes(), state_before)

    def test_a_later_user_call_on_the_kept_packet_logs_the_held_ask(self):
        self.hold_the_user_only_ask()
        kept_id = self.stored_state()["waiting_packets"][0]["packet_id"]

        self.asks_done("--by", "user", "--packet", kept_id, "rejected:keep it")

        self.assertEqual(self.logged_outcomes(), ["accepted", "accepted", "rejected"])
        deciders = [row["ask_decided_by"] for row in self.ledger_writes() if "ask_decided_by" in row]
        self.assertEqual(deciders, ["session", "session", "user"])
        self.assertEqual(self.stored_state()["waiting_packets"], [])

    def assert_refused_with_nothing_logged(self, words, expected_text, packet_asks=HELD_PACKET_ASKS):
        self.packet(packet_asks)
        state_before = self.state_file().read_bytes()
        code, output = self.run_script(["asks-done", *words])
        self.assertEqual(code, 2, output)
        self.assertIn(expected_text, output)
        self.assertEqual(self.logged_outcomes(), [])
        self.assertEqual(self.state_file().read_bytes(), state_before)

    def test_held_on_a_plain_ask_is_refused(self):
        self.assert_refused_with_nothing_logged(
            ["--by", "session", "held", "accepted", "accepted"], "ask 1: held is only for a user_only ask")

    def test_held_in_a_user_call_is_refused(self):
        self.assert_refused_with_nothing_logged(
            ["--by", "user", "accepted", "held", "accepted"], "ask 2: held is for a session call")

    def test_a_session_call_with_a_word_other_than_held_on_a_user_only_ask_names_held_in_the_refusal(self):
        self.assert_refused_with_nothing_logged(
            ["--by", "session", "accepted", "accepted", "accepted"], "A session call gives `held`")

    def test_held_on_every_ask_is_refused(self):
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[USER_ONLY_SECOND_ASK]))
        state_before = self.state_file().read_bytes()
        code, output = self.run_script(["asks-done", "--by", "session", "held"])
        self.assertEqual(code, 2, output)
        self.assertIn("every ask is held", output)
        self.assertEqual(self.logged_outcomes(), [])
        self.assertEqual(self.state_file().read_bytes(), state_before)

    def test_a_refusal_names_the_ask_by_its_place_in_the_stop_when_an_earlier_ask_is_held(self):
        user_only_first = {**FIRST_ASK, "user_only": True}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[user_only_first, USER_ONLY_SECOND_ASK, THIRD_ASK]))
        code, output = self.run_script(["asks-done", "--by", "session", "held", "accepted", "accepted"])
        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 2 are user_only", output)

    def test_a_conditional_change_is_numbered_by_its_place_in_the_stop_when_earlier_asks_are_held(self):
        user_only_first = {**FIRST_ASK, "user_only": True}
        conditional_third = {**THIRD_ASK, "change": "if yes, drop it; if no, keep it"}
        packet_asks = packet_text(CLEAN_EMPTY_FIELDS, ask=[user_only_first, USER_ONLY_SECOND_ASK, conditional_third])
        self.assert_refused_with_nothing_logged(
            ["--by", "session", "held", "held", "accepted"],
            "ask 3 (three.ts:3) has a conditional proposed change", packet_asks)

    def test_a_user_call_with_no_packet_rules_the_held_ask_after_a_hold(self):
        self.hold_the_user_only_ask()

        self.asks_done("--by", "user", "accepted")

        self.assertEqual(self.logged_outcomes(), ["accepted", "accepted", "accepted"])
        self.assertEqual(self.stored_state()["waiting_packets"], [])

    def test_a_hold_on_a_kept_packet_prints_no_retry_sentence(self):
        user_only_first = {**FIRST_ASK, "user_only": True}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[FIRST_ASK, USER_ONLY_SECOND_ASK, THIRD_ASK]))
        parent_id = self.stored_state()["packet_id"]
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[user_only_first]))

        output = self.asks_done("--by", "session", "--packet", parent_id, "accepted", "held", "accepted")

        self.assertIn("--by user --packet", output)
        self.assertNotIn("A retry of this call", output)

    def test_a_kept_parent_whose_plain_row_fails_to_log_prints_the_retry_call(self):
        self.packet(HELD_PACKET_ASKS)
        parent_id = self.stored_state()["packet_id"]
        user_only_first = {**FIRST_ASK, "user_only": True}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[user_only_first]))
        fail_call = fake_ledger.write_call_count(self.ledger_env) + 1

        code, output = self.run_script(
            ["asks-done", "--by", "session", "--packet", parent_id, "accepted", "held", "accepted"],
            FAKE_LEDGER_FAIL_WRITE_CALL=str(fail_call))

        self.assertEqual(code, 0, output)
        self.assertIn("call in the held line below", output)
        self.assertIn(f"A retry of this call is `asks-done --by session --packet {parent_id}", output)

    def test_a_retry_that_logs_nothing_new_reprints_a_waiting_held_ask_when_no_fix_run_was_stored(self):
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[FIRST_ASK, USER_ONLY_SECOND_ASK]))
        self.asks_done("--by", "session", "rejected", "held")
        kept_id = self.stored_state()["waiting_packets"][0]["packet_id"]

        output = self.asks_done("--by", "session", "rejected")

        self.assertIn("already logged", output)
        self.assertIn(f"--by user --packet {kept_id}", output)

    def test_held_on_a_retry_of_a_partly_logged_call_is_refused(self):
        self.packet(HELD_PACKET_ASKS)
        fail_call = fake_ledger.write_call_count(self.ledger_env) + 2
        code, output = self.run_script(["asks-done", "--by", "user", "accepted", "accepted", "accepted"],
                                       FAKE_LEDGER_FAIL_WRITE_CALL=str(fail_call))
        self.assertEqual(code, 0, output)
        state_before = self.state_file().read_bytes()

        code, output = self.run_script(["asks-done", "--by", "session", "accepted", "held", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("a retry gives the outcomes already logged", output)
        self.assertEqual(self.state_file().read_bytes(), state_before)

    def assert_retry_prints_the_launch_line_again(self, *retry_words):
        self.hold_the_user_only_ask()
        kept_id = self.stored_state()["waiting_packets"][0]["packet_id"]

        retry_output = self.asks_done(*retry_words)

        self.assertIn("already logged", retry_output)
        self.assertIn(review_fix_asks.PRINTED_RUN_LINE, retry_output)
        self.assertIn(f"--by user --packet {kept_id}", retry_output)
        self.assertEqual(self.logged_outcomes(), ["accepted", "accepted"])
        self.assertEqual(self.stored_state()["waiting_packets"][0]["packet_id"], kept_id)

    def test_a_retry_with_the_plain_outcomes_and_no_packet_prints_the_launch_line_again(self):
        self.assert_retry_prints_the_launch_line_again("--by", "session", "accepted", "accepted")

    def test_a_retry_naming_the_parent_packet_prints_the_launch_line_again(self):
        self.packet(HELD_PACKET_ASKS)
        parent_id = json.loads(self.state_file().read_text())["packet_id"]
        self.asks_done("--by", "session", "accepted", "held", "accepted")
        kept_id = self.stored_state()["waiting_packets"][0]["packet_id"]
        output = self.asks_done("--by", "session", "--packet", parent_id, "accepted", "accepted")
        self.assertIn("already logged", output)
        self.assertIn(review_fix_asks.PRINTED_RUN_LINE, output)
        self.assertEqual(self.logged_outcomes(), ["accepted", "accepted"])
        self.assertEqual(self.stored_state()["waiting_packets"][0]["packet_id"], kept_id)

    def test_held_is_an_unknown_word_to_a_correction(self):
        self.packet(ONE_ASK)
        self.asks_done("--by", "session", "accepted")
        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "held"])
        self.assertEqual(code, 2, output)
        self.assertIn("is not one of", output)


class ScriptsClaudeMdSessionRulingTest(unittest.TestCase):
    """An ask whose only approval-file change is the scripts CLAUDE.md is ruled by the session; an ask for any other
    approval file stays user_only."""
    setUp = fixture.ReviewFixScriptTest.setUp
    stop_launched_loops = fixture.ReviewFixScriptTest.stop_launched_loops
    fake_command = fixture.ReviewFixScriptTest.fake_command
    environment = fixture.ReviewFixScriptTest.environment
    git = fixture.ReviewFixScriptTest.git
    run_script = fixture.ReviewFixScriptTest.run_script
    packet = fixture.ReviewFixScriptTest.packet
    ledger_writes = fixture.ReviewFixScriptTest.ledger_writes
    findings_file = fixture.ReviewFixScriptTest.findings_file
    state_file = AskRulerTest.state_file
    edit_state = AskRulerTest.edit_state

    PRE_PASS_TEXT = "rules\nuser line\n"
    EDITED_TEXT = "rules\nuser line\ncoder line\n"

    def approval_entry(self, path, user_only):
        change = approval_asks_store.approval_change(path)
        entry = ask_entry("edit", f"{path}:1", finding_id="a1b2c3d4e5f60061", question="approve?", change=change)
        if user_only:
            return {**entry, "user_only": True}
        return entry

    def edited_file(self, path):
        """`path` holding the coder's edit, with the blob of its pre-pass text returned."""
        file = pathlib.Path(self.repo) / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(self.PRE_PASS_TEXT)
        pre_pass_blob = script_utils.work_tree_blob(self.repo, path, keep_object=True)
        file.write_text(self.EDITED_TEXT)
        return pre_pass_blob

    def packet_with_scripts_ask(self):
        scripts_blob = self.edited_file(owner_lines.SCRIPTS_CLAUDE_MD)
        approval_asks_store.write_saved_asks(self.repo, {owner_lines.SCRIPTS_CLAUDE_MD: scripts_blob}, [])
        entry = self.approval_entry(owner_lines.SCRIPTS_CLAUDE_MD, user_only=False)
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[entry, SECOND_ASK]))

    def scripts_text(self):
        return (pathlib.Path(self.repo) / owner_lines.SCRIPTS_CLAUDE_MD).read_text()

    def test_a_session_accepting_the_scripts_claude_md_ask_restores_the_file_and_logs_it(self):
        self.packet_with_scripts_ask()

        code, output = self.run_script(["asks-done", "--by", "session", "accepted", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertEqual(self.scripts_text(), self.PRE_PASS_TEXT)
        self.assertEqual(approval_asks_store.read_approval_paths(self.repo), {})
        self.assertEqual(len(self.ledger_writes()), 2)

    def test_a_session_rejecting_the_scripts_claude_md_ask_keeps_the_edit_and_logs_it(self):
        self.packet_with_scripts_ask()

        code, output = self.run_script(["asks-done", "--by", "session", "rejected:the edit is right", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertEqual(self.scripts_text(), self.EDITED_TEXT)
        self.assertEqual(approval_asks_store.read_approval_paths(self.repo), {})
        self.assertEqual(len(self.ledger_writes()), 2)

    def test_a_session_ruling_is_refused_for_the_other_approval_file_beside_the_scripts_claude_md_ask(self):
        scripts_blob = self.edited_file(owner_lines.SCRIPTS_CLAUDE_MD)
        root_blob = self.edited_file("CLAUDE.md")
        approval_asks_store.write_saved_asks(
            self.repo, {owner_lines.SCRIPTS_CLAUDE_MD: scripts_blob, "CLAUDE.md": root_blob}, [])
        scripts_entry = self.approval_entry(owner_lines.SCRIPTS_CLAUDE_MD, user_only=False)
        root_entry = self.approval_entry("CLAUDE.md", user_only=True)
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[scripts_entry, root_entry]))
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--by", "session", "accepted", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("ask(s) 2 are user_only", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)
        self.assertEqual(self.scripts_text(), self.EDITED_TEXT)

    def test_a_correction_that_touches_no_rejection_leaves_the_scripts_claude_md_edit_and_logs_the_outcome(self):
        self.edited_file(owner_lines.SCRIPTS_CLAUDE_MD)
        approval_asks_store.write_saved_asks(
            self.repo, {owner_lines.SCRIPTS_CLAUDE_MD: approval_asks_store.UNKNOWN_BASE}, [])
        entry = self.approval_entry(owner_lines.SCRIPTS_CLAUDE_MD, user_only=False)
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[entry, SECOND_ASK]))
        self.run_script(["asks-done", "--by", "session", "accepted", "accepted"])
        rows_before = len(self.ledger_writes())
        saved_before = approval_asks_store.read_approval_paths(self.repo)
        correction = f"modified:keep the edit in `{owner_lines.SCRIPTS_CLAUDE_MD}`"

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", correction, "accepted"])

        self.assertEqual(code, 0, output)
        self.assertEqual(saved_before, {}, "the accepted ask left the saved paths")
        self.assertEqual(self.scripts_text(), self.EDITED_TEXT)
        self.assertGreater(len(self.ledger_writes()), rows_before)

    def test_a_correction_of_the_scripts_claude_md_ask_reads_the_packets_repo_not_the_cwd(self):
        """The state sits in the cwd repo while the packet's launch `--repo` names another one, whose saved file is
        damaged: the correction stops on that file, as it does for a user-only ask."""
        self.edited_file(owner_lines.SCRIPTS_CLAUDE_MD)
        approval_asks_store.write_saved_asks(
            self.repo, {owner_lines.SCRIPTS_CLAUDE_MD: approval_asks_store.UNKNOWN_BASE}, [])
        entry = self.approval_entry(owner_lines.SCRIPTS_CLAUDE_MD, user_only=False)
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[entry, SECOND_ASK]))
        self.run_script(["asks-done", "--by", "session", "accepted", "accepted"])
        rows_before = len(self.ledger_writes())
        correction = f"modified:keep the edit in `{owner_lines.SCRIPTS_CLAUDE_MD}`"

        with tempfile.TemporaryDirectory() as packet_repo:
            subprocess.run(["git", "init", "-q", packet_repo], check=True, capture_output=True)
            damaged = approval_asks_store.approval_paths_file(packet_repo)
            damaged.parent.mkdir(parents=True, exist_ok=True)
            damaged.write_text("{")
            self.edit_state(relaunch_args=["--repo", packet_repo])

            code, output = self.run_script(["asks-done", "--correct", "--by", "session", correction, "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("approval-asks.json", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)

    def test_a_correction_after_a_session_accepted_the_scripts_claude_md_ask_is_refused(self):
        self.packet_with_scripts_ask()
        self.run_script(["asks-done", "--by", "session", "accepted", "accepted"])
        rows_before = len(self.ledger_writes())

        code, output = self.run_script(["asks-done", "--correct", "--by", "session", "rejected:keep it", "accepted"])

        self.assertEqual(code, 2, output)
        self.assertIn("already put the file back", output)
        self.assertEqual(len(self.ledger_writes()), rows_before)
        self.assertEqual(self.scripts_text(), self.PRE_PASS_TEXT)


if __name__ == "__main__":
    unittest.main()
