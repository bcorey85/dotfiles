"""Checks for suite_receipt.py: a merge check skips the suite rerun only when the branch fast-forwards the base and its
exact tree has a green receipt; any other branch reruns."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SUITE_RECEIPT = pathlib.Path(os.environ.get("SUITE_RECEIPT_SCRIPT") or toolkit_paths.TOOLS_DIR / "suite_receipt.py")
EXIT_SKIP = 0
EXIT_RERUN = 1
EXIT_FAILED = 2
EXIT_DIRTY = 3
GREEN_SUMMARY = {"tests": 12, "files": 3, "failed_files": []}
RED_SUMMARY = {"tests": 12, "files": 3, "failed_files": ["test_a.py"]}


def git(repo, *args):
    finished = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return finished.stdout.strip()


class LaneRepoCase(unittest.TestCase):
    """A repo on master with one commit and a worktree `lane` on its own branch."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name)
        self.repo = self.scratch / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "--quiet", "--initial-branch=master")
        git(self.repo, "config", "user.email", "test@example.com")
        git(self.repo, "config", "user.name", "Test")
        self.commit("base.txt", "base\n")
        self.lane = self.scratch / "lane"
        git(self.repo, "worktree", "add", "--quiet", "-b", "lane", str(self.lane))

    def commit(self, name, text, repo=None):
        where = repo or self.repo
        (where / name).write_text(text)
        git(where, "add", name)
        git(where, "commit", "--quiet", "-m", f"add {name}")

    def run_receipt(self, *args):
        return subprocess.run([sys.executable, str(SUITE_RECEIPT), *args], capture_output=True, text=True, timeout=30)


class SuiteReceiptTest(LaneRepoCase):
    def record_run(self, summary, exit_code, start_tree=None):
        """Records one suite run in the lane worktree; the tree is the lane's as it stands unless start_tree names
        another."""
        tree = start_tree or self.run_receipt("tree", str(self.lane)).stdout.strip()
        summary_file = self.scratch / "summary.json"
        summary_file.write_text(json.dumps(summary))
        return self.run_receipt("record", str(self.lane), "--tree", tree, "--exit", str(exit_code),
                                "--scope", "full", "--summary", str(summary_file))

    def check_lane(self):
        return self.run_receipt("check", str(self.repo), "lane")

    def test_a_fast_forward_branch_whose_tree_ran_green_skips_the_rerun(self):
        self.commit("feature.txt", "feature\n", repo=self.lane)
        self.assertEqual(0, self.record_run(GREEN_SUMMARY, 0).returncode)

        finished = self.check_lane()

        self.assertEqual(EXIT_SKIP, finished.returncode, finished.stdout + finished.stderr)
        self.assertIn("skip:", finished.stdout)
        self.assertIn("12 tests", finished.stdout)

    def test_a_branch_that_does_not_fast_forward_reruns_even_with_a_green_receipt(self):
        self.commit("feature.txt", "feature\n", repo=self.lane)
        self.record_run(GREEN_SUMMARY, 0)
        self.commit("other.txt", "landed on master meanwhile\n")

        finished = self.check_lane()

        self.assertEqual(EXIT_RERUN, finished.returncode, finished.stdout + finished.stderr)
        self.assertIn("does not fast-forward master", finished.stdout)

    def test_a_branch_with_no_run_recorded_reruns(self):
        self.commit("feature.txt", "feature\n", repo=self.lane)

        finished = self.check_lane()

        self.assertEqual(EXIT_RERUN, finished.returncode, finished.stdout + finished.stderr)
        self.assertIn("no suite run is recorded", finished.stdout)

    def test_a_commit_after_the_green_run_reruns(self):
        self.record_run(GREEN_SUMMARY, 0)
        self.commit("feature.txt", "feature\n", repo=self.lane)

        finished = self.check_lane()

        self.assertEqual(EXIT_RERUN, finished.returncode, finished.stdout + finished.stderr)
        self.assertIn("no suite run is recorded", finished.stdout)

    def test_a_branch_whose_last_run_failed_reruns(self):
        self.commit("feature.txt", "feature\n", repo=self.lane)
        self.record_run(RED_SUMMARY, 1)

        finished = self.check_lane()

        self.assertEqual(EXIT_RERUN, finished.returncode, finished.stdout + finished.stderr)
        self.assertIn("failed", finished.stdout)

    def test_a_red_run_after_a_green_one_on_the_same_tree_voids_the_skip(self):
        self.commit("feature.txt", "feature\n", repo=self.lane)
        self.record_run(GREEN_SUMMARY, 0)
        self.record_run(GREEN_SUMMARY, 1)

        finished = self.check_lane()

        self.assertEqual(EXIT_RERUN, finished.returncode, finished.stdout)

    def test_an_uncommitted_edit_in_the_tested_tree_gives_a_receipt_the_committed_branch_cannot_use(self):
        self.commit("feature.txt", "feature\n", repo=self.lane)
        (self.lane / "feature.txt").write_text("edited after the commit\n")
        self.record_run(GREEN_SUMMARY, 0)

        finished = self.check_lane()

        self.assertEqual(EXIT_RERUN, finished.returncode, finished.stdout)

    def test_a_tree_that_changed_during_the_run_writes_no_receipt(self):
        start_tree = self.run_receipt("tree", str(self.lane)).stdout.strip()
        self.commit("feature.txt", "feature\n", repo=self.lane)

        recorded = self.record_run(GREEN_SUMMARY, 0, start_tree=start_tree)
        finished = self.check_lane()

        self.assertEqual(EXIT_FAILED, recorded.returncode)
        self.assertIn("changed during the run", recorded.stderr)
        self.assertEqual(EXIT_RERUN, finished.returncode, finished.stdout)

    def test_the_tree_hash_leaves_the_repo_index_untouched(self):
        (self.lane / "untracked.txt").write_text("not staged\n")
        status_before = git(self.lane, "status", "--porcelain")

        tree = self.run_receipt("tree", str(self.lane)).stdout.strip()

        self.assertEqual(status_before, git(self.lane, "status", "--porcelain"))
        self.assertIn("untracked.txt", git(self.lane, "ls-tree", "--name-only", tree))


