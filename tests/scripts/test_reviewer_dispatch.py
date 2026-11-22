"""Checks for reviewer_dispatch.py, the hand-off of a review round to the main session.

Set REVIEWER_DISPATCH_SCRIPT to run the CLI checks against another copy."""
import json
import os
import pathlib
import shutil
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

    def test_two_requests_for_one_role_get_their_own_files_and_both_reports_return(self):
        split = [("review1-code-reviewer", "code-reviewer", "review half one"),
                 ("review1-code-reviewer", "code-reviewer", "review half two")]
        entries = reviewer_dispatch.write_round(self.loop_dir, 1, split)
        self.assertEqual(len({entry["report_file"] for entry in entries}), 2)
        self.assertEqual([pathlib.Path(entry["prompt_file"]).read_text() for entry in entries],
                         ["review half one", "review half two"])
        for entry, text in zip(entries, ("one ok", "two ok"), strict=True):
            pathlib.Path(entry["report_file"]).write_text(text)
        replies = reviewer_dispatch.request_round(self.loop_dir, 1, split, timeout=5, poll=0.01)
        self.assertEqual([text for text, _wall in replies], ["one ok", "two ok"])

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
        request = f"- agent code-reviewer; prompt \"Read {entries[0]['prompt_file']} whole and do that task.\"; "
        self.assertIn(f"{request}report {entries[0]['report_file']} {reviewer_dispatch.SESSION_WRITES_NOTE}", lines)
        self.assertIn("main session", lines[1])
        self.assertIn(f"wait {self.loop_dir}", lines[-1])
        self.assertNotIn("code_wait.py review", output)

    def test_the_line_gives_the_exact_prompt_and_the_note_it_was_given(self):
        entries = reviewer_dispatch.write_round(self.loop_dir, 1, REQUESTS)
        note = "(a note the caller chose)"
        line = reviewer_dispatch.request_lines(entries, note)[1]
        self.assertIn(f'prompt "Read {entries[0]["prompt_file"]} whole and do that task."', line)
        self.assertIn(note, line)

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

    def test_wait_gives_no_dispatch_order_for_an_open_request_of_a_dead_loop(self):
        entries = reviewer_dispatch.write_round(self.loop_dir, 1, REQUESTS)
        ended = subprocess.Popen([sys.executable, "-c", "pass"])
        ended.wait()
        (self.loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{ended.pid}\n")
        code, output = self.run_wait()
        self.assertEqual(code, 0, output)
        for entry in entries:
            self.assertIn(f"report {entry['report_file']}", output)
            self.assertNotIn(entry["prompt_file"], output)
            self.assertNotIn(reviewer_dispatch.AGENT_PROMPT.format(prompt_file=entry["prompt_file"]), output)
        self.assertNotIn("ACTION: dispatch-reviewer", output)
        self.assertNotIn(f"wait {self.loop_dir}", output)
        lines = output.splitlines()
        self.assertEqual(lines[0], reviewer_dispatch.LOOP_GONE)
        self.assertEqual(lines[-1], f"Run `{reviewer_dispatch.packet_command(self.loop_dir)}` now.")

    def test_wait_for_a_dead_loop_with_a_crashed_packet_still_prints_heading_and_packet_command(self):
        entries = reviewer_dispatch.write_round(self.loop_dir, 1, REQUESTS)
        (self.loop_dir / reviewer_dispatch.PACKET_FILE).write_text("status: crashed\n")
        ended = subprocess.Popen([sys.executable, "-c", "pass"])
        ended.wait()
        (self.loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{ended.pid}\n")
        code, output = self.run_wait()
        self.assertEqual(code, 0, output)
        lines = output.splitlines()
        self.assertEqual(lines[0], reviewer_dispatch.LOOP_GONE)
        self.assertIn(f"report {entries[0]['report_file']}", output)
        self.assertEqual(lines[-1], f"Run `{reviewer_dispatch.packet_command(self.loop_dir)}` now.")

    def test_wait_names_the_model_of_a_round_that_has_one(self):
        entries = reviewer_dispatch.write_round(self.loop_dir, 1, REQUESTS, model="haiku")
        (self.loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{os.getpid()}\n")
        code, output = self.run_wait()
        self.assertEqual(code, 0, output)
        self.assertIn(f"- agent code-reviewer; prompt \"Read {entries[0]['prompt_file']} whole and do that task.\"; "
                      f"model haiku; report {entries[0]['report_file']} {reviewer_dispatch.SESSION_WRITES_NOTE}",
                      output.splitlines())

    def test_wait_prints_the_packet_arguments_the_launch_saved(self):
        self.loop_dir.mkdir(parents=True)
        launch_record = {"packet_args": ["--skill", "fix", "--scope", "branch-exit", "--lane", "code"]}
        (self.loop_dir / reviewer_dispatch.LAUNCH_FILE).write_text(json.dumps(launch_record))
        ended = subprocess.Popen([sys.executable, "-c", "pass"])
        ended.wait()
        (self.loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{ended.pid}\n")
        code, output = self.run_wait()
        self.assertEqual(code, 0, output)
        self.assertIn("review_fix.py packet --skill fix --scope branch-exit --lane code`", output)

    def waiting_loop_repo(self, **launch):
        """A git repo whose one live loop waits on a report; `launch` is that loop's launch record."""
        repo = self.loop_dir.parent / "repo"
        subprocess.run(["git", "init", "-q", "-b", "this-branch", str(repo)], check=True)
        loop_dir = repo / ".git" / reviewer_dispatch.LAUNCH_STATE_NAME / reviewer_dispatch.LOOP_FOLDER / "loop-1"
        reviewer_dispatch.write_round(loop_dir, 1, REQUESTS[:1])
        (loop_dir / reviewer_dispatch.PID_FILE).write_text(f"{os.getpid()}\n")
        (loop_dir / reviewer_dispatch.LAUNCH_FILE).write_text(json.dumps(launch))
        return repo

    def test_a_waiting_loop_of_this_branch_gets_dispatch_lines_with_age_and_branch(self):
        now = time.time()
        repo = self.waiting_loop_repo(branch="this-branch", launched_at=now - 7200)
        notice = reviewer_dispatch.waiting_launch_lines(repo, now=now)
        self.assertEqual(notice.left_out, [])
        self.assertIn("ACTION: dispatch-reviewer", notice.dispatch)
        self.assertIn("Loop loop-1 (2h old, branch this-branch):", notice.dispatch)

    def test_a_waiting_loop_of_another_branch_or_detached_is_named_with_no_action(self):
        now = time.time()
        cases = {
            "another branch": ({"branch": "other", "launched_at": now - 7 * 86400}, "7d old, branch other",
                               "belongs to branch other"),
            "detached": ({"branch": "this-branch", "launched_at": now, "detach": True},
                         "under 1m old, branch this-branch", "launched detached for a code fork"),
        }
        for name, (launch, facts, reason) in cases.items():
            with self.subTest(name):
                repo = self.waiting_loop_repo(**launch)
                notice = reviewer_dispatch.waiting_launch_lines(repo, now)
                self.assertEqual(notice.dispatch, [])
                self.assertEqual(len(notice.left_out), 1)
                self.assertIn(facts, notice.left_out[0])
                self.assertIn(reason, notice.left_out[0])
                self.assertNotIn("ACTION", notice.left_out[0])
                shutil.rmtree(repo)

    def test_a_record_with_no_branch_is_dispatched_as_branch_unknown(self):
        now = time.time()
        repo = self.waiting_loop_repo(launched_at=now - 60)
        notice = reviewer_dispatch.waiting_launch_lines(repo, now=now)
        self.assertEqual(notice.left_out, [])
        self.assertIn("Loop loop-1 (1m old, branch unknown):", notice.dispatch)

    def test_a_record_saved_from_a_detached_head_is_dispatched_as_detached_head(self):
        now = time.time()
        repo = self.waiting_loop_repo(branch="", launched_at=now - 60)
        notice = reviewer_dispatch.waiting_launch_lines(repo, now=now)
        self.assertEqual(notice.left_out, [])
        self.assertIn("Loop loop-1 (1m old, branch detached HEAD):", notice.dispatch)

    def test_a_detached_head_is_dispatched_for_a_loop_with_a_branch(self):
        now = time.time()
        repo = self.waiting_loop_repo(branch="this-branch", launched_at=now - 60)
        subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                        "--allow-empty", "-m", "x"], check=True)
        subprocess.run(["git", "-C", str(repo), "checkout", "-q", "--detach"], check=True)
        notice = reviewer_dispatch.waiting_launch_lines(repo, now=now)
        self.assertEqual(notice.left_out, [])
        self.assertIn("ACTION: dispatch-reviewer", notice.dispatch)

    def test_a_record_with_no_launch_time_reads_its_age_from_the_pid_file(self):
        now = time.time()
        repo = self.waiting_loop_repo(branch="this-branch")
        loop_dir = repo / ".git" / reviewer_dispatch.LAUNCH_STATE_NAME / reviewer_dispatch.LOOP_FOLDER / "loop-1"
        pid_file = loop_dir / reviewer_dispatch.PID_FILE
        os.utime(pid_file, (now - 7200, now - 7200))
        notice = reviewer_dispatch.waiting_launch_lines(repo, now=now)
        self.assertEqual(notice.left_out, [])
        self.assertIn("Loop loop-1 (2h old, branch this-branch):", notice.dispatch)

    def test_a_launch_time_that_is_not_a_number_stops_loudly(self):
        for bad in ("x", True, [1]):
            with self.subTest(bad=bad):
                repo = self.waiting_loop_repo(branch="this-branch", launched_at=bad)
                with self.assertRaises(reviewer_dispatch.ManifestError):
                    reviewer_dispatch.waiting_launch_lines(repo, time.time())
                shutil.rmtree(repo)

    def test_a_branch_or_detach_value_of_the_wrong_type_stops_loudly(self):
        for name, launch in {"detach text": {"detach": "false"}, "branch number": {"branch": 5}}.items():
            with self.subTest(name):
                repo = self.waiting_loop_repo(launched_at=time.time(), **launch)
                with self.assertRaises(reviewer_dispatch.ManifestError):
                    reviewer_dispatch.waiting_launch_lines(repo, time.time())
                shutil.rmtree(repo)

    def test_a_launch_file_that_is_not_a_json_object_stops_loudly(self):
        self.loop_dir.mkdir(parents=True)
        launch_file = self.loop_dir / reviewer_dispatch.LAUNCH_FILE
        for text in ("[]", "5", "not json"):
            with self.subTest(text=text):
                launch_file.write_text(text)
                with self.assertRaisesRegex(reviewer_dispatch.ManifestError, "expected a launch record"):
                    reviewer_dispatch.read_launch_file(launch_file)
                with self.assertRaises(reviewer_dispatch.ManifestError):
                    reviewer_dispatch.read_launch_record(launch_file, "k", default=None)
                with self.assertRaises(reviewer_dispatch.ManifestError):
                    reviewer_dispatch.loop_launch(self.loop_dir)

    def test_a_launch_file_not_in_the_form_stops_loudly(self):
        self.loop_dir.mkdir(parents=True)
        (self.loop_dir / reviewer_dispatch.LAUNCH_FILE).write_text(json.dumps({"args": []}))
        with self.assertRaises(reviewer_dispatch.ManifestError):
            reviewer_dispatch.packet_command(self.loop_dir)

    def test_packet_args_that_are_not_a_list_of_strings_stop_loudly(self):
        self.loop_dir.mkdir(parents=True)
        for name, bad in {"text": "--skill review", "number": 5, "mixed list": ["--skill", 3]}.items():
            with self.subTest(name):
                launch_file = self.loop_dir / reviewer_dispatch.LAUNCH_FILE
                launch_file.write_text(json.dumps({reviewer_dispatch.PACKET_ARGS_KEY: bad}))
                with self.assertRaises(reviewer_dispatch.ManifestError):
                    reviewer_dispatch.packet_command(self.loop_dir)
                with self.assertRaises(reviewer_dispatch.ManifestError):
                    reviewer_dispatch.read_string_list(launch_file, reviewer_dispatch.PACKET_ARGS_KEY, default=[])

    def test_the_packet_command_names_the_plan_the_loop_prompt_header_gives(self):
        self.loop_dir.mkdir(parents=True)
        prompt = "lane: code\nrepo: /work/repo\nplan: docs/plans/x/plan.md\nphase: 2\n\nhandoff\n"
        (self.loop_dir / reviewer_dispatch.PROMPT_FILE).write_text(prompt)

        command = reviewer_dispatch.packet_command(self.loop_dir)

        self.assertEqual(command, f"{reviewer_dispatch.PACKET_COMMAND} --skill review "
                                  "--plan /work/repo/docs/plans/x/plan.md")

    def test_the_packet_command_adds_no_plan_for_a_prompt_header_without_one(self):
        self.loop_dir.mkdir(parents=True)
        (self.loop_dir / reviewer_dispatch.PROMPT_FILE).write_text("lane: code\nrepo: /work/repo\n\nhandoff\n")

        command = reviewer_dispatch.packet_command(self.loop_dir)

        self.assertEqual(command, f"{reviewer_dispatch.PACKET_COMMAND} --skill review")

    def test_a_prompt_file_not_in_the_form_stops_loudly(self):
        self.loop_dir.mkdir(parents=True)
        (self.loop_dir / reviewer_dispatch.PROMPT_FILE).write_text("repo: /work/repo\n\nhandoff\n")
        with self.assertRaises(reviewer_dispatch.ManifestError):
            reviewer_dispatch.packet_command(self.loop_dir)

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
