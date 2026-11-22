"""Checks for waiting_review_launch.py, the SessionStart hook that reminds the main session of a review loop that
waits on its reviewers.

Set WAITING_REVIEW_LAUNCH_SCRIPT to run against another copy of the script."""
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.GATES_DIR))
import waiting_review_launch

SCRIPT = pathlib.Path(os.environ.get("WAITING_REVIEW_LAUNCH_SCRIPT")
                      or toolkit_paths.GATES_DIR / "waiting_review_launch.py")
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


class WaitingReviewLaunchTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name) / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        self.loop_dir = self.repo / ".git" / "review-script" / "loop-script" / "review-script-1"
        self.loop_dir.mkdir(parents=True)
        self.report_file = self.loop_dir / "reviewer-requests" / "code-reviewer.report.md"

    def write_round(self, pid, loop_dir=None):
        loop_dir = loop_dir or self.loop_dir
        requests = loop_dir / "reviewer-requests"
        requests.mkdir(parents=True)
        report_file = requests / "code-reviewer.report.md"
        manifest = {"round": 1, "requests": [{"role": "code-reviewer", "agent": "code-reviewer",
                                              "prompt_file": str(requests / "code-reviewer.prompt.md"),
                                              "report_file": str(report_file)}]}
        (requests / "round-1.json").write_text(json.dumps(manifest))
        (loop_dir / "loop.pid").write_text(f"{pid}\n")

    def write_launch(self, loop_dir=None, **record):
        loop_dir = loop_dir or self.loop_dir
        (loop_dir / "launch.json").write_text(json.dumps(record))

    def current_branch(self):
        return subprocess.run(["git", "-C", str(self.repo), "branch", "--show-current"], capture_output=True,
                              text=True, check=True).stdout.strip()

    def run_hook(self, **fields):
        return self.run_hook_process(**fields).stdout

    def run_hook_process(self, **fields):
        event = json.loads((FIXTURES / "hook_event_session_start_main.json").read_text())
        event.update({"cwd": str(self.repo), "source": "compact"}, **fields)
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(event), capture_output=True,
                                  text=True, timeout=30, check=False)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished

    def test_a_running_loop_with_an_unwritten_report_prints_its_dispatch_lines(self):
        self.write_round(os.getpid())
        document = json.loads(self.run_hook())
        context = document["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(document["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("ACTION: dispatch-reviewer", context)
        self.assertIn(waiting_review_launch.HEADER, context)
        self.assertIn(f"report {self.report_file}", context)
        self.assertIn(f"reviewer_dispatch.py wait {self.loop_dir}", context)

    def test_a_loop_of_another_branch_prints_no_action_but_names_its_age_and_branch(self):
        self.write_round(os.getpid())
        week_ago = time.time() - 7 * 86400
        self.write_launch(branch="other-branch", launched_at=week_ago)
        context = json.loads(self.run_hook())["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("ACTION", context)
        self.assertNotIn(waiting_review_launch.HEADER, context)
        self.assertIn("7d old, branch other-branch", context)

    def test_a_loop_of_this_branch_launched_long_ago_keeps_its_action_and_shows_its_age_and_branch(self):
        self.write_round(os.getpid())
        self.write_launch(branch=self.current_branch(), launched_at=time.time() - 3 * 3600)
        for source in ("compact", "resume"):
            with self.subTest(source):
                context = json.loads(self.run_hook(source=source))["hookSpecificOutput"]["additionalContext"]
                self.assertIn("ACTION: dispatch-reviewer", context)
                self.assertIn(f"3h old, branch {self.current_branch()}", context)

    def test_a_loop_detached_for_a_code_fork_prints_no_action(self):
        self.write_round(os.getpid())
        self.write_launch(branch=self.current_branch(), launched_at=time.time(), detach=True)
        context = json.loads(self.run_hook())["hookSpecificOutput"]["additionalContext"]
        self.assertNotIn("ACTION", context)
        self.assertNotIn(waiting_review_launch.HEADER, context)
        self.assertIn("code_wait.py review", context)

    def test_one_loop_to_dispatch_and_one_left_out_print_both_under_the_header(self):
        self.write_round(os.getpid())
        self.write_launch(branch=self.current_branch(), launched_at=time.time())
        other_loop = self.loop_dir.parent / "review-script-2"
        self.write_round(os.getpid(), other_loop)
        self.write_launch(other_loop, branch="other-branch", launched_at=time.time())
        context = json.loads(self.run_hook())["hookSpecificOutput"]["additionalContext"]
        self.assertIn("ACTION: dispatch-reviewer", context)
        self.assertIn(waiting_review_launch.HEADER, context)
        self.assertIn("Left out: loop review-script-2", context)

    def test_a_bad_launch_record_warns_on_stderr_and_prints_no_context(self):
        self.write_round(os.getpid())
        self.write_launch(branch=self.current_branch(), launched_at="x")
        finished = self.run_hook_process()
        self.assertEqual(finished.stdout, "")
        self.assertIn("no reminder", finished.stderr)

    def test_an_os_error_while_reading_a_loop_warns_on_stderr_and_prints_no_context(self):
        event = json.dumps({"cwd": str(self.repo), "session_id": "s"}).encode()
        stdin = io.TextIOWrapper(io.BytesIO(event))
        stdout = io.StringIO()
        stderr = io.TextIOWrapper(io.BytesIO(), write_through=True)
        with unittest.mock.patch.object(sys, "stdin", stdin), \
                unittest.mock.patch.object(sys, "stdout", stdout), \
                unittest.mock.patch.object(sys, "stderr", stderr), \
                unittest.mock.patch.object(waiting_review_launch.reviewer_dispatch, "waiting_launch_lines",
                                           side_effect=OSError("loop.pid vanished")):
            code = waiting_review_launch.main()
        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("no reminder", stderr.buffer.getvalue().decode())

    def test_a_written_report_an_ended_loop_or_an_agent_seat_prints_nothing(self):
        self.write_round(os.getpid())
        self.assertNotEqual(self.run_hook(), "")
        self.assertEqual(self.run_hook(agent_type="code-reviewer"), "")
        self.report_file.write_text("no findings\n")
        self.assertEqual(self.run_hook(), "")
        self.report_file.unlink()
        (self.loop_dir / "loop.pid").write_text("999999999\n")
        self.assertEqual(self.run_hook(), "")


if __name__ == "__main__":
    unittest.main()
