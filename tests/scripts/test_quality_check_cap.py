"""Checks for quality-check-cap.py: caps a quality check at one re-run per edit."""
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

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR")
                      or pathlib.Path.home() / ".claude" / "scripts") / "quality-check-cap.py"
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
        self.assertIn("#skip-quality-cap", reason)

    def test_run_state_file_is_named_by_cksum_of_command_and_cwd(self):
        module = self.load_module()
        self.post("pytest -q")
        key = module.cksum(b"pytest -q\n" + str(self.work).encode())
        self.assertEqual(self.state_files(), ["run-%d" % key])

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
        self.assert_allowed(self.pre("cd %s && pytest" % other))
        self.post("cd %s && pytest" % other)
        self.assert_denied(self.pre("pytest", cwd=other))
        self.assert_denied(self.pre("cd %s; pytest" % self.work))

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

    def test_timeout_and_interrupt_failures_record_nothing(self):
        self.fire("PostToolUseFailure", command="pytest", tool_error={"error_type": "timeout"})
        self.fire("PostToolUseFailure", command="pytest", tool_error={"error_type": "interrupted"})
        self.fire("PostToolUseFailure", command="pytest", error="Command timed out after 120s")
        self.assert_allowed(self.pre("pytest"))

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

    def test_deleted_tracked_file_does_not_allow(self):
        repo = self.make_repo()
        self.post("pytest", cwd=repo)
        time.sleep(0.05)
        (repo / "tracked.py").unlink()
        self.assert_denied(self.pre("pytest", cwd=repo))

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
