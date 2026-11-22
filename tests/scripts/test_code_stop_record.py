"""Tests for lib/code_stop_record.py, the per-session record of the last relayed /code stop."""
import contextlib
import io
import json
import os
import pathlib
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path[:0] = [str(toolkit_paths.LIB_DIR)]
import code_stop_record  # noqa: E402

SESSION = "record-session"


class StopRecordTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.home = pathlib.Path(folder.name).resolve()
        environment = unittest.mock.patch.dict(os.environ, {"HOME": str(self.home)})
        environment.start()
        self.addCleanup(environment.stop)

    def write_record(self, text):
        record_file = code_stop_record.stop_record_path(SESSION)
        record_file.parent.mkdir(parents=True, exist_ok=True)
        record_file.write_text(text)

    def last_stop_with_stderr(self):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            return code_stop_record.last_stop(SESSION), stderr.getvalue()

    def test_a_record_that_is_not_json_reads_as_none_and_says_so_on_stderr(self):
        self.write_record("{not json")

        recorded, stderr = self.last_stop_with_stderr()

        self.assertIsNone(recorded)
        self.assertIn("code_stop_record: ignoring", stderr)

    def test_a_record_missing_a_key_reads_as_none_and_says_so_on_stderr(self):
        self.write_record(json.dumps({"runFolder": "/run", "repoTop": "/top", "time": 1.0}))

        recorded, stderr = self.last_stop_with_stderr()

        self.assertIsNone(recorded)
        self.assertIn("goOn", stderr)

    def test_a_record_that_is_not_an_object_reads_as_none_and_says_so_on_stderr(self):
        self.write_record("[]")

        recorded, stderr = self.last_stop_with_stderr()

        self.assertIsNone(recorded)
        self.assertIn("code_stop_record: ignoring", stderr)

    def test_a_record_with_a_wrong_typed_value_reads_as_none_and_names_the_key(self):
        cases = [("runFolder", None), ("repoTop", 3), ("goOn", []), ("time", "now"), ("time", True)]
        for key, bad_value in cases:
            with self.subTest(key):
                record = {"runFolder": "/run", "repoTop": "/top", "goOn": "", "time": 1.0}
                record[key] = bad_value
                self.write_record(json.dumps(record))

                recorded, stderr = self.last_stop_with_stderr()

                self.assertIsNone(recorded)
                self.assertIn(f"bad {key}", stderr)

    def test_no_record_and_no_session_read_as_none_without_stderr(self):
        recorded, stderr = self.last_stop_with_stderr()

        self.assertIsNone(recorded)
        self.assertEqual(stderr, "")
        self.assertIsNone(code_stop_record.last_stop(None))

    def test_recording_twice_keeps_only_the_second_run_folder(self):
        code_stop_record.record_stop(SESSION, "/first/run", "/first", "To go on: /code resume /first")
        code_stop_record.record_stop(SESSION, "/second/run", "/second", "To go on: /code resume /second x")

        recorded = code_stop_record.last_stop(SESSION)

        self.assertEqual(recorded["runFolder"], "/second/run")
        self.assertEqual(recorded["repoTop"], "/second")
        self.assertEqual(recorded["goOn"], "To go on: /code resume /second x")

    def test_a_finished_stop_records_an_empty_go_on_line(self):
        code_stop_record.record_stop(SESSION, "/run", "/top", None)

        self.assertEqual(code_stop_record.last_stop(SESSION)["goOn"], "")


if __name__ == "__main__":
    unittest.main()
