"""Tests for tools/pull_keep_index.py: a pull before a push keeps the user's staged files staged."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from toolkit_paths import TOOLS_DIR

SCRIPT = pathlib.Path(os.environ.get("PULL_KEEP_INDEX_SCRIPT") or TOOLS_DIR / "pull_keep_index.py")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t", "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}


class PullKeepIndexTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.remote = self.tmp / "remote.git"
        self.git(self.tmp, "init", "-q", "--bare", "-b", "master", str(self.remote))
        self.repo = self.clone("a")
        self.write(self.repo, "f", "1\n")
        self.write(self.repo, "g", "1\n")
        self.git(self.repo, "add", "f", "g")
        self.git(self.repo, "commit", "-qm", "one")
        self.git(self.repo, "push", "-q", "-u", "origin", "HEAD:master")

    def git(self, folder, *arguments):
        env = {**os.environ, **GIT_ENV}
        finished = subprocess.run(["git", "-C", str(folder), *arguments], capture_output=True, text=True, env=env)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout

    def clone(self, name):
        folder = self.tmp / name
        self.git(self.tmp, "clone", "-q", str(self.remote), str(folder))
        return folder

    def write(self, folder, name, text):
        (folder / name).write_text(text)

    def push_from_other_machine(self, name, text):
        other = self.clone("other-" + name)
        self.write(other, name, text)
        self.git(other, "add", name)
        self.git(other, "commit", "-qm", "other " + name)
        self.git(other, "push", "-q")

    def run_script(self):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run([sys.executable, str(SCRIPT), str(self.repo)], capture_output=True, text=True, env=env)

    def status(self):
        return self.git(self.repo, "status", "--porcelain").splitlines()

    def test_staged_and_unstaged_changes_keep_their_state_across_the_pull(self):
        self.push_from_other_machine("h", "2\n")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M g", "M  f"])
        self.assertEqual((self.repo / "h").read_text(), "2\n")
        self.assertEqual(self.git(self.repo, "stash", "list"), "")

    def test_a_partly_staged_file_keeps_both_its_staged_and_unstaged_text(self):
        self.push_from_other_machine("h", "2\n")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "f", "staged then edited\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.status(), ["MM f"])
        self.assertEqual(self.git(self.repo, "show", ":f"), "staged\n")
        self.assertEqual((self.repo / "f").read_text(), "staged then edited\n")

    def test_a_clean_tree_just_pulls(self):
        self.push_from_other_machine("h", "2\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(self.status(), [])
        self.assertEqual((self.repo / "h").read_text(), "2\n")

    def test_a_failed_pull_puts_the_changes_back_staged(self):
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        shutil.rmtree(self.remote)

        finished = self.run_script()

        self.assertNotEqual(finished.returncode, 0)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_staged_change_the_pull_conflicts_with_stops_and_names_the_saved_commit(self):
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertNotEqual(finished.returncode, 0)
        self.assertIn("stash apply --index", finished.stderr)
        saved = finished.stderr.split("stash apply --index ")[1].split()[0]
        self.assertEqual(self.git(self.repo, "show", saved + ":f"), "mine\n")

    def add_files(self, *names):
        for name in names:
            self.write(self.repo, name, "1\n")
        self.git(self.repo, "add", *names)
        self.git(self.repo, "commit", "-qm", "more files")
        self.git(self.repo, "push", "-q")

    def test_the_re_apply_names_the_saved_commit_to_the_built_page_driver(self):
        # The agent-evals built-page driver rebuilds a page during a stash apply only when BUILT_PAGE_STASH names it.
        recorder = self.tmp / "record_driver.py"
        recorder.write_text("import os, pathlib, sys\n"
                            "pathlib.Path(sys.argv[1]).write_text(os.environ.get('BUILT_PAGE_STASH', ''))\n"
                            "pathlib.Path(sys.argv[3]).write_text(pathlib.Path(sys.argv[4]).read_text())\n")
        record = self.tmp / "record"
        self.git(self.repo, "config", "merge.built-page.driver", f"{sys.executable} {recorder} {record} %O %A %B")
        self.write(self.repo, ".gitattributes", "f merge=built-page\n")
        self.git(self.repo, "add", ".gitattributes")
        self.git(self.repo, "commit", "-qm", "attributes")
        self.git(self.repo, "push", "-q")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        saved = record.read_text()
        self.assertEqual(self.git(self.repo, "show", saved + ":f"), "mine\n")
        self.assertEqual(self.status(), [" M f"])

    def test_a_conflicting_re_apply_keeps_the_staged_and_unstaged_split(self):
        self.add_files("k", "m")
        self.push_from_other_machine("f", "theirs\n")
        self.write(self.repo, "f", "mine\n")
        self.write(self.repo, "g", "staged\n")
        self.git(self.repo, "add", "g")
        self.write(self.repo, "m", "staged\n")
        self.git(self.repo, "add", "m")
        self.write(self.repo, "m", "staged then edited\n")
        self.write(self.repo, "k", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M k", "M  g", "MM m", "UU f"])
        self.assertEqual(self.git(self.repo, "show", ":m"), "staged\n")
        self.assertEqual((self.repo / "m").read_text(), "staged then edited\n")
        self.assertIn("conflict with the pull in: f.", finished.stderr)
        recovery = finished.stderr.split("then run: ")[1].split("\n")[0].split()
        self.write(self.repo, "f", "resolved\n")
        subprocess.run(recovery, check=True, env={**os.environ, **GIT_ENV})
        self.assertEqual(sorted(self.status()), [" M f", " M k", "M  g", "MM m"])

    def test_a_new_branch_with_no_upstream_and_no_remote_branch_exits_0_and_keeps_staged_files(self):
        self.git(self.repo, "checkout", "-q", "-b", "fresh")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("nothing to pull", finished.stdout)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_remote_branch_whose_name_ends_in_the_local_name_does_not_count_as_the_same_branch(self):
        self.git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/feature/fresh")
        self.git(self.repo, "checkout", "-q", "-b", "fresh")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("nothing to pull", finished.stdout)
        self.assertEqual(self.status(), ["M  f"])

    def test_a_branch_with_no_upstream_pulls_the_remote_branch_of_the_same_name(self):
        self.git(self.repo, "checkout", "-q", "-b", "shared")
        self.git(self.repo, "push", "-q", "origin", "shared")
        other = self.clone("other-shared")
        self.git(other, "checkout", "-q", "shared")
        self.write(other, "h", "2\n")
        self.git(other, "add", "h")
        self.git(other, "commit", "-qm", "other h")
        self.git(other, "push", "-q", "origin", "shared")
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual((self.repo / "h").read_text(), "2\n")
        self.assertEqual(self.status(), ["M  f"])

    def test_a_branch_with_no_upstream_and_no_origin_exits_1_with_the_git_error(self):
        self.git(self.repo, "checkout", "-q", "-b", "fresh")
        self.git(self.repo, "remote", "remove", "origin")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1)
        self.assertIn("could not look up fresh on origin", finished.stderr)

    def commit_local(self, name, text):
        self.write(self.repo, name, text)
        self.git(self.repo, "add", name)
        self.git(self.repo, "commit", "-qm", "local " + name)

    def assert_names_both_ways_out(self, stderr):
        self.assertIn(f"git -C {self.repo} rebase --continue", stderr)
        self.assertIn(f"git -C {self.repo} rebase --abort", stderr)
        self.assertIn("refs/heads/master", stderr)

    def test_a_run_inside_a_stopped_rebase_touches_nothing_and_names_the_way_out(self):
        self.commit_local("h", "local\n")
        env = {**os.environ, **GIT_ENV, "GIT_SEQUENCE_EDITOR": "sed -i 1s/^pick/edit/"}
        subprocess.run(["git", "-C", str(self.repo), "rebase", "-q", "-i", "HEAD~1"], check=True, env=env,
                       capture_output=True)
        self.write(self.repo, "f", "staged\n")
        self.git(self.repo, "add", "f")
        self.write(self.repo, "g", "unstaged\n")
        head = self.git(self.repo, "rev-parse", "HEAD")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertEqual(sorted(self.status()), [" M g", "M  f"])
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD"), head)
        self.assertIn("a rebase is stopped", finished.stderr)
        self.assertIn("no conflicted paths", finished.stderr)
        self.assert_names_both_ways_out(finished.stderr)

    def test_a_pull_that_stops_mid_rebase_names_the_conflict_and_both_ways_out(self):
        self.push_from_other_machine("f", "theirs\n")
        self.commit_local("f", "local\n")
        self.write(self.repo, "g", "unstaged\n")

        finished = self.run_script()

        self.assertEqual(finished.returncode, 1, finished.stderr)
        self.assertIn("conflicted paths: f", finished.stderr)
        self.assert_names_both_ways_out(finished.stderr)
        self.assertIn("stash apply --index", finished.stderr)
        saved = finished.stderr.split("stash apply --index ")[1].split()[0]
        self.assertEqual(self.git(self.repo, "show", saved + ":g"), "unstaged\n")


if __name__ == "__main__":
    unittest.main()
