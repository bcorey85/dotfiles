"""Checks for git_alias_commits.py: whether a git call makes a commit through an alias."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

HERE = pathlib.Path(__file__).resolve().parent
LIVE_SCRIPTS_DIR = toolkit_paths.LIB_DIR
SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "git_alias_commits.py").exists()
                                                                  else LIVE_SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from git_alias_commits import git_words_make_commit
from git_commit_calls import UNPLACED_COMMIT


def no_shell_text_commits(_text):
    return False


def makes_commit(words, directory=None):
    return git_words_make_commit(words, directory, 0, no_shell_text_commits, 3)


class GitWordsMakeCommitTest(unittest.TestCase):
    def test_an_alias_is_read_from_the_calls_own_option(self):
        self.assertTrue(makes_commit(["git", "-c", "alias.ci=commit", "ci"]))

    def test_an_alias_option_matches_without_regard_to_case(self):
        self.assertTrue(makes_commit(["git", "-c", "ALIAS.ci=commit", "ci"]))
        self.assertTrue(makes_commit(["git", "-c", "alias.CI=commit", "ci"]))

    def test_an_alias_that_names_another_alias_of_the_calls_own_options_is_read(self):
        words = ["git", "-c", "alias.a=b", "-c", "alias.b=commit", "a", "-m", "x"]
        self.assertTrue(makes_commit(words))

    def test_an_alias_that_expands_to_no_commit_is_no_commit(self):
        self.assertFalse(makes_commit(["git", "-c", "alias.st=status", "st"]))


class RepoConfigAliasTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = self.temp.name
        subprocess.run(["git", "init", "-q", self.repo], check=True)

    def set_alias(self, name, value):
        subprocess.run(["git", "-C", self.repo, "config", "alias." + name, value], check=True)

    def set_chain(self, length):
        for number in range(1, length):
            self.set_alias(f"a{number}", f"a{number + 1}")
        self.set_alias(f"a{length}", "commit")

    def test_a_chain_of_four_aliases_commits_and_a_chain_of_five_does_not(self):
        self.set_chain(4)
        self.assertTrue(makes_commit(["git", "a1"], self.repo), "four aliases deep is read")
        self.set_chain(5)
        self.assertFalse(makes_commit(["git", "a1"], self.repo), "five aliases deep is past the limit")

    def test_the_repo_config_is_read_only_for_a_directory_that_is_a_repo(self):
        self.set_alias("ci", "commit")
        self.assertTrue(makes_commit(["git", "ci"], self.repo))
        self.assertFalse(makes_commit(["git", "ci"], None), "no directory reads no config")
        self.assertFalse(makes_commit(["git", "ci"], "/nonexistent-directory"), "no repo reads no alias")

    def test_an_alias_named_like_a_plain_subcommand_is_never_read(self):
        self.set_alias("status", "commit")
        self.assertFalse(makes_commit(["git", "status"], self.repo))

    def test_an_alias_named_like_a_committing_subcommand_does_not_hide_the_commit(self):
        self.set_alias("commit", "status")
        self.assertTrue(makes_commit(["git", "commit", "-m", "x"], self.repo))

    def test_an_alias_value_that_cannot_be_parsed_counts_as_a_commit(self):
        self.set_alias("bad", 'commit "unterminated')
        self.assertTrue(makes_commit(["git", "bad"], self.repo))

    def test_an_alias_with_a_blank_value_is_no_commit(self):
        self.set_alias("blank", "  ")
        self.assertFalse(makes_commit(["git", "blank"], self.repo))

    def test_a_shell_alias_is_read_by_the_callback_and_its_answer_returned(self):
        self.set_alias("ship", "!git commit -am x")
        seen = []

        def shell_text_commits(text):
            seen.append(text)
            return True

        answer = git_words_make_commit(["git", "ship"], self.repo, 0, shell_text_commits, 3)
        self.assertEqual(answer, UNPLACED_COMMIT)
        self.assertEqual(seen, ["git commit -am x"])
        answer = git_words_make_commit(["git", "ship"], self.repo, 0, no_shell_text_commits, 3)
        self.assertFalse(answer)


if __name__ == "__main__":
    unittest.main()
