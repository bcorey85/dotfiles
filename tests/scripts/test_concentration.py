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

    def split_line(self):
        done = self.run_gate(self.base)
        self.assertEqual(done.returncode, 0, done.stderr)
        return done.stdout.splitlines()[1]

    def test_split_counts_docs_tests_and_code_and_leaves_out_lockfiles_and_binary_files(self):
        (self.repo / "blob.bin").write_bytes(b"\x00\x01\x02" * 100)
        self.commit_files({"src/a/one.py": 50, "tests/test_a.py": 30, "README.md": 20, "docs/x.txt": 10,
                           "docs/test_x.py": 10, "docs/tests/a.py": 5, "package-lock.json": 500})

        self.assertEqual(self.split_line(), "Diff split: docs 30 (24%), tests 45 (36%), code 50 (40%) of 125 added "
                         "lines. No part over 40%.")

    def test_oversized_parts_are_named_docs_first(self):
        self.commit_files({"docs/a.md": 150, "tests/test_a.py": 150, "src/a/one.py": 50})

        self.assertEqual(
            self.split_line(),
            "Diff split: docs 150 (43%), tests 150 (43%), code 50 (14%) of 350 added lines. "
            "OVERSIZED: new docs files 43% (limit 40%): check each new docs file against a plan step, criterion or "
            "finding, and cut the rest. "
            "OVERSIZED: new tests files 43% (limit 40%): check each new tests file against a plan step, criterion or "
            "finding, and cut the rest.")

    def test_lines_added_to_an_existing_test_file_never_make_tests_oversized(self):
        self.write("tests/test_a.py", lines(1))
        self.git("add", "-A")
        self.git(*GIT_IDENTITY, "commit", "-q", "-m", "existing test file")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.commit_files({"tests/test_a.py": 201, "src/a/one.py": 100})

        self.assertEqual(self.split_line(), "Diff split: docs 0 (0%), tests 200 (67%), code 100 (33%) of 300 added "
                         "lines. No part over 40%.")

    def test_only_the_new_file_lines_count_toward_oversized(self):
        self.write("tests/test_old.py", lines(1))
        self.git("add", "-A")
        self.git(*GIT_IDENTITY, "commit", "-q", "-m", "existing test file")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.commit_files({"tests/test_old.py": 101, "tests/test_new.py": 130, "src/a/one.py": 70})

        self.assertIn("OVERSIZED: new tests files 43% (limit 40%)", self.split_line())

    def test_only_the_part_over_the_limit_is_named(self):
        self.commit_files({"tests/test_a.py": 150, "src/a/one.py": 150})

        line = self.split_line()

        self.assertIn("OVERSIZED: new tests files 50%", line)
        self.assertNotIn("OVERSIZED: new docs", line)

    def test_a_total_at_the_trigger_can_be_oversized(self):
        self.commit_files({"docs/a.md": 123, "src/a/one.py": 177})

        self.assertIn("OVERSIZED: new docs files 41%", self.split_line())

    def test_a_total_just_under_the_trigger_is_not_oversized(self):
        self.commit_files({"docs/a.md": 123, "src/a/one.py": 176})

        self.assertTrue(self.split_line().endswith("No part over 40%."))

    def test_a_share_exactly_at_the_limit_is_not_oversized(self):
        self.commit_files({"docs/a.md": 120, "src/a/one.py": 180})

        self.assertTrue(self.split_line().endswith("No part over 40%."))

    def test_a_part_over_the_share_on_a_branch_under_the_trigger_is_not_oversized(self):
        self.commit_files({"tests/test_a.py": 200, "src/a/one.py": 50})

        self.assertTrue(self.split_line().endswith("No part over 40%."))

    def test_a_branch_with_no_added_lines_shows_zero_shares(self):
        self.commit_files({"package-lock.json": 5})

        self.assertEqual(self.split_line(), "Diff split: docs 0 (0%), tests 0 (0%), code 0 (0%) of 0 added lines. "
                         "No part over 40%.")

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
