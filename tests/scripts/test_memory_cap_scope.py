"""Checks for lib/memory_cap_scope.py and its use in inline_interpreter_hint.py: a test run outside a memory-capped
systemd scope is denied with the capped form, a command that only names a runner or already runs in a scope passes,
and a child that allocates past the cap is killed while the calling shell survives."""
import json
import os
import subprocess
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import memory_cap_scope

HOOK = toolkit_paths.GATES_DIR / "inline_interpreter_hint.py"

CAUGHT = {
    "unittest_piped_to_tail": "python3 -m unittest discover -s bin 2>&1 | tail -5",
    "pytest": "pytest -x tests/",
    "python_module_pytest_after_cd": "cd app && python -m pytest",
    "vitest": "npx vitest run",
    "jest": "npx jest --ci",
    "npm_test": "npm test",
    "tests_run_sh_through_bash": "bash tests/run.sh",
    "tests_run_sh_direct": "./tests/run.sh",
    "tests_run_sh_with_env_and_home_path": "REAL_PLANS=1 bash ~/dotfiles/tests/run.sh",
    "pytest_under_timeout": "timeout 60 pytest",
    "second_step_of_a_chain": "echo start && pytest",
}
PASSED = {
    "grep_names_pytest": "grep pytest requirements.txt",
    "cat_run_script": "cat tests/run.sh",
    "edit_run_script": "vim tests/run.sh",
    "commit_message_names_pytest": "git commit -m 'run pytest'",
    "echo_runner": "echo vitest",
    "pytest_help": "pytest --help",
    "unittest_help": "python3 -m unittest -h",
    "already_capped_pytest": "systemd-run --user --scope -p MemoryMax=4G pytest",
    "already_capped_run_sh": f"{memory_cap_scope.CAPPED_PREFIX} bash tests/run.sh",
    "already_capped_with_env": "FOO=1 systemd-run --user --scope -q -p MemoryMax=1G python3 -m unittest",
    "plain_ls": "ls tests",
    "unsplittable_text": "echo 'unterminated",
}


def systemd_scope_works():
    if not memory_cap_scope.cap_available():
        return False
    probe = subprocess.run(
        ["systemd-run", "--user", "--scope", "--quiet", "-p", "MemoryMax=64M", "-p", "MemorySwapMax=0", "true"],
        capture_output=True, timeout=30)
    return probe.returncode == 0


def run_hook(command, env=None):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True,
                          env=env or os.environ, timeout=30)


class MatcherTest(unittest.TestCase):
    def test_caught(self):
        for name, command in CAUGHT.items():
            with self.subTest(name):
                self.assertTrue(memory_cap_scope.uncapped_test_run(command), command)

    def test_passed(self):
        for name, command in PASSED.items():
            with self.subTest(name):
                self.assertFalse(memory_cap_scope.uncapped_test_run(command), command)


RUN_WITH_SCOPE = ("import sys, runpy; sys.path.insert(0, sys.argv[1]); import memory_cap_scope; "
                  "memory_cap_scope.cap_available = lambda: True; sys.argv = [sys.argv[2]]; "
                  "runpy.run_path(sys.argv[0], run_name='__main__')")


class HookTest(unittest.TestCase):
    def test_denies_with_the_capped_form_where_a_scope_runs(self):
        result = subprocess.run(
            [sys.executable, "-c", RUN_WITH_SCOPE, str(toolkit_paths.LIB_DIR), str(HOOK)],
            input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "pytest -x"}}),
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("systemd-run --user --scope", decision["permissionDecisionReason"])
        self.assertIn("MemorySwapMax=0", decision["permissionDecisionReason"])

    def test_a_machine_with_no_scope_passes_the_call(self):
        result = subprocess.run(["/usr/bin/env", "-i", "PATH=/nonexistent", sys.executable, str(HOOK)],
                                input=json.dumps({"tool_name": "Bash", "tool_input": {"command": "pytest"}}),
                                capture_output=True, text=True, timeout=30)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_unreadable_input_passes_the_call(self):
        result = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True,
                                timeout=30)
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_skip_switch_passes_the_call(self):
        env = dict(os.environ, CLAUDE_SKIP_HOOKS="1")
        result = run_hook("pytest", env=env)
        self.assertEqual((result.returncode, result.stdout), (0, ""))


@unittest.skipUnless(systemd_scope_works(), "systemd-run --user --scope is not available on this machine")
class KillTest(unittest.TestCase):
    def test_child_past_the_cap_is_killed_and_the_calling_shell_survives(self):
        allocate = "x = bytearray(512 * 1024 * 1024); x[::4096] = b'1' * len(x[::4096]); print('survived')"
        script = ('systemd-run --user --scope --quiet -p MemoryMax=64M -p MemorySwapMax=0 '
                  f'python3 -c "{allocate}"; echo "child_status=$?"; echo parent_alive')
        result = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=120)
        self.assertNotIn("survived", result.stdout)
        self.assertIn("parent_alive", result.stdout)
        self.assertNotIn("child_status=0", result.stdout)


if __name__ == "__main__":
    unittest.main()
