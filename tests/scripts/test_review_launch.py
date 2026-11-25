"""Checks for `review_fix.py launch` (review_launch.py): what a launch consumes from the code-fork run folder, and which
earlier loops it stops.

Set REVIEW_FIX_SCRIPT to run against another copy of review_fix.py."""
import argparse
import contextlib
import io
import itertools
import json
import os
import pathlib
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import fake_ledger
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
import code_wait
import handback_store
import process_group
import review_fix_names
import review_launch
import reviewer_dispatch
import stop_file_names

SCRIPT = pathlib.Path(os.environ.get("REVIEW_FIX_SCRIPT") or toolkit_paths.REVIEW_DIR / "review_fix.py")
SESSION = "11111111-aaaa-bbbb-cccc-222222222222"
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}
FINDINGS = "- README.md:1 the greeting is wrong\n"
HANDOFF = "Fix the greeting.\n"
WAIT_SECONDS = 10


def process_is_running(pid):
    command = process_group.command_line(pid)
    return bool(command) and "<defunct>" not in command


def wait_until_gone(pid):
    deadline = time.monotonic() + WAIT_SECONDS
    while time.monotonic() < deadline:
        if not process_is_running(pid):
            return True
        time.sleep(0.1)
    return False


class ReviewLaunchTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name)
        self.ledger_env = fake_ledger.install(self.temp_root)
        self.loop_stub = self.temp_root / "loop_stub.py"
        self.loop_stub.write_text("import time\ntime.sleep(60)\n")
        self.repo = self.make_repo("myrepo")
        self.run_folder = self.repo / ".git" / code_wait.PHASE_DIR_NAME
        self.run_folder.mkdir()
        self.addCleanup(self.stop_every_loop)

    def make_repo(self, name):
        repo = self.temp_root / name
        repo.mkdir()
        self.git(repo, "init", "-q")
        (repo / "README.md").write_text("hi\n")
        self.git(repo, "add", "README.md")
        self.git(repo, "commit", "-q", "-m", "init")
        return repo

    def git(self, repo, *args):
        subprocess.run(["git", *args], cwd=repo, env={**os.environ, **GIT_ENV}, check=True, capture_output=True)

    def loop_dirs(self, repo):
        loop_root = repo / ".git" / "review-script" / reviewer_dispatch.LOOP_FOLDER
        return sorted(loop_root.iterdir()) if loop_root.is_dir() else []

    def stop_every_loop(self):
        for repo in self.temp_root.iterdir():
            for loop_dir in self.loop_dirs(repo):
                pid = reviewer_dispatch.loop_pid(loop_dir)
                if pid is None:
                    continue
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    continue

    def run_launch(self, *flags, repo=None, env_overrides=None, detach=True):
        repo = repo or self.repo
        detach_flags = ["--detach"] if detach else []
        (repo / "README.md").write_text(f"hi, edited {time.monotonic()}\n")
        environment = {**os.environ, **GIT_ENV, **self.ledger_env, "CLAUDE_CODE_SESSION_ID": SESSION,
                       "HANDBACK_STORE_DIR": str(self.temp_root / "store"),
                       "REVIEW_FIX_LOOP_SCRIPT": str(self.loop_stub), "CLAUDE_TOOLKIT_TELEMETRY": "1",
                       **(env_overrides or {})}
        return subprocess.run([sys.executable, "-I", str(SCRIPT), "launch", *detach_flags, *flags], cwd=repo,
                              text=True, capture_output=True, env=environment, check=False)

    def launch(self, *flags, repo=None, env_overrides=None):
        done = self.run_launch(*flags, repo=repo, env_overrides=env_overrides)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout + done.stderr

    def write_inputs(self, folder):
        folder.mkdir(parents=True, exist_ok=True)
        fix_file = folder / "fix-findings.md"
        handoff_file = folder / "review-handoff.txt"
        fix_file.write_text(FINDINGS)
        handoff_file.write_text(HANDOFF)
        return fix_file, handoff_file

    def test_a_launch_deletes_the_run_folder_inputs_it_read_and_keeps_a_review_stop(self):
        fix_file, handoff_file = self.write_inputs(self.run_folder)
        stop_file = self.run_folder / stop_file_names.REVIEW_STOP_FILE
        stop_file.write_text("old stop\n")

        self.launch("--fix", str(fix_file), "--handoff", str(handoff_file))

        self.assertFalse(fix_file.exists(), "the run-folder findings file stays for the next launch")
        self.assertFalse(handoff_file.exists(), "the run-folder handoff file stays for the next launch")
        self.assertTrue(stop_file.exists(), "launch deleted review-stop.md")
        loop_dir = self.loop_dirs(self.repo)[-1]
        self.assertEqual((loop_dir / "handoff.txt").read_text(), HANDOFF)
        self.assertTrue((loop_dir / "findings.json").is_file())

    def test_also_fix_findings_follow_the_fix_findings_and_the_run_folder_file_is_consumed(self):
        fix_file = self.run_folder / "asks.md"
        also_file = self.run_folder / review_fix_names.RUN_FOLDER_FINDINGS_NAME
        fix_file.write_text("- README.md:1 first bug\n- README.md:2 second bug\n")
        also_file.write_text("- README.md:3 deferred bug\n  continued\n")

        self.launch("--fix", str(fix_file), "--also-fix", str(also_file), "--user-ruled", "2")

        loop_dir = self.loop_dirs(self.repo)[-1]
        kept = json.loads((loop_dir / "findings.json").read_text())
        self.assertEqual(
            kept, ["README.md:1 first bug", "README.md:2 second bug", "README.md:3 deferred bug continued"])
        prompt_file = next((self.repo / ".git" / "review-script" / "loop-script").glob("*/prompt.txt"))
        self.assertRegex(prompt_file.read_text(), r"(?m)^user-ruled: 2$")
        self.assertFalse(fix_file.exists(), "the run-folder --fix file is consumed by the launch")
        self.assertFalse(also_file.exists(), "the run-folder --also-fix file is consumed by the launch")
        launch_record = json.loads((loop_dir / reviewer_dispatch.LAUNCH_FILE).read_text())
        self.assertNotIn("--also-fix", json.dumps(launch_record))

    def test_each_ruled_out_file_reaches_the_prompt_header_and_the_relaunch_args_as_a_repo_relative_path(self):
        absolute = str(self.repo / "sub" / "b.py")

        self.launch("--ruled-out", "a.py", "--ruled-out", absolute)

        prompt_file = next((self.repo / ".git" / "review-script" / "loop-script").glob("*/prompt.txt"))
        self.assertRegex(prompt_file.read_text(), r"(?m)^ruled-out files: a\.py, sub/b\.py$")
        loop_dir = self.loop_dirs(self.repo)[-1]
        relaunch = json.loads((loop_dir / reviewer_dispatch.LAUNCH_FILE).read_text())["relaunch_args"]
        self.assertEqual([relaunch[index + 1] for index, word in enumerate(relaunch) if word == "--ruled-out"],
                         ["a.py", "sub/b.py"])

    def test_a_launch_with_no_ruled_out_file_writes_no_ruled_out_line(self):
        self.launch()

        prompt_file = next((self.repo / ".git" / "review-script" / "loop-script").glob("*/prompt.txt"))
        self.assertNotIn("ruled-out", prompt_file.read_text())

    def test_a_ruled_out_file_outside_the_repo_stops_the_launch_and_the_error_names_the_flag(self):
        outside = self.temp_root / "elsewhere.py"

        with self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.ruled_out_files(self.repo.resolve(), [str(outside)])

        self.assertIn(f"--ruled-out {outside} is outside the repo", str(raised.exception))

    def session_brief(self, root_name, text):
        root = self.temp_root / root_name / f"claude-{os.getuid()}"
        root.mkdir(parents=True)
        brief = root / "brief.md"
        brief.write_text(text)
        return brief

    def test_a_file_flag_naming_a_brief_under_the_tmpdir_session_root_reaches_the_reviewer_prompt(self):
        brief = self.session_brief("tmpdir", "Check the retry path first.\n")

        self.launch("--file", str(brief), "--file", "README.md",
                    env_overrides={"TMPDIR": str(self.temp_root / "tmpdir")})

        prompt_file = next((self.repo / ".git" / "review-script" / "loop-script").glob("*/prompt.txt"))
        self.assertIn("Check the retry path first.", prompt_file.read_text())
        loop_dir = self.loop_dirs(self.repo)[-1]
        self.assertIn("Check the retry path first.", (loop_dir / "handoff.txt").read_text())
        relaunch = json.loads((loop_dir / reviewer_dispatch.LAUNCH_FILE).read_text())["relaunch_args"]
        self.assertNotIn(str(brief), relaunch)

    def test_a_brief_under_the_claude_code_tmpdir_root_is_read_as_a_brief(self):
        brief = self.session_brief("cct", "brief\n")

        with mock.patch.dict(os.environ, {"CLAUDE_CODE_TMPDIR": str(self.temp_root / "cct")}):
            split = review_launch.split_brief_files(self.repo.resolve(), [str(brief)])

        self.assertEqual((split.repo_files, split.briefs), ([], [brief.resolve()]))

    def test_a_relative_file_flag_outside_the_repo_is_read_against_the_repo_and_kept_as_a_brief(self):
        brief = self.session_brief("tmpdir", "brief\n")
        relative = os.path.relpath(brief, self.repo)

        with mock.patch.dict(os.environ, {"TMPDIR": str(self.temp_root / "tmpdir")}):
            split = review_launch.split_brief_files(self.repo.resolve(), [relative])

        self.assertEqual(split.briefs, [brief.resolve()])

    def test_a_brief_that_is_not_utf8_stops_with_a_launch_error_naming_the_file(self):
        brief = self.session_brief("tmpdir", "")
        brief.write_bytes(b"\xff\xfe")

        with self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.with_briefs("handoff", [brief])

        self.assertIn(str(brief), str(raised.exception))

    def test_a_file_flag_outside_the_repo_and_the_session_root_stops_and_names_every_root_form(self):
        with self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.split_brief_files(self.repo.resolve(), ["/etc/hosts"])

        message = str(raised.exception)
        self.assertIn("--file /etc/hosts is outside the repo", message)
        self.assertIn("/tmp/claude-<uid>/", message)
        self.assertIn("$TMPDIR/claude-<uid>/", message)
        self.assertIn("$CLAUDE_CODE_TMPDIR/claude-<uid>/", message)

    def test_a_missing_file_under_the_session_root_stops(self):
        missing = self.temp_root / "tmpdir" / f"claude-{os.getuid()}" / "nope.md"

        tmpdir = {"TMPDIR": str(self.temp_root / "tmpdir")}
        with mock.patch.dict(os.environ, tmpdir), self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.split_brief_files(self.repo.resolve(), [str(missing)])

        self.assertIn(f"--file {missing} is outside the repo", str(raised.exception))

    def test_a_folder_given_to_ruled_out_stops_the_launch(self):
        (self.repo / "sub").mkdir()
        (self.repo / "sub" / "b.py").write_text("x = 1\n")

        with self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.ruled_out_files(self.repo.resolve(), ["sub"])

        self.assertIn("--ruled-out sub is a folder; --ruled-out takes one file per flag", str(raised.exception))

    def test_a_tree_whose_only_changes_are_ruled_out_files_stops_as_an_empty_scope(self):
        environment = {**os.environ, **GIT_ENV, **self.ledger_env, "CLAUDE_CODE_SESSION_ID": SESSION,
                       "HANDBACK_STORE_DIR": str(self.temp_root / "store"),
                       "REVIEW_FIX_LOOP_SCRIPT": str(self.loop_stub), "CLAUDE_TOOLKIT_TELEMETRY": "1"}
        (self.repo / "README.md").write_text("hi, edited\n")

        with mock.patch.dict(os.environ, environment), self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.command_launch(["--detach", "--repo", str(self.repo), "--ruled-out", "README.md"],
                                         str(self.loop_stub))

        self.assertIn("every changed file against HEAD was given to --ruled-out", str(raised.exception))
        self.assertEqual(self.loop_dirs(self.repo), [])

    def test_also_fix_without_fix_stops_the_launch(self):
        with self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.launch_arguments(["--also-fix", "x.md"])
        self.assertIn("needs --fix", str(raised.exception))

    def test_a_launch_keeps_inputs_outside_the_run_folder_and_the_asks_findings_file(self):
        outside_fix, outside_handoff = self.write_inputs(self.temp_root / "elsewhere")
        outside_stop = self.run_folder / stop_file_names.REVIEW_STOP_FILE
        outside_stop.write_text("old stop\n")
        self.launch("--fix", str(outside_fix), "--handoff", str(outside_handoff))
        self.assertTrue(outside_fix.exists(), "a findings file outside the run folder was deleted")
        self.assertTrue(outside_handoff.exists(), "a handoff file outside the run folder was deleted")
        self.assertTrue(outside_stop.exists(), "launch deleted review-stop.md")

        asks_folder = self.repo / ".git" / review_fix_names.REVIEW_FIX_FOLDER
        asks_file = asks_folder / review_fix_names.ASK_FINDINGS_NAME
        asks_folder.mkdir()
        asks_file.write_text(FINDINGS)
        self.launch("--fix", str(asks_file))
        self.assertTrue(asks_file.exists(), "the asks findings file was deleted")

    def test_a_second_launch_of_the_repo_stops_the_first_loops_process_group(self):
        self.launch()
        first_dir = self.loop_dirs(self.repo)[-1]
        first_pid = reviewer_dispatch.loop_pid(first_dir)
        self.assertTrue(process_is_running(first_pid))

        output = self.launch()

        self.assertTrue(wait_until_gone(first_pid), "the first loop is still running")
        self.assertIn(first_dir.name, output)
        # Loop folder names sort by second, so two launches in one second sort in random order: pick by name.
        second_dir = next(loop_dir for loop_dir in self.loop_dirs(self.repo) if loop_dir != first_dir)
        second_pid = reviewer_dispatch.loop_pid(second_dir)
        self.assertTrue(process_is_running(second_pid), "the new loop was stopped")

    def test_a_launch_saves_its_skill_in_the_launch_record(self):
        self.launch()
        record = json.loads((self.loop_dirs(self.repo)[-1] / reviewer_dispatch.LAUNCH_FILE).read_text())
        self.assertEqual(record["packet_args"][:2], ["--skill", "review"])

    def test_a_launch_saves_its_branch_launch_time_and_detach_flag(self):
        before = time.time()
        self.launch()
        record = json.loads((self.loop_dirs(self.repo)[-1] / reviewer_dispatch.LAUNCH_FILE).read_text())
        branch = subprocess.run(["git", "-C", str(self.repo), "branch", "--show-current"], capture_output=True,
                                text=True, check=True).stdout.strip()
        self.assertEqual(record["branch"], branch)
        self.assertGreaterEqual(record["launched_at"], before)
        self.assertIs(record["detach"], True)

    def test_a_launch_from_a_detached_head_saves_an_empty_branch(self):
        subprocess.run(["git", "-C", str(self.repo), "checkout", "--detach"], capture_output=True, check=True)
        self.launch()
        record = json.loads((self.loop_dirs(self.repo)[-1] / reviewer_dispatch.LAUNCH_FILE).read_text())
        self.assertEqual(record["branch"], "")

    def test_a_launch_without_detach_saves_detach_false(self):
        done = self.run_launch(detach=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        record = json.loads((self.loop_dirs(self.repo)[-1] / reviewer_dispatch.LAUNCH_FILE).read_text())
        self.assertIs(record["detach"], False)

    def test_a_refusal_comes_before_any_loop_is_stopped(self):
        # The fix loop sorts first, so a single pass that checks and then stops each loop would stop it before it
        # reached the review loop and refused.
        fix_loop = self.plant_loop(self.repo, "review-script-a-fix", record_repo=self.repo, skill="fix")
        review_loop = self.plant_loop(self.repo, "review-script-b-review", record_repo=self.repo, skill="review")
        fix_file, _handoff = self.write_inputs(self.run_folder)

        done = self.run_launch("--fix", str(fix_file))

        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertTrue(process_is_running(reviewer_dispatch.loop_pid(review_loop)), "the review loop was stopped")
        self.assertTrue(process_is_running(reviewer_dispatch.loop_pid(fix_loop)), "the fix loop was stopped")

    def test_a_loop_of_another_repo_or_another_command_does_not_refuse_a_launch(self):
        other_repo = self.make_repo("otherrepo")
        foreign = self.plant_loop(self.repo, "review-script-foreign-fix", record_repo=other_repo, skill="fix")
        stranger = self.plant_loop(self.repo, "review-script-stranger-none", record_repo=self.repo, skill=None,
                                   command_names_agent=False)

        done = self.run_launch()

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for planted in (foreign, stranger):
            self.assertTrue(process_is_running(reviewer_dispatch.loop_pid(planted)), f"{planted.name} was stopped")

    def test_a_fix_launch_refuses_a_live_review_loop_and_leaves_it_running(self):
        review_loop = self.plant_loop(self.repo, "review-script-review", record_repo=self.repo, skill="review")
        review_pid = reviewer_dispatch.loop_pid(review_loop)
        fix_file, _handoff = self.write_inputs(self.run_folder)

        done = self.run_launch("--fix", str(fix_file))

        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        output = done.stdout + done.stderr
        for named in (review_loop.name, "started as a review run, not a fix run", str(review_pid)):
            self.assertIn(named, output)
        self.assertIn(f"End the run with a stop that names this loop; launch again after pid {review_pid} exits.",
                      output)
        self.assertNotIn(reviewer_dispatch.WAIT_COMMAND, output)
        self.assertTrue(process_is_running(review_pid), "the review loop was stopped")
        self.assertEqual(self.loop_dirs(self.repo), [review_loop], "a loop folder was made")

    def test_a_loop_record_with_no_skill_reads_as_another_skill(self):
        unlabeled = self.plant_loop(self.repo, "review-script-unlabeled", record_repo=self.repo, skill=None)

        done = self.run_launch()

        self.assertEqual(done.returncode, 2, done.stdout + done.stderr)
        self.assertIn(unlabeled.name, done.stdout + done.stderr)
        self.assertTrue(process_is_running(reviewer_dispatch.loop_pid(unlabeled)), "the loop was stopped")

    def test_a_fix_relaunch_stops_the_live_fix_loop(self):
        fix_file, _handoff = self.write_inputs(self.run_folder)
        self.launch("--fix", str(fix_file))
        first_dir = self.loop_dirs(self.repo)[-1]
        first_pid = reviewer_dispatch.loop_pid(first_dir)
        fix_file, _handoff = self.write_inputs(self.run_folder)

        output = self.launch("--fix", str(fix_file))

        self.assertIn(f"Stopped the earlier review loop {first_dir.name}", output)
        self.assertTrue(wait_until_gone(first_pid), "the first fix loop is still running")

    def test_a_launch_leaves_a_loop_of_another_repo_and_a_pid_of_another_command_running(self):
        other_repo = self.make_repo("otherrepo")
        self.launch(repo=other_repo)
        other_pid = reviewer_dispatch.loop_pid(self.loop_dirs(other_repo)[-1])
        # A loop folder of this repo's state whose launch record names the other repo.
        foreign_dir = self.plant_loop(self.repo, "review-script-foreign", record_repo=other_repo)
        # A loop folder of this repo whose pid runs a command that does not name its agent id.
        stranger_dir = self.plant_loop(self.repo, "review-script-stranger", record_repo=self.repo,
                                       command_names_agent=False)

        self.launch()

        self.assertTrue(process_is_running(other_pid), "a loop of another repo was stopped")
        for planted in (foreign_dir, stranger_dir):
            self.assertTrue(process_is_running(reviewer_dispatch.loop_pid(planted)),
                            f"{planted.name} was stopped")

    def test_a_launch_goes_on_and_reports_when_ps_fails(self):
        planted = self.plant_loop(self.repo, "review-script-planted", record_repo=self.repo)
        stub_dir = self.temp_root / "failing_ps"
        stub_dir.mkdir()
        stub = stub_dir / "ps"
        stub.write_text("#!/bin/sh\necho 'ps broke' >&2\nexit 2\n")
        stub.chmod(0o755)
        env_overrides = {"PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}"}

        output = self.launch(env_overrides=env_overrides)

        self.assertIn("could not stop the loop", output)
        self.assertTrue(process_is_running(reviewer_dispatch.loop_pid(planted)), "the planted loop was stopped")
        new_dir = [loop_dir for loop_dir in self.loop_dirs(self.repo) if loop_dir != planted][-1]
        self.assertTrue(process_is_running(reviewer_dispatch.loop_pid(new_dir)), "the new loop did not start")

    def test_a_launch_goes_on_and_reports_a_loop_record_it_cannot_read(self):
        corrupt = self.plant_loop(self.repo, "review-script-corrupt", record_repo=self.repo)
        (corrupt / reviewer_dispatch.LAUNCH_FILE).write_text("not json\n")
        wrong_shape = self.plant_loop(self.repo, "review-script-wrongshape", record_repo=self.repo)
        (wrong_shape / reviewer_dispatch.LAUNCH_FILE).write_text(json.dumps({"relaunch_args": {"a": 1}}) + "\n")

        output = self.launch()

        self.assertEqual(output.count("could not stop the loop"), 2, output)
        new_dir = [loop_dir for loop_dir in self.loop_dirs(self.repo) if loop_dir not in (corrupt, wrong_shape)][-1]
        self.assertTrue(process_is_running(reviewer_dispatch.loop_pid(new_dir)), "the new loop did not start")

    def test_a_launch_skips_a_gone_loop_without_reading_its_record(self):
        gone = self.plant_loop(self.repo, "review-script-gone", record_repo=self.repo)
        (gone / reviewer_dispatch.LAUNCH_FILE).write_text(json.dumps({"packet_args": []}) + "\n")
        # A reaped child: its pid is gone. Killing the planted loop would leave a zombie, which still counts as live.
        finished = subprocess.Popen([sys.executable, "-c", "pass"])
        finished.wait()
        (gone / reviewer_dispatch.PID_FILE).write_text(f"{finished.pid}\n")

        output = self.launch()

        self.assertNotIn("could not stop the loop", output)

    def test_a_launch_that_leaves_out_one_ruled_impact_renumbers_user_ruled_and_fixes_the_rest(self):
        impact = "PLAN-IMPACT: AC2 reworded. acceptance_criteria: AC2"
        store = self.temp_root / "store"
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(store)}):
            handback_store.record_ruled_impact(SESSION, impact, os.path.realpath(self.repo), finding_text=impact)
        findings_file = self.temp_root / "three-findings.md"
        findings_file.write_text(f"- README.md:1 first bug\n- {impact}\n- README.md:3 third bug\n")

        output = self.launch("--fix", str(findings_file), "--user-ruled", "2", "--user-ruled", "3")

        self.assertIn("Left out of the fix run", output)
        loop_dir = self.loop_dirs(self.repo)[-1]
        kept = json.loads((loop_dir / "findings.json").read_text())
        self.assertEqual(kept, ["README.md:1 first bug", "README.md:3 third bug"])
        prompt_file = next((self.repo / ".git" / "review-script" / "loop-script").glob("*/prompt.txt"))
        self.assertRegex(prompt_file.read_text(), r"(?m)^user-ruled: 2$")

    def test_a_fix_launch_that_leaves_out_every_finding_gets_the_plain_review_handoff(self):
        impact = "PLAN-IMPACT: AC2 reworded. acceptance_criteria: AC2"
        store = self.temp_root / "store"
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(store)}):
            handback_store.record_ruled_impact(SESSION, impact, os.path.realpath(self.repo), finding_text=impact)
        findings_file = self.temp_root / "one-finding.md"
        findings_file.write_text(f"- {impact}\n")

        self.launch("--fix", str(findings_file), "--user-ruled", "1")

        loop_dir = self.loop_dirs(self.repo)[-1]
        self.assertEqual((loop_dir / "handoff.txt").read_text(), review_launch.DEFAULT_HANDOFF)

    def test_a_session_ruled_flag_reaches_the_prompt_header_of_the_fix_run(self):
        findings_file = self.temp_root / "two-findings.md"
        findings_file.write_text("- README.md:1 first bug\n- README.md:2 second bug\n")

        self.launch("--fix", str(findings_file), "--session-ruled", "2")

        prompt_file = next((self.repo / ".git" / "review-script" / "loop-script").glob("*/prompt.txt"))
        prompt = prompt_file.read_text()
        self.assertRegex(prompt, r"(?m)^session-ruled: 2$")
        self.assertNotIn("user-ruled", prompt)

    def test_the_session_ruled_header_follows_a_ruled_impact_dropped_before_it(self):
        impact = "PLAN-IMPACT: AC2 reworded. acceptance_criteria: AC2"
        store = self.temp_root / "store"
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(store)}):
            handback_store.record_ruled_impact(SESSION, impact, os.path.realpath(self.repo), finding_text=impact)
        findings_file = self.temp_root / "impact-then-bug.md"
        findings_file.write_text(f"- {impact}\n- README.md:2 second bug\n")

        self.launch("--fix", str(findings_file), "--session-ruled", "2")

        prompt_file = next((self.repo / ".git" / "review-script" / "loop-script").glob("*/prompt.txt"))
        self.assertRegex(prompt_file.read_text(), r"(?m)^session-ruled: 1$")

    def test_a_launch_with_no_fix_still_carries_an_adopted_ruling_as_a_finding(self):
        impact = "PLAN-IMPACT: AC2 reworded. acceptance_criteria: AC2"
        store = self.temp_root / "store"
        with mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(store), "CLAUDE_CODE_SESSION_ID": SESSION}):
            handback_store.record_ruled_impact(SESSION, impact, os.path.realpath(self.repo), finding_text=impact,
                                               decision="adopt", owner="the user", ruled_at="2026-11-19 10:00")
            options = review_launch.launch_arguments([])
            found = review_launch.fix_run_findings(options, self.repo)

        self.assertEqual(len(found.findings), 1)
        self.assertIn(impact, found.findings[0])
        self.assertEqual(found.user_ruled_numbers, [1])

    def test_a_session_ruled_flag_with_no_fix_stops_the_launch(self):
        with self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.launch_arguments(["--session-ruled", "1"])
        self.assertIn("needs --fix", str(raised.exception))

    def test_a_session_ruled_number_past_the_findings_stops_the_launch_like_a_user_ruled_one(self):
        findings_file = self.temp_root / "one-finding.md"
        findings_file.write_text("- README.md:1 only bug\n")
        for flag in ("--user-ruled", "--session-ruled"):
            options = review_launch.launch_arguments(["--fix", str(findings_file), flag, "3"])
            with self.assertRaises(review_launch.LaunchError) as raised:
                review_launch.fix_run_findings(options, self.repo)
            self.assertIn(f"{flag} 3 names no finding", str(raised.exception))

    def test_relaunch_flags_with_no_repo_value_or_no_repo_flag_name_no_repo(self):
        self.assertIsNone(review_launch.relaunch_repo(["--repo"]))
        self.assertIsNone(review_launch.relaunch_repo([]))

    def plant_loop(self, repo, agent_id, record_repo, command_names_agent=True, skill="review"):
        loop_dir = repo / ".git" / "review-script" / reviewer_dispatch.LOOP_FOLDER / agent_id
        loop_dir.mkdir(parents=True)
        marker = agent_id if command_names_agent else "unrelated"
        process = subprocess.Popen([sys.executable, str(self.loop_stub), marker], start_new_session=True)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        (loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{process.pid}\n")
        record = {"relaunch_args": ["--repo", str(record_repo)]}
        if skill:
            record["packet_args"] = ["--skill", skill]
        (loop_dir / reviewer_dispatch.LAUNCH_FILE).write_text(json.dumps(record) + "\n")
        return loop_dir


class UserRuledHeaderTest(unittest.TestCase):
    def test_the_user_ruled_time_is_the_plan_ruling_form_the_deviation_entry_takes(self):
        options = argparse.Namespace(fix="findings.md", skill="code", lane="code", no_review=False, fast=False,
                                     iter=None, fix_rounds=0, post_cap_passes="", user_ruled=[1],
                                     session_ruled=[])

        pairs = dict(review_launch.header_pairs(options, "", [], pathlib.Path("findings.md")))

        self.assertRegex(pairs["user-ruled-at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual(pairs["user-ruled"], "1")

    def test_session_ruled_numbers_are_written_as_a_header_pair_with_no_ruling_time(self):
        options = argparse.Namespace(fix="findings.md", skill="code", lane="code", no_review=False, fast=False,
                                     iter=None, fix_rounds=0, post_cap_passes="", user_ruled=[],
                                     session_ruled=[2, 3])

        pairs = dict(review_launch.header_pairs(options, "", [], pathlib.Path("findings.md")))

        self.assertEqual(pairs["session-ruled"], "2, 3")
        self.assertNotIn("user-ruled-at", pairs)

    def test_a_launch_with_no_fix_flag_but_findings_to_apply_writes_the_fix_first_mode(self):
        options = argparse.Namespace(fix=None, skill="code", lane="code", no_review=False, fast=False,
                                     iter=None, fix_rounds=0, post_cap_passes="", user_ruled=[],
                                     session_ruled=[])

        with_findings = dict(review_launch.header_pairs(options, "", [], pathlib.Path("findings.json")))
        without_findings = dict(review_launch.header_pairs(options, "", [], None))

        self.assertEqual(with_findings["mode"], "fix-first")
        self.assertEqual(without_findings["mode"], "review-first")

    def test_no_user_ruled_pair_is_written_without_user_ruled_numbers(self):
        options = argparse.Namespace(fix="findings.md", skill="code", lane="code", no_review=False, fast=False,
                                     iter=None, fix_rounds=0, post_cap_passes="", user_ruled=[],
                                     session_ruled=[])

        pairs = dict(review_launch.header_pairs(options, "", [], pathlib.Path("findings.md")))

        self.assertNotIn("user-ruled", pairs)
        self.assertNotIn("user-ruled-at", pairs)


class StopLoopTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.loop_dir = pathlib.Path(temp_dir.name) / "review-script-x"
        self.loop_dir.mkdir()
        self.repo = pathlib.Path(temp_dir.name).resolve()
        self.launch_file = self.loop_dir / reviewer_dispatch.LAUNCH_FILE

    def write_record(self, relaunch_args):
        self.launch_file.write_text(json.dumps({"packet_args": [], "relaunch_args": relaunch_args}) + "\n")

    def stop(self, running_answers, wait_seconds=5):
        with mock.patch.object(review_launch.process_group, "command_line", return_value="loop review-script-x"), \
                mock.patch.object(review_launch.process_group, "terminate_group", return_value=True), \
                mock.patch.object(review_launch.process_group, "pid_is_alive", side_effect=running_answers), \
                mock.patch.object(review_launch, "STOP_WAIT_SECONDS", wait_seconds), \
                mock.patch.object(review_launch, "STOP_POLL_SECONDS", 0.01), \
                contextlib.redirect_stderr(io.StringIO()) as stderr, contextlib.redirect_stdout(io.StringIO()):
            review_launch.stop_loop(self.loop_dir, 4242, self.repo)
        return stderr.getvalue()

    def test_a_stopped_loop_is_waited_for_until_it_exits(self):
        self.write_record(["--repo", str(self.repo)])
        running = mock.Mock(side_effect=[True, True, False])
        errors = self.stop(running)
        self.assertEqual(running.call_count, 3)
        self.assertEqual(errors, "")

    def test_a_loop_that_outlives_the_wait_is_named_on_stderr(self):
        self.write_record(["--repo", str(self.repo)])
        errors = self.stop(itertools.repeat(True), wait_seconds=0.1)
        self.assertIn("pid 4242", errors)

    def test_a_record_with_no_repo_is_a_launch_error_that_stop_reports(self):
        self.write_record(["--lane", "none"])
        with self.assertRaises(review_launch.LaunchError):
            review_launch.loop_repo(self.launch_file)
        with mock.patch.object(review_launch.process_group, "command_line", return_value="loop review-script-x"), \
                contextlib.redirect_stderr(io.StringIO()) as stderr:
            loop = review_launch.live_loop_of(self.loop_dir, 4242, self.repo)
        self.assertIsNone(loop, "a loop whose record cannot be read must not be stopped")
        self.assertIn("names no --repo", stderr.getvalue())

    def test_a_record_that_is_not_a_json_object_is_a_launch_error_from_loop_skill(self):
        self.launch_file.write_text("[]\n")
        with self.assertRaises(review_launch.LaunchError) as raised:
            review_launch.loop_skill(self.launch_file)
        self.assertIn(str(self.launch_file), str(raised.exception))
        self.assertNotIn("--launch", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
