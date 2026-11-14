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

    def launch(self, *flags, repo=None, env_overrides=None):
        repo = repo or self.repo
        (repo / "README.md").write_text(f"hi, edited {time.monotonic()}\n")
        environment = {**os.environ, **GIT_ENV, **self.ledger_env, "CLAUDE_CODE_SESSION_ID": SESSION,
                       "HANDBACK_STORE_DIR": str(self.temp_root / "store"),
                       "REVIEW_FIX_LOOP_SCRIPT": str(self.loop_stub), "CLAUDE_TOOLKIT_TELEMETRY": "1",
                       **(env_overrides or {})}
        done = subprocess.run([sys.executable, "-I", str(SCRIPT), "launch", "--detach", *flags], cwd=repo,
                              text=True, capture_output=True, env=environment, check=False)
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

    def plant_loop(self, repo, agent_id, record_repo, command_names_agent=True):
        loop_dir = repo / ".git" / "review-script" / reviewer_dispatch.LOOP_FOLDER / agent_id
        loop_dir.mkdir(parents=True)
        marker = agent_id if command_names_agent else "unrelated"
        process = subprocess.Popen([sys.executable, str(self.loop_stub), marker], start_new_session=True)
        self.addCleanup(process.wait)
        self.addCleanup(process.kill)
        (loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{process.pid}\n")
        record = {"packet_args": [], "relaunch_args": ["--repo", str(record_repo)]}
        (loop_dir / reviewer_dispatch.LAUNCH_FILE).write_text(json.dumps(record) + "\n")
        return loop_dir


class UserRuledHeaderTest(unittest.TestCase):
    def test_the_user_ruled_time_is_the_plan_ruling_form_the_deviation_entry_takes(self):
        options = argparse.Namespace(fix="findings.md", skill="code", lane="code", no_review=False, fast=False,
                                     iter=None, user_ruled=[1])

        pairs = dict(review_launch.header_pairs(options, "", [], pathlib.Path("findings.md")))

        self.assertRegex(pairs["user-ruled-at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual(pairs["user-ruled"], "1")

    def test_no_user_ruled_pair_is_written_without_user_ruled_numbers(self):
        options = argparse.Namespace(fix="findings.md", skill="code", lane="code", no_review=False, fast=False,
                                     iter=None, user_ruled=[])

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
                mock.patch.object(review_launch.reviewer_dispatch, "pid_is_running", side_effect=running_answers), \
                mock.patch.object(review_launch, "STOP_WAIT_SECONDS", wait_seconds), \
                mock.patch.object(review_launch, "STOP_POLL_SECONDS", 0.01), \
                contextlib.redirect_stderr(io.StringIO()) as stderr, contextlib.redirect_stdout(io.StringIO()):
            review_launch.stop_loop_if_live(self.loop_dir, 4242, self.repo)
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
        errors = self.stop([])
        self.assertIn("names no --repo", errors)


if __name__ == "__main__":
    unittest.main()
