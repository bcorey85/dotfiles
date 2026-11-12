"""Checks for lib/process_group.py: a process's command line and a SIGTERM for its group."""
import importlib.util
import os
import pathlib
import signal
import subprocess
import sys
import time
import unittest
import unittest.mock

import toolkit_paths

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

    def test_command_line_raises_when_ps_fails(self):
        for returncode, stderr in ((1, "boom"), (2, ""), (2, "boom")):
            finished = subprocess.CompletedProcess([], returncode, stdout="", stderr=stderr)
            with (
                self.subTest(returncode=returncode, stderr=stderr),
                unittest.mock.patch("subprocess.run", return_value=finished),
                self.assertRaises(process_group.ProcessQueryError),
            ):
                process_group.command_line(1)


if __name__ == "__main__":
    unittest.main()
