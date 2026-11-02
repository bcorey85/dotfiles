"""Tests for concentration.py: the added-line counts of the concentration gate of the refactor closing phase."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

CONCENTRATION = toolkit_paths.CODE_DIR / "concentration.py"
GIT_IDENTITY = ["-c", "user.name=t", "-c", "user.email=t@example.com"]


def lines(count):
    return "".join(f"x = {number}\n" for number in range(count))


class ConcentrationGateTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name)
        self.git("init", "-q")
        self.write("README.md", "start\n")
        self.git("add", "-A")
        self.git(*GIT_IDENTITY, "commit", "-q", "-m", "start")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True)

    def write(self, name, text):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit_files(self, files):
        for name, count in files.items():
            self.write(name, lines(count))
        self.git("add", "-A")
        self.git(*GIT_IDENTITY, "commit", "-q", "-m", "work")

    def run_gate(self, *args):
        return subprocess.run([sys.executable, str(CONCENTRATION), *args], cwd=self.repo, capture_output=True,
                              text=True, check=False)

    def test_a_small_branch_does_not_trigger(self):
        self.commit_files({"src/a/one.py": 10})

        done = self.run_gate(self.base)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("largest module src/a 10 added lines", done.stdout)
        self.assertIn("Not triggered", done.stdout)

    def test_one_module_past_the_limit_names_it_for_simplify(self):
        self.commit_files({"src/a/one.py": 100})

        done = self.run_gate(self.base)

        self.assertIn("TRIGGERED (concentrated): run `/refactor simplify src/a`", done.stdout)

    def test_many_modules_past_the_branch_limit_trigger_as_distributed(self):
        self.commit_files({f"src/m{number}/one.py": 60 for number in range(5)})

        done = self.run_gate(self.base)

        self.assertIn("TRIGGERED (distributed)", done.stdout)

    def test_tests_and_docs_do_not_count(self):
        self.commit_files({"tests/test_a.py": 400, "docs/plans/p/spec.md": 400, "src/a/one.py": 5})

        done = self.run_gate(self.base)

        self.assertIn("branch 5 added lines", done.stdout)
        self.assertIn("Not triggered", done.stdout)

    def test_drizzle_migration_metadata_does_not_count_and_the_real_largest_module_is_named(self):
        self.commit_files({"backend/drizzle/meta/0001_snapshot.json": 900, "backend/drizzle/meta/_journal.json": 40,
                           "backend/src/orders.ts": 120})

        done = self.run_gate(self.base)

        self.assertIn("largest module backend/src 120 added lines", done.stdout)
        self.assertIn("run `/refactor simplify backend/src`", done.stdout)

    def test_uncommitted_changes_do_not_count(self):
        self.commit_files({"src/a/one.py": 10})
        self.write("src/b/two.py", lines(200))

        done = self.run_gate(self.base)

        self.assertIn("branch 10 added lines", done.stdout)

    def test_a_base_that_does_not_exist_stops_with_a_reason(self):
        done = self.run_gate("0" * 40)

        self.assertEqual(done.returncode, 1)
        self.assertIn("git could not diff", done.stderr)

    def test_no_argument_prints_the_usage(self):
        done = self.run_gate()

        self.assertEqual(done.returncode, 1)
        self.assertIn("usage: concentration.py <base-sha>", done.stderr)


if __name__ == "__main__":
    unittest.main()
