"""Runs memory_sample.py against a fake process table and a temp state folder, and reads the real process table once."""
import datetime
import importlib.util
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
import process_table
import script_utils
import system_resources

MEMORY_SAMPLE = pathlib.Path(os.environ.get("MEMORY_SAMPLE_SCRIPT", toolkit_paths.TOOLS_DIR / "memory_sample.py"))
ROTATE_BYTES = 5 * 1024 * 1024
MEMORY_SPEC = importlib.util.spec_from_file_location("memory_sample", MEMORY_SAMPLE)
memory_sample = importlib.util.module_from_spec(MEMORY_SPEC)
MEMORY_SPEC.loader.exec_module(memory_sample)


def fake_row(pid, rss_kb, command, workspace=None, cwd=None):
    return {"pid": pid, "rss_kb": rss_kb, "command": command, "workspace": workspace, "cwd": cwd}


class MemorySampleTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = pathlib.Path(os.path.realpath(scratch.name))
        self.state_home = self.root / "state"
        self.table_file = self.root / "table.json"
        self.log_file = self.state_home / "memory-sample" / "samples.jsonl"

    def sample_env(self):
        table_setting = {process_table.TABLE_FILE_VARIABLE: str(self.table_file)}
        return dict(os.environ, XDG_STATE_HOME=str(self.state_home), **table_setting)

    def run_sample(self, rows):
        self.table_file.write_text(json.dumps(rows))
        env = self.sample_env()
        return subprocess.run([sys.executable, str(MEMORY_SAMPLE)], env=env, capture_output=True, text=True)

    def last_line(self):
        return json.loads(self.log_file.read_text().splitlines()[-1])

    def test_one_line_names_the_top_holders_by_command_and_by_workspace(self):
        rows = [
            fake_row(1, 500, "claude", "w1"),
            fake_row(2, 700, "claude", "w2"),
            fake_row(3, 900, "hunk", "w1"),
            fake_row(4, 100, "zsh"),
        ]

        finished = self.run_sample(rows)

        self.assertEqual(finished.returncode, 0, finished.stderr)
        line = self.last_line()
        self.assertEqual([
            {"command": "claude", "rss_kb": 1200, "count": 2},
            {"command": "hunk", "rss_kb": 900, "count": 1},
            {"command": "zsh", "rss_kb": 100, "count": 1}], line["by_command"])
        self.assertEqual([
            {"workspace": "w1", "rss_kb": 1400},
            {"workspace": "w2", "rss_kb": 700},
            {"workspace": "", "rss_kb": 100}], line["by_workspace"])

    def test_only_the_top_15_holders_are_kept(self):
        rows = [fake_row(number, number, f"cmd{number}") for number in range(1, 21)]

        self.run_sample(rows)

        commands = [holder["command"] for holder in self.last_line()["by_command"]]
        self.assertEqual([f"cmd{number}" for number in range(20, 5, -1)], commands)

    def test_only_the_top_15_workspaces_are_kept(self):
        rows = [fake_row(number, number, "cmd", f"w{number:02d}") for number in range(1, 21)]

        self.run_sample(rows)

        workspaces = [holder["workspace"] for holder in self.last_line()["by_workspace"]]
        self.assertEqual([f"w{number:02d}" for number in range(20, 5, -1)], workspaces)

    def test_each_run_appends_one_line_and_keeps_the_first(self):
        self.run_sample([fake_row(1, 10, "a")])
        first_line = self.log_file.read_text().splitlines()[0]
        self.run_sample([fake_row(1, 20, "a")])

        lines = self.log_file.read_text().splitlines()
        self.assertEqual(2, len(lines))
        self.assertEqual(first_line, lines[0])

    def test_a_file_of_exactly_5_mb_does_not_rotate(self):
        self.log_file.parent.mkdir(parents=True)
        self.log_file.write_text("x" * ROTATE_BYTES)

        finished = self.run_sample([fake_row(1, 10, "a")])

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertFalse(self.log_file.with_name("samples.jsonl.1").exists())
        self.assertTrue(self.log_file.read_text().startswith("x" * ROTATE_BYTES))

    def test_a_file_over_5_mb_rotates_when_no_dot_1_copy_exists(self):
        self.log_file.parent.mkdir(parents=True)
        self.log_file.write_text("x" * (ROTATE_BYTES + 1))

        self.run_sample([fake_row(1, 10, "a")])

        self.assertEqual("x" * (ROTATE_BYTES + 1), self.log_file.with_name("samples.jsonl.1").read_text())

    def test_a_file_over_5_mb_rotates_to_one_dot_1_copy(self):
        self.log_file.parent.mkdir(parents=True)
        self.log_file.write_text("x" * (ROTATE_BYTES + 1))
        rotated = self.log_file.with_name("samples.jsonl.1")
        rotated.write_text("older copy")

        finished = self.run_sample([fake_row(1, 10, "a")])

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual("x" * (ROTATE_BYTES + 1), rotated.read_text())
        self.assertEqual(1, len(self.log_file.read_text().splitlines()))

    def test_a_bad_fake_table_exits_1_naming_the_file(self):
        self.table_file.write_text("{not json")
        env = self.sample_env()

        finished = subprocess.run([sys.executable, str(MEMORY_SAMPLE)], env=env, capture_output=True, text=True)

        self.assertEqual(1, finished.returncode)
        self.assertIn(str(self.table_file), finished.stderr)
        self.assertFalse(self.log_file.exists())


