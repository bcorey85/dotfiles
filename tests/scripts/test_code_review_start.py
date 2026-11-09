"""Tests for code_review_start.py: the prompt header of the review loop and the detached run."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

REVIEW_START = toolkit_paths.CODE_DIR / "code_review_start.py"
PLAN = "\n".join([
    "## Phase Status", "", "- [ ] Phase 1: First (risk: low)", "- [ ] Phase 2: Second (risk: low)", "",
    "## Phase 1: First", "", "### Changes Required", "", "#### 1. One", "**File**: `src/one.py`", "",
    "## Phase 2: Second", "", "### Changes Required", "", "#### 1. Two", "**File**: `src/two.py`", ""])


BASE = "abc1234"
SAMPLE_COMMANDS = ["ruff check {files:.py}", "python3 -m pytest {tests:.py}"]
STALE_PROSE_COMMAND = f"python3 {toolkit_paths.CODE_DIR / 'stale_prose.py'} --base {BASE}"
READABILITY_COMMAND = f"python3 {toolkit_paths.CODE_DIR / 'readability_check.py'} --base {BASE}"


class CodeReviewStartTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "docs/plans/p").mkdir(parents=True)
        (self.repo / "docs/plans/p/spec.md").write_text(PLAN)
        (self.repo / "handoff.txt").write_text("  Phase 1 is done.\n")

    def start(self, *extra):
        return subprocess.run([sys.executable, str(REVIEW_START), "lane-a", "docs/plans/p/spec.md", "1",
                               "handoff.txt", "--base", BASE, *extra], cwd=self.repo, capture_output=True, text=True,
                              check=False,
                              env={**os.environ, "CLAUDE_CODE_SESSION_ID": "test-session"})

    def test_a_dry_run_prints_the_header_the_later_phase_files_and_the_handoff(self):
        done = self.start("--dry-run")

        self.assertEqual(done.returncode, 0, done.stderr)
        header, _, handoff = done.stdout.partition("\n\n")
        self.assertEqual(header.splitlines(), [
            "mode: review-first", "caller: code", "lane: lane-a", f"repo: {self.repo}", "plan: docs/plans/p/spec.md",
            "phase: 1", "later-phase files: src/two.py"])
        self.assertEqual(handoff.strip(), "Phase 1 is done.")

    def test_a_later_phase_file_this_phase_already_changed_is_not_a_later_phase_file(self):
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "base"], check=True)
        (self.repo / "src").mkdir()
        (self.repo / "src/two.py").write_text("# guide lines phase 1 wrote\n")

        done = subprocess.run([sys.executable, str(REVIEW_START), "lane-a", "docs/plans/p/spec.md", "1",
                               "handoff.txt", "--base", "HEAD", "--dry-run"], cwd=self.repo, capture_output=True,
                              text=True, check=False, env={**os.environ, "CLAUDE_CODE_SESSION_ID": "test-session"})

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("later-phase files:", done.stdout)

    def load_module(self):
        module_spec = importlib.util.spec_from_file_location("code_review_start", REVIEW_START)
        code_review_start = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(code_review_start)
        return code_review_start

    def test_the_gate_commands_come_from_the_phase_section_of_the_plan(self):
        (self.repo / "pyproject.toml").write_text("[tool.ruff]\n")
        code_review_start = self.load_module()

        commands = code_review_start.phase_gate_commands(self.repo, "docs/plans/p/spec.md", "2", BASE)

        self.assertEqual(commands, [*SAMPLE_COMMANDS, STALE_PROSE_COMMAND, READABILITY_COMMAND])

    def test_a_plan_with_no_entry_for_the_phase_gives_the_gate_commands_of_the_whole_plan(self):
        (self.repo / "pyproject.toml").write_text("[tool.ruff]\n")
        code_review_start = self.load_module()

        commands = code_review_start.phase_gate_commands(self.repo, "docs/plans/p/spec.md", "9", BASE)

        self.assertEqual(commands, [*SAMPLE_COMMANDS, READABILITY_COMMAND])

    def test_the_live_run_passes_each_gate_command_to_the_loop(self):
        (self.repo / "pyproject.toml").write_text("[tool.ruff]\n")
        code_review_start = self.load_module()

        _printed, _prompt_folder, _loop_folder, command = self.run_live(code_review_start, write_packet=False)

        self.fake_handback.record_script_dispatch.assert_called_once_with("test-session", self.repo)
        passed = [command[at + 1] for at, word in enumerate(command) if word == "--gate-command"]
        self.assertEqual(passed, [*SAMPLE_COMMANDS, STALE_PROSE_COMMAND, READABILITY_COMMAND])
        self.assertTrue(code_review_start.coder_gate.is_stale_prose_check(passed[-2]))
        self.assertTrue(code_review_start.coder_gate.is_readability_check(passed[-1]))

    def run_live(self, code_review_start, write_packet, packet_text="status: converged\n"):
        # Runs main with the loop mocked; `write_packet` puts `packet_text` in packet.txt beside the prompt file.
        argv = ["code_review_start.py", "lane-a", "docs/plans/p/spec.md", "1", str(self.repo / "handoff.txt"),
                "--base", BASE]
        output = io.StringIO()

        with mock.patch.object(code_review_start, "subprocess") as fake_subprocess, \
                mock.patch.object(code_review_start, "handback_hook") as self.fake_handback, \
                mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "test-session"}), \
                mock.patch.object(pathlib.Path, "cwd", return_value=self.repo), \
                contextlib.redirect_stdout(output):
            fake_subprocess.run.return_value = mock.Mock(returncode=0)
            real_write_script_prompt = code_review_start.write_script_prompt
            prompt_folders = []

            def write_script_prompt(*args):
                prompt_file, log_path = real_write_script_prompt(*args)
                prompt_folders.append(prompt_file.parent)
                if write_packet:
                    (prompt_file.parent / "packet.txt").write_text(packet_text)
                return prompt_file, log_path

            with mock.patch.object(code_review_start, "write_script_prompt", write_script_prompt):
                code_review_start.main(argv)

        command = fake_subprocess.run.call_args.args[0]
        state_dir = command[command.index("--state-dir") + 1]
        agent_id = command[command.index("--agent-id") + 1]
        loop_folder = pathlib.Path(state_dir) / "loop-script" / agent_id

        return output.getvalue(), prompt_folders[0], loop_folder, command

    def test_the_live_run_hands_the_reviewers_to_the_fork_and_names_the_loop_folder(self):
        code_review_start = self.load_module()

        _printed, prompt_folder, _loop_folder, command = self.run_live(code_review_start, write_packet=False)

        self.assertEqual(command[command.index("--reviewers") + 1], "main")
        loop_dir_file = self.repo / ".git/code-phase/loop-dir"
        self.assertEqual(loop_dir_file.read_text().strip(), str(prompt_folder))

    def test_detach_drops_the_loop_folder_an_earlier_phase_named(self):
        code_review_start = self.load_module()
        phase_dir = self.repo / ".git/code-phase"
        phase_dir.mkdir()
        (phase_dir / "loop-dir").write_text("/old/loop\n")

        with mock.patch.object(code_review_start, "subprocess") as fake_subprocess, \
                contextlib.redirect_stdout(io.StringIO()):
            fake_subprocess.Popen.return_value = mock.Mock(pid=4242)
            code_review_start.detach(self.repo, ["code_review_start.py", "lane-a", "--detach"])

        self.assertFalse((phase_dir / "loop-dir").exists())

    def test_detach_refuses_while_another_review_loop_of_this_repo_runs(self):
        code_review_start = self.load_module()
        phase_dir = self.repo / ".git/code-phase"
        phase_dir.mkdir()
        (phase_dir / "pid").write_text(str(os.getpid()))
        (phase_dir / "loop-dir").write_text("/running/loop\n")
        (phase_dir / "review.out").write_text("running loop output\n")

        with mock.patch.object(code_review_start, "subprocess") as fake_subprocess, \
                self.assertRaises(SystemExit) as stop:
            code_review_start.detach(self.repo, ["code_review_start.py", "lane-a", "--detach"])

        self.assertIn(str(os.getpid()), str(stop.exception.code))
        self.assertIn("/running/loop", str(stop.exception.code))
        fake_subprocess.Popen.assert_not_called()
        self.assertEqual((phase_dir / "pid").read_text(), str(os.getpid()))
        self.assertEqual((phase_dir / "review.out").read_text(), "running loop output\n")

    def test_the_live_run_prints_the_packet_the_loop_wrote_beside_the_prompt(self):
        printed, prompt_folder, loop_folder, _command = self.run_live(self.load_module(), write_packet=True)

        self.assertIn("status: converged", printed)
        self.assertEqual(loop_folder, prompt_folder, "the loop writes its packet where the run looks for it")

    def test_a_converged_packet_with_a_held_plan_impact_prints_the_defer_action(self):
        impacts = [{"text": "PLAN-IMPACT: AC2 now names the archived orders too", "gate": "code-reviewer",
                    "ac_change": True, "cause": "plan", "adopted": False}]
        packet = json.dumps({"status": "converged", "iter": 1, "fixed": [], "plan_impacts": impacts})

        printed, _folder, _loop_folder, _command = self.run_live(self.load_module(), write_packet=True,
                                                                 packet_text=packet)

        handoff = self.repo / "handoff.txt"
        self.assertIn("ACTION: defer-plan-impacts. 1 plan impact(s) wait for a ruling", printed)
        self.assertIn(f"review_fix.py defer {handoff}", printed)

    def test_a_converged_packet_with_only_an_adopted_plan_impact_prints_no_defer_action(self):
        impacts = [{"text": "PLAN-IMPACT: the helper lives in lib", "gate": "code-reviewer", "ac_change": False,
                    "cause": "plan", "adopted": True}]
        packet = json.dumps({"status": "converged", "iter": 1, "fixed": [], "plan_impacts": impacts})

        printed, _folder, _loop_folder, _command = self.run_live(self.load_module(), write_packet=True,
                                                                 packet_text=packet)

        self.assertNotIn("defer-plan-impacts", printed)

    def test_the_live_run_names_the_log_when_the_loop_wrote_no_packet(self):
        printed, folder, _loop_folder, _command = self.run_live(self.load_module(), write_packet=False)

        self.assertIn("No packet. Log: ", printed)
        self.assertIn(str(self.repo / ".git/code-step/loop-script"), str(folder))

    def test_a_dash_for_the_plan_leaves_out_the_plan_lines_and_takes_the_gate_files_from_the_handoff(self):
        (self.repo / "pyproject.toml").write_text("[tool.ruff]\n")
        (self.repo / "handoff.txt").write_text("handoff:\n  files:\n    - path: src/one.py\n      change: x\n")
        base = self.commit_base()
        code_review_start = self.load_module()

        done = subprocess.run([sys.executable, str(REVIEW_START), "lane-a", "-", "1", "handoff.txt", "--base", base,
                               "--dry-run"], cwd=self.repo, capture_output=True, text=True, check=False)
        commands = code_review_start.phase_gate_commands(self.repo, "-", "1", BASE,
                                                         (self.repo / "handoff.txt").read_text())

        self.assertEqual(done.returncode, 0, done.stderr)
        header = done.stdout.partition("\n\n")[0].splitlines()
        self.assertEqual(["mode: review-first", "caller: code", "lane: lane-a", f"repo: {self.repo}"], header)
        self.assertEqual([*SAMPLE_COMMANDS, READABILITY_COMMAND], commands)

    def test_a_handoff_that_names_a_repo_root_file_gets_its_gate(self):
        (self.repo / "pyproject.toml").write_text("[tool.ruff]\n")
        (self.repo / "app.py").write_text("")
        code_review_start = self.load_module()

        commands = code_review_start.phase_gate_commands(self.repo, "-", "1", BASE,
                                                         "handoff:\n  files:\n    - path: app.py\n      change: x\n")

        self.assertEqual([*SAMPLE_COMMANDS, READABILITY_COMMAND], commands)

    def commit_base(self):
        git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.com"]
        subprocess.run([*git, "add", "-A"], cwd=self.repo, check=True)
        subprocess.run([*git, "commit", "-q", "-m", "base"], cwd=self.repo, check=True)
        done = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, capture_output=True, text=True, check=True)
        return done.stdout.strip()

    def test_the_handoff_files_come_from_git_and_only_the_coders_why_lines_are_kept(self):
        base = self.commit_base()
        (self.repo / "src").mkdir()
        (self.repo / "src/tracked.py").write_text("a = 1\n")
        subprocess.run(["git", "add", "src/tracked.py"], cwd=self.repo, check=True)
        (self.repo / "docs/plans/p/spec.md").write_text(PLAN + "edited\n")
        (self.repo / "src/untracked.py").write_text("b = 2\n")
        coder_handoff = "\n".join([
            "handoff:", "  files:", "    - path: src/untracked.py", "      change: invented export foo",
            "      why:", "        - lines: 1-1", "          note: kept", "    - path: src/forgotten_by_git.py",
            "      change: not changed at all", "  tests-run: none", "  iter: 0", ""])
        (self.repo / "handoff.txt").write_text(coder_handoff)

        done = subprocess.run([sys.executable, str(REVIEW_START), "lane-a", "-", "1", "handoff.txt", "--base", base,
                               "--dry-run"], cwd=self.repo, capture_output=True, text=True, check=False)

        self.assertEqual(done.returncode, 0, done.stderr)
        handoff = done.stdout.partition("\n\n")[2]
        paths = [line.split("path: ")[1] for line in handoff.splitlines() if "path: " in line]
        self.assertEqual(["docs/plans/p/spec.md", "handoff.txt", "src/tracked.py", "src/untracked.py"], paths)
        self.assertNotIn("invented export", handoff)
        self.assertNotIn("forgotten_by_git", handoff)
        self.assertIn("      why:\n        - lines: 1-1\n          note: kept\n  tests-run: none", handoff)

    def test_a_base_that_is_not_a_commit_stops_the_run_when_the_handoff_lists_files(self):
        (self.repo / "handoff.txt").write_text("handoff:\n  files:\n    - path: a.py\n  iter: 0\n")

        done = self.start("--dry-run")

        self.assertNotEqual(done.returncode, 0)
        self.assertIn("is not a commit", done.stderr)

    def test_too_few_arguments_print_the_usage(self):
        done = subprocess.run([sys.executable, str(REVIEW_START), "lane-a"], cwd=self.repo, capture_output=True,
                              text=True, check=False)

        self.assertEqual(done.returncode, 1)
        self.assertIn("code_review_start.py <lane> <plan> <phase> <handoff file>", done.stderr)

    def test_detach_names_the_wait_command_and_leaves_a_pid_for_it(self):
        code_review_start = self.load_module()
        output = io.StringIO()

        with mock.patch.object(code_review_start, "subprocess") as fake_subprocess, \
                contextlib.redirect_stdout(output):
            popen = fake_subprocess.Popen
            popen.return_value = mock.Mock(pid=4242)
            code_review_start.detach(self.repo, ["code_review_start.py", "lane-a", "--detach"])

        self.assertIn("python3 ~/.claude/scripts/code/code_wait.py review", output.getvalue())
        self.assertIn("Bash timeout set to 600000", output.getvalue())
        self.assertNotIn("--detach", popen.call_args.args[0])
        self.assertIs(popen.call_args.kwargs["start_new_session"], True)
        self.assertIs(popen.call_args.kwargs["stdin"], fake_subprocess.DEVNULL)
        phase_dir = self.repo / ".git/code-phase"
        self.assertEqual((phase_dir / "pid").read_text(), "4242")
        self.assertTrue((phase_dir / "review.out").exists())


if __name__ == "__main__":
    unittest.main()
