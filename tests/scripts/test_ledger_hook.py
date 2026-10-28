"""Checks for ledger-hook, the wrapper a settings.json hook runs in place of an inline `ledger hook` call.

Every case runs with HOME and CARGO_HOME set to a temp dir and a PATH that holds no ledger unless the case plants one.
"""

import os
import pathlib
import subprocess
import tempfile
import unittest

import fake_ledger
import toolkit_paths

# A stand-in ledger that records its arguments and stdin, then exits with LEDGER_HOOK_EXIT.
HOOK_LEDGER_SOURCE = """#!/usr/bin/env bash
printf '%s\\n' "$*" > "$LEDGER_HOOK_CALL"
cat >> "$LEDGER_HOOK_CALL"
exit "${LEDGER_HOOK_EXIT:-0}"
"""


class LedgerHookTest(unittest.TestCase):
    """ledger-hook runs `ledger hook <event>` with the event on stdin, and never fails the hook."""

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.temp_root / "home"
        self.call_path = self.temp_root / "ledger-call.txt"

    def plant_ledger(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        ledger_path = folder / "ledger"
        ledger_path.write_text(HOOK_LEDGER_SOURCE)
        ledger_path.chmod(0o755)

    def run_hook(self, extra_path="", ledger_exit="0"):
        bare_path = fake_ledger.path_without_ledger(os.environ["PATH"])
        env = {
            **os.environ,
            "HOME": str(self.home),
            "CARGO_HOME": str(self.home / ".cargo"),
            "PATH": f"{extra_path}:{bare_path}" if extra_path else bare_path,
            "LEDGER_HOOK_CALL": str(self.call_path),
            "LEDGER_HOOK_EXIT": ledger_exit,
        }
        hook_script = toolkit_paths.TELEMETRY_DIR / "ledger-hook"
        return subprocess.run(
            [str(hook_script), "stop"], env=env, capture_output=True, text=True, input='{"event":"Stop"}'
        )

    def test_the_ledger_on_path_gets_the_event_and_its_stdin(self):
        on_path = self.temp_root / "on-path"
        self.plant_ledger(on_path)

        done = self.run_hook(extra_path=str(on_path))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.call_path.read_text(), 'hook stop\n{"event":"Stop"}')

    def test_a_ledger_in_the_cargo_bin_folder_runs_when_path_has_none(self):
        self.plant_ledger(self.home / ".cargo" / "bin")

        done = self.run_hook()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(self.call_path.read_text().startswith("hook stop\n"))

    def test_a_failing_ledger_still_exits_0(self):
        self.plant_ledger(self.home / ".cargo" / "bin")

        done = self.run_hook(ledger_exit="3")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(self.call_path.exists(), "the ledger never ran")

    def test_no_ledger_exits_0_silently(self):
        done = self.run_hook()

        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertFalse(self.call_path.exists())

    def test_a_directory_named_ledger_in_the_cargo_bin_folder_is_not_run(self):
        (self.home / ".cargo" / "bin" / "ledger").mkdir(parents=True)

        done = self.run_hook()

        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))
        self.assertFalse(self.call_path.exists())


if __name__ == "__main__":
    unittest.main()
