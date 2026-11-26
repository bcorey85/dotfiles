"""Checks for shell_quoting.py: which positions of a command text lie inside quotes."""
import os
import pathlib
import sys
import unittest

import toolkit_paths

HERE = pathlib.Path(__file__).resolve().parent
LIVE_SCRIPTS_DIR = toolkit_paths.LIB_DIR
SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "shell_quoting.py").exists()
                                                                  else LIVE_SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from shell_command import split_command_steps
from shell_quoting import (
    join_line_continuations,
    literal_positions,
    quoted_positions,
    shell_word,
    strip_comments,
    without_quote_characters,
)


class ShellWordTest(unittest.TestCase):
    def test_plain_text_is_double_quoted_and_text_double_quotes_cannot_hold_is_single_quoted(self):
        cases = {
            "/w/a b.ts": '"/w/a b.ts"',
            "/w/it's": '"/w/it\'s"',
            "/w/a $(x)": "'/w/a $(x)'",
            "/w/a`x`": "'/w/a`x`'",
            "/w/a\\x": "'/w/a\\x'",
            "/w/a!x": "'/w/a!x'",
            '/w/a"b': "'/w/a\"b'",
            "/w/a\nx": "'/w/a\nx'",
            "/w/it's $x": "'/w/it'\"'\"'s $x'",
        }
        for text, expected in cases.items():
            with self.subTest(text):
                self.assertEqual(shell_word(text), expected)


class WithoutQuoteCharactersTest(unittest.TestCase):
    def test_quotes_and_backslashes_are_dropped_and_other_text_stays(self):
        cases = {
            "t\"\"ee": "tee",
            "t\\ee": "tee",
            "git 'commit' -m \"a b\"": "git commit -m a b",
            "plain text": "plain text",
        }
        for text, expected in cases.items():
            with self.subTest(text):
                self.assertEqual(without_quote_characters(text), expected)


class QuotedPositionsTest(unittest.TestCase):
    def test_an_unclosed_quote_covers_the_rest_unless_told_otherwise(self):
        command = "echo 'a | sh"
        pipe_index = command.index("|")
        self.assertIn(pipe_index, quoted_positions(command))
        self.assertNotIn(pipe_index, quoted_positions(command, unclosed_is_quoted=False))

    def test_a_closed_quote_covers_its_text_either_way(self):
        command = "echo 'a | b' | sh"
        inside = command.index("|")
        for unclosed_is_quoted in (True, False):
            positions = quoted_positions(command, unclosed_is_quoted=unclosed_is_quoted)
            self.assertIn(inside, positions)
            self.assertNotIn(command.rindex("|"), positions)

    def test_a_backslash_quote_inside_an_ansi_c_string_does_not_close_it(self):
        command = "h $'echo \\'a > b\\'' > out"
        positions = quoted_positions(command)
        self.assertIn(command.index("> b"), positions)
        self.assertNotIn(command.rindex(">"), positions)

    def test_a_quote_after_an_escaped_dollar_or_a_pid_is_a_plain_quote(self):
        for command in ("echo \\$'a\\' > out; echo '|'", "echo $$'a\\' > out; echo '|'"):
            positions = quoted_positions(command)
            self.assertNotIn(command.index(">"), positions, command)
            self.assertIn(command.rindex("|"), positions, command)

    def test_a_backslash_in_a_plain_single_quote_stays_literal(self):
        command = "echo 'a\\' > out"
        self.assertNotIn(command.rindex(">"), quoted_positions(command))

    def test_the_code_in_a_substitution_inside_double_quotes_is_not_quoted(self):
        for command in ('echo "a $(echo x > f) b"', 'echo "a `echo x > f` b"'):
            positions = quoted_positions(command)
            self.assertNotIn(command.rindex(">"), positions, command)
            self.assertIn(command.index("b"), positions, command)

    def test_a_quote_nested_in_a_substitution_in_double_quotes_is_quoted_by_its_own_state(self):
        command = 'echo "$(echo "q > r" > f)"'
        positions = quoted_positions(command)
        self.assertIn(command.index("q"), positions)
        self.assertNotIn(command.rindex(">"), positions)

    def test_a_comment_hides_its_text_up_to_the_newline_only(self):
        command = "echo a # b > c\necho d > e"
        positions = quoted_positions(command)
        self.assertIn(command.index("> c"), positions)
        self.assertNotIn(command.index("#"), positions)
        self.assertNotIn(command.rindex(">"), positions)

    def test_a_comment_that_ends_the_command_hides_its_text_to_the_end(self):
        command = "echo a > b # c > d"
        positions = quoted_positions(command)
        self.assertNotIn(command.index(">"), positions)
        self.assertNotIn(command.index("#"), positions)
        self.assertIn(command.rindex(">"), positions)

    def test_a_hash_after_an_operator_or_at_the_start_starts_a_comment(self):
        for command in ("true;# x > y", "true&# x > y", "true|# x > y", "(# x > y", "# x > y"):
            with self.subTest(command=command):
                self.assertIn(command.index(">"), quoted_positions(command))

    def test_a_hash_inside_a_word_starts_no_comment(self):
        command = "echo a#b > c"
        self.assertNotIn(command.index(">"), quoted_positions(command))

    def test_a_quote_inside_a_comment_opens_no_quote(self):
        command = "echo a # it's\necho b > c"
        self.assertNotIn(command.rindex(">"), quoted_positions(command))

    def test_the_text_after_a_substitution_in_double_quotes_is_quoted_again(self):
        command = 'echo "$(true) | x" | y'
        positions = quoted_positions(command)
        self.assertIn(command.index("| x"), positions)
        self.assertNotIn(command.rindex("|"), positions)

    def test_a_hash_after_a_backslash_newline_starts_a_comment_but_one_after_an_escaped_blank_does_not(self):
        continued = "echo a \\\n#it's fine\ngit commit -m x"
        self.assertEqual(2, len(split_command_steps(continued)))
        escaped = "echo a\\ #it's fine\ngit commit -m x"
        self.assertEqual(1, len(split_command_steps(escaped)))


