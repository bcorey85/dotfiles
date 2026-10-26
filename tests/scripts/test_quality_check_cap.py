"""Checks for quality_check_cap.py: caps a quality check at one re-run per edit."""
import importlib.util
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import toolkit_paths

HERE = pathlib.Path(__file__).resolve().parent
LIVE_SCRIPTS_DIR = toolkit_paths.GATES_DIR
SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "quality_check_cap.py").exists()
                                                             else LIVE_SCRIPTS_DIR)) / "quality_check_cap.py"
DENY_START = "[quality-check-cap] '"
TICK = 0.03


class QualityCheckCapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.work = self.tmp / "work"
        self.work.mkdir()
        self.state_root = self.home / ".claude" / "state" / "quality-check"

    def fire(self, event, tool="Bash", command=None, session="s1", cwd=None, env_extra=None, **extra):
        payload = {"hook_event_name": event, "tool_name": tool, "session_id": session,
                   "cwd": str(cwd or self.work), "tool_input": {}}
        if command is not None:
            payload["tool_input"]["command"] = command
        payload.update(extra)
        return self.fire_raw(json.dumps(payload), env_extra)

    def fire_raw(self, stdin, env_extra=None):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": str(self.tmp)}
        env.update(env_extra or {})
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                                  env=env, cwd=str(self.work))
        time.sleep(TICK)
        return finished

    def pre(self, command, **options):
        return self.fire("PreToolUse", command=command, **options)

    def post(self, command, **options):
        return self.fire("PostToolUse", command=command, **options)

    def edit(self, tool="Edit", **options):
        return self.fire("PostToolUse", tool=tool, **options)

    def assert_allowed(self, finished):
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def assert_denied(self, finished):
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stderr, "")
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        return decision["permissionDecisionReason"]

    def state_files(self, session="s1"):
        folder = self.state_root / session
        return sorted(p.name for p in folder.iterdir()) if folder.exists() else []

    def load_module(self):
        sys.path.insert(0, str(SCRIPT.parent))
        self.addCleanup(sys.path.remove, str(SCRIPT.parent))
        spec =importlib.util.spec_from_file_location("quality_check_cap", str(SCRIPT))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    # basics

    def test_cksum_matches_the_posix_cksum_command(self):
        module = self.load_module()
        self.assertEqual(module.cksum(b"123456789"), 930766865)
        sample = b"pytest\n/some/where"
        expected = subprocess.run(["cksum"], input=sample, capture_output=True).stdout.split()[0]
        self.assertEqual(str(module.cksum(sample)).encode(), expected)

    def test_first_run_allowed_then_repeat_denied(self):
        self.assert_allowed(self.pre("pytest -q"))
        self.assert_allowed(self.post("pytest -q"))
        reason = self.assert_denied(self.pre("pytest -q"))
        self.assertTrue(reason.startswith(DENY_START + "pytest -q' already ran this session and nothing has been "
                                          "edited since."), reason)
        self.assertNotIn("#skip-quality-cap", reason)

    def test_a_subagents_first_run_is_allowed_after_another_agents_run_on_the_same_tree(self):
        self.post("cargo test", agent_id="coder-1", agent_type="coder")
        self.assert_denied(self.pre("cargo test", agent_id="coder-1", agent_type="coder"))
        self.assert_allowed(self.pre("cargo test", agent_id="reviewer-1", agent_type="test-reviewer"))
        self.assert_allowed(self.pre("cargo test"))
        self.assert_allowed(self.pre("cargo test", agent_id="reviewer-2", agent_type="test-reviewer"))

    def test_a_repeat_is_capped_against_the_same_agents_earlier_run_only(self):
        self.post("cargo test", agent_id="coder-1")
        self.post("cargo test", agent_id="reviewer-1")
        self.assert_denied(self.pre("cargo test", agent_id="reviewer-1"))
        self.assert_denied(self.pre("cargo test", agent_id="coder-1"))
        self.assert_allowed(self.pre("cargo test"))
        self.post("cargo test")
        self.assert_denied(self.pre("cargo test"))
        self.assert_allowed(self.pre("cargo test", agent_id="reviewer-2"))

    def test_the_main_thread_runs_a_check_a_subagent_already_ran(self):
        self.post("pytest -q", agent_id="coder-1")
        self.assert_allowed(self.pre("pytest -q"))
        self.post("pytest -q")
        self.assert_denied(self.pre("pytest -q"))
        self.assert_denied(self.pre("pytest -q", agent_id="coder-1"))

    def test_an_edit_by_any_agent_resets_the_cap_for_every_agent(self):
        self.post("cargo test", agent_id="coder-1")
        self.post("cargo test", agent_id="reviewer-1")
        self.assert_allowed(self.edit(agent_id="coder-2"))
        self.assert_allowed(self.pre("cargo test", agent_id="coder-1"))
        self.assert_allowed(self.pre("cargo test", agent_id="reviewer-1"))

    def test_an_agent_id_cannot_name_a_path_outside_the_session_state(self):
        self.post("cargo test", agent_id="../../escape/x y")
        self.assert_denied(self.pre("cargo test", agent_id="../../escape/x y"))
        self.assertFalse((self.state_root.parent / "escape").exists())
        files = self.state_files()
        self.assertEqual(len(files), 1)
        self.assertRegex(files[0], r"^run-\d+-[0-9a-f]{16}$")

    def test_agent_ids_that_differ_only_in_characters_unsafe_for_a_file_name_are_separate_agents(self):
        self.post("cargo test", agent_id="coder/1")
        self.assert_allowed(self.pre("cargo test", agent_id="coder_1"))
        self.assert_denied(self.pre("cargo test", agent_id="coder/1"))

    def test_edit_after_a_passing_cargo_test_allows_it_again(self):
        for agent in ({}, {"agent_id": "sub-1", "agent_type": "coder"}):
            self.post("cargo test")
            self.assert_denied(self.pre("cargo test"))
            self.assert_allowed(self.edit(**agent))
            self.assert_allowed(self.pre("cargo test"))

    def test_run_state_file_is_named_by_cksum_of_command_and_cwd(self):
        module = self.load_module()
        self.post("pytest -q")
        key = module.cksum(b"pytest -q\n" + str(self.work).encode())
        self.assertEqual(self.state_files(), [f"run-{key}"])

    def test_edit_tools_reset_the_cap(self):
        for tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
            self.post("pytest")
            self.assert_denied(self.pre("pytest"))
            self.assert_allowed(self.edit(tool=tool))
            self.assertIn("edits", self.state_files())
            self.assert_allowed(self.pre("pytest"))

    def test_run_after_edit_is_capped_again(self):
        self.edit()
        self.assert_allowed(self.pre("npm test"))
        self.post("npm test")
        self.assert_denied(self.pre("npm test"))

    def test_edit_newer_than_run_allows(self):
        self.post("ruff check .")
        self.edit()
        self.assert_allowed(self.pre("ruff check ."))

    def test_unrelated_tools_and_commands_pass_and_record_nothing(self):
        self.assert_allowed(self.fire("PreToolUse", tool="Read"))
        self.assert_allowed(self.pre("ls -la"))
        self.assert_allowed(self.post("ls -la"))
        self.assert_allowed(self.pre(""))
        self.assertEqual(self.state_files(), [])

    def test_check_names_are_recognised(self):
        for command in ("npm run lint", "pnpm test", "yarn typecheck", "bun run build", "jest", "vitest run",
                        "tsc --noEmit", "eslint .", "mypy src", "go test ./...", "go vet", "golangci-lint run",
                        "cargo clippy", "make check", "bundle exec rspec", "rspec", "phpunit", "dotnet test",
                        "mvn test", "gradle test", "shellcheck a.sh", "luacheck .", "stylua ."):
            self.post(command)
            self.assert_denied(self.pre(command))
        for command in ("npm install", "echo pytest", "go build", "make all", "pytestx"):
            self.post(command)
            self.assert_allowed(self.pre(command))

    # normalising the command

    def test_wrappers_redirects_and_spacing_do_not_change_the_key(self):
        self.post("pytest   tests/a.py")
        for command in ("time pytest tests/a.py", "env FOO=1 pytest tests/a.py", "npx pytest tests/a.py",
                        "FOO=1 BAR=2 pytest tests/a.py", "pytest tests/a.py > /tmp/check.log 2>&1",
                        "pytest tests/a.py 2>&1", "pytest tests/a.py | tail -5", "pytest tests/a.py;"):
            self.assert_denied(self.pre(command))
        self.assert_allowed(self.pre("pytest tests/b.py"))

    def test_keyed_by_cwd_and_cd_prefix(self):
        other = self.tmp / "other"
        other.mkdir()
        self.post("pytest")
        self.assert_allowed(self.pre("pytest", cwd=other))
        self.assert_allowed(self.pre(f"cd {other} && pytest"))
        self.post(f"cd {other} && pytest")
        self.assert_denied(self.pre("pytest", cwd=other))
        self.assert_denied(self.pre(f"cd {self.work}; pytest"))

    def test_tilde_cd_uses_home(self):
        (self.home / "proj").mkdir()
        self.post("cd ~/proj && pytest")
        self.assert_denied(self.pre("pytest", cwd=self.home / "proj"))

    def test_every_segment_of_a_chain_is_checked(self):
        self.post("pytest a.py && eslint .")
        self.assert_denied(self.pre("eslint . || true"))
        self.assert_denied(self.pre("ls; pytest a.py"))

    def test_skip_comment_allows_pre_and_is_stripped_for_post(self):
        self.post("pytest")
        self.assert_allowed(self.pre("pytest #skip-quality-cap"))
        self.post("mypy . #skip-quality-cap")
        self.assert_denied(self.pre("mypy ."))

    def test_session_state_is_separate(self):
        self.post("pytest", session="a")
        self.assert_denied(self.pre("pytest", session="a"))
        self.assert_allowed(self.pre("pytest", session="b"))

    def test_missing_session_uses_unknown(self):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Edit", "tool_input": {}, "cwd": str(self.work)}
        self.assert_allowed(self.fire_raw(json.dumps(payload)))
        self.assertEqual(self.state_files("unknown"), ["edits"])

    # failures

    def test_failed_check_counts_as_a_run(self):
        self.fire("PostToolUseFailure", command="pytest", error="Exit code 1\nFAILED")
        self.assert_denied(self.pre("pytest"))

    def test_a_timeout_records_nothing(self):
        self.fire("PostToolUseFailure", command="pytest", error="Exit code 143\n\nCommand timed out after 2m 0s",
                  is_interrupt=False, tool_use_id="toolu_01", duration_ms=120000)
        self.assertEqual(self.state_files(), [])
        self.assert_allowed(self.pre("pytest"))

    def test_a_failure_whose_output_quotes_the_timeout_text_is_still_recorded(self):
        self.fire("PostToolUseFailure", command="pytest", is_interrupt=False, tool_use_id="toolu_01", duration_ms=900,
                  error="Exit code 1\nFAILED test_runner.py::test_timeout - AssertionError: "
                        "'Command timed out after 5s'")
        self.assert_denied(self.pre("pytest"))

    def test_an_interrupted_run_records_nothing(self):
        payload = {"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "session_id": "s1",
                   "cwd": str(self.work), "tool_input": {"command": "pytest"}, "is_interrupt": True,
                   "error": "Exit code 1\n[Request interrupted by user for tool use]"}
        self.fire_raw(json.dumps(payload))
        self.assertEqual(self.state_files(), [])
        self.assert_allowed(self.pre("pytest"))

    def test_the_same_failure_without_the_interrupt_flag_is_recorded(self):
        self.fire("PostToolUseFailure", command="pytest", is_interrupt=False,
                  error="Exit code 1\n[Request interrupted by user for tool use]")
        self.assert_denied(self.pre("pytest"))

    def test_a_run_ended_by_a_signal_is_not_recorded_and_the_rerun_is_allowed(self):
        for code in (129, 137, 144, 192):
            self.fire("PostToolUseFailure", command="pytest", error=f"Exit code {code}\nTerminated")
            self.assertEqual(self.state_files(), [])
            self.assert_allowed(self.pre("pytest"))

    def test_a_signal_exit_leaves_an_earlier_record_of_another_check_alone(self):
        self.fire("PostToolUseFailure", command="pytest", error="Exit code 1")
        self.assert_denied(self.pre("pytest"))
        self.fire("PostToolUseFailure", command="eslint .", error="Exit code 144")
        self.assert_allowed(self.pre("eslint ."))
        self.assert_denied(self.pre("pytest"))

    def test_a_plain_nonzero_exit_is_still_recorded(self):
        for code in (1, 2, 127, 128, 193, 255):
            self.fire("PostToolUseFailure", command="pytest", error=f"Exit code {code}\nFAILED")
            self.assert_denied(self.pre("pytest"))
            self.assert_allowed(self.edit())

    def test_exit_code_in_error_text_reads_only_a_leading_exit_code_line(self):
        module = self.load_module()
        self.assertEqual(module.exit_code_in_error_text("Exit code 144\nTerminated"), 144)
        self.assertEqual(module.exit_code_in_error_text("Exit code 1"), 1)
        self.assertIsNone(module.exit_code_in_error_text("FAILED\nExit code 144"))
        self.assertIsNone(module.exit_code_in_error_text("Command timed out after 120s"))
        self.assertIsNone(module.exit_code_in_error_text(""))

    def test_exit_code_text_after_the_first_line_does_not_count_as_the_exit_status(self):
        self.fire("PostToolUseFailure", command="pytest", error="FAILED\nworker ended: Exit code 144")
        self.assert_denied(self.pre("pytest"))

    # only a check that ran is counted

    GATE = ("cargo fmt && (cargo fmt --check && cargo clippy --all-targets -- -D warnings && "
            "cargo test --all-targets --no-fail-fast && python3 -m unittest x) > log")

    def test_check_behind_a_failed_and_chain_is_not_counted(self):
        self.fire("PostToolUseFailure", command=self.GATE, error="Exit code 1")
        self.assert_allowed(self.pre("cargo clippy --all-targets -- -D warnings"))
        self.assert_allowed(self.pre("cargo test --all-targets --no-fail-fast"))

    def test_first_check_of_a_failed_chain_is_counted(self):
        self.fire("PostToolUseFailure", command="pytest -q && eslint .", error="Exit code 1")
        self.assert_denied(self.pre("pytest -q"))
        self.assert_allowed(self.pre("eslint ."))

    def test_failed_check_after_cd_or_source_or_assignment_is_counted(self):
        for command in (f"cd {self.work} && pytest -q", "source .venv/bin/activate && pytest -q",
                        ". .venv/bin/activate && pytest -q", "FOO=1 && pytest -q",
                        f"cd {self.work} && source .venv/bin/activate && pytest -q"):
            self.fire("PostToolUseFailure", command=command, error="Exit code 1")
            self.assert_denied(self.pre(command))
            self.assert_allowed(self.edit())

    def test_failed_check_behind_a_real_command_is_still_not_counted(self):
        self.fire("PostToolUseFailure", command="cd /x && make build && pytest -q", error="Exit code 1")
        self.assert_allowed(self.pre("pytest -q"))

    def test_formatter_after_a_check_does_not_exempt_the_check(self):
        self.post("npm test; prettier --write x")
        self.assert_denied(self.pre("npm test; prettier --write x"))
        self.assert_denied(self.pre("npm test"))
        self.assert_allowed(self.pre("prettier --write x && npm test"))

    def test_formatter_not_joined_to_the_check_by_and_does_not_exempt_it(self):
        self.post("npm test")
        for command in ("prettier --write x; npm test", "prettier --write x\nnpm test",
                        "prettier --write x || npm test", "prettier --write x && echo done; npm test",
                        "cargo fmt && cargo clippy; npm test"):
            self.assert_denied(self.pre(command))

    def test_a_pipe_inside_an_and_chain_keeps_the_checks_behind_the_formatter(self):
        self.post("cargo clippy && cargo test")
        self.assert_allowed(self.pre("cargo fmt && cargo clippy 2>&1 | tail -50 && cargo test 2>&1 | tail -50"))
        self.assert_denied(self.pre("cargo fmt | cat && cargo clippy"))
        self.assert_denied(self.pre("cargo fmt && cargo clippy | tail -5; cargo test"))
        self.post("npm test")
        self.assert_denied(self.pre("prettier --write x | cat && npm test"))
        self.assert_denied(self.pre("prettier --write x | npm test"))

    def test_any_formatter_before_the_check_exempts_it(self):
        self.post("npm test")
        self.assert_allowed(self.pre("cargo fmt; prettier --write . && npm test"))
        self.assert_allowed(self.pre("prettier --write . && cargo fmt; prettier --write . && npm test"))
        self.assert_denied(self.pre("cargo fmt && prettier --write .; npm test"))

    def test_a_group_entered_through_and_keeps_its_checks_behind_the_formatter(self):
        self.post("cargo clippy && cargo test")
        self.assert_allowed(self.pre("cargo fmt && { cargo clippy; cargo test; }"))
        self.assert_allowed(self.pre("cargo fmt && (cargo clippy; cargo test)"))
        self.assert_denied(self.pre("cargo fmt && { cargo clippy; }; cargo test"))
        self.assert_denied(self.pre("cargo fmt; { cargo clippy; cargo test; }"))

    def test_a_formatter_that_an_or_can_skip_does_not_exempt_the_check(self):
        self.post("npm test")
        self.assert_denied(self.pre("true || prettier --write . && npm test"))
        self.assert_denied(self.pre("make build && echo x || prettier --write . && npm test"))
        self.assert_allowed(self.pre("true || echo x; prettier --write . && npm test"))
        self.assert_allowed(self.pre("true || echo x\nprettier --write . && npm test"))

    def test_a_lone_ampersand_does_not_join_the_formatter_to_the_check(self):
        self.post("npm test")
        self.assert_denied(self.pre("prettier --write x & npm test"))
        self.assert_denied(self.pre("prettier --write x && echo x & npm test"))

    def test_a_check_sent_to_the_background_is_not_recorded(self):
        self.post("npm test &")
        self.assert_allowed(self.pre("npm test"))
        self.post("pytest -q && eslint . &")
        self.assert_allowed(self.pre("pytest -q"))
        self.post("pytest -q & eslint .")
        self.assert_allowed(self.pre("pytest -q"))
        self.assert_denied(self.pre("eslint ."))

    def test_stderr_redirects_and_pipe_stderr_are_not_a_lone_ampersand(self):
        self.post("pytest -q 2>&1 | tail -5")
        self.assert_denied(self.pre("pytest -q"))
        for command in ("eslint . &> /tmp/c.log", "mypy src |& tail -5"):
            self.post(command)
            self.assert_denied(self.pre(command))

    def test_checks_of_a_passing_and_chain_are_all_counted(self):
        self.post("pytest -q && eslint . && mypy src")
        for command in ("pytest -q", "eslint .", "mypy src"):
            self.assert_denied(self.pre(command))

    def test_passing_gate_in_a_subshell_counts_its_checks_with_clean_keys(self):
        self.post(self.GATE)
        reason = self.assert_denied(self.pre("cargo clippy --all-targets -- -D warnings"))
        self.assertTrue(reason.startswith(DENY_START + "cargo clippy --all-targets -- -D warnings' already ran"))
        self.assert_denied(self.pre("cargo test --all-targets --no-fail-fast"))

    def test_check_behind_or_is_not_counted_after_success(self):
        self.post("pytest -q || eslint .")
        self.assert_denied(self.pre("pytest -q"))
        self.assert_allowed(self.pre("eslint ."))

    def test_checks_joined_by_semicolon_and_pipe_are_counted_after_failure(self):
        self.fire("PostToolUseFailure", command="pytest -q; eslint . | tail -3", error="Exit code 1")
        self.assert_denied(self.pre("pytest -q"))
        self.assert_denied(self.pre("eslint ."))

    # changes made by git itself

    def git(self, repo, *args):
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], check=True,
                       capture_output=True)

    def make_committed_repo(self):
        repo = self.make_repo()
        self.git(repo, "commit", "-q", "-m", "first")
        return repo

    def test_commit_made_by_git_between_runs_allows_a_rerun(self):
        repo = self.make_committed_repo()
        self.post("cargo test", cwd=repo)
        self.assert_denied(self.pre("cargo test", cwd=repo))
        time.sleep(0.05)
        (repo / "tracked.py").write_text("merged\n")
        self.git(repo, "commit", "-q", "-am", "merge-like change")
        self.assert_allowed(self.pre("cargo test", cwd=repo))

    def test_branch_switch_between_runs_allows_a_rerun(self):
        repo = self.make_committed_repo()
        self.git(repo, "checkout", "-q", "-b", "other")
        (repo / "tracked.py").write_text("other\n")
        self.git(repo, "commit", "-q", "-am", "other")
        self.git(repo, "checkout", "-q", "-")
        self.post("cargo test", cwd=repo)
        time.sleep(0.05)
        self.git(repo, "merge", "-q", "--no-ff", "-m", "merge", "other")
        self.assert_allowed(self.pre("cargo test", cwd=repo))

    def test_same_tree_in_a_committed_repo_is_still_a_repeat(self):
        repo = self.make_committed_repo()
        (repo / "tracked.py").write_text("dirty\n")
        (repo / "new.py").write_text("n\n")
        self.post("cargo test", cwd=repo)
        self.assert_denied(self.pre("cargo test", cwd=repo))
        self.assert_denied(self.pre("cargo test", cwd=repo))

    def test_git_failure_after_a_recorded_fingerprint_allows(self):
        repo = self.make_committed_repo()
        self.post("cargo test", cwd=repo)
        self.assert_denied(self.pre("cargo test", cwd=repo))
        shutil.rmtree(repo / ".git")
        self.assert_allowed(self.pre("cargo test", cwd=repo))

    def test_edit_by_a_subagent_of_the_same_session_resets_the_cap(self):
        self.post("cargo clippy")
        self.assert_denied(self.pre("cargo clippy"))
        self.assert_allowed(self.edit(agent_id="sub-1", agent_type="coder"))
        self.assert_allowed(self.pre("cargo clippy"))

    def test_subagent_shell_edits_after_the_run_allow_a_rerun(self):
        repo = self.make_repo()
        self.post("cargo clippy", cwd=repo)
        time.sleep(0.05)
        for name in ("a.rs", "b.rs"):
            (repo / name).write_text("x\n")
        self.assert_allowed(self.pre("cargo clippy", cwd=repo))

    # scoped cargo test

    def test_a_cargo_test_scoped_to_a_named_target_is_never_a_repeat(self):
        for command in ("cargo test --lib", "cargo test --doc", "cargo test --test api", "cargo test --test=api",
                        "cargo test --bin tool", "cargo test parses_header", "cargo test -p core --lib",
                        "cargo test --lib -- --nocapture", "cargo fmt --check && cargo test --lib"):
            self.post(command)
            self.assert_allowed(self.pre(command))

    def test_an_unscoped_cargo_test_is_still_a_repeat(self):
        for command in ("cargo test", "cargo test --workspace", "cargo test --workspace --lib", "cargo test -p core",
                        "cargo test --all-targets", "cargo test -- --nocapture"):
            self.post(command)
            self.assert_denied(self.pre(command))

    def test_a_format_check_alone_is_never_a_repeat(self):
        self.post("cargo fmt --check")
        self.assert_allowed(self.pre("cargo fmt --check"))

    # formatters that write

    def test_command_with_a_writing_formatter_is_never_a_repeat(self):
        self.post("cargo clippy && cargo test")
        for command in ("cargo fmt && cargo clippy", "prettier --write . && eslint . && cargo test",
                        "ruff format . && cargo test", "cargo fmt && cargo clippy && cargo test"):
            self.assert_allowed(self.pre(command))

    def test_read_only_formatter_run_is_still_a_repeat(self):
        self.post("cargo clippy")
        self.assert_denied(self.pre("cargo fmt --check && cargo clippy"))
        self.assert_denied(self.pre("prettier --check . && cargo clippy"))
        self.assert_denied(self.pre("ruff format --check . && cargo clippy"))

    def test_formatter_run_resets_the_cap_for_other_checks_but_not_its_own_checks(self):
        self.post("pytest")
        self.post("cargo fmt && cargo clippy")
        self.assert_allowed(self.pre("pytest"))
        self.assert_denied(self.pre("cargo clippy"))

    def test_full_gate_after_formatter_and_failed_run_is_allowed(self):
        self.post("cargo clippy --all-targets -- -D warnings")
        self.fire("PostToolUseFailure", command=self.GATE, error="Exit code 1")
        self.assert_allowed(self.pre(self.GATE))

    # changes the Write/Edit hook never saw

    def make_repo(self):
        repo = self.tmp / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        (repo / "tracked.py").write_text("a\n")
        subprocess.run(["git", "-C", str(repo), "add", "tracked.py"], check=True)
        return repo

    def test_shell_modified_file_since_run_allows_rerun(self):
        repo = self.make_repo()
        self.post("pytest", cwd=repo)
        self.assert_denied(self.pre("pytest", cwd=repo))
        time.sleep(0.05)
        (repo / "tracked.py").write_text("b\n")
        self.assert_allowed(self.pre("pytest", cwd=repo))

    def test_new_untracked_file_since_run_allows_rerun(self):
        repo = self.make_repo()
        self.post("pytest", cwd=repo)
        time.sleep(0.05)
        (repo / "fresh.py").write_text("b\n")
        self.assert_allowed(self.pre("pytest", cwd=repo))

    def test_file_changed_before_run_still_denies(self):
        repo = self.make_repo()
        (repo / "tracked.py").write_text("b\n")
        time.sleep(0.05)
        self.post("pytest", cwd=repo)
        self.assert_denied(self.pre("pytest", cwd=repo))

    def test_deleted_tracked_file_changes_the_tree_and_allows(self):
        repo = self.make_repo()
        self.post("pytest", cwd=repo)
        time.sleep(0.05)
        (repo / "tracked.py").unlink()
        self.assert_allowed(self.pre("pytest", cwd=repo))

    # environment and robustness

    def test_skip_hooks_env_does_nothing_at_all(self):
        self.assert_allowed(self.fire("PostToolUse", command="pytest", env_extra={"CLAUDE_SKIP_HOOKS": "1"}))
        self.assertFalse(self.state_root.exists())

    def test_unparseable_input_exits_zero_silently(self):
        for stdin in ("not json", "[1]", "{"):
            self.assert_allowed(self.fire_raw(stdin))

    def test_empty_input_is_silent(self):
        self.assert_allowed(self.fire_raw(""))

    def test_old_state_is_pruned_and_fresh_state_kept(self):
        old = self.state_root / "old-session"
        old.mkdir(parents=True)
        (old / "run-1").write_text("")
        stale = time.time() - 5 * 86400
        os.utime(str(old / "run-1"), (stale, stale))
        os.utime(str(old), (stale, stale))
        recent = self.state_root / "recent"
        recent.mkdir()
        (recent / "run-2").write_text("")
        self.edit()
        self.assertFalse(old.exists())
        self.assertTrue((recent / "run-2").exists())

    def test_state_dir_creation_failure_fails_open(self):
        (self.home / ".claude").write_text("a file, not a directory")
        self.assert_allowed(self.pre("pytest"))

    def test_internal_error_fails_closed_only_on_pre_bash(self):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "session_id": "s1", "tool_input": "oops"}
        reason = self.assert_denied(self.fire_raw(json.dumps(payload)))
        self.assertEqual(reason, "[quality-check-cap] internal error (exit 5) — failing closed. "
                                 "Report this to the user.")
        payload["hook_event_name"] = "PostToolUse"
        finished = self.fire_raw(json.dumps(payload))
        self.assertEqual((finished.returncode, finished.stdout), (5, ""))


if __name__ == "__main__":
    unittest.main()
