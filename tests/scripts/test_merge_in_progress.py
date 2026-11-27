"""Checks for lib/merge_in_progress.py (whether a commit only ends the open merge)."""
import io
import pathlib
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

import merge_in_progress
import script_utils
from merge_fixtures import (
    git,
    start_clean_resolved_merge,
    start_conflicted_merge,
    start_octopus_merge,
    write_and_commit,
)


class CommitEndsMergeTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = pathlib.Path(tmp.name)
        git(self.repo, "init", "-q", "-b", "main")

    def test_merge_with_only_merge_paths_staged_ends_the_merge(self):
        start_conflicted_merge(self.repo)
        self.assertTrue(merge_in_progress.commit_ends_merge(self.repo))

    def test_a_staged_path_outside_the_merge_does_not(self):
        self.merge_with_staged_peer_file()
        self.assertFalse(merge_in_progress.commit_ends_merge(self.repo))

    def test_an_empty_staged_set_during_a_merge_ends_it(self):
        start_clean_resolved_merge(self.repo)
        self.assertEqual(set(), script_utils.diff_paths(self.repo, "--cached"))
        self.assertTrue(merge_in_progress.commit_ends_merge(self.repo))

    def test_no_merge_in_progress_is_false(self):
        write_and_commit(self.repo, "a.txt", "base\n", "base")
        self.assertFalse(merge_in_progress.commit_ends_merge(self.repo))

    def test_git_failure_is_false_and_named_on_stderr(self):
        stderr = io.StringIO()
        with unittest.mock.patch.object(sys, "stderr", stderr):
            ended = merge_in_progress.commit_ends_merge(self.repo / "missing")
        self.assertFalse(ended)
        self.assertIn("could not read MERGE_HEAD", stderr.getvalue())

    def test_a_failing_staged_diff_is_false(self):
        start_conflicted_merge(self.repo)
        self.assert_false_when_diff_fails(lambda args: "--cached" in args, "git diff --cached failed")

    def test_a_failing_merge_diff_is_false(self):
        start_conflicted_merge(self.repo)
        self.assert_false_when_diff_fails(lambda args: any(word.startswith("HEAD...") for word in args),
                                          "git diff HEAD...")

    def test_a_merge_in_a_linked_worktree_ends_the_merge(self):
        write_and_commit(self.repo, "a.txt", "base\n", "base")
        linked = self.repo.parent / (self.repo.name + "-linked")
        self.addCleanup(shutil.rmtree, linked, ignore_errors=True)
        git(self.repo, "worktree", "add", "-q", "-b", "work", str(linked))
        start_merge_in_linked_worktree(linked)
        self.assertTrue(merge_in_progress.commit_ends_merge(linked))

    def test_an_octopus_merge_counts_the_paths_of_every_head(self):
        start_octopus_merge(self.repo)
        self.assertEqual(len(merge_in_progress.merge_heads(self.repo)), 2)
        self.assertTrue(merge_in_progress.commit_ends_merge(self.repo))

    def test_a_staged_delete_is_not_hidden_as_a_rename_of_a_merge_copy(self):
        write_and_commit(self.repo, "x.txt", "same content\nsecond line\nthird line\n", "base")
        git(self.repo, "branch", "side")
        write_and_commit(self.repo, "other.txt", "ours\n", "ours")
        git(self.repo, "switch", "-q", "side")
        write_and_commit(self.repo, "y.txt", "same content\nsecond line\nthird line\n", "copy")
        git(self.repo, "switch", "-q", "main")
        git(self.repo, "merge", "--no-commit", "--no-ff", "side")
        git(self.repo, "rm", "-q", "x.txt")
        self.assertFalse(merge_in_progress.commit_ends_merge(self.repo))

    def merge_with_staged_peer_file(self):
        """Start a conflicted merge, then stage peer.txt, a path the merge does not change."""
        start_conflicted_merge(self.repo)
        (self.repo / "peer.txt").write_text("peer\n")
        git(self.repo, "add", "peer.txt")

    def assert_false_when_diff_fails(self, fails, expected_message):
        real_git_output = script_utils.git_output

        def git_output(cwd, *args, **options):
            if args[0] == "diff" and fails(args):
                return None
            return real_git_output(cwd, *args, **options)

        stderr = io.StringIO()
        with unittest.mock.patch.object(script_utils, "git_output", git_output), \
                unittest.mock.patch.object(sys, "stderr", stderr):
            ended = merge_in_progress.commit_ends_merge(self.repo)
        self.assertFalse(ended)
        self.assertIn(expected_message, stderr.getvalue())


def start_merge_in_linked_worktree(repo):
    """Start a clean `--no-commit` merge in a linked worktree: `side-linked` adds d.txt, which the merge stages."""
    git(repo, "branch", "side-linked", "HEAD")
    git(repo, "switch", "-q", "side-linked")
    write_and_commit(repo, "d.txt", "side\n", "side")
    git(repo, "switch", "-q", "work")
    write_and_commit(repo, "e.txt", "work\n", "work")
    git(repo, "merge", "--no-commit", "--no-ff", "side-linked")


if __name__ == "__main__":
    unittest.main()
