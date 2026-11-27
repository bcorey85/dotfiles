"""resolve-task-dir.sh: the git-dir plan root for a repo with no docs/plans, and the --home verb."""
import os
import pathlib
import subprocess
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("RESOLVE_TASK_DIR_SCRIPT")
                      or toolkit_paths.TOOLS_DIR / "resolve-task-dir.sh")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
           "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}


class ResolveTaskDirTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.env = {**os.environ, **GIT_ENV}
        self.git(self.repo, "init", "-q", "-b", "master")
        (self.repo / "README.md").write_text("hi\n")
        self.git(self.repo, "add", ".")
        self.git(self.repo, "commit", "-q", "-m", "init")
        self.git(self.repo, "checkout", "-q", "-b", "LED-9-thing")

    def git(self, cwd, *args):
        return subprocess.run(["git", *args], cwd=cwd, env=self.env, check=True, capture_output=True,
                              text=True).stdout.strip()

    def git_dir(self, cwd):
        return pathlib.Path(self.git(cwd, "rev-parse", "--path-format=absolute", "--git-dir"))

    def make_plan_folder(self, cwd, name):
        folder = self.git_dir(cwd) / "claude-plans" / name
        folder.mkdir(parents=True)
        return folder

    def resolve(self, *args, cwd=None):
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=cwd or self.repo, env=self.env,
                              capture_output=True, text=True)

    def test_a_ticket_branch_finds_the_git_dir_folder_as_an_absolute_path(self):
        folder = self.make_plan_folder(self.repo, "LED-9-x")

        done = self.resolve()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), str(folder))

    def test_a_ticket_argument_finds_the_git_dir_folder_named_by_the_bare_key(self):
        folder = self.make_plan_folder(self.repo, "LED-9")

        done = self.resolve("led-9")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), str(folder))

    def test_two_ticket_matches_across_roots_exit_3(self):
        folder = self.make_plan_folder(self.repo, "LED-9-b")
        (self.repo / "docs/plans/LED-9-a").mkdir(parents=True)

        done = self.resolve()

        self.assertEqual(done.returncode, 3)
        self.assertEqual(done.stdout.split(), ["docs/plans/LED-9-a", str(folder)])

    def test_a_ticketless_branch_with_a_git_dir_folder_and_no_argument_exits_4(self):
        self.git(self.repo, "checkout", "-q", "-b", "feature-x")
        self.make_plan_folder(self.repo, "my-plan")

        done = self.resolve()

        self.assertEqual(done.returncode, 4)
        self.assertEqual(done.stdout, "")

    def test_a_ticketless_branch_resolves_the_git_dir_folder_given_as_a_path(self):
        self.git(self.repo, "checkout", "-q", "-b", "feature-x")
        folder = self.make_plan_folder(self.repo, "my-plan")

        done = self.resolve(str(folder))

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), str(folder))

    def test_a_ticketless_branch_with_a_mistyped_path_exits_4(self):
        self.git(self.repo, "checkout", "-q", "-b", "feature-x")
        self.make_plan_folder(self.repo, "my-plan")

        done = self.resolve("docs/plans/typo")

        self.assertEqual(done.returncode, 4)

    def test_a_ticketless_branch_with_no_git_dir_folder_exits_4(self):
        self.git(self.repo, "checkout", "-q", "-b", "feature-x")

        done = self.resolve()

        self.assertEqual(done.returncode, 4)

    def test_home_prints_the_docs_plans_path_when_the_folder_exists(self):
        (self.repo / "docs/plans").mkdir(parents=True)

        done = self.resolve("--home", "my-slug")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), str(self.repo / "docs/plans/my-slug"))

    def test_home_from_a_subfolder_prints_the_top_level_docs_plans_path(self):
        (self.repo / "docs/plans").mkdir(parents=True)
        sub = self.repo / "src" / "deep"
        sub.mkdir(parents=True)

        done = self.resolve("--home", "my-slug", cwd=sub)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), str(self.repo / "docs/plans/my-slug"))

    def test_home_outside_a_git_repo_with_docs_plans_prints_the_absolute_path(self):
        outside = self.root / "plain-docs"
        (outside / "docs/plans").mkdir(parents=True)
        env = {**self.env, "GIT_CEILING_DIRECTORIES": str(self.root)}

        done = subprocess.run(["bash", str(SCRIPT), "--home", "s"], cwd=outside, env=env, capture_output=True,
                              text=True)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), str(outside / "docs/plans/s"))

    def test_home_prints_the_git_dir_path_without_docs_plans(self):
        done = self.resolve("--home", "my-slug")

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), str(self.git_dir(self.repo) / "claude-plans" / "my-slug"))

    def test_a_linked_worktree_uses_its_own_git_dir_for_home_and_lookup(self):
        linked = self.root / "linked"
        self.git(self.repo, "worktree", "add", "-q", "-b", "LED-5-other", str(linked))
        folder = self.make_plan_folder(linked, "LED-5-y")

        home = self.resolve("--home", "s", cwd=linked)
        lookup = self.resolve(cwd=linked)

        linked_git_dir = self.git_dir(linked)
        self.assertNotEqual(linked_git_dir, self.git_dir(self.repo))
        self.assertEqual(home.stdout.strip(), str(linked_git_dir / "claude-plans" / "s"))
        self.assertEqual(lookup.returncode, 0, lookup.stderr)
        self.assertEqual(lookup.stdout.strip(), str(folder))

    def test_a_bad_slug_exits_2_with_a_usage_line(self):
        for args in (("--home",), ("--home", ""), ("--home", "a/b"), ("--home", "."), ("--home", "..")):
            with self.subTest(args=args):
                done = self.resolve(*args)

                self.assertEqual(done.returncode, 2)
                self.assertIn("usage: resolve-task-dir.sh --home <slug>", done.stderr)

    def test_home_outside_a_git_repo_with_no_docs_plans_exits_2_naming_both(self):
        outside = self.root / "plain"
        outside.mkdir()
        env = {**self.env, "GIT_CEILING_DIRECTORIES": str(self.root)}

        done = subprocess.run(["bash", str(SCRIPT), "--home", "s"], cwd=outside, env=env, capture_output=True,
                              text=True)

        self.assertEqual(done.returncode, 2)
        self.assertIn("docs/plans", done.stderr)
        self.assertIn("git repo", done.stderr)

    def test_no_argument_outside_a_git_repo_exits_4_with_no_ticket(self):
        outside = self.root / "plain-no-arg"
        outside.mkdir()
        env = {**self.env, "GIT_CEILING_DIRECTORIES": str(self.root)}

        done = subprocess.run(["bash", str(SCRIPT)], cwd=outside, env=env, capture_output=True, text=True)

        self.assertEqual(done.returncode, 4, done.stderr)
        self.assertIn("no ticket", done.stderr)

    def test_a_docs_plans_ticket_dir_resolves_as_before(self):
        (self.repo / "docs/plans/LED-9-a").mkdir(parents=True)

        done = self.resolve()

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.strip(), "docs/plans/LED-9-a")


if __name__ == "__main__":
    unittest.main()
