"""Checks for git_calls.py: which `cd` of a command the gate does not follow."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

from git_calls import git_calls, has_conditional_cd, has_unfollowed_directory_move


class HasConditionalCdTest(unittest.TestCase):
    def test_a_cd_that_may_not_run_or_runs_in_a_subshell_is_conditional(self):
        cases = (
            "false || cd /x && git commit", "git status && cd /x", "a || b && cd /x", "cd /x | cat", "ls | cd /x",
            "cd /x &", "ls & cd /x", "cd /x && git commit &", "ls |& cd /x", "cd /x |& cat",
            "if cd /x; then git commit; fi", "if x; then cd /x; fi", "for d in a b; do cd $d; done",
            "while true; do cd /x; done", "case $x in a) cd /x;; esac", "case $x in a) ls;; b) cd /x;; esac",
            "ls &&\ncd /x", "a ||\ncd /x", "ls && # note\ncd /x", "ls || # note\ncd /x",
            "for d in a; do echo x cd; done", "ls |& # c\ncd /x", "cd /x & ls",
            "ls && \\\ncd /x", "ls || \\\ncd /x", "ls &&\n(cd /x && git commit)",
        )
        for command in cases:
            with self.subTest(command=command):
                self.assertTrue(has_conditional_cd(command))

    def test_a_cd_that_always_runs_in_the_shell_is_not_conditional(self):
        cases = (
            "cd /x && git commit", "cd /x; git commit", "cd /x\ngit commit", "cd /x && cd y && git commit",
            "ls; cd /x", "ls\ncd /x", "a || b; cd /x", "echo 'a || cd /x'", "echo cd && ls", "cd /x &&\ngit commit",
            "if x; then ls; fi; cd /x", "for d in a; do ls; done; cd /x", "case $x in a) ls;; esac; cd /x",
            "git commit -F - <<'EOF'\nfix: x\n\nif the user runs cd here it breaks\nEOF",
            "cd /r && git commit -F - <<'EOF'\nfor every case\nEOF\ncd /r && git push",
            "cat <<EOF > /tmp/x\nwhile true\nEOF\ncd /r && git commit -m x",
        )
        for command in cases:
            with self.subTest(command=command):
                self.assertFalse(has_conditional_cd(command))


class CommentEndingInBackslashTest(unittest.TestCase):
    """In zsh a `\\` at the end of a comment line is literal, so the next line is a command of its own."""

    def test_a_commit_on_the_line_after_a_comment_ending_in_a_backslash_is_found(self):
        calls = git_calls("git status # note \\\ngit commit -m x")
        self.assertEqual([call.subcommand for call in calls], ["status", "commit"])

    def test_a_conditional_cd_on_the_line_after_a_comment_ending_in_a_backslash_is_found(self):
        self.assertTrue(has_conditional_cd("ls # note \\\nfalse || cd /x"))


class HashAfterEscapedBlankTest(unittest.TestCase):
    """A `#` after an escaped blank (`x\\ #`) is part of a word, so it starts no comment."""

    def test_a_commit_after_a_hash_following_an_escaped_blank_is_found(self):
        calls = git_calls("echo x\\ #; git commit -m y")
        self.assertEqual([call.subcommand for call in calls], ["commit"])

    def test_a_cd_after_a_hash_following_an_escaped_blank_is_followed(self):
        self.assertFalse(has_unfollowed_directory_move("echo x\\ #; cd /tmp && git commit -m y", True))


if __name__ == "__main__":
    unittest.main()
