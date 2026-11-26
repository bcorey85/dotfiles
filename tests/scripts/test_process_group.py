"""Checks for lib/process_group.py: a process's command line and a SIGTERM for its group."""
import importlib.util
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

import toolkit_paths
from stubs import write_stub

MODULE = pathlib.Path(os.environ.get("PROCESS_GROUP_MODULE") or toolkit_paths.LIB_DIR / "process_group.py")
sys.path.insert(0, str(MODULE.parent))
module_spec = importlib.util.spec_from_file_location("process_group", MODULE)
process_group = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(process_group)

MARKER = "process-group-test-marker"
GROUP_PARENT_CODE = (
    "import subprocess, sys, time\n"
    "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
    "print(child.pid, flush=True)\n"
    "time.sleep(60)\n")


class ProcessGroupTest(unittest.TestCase):
    def sleeper(self):
        process = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)", MARKER],
                                   start_new_session=True)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        return process

    def test_command_line_names_a_running_process_and_is_empty_for_a_gone_one(self):
        process = self.sleeper()
        self.assertIn(MARKER, process_group.command_line(process.pid))
        process.kill()
        process.wait()
        self.assertEqual(process_group.command_line(process.pid), "")

    def test_command_line_is_not_cut_to_a_narrow_columns_width(self):
        process = self.sleeper()
        with unittest.mock.patch.dict(os.environ, {"COLUMNS": "20"}):
            self.assertIn(MARKER, process_group.command_line(process.pid))

    def test_pid_is_alive_for_a_running_pid_and_not_for_a_gone_unusable_or_oversized_one(self):
        self.assertTrue(process_group.pid_is_alive(os.getpid()))
        self.assertTrue(process_group.pid_is_alive(str(os.getpid())))
        for pid in (0, -1, None, "abc", 10**30):
            with self.subTest(pid=pid):
                self.assertFalse(process_group.pid_is_alive(pid))

    def test_wait_until_group_gone_stays_false_while_a_child_outlives_the_leader(self):
        parent = subprocess.Popen([sys.executable, "-c", GROUP_PARENT_CODE], stdout=subprocess.PIPE, text=True,
                                  start_new_session=True)
        self.addCleanup(parent.wait)
        self.addCleanup(parent.kill)
        child_pid = int(parent.stdout.readline())
        self.addCleanup(self.kill_if_running, child_pid)
        group = process_group.group_id(parent.pid)
        parent.kill()
        parent.wait(timeout=10)

        self.assertFalse(process_group.wait_until_group_gone(group, 0.3), "the child still lives in the group")
        os.kill(child_pid, signal.SIGKILL)
        self.assertTrue(process_group.wait_until_group_gone(group, 5))

    def test_group_id_is_none_for_a_gone_process_and_group_is_alive_for_one_it_may_not_signal(self):
        process = self.sleeper()
        process.kill()
        process.wait()
        self.assertIsNone(process_group.group_id(process.pid))
        with unittest.mock.patch.object(process_group.os, "killpg", side_effect=PermissionError):
            self.assertTrue(process_group.group_is_alive(1))

    def test_pid_is_alive_for_a_process_this_user_may_not_signal(self):
        with unittest.mock.patch.object(process_group.os, "kill", side_effect=PermissionError):
            self.assertTrue(process_group.pid_is_alive(1))

    def test_terminate_group_stops_the_whole_group_once_and_reports_a_gone_process(self):
        parent = subprocess.Popen([sys.executable, "-c", GROUP_PARENT_CODE], stdout=subprocess.PIPE, text=True,
                                  start_new_session=True)
        self.addCleanup(parent.wait)
        self.addCleanup(parent.kill)
        child_pid = int(parent.stdout.readline())
        self.addCleanup(self.kill_if_running, child_pid)

        self.assertTrue(process_group.terminate_group(parent.pid))
        parent.wait(timeout=10)
        self.assertTrue(self.wait_until_gone(child_pid), "the grandchild in the group survived terminate_group")
        self.assertFalse(process_group.terminate_group(parent.pid))

    @staticmethod
    def kill_if_running(pid):
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            return

    @staticmethod
    def wait_until_gone(pid):
        """True once pid is gone. The test does not reap the grandchild, so a zombie counts as gone."""
        for _attempt in range(100):
            command = process_group.command_line(pid)
            if command == "" or "<defunct>" in command:
                return True
            time.sleep(0.1)
        return False

    def test_command_line_raises_when_ps_is_missing(self):
        with unittest.mock.patch.dict(os.environ, {"PATH": ""}), self.assertRaises(process_group.ProcessQueryError):
            process_group.command_line(1)

    def test_resident_bytes_of_a_running_process_is_positive_and_none_when_gone(self):
        process = self.sleeper()
        self.assertGreater(process_group.resident_bytes(process.pid), 0)
        process.kill()
        process.wait()
        self.assertIsNone(process_group.resident_bytes(process.pid))

    def test_program_name_is_the_base_name_of_the_program(self):
        process = self.sleeper()
        expected = os.path.basename(sys.executable)[:15]
        self.assertEqual(process_group.program_name(process.pid), expected)
        process.kill()
        process.wait()
        self.assertEqual(process_group.program_name(process.pid), "")

    def test_resident_bytes_raises_when_ps_fails(self):
        with tempfile.TemporaryDirectory() as bin_dir:
            write_stub(pathlib.Path(bin_dir) / "ps", "echo boom >&2\nexit 2")
            with (
                unittest.mock.patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}"}),
                self.assertRaises(process_group.ProcessQueryError),
            ):
                process_group.resident_bytes(1)
        with tempfile.TemporaryDirectory() as bin_dir:
            write_stub(pathlib.Path(bin_dir) / "ps", "echo abc")
            with (
                unittest.mock.patch.dict(os.environ, {"PATH": f"{bin_dir}:{os.environ['PATH']}"}),
                self.assertRaises(process_group.ProcessQueryError),
            ):
                process_group.resident_bytes(1)

    def test_command_line_raises_when_ps_fails(self):
        for returncode, stderr in ((1, "boom"), (2, ""), (2, "boom")):
            finished = subprocess.CompletedProcess([], returncode, stdout="", stderr=stderr)
            with (
                self.subTest(returncode=returncode, stderr=stderr),
                unittest.mock.patch("subprocess.run", return_value=finished),
                self.assertRaises(process_group.ProcessQueryError),
            ):
                process_group.command_line(1)

    def stop_group_with(self, group, signalled, group_exited=True):
        """Runs stop_group with the group id, the signal and the wait patched; returns the result and the wait mock."""
        with (
            unittest.mock.patch.object(process_group, "group_id", return_value=group),
            unittest.mock.patch.object(process_group, "terminate_group", return_value=signalled),
            unittest.mock.patch.object(process_group, "STOP_WAIT_SECONDS", 7),
            unittest.mock.patch.object(process_group, "wait_until_group_gone", return_value=group_exited) as wait,
        ):
            return process_group.stop_group(4242), wait

    def test_stop_group_is_gone_when_there_is_no_group_or_no_signal_was_sent(self):
        for group, signalled in ((None, True), (99, False)):
            with self.subTest(group=group, signalled=signalled):
                result, wait = self.stop_group_with(group, signalled)
                self.assertEqual(result, process_group.GROUP_GONE)
                wait.assert_not_called()

    def test_stop_group_waits_the_current_stop_wait_and_reports_stopped(self):
        result, wait = self.stop_group_with(99, True, group_exited=True)
        self.assertEqual(result, process_group.GROUP_STOPPED)
        wait.assert_called_once_with(99, 7)

    def test_stop_group_reports_still_running_when_the_group_outlives_the_wait(self):
        result, _wait = self.stop_group_with(99, True, group_exited=False)
        self.assertEqual(result, process_group.GROUP_STILL_RUNNING)


if __name__ == "__main__":
    unittest.main()
