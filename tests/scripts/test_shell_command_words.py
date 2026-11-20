"""Checks for shell_command_words.py: which raw word is the command word of a word list."""
import os
import pathlib
import sys
import unittest

import toolkit_paths

HERE = pathlib.Path(__file__).resolve().parent
LIVE_SCRIPTS_DIR = toolkit_paths.LIB_DIR
SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "shell_command_words.py").exists()
                                                                  else LIVE_SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from shell_command_words import command_word_index, raw_word_names_command, without_subshell_closers


class RawWordNamesCommandTest(unittest.TestCase):
    def test_a_quoted_escaped_path_or_grouped_word_reads_as_the_command(self):
        for word in ('"tee"', "\\tee", "'t'ee", "/usr/bin/tee", "(tee", 't""ee', "te''e"):
            self.assertTrue(raw_word_names_command(word, "tee"), word)

    def test_a_word_that_only_holds_the_name_is_no_match(self):
        for word in ("echo", "tee-x", 'A="a tee"'):
            self.assertFalse(raw_word_names_command(word, "tee"), word)


class CommandWordIndexTest(unittest.TestCase):
    def test_the_command_word_after_wrappers_and_groups_is_found(self):
        cases = {
            ("tee", "a"): 0,
            ('"tee"', "a"): 0,
            ("(tee", "a"): 0,
            ("(", "tee", "a"): 1,
            ("env", "A=1", "tee", "a"): 2,
            ("sudo", "-u", "root", "tee", "a"): 3,
            ("A=1", "tee", "a"): 1,
        }
        for words, expected in cases.items():
            self.assertEqual(command_word_index(list(words), "tee"), expected, words)

    def test_a_name_among_the_arguments_of_another_command_is_no_match(self):
        cases = (["grep", "tee", "*.py"], ["grep", "'a;'", "tee", "x"], ["echo", "tee"], ["env", "A=1"], ["("], [])
        for words in cases:
            self.assertIsNone(command_word_index(words, "tee"), words)


class WithoutSubshellClosersTest(unittest.TestCase):
    def test_only_the_closers_with_no_opener_in_the_word_are_dropped(self):
        cases = {"/tmp/x*)": "/tmp/x*", "/tmp/x(N))": "/tmp/x(N)", "/tmp/x(N)": "/tmp/x(N)", "a))": "a"}
        for word, expected in cases.items():
            self.assertEqual(without_subshell_closers(word), expected, word)


if __name__ == "__main__":
    unittest.main()
