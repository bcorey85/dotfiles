"""The ask-findings file names who changed a modified ask: the user for `asks-done --by user`, the session for
`--by session`, and no one when the state does not say."""
import json
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_fix_asks
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


class AskRulerTest(unittest.TestCase):
    # The real asks-done runs against a temp repo, set up as the review-fix script tests set it up.
    setUp = fixture.ReviewFixScriptTest.setUp
    stop_launched_loops = fixture.ReviewFixScriptTest.stop_launched_loops
    fake_command = fixture.ReviewFixScriptTest.fake_command
    environment = fixture.ReviewFixScriptTest.environment
    git = fixture.ReviewFixScriptTest.git
    run_script = fixture.ReviewFixScriptTest.run_script
    packet = fixture.ReviewFixScriptTest.packet

    def asks_done(self, *words):
        code, output = self.run_script(["asks-done", *words])
        self.assertEqual(code, 0, output)
        return output

    def findings_lines(self):
        findings_file = script_utils.git_path(self.repo, "review-fix") / "ask-findings.md"
        return findings_file.read_text().splitlines()

    def state_file(self):
        return self.repo / ".git" / "review-fix" / "state.json"

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

    def test_a_modified_ask_ruled_by_the_session_names_the_session_not_the_user(self):
        self.answered(ONE_ASK, "--by", "session", "modified:cap at 5")
        self.assertEqual(self.findings_lines(),
                         ["- one.ts:1 [smell] Proposed change: c1 " + SESSION_SENTENCE + "cap at 5"])
        self.assertNotIn("The user changed it", self.findings_lines()[0])

    def test_a_converted_ask_names_its_ruler_in_both_branches(self):
        converted = {"question": "Apply it anyway?", "change": "src/a.py:3 [bug] cap it",
                     "file_line": "src/a.py:3", "class": "bug", review_fix_asks.USER_RULED_KEY: True}
        cases = [("user", USER_SENTENCE), ("session", SESSION_SENTENCE), (None, NEUTRAL_SENTENCE),
                 ("robot", NEUTRAL_SENTENCE)]
        for decided_by, sentence in cases:
            with self.subTest(decided_by=decided_by):
                text = review_fix_asks.ask_finding_text(converted, "cap at 5", decided_by)
                self.assertEqual(text, "src/a.py:3 [bug] cap it " + sentence + "cap at 5")
                plain = review_fix_asks.ask_finding_text({**converted, review_fix_asks.USER_RULED_KEY: False,
                                                          "change": "cap it"}, "cap at 5", decided_by)
                self.assertEqual(plain, "src/a.py:3 [bug] Proposed change: cap it " + sentence + "cap at 5")

    def assert_uncorrected_ask_is_neutral_for(self, first_decider):
        self.answered(TWO_ASKS, "--by", "user", "modified:one", "modified:two")
        self.edit_state(asks_decided_by=[first_decider, "user"])
        self.asks_done("--correct", "--by", "user", "modified:one", "modified:three")
        lines = self.findings_lines()
        self.assertTrue(lines[0].endswith(NEUTRAL_SENTENCE + "one"), lines[0])
        self.assertTrue(lines[1].endswith(USER_SENTENCE + "three"), lines[1])

    def test_a_none_ruler_in_the_state_gets_the_neutral_sentence_never_the_user(self):
        self.assert_uncorrected_ask_is_neutral_for(None)

    def test_an_unknown_ruler_word_in_the_state_gets_the_neutral_sentence_never_the_user(self):
        self.assert_uncorrected_ask_is_neutral_for("robot")

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
        code, output = self.run_script(["asks-done", "--correct", "--by", "user", "modified:one", "modified:three"])
        self.assertEqual(code, 2, output)
        self.assertIn(review_fix_asks.ASKS_DECIDED_BY_KEY, output)

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


if __name__ == "__main__":
    unittest.main()
