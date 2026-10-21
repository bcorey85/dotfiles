"""Checks for shell_command.py: reading a command line as steps joined by operators."""
import os
import pathlib
import sys
import unittest

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or pathlib.Path.home() / ".claude" / "scripts")
sys.path.insert(0, str(SCRIPTS_DIR))

from shell_command import split_command_steps, step_surely_ran  # noqa: E402


class SplitCommandStepsTest(unittest.TestCase):
    def test_each_step_carries_the_operator_before_it(self):
        steps = split_command_steps("a && b || c | d; e\nf")
        self.assertEqual(steps, [("", "a "), ("&&", " b "), ("||", " c "), ("|", " d"), (";", " e"), (";", "f")])

    def test_single_step_has_no_operator(self):
        self.assertEqual(split_command_steps("ls -la"), [("", "ls -la")])


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


if __name__ == "__main__":
    unittest.main()
