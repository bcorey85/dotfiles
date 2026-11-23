"""branch_bounds.py: exit codes and listed paths over a scratch repo."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = os.environ.get("BRANCH_BOUNDS_SCRIPT") or str(Path(__file__).resolve().parent / "branch_bounds.py")

OFFENDING_SHAPES = [
    "claude/.claude/scripts/review/verify-prep",
    "claude/.claude/scripts/review/handback.py",
    "claude/.claude/scripts/gates/some_gate.py",
    "claude/.claude/scripts/code/plan_check.py",
    "claude/.claude/settings.json",
    "CLAUDE.md",
    "docs/deep/orchestration.md",
    "claude/.claude/skills/x/CLAUDE.md",
]
CLEAN_SHAPES = [
    "tests/scripts/test_other.py",
    "claude/.claude/scripts/code/other.py",
    "claude/.claude/scripts/review_notes.md",
    "docs/CLAUDE.md.bak",
]


class BranchBoundsTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")
        self.git("config", "commit.gpgsign", "false")
        self.write("seed.txt")
        self.base = self.commit("seed")

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def write(self, rel):
        target = self.repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("x\n")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD")

    def run_bounds(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, *args], cwd=self.repo, capture_output=True, text=True
        )

    def test_each_offending_shape_in_a_commit_exits_1_and_is_listed(self):
        for shape in OFFENDING_SHAPES:
            with self.subTest(shape=shape):
                self.write(shape)
                head = self.commit("add " + shape)
                result = self.run_bounds(self.base, head)
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(shape, result.stdout)
                self.git("reset", "-q", "--hard", self.base)

    def test_clean_commit_exits_0(self):
        for shape in CLEAN_SHAPES:
            self.write(shape)
        head = self.commit("clean")
        result = self.run_bounds(self.base, head)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")

    def test_verify_prep_hit_is_named_in_the_message(self):
        self.write("claude/.claude/scripts/review/verify-prep")
        head = self.commit("verify-prep")
        result = self.run_bounds(self.base, head)
        self.assertEqual(result.returncode, 1)
        self.assertIn("verify-prep is off limits", result.stdout)

    def test_untracked_work_tree_file_exits_1_and_is_listed(self):
        self.write("tests/ok.py")
        head = self.commit("clean")
        self.write("claude/.claude/scripts/gates/new_dir/untracked_gate.py")
        result = self.run_bounds(self.base, head)
        self.assertEqual(result.returncode, 1)
        self.assertIn("claude/.claude/scripts/gates/new_dir/untracked_gate.py", result.stdout)

    def test_modified_work_tree_file_exits_1(self):
        self.write("claude/.claude/settings.json")
        head = self.commit("settings")
        (self.repo / "claude/.claude/settings.json").write_text("changed\n")
        result = self.run_bounds(head, head)
        self.assertEqual(result.returncode, 1)
        self.assertIn("claude/.claude/settings.json", result.stdout)

    def test_a_commit_only_the_base_has_is_not_counted_against_the_head(self):
        trunk = self.git("rev-parse", "--abbrev-ref", "HEAD")
        self.git("checkout", "-q", "-b", "side")
        self.write("tests/ok.py")
        head = self.commit("clean head work")
        self.git("checkout", "-q", trunk)
        self.write("CLAUDE.md")
        base = self.commit("base moved on")
        self.git("checkout", "-q", "side")
        result = self.run_bounds(base, head)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")

    def test_bad_sha_exits_2(self):
        for base, head in [("deadbeef" * 5, self.base), (self.base, "not-a-sha")]:
            with self.subTest(base=base, head=head):
                result = self.run_bounds(base, head)
                self.assertEqual(result.returncode, 2, result.stdout)

    def test_wrong_argument_count_exits_2(self):
        result = self.run_bounds(self.base)
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
