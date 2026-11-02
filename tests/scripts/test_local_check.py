"""Checks for lib/local_check.py: the per-repo quality check in the machine-local CLAUDE.local.md."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import local_check


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=cwd, check=True,
                   capture_output=True, stdin=subprocess.DEVNULL)


class LocalCheckTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name).resolve()
        self.home = self.scratch / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.repo = self.scratch / "shop-api"
        self.repo.mkdir()
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "first")
        home_patch = mock.patch.dict(os.environ, {"HOME": str(self.home)})
        home_patch.start()
        self.addCleanup(home_patch.stop)

    def write_local(self, text):
        (self.home / ".claude" / "CLAUDE.local.md").write_text(text)

    def test_the_entry_named_for_the_repo_gives_its_command(self):
        self.write_local("# Notes\nQuality check (other): `false`\nQuality check (shop-api): `make check`\n")

        self.assertEqual("make check", local_check.local_check_command(self.repo))

    def test_a_list_item_entry_is_read_too(self):
        self.write_local("- Quality check (shop-api): `pnpm run check`\n")

        self.assertEqual("pnpm run check", local_check.local_check_command(self.repo))

    def test_a_missing_file_or_a_missing_entry_gives_none(self):
        self.assertIsNone(local_check.local_check_command(self.repo))

        self.write_local("Quality check (other): `false`\nQuality check: `bare line is not an entry`\n")

        self.assertIsNone(local_check.local_check_command(self.repo))

    def test_a_linked_worktree_with_another_folder_name_matches_the_main_checkout_entry(self):
        self.write_local("Quality check (shop-api): `make check`\n")
        linked = self.scratch / "shop-api-ABC-123"
        git(self.repo, "worktree", "add", "-q", "-b", "abc-123", str(linked))

        self.assertEqual("shop-api", local_check.main_checkout_name(linked))
        self.assertEqual("make check", local_check.local_check_command(linked))

    def test_a_folder_outside_git_is_named_by_its_own_folder(self):
        plain = self.scratch / "plain-repo"
        plain.mkdir()

        self.assertEqual("plain-repo", local_check.main_checkout_name(plain))


if __name__ == "__main__":
    unittest.main()
