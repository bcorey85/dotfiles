"""Checks for shell_command.py: reading a command line as steps joined by operators."""
import os
import pathlib
import sys
import unittest

import toolkit_paths

HERE = pathlib.Path(__file__).resolve().parent
LIVE_SCRIPTS_DIR = toolkit_paths.SCRIPTS_DIR
SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "shell_command.py").exists()
                                                                  else LIVE_SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from shell_command import (
    parse_simple_commands,
    redirection_writes_file,
    runs_only_after_success,
    split_command_steps,
    split_simple_commands,
    step_surely_ran,
)


class SplitSimpleCommandsTest(unittest.TestCase):
    def test_operators_and_groups_end_a_command_and_quotes_are_resolved(self):
        self.assertEqual(split_simple_commands('(cd x && git add "a b.md") ; git commit -m \'it is\' | cat & ls'),
                         [["cd", "x"], ["git", "add", "a b.md"], ["git", "commit", "-m", "it is"], ["cat"], ["ls"]])

    def test_an_unquoted_newline_ends_a_command_but_a_quoted_one_stays_in_the_word(self):
        self.assertEqual(split_simple_commands('git add a.md\ngit commit -m "one\ntwo"\n\n'),
                         [["git", "add", "a.md"], ["git", "commit", "-m", "one\ntwo"]])
        self.assertEqual(split_simple_commands("a &&\nb"), [["a"], ["b"]])

    def test_redirections_and_their_targets_are_dropped(self):
        self.assertEqual(split_simple_commands("git commit -m x 2>&1 >out.log"), [["git", "commit", "-m", "x"]])
        self.assertEqual(split_simple_commands("a &>/dev/null & b >> f"), [["a"], ["b"]])

    def test_a_hash_word_is_kept_not_read_as_a_comment(self):
        self.assertEqual(split_simple_commands("git add a.md # b"), [["git", "add", "a.md", "#", "b"]])

    def test_an_empty_quoted_word_is_a_word(self):
        self.assertEqual(split_simple_commands('git commit -m ""'), [["git", "commit", "-m", ""]])

    def test_text_it_cannot_trust_raises(self):
        for command in ('git commit -m "open', 'git commit -m ";"', "git commit -m '&&'", r"git add a\;b",
                        'a ";"', "a ;> b", 'a ">" b', "a '(' b", 'a "|" b', r"a \> b"):
            with self.assertRaises(ValueError, msg=command):
                split_simple_commands(command)

    def test_a_quoted_word_holding_only_a_newline_raises(self):
        for command in ('git commit -m y docs/x.md "\n" ls src/a.py', "a '\n' b", 'a "\n\n" b'):
            with self.assertRaises(ValueError, msg=command):
                split_simple_commands(command)

    def test_a_number_then_a_space_then_a_redirection_raises_but_a_file_descriptor_does_not(self):
        for command in ("git add a.md 5 >/dev/null", "a 5 > f", "a 12\t<in"):
            with self.assertRaises(ValueError, msg=command):
                split_simple_commands(command)
        self.assertEqual(split_simple_commands("a 2>&1 b 3>f"), [["a", "b"]])
        self.assertEqual(split_simple_commands("echo 5"), [["echo", "5"]])


class ParseSimpleCommandsTest(unittest.TestCase):
    def test_each_command_carries_its_redirections_with_their_targets(self):
        self.assertEqual(parse_simple_commands("echo x >> a.txt 2>&1 && git show HEAD:a > b <in &>c"),
                         [(["echo", "x"], [(">>", "a.txt"), (">&", "1")]),
                          (["git", "show", "HEAD:a"], [(">", "b"), ("<", "in"), ("&>", "c")])])

    def test_a_redirection_with_no_words_is_still_a_command_but_not_a_split_one(self):
        self.assertEqual(parse_simple_commands("echo x; > f"), [(["echo", "x"], []), ([], [(">", "f")])])
        self.assertEqual(split_simple_commands("echo x; > f"), [["echo", "x"]])

    def test_a_redirection_with_no_target_gets_an_empty_one(self):
        self.assertEqual(parse_simple_commands("a >"), [(["a"], [(">", "")])])
        self.assertEqual(parse_simple_commands("a > ; b"), [(["a"], [(">", "")]), (["b"], [])])
        self.assertEqual(parse_simple_commands("a > > f"), [(["a"], [(">", ""), (">", "f")])])

    def test_a_quoted_target_is_resolved_and_a_run_of_operator_characters_it_cannot_sort_raises(self):
        self.assertEqual(parse_simple_commands('a > "/dev/null"'), [(["a"], [(">", "/dev/null")])])
        with self.assertRaises(ValueError):
            parse_simple_commands("a >| f")


class RedirectionWritesFileTest(unittest.TestCase):
    def test_an_output_redirection_to_a_file_writes(self):
        for operator in (">", ">>", "&>", "&>>", ">&", "<>"):
            self.assertTrue(redirection_writes_file(operator, ".husky/pre-commit"), operator)
        self.assertTrue(redirection_writes_file(">", ""))

    def test_dev_null_and_file_descriptor_copies_do_not_write(self):
        self.assertFalse(redirection_writes_file(">", "/dev/null"))
        self.assertFalse(redirection_writes_file("&>", "/dev/null"))
        for target in ("1", "2", "12", "-", "2-"):
            self.assertFalse(redirection_writes_file(">&", target), target)
        self.assertTrue(redirection_writes_file(">", "1"))

    def test_an_input_redirection_never_writes(self):
        for operator, target in (("<", ".git/index"), ("<<", "EOF"), ("<&", "0"), ("<<<", "text")):
            self.assertFalse(redirection_writes_file(operator, target), operator)


