"""Checks for reviewer_dispatch.py, the hand-off of a review round to the main session.

Set REVIEWER_DISPATCH_SCRIPT to run the CLI checks against another copy."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import reviewer_dispatch

SCRIPT = pathlib.Path(os.environ.get("REVIEWER_DISPATCH_SCRIPT")
                      or toolkit_paths.REVIEW_DIR / "reviewer_dispatch.py")
REQUESTS = [("review1-code-reviewer", "code-reviewer", "review the diff"),
            ("review1-test-reviewer", "test-reviewer", "review the tests")]


class ReviewerDispatchTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.loop_dir = pathlib.Path(scratch.name) / "loop"

    def manifest(self, round_number=1):
        return self.loop_dir / reviewer_dispatch.REQUESTS_FOLDER / f"round-{round_number}.json"

    def run_wait(self, *, timeout=30):
        done = subprocess.run([sys.executable, "-I", str(SCRIPT), "wait", str(self.loop_dir)], capture_output=True,
                              text=True, timeout=timeout)
        return done.returncode, done.stdout + done.stderr

    def test_a_round_writes_prompts_and_manifest_and_returns_the_reports_in_order(self):
        def main_session():
            while not self.manifest().is_file():
                time.sleep(0.01)
            requests = json.loads(self.manifest().read_text())["requests"]
            for request, text in zip(reversed(requests), ("tests ok", "code ok"), strict=True):
                pathlib.Path(request["report_file"]).write_text(text)

        helper = threading.Thread(target=main_session)
        helper.start()
        replies = reviewer_dispatch.request_round(self.loop_dir, 1, REQUESTS, timeout=30, poll=0.01)
        helper.join()

        self.assertEqual([text for text, _wall in replies], ["code ok", "tests ok"])
        manifest = json.loads(self.manifest().read_text())
        self.assertEqual(manifest["round"], 1)
        self.assertEqual([(entry["role"], entry["agent"]) for entry in manifest["requests"]],
                         [(role, agent) for role, agent, _prompt in REQUESTS])
        self.assertEqual(pathlib.Path(manifest["requests"][0]["prompt_file"]).read_text(), "review the diff")

    def test_a_round_with_no_report_in_time_raises_naming_the_missing_report(self):
        with self.assertRaisesRegex(RuntimeError, "review1-test-reviewer.report.md"):
            reviewer_dispatch.request_round(self.loop_dir, 1, REQUESTS, timeout=0.05, poll=0.01)

    def test_an_empty_report_is_still_pending(self):
        entries = reviewer_dispatch.write_round(self.loop_dir, 1, REQUESTS)
        pathlib.Path(entries[0]["report_file"]).write_text("  \n")
        pathlib.Path(entries[1]["report_file"]).write_text("done")
        pending = reviewer_dispatch.pending_requests(self.loop_dir)
        self.assertEqual([entry["role"] for entry in pending], ["review1-code-reviewer"])

    def test_wait_prints_the_dispatch_lines_for_an_open_round(self):
        entries = reviewer_dispatch.write_round(self.loop_dir, 1, REQUESTS)
        (self.loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{os.getpid()}\n")
        code, output = self.run_wait()
        self.assertEqual(code, 0, output)
        lines = output.splitlines()
        self.assertEqual(lines[0], "ACTION: dispatch-reviewer")
        self.assertIn(f"- agent code-reviewer; prompt {entries[0]['prompt_file']}; "
                      f"report {entries[0]['report_file']}", lines)
        self.assertIn(f"wait {self.loop_dir}", lines[-1])

    def test_wait_reports_the_finish_once_the_loop_process_has_ended(self):
        entries = reviewer_dispatch.write_round(self.loop_dir, 1, REQUESTS)
        for entry in entries:
            pathlib.Path(entry["report_file"]).write_text("done")
        ended = subprocess.Popen([sys.executable, "-c", "pass"])
        ended.wait()
        (self.loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{ended.pid}\n")
        code, output = self.run_wait()
        self.assertEqual(code, 0, output)
        self.assertIn("finished", output)
        self.assertIn("packet --skill review", output)

    def test_wait_with_no_pid_file_stops_loudly(self):
        self.loop_dir.mkdir(parents=True)
        code, output = self.run_wait()
        self.assertEqual(code, 2, output)
        self.assertIn(reviewer_dispatch.PID_FILE, output)

    def test_a_manifest_not_in_the_form_stops_loudly(self):
        self.manifest().parent.mkdir(parents=True)
        self.manifest().write_text(json.dumps({"round": 1}))
        (self.loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{os.getpid()}\n")
        code, output = self.run_wait()
        self.assertEqual(code, 2, output)
        self.assertIn("no \"requests\" list", output)


if __name__ == "__main__":
    unittest.main()
