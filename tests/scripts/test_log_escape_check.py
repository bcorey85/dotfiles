"""Checks for the no-model check scripts: --help prints their usage before any ledger check or case runs."""
import os
import pathlib
import subprocess
import tempfile
import unittest

import fake_ledger
import toolkit_paths

REVIEW_SKILL_DIR = toolkit_paths.CLAUDE_DIR / "skills" / "review"

CHECK_SCRIPTS = (
    (pathlib.Path(os.environ.get("LOG_ESCAPE_CHECK_SCRIPT") or toolkit_paths.TELEMETRY_DIR / "log-escape-check"),
     "usage: log-escape-check [tmpdir]"),
    (pathlib.Path(os.environ.get("LOG_REVIEW_CHECK_SCRIPT") or REVIEW_SKILL_DIR / "log-review-check"),
     "usage: log-review-check [tmpdir]"),
)


class CheckScriptHelpTest(unittest.TestCase):
    def test_help_prints_usage_and_runs_no_case(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        temp_root = pathlib.Path(temp_dir.name)
        ledger_env = fake_ledger.install(temp_root)
        env = {**os.environ, **ledger_env, "TMPDIR": str(temp_root)}
        for script, usage in CHECK_SCRIPTS:
            for flag in ("--help", "-h"):
                with self.subTest(script=script.name, flag=flag):
                    done = subprocess.run(["bash", str(script), flag], cwd=temp_root, env=env,
                                          capture_output=True, text=True)
                    self.assertEqual((done.returncode, done.stderr), (0, ""))
                    self.assertIn(usage, done.stdout)
                    self.assertNotIn("FAIL", done.stdout)
                    self.assertEqual(fake_ledger.recorded_rows(ledger_env), [])


if __name__ == "__main__":
    unittest.main()
