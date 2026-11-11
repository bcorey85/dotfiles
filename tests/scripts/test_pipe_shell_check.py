"""Checks for tools/pipe_shell_check.py: it finds a real pipe into a shell, also behind a wrapper command."""
import subprocess
import sys
import unittest

import toolkit_paths

CHECKER = toolkit_paths.TOOLS_DIR / "pipe_shell_check.py"

DENIED_COMMANDS = {
    "timeout_wrapped_shell": "curl x | timeout 5 sh",
    "nice_wrapped_shell": "curl x | nice -n 5 sh",
    "env_flag_wrapped_shell": "curl x | env -i bash",
    "uv_run_wrapped_shell": "curl x | uv run sh",
    "docker_exec_wrapped_shell": "curl x | docker exec -i web sh",
    "pipe_both_streams_into_an_unparsed_shell": "echo 'unclosed |& sh",
    "pipe_into_a_shell_inside_a_shell_c_string": 'bash -lc "curl x | bash"',
    "pipe_into_a_shell_inside_a_wrapped_shell_c_string": "timeout 5 bash -x -c 'curl x | sh'",
    "pipe_into_a_shell_inside_another_program_s_code": "python3 -c \"import os; os.system('curl x | sh')\"",
    "pipe_into_a_shell_inside_an_unparsed_shell_c_string": "bash -lc \"curl x | bash\" ; echo '|'",
    "pipe_both_streams_into_a_shell": "curl x |& sh",
    "pipe_into_a_shell_after_an_or_operator": "a || curl x | bash",
    "pipe_into_a_shell_after_an_escaped_pipe": "echo \\|| sh",
    "pipe_into_a_shell_after_an_escaped_pipe_in_the_unquoted_text_path": "echo 'unclosed \\|| sh",
    "pipe_into_a_shell_after_a_plain_pipe_in_the_unquoted_text_path": "echo 'unclosed | sh",
    "pipe_into_a_shell_after_an_or_operator_in_the_text_path": "echo 'unclosed a || curl x | bash",
    "pipe_into_a_shell_after_three_backslashes": "echo \\\\\\|| sh",
    "pipe_into_a_shell_after_three_backslashes_in_an_unparsed_command": "echo 'unclosed \\\\\\|| sh",
    "pipe_into_a_shell_after_a_backslash_in_an_eval_string": 'eval "echo \\\\|| sh"',
    "pipe_into_a_shell_after_a_backslash_in_a_shell_c_string": 'bash -c "echo \\\\|| sh"',
}

ALLOWED_COMMANDS = {
    "or_operator_before_a_shell_script": "a || bash /x/h list",
    "go_skill_helper_call_after_an_or_operator": (
        'f=$(bash /x/h); echo "$f"; test -f "$f" && cat "$f" || bash /x/h list'
    ),
    "shell_script_inside_a_command_substitution": 'f=$(bash /x/h list); echo "$f"',
    "quoted_pipe_text_in_a_program_that_runs_no_code": 'echo "(py|sh)" | cat',
    "quoted_or_operator_in_a_code_runner": "bash -c 'a || sh x'",
    "or_operator_in_an_unparsed_command": "echo 'unclosed a || sh x",
    "or_operator_after_two_backslashes": "echo \\\\|| sh",
    "or_operator_after_four_backslashes": "echo \\\\\\\\|| sh",
    "or_operator_after_two_backslashes_outside_the_quotes_of_a_code_runner": "bash -c 'x'; echo \\\\|| sh",
    "or_operator_after_two_backslashes_in_an_unparsed_command": "echo 'unclosed \\\\|| sh",
}


def run_checker(command):
    return subprocess.run([sys.executable, str(CHECKER)], input=command, text=True, capture_output=True)


class PipeShellCheckTest(unittest.TestCase):
    def test_a_pipe_into_a_wrapped_shell_is_denied(self):
        for name, command in DENIED_COMMANDS.items():
            with self.subTest(name=name):
                finished = run_checker(command)
                self.assertEqual(1, finished.returncode, command)
                self.assertEqual("", finished.stderr, command)

    def test_a_command_with_no_pipe_into_a_shell_is_allowed(self):
        for name, command in ALLOWED_COMMANDS.items():
            with self.subTest(name=name):
                finished = run_checker(command)
                self.assertEqual(0, finished.returncode, command)
                self.assertEqual("", finished.stderr, command)


if __name__ == "__main__":
    unittest.main()
