"""Checks for the unread-overwrite check in fork_write_scope.py: a Write of an existing file the session has not read
since it last changed is refused, and the last writer is named."""
import contextlib
import datetime
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import transcript_time
import unread_overwrite

HOOK = pathlib.Path(os.environ.get("FORK_WRITE_SCOPE") or toolkit_paths.GATES_DIR / "fork_write_scope.py")
FILE_MTIME = 1_800_000_000


def stamp(offset_seconds):
    moment = datetime.datetime.fromtimestamp(FILE_MTIME + offset_seconds, datetime.timezone.utc)
    return moment.isoformat().replace("+00:00", "Z")


def result_line(file_path, offset_seconds, kind):
    """One user transcript line holding the tool result of `kind` ("read", "write" or "edit") for the path."""
    if kind == "read":
        tool_result = {"type": "text", "file": {"filePath": file_path, "content": "x"}}
    elif kind == "edit":
        tool_result = {"filePath": file_path, "oldString": "a", "newString": "b", "structuredPatch": [],
                       "userModified": False, "replaceAll": False}
    else:
        tool_result = {"type": "update", "filePath": file_path, "content": "x"}
    return json.dumps({"type": "user", "timestamp": stamp(offset_seconds), "toolUseResult": tool_result},
                      separators=(",", ":"))


class UnreadOverwriteTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name)
        self.config_dir = self.root / "config"
        self.project = self.config_dir / "projects" / "proj"
        self.project.mkdir(parents=True)
        self.shared_log = self.root / "decisions.md"
        self.shared_log.write_text("first session's entries\n")
        os.utime(self.shared_log, (FILE_MTIME, FILE_MTIME))

    def transcript(self, session_id, lines, modified=FILE_MTIME + 100, live=True):
        """A session transcript. The last-writer lookup reads live sessions only, so it gets a live registry row
        unless `live` is False."""
        transcript = self.project / f"{session_id}.jsonl"
        transcript.write_text("\n".join(lines) + "\n")
        os.utime(transcript, (modified, modified))
        if live:
            self.name_session(session_id, None)
        return transcript

    def name_session(self, session_id, name):
        sessions = self.config_dir / "sessions"
        sessions.mkdir(exist_ok=True)
        row = {"pid": os.getpid(), "sessionId": session_id, "name": name}
        row_name = session_id.replace("\0", "_")
        (sessions / f"{row_name}.json").write_text(json.dumps(row))

    def run_raw(self, payload):
        env = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
        env["CLAUDE_CONFIG_DIR"] = str(self.config_dir)
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True,
                              capture_output=True, env=env, check=False)

    def run_hook(self, file_path, transcript, agent_id=None):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(file_path), "content": "second"},
                   "transcript_path": str(transcript)}
        if agent_id:
            payload["agent_id"] = agent_id
        result = self.run_raw(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        if not result.stdout.strip():
            return None
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    def test_a_second_session_write_to_an_unread_file_is_refused_with_the_last_writer_named(self):
        self.transcript("first-id", [result_line(str(self.shared_log), 10, "write")])
        self.name_session("first-id", "lane-one")
        second = self.transcript("second-id", [result_line(str(self.root / "other.md"), 5, "read")])
        reason = self.run_hook(self.shared_log, second)
        self.assertIsNotNone(reason)
        self.assertIn("lane-one", reason)
        self.assertIn(str(self.shared_log), reason)

    def test_an_unnamed_last_writer_is_named_by_session_id(self):
        self.transcript("first-id", [result_line(str(self.shared_log), 10, "edit")])
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("first-id", reason)

    def test_a_file_no_live_session_wrote_says_so(self):
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("no live Claude session's Write, Edit or Bash edit of it was found", reason)
        self.assertIn("a process outside any live Claude session", reason)

    def test_a_write_with_no_transcript_path_passes_silently(self):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(self.shared_log), "content": "x"}}
        result = self.run_raw(payload)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")

    def test_an_at_mentioned_file_counts_as_a_read(self):
        content = {"file": {"filePath": str(self.shared_log)}}
        attachment = json.dumps({"type": "attachment", "timestamp": stamp(10),
                                 "attachment": {"type": "file", "content": content}},
                                separators=(",", ":"))
        second = self.transcript("second-id", [attachment])
        self.assertIsNone(self.run_hook(self.shared_log, second))

    def attachment_line(self, offset_seconds, attachment_type="file", content=None):
        if content is None:
            content = {"file": {"filePath": str(self.shared_log)}}
        attachment = {"type": attachment_type, "content": content, "filePath": str(self.shared_log)}
        return json.dumps({"type": "attachment", "timestamp": stamp(offset_seconds), "attachment": attachment},
                          separators=(",", ":"))

    def test_an_attachment_is_not_named_as_the_writer(self):
        self.transcript("first-id", [self.attachment_line(10)])
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("no live Claude session's Write, Edit or Bash edit of it was found", reason)
        self.assertNotIn("first-id", reason)

    def test_an_attachment_that_is_not_a_file_read_counts_as_nothing(self):
        cases = {"other attachment type": self.attachment_line(30, attachment_type="hook_success"),
                 "content without a file key": self.attachment_line(30, content={"text": "x"})}
        for label, attachment in cases.items():
            with self.subTest(label):
                lines = [result_line(str(self.shared_log), -30, "read"), attachment]
                second = self.transcript("second-id", lines)
                self.assertIsNotNone(self.run_hook(self.shared_log, second), label)

    def test_the_event_named_agent_transcript_path_is_read(self):
        session = self.transcript("second-id", [])
        self.subagent_transcript(session, "abc", [])
        elsewhere = self.root / "elsewhere" / "agent-abc.jsonl"
        elsewhere.parent.mkdir()
        elsewhere.write_text(result_line(str(self.shared_log), 30, "read") + "\n")
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(self.shared_log), "content": "x"},
                   "transcript_path": str(session), "agent_id": "abc", "agent_transcript_path": str(elsewhere)}
        result = self.run_raw(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertEqual(result.stderr, "")

    def run_code_fork(self, transcript):
        payload = {"tool_name": "Write", "agent_type": "code-fork",
                   "tool_input": {"file_path": str(self.shared_log), "content": "x"},
                   "transcript_path": str(transcript)}
        result = self.run_raw(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    def test_a_code_fork_unread_write_gets_the_unread_overwrite_deny(self):
        second = self.transcript("second-id", [])
        reason = self.run_code_fork(second)
        self.assertTrue(reason.startswith("unread-overwrite:"), reason)
        self.assertIn(str(self.shared_log), reason)

    def test_a_code_fork_write_that_passes_the_read_check_still_gets_the_fork_deny(self):
        second = self.transcript("second-id", [result_line(str(self.shared_log), 30, "read")])
        reason = self.run_code_fork(second)
        self.assertTrue(reason.startswith("fork-write-scope: code-fork writes only"), reason)

    def test_a_code_fork_write_to_an_existing_run_folder_file_it_read_is_allowed(self):
        run_folder = self.root / "repo" / "code-phase"
        run_folder.mkdir(parents=True)
        (run_folder.parent / "HEAD").write_text("ref: refs/heads/main\n")
        handoff = run_folder / "handoff.txt"
        handoff.write_text("old\n")
        os.utime(handoff, (FILE_MTIME, FILE_MTIME))
        second = self.transcript("second-id", [result_line(str(handoff), 30, "read")])
        payload = {"tool_name": "Write", "agent_type": "code-fork",
                   "tool_input": {"file_path": str(handoff), "content": "x"}, "transcript_path": str(second)}
        result = self.run_raw(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def bash_edit_line(self, file_path, offset_seconds):
        """A user line as Claude Code records a Bash command that changed `file_path`."""
        tool_result = {"stdout": "", "bashEditDiff": {"files": [{"filePath": file_path, "hunks": []}]}}
        return json.dumps({"type": "user", "timestamp": stamp(offset_seconds), "toolUseResult": tool_result},
                          separators=(",", ":"))

    def test_the_sessions_own_bash_edit_lets_the_write_through(self):
        second = self.transcript("second-id", [self.bash_edit_line(str(self.shared_log), 30)])
        self.assertIsNone(self.run_hook(self.shared_log, second))

    def test_another_sessions_bash_edit_is_refused_and_names_that_session(self):
        self.transcript("first-id", [self.bash_edit_line(str(self.shared_log), 10)])
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("first-id", reason)

    def test_a_result_with_an_unreadable_timestamp_is_reported_not_skipped(self):
        path = str(self.shared_log)
        for label, line_object in {
            "missing": {"type": "user", "toolUseResult": {"filePath": path}},
            "not a string": {"type": "user", "timestamp": 5, "toolUseResult": {"filePath": path}},
            "unparseable": {"type": "user", "timestamp": "soon", "toolUseResult": {"filePath": path}},
        }.items():
            with self.subTest(label):
                second = self.transcript("second-id", [result_line(path, 30, "read"),
                                                    json.dumps(line_object, separators=(",", ":"))])
                result = self.run_raw({"tool_name": "Write", "tool_input": {"file_path": path, "content": "x"},
                                       "transcript_path": str(second)})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "", label)
                self.assertIn("the unread-overwrite check crashed", result.stderr)
                self.assertIn(str(second), result.stderr)
                self.assertIn(path, result.stderr)

    def test_a_writer_line_with_an_unreadable_timestamp_keeps_the_deny_and_names_the_error(self):
        path = str(self.shared_log)
        bad_line = {"type": "user", "timestamp": "soon", "toolUseResult": {"filePath": path}}
        first = self.transcript("first-id", [json.dumps(bad_line, separators=(",", ":"))])
        second = self.transcript("second-id", [])
        result = self.run_raw({"tool_name": "Write", "tool_input": {"file_path": path, "content": "x"},
                               "transcript_path": str(second)})
        self.assertEqual(result.returncode, 0, result.stderr)
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("writer could not be looked up (TranscriptStampError", reason)
        self.assertIn(str(first), reason)
        self.assertIn("last-writer lookup crashed", result.stderr)

    def test_a_read_through_a_symlink_does_not_count_for_the_real_path(self):
        link = self.root / "link.md"
        link.symlink_to(self.shared_log)
        second = self.transcript("second-id", [result_line(str(link), 30, "read")])
        self.assertIsNotNone(self.run_hook(self.shared_log, second))

    def test_a_writer_whose_transcript_is_older_than_the_mtime_is_not_named(self):
        self.transcript("first-id", [result_line(str(self.shared_log), 10, "write")], modified=FILE_MTIME - 100)
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertNotIn("first-id", reason)

    def test_a_directory_as_transcript_lets_the_write_through_and_names_the_error(self):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(self.shared_log), "content": "x"},
                   "transcript_path": str(self.root)}
        result = self.run_raw(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("fork-write-scope: the unread-overwrite check could not read", result.stderr)
        self.assertIn("IsADirectoryError", result.stderr)

    def test_a_read_of_a_relative_path_spelling_does_not_count(self):
        relative = os.path.relpath(self.shared_log)
        second = self.transcript("second-id", [result_line(relative, 30, "read")])
        self.assertIsNotNone(self.run_hook(self.shared_log, second))

    def test_a_read_at_or_after_the_mtime_lets_the_write_through(self):
        for offset in (0, 30):
            with self.subTest(offset=offset):
                second = self.transcript("second-id", [result_line(str(self.shared_log), offset, "read")])
                self.assertIsNone(self.run_hook(self.shared_log, second))

    def test_the_sessions_own_write_result_counts_as_having_seen_the_content(self):
        second = self.transcript("second-id", [result_line(str(self.shared_log), 30, "write")])
        self.assertIsNone(self.run_hook(self.shared_log, second))

    def test_a_read_before_the_mtime_is_refused(self):
        second = self.transcript("second-id", [result_line(str(self.shared_log), -30, "read")])
        self.assertIsNotNone(self.run_hook(self.shared_log, second))

    def test_the_latest_result_decides_when_an_old_read_is_followed_by_a_stale_one(self):
        lines = [result_line(str(self.shared_log), 30, "read"), result_line(str(self.shared_log), -30, "read")]
        second = self.transcript("second-id", lines)
        self.assertIsNotNone(self.run_hook(self.shared_log, second))

    def test_a_new_file_an_empty_file_and_a_directory_are_not_refused(self):
        second = self.transcript("second-id", [])
        empty = self.root / "empty.md"
        empty.write_text("")
        for target in (self.root / "missing.md", empty, self.root):
            with self.subTest(target=target.name):
                self.assertIsNone(self.run_hook(target, second))

    def subagent_transcript(self, session, agent_id, lines):
        subagents = session.with_suffix("") / "subagents"
        subagents.mkdir(parents=True, exist_ok=True)
        transcript = subagents / f"agent-{agent_id}.jsonl"
        transcript.write_text("\n".join(lines) + ("\n" if lines else ""))
        return transcript

    def test_an_empty_subagent_transcript_is_refused_even_when_the_session_read_the_file(self):
        session = self.transcript("second-id", [result_line(str(self.shared_log), 30, "read")])
        self.subagent_transcript(session, "abc", [])
        self.assertIsNotNone(self.run_hook(self.shared_log, session, agent_id="abc"))

    def test_a_subagent_read_lets_the_write_through(self):
        session = self.transcript("second-id", [])
        self.subagent_transcript(session, "abc", [result_line(str(self.shared_log), 30, "read")])
        self.assertIsNone(self.run_hook(self.shared_log, session, agent_id="abc"))

    def test_a_subagent_that_wrote_last_is_named_by_agent_and_parent_session(self):
        first = self.transcript("first-id", [], modified=FILE_MTIME - 100)
        agent = self.subagent_transcript(first, "abc", [result_line(str(self.shared_log), 10, "write")])
        os.utime(agent, (FILE_MTIME + 100, FILE_MTIME + 100))
        self.name_session("first-id", "lane-one")
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("subagent abc of lane-one", reason)

    def test_a_transcript_of_a_session_that_is_not_live_is_not_read(self):
        self.transcript("gone-id", [result_line(str(self.shared_log), 10, "write")], live=False)
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("no live Claude session's Write, Edit or Bash edit of it was found", reason)
        self.assertNotIn("gone-id", reason)

    def test_a_crash_in_the_writer_lookup_keeps_the_deny(self):
        second = self.transcript("second-id", [])
        stderr = io.StringIO()
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config_dir)}), \
                mock.patch.object(unread_overwrite, "last_writer", side_effect=RuntimeError("lookup broke")), \
                contextlib.redirect_stderr(stderr):
            reason = unread_overwrite.unread_overwrite_reason(str(self.shared_log),
                                                              {"transcript_path": str(second)})
        self.assertIn("writer could not be looked up (RuntimeError: lookup broke)", reason)
        self.assertIn("fork-write-scope: the unread-overwrite last-writer lookup crashed", stderr.getvalue())

    def test_a_write_stamped_before_the_mtime_is_not_named_as_the_writer(self):
        self.transcript("first-id", [result_line(str(self.shared_log), -10, "write")])
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("no live Claude session's Write, Edit or Bash edit of it was found", reason)
        self.assertNotIn("first-id", reason)

    def test_a_write_stamped_at_the_mtime_is_named_as_the_writer(self):
        self.transcript("first-id", [result_line(str(self.shared_log), 0, "write")])
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("first-id", reason)

    def test_the_last_of_two_writers_is_named(self):
        # Registry rows list in id order, so the older writer's id sorts first: only the mtime sort puts the newer
        # writer ahead of it.
        self.transcript("a-older-id", [result_line(str(self.shared_log), 10, "write")], modified=FILE_MTIME + 100)
        self.transcript("z-newer-id", [result_line(str(self.shared_log), 20, "write")], modified=FILE_MTIME + 200)
        second = self.transcript("zz-second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("z-newer-id", reason)
        self.assertNotIn("a-older-id", reason)

    def test_lines_that_hold_the_path_but_are_not_results_do_not_hide_an_earlier_read(self):
        path = str(self.shared_log)
        not_a_result = json.dumps({"type": "assistant", "x": {"filePath": path}}, separators=(",", ":"))
        truncated = '{"type":"user","toolUseResult":{"filePath":' + json.dumps(path)
        lines = [result_line(path, 30, "read"), not_a_result, truncated]
        second = self.transcript("second-id", lines)
        self.assertIsNone(self.run_hook(self.shared_log, second))

    def test_another_sessions_read_after_the_mtime_is_not_a_writer(self):
        self.transcript("first-id", [result_line(str(self.shared_log), 10, "read")])
        second = self.transcript("second-id", [])
        reason = self.run_hook(self.shared_log, second)
        self.assertIn("no live Claude session's Write, Edit or Bash edit of it was found", reason)

    def test_a_non_ascii_path_read_at_the_mtime_lets_the_write_through(self):
        target = self.root / "é.md"
        target.write_text("entries\n")
        os.utime(target, (FILE_MTIME, FILE_MTIME))
        escaped_line = json.loads(result_line(str(target), 0, "read"))
        second = self.transcript("second-id", [json.dumps(escaped_line, ensure_ascii=False, separators=(",", ":"))])
        self.assertIsNone(self.run_hook(target, second))

    def test_a_result_in_the_same_millisecond_as_the_mtime_counts_as_seen(self):
        os.utime(self.shared_log, (FILE_MTIME + 0.1236, FILE_MTIME + 0.1236))
        line = json.dumps({"type": "user", "timestamp": stamp(0.123),
                           "toolUseResult": {"type": "update", "filePath": str(self.shared_log)}},
                          separators=(",", ":"))
        second = self.transcript("second-id", [line])
        self.assertIsNone(self.run_hook(self.shared_log, second))

    def test_a_crash_in_the_check_lets_the_write_through_and_names_the_gate(self):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(self.shared_log), "content": "x"},
                   "transcript_path": "bad\0path"}
        result = self.run_raw(payload)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("fork-write-scope", result.stderr)

    def test_a_malformed_tool_input_produces_no_output(self):
        for tool_input in ("text", {"file_path": 5}, {}):
            with self.subTest(tool_input=tool_input):
                result = self.run_raw({"tool_name": "Write", "tool_input": tool_input, "transcript_path": "x"})
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout.strip(), "")

    def test_a_missing_transcript_lets_the_write_through(self):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(self.shared_log), "content": "x"},
                   "transcript_path": str(self.root / "no-such.jsonl")}
        result = self.run_raw(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")
        self.assertIn("fork-write-scope: the unread-overwrite check could not read", result.stderr)
        self.assertIn("FileNotFoundError", result.stderr)


class EpochOfTimestampTest(unittest.TestCase):
    def test_a_timestamp_with_no_offset_is_read_as_utc(self):
        naive = transcript_time.epoch_of_timestamp("2026-11-15T06:22:12.305")
        zulu = transcript_time.epoch_of_timestamp("2026-11-15T06:22:12.305Z")
        self.assertEqual(naive, zulu)

    def test_the_fraction_of_a_second_is_kept(self):
        whole = transcript_time.epoch_of_timestamp("2026-11-15T06:22:12Z")
        fractional = transcript_time.epoch_of_timestamp("2026-11-15T06:22:12.305Z")
        self.assertAlmostEqual(fractional - whole, 0.305, places=3)

    def test_text_that_is_not_a_timestamp_raises_value_error(self):
        with self.assertRaises(ValueError):
            transcript_time.epoch_of_timestamp("soon")


if __name__ == "__main__":
    unittest.main()
