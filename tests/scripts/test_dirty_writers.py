"""lib/dirty_writers.py: a live session in a repo is a holder only when its transcripts show a write to a dirty path."""
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths
import transcript_lines

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import dirty_writers

AFTER_HEAD = transcript_lines.AFTER_HEAD
BEFORE_HEAD = "2000-01-01T00:00:00Z"


class DirtyWritersTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        scratch = pathlib.Path(temp.name).resolve()
        self.repo = scratch / "repo"
        self.repo.mkdir()
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "init", "-q"], check=True)
        (self.repo / "a.py").write_text("a\n")
        subprocess.run([*git, "add", "."], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "base"], check=True)
        self.config = scratch / "config"
        (self.config / "sessions").mkdir(parents=True)
        (self.config / "projects" / "p").mkdir(parents=True)
        environment = unittest.mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": str(self.config)})
        environment.start()
        self.addCleanup(environment.stop)

    def live_session(self, session_id):
        row = {"pid": os.getpid(), "sessionId": session_id, "name": f"name-{session_id}", "cwd": str(self.repo)}
        (self.config / "sessions" / f"{session_id}.json").write_text(json.dumps(row))

    def transcript(self, session_id, edited, timestamp=AFTER_HEAD):
        text = transcript_lines.edit_lines(edited, timestamp)
        (self.config / "projects" / "p" / f"{session_id}.jsonl").write_text(text)

    def holder(self, dirty=("a.py",)):
        found = dirty_writers.holder_with_paths(str(self.repo), list(dirty), "own")
        return None if found is None else found.row

    def test_a_write_in_the_other_sessions_subagent_transcript_makes_it_the_holder(self):
        self.live_session("other")
        self.transcript("other", [])
        subagents = self.config / "projects" / "p" / "other" / "subagents"
        subagents.mkdir(parents=True)
        (subagents / "agent-x.jsonl").write_text(transcript_lines.edit_lines([self.repo / "a.py"]))

        self.assertEqual(self.holder()["sessionId"], "other")

    def test_a_live_other_session_that_wrote_nothing_is_not_a_holder(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "elsewhere.py"])

        self.assertIsNone(self.holder())

    def test_a_live_other_session_with_no_transcript_is_not_a_holder(self):
        self.live_session("other")

        self.assertIsNone(self.holder())

    def test_a_live_other_session_that_wrote_a_dirty_path_is_the_holder(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"])

        self.assertEqual(self.holder()["sessionId"], "other")

    def test_a_write_before_the_head_commit_is_no_evidence(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"], timestamp=BEFORE_HEAD)

        self.assertIsNone(self.holder())

    def test_two_writers_name_no_holder(self):
        for session_id in ("one", "two"):
            self.live_session(session_id)
            self.transcript(session_id, [self.repo / "a.py"])

        self.assertIsNone(self.holder())

    def test_a_write_by_the_own_session_too_names_no_holder(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"])
        self.transcript("own", [self.repo / "a.py"])

        self.assertIsNone(self.holder())

    def test_a_path_the_own_session_wrote_is_left_out_and_the_other_writers_paths_are_returned(self):
        (self.repo / "b.py").write_text("b\n")
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py", self.repo / "b.py"])
        self.transcript("own", [self.repo / "a.py"])

        found = dirty_writers.holder_with_paths(str(self.repo), ["a.py", "b.py"], "own")

        self.assertEqual((found.row["sessionId"], found.paths), ("other", ["b.py"]))

    def test_a_second_live_session_whose_transcript_is_missing_names_no_holder(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"])
        self.live_session("silent")

        self.assertIsNone(self.holder())

    def test_no_dirty_path_or_no_own_session_id_names_no_holder(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"])

        self.assertIsNone(self.holder(dirty=()))
        self.assertIsNone(dirty_writers.holder_with_paths(str(self.repo), ["a.py"], ""))

    def test_a_write_call_with_a_relative_path_is_no_evidence(self):
        self.live_session("other")
        self.transcript("other", ["a.py"])

        self.assertIsNone(self.holder())

    def test_an_unknown_head_commit_time_names_no_holder(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"])

        with unittest.mock.patch.object(dirty_writers.script_utils, "head_commit_time", return_value=None):
            self.assertIsNone(self.holder())

    def test_an_unreadable_other_transcript_is_listed_unread_and_names_no_holder(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"])
        stderr = io.StringIO()

        with unittest.mock.patch.object(dirty_writers.loop_transcript, "written_paths", side_effect=OSError("gone")), \
                unittest.mock.patch.object(sys, "stderr", stderr):
            self.assertIsNone(self.holder())
            found = dirty_writers.dirty_writers(str(self.repo), [{"sessionId": "other", "name": "name-other"}],
                                                ["a.py"], 0, "own")

        self.assertEqual(found.unread, ["name-other"])
        self.assertEqual(found.writers, [])
        self.assertIn("dirty_writers: could not read the transcript", stderr.getvalue())

    def test_an_unreadable_own_transcript_counts_as_a_possible_write(self):
        self.transcript("own", [self.repo / "a.py"])
        stderr = io.StringIO()

        with unittest.mock.patch.object(dirty_writers.loop_transcript, "written_paths", side_effect=OSError("gone")), \
                unittest.mock.patch.object(sys, "stderr", stderr):
            may_have_written = dirty_writers.own_session_may_have_written(str(self.repo), ["a.py"], 0, "own")

        self.assertTrue(may_have_written)
        self.assertIn("dirty_writers: could not read the transcript", stderr.getvalue())

    def test_an_unreadable_own_transcript_names_no_holder_even_when_another_session_wrote(self):
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"])
        self.transcript("own", [self.repo / "a.py"])
        real_written_paths = dirty_writers.loop_transcript.written_paths

        def unreadable_for_own(transcript, since):
            if pathlib.Path(transcript).name == "own.jsonl":
                raise OSError("gone")
            return real_written_paths(transcript, since=since)

        with unittest.mock.patch.object(dirty_writers.loop_transcript, "written_paths",
                                        side_effect=unreadable_for_own), \
                unittest.mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertIsNone(self.holder())

    def test_a_write_before_a_later_commit_names_the_holder_only_against_the_recorded_head(self):
        recorded_head = subprocess.run(["git", "-C", str(self.repo), "rev-parse", "HEAD"], check=True,
                                       capture_output=True, text=True).stdout.strip()
        (self.repo / "b.py").write_text("b\n")
        git = ["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "add", "b.py"], check=True)
        later_commit = {**os.environ, "GIT_COMMITTER_DATE": "2030-01-01T00:00:00Z"}
        subprocess.run([*git, "commit", "-q", "-m", "later"], check=True, env=later_commit)
        self.live_session("other")
        self.transcript("other", [self.repo / "a.py"], timestamp="2028-01-01T00:00:00Z")
        self.transcript("own", [])

        self.assertIsNone(self.holder())
        found = dirty_writers.holder_with_paths(str(self.repo), ["a.py"], "own", recorded_head)

        self.assertEqual(found.row["sessionId"], "other")

    def test_an_unreadable_own_transcript_with_no_other_writer_names_no_holder(self):
        self.live_session("other")
        self.transcript("other", [])
        self.transcript("own", [self.repo / "a.py"])

        with unittest.mock.patch.object(dirty_writers.loop_transcript, "written_paths", side_effect=OSError("gone")), \
                unittest.mock.patch.object(sys, "stderr", io.StringIO()):
            self.assertIsNone(self.holder())

    def test_sole_writer_is_the_row_only_when_the_own_session_wrote_nothing_and_none_is_unread(self):
        row = {"sessionId": "other"}

        self.assertEqual(dirty_writers.DirtyWriters(False, [row], []).sole_writer(), row)
        self.assertIsNone(dirty_writers.DirtyWriters(True, [row], []).sole_writer())

    def test_the_writers_of_a_mixed_case_are_reported_with_their_unread_labels(self):
        self.live_session("writer")
        self.transcript("writer", [self.repo / "a.py"])
        self.live_session("silent")
        others = dirty_writers.session_registry.other_live_sessions_in(str(self.repo), "own")

        found = dirty_writers.dirty_writers(str(self.repo), others, ["a.py"], 0, "own")

        self.assertFalse(found.own_wrote)
        self.assertEqual([row["sessionId"] for row in found.writers], ["writer"])
        self.assertEqual(found.unread, ["name-silent"])
        self.assertIsNone(found.sole_writer())


if __name__ == "__main__":
    unittest.main()
