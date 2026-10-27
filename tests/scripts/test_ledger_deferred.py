"""Checks for tools/ledger_deferred.py: the deferred-findings queue read, with a wait for a ledger that is behind.

run: python3 tests/scripts/test_ledger_deferred.py
"""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from toolkit_paths import LIB_DIR, TOOLS_DIR

sys.path.insert(0, str(LIB_DIR))
import script_utils

SCRIPT = pathlib.Path(os.environ.get("LEDGER_DEFERRED_SCRIPT") or TOOLS_DIR / "ledger_deferred.py")
BUSY_LINE = "cache behind: too many shard rows are not loaded yet; retry"


class LedgerDeferredTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        self.env = {**os.environ, "PATH": os.pathsep.join([str(self.folder), "/usr/bin", "/bin"]),
                    script_utils.LEDGER_BACKOFF_ENV: "0"}

    def plant(self, body):
        stub = self.folder / "ledger"
        stub.write_text("#!/bin/sh\n" + body)
        stub.chmod(0o755)

    def run_script(self):
        return subprocess.run([str(SCRIPT)], env=self.env, capture_output=True, text=True, timeout=60)

    def test_the_ledger_output_is_printed_unchanged(self):
        self.plant('[ "$*" = "yield --deferred" ] || exit 64\nprintf "# deferred\\nrow-1\\trow\\n"\n')

        done = self.run_script()

        self.assertEqual((0, "# deferred\nrow-1\trow\n"), (done.returncode, done.stdout))

    def test_a_ledger_that_is_not_installed_is_not_tracked(self):
        done = self.run_script()

        self.assertEqual((0, "deferred: not tracked (ledger not installed)\n"), (done.returncode, done.stdout))

    def test_a_ledger_that_stays_busy_exits_75_with_the_command_to_run(self):
        self.plant(f'echo "{BUSY_LINE}" >&2\nexit 75\n')

        done = self.run_script()

        self.assertEqual(75, done.returncode)
        self.assertEqual(
            f"deferred: not read (ledger yield --deferred: {BUSY_LINE} (0 s of pauses)). "
            f"Run `ledger worker --once`, then `{SCRIPT.resolve()}` to read the queue.\n", done.stdout)

    def test_another_failure_prints_the_ledger_stderr_and_its_exit_code(self):
        self.plant('echo "ledger yield: not inside a git repository" >&2\nexit 3\n')

        done = self.run_script()

        self.assertEqual((3, "ledger yield: not inside a git repository\n",
                          "deferred: not read (ledger yield: not inside a git repository)\n"),
                         (done.returncode, done.stderr, done.stdout))

    def test_another_failure_without_stderr_names_the_exit_code(self):
        self.plant("exit 4\n")

        done = self.run_script()

        self.assertEqual((4, "deferred: not read (exited 4)\n"), (done.returncode, done.stdout))


if __name__ == "__main__":
    unittest.main()
