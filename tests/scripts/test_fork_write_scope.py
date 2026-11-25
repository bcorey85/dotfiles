"""Checks for fork_write_scope.py: code-fork may Write its run folder files, and nothing else."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

HOOK = pathlib.Path(os.environ.get("FORK_WRITE_SCOPE") or toolkit_paths.GATES_DIR / "fork_write_scope.py")
SETTINGS = toolkit_paths.CLAUDE_DIR / "settings.json"
FORK_AGENT = toolkit_paths.CLAUDE_DIR / "agents" / "code-fork.md"


def run_hook(file_path, agent_type="code-fork"):
    payload = {"tool_name": "Write", "tool_input": {"file_path": file_path, "content": "python3 - <<'EOF'\n"}}
    if agent_type:
        payload["agent_type"] = agent_type
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True,
                            capture_output=True, env=env, check=False)
    return result


def decision(result):
    if not result.stdout.strip():
        return "allow"
    return json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"]


class ForkWriteScopeTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name) / "repo"
        git_dir = self.repo / ".git"
        (git_dir / "code-phase").mkdir(parents=True)
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        worktree_git_dir = git_dir / "worktrees" / "lane"
        (worktree_git_dir / "code-phase").mkdir(parents=True)
        (worktree_git_dir / "HEAD").write_text("ref: refs/heads/lane\n")
        self.worktree_run_folder = worktree_git_dir / "code-phase"

    def test_fork_writes_stop_md_in_the_run_folder(self):
        result = run_hook(str(self.repo / ".git" / "code-phase" / "stop.md"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(decision(result), "allow")

    def test_fork_writes_in_a_linked_worktree_run_folder(self):
        result = run_hook(str(self.worktree_run_folder / "review-stop.md"))
        self.assertEqual(decision(result), "allow")

    def test_fork_write_to_a_repo_file_is_denied(self):
        result = run_hook(str(self.repo / "src" / "app.py"))
        self.assertEqual(decision(result), "deny")
        self.assertIn("coder", result.stdout)
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertTrue(reason.startswith("fork-write-scope: "), reason)

    def test_a_review_fix_path_is_denied_and_the_reason_names_the_also_fix_route(self):
        git_dir = self.repo / ".git"
        result = run_hook(str(git_dir / "review-fix" / "ask-findings.md"))
        self.assertEqual(decision(result), "deny")
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        findings_file = git_dir.resolve() / "code-phase" / "fix-findings.md"
        self.assertIn(f"--also-fix {findings_file}", reason)
        self.assertIn("stays closed", reason)
        self.assertTrue(reason.startswith("fork-write-scope: "), reason)

    def test_a_review_fix_folder_outside_a_git_dir_is_denied_without_the_also_fix_route(self):
        result = run_hook(str(self.repo / "review-fix" / "x.md"))
        self.assertEqual(decision(result), "deny")
        self.assertNotIn("--also-fix", result.stdout)

    def test_a_repo_file_denial_does_not_name_the_also_fix_route(self):
        result = run_hook(str(self.repo / "src" / "app.py"))
        self.assertNotIn("--also-fix", result.stdout)

    def test_code_phase_folder_outside_a_git_dir_is_denied(self):
        result = run_hook(str(self.repo / "code-phase" / "stop.md"))
        self.assertEqual(decision(result), "deny")

    def test_path_climbing_out_of_the_run_folder_is_denied(self):
        result = run_hook(str(self.repo / ".git" / "code-phase" / ".." / ".." / "app.py"))
        self.assertEqual(decision(result), "deny")

    def test_other_agents_and_the_main_session_pass(self):
        for agent_type in ("coder", None):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(decision(run_hook(str(self.repo / "app.py"), agent_type)), "allow")


class PendingLaunchTest(unittest.TestCase):
    LAUNCH_LINE = "python3 ~/.claude/scripts/review/review_fix.py launch --fix /g/review-fix/ask-findings.md --detach"

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        git_dir = pathlib.Path(temp_dir.name) / "repo" / ".git"
        (git_dir / "code-phase").mkdir(parents=True)
        (git_dir / "review-fix").mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
        self.stop_file = str(git_dir / "code-phase" / "review-stop.md")
        self.state_file = git_dir / "review-fix" / "state.json"

    def test_review_stop_is_denied_while_a_fix_run_is_pending_and_the_reason_names_the_line(self):
        self.state_file.write_text(json.dumps({"asks_launch_pending": self.LAUNCH_LINE}))
        result = run_hook(self.stop_file)
        self.assertEqual(decision(result), "deny")
        reason = json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertTrue(reason.startswith("fork-write-scope: "), reason)
        self.assertIn(self.LAUNCH_LINE, reason)
        self.assertIn("review-stop.md cannot be written yet", reason)
        self.assertIn("stop and tell the user", reason)
        self.assertIn("`asks_launch_pending` key", reason)
        self.assertIn(str(self.state_file.resolve()), reason)
        self.assertNotIn("launch a new review", reason)

    def test_review_stop_in_a_linked_worktree_is_denied_while_a_fix_run_is_pending(self):
        worktree_git_dir = self.state_file.parent.parent / "worktrees" / "x"
        (worktree_git_dir / "code-phase").mkdir(parents=True)
        (worktree_git_dir / "review-fix").mkdir()
        (worktree_git_dir / "HEAD").write_text("ref: refs/heads/x\n")
        (worktree_git_dir / "review-fix" / "state.json").write_text(
            json.dumps({"asks_launch_pending": self.LAUNCH_LINE}))
        result = run_hook(str(worktree_git_dir / "code-phase" / "review-stop.md"))
        self.assertEqual(decision(result), "deny")
        self.assertIn(self.LAUNCH_LINE, result.stdout)

    def test_review_stop_is_allowed_without_a_pending_fix_run(self):
        cases = {"no state file": None, "no flag": {"stage": "done"}, "empty flag": {"asks_launch_pending": ""}}
        for label, state in cases.items():
            with self.subTest(label):
                self.state_file.unlink(missing_ok=True)
                if state is not None:
                    self.state_file.write_text(json.dumps(state))
                self.assertEqual(decision(run_hook(self.stop_file)), "allow", label)

    def test_another_run_folder_file_is_allowed_while_a_fix_run_is_pending(self):
        self.state_file.write_text(json.dumps({"asks_launch_pending": self.LAUNCH_LINE}))
        for file_name in ("stop.md", "notes.md"):
            with self.subTest(file_name):
                other_file = str(pathlib.Path(self.stop_file).parent / file_name)
                self.assertEqual(decision(run_hook(other_file)), "allow")

    def test_a_non_code_fork_write_is_allowed_while_a_fix_run_is_pending(self):
        self.state_file.write_text(json.dumps({"asks_launch_pending": self.LAUNCH_LINE}))
        for agent_type in ("coder", None):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(decision(run_hook(self.stop_file, agent_type)), "allow")

    def test_an_unreadable_state_denies_review_stop_and_names_the_gate(self):
        self.state_file.write_text("{not json")
        result = run_hook(self.stop_file)
        self.assertEqual(decision(result), "deny")
        self.assertIn("fork-write-scope", result.stdout)
        self.assertIn(str(self.state_file.resolve()), result.stdout)
        self.assertIn("Tell the user to repair or delete that file", result.stdout)

    def test_a_state_that_is_not_an_object_denies_review_stop_and_names_the_file(self):
        self.state_file.write_text("[1]")
        result = run_hook(self.stop_file)
        self.assertEqual(decision(result), "deny")
        self.assertIn(str(self.state_file.resolve()), result.stdout)


class CrashInScopeCheckTest(unittest.TestCase):
    def test_a_crash_in_the_scope_check_exits_2_and_names_the_gate(self):
        with tempfile.TemporaryDirectory() as temp_name:
            scripts = pathlib.Path(temp_name) / "scripts"
            shutil.copytree(toolkit_paths.SCRIPTS_DIR, scripts, ignore=shutil.ignore_patterns("__pycache__"))
            (scripts / "lib" / "stop_file_names.py").write_text('x = "unterminated\n')
            payload = {"tool_name": "Write", "agent_type": "code-fork",
                       "tool_input": {"file_path": "/tmp/outside.txt", "content": "x"}}
            env = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}

            result = subprocess.run([sys.executable, str(scripts / "gates" / "fork_write_scope.py")],
                                    input=json.dumps(payload), text=True, capture_output=True, env=env, check=False)

        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("[fork-write-scope] crashed while judging the call", result.stderr)
        self.assertNotIn("every Bash call is blocked", result.stderr)

    def test_unreadable_hook_input_passes_and_names_the_gate(self):
        env = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}

        result = subprocess.run([sys.executable, str(HOOK)], input="not json", text=True,
                                capture_output=True, env=env, check=False)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("fork-write-scope: could not read the hook input", result.stderr)


STOP_EVENT = pathlib.Path(__file__).parent / "fixtures" / "hook_event_code_fork_write_stop.json"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


class ResumeReviewTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name).resolve() / "repo"
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        (self.repo / "app.py").write_text("x = 1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        self.run_folder = self.repo / ".git" / "code-phase"
        self.run_folder.mkdir()
        sys.path.insert(0, str(toolkit_paths.CODE_DIR))
        self.addCleanup(sys.path.remove, str(toolkit_paths.CODE_DIR))
        import resume_review_gate
        resume_review_gate.record_resume(self.run_folder, self.repo)

    def write_stop(self, agent_type="code-fork"):
        text = STOP_EVENT.read_text().replace("{RUN_FOLDER}", str(self.run_folder))
        payload = json.loads(text)
        if agent_type is None:
            del payload["agent_type"]
        else:
            payload["agent_type"] = agent_type
        env = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
        return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True,
                              capture_output=True, env=env, check=False)

    def edit_source(self):
        (self.repo / "app.py").write_text("x = 2\n")

    def test_a_source_edit_with_no_review_loop_is_denied_naming_the_file(self):
        self.edit_source()

        result = self.write_stop()

        self.assertEqual(decision(result), "deny", result.stderr)
        self.assertIn("app.py", result.stdout)
        self.assertIn("fork-write-scope", result.stdout)
        self.assertIn("1 path(s)", result.stdout)

    def test_a_deleted_source_file_is_denied_naming_the_file(self):
        (self.repo / "app.py").unlink()

        result = self.write_stop()

        self.assertEqual(decision(result), "deny", result.stderr)
        self.assertIn("app.py", result.stdout)

    def test_a_committed_source_edit_is_denied_naming_the_file(self):
        self.edit_source()
        git(self.repo, "commit", "-aqm", "edit")

        result = self.write_stop()

        self.assertEqual(decision(result), "deny", result.stderr)
        self.assertIn("app.py", result.stdout)

    def test_a_started_review_loop_allows_the_stop(self):
        self.edit_source()
        (self.run_folder / "loop-dir").write_text("/tmp/loop\n")

        self.assertEqual(decision(self.write_stop()), "allow")

    def test_no_edit_or_notes_only_allows_the_stop(self):
        self.assertEqual(decision(self.write_stop()), "allow")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "note.md").write_text("notes\n")

        self.assertEqual(decision(self.write_stop()), "allow")

    def test_a_new_untracked_source_file_is_denied_naming_it_and_not_the_notes_file(self):
        (self.repo / "new.py").write_text("y = 1\n")
        (self.repo / "docs").mkdir()
        (self.repo / "docs" / "note.md").write_text("notes\n")

        result = self.write_stop()

        self.assertEqual(decision(result), "deny", result.stderr)
        self.assertIn("new.py", result.stdout)
        self.assertNotIn("note.md", result.stdout)

    def test_a_second_stop_write_after_a_deny_is_allowed(self):
        self.edit_source()
        self.assertEqual(decision(self.write_stop()), "deny")

        self.assertEqual(decision(self.write_stop()), "allow")

    def test_no_resume_record_allows_the_stop(self):
        self.edit_source()
        (self.run_folder / "resume.json").unlink()

        self.assertEqual(decision(self.write_stop()), "allow")

    def test_a_non_code_fork_agent_is_allowed(self):
        self.edit_source()

        for agent_type in ("coder", None):
            with self.subTest(agent_type=agent_type):
                self.assertEqual(decision(self.write_stop(agent_type)), "allow")

    def assert_denied_naming_the_record_and_the_review(self, result):
        self.assertEqual(decision(result), "deny", result.stderr)
        self.assertIn("fork-write-scope", result.stdout)
        self.assertIn(str(self.run_folder / "resume.json"), result.stdout)
        self.assertIn("code_review_start.py ... --base <phase base>", result.stdout)
        for skip_path in ("delete", "Delete", "remove", "phase_start.py --resume"):
            self.assertNotIn(skip_path, result.stdout, f"the deny names a way past the review: {skip_path}")

    def test_a_corrupt_record_passes_once_a_review_loop_has_started(self):
        (self.run_folder / "resume.json").write_text("not json")
        (self.run_folder / "loop-dir").write_text("/some/loop\n")

        self.assertEqual(decision(self.write_stop()), "allow")

    def test_the_resume_gate_does_not_import_code_wait(self):
        probe = ("import sys; sys.path[:0] = [sys.argv[1], sys.argv[2]]; import resume_review_gate; "
                 "sys.exit(1 if 'code_wait' in sys.modules else 0)")
        done = subprocess.run([sys.executable, "-I", "-c", probe, str(toolkit_paths.LIB_DIR),
                               str(toolkit_paths.CODE_DIR)], capture_output=True, text=True, check=False)

        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_corrupt_resume_record_denies_naming_the_record_and_the_review(self):
        for text in ("not json", "[]", '{"repo": "x"}'):
            with self.subTest(text=text):
                (self.run_folder / "resume.json").write_text(text)

                self.assert_denied_naming_the_record_and_the_review(self.write_stop())

    def test_a_tree_that_cannot_be_fingerprinted_denies_naming_the_record_and_the_review(self):
        record_file = self.run_folder / "resume.json"
        record = json.loads(record_file.read_text())
        record_file.write_text(json.dumps({**record, "repo": str(self.repo / "missing")}))

        self.assert_denied_naming_the_record_and_the_review(self.write_stop())

    def test_the_deny_names_the_phase_base_for_the_review(self):
        self.edit_source()

        result = self.write_stop()

        self.assertIn("--base <phase base>", result.stdout)

    def test_a_commit_between_the_resume_and_the_stop_with_no_other_change_allows_the_stop(self):
        git(self.repo, "commit", "-q", "--allow-empty", "-m", "empty")

        self.assertEqual(decision(self.write_stop()), "allow")


class ForkHasWriteTest(unittest.TestCase):
    def test_code_fork_may_use_write(self):
        frontmatter = FORK_AGENT.read_text().split("---")[1]
        disallowed_line = next(line for line in frontmatter.splitlines() if line.startswith("disallowedTools:"))
        disallowed = [tool.strip() for tool in disallowed_line.split(":", 1)[1].split(",")]
        self.assertNotIn("Write", disallowed)
        self.assertIn("Edit", disallowed)

    def test_hook_is_registered_on_write(self):
        settings = json.loads(SETTINGS.read_text())
        commands = [hook["command"] for group in settings["hooks"]["PreToolUse"]
                    if group.get("matcher") == "Write" for hook in group.get("hooks", [])]
        self.assertTrue(any("gates/fork_write_scope.py" in command for command in commands), commands)


if __name__ == "__main__":
    unittest.main()
