"""lib/human_turn_lookup.py: a relay is backed by a real user turn of one live named session, or the lookup
refuses."""
import json
import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import human_turn_lookup
from human_turn_lookup import HumanTurnRefusedError

NAME = "relay-session"
SESSION_ID = "11111111-2222-3333-4444-555555555555"
ASKED_AT = human_turn_lookup.epoch_of_timestamp("2026-11-15T06:00:00.000Z")


def user_row(content, origin=None, timestamp="2026-11-15T06:22:12.305Z", **extra):
    """A transcript user row in the shape Claude Code writes."""
    row = {"type": "user", "message": {"role": "user", "content": content}, "timestamp": timestamp}
    if origin is not None:
        row["origin"] = origin
    row.update(extra)
    return row


HUMAN = {"kind": "human"}
PEER = {"kind": "peer", "from": "orchestrator"}


class HumanTurnLookupTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.home = pathlib.Path(temp.name)
        (self.home / "sessions").mkdir()
        (self.home / "projects" / "-some-project").mkdir(parents=True)
        config_env = unittest.mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.home)})
        config_env.start()
        self.addCleanup(config_env.stop)

    def register(self, name=NAME, session_id=SESSION_ID, pid=None, file_name="1.json"):
        row = {"pid": os.getpid() if pid is None else pid, "name": name, "sessionId": session_id}
        (self.home / "sessions" / file_name).write_text(json.dumps(row))

    def transcript(self, rows, folder="-some-project", session_id=SESSION_ID):
        folder_path = self.home / "projects" / folder
        folder_path.mkdir(parents=True, exist_ok=True)
        (folder_path / f"{session_id}.jsonl").write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    def verified(self, after=ASKED_AT):
        return human_turn_lookup.verified_human_turn(NAME, after)

    def refused(self, after=ASKED_AT):
        with self.assertRaises(HumanTurnRefusedError) as caught:
            self.verified(after)
        return str(caught.exception)

    def test_a_human_turn_after_the_ask_is_returned_with_its_time_and_no_words(self):
        self.register()
        self.transcript([user_row("  rule it accepted\n", HUMAN)])
        turn = self.verified()
        self.assertEqual(turn.timestamp, "2026-11-15T06:22:12.305Z")
        self.assertGreater(turn.epoch, ASKED_AT)
        self.assertNotIn("rule it accepted", repr(turn))

    def test_the_latest_turn_is_returned(self):
        self.register()
        self.transcript([user_row("rule it accepted", HUMAN, timestamp="2026-11-15T06:10:00.000Z"),
                         user_row("rule it accepted", HUMAN, timestamp="2026-11-15T06:30:00.000Z")])
        self.assertEqual(self.verified().timestamp, "2026-11-15T06:30:00.000Z")

    def test_a_peer_message_is_not_a_user_turn(self):
        self.register()
        self.transcript([user_row("rule it accepted", PEER)])
        self.assertIn("no human turn", self.refused())

    def test_a_row_with_no_origin_is_not_a_user_turn(self):
        self.register()
        self.transcript([user_row("rule it accepted")])
        self.assertIn("no human turn", self.refused())

    def test_a_tool_result_list_is_not_a_user_turn(self):
        self.register()
        content = [{"type": "tool_result", "tool_use_id": "t1", "content": "rule it accepted"}]
        self.transcript([user_row(content, HUMAN)])
        self.assertIn("no human turn", self.refused())

    def test_a_compact_summary_is_not_a_user_turn(self):
        self.register()
        self.transcript([user_row("rule it accepted", HUMAN, isCompactSummary=True)])
        self.assertIn("no human turn", self.refused())

    def test_a_meta_row_is_not_a_user_turn(self):
        self.register()
        self.transcript([user_row("rule it accepted", HUMAN, isMeta=True)])
        self.assertIn("no human turn", self.refused())

    def test_an_assistant_row_is_not_a_user_turn(self):
        self.register()
        row = {"type": "assistant", "origin": HUMAN, "message": {"role": "assistant", "content": "rule it accepted"},
               "timestamp": "2026-11-15T06:22:12.305Z"}
        self.transcript([row])
        self.assertIn("no human turn", self.refused())

    def test_a_turn_older_than_the_ask_is_refused(self):
        self.register()
        self.transcript([user_row("rule it accepted", HUMAN, timestamp="2026-11-15T05:59:59.000Z")])
        self.assertIn("older than the ask", self.refused())

    def test_a_turn_typed_at_the_very_moment_of_the_ask_is_refused(self):
        self.register()
        self.transcript([user_row("rule it accepted", HUMAN, timestamp="2026-11-15T06:00:00.000Z")])
        self.assertIn("older than the ask", self.refused())

    def test_a_registry_row_with_no_session_id_is_refused(self):
        for message, session_id in (("empty", ""), ("missing", None)):
            with self.subTest(message):
                self.register(session_id=session_id)
                if session_id is None:
                    row = json.loads((self.home / "sessions" / "1.json").read_text())
                    del row["sessionId"]
                    (self.home / "sessions" / "1.json").write_text(json.dumps(row))
                self.assertIn("holds no sessionId", self.refused())

    def test_an_unreadable_transcript_is_refused(self):
        self.register()
        folder = self.home / "projects" / "-some-project"
        (folder / f"{SESSION_ID}.jsonl").mkdir()
        self.assertIn("cannot read the transcript", self.refused())

    def test_an_invalid_byte_on_another_line_does_not_hide_the_human_turn(self):
        self.register()
        folder = self.home / "projects" / "-some-project"
        human_line = json.dumps(user_row("rule it accepted", HUMAN)).encode()
        (folder / f"{SESSION_ID}.jsonl").write_bytes(b'{"note": "bad \xff byte"}\n' + human_line + b"\n")
        self.assertEqual(self.verified().timestamp, "2026-11-15T06:22:12.305Z")

    def test_a_user_turn_with_a_missing_or_garbage_timestamp_is_skipped(self):
        self.register()
        no_timestamp = user_row("rule it accepted", HUMAN)
        del no_timestamp["timestamp"]
        self.transcript([no_timestamp, user_row("rule it accepted", HUMAN, timestamp="not a time"),
                         user_row("rule it accepted", HUMAN, timestamp=12)])
        self.assertIn("no human turn", self.refused())

    def test_a_row_with_a_bool_pid_is_not_live(self):
        (self.home / "sessions" / "1.json").write_text(json.dumps({"pid": True, "name": NAME, "sessionId": SESSION_ID}))
        self.transcript([user_row("rule it accepted", HUMAN)])
        self.assertIn("no live session named", self.refused())

    def test_a_row_with_a_pid_past_the_int_range_is_not_live(self):
        self.register(pid=10**30)
        self.transcript([user_row("rule it accepted", HUMAN)])
        self.assertIn("no live session named", self.refused())

    def test_without_a_config_dir_the_registry_and_transcripts_are_under_the_home_claude_folder(self):
        with tempfile.TemporaryDirectory() as fake_home:
            claude_folder = pathlib.Path(fake_home) / ".claude"
            (claude_folder / "sessions").mkdir(parents=True)
            (claude_folder / "projects" / "-some-project").mkdir(parents=True)
            row = {"pid": os.getpid(), "name": NAME, "sessionId": SESSION_ID}
            (claude_folder / "sessions" / "1.json").write_text(json.dumps(row))
            transcript = claude_folder / "projects" / "-some-project" / f"{SESSION_ID}.jsonl"
            transcript.write_text(json.dumps(user_row("rule it accepted", HUMAN)) + "\n")
            with unittest.mock.patch.dict(os.environ, {"HOME": fake_home}):
                os.environ.pop("CLAUDE_CONFIG_DIR")
                turn = self.verified()
        self.assertEqual(turn.timestamp, "2026-11-15T06:22:12.305Z")

    def test_a_typed_turn_with_an_appended_reminder_is_a_user_turn(self):
        self.register()
        self.transcript([user_row("rule it accepted\n<system-reminder>x</system-reminder>", HUMAN)])
        self.assertEqual(self.verified().timestamp, "2026-11-15T06:22:12.305Z")

    def test_a_sidechain_turn_is_not_a_human_turn(self):
        self.register()
        self.transcript([user_row("rule it accepted", HUMAN, isSidechain=True)])
        self.assertIn("no human turn", self.refused())

    def test_any_typed_human_turn_backs_the_relay(self):
        self.register()
        self.transcript([user_row("something else", HUMAN)])
        self.assertEqual(self.verified().timestamp, "2026-11-15T06:22:12.305Z")

    def test_a_blank_human_turn_is_not_a_typed_turn(self):
        self.register()
        self.transcript([user_row("  ", HUMAN)])
        self.assertIn("no human turn", self.refused())

    def test_no_registry_row_is_refused(self):
        self.transcript([user_row("rule it accepted", HUMAN)])
        self.assertIn("no live session named", self.refused())

    def test_a_row_whose_pid_is_dead_is_not_live(self):
        self.register(pid=2 ** 22 + 12345)
        self.transcript([user_row("rule it accepted", HUMAN)])
        self.assertIn("no live session named", self.refused())

    def test_a_key_file_in_the_registry_folder_is_left_out(self):
        self.register()
        (self.home / "sessions" / "x.key.json").write_text("not json")
        (self.home / "sessions" / "list.json").write_text("[1, 2]")
        self.transcript([user_row("rule it accepted", HUMAN)])
        self.assertEqual(self.verified().timestamp, "2026-11-15T06:22:12.305Z")

    def test_two_live_rows_with_one_name_are_refused(self):
        self.register(file_name="1.json")
        self.register(file_name="2.json", session_id="99999999-2222-3333-4444-555555555555")
        self.transcript([user_row("rule it accepted", HUMAN)])
        self.assertIn("2 live sessions", self.refused())

    def test_no_transcript_is_refused(self):
        self.register()
        self.assertIn("no transcript", self.refused())

    def test_the_transcript_is_found_under_another_project_folder(self):
        self.register()
        self.transcript([user_row("rule it accepted", HUMAN)], folder="-an-unrelated-folder")
        self.assertEqual(self.verified().timestamp, "2026-11-15T06:22:12.305Z")

    def test_two_transcripts_of_one_session_id_are_refused(self):
        self.register()
        self.transcript([user_row("rule it accepted", HUMAN)], folder="-one")
        self.transcript([user_row("rule it accepted", HUMAN)], folder="-two")
        self.assertIn("2 transcripts", self.refused())

    def test_an_unparsable_transcript_line_is_skipped(self):
        self.register()
        folder = self.home / "projects" / "-some-project"
        good = json.dumps(user_row("rule it accepted", HUMAN))
        (folder / f"{SESSION_ID}.jsonl").write_text("{not json\n" + good + "\n")
        self.assertEqual(self.verified().timestamp, "2026-11-15T06:22:12.305Z")

    def test_a_timestamp_with_an_offset_and_one_with_z_read_the_same_moment(self):
        zulu = human_turn_lookup.epoch_of_timestamp("2026-11-15T06:22:12.305Z")
        offset = human_turn_lookup.epoch_of_timestamp("2026-11-15T07:22:12.305+01:00")
        self.assertEqual(zulu, offset)


if __name__ == "__main__":
    unittest.main()
