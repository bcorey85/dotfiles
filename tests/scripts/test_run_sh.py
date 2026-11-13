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

        # run.sh needs dirname before its ruff check, and mktemp and rm for its run temp folder and the trap that
        # removes it, and cat for the compare stub that records its stdin; nothing else is on this PATH.
        for command in ("dirname", "mktemp", "rm", "cat"):
            (self.bin_dir / command).symlink_to(shutil.which(command))

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

    def run_with_gate_stubs(self, snapshot_exit, compare_exit):
        """Runs run.sh with a python3 stub: snapshot prints SNAP, compare records its argument and stdin."""
        write_stub(self.bin_dir / "ruff", "exit 0")
        self.record_file = self.bin_dir / "recorded"
        self.compare_stdin_file = self.bin_dir / "compare_stdin"
        write_stub(self.bin_dir / "python3", f"""case "$*" in
  *"review_gate_unchanged.py snapshot"*) echo SNAP; exit {snapshot_exit} ;;
  *"review_gate_unchanged.py compare"*)
    echo "compare $3" >> {self.record_file}
    cat > {self.compare_stdin_file}
    echo "  leaked.reviewed: $3/repo" >&2
    exit {compare_exit} ;;
  *parallel_tests.py*) echo "tests $TMPDIR" >> {self.record_file}; exit 0 ;;
  *) exit 0 ;;
esac""")

        bash_path = shutil.which("bash")
        return subprocess.run([bash_path, str(SCRIPT)], env={"PATH": str(self.bin_dir)},
                              capture_output=True, text=True, timeout=30)

    def test_a_leaked_gate_key_fails_the_run_and_the_tests_use_the_folder_the_gate_compares(self):
        finished = self.run_with_gate_stubs(snapshot_exit=0, compare_exit=1)

        self.assertEqual(finished.returncode, 1)
        self.assertEqual(finished.stdout.splitlines()[-1], "FAILED: review-gate-state")
        recorded = dict(line.split(" ", 1) for line in self.record_file.read_text().splitlines())
        self.assertNotEqual(recorded["tests"], "", "the tests run with their own TMPDIR")
        self.assertEqual(recorded["tests"], recorded["compare"], "the gate compares the folder the tests used")
        self.assertEqual(self.compare_stdin_file.read_text().strip(), "SNAP", "compare gets the snapshot on stdin")

    def test_a_clean_gate_passes_the_run_with_no_failed_line(self):
        finished = self.run_with_gate_stubs(snapshot_exit=0, compare_exit=0)

        self.assertEqual(finished.returncode, 0)
        self.assertNotIn("FAILED:", finished.stdout)

    def test_a_failed_snapshot_skips_the_compare_and_fails_the_run(self):
        finished = self.run_with_gate_stubs(snapshot_exit=1, compare_exit=0)

        self.assertEqual(finished.returncode, 1)
        self.assertEqual(finished.stdout.splitlines()[-1], "FAILED: review-gate-state")
        recorded = self.record_file.read_text()
        self.assertNotIn("compare", recorded, "compare never runs after a failed snapshot")


if __name__ == "__main__":
    unittest.main()
