"""Checks for shell_command.py: reading a command line as steps joined by operators."""
import os
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
LIVE_SCRIPTS_DIR = pathlib.Path.home() / ".claude" / "scripts"
SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "shell_command.py").exists()
                                                                  else LIVE_SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from shell_command import runs_only_after_success, split_command_steps, step_surely_ran  # noqa: E402


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