class StripCommentsTest(unittest.TestCase):
    def test_an_apostrophe_in_a_comment_does_not_hide_the_next_comments(self):
        command = "ls # it's\nls # don't\nsed -i x f"

        self.assertEqual("ls \nls \nsed -i x f", strip_comments(command))

    def test_a_hash_after_an_escaped_blank_starts_no_comment(self):
        self.assertEqual("echo x\\ #; touch tracked.txt", strip_comments("echo x\\ #; touch tracked.txt"))

    def test_a_hash_after_a_paren_that_ends_or_sits_inside_a_word_starts_no_comment(self):
        for command in ("ls *(#q.) ; git commit -m y", "echo $(true)#x; git commit -m y",
                        "echo <(true)#x; git commit -m y", "echo (true)#x; git commit -m y"):
            with self.subTest(command=command):
                self.assertEqual(command, strip_comments(command))

    def test_a_hash_after_a_paren_that_starts_a_word_starts_a_comment(self):
        self.assertEqual("( \nls", strip_comments("( # c\nls"))
        self.assertEqual("((\nls", strip_comments("((# c\nls"))

    def test_a_hash_inside_quotes_is_kept(self):
        self.assertEqual("echo '# a'", strip_comments("echo '# a'"))
        self.assertEqual('echo "x # y" ', strip_comments('echo "x # y" # z'))


class JoinLineContinuationsTest(unittest.TestCase):
    def test_a_backslash_newline_joins_but_an_escaped_backslash_before_a_newline_does_not(self):
        cases = {
            "a\\\nb": "ab",
            "a\\\\\nb": "a\\\\\nb",
            "a\\\r\nb": "ab",
            "'a\\\n'b": "'a\\\n'b",
            '"a\\\nb"': '"ab"',
        }
        for text, expected in cases.items():
            self.assertEqual(expected, join_line_continuations(text), repr(text))


class LiteralPositionsTest(unittest.TestCase):
    def test_single_quoted_and_backslash_escaped_characters_are_literal_but_double_quoted_are_not(self):
        cases = {
            "'$a'": {1, 2},
            "\\$a": {1},
            '"$a"': set(),
            "$a": set(),
        }
        for text, expected in cases.items():
            self.assertEqual(expected, literal_positions(text), text)


if __name__ == "__main__":
    unittest.main()
