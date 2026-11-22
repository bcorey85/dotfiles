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

from shell_command import parse_raw_simple_commands
from shell_command_words import (
    before_subshell_closer,
    command_word_index,
    joined_raw_words,
    placed_raw_words,
    raw_word_names_command,
)
from shell_steps import PlacedCommand


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


class JoinedRawWordsTest(unittest.TestCase):
    def joined(self, step, placed_words):
        raw_words = parse_raw_simple_commands(step)[0]
        return joined_raw_words(raw_words, placed_words, step)

    def test_a_glued_part_joins_with_no_gap(self):
        self.assertEqual(self.joined('docker run -v "$PWD":/app img', ["docker", "run", "-v", "$PWD:/app", "img"]),
                         ["docker", "run", "-v", '"$PWD":/app', "img"])

    def test_a_part_split_at_a_blank_joins_with_the_blank_that_split_it(self):
        cases = {
            'e TOKEN="$TOKEN x" img': ("TOKEN=$TOKEN x", 'TOKEN="$TOKEN x"'),
            'e TOKEN="$TOKEN\tx" img': ("TOKEN=$TOKEN\tx", 'TOKEN="$TOKEN\tx"'),
            'e TOKEN="a  b" img': ("TOKEN=a  b", 'TOKEN="a  b"'),
        }
        for step, (placed, raw) in cases.items():
            with self.subTest(step=step):
                self.assertEqual(self.joined(step, ["e", placed, "img"]), ["e", raw, "img"])


class JoinedRawWordsNoneTest(unittest.TestCase):
    def test_words_that_do_not_line_up_give_none(self):
        cases = {
            "too few raw words": ("a b", ["a", "b", "c"]),
            "too many raw words": ("a b", ["a"]),
            "a joined word that never equals the placed word": ('"a"b', ["ac"]),
        }
        for label, (step, placed_words) in cases.items():
            with self.subTest(label):
                raw_words = parse_raw_simple_commands(step)[0]
                self.assertIsNone(joined_raw_words(raw_words, placed_words, step))

    def test_a_part_missing_from_the_step_gives_none(self):
        self.assertIsNone(joined_raw_words(["a", "zz"], ["a", "zz"], "a b"))

    def test_a_part_that_is_missing_when_joining_gives_none(self):
        self.assertIsNone(joined_raw_words(["a", "b"], ["ab"], "a c"))

    def test_a_redirection_between_two_parts_gives_none(self):
        self.assertIsNone(joined_raw_words(['"a"', '"b"'], ["ab"], '"a" >f "b"'))

    def test_a_redirection_glued_between_two_parts_gives_none_even_when_the_joined_text_matches(self):
        self.assertIsNone(joined_raw_words(['"a"', '"b"'], ["a>fb"], '"a">f"b"'))


class PlacedRawWordsTest(unittest.TestCase):
    def test_words_that_line_up_are_the_raw_words(self):
        placed = PlacedCommand('docker run "a b"', ["docker", "run", "a b"], ["docker", "run", "a b"], "/")
        self.assertEqual(placed_raw_words(placed), ["docker", "run", '"a b"'])

    def test_resolved_words_are_quoted_when_none_lines_up(self):
        placed = PlacedCommand("docker run x", ["docker", "run", "a b"], ["docker", "run", "a b"], "/")
        self.assertEqual(placed_raw_words(placed), ["docker", "run", "'a b'"])

    def test_an_unclosable_quote_falls_back_to_the_resolved_words(self):
        step = 'docker run -e A=" x " img'
        words = ["docker", "run", "-e", "A= x ", "img"]
        placed = PlacedCommand(step, words, words, "/")
        self.assertEqual(placed_raw_words(placed), ["docker", "run", "-e", "'A= x '", "img"])


class BeforeSubshellCloserTest(unittest.TestCase):
    def test_the_text_is_cut_at_the_first_closer_with_no_opener_in_it(self):
        cases = {
            "/tmp/x*)": "/tmp/x*",
            "/tmp/x(N))": "/tmp/x(N)",
            "/tmp/x(N)": "/tmp/x(N)",
            "a))": "a",
            "img) foo": "img",
            "img) $(ls)": "img",
            "img sh -c 'a)b') z": "img sh -c 'a)b'",
            "img) > out": "img",
            "img ": "img",
        }
        for text, expected in cases.items():
            self.assertEqual(before_subshell_closer(text), expected, text)


if __name__ == "__main__":
    unittest.main()
