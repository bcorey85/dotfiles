"""Checks for the git_push_main rule of bash-safety-gate.sh: it reads only the arguments of each `git push`."""
import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.SCRIPTS_DIR) / "bash-safety-gate.sh"

DENIED_PUSHES = [
    "git push origin main",
    "git push origin master",
    "git push origin HEAD:main",
    "git push origin +master",
    "git push --force origin master",
    "git push origin feature:refs/heads/main",
    "git worktree add ../x origin/master && git push origin main",
]
ALLOWED_PUSHES = [
    "git worktree add ../wt -b fix/x origin/master && git push -u origin fix/push-hook-scope",
    "python3 bin/build_queue.py set stop-hook-blocks-from-ending-main-turns-and-run --status done"
    " && git push origin bench-base",
    "git push origin bench-base",
    "git push",
    "git push origin feature/main-menu",
]


class GitPushMainRuleTest(unittest.TestCase):
    def setUp(self):
        self.home = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.home, ignore_errors=True)

    def decision_for(self, command):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        finished = subprocess.run(["bash", str(SCRIPT)], input=json.dumps({"tool_input": {"command": command}}),
                                  capture_output=True, text=True, env=env, check=True)
        if not finished.stdout.strip():
            return "allow", ""
        output = json.loads(finished.stdout)["hookSpecificOutput"]
        return output["permissionDecision"], output["permissionDecisionReason"]

    def test_pushes_to_main_or_master_are_denied(self):
        for command in DENIED_PUSHES:
            with self.subTest(command=command):
                decision, reason = self.decision_for(command)
                self.assertEqual(decision, "deny")
                self.assertTrue("git_push_main" in reason or "git_force_push" in reason, reason)

    def test_pushes_to_other_branches_are_allowed_beside_a_main_word(self):
        for command in ALLOWED_PUSHES:
            with self.subTest(command=command):
                decision, reason = self.decision_for(command)
                self.assertNotIn("git_push_main", reason)
                self.assertNotEqual(decision, "deny", reason)


if __name__ == "__main__":
    unittest.main()
