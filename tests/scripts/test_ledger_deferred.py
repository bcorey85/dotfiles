"""Checks for tools/ledger_deferred.py: the deferred-findings queue read, with a wait for a ledger that is behind.

run: python3 tests/scripts/test_ledger_deferred.py
"""
import contextlib
import importlib.util
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

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

    def test_a_busy_ledger_gets_a_worker_run_and_then_the_queue_prints(self):
        flag = self.folder / "worker-ran"
        self.plant(
            f'if [ "$*" = "worker --once" ]; then touch "{flag}"; exit 0; fi\n'
            f'[ "$*" = "yield --deferred" ] || exit 64\n'
            f'if [ -e "{flag}" ]; then printf "# deferred\\nrow-1\\trow\\n"; exit 0; fi\n'
            f'echo "{BUSY_LINE}" >&2\nexit 75\n')

        done = self.run_script()

        self.assertEqual((0, "# deferred\nrow-1\trow\n"), (done.returncode, done.stdout))
        self.assertTrue(flag.exists())

    def test_a_ledger_that_stays_busy_after_the_worker_exits_75_and_says_it_ran(self):
        calls = self.folder / "yield-calls"
        self.plant(f'[ "$*" = "worker --once" ] && exit 0\necho x >> "{calls}"\necho "{BUSY_LINE}" >&2\nexit 75\n')

        done = self.run_script()

        self.assertEqual(75, done.returncode)
        first = f"ledger yield --deferred: {BUSY_LINE} (0 s of pauses)"
        self.assertEqual(f"deferred: not read ({first}; {first}; the worker already ran)\n", done.stdout)
        attempts = script_utils.attempts_within(script_utils.LEDGER_WAIT_SECONDS, script_utils.LEDGER_BACKOFF_SECONDS)
        self.assertEqual(attempts + 1, len(calls.read_text().splitlines()),
                         "first read tries every attempt, the read after the worker tries once")

    def test_a_failing_worker_exits_75_and_names_the_worker(self):
        self.plant(f'if [ "$*" = "worker --once" ]; then echo "worker broke" >&2; exit 2; fi\n'
                   f'echo "{BUSY_LINE}" >&2\nexit 75\n')

        done = self.run_script()

        self.assertEqual(75, done.returncode)
        self.assertEqual(
            f"deferred: not read (ledger yield --deferred: {BUSY_LINE} (0 s of pauses); the worker ran and failed: "
            f"ledger worker --once: worker broke)\n",
            done.stdout)

    def test_a_worker_that_hangs_exits_75_and_names_the_timeout(self):
        self.plant(f'if [ "$*" = "worker --once" ]; then sleep 5; exit 0; fi\n'
                   f'echo "{BUSY_LINE}" >&2\nexit 75\n')
        spec = importlib.util.spec_from_file_location("ledger_deferred", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        output = io.StringIO()

        with mock.patch.dict(os.environ, self.env), \
                mock.patch.object(module, "WORKER_TIMEOUT_SECONDS", 0.2), \
                contextlib.redirect_stdout(output):
            code = module.main()

        self.assertEqual(75, code)
        self.assertIn("the worker ran and failed: ledger worker --once: no answer within", output.getvalue())

    def test_a_worker_that_prints_bytes_that_are_not_utf8_still_gets_a_line(self):
        self.plant('if [ "$*" = "worker --once" ]; then printf "\\377\\376" >&2; exit 2; fi\n'
                   f'echo "{BUSY_LINE}" >&2\nexit 75\n')

        done = self.run_script()

        self.assertEqual(75, done.returncode)
        self.assertIn("the worker ran and failed: ledger worker --once:", done.stdout)

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
