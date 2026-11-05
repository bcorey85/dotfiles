"""Checks for waiting_review_launch.py, the SessionStart hook that reminds the main session of a review loop that
waits on its reviewers.

Set WAITING_REVIEW_LAUNCH_SCRIPT to run against another copy of the script."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

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

    def write_round(self, pid):
        requests = self.loop_dir / "reviewer-requests"
        requests.mkdir()
        manifest = {"round": 1, "requests": [{"role": "code-reviewer", "agent": "code-reviewer",
                                              "prompt_file": str(requests / "code-reviewer.prompt.md"),
                                              "report_file": str(self.report_file)}]}
        (requests / "round-1.json").write_text(json.dumps(manifest))
        (self.loop_dir / "loop.pid").write_text(f"{pid}\n")

    def run_hook(self, **fields):
        event = json.loads((FIXTURES / "hook_event_session_start_main.json").read_text())
        event.update({"cwd": str(self.repo), "source": "compact"}, **fields)
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(event), capture_output=True,
                                  text=True, timeout=30, check=False)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout

    def test_a_running_loop_with_an_unwritten_report_prints_its_dispatch_lines(self):
        self.write_round(os.getpid())
        document = json.loads(self.run_hook())
        context = document["hookSpecificOutput"]["additionalContext"]
        self.assertEqual(document["hookSpecificOutput"]["hookEventName"], "SessionStart")
        self.assertIn("ACTION: dispatch-reviewer", context)
        self.assertIn(f"report {self.report_file}", context)
        self.assertIn(f"reviewer_dispatch.py wait {self.loop_dir}", context)

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
