"""Tests for merge_free_base.py, the review base that leaves out what merge commits brought in."""
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import merge_free_base


def git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, check=True)
    return done.stdout.strip()


def commit_file(repo, name, text):
    (repo / name).write_text(text)
    git(repo, "add", name)
    git(repo, "commit", "-q", "-m", f"add {name}")


class MergeFreeBaseTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name).resolve()
        git(self.repo, "init", "-q", "-b", "main")
        commit_file(self.repo, "base.py", "base\n")
        self.base = git(self.repo, "rev-parse", "HEAD")

    def merge_integration_branch_after_a_phase_commit(self):
        git(self.repo, "checkout", "-q", "-b", "integration")
        commit_file(self.repo, "integration.py", "from the integration branch\n")
        git(self.repo, "checkout", "-q", "main")
        commit_file(self.repo, "phase.py", "the phase\n")
        git(self.repo, "merge", "-q", "--no-ff", "-m", "merge integration", "integration")

    def test_a_range_with_no_merge_commit_keeps_the_base(self):
        commit_file(self.repo, "phase.py", "the phase\n")

        self.assertEqual(merge_free_base.merge_free_base(self.repo, self.base), self.base)

    def test_a_merge_commit_gives_a_base_whose_diff_holds_only_the_phase_change(self):
        self.merge_integration_branch_after_a_phase_commit()

        review_base = merge_free_base.merge_free_base(self.repo, self.base)

        self.assertNotEqual(review_base, self.base)
        self.assertEqual(git(self.repo, "diff", "--name-only", review_base).splitlines(), ["phase.py"])

    def test_the_synthetic_base_is_no_ref(self):
        self.merge_integration_branch_after_a_phase_commit()
        refs_before = git(self.repo, "for-each-ref")

        merge_free_base.merge_free_base(self.repo, self.base)

        self.assertEqual(git(self.repo, "for-each-ref"), refs_before)

    def test_a_merged_in_parent_that_cannot_merge_into_the_base_names_the_merge(self):
        git(self.repo, "checkout", "-q", "--orphan", "unrelated")
        commit_file(self.repo, "base.py", "an unrelated history\n")
        git(self.repo, "checkout", "-q", "main")
        git(self.repo, "merge", "-q", "--allow-unrelated-histories", "-X", "ours", "-m", "merge unrelated", "unrelated")
        merge = git(self.repo, "rev-parse", "HEAD")

        with self.assertRaises(merge_free_base.MergeConflictError) as raised:
            merge_free_base.merge_free_base(self.repo, self.base)

        self.assertEqual(raised.exception.merge, merge)
        self.assertIn(merge, str(raised.exception))
        self.assertIn("base.py", str(raised.exception))

    def test_a_signing_config_does_not_stop_the_synthetic_commit(self):
        self.merge_integration_branch_after_a_phase_commit()
        git(self.repo, "config", "commit.gpgsign", "true")
        git(self.repo, "config", "gpg.program", "/bin/false")

        review_base = merge_free_base.merge_free_base(self.repo, self.base)

        self.assertEqual(git(self.repo, "diff", "--name-only", review_base).splitlines(), ["phase.py"])

    def test_a_merge_inside_the_merged_in_branch_is_not_folded_in_a_second_time(self):
        git(self.repo, "checkout", "-q", "-b", "integration")
        git(self.repo, "checkout", "-q", "-b", "feature")
        commit_file(self.repo, "h.py", "X\n")
        git(self.repo, "checkout", "-q", "integration")
        git(self.repo, "merge", "-q", "--no-ff", "-m", "merge feature", "feature")
        commit_file(self.repo, "h.py", "Y\n")
        git(self.repo, "checkout", "-q", "main")
        commit_file(self.repo, "phase.py", "the phase\n")
        git(self.repo, "merge", "-q", "--no-ff", "-m", "merge integration", "integration")

        review_base = merge_free_base.merge_free_base(self.repo, self.base)

        self.assertEqual(git(self.repo, "diff", "--name-only", review_base).splitlines(), ["phase.py"])

    def test_two_merges_each_fold_onto_the_result_of_the_one_before(self):
        commit_file(self.repo, "phase.py", "the phase\n")
        for name in ("a.py", "b.py"):
            git(self.repo, "checkout", "-q", "-b", f"side-{name}", self.base)
            commit_file(self.repo, name, f"{name}\n")
            git(self.repo, "checkout", "-q", "main")
            git(self.repo, "merge", "-q", "--no-ff", "-m", f"merge {name}", f"side-{name}")

        review_base = merge_free_base.merge_free_base(self.repo, self.base)

        self.assertEqual(git(self.repo, "diff", "--name-only", review_base).splitlines(), ["phase.py"])

    def test_a_base_git_cannot_list_a_range_for_raises_and_does_not_keep_the_base(self):
        with self.assertRaises(merge_free_base.MergeBaseGitError) as raised:
            merge_free_base.merge_free_base(self.repo, "no-such-ref")

        self.assertIn("no-such-ref", str(raised.exception))

    def test_a_merge_tree_failure_that_is_no_conflict_names_the_git_version_need(self):
        self.merge_integration_branch_after_a_phase_commit()
        real_git = merge_free_base._git

        def git_without_write_tree(repo, *args):
            if args[0] == "merge-tree":
                return subprocess.CompletedProcess(args, 129, "", "error: unknown option `write-tree'")
            return real_git(repo, *args)

        with (
            mock.patch.object(merge_free_base, "_git", git_without_write_tree),
            self.assertRaises(merge_free_base.MergeBaseGitError) as raised,
        ):
            merge_free_base.merge_free_base(self.repo, self.base)

        self.assertNotIsInstance(raised.exception, merge_free_base.MergeConflictError)
        self.assertIn("2.38", str(raised.exception))

    def test_a_parent_listing_failure_raises_with_gits_stderr(self):
        self.merge_integration_branch_after_a_phase_commit()
        real_git = merge_free_base._git

        def git_failing_parent_listing(repo, *args):
            if args[0] == "rev-list" and "--parents" in args:
                return subprocess.CompletedProcess(args, 128, "", "fatal: bad object")
            return real_git(repo, *args)

        with (
            mock.patch.object(merge_free_base, "_git", git_failing_parent_listing),
            self.assertRaises(merge_free_base.MergeBaseGitError) as raised,
        ):
            merge_free_base.merge_free_base(self.repo, self.base)

        self.assertIn("fatal: bad object", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
