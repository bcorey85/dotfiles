"""Every gate that names a working tree gets its identity from reviewed_tree.tree_fingerprint, so a change to an
untracked file gives each of them a new value, and a tree that did not change gives the same one."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

for folder in (toolkit_paths.GATES_DIR, toolkit_paths.REVIEW_DIR, toolkit_paths.LIB_DIR):
    sys.path.insert(0, str(folder))
import full_check  # noqa: E402
import quality_check_cap  # noqa: E402
import reviewed_tree  # noqa: E402
import verify_common  # noqa: E402

UNTRACKED_NAME = "scratch.txt"


def git(top, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=top, check=True,
                   capture_output=True)


class TreeIdentityCallers(unittest.TestCase):
    def setUp(self):
        isolated_git_config = mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": os.devnull,
                                                           "GIT_CONFIG_SYSTEM": os.devnull})
        isolated_git_config.start()
        self.addCleanup(isolated_git_config.stop)
        directory = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        self.top = pathlib.Path(directory).resolve()
        git(self.top, "init", "-q")
        (self.top / "kept.txt").write_text("committed\n")
        git(self.top, "add", ".")
        git(self.top, "commit", "-q", "-m", "base")
        (self.top / UNTRACKED_NAME).write_text("first\n")
        self.log = self.top.parent / (self.top.name + ".log")

    def callers(self):
        """Each caller's name and its value for the tree as it stands."""
        return {
            "reviewed_tree.fingerprint": reviewed_tree.fingerprint(self.top)[1],
            "quality_check_cap.git_state_hash": quality_check_cap.git_state_hash(str(self.top)),
            "verify_common.tree_fingerprint": verify_common.tree_fingerprint(self.top),
            "full_check.checked_tree_fingerprint": full_check.checked_tree_fingerprint(str(self.top), str(self.log)),
        }

    def test_untracked_file_change_gives_every_caller_a_new_fingerprint(self):
        before = self.callers()

        (self.top / UNTRACKED_NAME).write_text("second\n")
        after = self.callers()

        for name, value in before.items():
            self.assertNotEqual(after[name], value, f"{name} ignored an untracked file's new content")

    def test_unchanged_tree_gives_every_caller_the_one_tree_value(self):
        values = self.callers()
        tree_value = values.pop("reviewed_tree.fingerprint")
        values["quality_check_cap.git_state_hash"] = values["quality_check_cap.git_state_hash"].split(":", 1)[1]

        for name, value in values.items():
            self.assertEqual(value, tree_value, f"{name} disagrees with reviewed_tree on the same tree")

    def test_full_check_fingerprints_a_repo_with_no_commit_as_the_cap_does(self):
        unborn = pathlib.Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, unborn, ignore_errors=True)
        git(unborn, "init", "-q")
        (unborn / "staged.txt").write_text("staged\n")
        git(unborn, "add", "staged.txt")
        log = unborn.parent / (unborn.name + ".log")

        checked = full_check.checked_tree_fingerprint(str(unborn), str(log))
        state = quality_check_cap.git_state_hash(str(unborn))

        self.assertIsNotNone(checked)
        self.assertTrue(state.startswith("unborn:"))
        self.assertEqual(checked, state.removeprefix("unborn:"))

    def test_full_check_fingerprint_leaves_its_own_log_out(self):
        inside_log = self.top / "check.log"
        before = full_check.checked_tree_fingerprint(str(self.top), str(inside_log))

        inside_log.write_text("output\n")
        after = full_check.checked_tree_fingerprint(str(self.top), str(inside_log))

        self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