class SampleLineTest(unittest.TestCase):
    def sample_with_memory(self, available_gb):
        with mock.patch.object(system_resources, "memory_available_gb", return_value=available_gb):
            return memory_sample.sample_line([])

    def test_the_time_is_an_iso_stamp_with_a_utc_offset(self):
        stamp = datetime.datetime.fromisoformat(self.sample_with_memory(3.5)["time"])

        self.assertEqual(datetime.timedelta(0), stamp.utcoffset())

    def test_the_available_memory_is_the_reader_value_or_null_when_unread(self):
        for available_gb in (3.5, None):
            with self.subTest(available_gb=available_gb):
                self.assertEqual(available_gb, self.sample_with_memory(available_gb)["mem_available_gb"])


class ProcessTableTest(unittest.TestCase):
    @unittest.skipUnless(sys.platform.startswith("linux"), "reads /proc")
    def test_the_real_table_holds_this_process_with_its_rss_and_cwd(self):
        with mock.patch.dict(os.environ):
            os.environ.pop(process_table.TABLE_FILE_VARIABLE, None)
            rows = process_table.read_table()

        mine = [row for row in rows if row.pid == os.getpid()]
        self.assertEqual(1, len(mine))
        self.assertGreater(mine[0].rss_bytes, 0)
        self.assertEqual(os.path.realpath(os.getcwd()), mine[0].cwd)

    def test_workspace_of_reads_the_workspace_id_from_the_nul_separated_environ(self):
        cases = {
            "set among other variables": (b"HOME=/root\0HERDR_WORKSPACE_ID=w7\0PATH=/bin\0", "w7"),
            "last entry with no trailing NUL": (b"A=1\0HERDR_WORKSPACE_ID=w9", "w9"),
            "unset": (b"HOME=/root\0PATH=/bin\0", None),
            "a variable that only ends in the name": (b"X_HERDR_WORKSPACE_ID=w1\0", None),
            "empty value": (b"HERDR_WORKSPACE_ID=\0", ""),
        }
        for label, (environ, expected) in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as folder:
                process_folder = pathlib.Path(folder)
                (process_folder / "environ").write_bytes(environ)
                self.assertEqual(expected, process_table.workspace_of(process_folder), label)

    def test_workspace_of_is_none_when_environ_cannot_be_read(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertIsNone(process_table.workspace_of(pathlib.Path(folder)))

    def test_a_malformed_fake_table_is_a_loud_failure(self):
        cases = {
            "no pid": [{"rss_kb": 1, "command": "a"}],
            "a table that is not a list": {"pid": 1, "rss_kb": 1, "command": "a"},
            "a str rss_kb": [{"pid": 1, "rss_kb": "1", "command": "a"}],
            "a bool rss_kb": [{"pid": 1, "rss_kb": True, "command": "a"}],
            "a non-str command": [{"pid": 1, "rss_kb": 1, "command": 7}],
            "a row that is not an object": [5],
        }
        for label, table_content in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as folder:
                table = pathlib.Path(folder) / "table.json"
                table.write_text(json.dumps(table_content))
                fake_setting = {process_table.TABLE_FILE_VARIABLE: str(table)}
                with mock.patch.dict(os.environ, fake_setting), self.assertRaises(process_table.ProcessTableError):
                    process_table.read_table()

    def read_ps_output(self, stdout):
        finished = mock.Mock(stdout=stdout)
        with mock.patch.dict(os.environ), mock.patch.object(sys, "platform", "darwin"), \
                mock.patch.object(script_utils, "run_or_raise", return_value=finished):
            os.environ.pop(process_table.TABLE_FILE_VARIABLE, None)
            return process_table.read_table()

    def test_the_ps_reader_gives_kilobytes_as_bytes_and_the_command_basename(self):
        rows = self.read_ps_output("  12 2048 /usr/bin/claude\n")

        self.assertEqual([process_table.ProcessRow(12, 2048 * 1024, "claude", None, None)], rows)

    def test_a_malformed_ps_line_is_a_loud_failure(self):
        with self.assertRaises(process_table.ProcessTableError):
            self.read_ps_output("12 not-a-number claude\n")

    def test_a_status_file_gives_its_name_and_rss_and_none_without_rss(self):
        with tempfile.TemporaryDirectory() as folder:
            process_folder = pathlib.Path(folder)
            status = process_folder / "status"

            status.write_text("Name:\tclaude\nVmRSS:\t   2048 kB\n")
            self.assertEqual(("claude", 2048), process_table.status_fields(process_folder))

            status.write_text("Name:\tkthreadd\n")
            self.assertIsNone(process_table.status_fields(process_folder))


if __name__ == "__main__":
    unittest.main()
