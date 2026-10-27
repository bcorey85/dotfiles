"""Checks for tests/run.sh, the toolkit test run: a machine with no ruff must fail it, never skip the lint, and a
failed step is named on the last line."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

from stubs import write_stub

SCRIPT = pathlib.Path(os.environ.get("RUN_SH_SCRIPT") or pathlib.Path(__file__).resolve().parents[1] / "run.sh")


class RunShTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.bin_dir = pathlib.Path(self.tmp.name)

        # run.sh needs only dirname before its ruff check; nothing else is on this PATH.
        dirname_path = shutil.which("dirname")
        (self.bin_dir / "dirname").symlink_to(dirname_path)

    def test_a_missing_ruff_stops_the_run_before_any_test_with_how_to_install_it(self):
        bash_path = shutil.which("bash")
        finished = subprocess.run([bash_path, str(SCRIPT)], env={"PATH": str(self.bin_dir)},
                                  capture_output=True, text=True, timeout=30)

        self.assertEqual(finished.returncode, 1)
        self.assertIn("ruff not installed: install it", finished.stderr)
        self.assertNotIn("python3", finished.stderr)

    def test_a_failed_lint_ends_the_run_on_a_line_naming_it_after_a_passing_test_summary(self):
        write_stub(self.bin_dir / "ruff", "exit 1")
        write_stub(self.bin_dir / "python3", 'echo "3177 tests in 86 files, 0 failed"')

        bash_path = shutil.which("bash")
        finished = subprocess.run([bash_path, str(SCRIPT)], env={"PATH": str(self.bin_dir)},
                                  capture_output=True, text=True, timeout=30)

        self.assertEqual(finished.returncode, 1)
        last_line = finished.stdout.splitlines()[-1]
        self.assertEqual(last_line, "FAILED: lint")


if __name__ == "__main__":
    unittest.main()
