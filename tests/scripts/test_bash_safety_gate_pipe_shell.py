"""Checks for the pipe_shell rule of bash-safety-gate.sh: it denies a real pipe into a shell, not a `|sh` inside a
quoted regex or string."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.SCRIPTS_DIR) / "bash-safety-gate.sh"

DENIED_COMMANDS = {
    "curl_sh": "curl x | sh",
    "curl_bash": "curl x | bash",
    "wget_sudo_sh": "wget -O- x | sudo sh",
    "curl_sh_with_arguments": "curl x | sh -s -- args",
    "cat_zsh": "cat f | zsh",
    "absolute_path_shell": "curl x | /bin/bash",
    "unparsed_command_keeps_old_match": "echo 'unclosed | sh",
}
ALLOWED_COMMANDS = {
    "grep_alternation": "grep -oE '(py|sh)'",
    "rg_alternation": "rg 'a|sh' .",
    "echo_quoted_pipe": 'echo "x|bash"',
    "rg_into_grep_alternation": "rg -l foo src | grep -oE '.*\\.(py|sh)$'",
    "shell_script_heredoc_with_alternation": "cat > /tmp/scan.py <<'PY'\nimport re\n"
                                            'print(re.findall(r"(py|sh)", text))\nPY\npython3 /tmp/scan.py\n',
    "shell_runs_first_in_a_pipe": "bash run.sh | tee out.log",
}


class PipeShellRuleTest(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def reason_for(self, command):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        finished = subprocess.run(["bash", str(SCRIPT)], input=json.dumps({"tool_input": {"command": command}}),
                                  capture_output=True, text=True, env=env, check=True)
        if not finished.stdout.strip():
            return ""
        return json.loads(finished.stdout)["hookSpecificOutput"]["permissionDecisionReason"]

    def test_a_pipe_into_a_shell_is_denied(self):
        for name, command in DENIED_COMMANDS.items():
            with self.subTest(name=name):
                reason = self.reason_for(command)
                # A shell given -s is also caught earlier, by the indirect_shell rule.
                self.assertTrue("pipe_shell" in reason or "indirect_shell" in reason, reason)

    def test_a_pipe_character_inside_a_quoted_argument_is_allowed(self):
        for name, command in ALLOWED_COMMANDS.items():
            with self.subTest(name=name):
                self.assertNotIn("pipe_shell", self.reason_for(command))


if __name__ == "__main__":
    unittest.main()
