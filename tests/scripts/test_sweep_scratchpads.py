"""Checks for sweep_scratchpads.py, the SessionStart hook that deletes the temp folders of sessions that ended a day
ago or more."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest

import toolkit_paths

SCRIPT = toolkit_paths.TOOLS_DIR / "sweep_scratchpads.py"
OLD_SESSION = "11111111-1111-4111-8111-111111111111"
NEW_SESSION = "22222222-2222-4222-8222-222222222222"
CURRENT_SESSION = "33333333-3333-4333-8333-333333333333"
TWO_DAYS = 2 * 24 * 3600


class SweepScratchpadsTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.base = pathlib.Path(temp_dir.name)
        self.project = self.base / f"claude-{os.getuid()}" / "-home-user-repo"
        self.project.mkdir(parents=True)
        self.sessions_dir = self.base / "config" / "sessions"
        self.sessions_dir.mkdir(parents=True)

    def running_session(self, session_id, pid):
        """A Claude Code session record naming `session_id` under `pid`."""
        record = {"pid": pid, "sessionId": session_id, "kind": "interactive"}
        (self.sessions_dir / f"{pid}.json").write_text(json.dumps(record))

    def dead_pid(self):
        """The pid of a process that has exited."""
        finished = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True,
                                  text=True, check=True)
        return int(finished.stdout)

    def session_folder(self, name, age_seconds):
        """A session folder holding a scratchpad file, with every entry `age_seconds` old."""
        folder = self.project / name
        scratch_file = folder / "scratchpad" / "notes.md"
        scratch_file.parent.mkdir(parents=True)
        scratch_file.write_text("notes\n")
        stamp = time.time() - age_seconds
        for entry in (scratch_file, scratch_file.parent, folder):
            os.utime(entry, (stamp, stamp))
        return folder

    def run_hook(self, session_id=CURRENT_SESSION):
        environment = dict(os.environ, CLAUDE_CODE_TMPDIR=str(self.base),
                           CLAUDE_CONFIG_DIR=str(self.sessions_dir.parent))
        event = json.dumps({"hook_event_name": "SessionStart", "session_id": session_id})
        return subprocess.run([sys.executable, str(SCRIPT)], input=event.encode("utf-8"), capture_output=True,
                              env=environment)

    def test_a_session_folder_untouched_for_two_days_is_deleted(self):
        old = self.session_folder(OLD_SESSION, TWO_DAYS)
        finished = self.run_hook()
        self.assertEqual((finished.returncode, finished.stderr), (0, b""))
        self.assertFalse(old.exists())

    def test_a_folder_with_one_recent_file_is_kept(self):
        folder = self.session_folder(NEW_SESSION, TWO_DAYS)
        (folder / "scratchpad" / "fresh.log").write_text("today\n")
        self.run_hook()
        self.assertTrue(folder.exists())

    def test_the_current_session_s_folder_is_kept_however_old(self):
        current = self.session_folder(CURRENT_SESSION, TWO_DAYS)
        self.run_hook()
        self.assertTrue(current.exists())

    def test_a_running_session_s_folder_is_kept_however_old(self):
        running = self.session_folder(OLD_SESSION, TWO_DAYS)
        self.running_session(OLD_SESSION, os.getpid())
        finished = self.run_hook()
        self.assertEqual((finished.returncode, finished.stderr), (0, b""))
        self.assertTrue(running.exists())

    def test_a_session_whose_recorded_pid_has_exited_is_deleted(self):
        ended = self.session_folder(OLD_SESSION, TWO_DAYS)
        self.running_session(OLD_SESSION, self.dead_pid())
        self.run_hook()
        self.assertFalse(ended.exists())

    def test_a_malformed_session_record_is_skipped(self):
        old = self.session_folder(OLD_SESSION, TWO_DAYS)
        (self.sessions_dir / "123.json").write_text("{not json")
        finished = self.run_hook()
        self.assertEqual((finished.returncode, finished.stderr), (0, b""))
        self.assertFalse(old.exists())

    def test_a_folder_not_named_for_a_session_is_kept(self):
        other = self.session_folder("cache", TWO_DAYS)
        self.run_hook()
        self.assertTrue(other.exists())

    def test_a_missing_temp_root_exits_zero_silently(self):
        environment = dict(os.environ, CLAUDE_CODE_TMPDIR=str(self.base / "absent"))
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=b"", capture_output=True, env=environment)
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, b"", b""))

    def test_bad_hook_input_reports_and_exits_zero(self):
        old = self.session_folder(OLD_SESSION, TWO_DAYS)
        environment = dict(os.environ, CLAUDE_CODE_TMPDIR=str(self.base))
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=b"{not json", capture_output=True,
                                  env=environment)
        self.assertEqual(finished.returncode, 0)
        self.assertIn(b"sweep-scratchpads: sweep stopped", finished.stderr)
        self.assertTrue(old.exists())


if __name__ == "__main__":
    unittest.main()
