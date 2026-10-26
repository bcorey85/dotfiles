"""Checks that the shell safety gate and the credential-read gate name the approved next step in their deny text."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.SCRIPTS_DIR)
SAFETY_GATE = SCRIPTS_DIR / "bash-safety-gate.sh"
CREDENTIAL_READ_GATE = SCRIPTS_DIR / "block-credential-read.sh"
WRAPPED_COMMAND = "bash" + " -c 'ls -la'"


class BlockNextStepTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        (self.home / ".claude").mkdir(parents=True)

    def denial(self, script, tool_input, tool_name):
        event = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input,
                 "cwd": str(self.tmp), "session_id": "next-step-test"}
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        finished = subprocess.run(["bash", str(script)], input=json.dumps(event), capture_output=True, text=True,
                                  env=environment, cwd=str(self.tmp))
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual("deny", decision["permissionDecision"])
        return decision["permissionDecisionReason"]

    def test_the_wrapped_shell_block_names_the_direct_form(self):
        reason = self.denial(SAFETY_GATE, {"command": WRAPPED_COMMAND}, "Bash")

        self.assertIn("[indirect_shell]", reason)
        self.assertIn("Run the inner command directly as its own Bash call, without the shell wrapper", reason)

    def test_the_shell_credential_block_tells_the_agent_to_carry_on(self):
        reason = self.denial(SAFETY_GATE, {"command": "cat .env"}, "Bash")

        self.assertIn("[cat_creds]", reason)
        self.assertIn("carry on without its contents", reason)

    def test_the_read_credential_block_tells_the_agent_to_carry_on(self):
        reason = self.denial(CREDENTIAL_READ_GATE, {"file_path": str(self.tmp / ".env")}, "Read")

        self.assertIn("[env_files]", reason)
        self.assertIn("carry on without its contents", reason)


if __name__ == "__main__":
    unittest.main()
