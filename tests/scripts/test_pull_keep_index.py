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


if __name__ == "__main__":
    unittest.main()
