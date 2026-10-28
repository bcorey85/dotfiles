"""Tests for review-scope: the no-base STOP, `root=` scoping, and review-loop's Step 0 call.

REVIEW_SCOPE_SCRIPT overrides the script path; it defaults to the one in this tree.
"""

import os
import subprocess
import tempfile
import unittest

import toolkit_paths

SCRIPT = os.environ.get(
    "REVIEW_SCOPE_SCRIPT",
    str(toolkit_paths.CLAUDE_DIR / "skills" / "review" / "review-scope"),
)
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True)
    if done.returncode != 0:
        raise AssertionError(f"git {args} failed: {done.stderr}")
    return done.stdout.strip()


def commit(cwd, name):
    with open(os.path.join(cwd, name), "w") as handle:
        handle.write(name)
    git(cwd, "add", "-A")
    git(cwd, "commit", "-qm", name)


def run_scope(cwd, *args):
    return subprocess.run([SCRIPT, *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True)


class ReviewScopeNoBaseTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def trunk_repo_with_committed_branch_work(self):
        """A repo whose default branch is neither main nor master, with no remote:
        branch-base finds no base for the feature branch."""
        path = os.path.join(self.tmp, "repo")
        git(self.tmp, "init", "-q", "-b", "trunk", path)
        commit(path, "base")
        git(path, "checkout", "-q", "-b", "feature")
        commit(path, "committed-on-feature")
        return path

    def test_stops_when_no_base_is_found_and_branch_has_commits_no_other_ref_has(self):
        path = self.trunk_repo_with_committed_branch_work()
        done = run_scope(path)
        self.assertEqual(done.returncode, 3, done.stdout + done.stderr)
        self.assertIn("STOP: no base ref found", done.stderr)
        self.assertNotIn("FILES=", done.stdout)

    def test_explicit_base_still_prints_the_scope(self):
        path = self.trunk_repo_with_committed_branch_work()
        done = run_scope(path, "base=trunk")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("committed-on-feature", done.stdout)

    def test_branch_with_no_commits_of_its_own_still_prints_the_scope(self):
        path = os.path.join(self.tmp, "repo")
        git(self.tmp, "init", "-q", "-b", "trunk", path)
        commit(path, "base")
        git(path, "checkout", "-q", "-b", "feature")
        with open(os.path.join(path, "dirty.txt"), "w") as handle:
            handle.write("x")
        done = run_scope(path)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("dirty.txt", done.stdout)

    def test_help_prints_usage_and_exits_zero(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                done = run_scope(self.tmp, flag)
                self.assertEqual((done.returncode, done.stderr), (0, ""))
                self.assertIn("usage: review-scope [key=value ...]", done.stdout)


class ReviewScopeRootTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def dirty_repo(self, name, dirty_file):
        path = os.path.join(self.tmp, name)
        git(self.tmp, "init", "-q", "-b", "main", path)
        commit(path, "base")
        with open(os.path.join(path, dirty_file), "w") as handle:
            handle.write("x")
        return path

    def test_root_outside_the_cwd_repo_scopes_that_worktrees_diff(self):
        session_repo = self.dirty_repo("session-repo", "session-change.txt")
        main_checkout = self.dirty_repo("dotfiles", "unrelated.txt")
        sibling_worktree = os.path.join(self.tmp, "dotfiles-fix")
        git(main_checkout, "worktree", "add", "-q", "-b", "fix/x", sibling_worktree)
        with open(os.path.join(sibling_worktree, "worktree-change.txt"), "w") as handle:
            handle.write("x")

        done = run_scope(session_repo, f"root={sibling_worktree}")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn(f"ROOT={os.path.realpath(sibling_worktree)}", done.stdout)
        self.assertIn("BRANCH=fix/x", done.stdout)
        self.assertIn("worktree-change.txt", done.stdout)
        self.assertNotIn("session-change.txt", done.stdout)
        self.assertNotIn("unrelated.txt", done.stdout)

    def test_review_loop_runs_review_scope_with_the_repo_as_root(self):
        agent_path = toolkit_paths.CLAUDE_DIR / "agents" / "review-loop.md"
        agent_text = agent_path.read_text()

        scope_command = "~/.claude/skills/review/review-scope"
        scope_calls = [line for line in agent_text.splitlines() if line.startswith(scope_command)]

        self.assertEqual(len(scope_calls), 1, scope_calls)
        self.assertIn("root=<repo>", scope_calls[0])


if __name__ == "__main__":
    unittest.main()
