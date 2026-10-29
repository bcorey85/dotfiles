"""Tests for the branch-base script.

BRANCH_BASE_SCRIPT overrides the script path; it defaults to the one in this tree.
"""
import os
import subprocess
import tempfile
import unittest

import toolkit_paths

SCRIPT = os.environ.get(
    "BRANCH_BASE_SCRIPT", str(toolkit_paths.TOOLS_DIR / "branch-base")
)
GIT_ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}


def git(cwd, *args):
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True
    )
    if done.returncode != 0:
        raise AssertionError(f"git {args} failed: {done.stderr}")
    return done.stdout.strip()


def commit(cwd, name):
    with open(os.path.join(cwd, name), "w") as handle:
        handle.write(name)
    git(cwd, "add", "-A")
    git(cwd, "commit", "-qm", name)


def run_script(cwd, *args):
    return subprocess.run(
        [SCRIPT, *args], cwd=cwd, env=GIT_ENV, capture_output=True, text=True
    )


class BranchBaseTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name

    def repo(self, name="repo", default="main"):
        path = os.path.join(self.tmp, name)
        git(self.tmp, "init", "-q", "-b", default, path)
        commit(path, "base")
        return path

    def with_origin(self, path, default="main"):
        """Give the repo a bare origin that holds its default branch."""
        origin = path + "-origin.git"
        git(self.tmp, "init", "-q", "--bare", "-b", default, origin)
        git(path, "remote", "add", "origin", origin)
        git(path, "push", "-q", "origin", default)
        git(path, "fetch", "-q", "origin")

    def assert_base(self, branch_base_run, expected):
        self.assertEqual(branch_base_run.returncode, 0, branch_base_run.stderr)
        self.assertEqual(branch_base_run.stdout, expected + "\n")

    # --- each source in the order ---------------------------------------

    def test_upstream_local_branch(self):
        path = self.repo()
        git(path, "branch", "develop")
        git(path, "checkout", "-q", "-b", "topic", "develop")
        git(path, "branch", "-u", "develop")
        self.assert_base(run_script(path), "develop upstream")

    def test_origin_head(self):
        path = self.repo(default="trunk")
        self.with_origin(path, "trunk")
        git(path, "remote", "set-head", "origin", "trunk")
        git(path, "checkout", "-q", "-b", "topic")
        self.assert_base(run_script(path), "origin/trunk origin-head")

    def test_origin_main_or_master(self):
        rows = [("main", "origin/main origin-main"), ("master", "origin/master origin-master")]
        for default, expected in rows:
            with self.subTest(default=default):
                path = self.repo(name=default, default=default)
                self.with_origin(path, default)
                git(path, "checkout", "-q", "-b", "topic")
                git(path, "remote", "set-head", "origin", "-d")
                self.assert_base(run_script(path), expected)

    def test_local_main_or_master(self):
        for default in ("main", "master"):
            with self.subTest(default=default):
                path = self.repo(name=default, default=default)
                git(path, "checkout", "-q", "-b", "topic")
                self.assert_base(run_script(path), f"{default} {default}")

    # --- upstream rules ---------------------------------------------------

    def test_pushed_feature_branch_gives_origin_main(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "remote", "set-head", "origin", "main")
        git(path, "checkout", "-q", "-b", "feature")
        commit(path, "f1")
        git(path, "push", "-q", "-u", "origin", "feature")
        self.assertEqual(
            git(path, "rev-parse", "--abbrev-ref", "feature@{upstream}"),
            "origin/feature",
        )
        self.assert_base(run_script(path), "origin/main origin-head")

    def test_pushed_feature_branch_without_origin_head(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "remote", "set-head", "origin", "-d")
        git(path, "checkout", "-q", "-b", "feature")
        git(path, "push", "-q", "-u", "origin", "feature")
        self.assert_base(run_script(path), "origin/main origin-main")

    def test_local_develop_upstream_kept_over_origin_main(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "branch", "develop")
        git(path, "checkout", "-q", "-b", "topic", "develop")
        git(path, "branch", "-u", "develop")
        self.assert_base(run_script(path), "develop upstream")

    def test_head_option_uses_the_heads_upstream(self):
        path = self.repo()
        git(path, "branch", "develop")
        git(path, "branch", "--track", "topic", "develop")
        # the checkout is on main, which has no upstream
        self.assert_base(run_script(path, "--head", "topic"), "develop upstream")

    def test_head_that_origin_head_points_at_uses_its_own_upstream(self):
        path = self.repo(default="trunk")
        self.with_origin(path, "trunk")
        git(path, "branch", "-u", "origin/trunk", "trunk")
        git(path, "remote", "set-head", "origin", "trunk")
        self.assert_base(run_script(path), "origin/trunk own-upstream")

    def test_head_that_is_not_a_branch_is_a_bad_argument(self):
        path = self.repo()
        self.assertEqual(run_script(path, "--head", "nosuch").returncode, 2)

    def test_head_that_exists_only_on_origin_is_allowed(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "push", "-q", "origin", "main:remoteonly")
        git(path, "fetch", "-q", "origin")
        git(path, "remote", "set-head", "origin", "main")
        self.assert_base(run_script(path, "--head", "remoteonly"), "origin/main origin-head")

    def renamed_master(self):
        """A main that was renamed from master and still tracks origin/master."""
        path = self.repo(default="master")
        self.with_origin(path, "master")
        git(path, "branch", "-u", "origin/master", "master")
        git(path, "branch", "-m", "master", "main")
        return path

    def test_renamed_master_prefers_origin_main_over_its_stale_upstream(self):
        path = self.renamed_master()
        git(path, "push", "-q", "origin", "main")
        git(path, "fetch", "-q", "origin")
        self.assertEqual(git(path, "rev-parse", "--abbrev-ref", "main@{upstream}"), "origin/master")
        self.assert_base(run_script(path), "origin/main own-upstream")

    def test_renamed_master_without_origin_main_keeps_its_upstream(self):
        path = self.renamed_master()
        self.assert_base(run_script(path), "origin/master upstream")

    def add_remote(self, path, name, branches):
        """Add a bare remote with the given branches pushed and fetched."""
        remote = os.path.join(self.tmp, f"{name}.git")
        git(self.tmp, "init", "-q", "--bare", "-b", "main", remote)
        git(path, "remote", "add", name, remote)
        for branch in branches:
            git(path, "push", "-q", name, branch)
        git(path, "fetch", "-q", name)

    # --- default branch ---------------------------------------------------

    def test_default_branch_uses_its_own_upstream(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "remote", "set-head", "origin", "main")
        git(path, "branch", "-u", "origin/main", "main")
        commit(path, "unpushed")
        self.assert_base(run_script(path, "--head", "main"), "origin/main own-upstream")

    def test_default_branch_tracking_fork_main(self):
        path = self.repo()
        self.add_remote(path, "fork", ["main"])
        git(path, "branch", "-u", "fork/main", "main")
        self.assert_base(run_script(path), "fork/main own-upstream")

    def test_default_branch_ignores_old_local_master(self):
        path = self.repo()
        git(path, "branch", "master")
        commit(path, "newer")
        self.with_origin(path)
        git(path, "remote", "set-head", "origin", "main")
        git(path, "branch", "-u", "origin/main", "main")
        self.assert_base(run_script(path), "origin/main own-upstream")

    def test_default_branch_ignores_old_origin_master(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "push", "-q", "origin", "main:master")
        git(path, "fetch", "-q", "origin")
        commit(path, "newer")
        git(path, "push", "-q", "origin", "main")
        git(path, "remote", "set-head", "origin", "main")
        git(path, "branch", "-u", "origin/main", "main")
        self.assert_base(run_script(path), "origin/main own-upstream")

    def test_feature_branch_that_origin_head_points_at_uses_origin_main(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "checkout", "-q", "-b", "feature")
        commit(path, "f1")
        git(path, "push", "-q", "-u", "origin", "feature")
        git(path, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/feature")
        self.assert_base(run_script(path), "origin/main origin-main")

    def test_default_branch_without_upstream_uses_origin_copy_not_old_origin_master(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "push", "-q", "origin", "main:master")
        git(path, "fetch", "-q", "origin")
        commit(path, "newer")
        git(path, "push", "-q", "origin", "main")
        git(path, "remote", "set-head", "origin", "main")
        self.assert_base(run_script(path), "origin/main own-upstream")

    def test_default_branch_without_remote_ignores_old_local_master(self):
        path = self.repo()
        git(path, "branch", "master")
        commit(path, "newer")
        branch_base_run = run_script(path)
        self.assertEqual(branch_base_run.returncode, 1)
        self.assertEqual(branch_base_run.stdout, "")

    def test_default_branch_with_pruned_upstream_stops(self):
        path = self.repo()
        git(path, "branch", "master")
        commit(path, "newer")
        self.with_origin(path)
        git(path, "branch", "-u", "origin/main", "main")
        git(path, "update-ref", "-d", "refs/remotes/origin/main")
        branch_base_run = run_script(path)
        self.assertEqual(branch_base_run.returncode, 1)
        self.assertIn("STOP: no base found for main;", branch_base_run.stderr)

    def test_default_branch_ignores_stale_origin_head(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "push", "-q", "origin", "main:master")
        git(path, "fetch", "-q", "origin")
        commit(path, "newer")
        git(path, "push", "-q", "-u", "origin", "main")
        git(path, "remote", "set-head", "origin", "master")
        self.assert_base(run_script(path), "origin/main own-upstream")

    def test_local_branch_named_origin_main_does_not_hide_the_remote_one(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "remote", "set-head", "origin", "main")
        git(path, "branch", "origin/main")
        commit(path, "newer")
        git(path, "push", "-q", "origin", "main")
        git(path, "checkout", "-q", "-b", "topic")
        self.assert_base(run_script(path), "remotes/origin/main origin-head")

    def test_empty_head_is_a_bad_argument(self):
        path = self.repo()
        self.assertEqual(run_script(path, "--head", "").returncode, 2)

    def test_default_branch_without_remote_stops(self):
        path = self.repo()
        branch_base_run = run_script(path)
        self.assertEqual(branch_base_run.returncode, 1)
        self.assertIn("STOP: no base found for main;", branch_base_run.stderr)

    # --- unusual heads and remotes ------------------------------------------

    def test_detached_head_falls_back_to_main(self):
        path = self.repo()
        git(path, "checkout", "-q", "--detach")
        self.assert_base(run_script(path), "main main")

    def test_branch_name_with_a_slash(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "remote", "set-head", "origin", "-d")
        git(path, "checkout", "-q", "-b", "feature/login")
        git(path, "push", "-q", "-u", "origin", "feature/login")
        self.assert_base(run_script(path), "origin/main origin-main")

    def test_same_named_upstream_on_fork_remote_is_skipped(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "remote", "set-head", "origin", "-d")
        self.add_remote(path, "fork", [])
        git(path, "checkout", "-q", "-b", "topic")
        git(path, "push", "-q", "-u", "fork", "topic")
        self.assert_base(run_script(path), "origin/main origin-main")

    def test_other_named_fork_upstream_is_kept(self):
        path = self.repo()
        self.add_remote(path, "fork", ["main"])
        git(path, "checkout", "-q", "-b", "topic")
        git(path, "branch", "-u", "fork/main")
        self.assert_base(run_script(path), "fork/main upstream")

    def test_origin_head_pointing_at_a_missing_ref_is_skipped(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/gone")
        git(path, "checkout", "-q", "-b", "topic")
        self.assert_base(run_script(path), "origin/main origin-main")

    # --- where it runs ------------------------------------------------------

    def test_runs_from_a_subdirectory(self):
        path = self.repo()
        git(path, "checkout", "-q", "-b", "topic")
        sub = os.path.join(path, "a", "b")
        os.makedirs(sub)
        self.assert_base(run_script(sub), "main main")

    def test_runs_in_a_linked_worktree(self):
        path = self.repo()
        self.with_origin(path)
        git(path, "remote", "set-head", "origin", "-d")
        linked = os.path.join(self.tmp, "linked")
        git(path, "worktree", "add", "-q", "-b", "topic", linked)
        git(linked, "push", "-q", "-u", "origin", "topic")
        self.assert_base(run_script(linked), "origin/main origin-main")

    # --- failure --------------------------------------------------------------

    def test_no_candidate_stops_and_names_the_branch_or_the_detached_head(self):
        rows = [
            (["checkout", "-q", "-b", "topic"], "topic"),
            (["checkout", "-q", "--detach"], "detached HEAD"),
        ]
        for checkout, state in rows:
            with self.subTest(state=state):
                path = self.repo(name=state.replace(" ", "-"), default="trunk")
                git(path, *checkout)
                branch_base_run = run_script(path)
                self.assertEqual(branch_base_run.returncode, 1)
                self.assertEqual(branch_base_run.stdout, "")
                self.assertEqual(
                    branch_base_run.stderr.strip(),
                    f"STOP: no base found for {state}; ask the user for a base branch",
                )


if __name__ == "__main__":
    unittest.main()