class SplitCommandStepsTest(unittest.TestCase):
    def test_each_step_carries_the_operator_before_it(self):
        steps = split_command_steps("a && b || c | d; e\nf")
        self.assertEqual(steps, [("", "a "), ("&&", " b "), ("||", " c "), ("|", " d"), (";", " e"), (";", "f")])

    def test_single_step_has_no_operator(self):
        self.assertEqual(split_command_steps("ls -la"), [("", "ls -la")])

    def test_a_lone_ampersand_is_an_operator(self):
        self.assertEqual(split_command_steps("a & b &"), [("", "a "), ("&", " b "), ("&", "")])

    def test_redirect_and_pipe_stderr_ampersands_stay_inside_their_step(self):
        for command in ("a 2>&1", "a >&2", "a &> f", "a &>> f", "a |& b"):
            self.assertEqual(len(split_command_steps(command)), 1, command)
        self.assertEqual(len(split_command_steps("a >f 2>&1 | b")), 2)


class RunsOnlyAfterSuccessTest(unittest.TestCase):
    def test_steps_chained_by_and_run_only_after_the_earlier_step_succeeded(self):
        steps = split_command_steps("a && b && c")
        self.assertTrue(runs_only_after_success(steps, 0, 1))
        self.assertTrue(runs_only_after_success(steps, 0, 2))
        self.assertTrue(runs_only_after_success(steps, 1, 2))

    def test_semicolon_newline_or_and_pipe_let_the_later_step_run_after_a_failure(self):
        for command in ("a ; b", "a\nb", "a || b", "a | b"):
            steps = split_command_steps(command)
            self.assertFalse(runs_only_after_success(steps, 0, 1), command)

    def test_one_loose_operator_anywhere_between_the_steps_breaks_the_chain(self):
        steps = split_command_steps("a && b; c")
        self.assertTrue(runs_only_after_success(steps, 0, 1))
        self.assertFalse(runs_only_after_success(steps, 0, 2))
        self.assertFalse(runs_only_after_success(steps, 1, 2))

    def test_a_step_is_not_gated_by_itself_or_by_a_later_step(self):
        steps = split_command_steps("a && b && c")
        self.assertFalse(runs_only_after_success(steps, 1, 1))
        self.assertFalse(runs_only_after_success(steps, 2, 0))

    def test_pipes_after_the_first_and_keep_the_chain(self):
        steps = split_command_steps("a && b 2>&1 | tail && c | tail")
        self.assertEqual([runs_only_after_success(steps, 0, later) for later in (1, 2, 3, 4)], [True] * 4)

    def test_a_pipe_right_after_the_earlier_step_breaks_the_chain(self):
        steps = split_command_steps("a | cat && b")
        self.assertFalse(runs_only_after_success(steps, 0, 2))

    def test_a_group_entered_through_and_holds_the_chain_until_it_closes(self):
        steps = split_command_steps("a && { b; c; }; d")
        self.assertTrue(runs_only_after_success(steps, 0, 1))
        self.assertTrue(runs_only_after_success(steps, 0, 2))
        self.assertFalse(runs_only_after_success(steps, 0, 4))
        steps = split_command_steps("a && (b; c); d")
        self.assertTrue(runs_only_after_success(steps, 0, 2))
        self.assertFalse(runs_only_after_success(steps, 0, 3))

    def test_a_group_that_is_not_entered_through_and_gives_no_chain(self):
        steps = split_command_steps("a; { b; c; }")
        self.assertFalse(runs_only_after_success(steps, 0, 2))

    def test_an_or_before_the_earlier_step_can_skip_it(self):
        self.assertFalse(runs_only_after_success(split_command_steps("t || a && b"), 1, 2))
        self.assertFalse(runs_only_after_success(split_command_steps("x && t || a && b"), 2, 3))
        self.assertTrue(runs_only_after_success(split_command_steps("t || x; a && b"), 2, 3))
        self.assertTrue(runs_only_after_success(split_command_steps("t || x\na && b"), 2, 3))
        self.assertTrue(runs_only_after_success(split_command_steps("t & a && b"), 1, 2))

    def test_a_lone_ampersand_ends_the_chain(self):
        self.assertFalse(runs_only_after_success(split_command_steps("a & b"), 0, 1))
        self.assertFalse(runs_only_after_success(split_command_steps("a && b & c"), 0, 2))


class StepSurelyRanTest(unittest.TestCase):
    def test_after_success_only_or_hides_a_step(self):
        steps = split_command_steps("a && b || c")
        self.assertEqual([step_surely_ran(steps, i, True) for i in range(3)], [True, True, False])

    def test_after_failure_setup_steps_do_not_hide_the_next_step(self):
        steps = split_command_steps("cd x && source v && FOO=1 && export A=1 && pytest && eslint")
        self.assertEqual([step_surely_ran(steps, i, False) for i in range(6)],
                         [True, True, True, True, True, False])

    def test_after_failure_and_or_both_hide_a_step(self):
        steps = split_command_steps("a && b; c")
        self.assertEqual([step_surely_ran(steps, i, False) for i in range(3)], [True, False, False])

    def test_after_failure_semicolon_and_pipe_steps_ran(self):
        steps = split_command_steps("a; b | c")
        self.assertEqual([step_surely_ran(steps, i, False) for i in range(3)], [True, True, True])

    def test_a_step_sent_to_the_background_never_surely_ran(self):
        steps = split_command_steps("a & b")
        self.assertEqual([step_surely_ran(steps, i, True) for i in range(2)], [False, True])
        steps = split_command_steps("x; a && b | c &")
        self.assertEqual([step_surely_ran(steps, i, True) for i in range(4)], [True, False, False, False])


if __name__ == "__main__":
    unittest.main()