class DirtyCheckTest(LaneRepoCase):
    """`dirty`: the check before a merge into the main checkout."""

    def lane_cuts_gate_and_rebuilds_page(self):
        """master holds gate.txt and page.html; the lane deletes the first and rewrites the second."""
        self.commit("gate.txt", "gate\n")
        self.commit("page.html", "page v1\n")
        git(self.lane, "merge", "--quiet", "master")
        git(self.lane, "rm", "--quiet", "gate.txt")
        # The commit helper's commit takes the staged deletion with the page.
        self.commit("page.html", "page v2\n", repo=self.lane)

    def test_a_staged_deletion_and_a_dirty_page_the_merge_touches_stop_it_with_the_fix(self):
        self.lane_cuts_gate_and_rebuilds_page()
        git(self.repo, "rm", "--quiet", "gate.txt")
        (self.repo / "page.html").write_text("page edited by another session\n")
        head_before = git(self.repo, "rev-parse", "HEAD")

        finished = self.run_receipt("dirty", str(self.repo), "lane")

        self.assertEqual(EXIT_DIRTY, finished.returncode, finished.stdout + finished.stderr)
        self.assertIn("gate.txt", finished.stdout)
        self.assertIn("page.html", finished.stdout)
        self.assertIn("Fix: commit them", finished.stdout)
        self.assertIn("rerun this line", finished.stdout)
        self.assertEqual(head_before, git(self.repo, "rev-parse", "HEAD"), "a merge started")
        self.assertFalse((self.repo / ".git" / "MERGE_HEAD").exists())
        self.assertEqual("page edited by another session\n", (self.repo / "page.html").read_text())

    def test_a_dirty_file_the_merge_does_not_touch_leaves_the_merge_clear(self):
        self.lane_cuts_gate_and_rebuilds_page()
        (self.repo / "base.txt").write_text("edited, not on the lane\n")

        finished = self.run_receipt("dirty", str(self.repo), "lane")

        self.assertEqual(EXIT_SKIP, finished.returncode, finished.stdout + finished.stderr)
        self.assertIn("clear:", finished.stdout)

    def test_a_clean_checkout_leaves_the_merge_clear(self):
        self.lane_cuts_gate_and_rebuilds_page()

        finished = self.run_receipt("dirty", str(self.repo), "lane")

        self.assertEqual(EXIT_SKIP, finished.returncode, finished.stdout + finished.stderr)


if __name__ == "__main__":
    unittest.main()
