"""Checks for shell_expansion.py: what zsh expands in a raw command word."""
import os
import pathlib
import sys
import unittest

import toolkit_paths

HERE = pathlib.Path(__file__).resolve().parent
LIVE_SCRIPTS_DIR = toolkit_paths.LIB_DIR
SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "shell_expansion.py").exists()
                                                                  else LIVE_SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from shell_expansion import (
    BraceListError,
    cut_at_glob_qualifier,
    expand_braces,
    has_attached_glob_syntax,
    redirect_target_words,
    unquoted_expanding_word,
)


class HasAttachedGlobSyntaxTest(unittest.TestCase):
    def test_a_paren_or_angle_against_a_word_is_glob_syntax(self):
        for step in ("echo > $S/a(:h:h)", "echo > $S/a<->", "S=(a b)"):
            self.assertTrue(has_attached_glob_syntax(step), step)

    def test_a_substitution_a_process_substitution_a_descriptor_or_a_quoted_opener_is_not(self):
        for step in ("echo $(date)", "cat <(ls)", "cat 2<in", "sed 's/(a)/b/' f", "echo hi > a.txt"):
            self.assertFalse(has_attached_glob_syntax(step), step)


class RedirectTargetWordsTest(unittest.TestCase):
    def test_each_redirect_operator_form_gives_its_target_word(self):
        cases = {
            "echo hi > a.txt": ["a.txt"],
            "echo hi >> a.txt": ["a.txt"],
            "echo hi >>| {a,b}": ["{a,b}"],
            "echo hi &>>| {a,b}": ["{a,b}"],
            "echo hi >&| {a,b}": ["{a,b}"],
            "echo hi >>&| {a,b}": ["{a,b}"],
            "echo hi >! {a,b}": ["{a,b}"],
            "echo hi >>! {a,b}": ["{a,b}"],
            "echo hi >&! {a,b}": ["{a,b}"],
        }
        for text, expected in cases.items():
            self.assertEqual(redirect_target_words(text), expected, text)

    def test_a_word_ends_at_an_operator_or_a_qualifier_paren_that_it_keeps(self):
        self.assertEqual(redirect_target_words("echo hi > {a,b}(N)"), ["{a,b}("])
        self.assertEqual(redirect_target_words("echo hi > a.txt; echo x > b.txt"), ["a.txt", "b.txt"])
        self.assertEqual(redirect_target_words("echo hi >(cat)"), [])

    def test_a_quoted_blank_stays_in_the_word_and_a_quoted_operator_opens_none(self):
        self.assertEqual(redirect_target_words("echo hi > 'a b'"), ["'a b'"])
        self.assertEqual(redirect_target_words("echo 'a > b'"), [])

    def test_a_redirect_inside_a_substitution_is_not_read_and_the_word_after_it_is_whole(self):
        cases = {
            "echo $(date > /tmp/d)*": [],
            "x=$(make 2> /tmp/err)[1]": [],
            "echo hi > $(date)/x": ["$(date)/x"],
            "echo `date > /tmp/d` > out": ["out"],
        }
        for text, expected in cases.items():
            self.assertEqual(redirect_target_words(text), expected, text)

    def test_a_position_in_extra_hidden_opens_no_redirect(self):
        text = "echo $((a>b)) > out"
        self.assertEqual(redirect_target_words(text, set(range(5, 13))), ["out"])


class CutAtGlobQualifierTest(unittest.TestCase):
    def test_the_word_is_cut_at_the_first_unquoted_qualifier_paren(self):
        cases = {"{a,b}(N)": "{a,b}(", "f(N)(x)": "f(", "plain": "plain", "$(ls)": "$(ls)", "'f(N)'": "'f(N)'"}
        for word, expected in cases.items():
            self.assertEqual(cut_at_glob_qualifier(word), expected, word)


class ExpandingWordTest(unittest.TestCase):
    def test_a_glob_a_brace_list_or_a_qualifier_paren_expands_only_outside_quotes(self):
        cases = {"/tmp/*.log": True, "/tmp/{a,b}": True, "/tmp/f?": True, "/tmp/f[12]": True, "f(N)": True,
                 "'/tmp/*'": False, '"/tmp/{a,b}"': False, "${A}": False, "/tmp/${A}/x": False,
                 "$(ls)": False, "<(cat)": False, "a\\*": False,
                 "log-$(ls *.txt | head -1)": False, "${arr[1]}": False, "${f%.*}.out": False,
                 "{a,$(echo b)}": True}
        for word, expected in cases.items():
            self.assertEqual(unquoted_expanding_word(word), expected, word)

    def test_a_leading_equals_before_a_name_expands_unless_quoted_mid_word_or_beside_a_variable(self):
        cases = {"=python3": True, "=x": True, "a=b": False, "'=x'": False, '"=x"': False, "\\=x": False,
                 "=": False, "=(cat)": False, "=ls$S": False}
        for word, expected in cases.items():
            self.assertEqual(unquoted_expanding_word(word), expected, word)

    def test_a_brace_pair_with_no_comma_or_sequence_is_a_literal_name(self):
        cases = {"/tmp/{x}": False, "/tmp/a{}": False, "{a,b": False, "/tmp/{x}/{a,b}": True, "/tmp/{1..3}": True,
                 "/tmp/{a..c}": True, "/tmp/{a,b}{x}": True}
        for word, expected in cases.items():
            self.assertEqual(unquoted_expanding_word(word), expected, word)



class ExpandBracesTest(unittest.TestCase):
    def test_a_brace_list_expands_with_nesting_and_affixes(self):
        cases = {
            "{a,b}": ["a", "b"],
            "x{a,b}y": ["xay", "xby"],
            "{a,{b,c}}": ["a", "b", "c"],
            "$TMPDIR/{a,b}.log": ["$TMPDIR/a.log", "$TMPDIR/b.log"],
            "{a,b}{1,2}": ["a1", "a2", "b1", "b2"],
        }
        for word, expected in cases.items():
            self.assertEqual(expand_braces(word), expected, word)

    def test_a_word_with_no_unquoted_list_stays_as_it_is(self):
        for word in ("plain", "{a}", "'{a,b}'", "${A,b}", "{a,b", "a\\{b,c}"):
            self.assertEqual(expand_braces(word), [word], word)

    def test_a_list_of_exactly_the_limit_expands_and_one_word_more_raises(self):
        self.assertEqual(len(expand_braces("{a,b}" * 6)), 64)
        with self.assertRaises(BraceListError):
            expand_braces("{a,b}" * 7)

    def test_a_nested_list_over_the_limit_names_the_word_as_written(self):
        word = "x{a,b}{c,d}{e,f}{g,h}{i,j}{k,l}{m,n}"
        with self.assertRaises(BraceListError) as caught:
            expand_braces(word)
        self.assertEqual(str(caught.exception), f"{word} expands to more than 64 words")

    def test_a_long_chain_of_lists_raises_at_once_in_place_of_expanding_in_full(self):
        with self.assertRaises(BraceListError):
            expand_braces("{a,b}" * 40)

    def test_a_sequence_list_raises_because_it_is_not_expanded(self):
        for word in ("{1..3}", "CLA{U..U}DE.md", "f{a..c}", "f{-2..2..2}"):
            with self.assertRaises(BraceListError, msg=word):
                expand_braces(word)


if __name__ == "__main__":
    unittest.main()
