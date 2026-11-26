"""Checks for lib/memory_cap_scope.py and its use in inline_interpreter_hint.py: the matcher for a test run outside a
memory-capped systemd scope, the one plain step the hook rewrites with the capped prefix (updatedInput, no
permission decision), every other uncapped test run denied with the capped form, a foreground full suite denied
with the background text, and a child that allocates past the cap killed while the calling shell survives."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
import uuid

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import check_scope
import memory_cap_scope
from systemd_scope import systemd_scope_works

sys.path.insert(0, str(toolkit_paths.GATES_DIR))
import inline_interpreter_hint

HOOK = toolkit_paths.GATES_DIR / "inline_interpreter_hint.py"

CAUGHT = {
    "heredoc_fed_to_a_shell": "bash <<'EOF'\npytest -x tests/\nEOF",
    "heredoc_piped_into_a_shell": "cat <<'EOF' | bash\npytest -x tests/\nEOF",
    "runner_after_a_quoted_heredoc": "cat <<'EOF' > notes.md\nvitest notes\nEOF\npytest -x tests/",
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
    "systemd_run_description_value_then_other_slice": ("systemd-run --user --scope --description x "
                                                      "--slice=other.slice -p MemoryMax=8G pytest"),
    "systemd_run_with_no_slice": "systemd-run --user --scope -p MemoryMax=4G pytest",
    "systemd_run_with_another_slice": "systemd-run --user --scope --slice=other.slice -p MemoryMax=4G pytest",
    "systemd_run_with_another_slice_word": "systemd-run --user --scope --slice other -p MemoryMax=4G pytest",
    "systemd_run_slice_named_only_after_the_program": "systemd-run --user --scope pytest --slice=tests.slice",
    "timeout_then_uncapped_systemd_run": "timeout 60 systemd-run --user --scope bash tests/run.sh",
    "uncapped_systemd_run_then_timeout": "systemd-run --user --scope timeout 600 bash tests/run.sh",
    "another_slice_systemd_run_then_timeout": ("systemd-run --user --scope --slice=other.slice timeout 60 "
                                               "bash tests/run.sh"),
    "uncapped_systemd_run_then_env": "systemd-run --user --scope env FOO=1 bash tests/run.sh",
    "last_slice_is_not_shared": "systemd-run --user --scope --slice=tests.slice --slice=other.slice pytest",
    "systemd_run_unit_value_then_program": "systemd-run --user --scope -u myunit pytest",
    "systemd_run_setenv_value_then_program": "systemd-run --user --scope -E A=1 bash tests/run.sh",
}
SHARED_SLICE_FORMS = ("--slice=tests.slice", "--slice tests.slice", "--slice=tests", "--slice tests")
PASSED = {
    "grep_names_pytest": "grep pytest requirements.txt",
    "cat_run_script": "cat tests/run.sh",
    "edit_run_script": "vim tests/run.sh",
    "commit_message_names_pytest": "git commit -m 'run pytest'",
    "echo_runner": "echo vitest",
    "pytest_help": "pytest --help",
    "unittest_help": "python3 -m unittest -h",
    "already_capped_pytest": "systemd-run --user --scope --slice=tests.slice -p MemoryMax=4G pytest",
    "already_capped_run_sh": f"{memory_cap_scope.CAPPED_PREFIX} bash tests/run.sh",
    "already_capped_with_env": ("FOO=1 systemd-run --user --scope -q --slice tests.slice -p MemoryMax=1G "
                                "python3 -m unittest"),
    "last_slice_is_shared": "systemd-run --user --scope --slice=other.slice --slice=tests.slice pytest",
    "capped_pytest_under_timeout": "timeout 60 systemd-run --user --scope --slice=tests.slice pytest",
    "capped_with_unit_value": "systemd-run --user --scope -u myunit --slice=tests.slice pytest",
    "capped_with_setenv_value": "systemd-run --user --scope -E A=1 --slice=tests.slice pytest",
    "capped_with_long_unit_value": "systemd-run --user --scope --unit myunit --slice=tests.slice pytest",
    "capped_with_long_property_value": ("systemd-run --user --scope --property MemoryMax=1G "
                                        "--slice=tests.slice pytest"),
    "capped_with_description_value": ("systemd-run --user --scope --description x --slice=tests.slice "
                                      "-p MemoryMax=8G pytest"),
    "capped_with_long_setenv_value": "systemd-run --user --scope --setenv A=1 --slice=tests.slice pytest",
    # A dangling --slice is fail-open: systemd-run rejects the command itself, so the gate leaves it alone.
    "systemd_run_dangling_slice_swallows_program": "systemd-run --user --scope --slice pytest",
    "systemd_run_dangling_slice_last_word": "echo pytest && systemd-run --user --scope --slice",
    "plain_ls": "ls tests",
    "unsplittable_text": "echo 'unterminated",
    # The bench call the gate once denied: quoted heredoc bodies and a quoted argument name vitest.
    "heredoc_bodies_name_runners": ("Q=bin/build_queue.py\npython3 $Q new --description \"runs vitest uncapped.\" "
                                    "--body - \"t\" <<'EOF'\nIt runs vitest without the cap.\nEOF\n"
                                    "python3 $Q new --body - \"u\" <<'EOF'\npytest and bash tests/run.sh\nEOF\n"
                                    "python3 $Q; echo rc=$?"),
}


def run_hook(command, env=None):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    return subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True,
                          env=env or os.environ, timeout=30)


STOWED_UNIT = toolkit_paths.REPO_ROOT / "systemd" / ".config" / "systemd" / "user" / memory_cap_scope.TEST_SLICE


class MatcherTest(unittest.TestCase):
    def test_each_shared_slice_form_counts_as_capped(self):
        for form in SHARED_SLICE_FORMS:
            with self.subTest(form):
                command = f"systemd-run --user --scope {form} -p MemoryMax=8G pytest"
                self.assertFalse(memory_cap_scope.uncapped_test_run(command), command)

    def test_the_capped_prefix_names_the_shared_slice_and_the_per_run_cap(self):
        prefix = memory_cap_scope.CAPPED_PREFIX
        self.assertIn(f"--slice={memory_cap_scope.TEST_SLICE}", prefix)
        self.assertIn(f"MemoryMax={memory_cap_scope.MEMORY_MAX}", prefix)
        self.assertIn("MemorySwapMax=0", prefix)

    def test_the_stowed_slice_unit_caps_memory_and_swap_above_one_run(self):
        self.assertTrue(STOWED_UNIT.is_file(), STOWED_UNIT)
        lines = STOWED_UNIT.read_text().splitlines()
        self.assertIn("[Slice]", lines)
        slice_lines = lines[lines.index("[Slice]") + 1:]
        slice_caps = [line for line in slice_lines if line.startswith("MemoryMax=")]
        self.assertEqual(len(slice_caps), 1, slice_lines)
        slice_cap = slice_caps[0][len("MemoryMax="):]
        self.assertTrue(slice_cap.endswith("G"), slice_cap)
        self.assertGreaterEqual(int(slice_cap[:-1]), int(memory_cap_scope.MEMORY_MAX.removesuffix("G")))
        self.assertIn("MemorySwapMax=0", slice_lines)

    def test_caught(self):
        for name, command in CAUGHT.items():
            with self.subTest(name):
                self.assertTrue(memory_cap_scope.uncapped_test_run(command), command)

    def test_passed(self):
        for name, command in PASSED.items():
            with self.subTest(name):
                self.assertFalse(memory_cap_scope.uncapped_test_run(command), command)

    def test_a_path_program_that_only_names_a_runner_in_its_arguments_is_not_named_by_path(self):
        for words in (["./deploy.sh", "pytest"], ["tools/lint", "jest"]):
            with self.subTest(words=words):
                self.assertFalse(check_scope.path_program_runs_tests(words), str(words))


RUN_WITH_SCOPE = ("import sys, runpy; sys.path.insert(0, sys.argv[1]); import memory_cap_scope; "
                  "memory_cap_scope.cap_available = lambda: True; sys.argv = [sys.argv[2]]; "
                  "runpy.run_path(sys.argv[0], run_name='__main__')")


NOT_REWRITABLE = {
    "after_cd": "cd x && python3 -m unittest t.py",
    "piped": "python3 -m unittest t.py | tail -5",
    "redirected": "python3 -m unittest t.py > log",
    "assignment": "FOO=1 python3 -m unittest t.py",
    "substitution": "python3 -m unittest $(ls t*.py)",
    "backticks": "python3 -m unittest `ls t.py`",
    "subshell": "(python3 -m unittest t.py)",
    "heredoc": "python3 -m unittest t.py <<EOF\nx\nEOF",
    "two_lines": "echo a\npython3 -m unittest t.py",
    "semicolon": "echo a; pytest",
    "runner_first_then_and": "pytest -x && rm -rf build",
    "runner_first_then_semicolon": "pytest; echo done",
    "stray_close_paren": "pytest x )",
    "stray_close_brace": "pytest x }",
    "bare_ampersand": "pytest &",
    "brace_group": "{ pytest; }",
    "sudo": "sudo pytest",
    "doas": "doas pytest",
    "env_split_string": "env -S 'rm -rf /tmp/zz' pytest",
    "uv_run_with": "uv run --with evilpkg pytest",
    "nohup": "nohup pytest",
    "exec": "exec pytest",
    "time": "time pytest",
    "bang": "! pytest",
    "foreign_run_sh": "/tmp/evil/tests/run.sh",
    "foreign_run_sh_through_bash": "bash /tmp/evil/tests/run.sh",
    "run_sh_outside_the_repo_through_bash": "bash ~/dotfiles/tests/run.sh",
    "runner_word_in_arguments": "rm -rf scratch pytest",
    "chmod_with_runner_word": "chmod -R 777 . jest",
    "perl_with_runner_word": "perl x.pl pytest",
    "sh_c_with_runner_word": 'sh -c "rm -rf x" pytest',
    "ssh": "ssh host pytest",
    "xargs": "xargs -a list pytest",
    "docker_run": "docker run -v /h:/host img pytest",
    "docker_exec": "docker exec box pytest",
    "npm_exec_later_test_word": "npm exec evil test",
    "npm_run_later_test_word": "npm run evil test",
    "make_file_later_test_word": "make -f evil.mk test",
    "go_run_later_test_word": "go run x.go test",
    "deno_run_later_test_word": "deno run x.ts test",
    "runner_named_by_relative_path": "./pytest -x",
    "runner_named_by_venv_path": ".venv/bin/pytest tests",
    "runner_named_by_absolute_path": "/tmp/x/pytest -x",
    "shell_named_by_relative_path": "./sh tests/run.sh",
    "shell_named_by_absolute_path": "/tmp/evil/bash tests/run.sh",
    "runner_script_at_foreign_path": "python3 /tmp/evil/parallel_tests.py x",
    "npm_run_script_later_test_word": "npm run-script evil test",
}
# A usage flag runs no tests, so the hook neither rewrites it nor denies it.
NOT_REWRITABLE_NOT_DENIED = {
    "help_flag": "pytest --help",
    "short_help_flag": "pytest -h",
    "version_flag": "pytest --version",
}
# An inline interpreter run is never rewritten, and is denied with the inline-interpreter text instead.
INLINE_INTERPRETER_WITH_RUNNER_WORD = "python3 -c 'print(1)' pytest"
REWRITABLE = {
    "pytest": "pytest -x tests/",
    "unittest": "python3 -m unittest tests/scripts/test_x.py",
    "npm_test": "npm test",
    "npm_run_test": "npm run test:unit",
    "npm_run_script_test": "npm run-script test:unit",
    "own_runner_script": "python3 tests/parallel_tests.py x.py",
    "own_runner_script_dot_slash": "python3 ./tests/parallel_tests.py x.py",
    "run_sh": "bash tests/run.sh",
    "quoted_pipe": 'python3 -m unittest -k "a|b" t.py',
    "quoted_parentheses": "pytest -k 'a and (b or c)'",
    "python_module_pytest": "python3 -m pytest tests",
    "cargo_test": "cargo test",
    "make_test_subcommand": "make test-unit",
    "go_test_subcommand": "go test ./...",
    "run_sh_direct": "./tests/run.sh",
    "run_sh_through_sh": "sh tests/run.sh",
    "run_sh_through_zsh": "zsh tests/run.sh",
}


def run_hook_with_scope(payload, env=None):
    # Runs the hook as if this machine could run a scope, so the test does not depend on the machine.
    return subprocess.run([sys.executable, "-c", RUN_WITH_SCOPE, str(toolkit_paths.LIB_DIR), str(HOOK)],
                          input=json.dumps(payload), capture_output=True, text=True, timeout=30,
                          env=env or os.environ)


class RewritableTest(unittest.TestCase):
    def test_rewritable(self):
        for name, command in REWRITABLE.items():
            with self.subTest(name):
                self.assertTrue(memory_cap_scope.is_rewritable_test_run(command), command)

    def test_not_rewritable(self):
        for name, command in {**NOT_REWRITABLE, **NOT_REWRITABLE_NOT_DENIED}.items():
            with self.subTest(name):
                self.assertFalse(memory_cap_scope.is_rewritable_test_run(command), command)

    def test_an_inline_interpreter_run_is_not_rewritable(self):
        self.assertFalse(memory_cap_scope.is_rewritable_test_run(INLINE_INTERPRETER_WITH_RUNNER_WORD))

    def test_an_unbalanced_quote_is_not_rewritable(self):
        self.assertFalse(memory_cap_scope.is_rewritable_test_run('python3 -m unittest "t.py'))

    def test_capped_command_puts_the_prefix_first(self):
        self.assertEqual(memory_cap_scope.capped_command("pytest"), f"{memory_cap_scope.CAPPED_PREFIX} pytest")


class HookTest(unittest.TestCase):
    def test_denies_with_the_capped_form_where_a_scope_runs(self):
        payload = {"tool_name": "Bash", "tool_input": {"command": "cd x && pytest -x", "run_in_background": True}}
        result = run_hook_with_scope(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertEqual(decision["permissionDecisionReason"], memory_cap_scope.DENY_TEXT)
        self.assertIn("systemd-run --user --scope", decision["permissionDecisionReason"])
        self.assertIn("MemorySwapMax=0", decision["permissionDecisionReason"])
        self.assertIn(memory_cap_scope.CAPPED_PREFIX, decision["permissionDecisionReason"])
        self.assertIn("shared slice", decision["permissionDecisionReason"])

    def test_a_blocked_command_the_pilot_passes_is_never_rewritten(self):
        # Under auto mode the pilot lets a blocked inline run go on to the classifier; the rewrite sends no decision,
        # so it must not apply. The command is one plain step with a runner first, so only the blocked check stops it.
        command = "pytest python3 -c x"
        self.assertTrue(memory_cap_scope.is_rewritable_test_run(command))
        with tempfile.TemporaryDirectory() as home:
            os.makedirs(os.path.join(home, ".claude"))
            payload = {"tool_name": "Bash", "permission_mode": "auto",
                       "tool_input": {"command": command, "run_in_background": True}}
            result = run_hook_with_scope(payload, env={**os.environ, "HOME": home})
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertEqual(decision["permissionDecisionReason"], memory_cap_scope.DENY_TEXT)

    def test_a_background_full_suite_gets_the_prefix_added(self):
        for command in ("pytest", "bash tests/run.sh"):
            with self.subTest(command):
                result = run_hook_with_scope({"tool_name": "Bash",
                                              "tool_input": {"command": command, "run_in_background": True}})
                self.assertEqual(result.returncode, 0, result.stderr)
                decision = json.loads(result.stdout)["hookSpecificOutput"]
                self.assertNotIn("permissionDecision", decision)
                self.assertEqual(decision["updatedInput"]["command"], f"{memory_cap_scope.CAPPED_PREFIX} {command}")

    def test_a_plain_test_step_gets_the_prefix_added(self):
        command = "python3 -m unittest tests/scripts/test_x.py"
        tool_input = {"command": command, "run_in_background": False, "description": "run it", "timeout": 5000}
        result = run_hook_with_scope({"tool_name": "Bash", "tool_input": tool_input})
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", decision)
        self.assertEqual(decision["permissionDecisionReason"],
                         f"Added the memory cap `{memory_cap_scope.CAPPED_PREFIX}` in front of the test run.")
        self.assertEqual(decision["updatedInput"],
                         {**tool_input, "command": f"{memory_cap_scope.CAPPED_PREFIX} {command}"})

    def test_an_already_capped_command_gets_no_output(self):
        command = f"{memory_cap_scope.CAPPED_PREFIX} python3 -m unittest tests/scripts/test_x.py"
        result = run_hook_with_scope({"tool_name": "Bash", "tool_input": {"command": command}})
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_a_command_that_is_not_one_plain_step_is_still_denied(self):
        for name, command in NOT_REWRITABLE.items():
            with self.subTest(name):
                # In the background, so the foreground full-suite deny does not answer first.
                result = run_hook_with_scope({"tool_name": "Bash",
                                              "tool_input": {"command": command, "run_in_background": True}})
                self.assertEqual(result.returncode, 0, result.stderr)
                decision = json.loads(result.stdout)["hookSpecificOutput"]
                self.assertEqual(decision["permissionDecision"], "deny")
                self.assertEqual(decision["permissionDecisionReason"], memory_cap_scope.DENY_TEXT)

    def test_a_usage_run_is_not_rewritten(self):
        for name, command in NOT_REWRITABLE_NOT_DENIED.items():
            with self.subTest(name):
                result = run_hook_with_scope({"tool_name": "Bash",
                                              "tool_input": {"command": command, "run_in_background": True}})
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")

    def test_an_inline_interpreter_run_is_denied_with_the_inline_interpreter_text(self):
        payload = {"tool_name": "Bash",
                   "tool_input": {"command": INLINE_INTERPRETER_WITH_RUNNER_WORD, "run_in_background": True}}
        result = run_hook_with_scope(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("updatedInput", result.stdout)
        self.assertNotIn(memory_cap_scope.DENY_TEXT, result.stdout)
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertEqual(decision["permissionDecisionReason"], inline_interpreter_hint.deny_text(payload))

    def test_a_subagent_plain_foreground_run_gets_the_prefix_added(self):
        payload = {"tool_name": "Bash", "agent_id": "coder-1", "tool_input": {"command": "pytest tests/test_a.py"}}
        result = run_hook_with_scope(payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertNotIn("permissionDecision", decision)
        self.assertEqual(decision["updatedInput"]["command"],
                         f"{memory_cap_scope.CAPPED_PREFIX} pytest tests/test_a.py")

    def test_a_foreground_full_suite_is_denied_with_the_background_text(self):
        result = run_hook_with_scope(hook_input("python3 -m unittest discover"))
        decision = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        with unittest.mock.patch.object(memory_cap_scope, "cap_available", return_value=True):
            expected = memory_cap_scope.background_deny_text()
        self.assertEqual(decision["permissionDecisionReason"], expected)

    def test_a_machine_with_no_scope_passes_the_call(self):
        result = subprocess.run(["/usr/bin/env", "-i", "PATH=/nonexistent", sys.executable, str(HOOK)],
                                input=json.dumps({"tool_name": "Bash",
                                                  "tool_input": {"command": "pytest", "run_in_background": True}}),
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


CAPPED_SUITE = f"{memory_cap_scope.CAPPED_PREFIX} bash tests/run.sh"
FULL_SUITES = {
    "run_sh": CAPPED_SUITE,
    "run_sh_piped": f"{CAPPED_SUITE} 2>&1 | tail -20",
    "unittest_discover": f"{memory_cap_scope.CAPPED_PREFIX} python3 -m unittest discover -s bin -p 'test_*.py'",
    "bare_pytest": f"{memory_cap_scope.CAPPED_PREFIX} pytest",
    "npm_test": f"{memory_cap_scope.CAPPED_PREFIX} npm test",
    "run_sh_under_timeout": f"{memory_cap_scope.CAPPED_PREFIX} timeout 600 bash tests/run.sh",
    "run_sh_under_env": f"{memory_cap_scope.CAPPED_PREFIX} env FOO=1 bash tests/run.sh",
}
TARGETED_RUNS = {
    "unittest_module": f"{memory_cap_scope.CAPPED_PREFIX} python3 -m unittest test_x",
    "pytest_file": f"{memory_cap_scope.CAPPED_PREFIX} pytest tests/test_a.py",
    "pytest_node": f"{memory_cap_scope.CAPPED_PREFIX} pytest tests/test_a.py::test_one",
    "parallel_tests_file": f"{memory_cap_scope.CAPPED_PREFIX} python3 tests/parallel_tests.py test_a.py",
    "pytest_help": "pytest --help",
    "pytest_file_under_timeout": f"{memory_cap_scope.CAPPED_PREFIX} timeout 60 pytest tests/test_a.py",
}


def hook_input(command, background=None, **extra):
    tool_input = {"command": command}
    if background is not None:
        tool_input["run_in_background"] = background
    return {"tool_name": "Bash", "tool_input": tool_input, **extra}


def run_hook_payload(payload):
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True,
                          timeout=30)


class BackgroundDenyTextTest(unittest.TestCase):
    def test_text_names_the_cap_only_where_a_scope_runs(self):
        with unittest.mock.patch.object(memory_cap_scope, "cap_available", return_value=True):
            capped = memory_cap_scope.background_deny_text()
        with unittest.mock.patch.object(memory_cap_scope, "cap_available", return_value=False):
            uncapped = memory_cap_scope.background_deny_text()
        self.assertIn(memory_cap_scope.CAPPED_PREFIX, capped)
        self.assertIn("run_in_background", capped)
        self.assertIn("run_in_background", uncapped)
        self.assertNotIn("systemd-run", uncapped)
        self.assertIn("completion notice", uncapped)

    def test_the_hook_names_run_in_background_alone_on_a_host_with_no_scope(self):
        payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "bash tests/run.sh"}})
        result = subprocess.run(["/usr/bin/env", "-i", "PATH=/nonexistent", sys.executable, str(HOOK)], input=payload,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("run_in_background", reason)
        self.assertNotIn("systemd-run", reason)


class ForegroundFullSuiteTest(unittest.TestCase):
    def test_a_full_suite_in_the_foreground_is_denied_with_the_background_fix(self):
        for name, command in FULL_SUITES.items():
            for background in (None, False):
                with self.subTest(name, background=background):
                    result = run_hook_payload(hook_input(command, background))
                    self.assertEqual(result.returncode, 0, result.stderr)
                    decision = json.loads(result.stdout)["hookSpecificOutput"]
                    self.assertEqual(decision["permissionDecision"], "deny")
                    self.assertIn("run_in_background", decision["permissionDecisionReason"])
                    self.assertIn("completion notice", decision["permissionDecisionReason"])

    def test_a_full_suite_in_the_background_is_allowed(self):
        for name, command in FULL_SUITES.items():
            for background in (True, "true"):
                with self.subTest(name, background=background):
                    result = run_hook_payload(hook_input(command, background))
                    self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_a_targeted_run_in_the_foreground_is_allowed(self):
        for name, command in TARGETED_RUNS.items():
            with self.subTest(name):
                result = run_hook_payload(hook_input(command))
                self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_a_subagent_foreground_full_suite_is_allowed(self):
        result = run_hook_payload(hook_input(CAPPED_SUITE, None, agent_id="coder-1"))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_a_command_that_runs_no_tests_is_allowed(self):
        result = run_hook_payload(hook_input("cat tests/run.sh | head"))
        self.assertEqual((result.returncode, result.stdout), (0, ""))

    def test_a_malformed_payload_fails_open(self):
        for payload in ("not json", "[]", json.dumps({"tool_input": "bash tests/run.sh"}),
                        json.dumps({"tool_input": {"command": ["bash", "tests/run.sh"]}}),
                        json.dumps({"tool_input": {"command": CAPPED_SUITE, "run_in_background": "yes"},
                                    "agent_id": {"x": 1}})):
            with self.subTest(payload=payload):
                result = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True,
                                        timeout=30)
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


@unittest.skipUnless(systemd_scope_works(), "systemd-run --user --scope is not available on this machine")
class SliceUseTest(unittest.TestCase):
    def test_a_missing_slice_unit_still_runs_the_capped_prefix_in_that_slice(self):
        probe_slice = f"probe{uuid.uuid4().hex}.slice"
        self.addCleanup(subprocess.run, ["systemctl", "--user", "stop", probe_slice], capture_output=True,
                        timeout=30)
        prefix = memory_cap_scope.CAPPED_PREFIX.replace(f"--slice={memory_cap_scope.TEST_SLICE}",
                                                         f"--slice={probe_slice}")
        self.assertIn(probe_slice, prefix)
        result = subprocess.run(["bash", "-c", f"{prefix} cat /proc/self/cgroup"], capture_output=True, text=True,
                                timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(probe_slice, result.stdout)


class CappedUnitNameTest(unittest.TestCase):
    def test_each_capped_argv_names_a_unit_of_its_own(self):
        command = f"{memory_cap_scope.CAPPED_PREFIX} true"
        first = memory_cap_scope.capped_shell_argv("/usr/bin/systemd-run", command)
        second = memory_cap_scope.capped_shell_argv("/usr/bin/systemd-run", command)

        first_units = [word for word in first if word.startswith("--unit=")]
        second_units = [word for word in second if word.startswith("--unit=")]
        self.assertEqual(1, len(first_units))
        self.assertEqual(1, len(second_units))
        self.assertNotEqual(first_units, second_units)

        # The unit option is a systemd-run option: it sits before the shell, and the command text stays the last word.
        shell_position = first.index(memory_cap_scope.CAPPED_SHELL)
        self.assertLess(first.index(first_units[0]), shell_position)
        self.assertEqual([memory_cap_scope.CAPPED_SHELL, "-c", command], first[shell_position:])
        self.assertTrue(first_units[0].startswith(f"--unit={memory_cap_scope.CAPPED_UNIT_PREFIX}-"))


@unittest.skipUnless(systemd_scope_works(), "systemd-run --user --scope is not available on this machine")
class NestedCappedRunTest(unittest.TestCase):
    def test_a_command_that_starts_with_the_capped_prefix_runs_inside_the_capped_shell(self):
        # Both scopes run as one pid, since `--scope` and `sh -c` exec in place.
        command = f"{memory_cap_scope.CAPPED_PREFIX} echo nested-ran"
        args, shell = memory_cap_scope.shell_popen_args(command)

        result = subprocess.run(args, shell=shell, capture_output=True, text=True, timeout=60)

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("nested-ran", result.stdout)


if __name__ == "__main__":
    unittest.main()
