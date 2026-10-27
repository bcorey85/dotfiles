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
}


class PipeShellCheckTest(unittest.TestCase):
    def test_a_pipe_into_a_wrapped_shell_is_denied(self):
        for name, command in DENIED_COMMANDS.items():
            with self.subTest(name=name):
                finished = subprocess.run([sys.executable, str(CHECKER)], input=command, text=True,
                                          capture_output=True)
                self.assertEqual(1, finished.returncode, command)
                self.assertEqual("", finished.stderr, command)


if __name__ == "__main__":
    unittest.main()
