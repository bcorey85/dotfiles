"""Tests for the scope guard of a review loop fix pass: the files outside the pass's scope that it puts back."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_coder
import review_loop_scope_guard
import test_review_loop_script as loop_tests

DOC_BEFORE = "| rule | anchor |\n"
DOC_REWRITTEN = "| rule | anchor | rewritten |\n"
MOVED_PATHS = ("old.txt", "staged_rm.txt", "ren_src.txt", "ren_dst.txt")


def git(cwd, *args):
    subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


class ScopeGuardTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name) / "repo"
        self.out = pathlib.Path(tmp.name) / "out"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        (self.repo / "docs" / "plans" / "shop").mkdir(parents=True)
        files = {"app.py": "x = 1\n", "docs/rule-anchors.md": DOC_BEFORE, "tests.py": "t = 1\n",
                 "docs/plans/shop/plan.md": "# Plan\n"}
        for name, text in files.items():
            (self.repo / name).write_text(text)
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "init")
        (self.repo / "app.py").write_text("x = 2\n")
        review_loop_scope_guard.SCOPE_FAULTS.clear()
        self.addCleanup(review_loop_scope_guard.SCOPE_FAULTS.clear)

    def guard(self, allowed=("app.py",), has_own_guard=lambda _path: False, finding_texts=()):
        return review_loop_scope_guard.guard_pass(self.repo, self.out, "coder1", allowed, has_own_guard,
                                                  finding_texts)

    def text(self, name):
        return (self.repo / name).read_text()

    def moved_paths_status(self):
        """`git status --short` for the paths the deletion and rename test moves: the index and work tree state."""
        status = subprocess.run(["git", "status", "--short", "--", *MOVED_PATHS], cwd=self.repo,
                                capture_output=True, text=True, check=True)
        return status.stdout

    def test_a_clean_file_outside_the_scope_is_put_back_and_named(self):
        guard = self.guard()
        (self.repo / "app.py").write_text("x = 3\n")
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        guard.undo()

        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)
        self.assertEqual(self.text("app.py"), "x = 3\n")
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS,
                         ["coder1 changed files outside the review scope that no finding names; the loop put them "
                          "back: docs/rule-anchors.md"])
        self.assertIn(review_loop_scope_guard.SCOPE_FAULTS[0], review_loop_coder.coder_fault_notes())

    def test_a_file_the_pass_staged_or_committed_is_put_back(self):
        for step in ("add", "commit"):
            with self.subTest(step):
                guard = self.guard()
                (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)
                git(self.repo, "add", "docs/rule-anchors.md")
                if step == "commit":
                    git(self.repo, "commit", "-qm", "fix")

                guard.undo()

                self.assertEqual(self.text("docs/rule-anchors.md"), DOC_BEFORE)

    def test_a_deleted_file_outside_the_scope_is_put_back(self):
        guard = self.guard()
        (self.repo / "tests.py").unlink()

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 1\n")

    def test_a_deletion_or_rename_made_before_the_pass_stays_and_is_not_blamed(self):
        for name in ("old.txt", "staged_rm.txt", "ren_src.txt"):
            (self.repo / name).write_text(f"{name}\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "more files")
        (self.repo / "old.txt").unlink()
        git(self.repo, "rm", "-q", "staged_rm.txt")
        git(self.repo, "mv", "ren_src.txt", "ren_dst.txt")
        index_before = self.moved_paths_status()
        guard = self.guard()
        (self.repo / "app.py").write_text("x = 3\n")

        guard.undo()

        for name in ("old.txt", "staged_rm.txt", "ren_src.txt"):
            self.assertFalse((self.repo / name).exists(), name)
        self.assertEqual(self.moved_paths_status(), index_before)
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS, [])

    def test_a_dirty_file_outside_the_scope_returns_to_its_text_before_the_pass(self):
        (self.repo / "tests.py").write_text("t = 2\n")
        (self.repo / "scratch.txt").write_text("mine\n")
        guard = self.guard()
        (self.repo / "tests.py").write_text("t = 3\n")
        (self.repo / "scratch.txt").write_text("theirs\n")

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual(self.text("scratch.txt"), "mine\n")
        self.assertIn("scratch.txt, tests.py", review_loop_scope_guard.SCOPE_FAULTS[0])

    def test_a_file_a_finding_names_stays_changed(self):
        findings = ["- `app.py:1` the test in tests.py asserts the old value",
                    f"full check failed, failing lines:\n  File \"{self.repo}/docs/rule-anchors.md\", line 1"]
        guard = self.guard(finding_texts=findings)
        (self.repo / "tests.py").write_text("t = 2\n")
        (self.repo / "docs/rule-anchors.md").write_text(DOC_REWRITTEN)

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 2\n")
        self.assertEqual(self.text("docs/rule-anchors.md"), DOC_REWRITTEN)
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS, [])

    def test_a_longer_path_in_a_finding_names_no_shorter_one(self):
        guard = self.guard(finding_texts=["- `pkg/tests.py:1` wrong"])
        (self.repo / "tests.py").write_text("t = 2\n")

        guard.undo()

        self.assertEqual(self.text("tests.py"), "t = 1\n")

    def test_a_new_file_and_a_file_with_its_own_guard_stay(self):
        guard = self.guard(has_own_guard=lambda path: path.startswith("docs/plans/"))
        (self.repo / "new_test.py").write_text("n = 1\n")
        (self.repo / "docs/plans/shop/plan.md").write_text("# Plan\n\nchanged\n")

        guard.undo()

        self.assertEqual(self.text("new_test.py"), "n = 1\n")
        self.assertEqual(self.text("docs/plans/shop/plan.md"), "# Plan\n\nchanged\n")
        self.assertEqual(review_loop_scope_guard.SCOPE_FAULTS, [])


class ScopeGuardLoopTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    def test_a_fix_pass_edit_outside_the_review_diff_is_put_back_and_the_packet_names_it(self):
        completed = self.run_script({
            "code-reviewer": [{"result": loop_tests.FIX_REVIEW}, {"result": loop_tests.CLEAN_REVIEW},
                              {"result": loop_tests.CLEAN_REVIEW}],
            "coder": [{"result": "Fixed 1.",
                       "edits": {"app.py": loop_tests.APP_FIXED, "notes.py": loop_tests.NOTES_REFLOWED}}],
            "closure": [{"result": loop_tests.CLOSED}],
        })

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual((self.repo / "notes.py").read_text(), loop_tests.NOTES_BEFORE)
        self.assertEqual((self.repo / "app.py").read_text(), loop_tests.APP_FIXED)
        _, packet = self.stored_packet()
        self.assertIn("coder1 changed files outside the review scope that no finding names; the loop put them back: "
                      "notes.py", packet["tool_fault"])
        self.assertNotIn("notes.py", packet["files_touched"])


if __name__ == "__main__":
    unittest.main()
