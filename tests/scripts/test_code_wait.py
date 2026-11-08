"""Tests for code_wait.py: the agent wait and the review wait of the /code fork."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import tempfile
import unittest
from unittest import mock

import toolkit_paths

module_spec = importlib.util.spec_from_file_location("code_wait", toolkit_paths.CODE_DIR / "code_wait.py")
code_wait = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(code_wait)

AGENT_ID = "a1817e9d1060d81ea"
REPORT = "Phase 0 is implemented."


def handback_records(report):
    call = {"type": "tool_use", "id": "toolu_1", "name": "SubagentHandback", "input": {"message": report}}
    result = {"type": "tool_result", "tool_use_id": "toolu_1",
              "content": [{"type": "text", "text": '{"success":true,"message":"Report delivered to your caller."}'}]}
    return [{"type": "assistant", "message": {"content": [{"type": "text", "text": "Done."}, call]}},
            {"type": "user", "message": {"content": [result]}}]


def temp_dir(test):
    folder = tempfile.TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    return pathlib.Path(folder.name)


def init_repo(repo):
    subprocess.run(["git", "init", "-q", str(repo)], check=True)


def printed(call, *args):
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        call(*args)
    return output.getvalue()


class WaitAgentTest(unittest.TestCase):
    def setUp(self):
        self.projects = temp_dir(self)
        for name, value in (("PROJECTS", self.projects), ("WAIT_SECONDS", 0)):
            patcher = mock.patch.object(code_wait, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_transcript(self, records, finished=None):
        subagents = self.projects / "proj/session/subagents"
        subagents.mkdir(parents=True)
        transcript = subagents / f"agent-{AGENT_ID}.jsonl"
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        if finished is not None:
            transcript.with_suffix(".meta.json").write_text(json.dumps({"finished": finished}))

    def test_a_delivered_hand_back_prints_its_report(self):
        self.write_transcript(handback_records(REPORT))

        self.assertEqual(printed(code_wait.main, ["code_wait.py", "agent", AGENT_ID]).strip(), REPORT)

    def test_an_agent_still_at_work_says_to_run_again(self):
        self.write_transcript([handback_records(REPORT)[0]], finished=False)

        self.assertEqual(printed(code_wait.main, ["code_wait.py", "agent", AGENT_ID]).strip(), code_wait.STILL_WORKING)

    def test_an_agent_not_yet_written_says_to_run_again(self):
        self.assertEqual(printed(code_wait.main, ["code_wait.py", "agent", AGENT_ID]).strip(), code_wait.STILL_WORKING)

    def test_a_finished_meta_without_a_hand_back_prints_the_last_text(self):
        self.write_transcript([{"type": "assistant", "message": {"content": [{"type": "text", "text": REPORT}]}}],
                              finished=True)

        self.assertEqual(printed(code_wait.main, ["code_wait.py", "agent", AGENT_ID]).strip(), REPORT)

    def test_a_denied_hand_back_is_not_a_finish(self):
        records = handback_records(REPORT)
        records[1]["message"]["content"][0]["is_error"] = True
        self.write_transcript(records)

        self.assertEqual(printed(code_wait.main, ["code_wait.py", "agent", AGENT_ID]).strip(), code_wait.STILL_WORKING)

    def test_a_denied_hand_back_message_is_not_the_report_of_a_finished_agent(self):
        later_text = "The real report."
        records = handback_records("Denied message.")
        records[1]["message"]["content"][0]["is_error"] = True
        records.append({"type": "assistant", "message": {"content": [{"type": "text", "text": later_text}]}})
        self.write_transcript(records, finished=True)

        self.assertEqual(printed(code_wait.main, ["code_wait.py", "agent", AGENT_ID]).strip(), later_text)


class WaitReviewTest(unittest.TestCase):
    def repo_with_pid(self, pid):
        repo = temp_dir(self)
        init_repo(repo)
        phase_dir = repo / ".git/code-phase"
        phase_dir.mkdir()
        (phase_dir / "pid").write_text(str(pid))
        return repo, phase_dir

    def test_a_finished_review_prints_its_output(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        (phase_dir / "review.out").write_text("status: converged\n")

        self.assertEqual(printed(code_wait.wait_review, repo), "status: converged\n\n")

    def test_a_finished_review_with_no_output_file_says_so(self):
        repo, _ = self.repo_with_pid(999999999)

        self.assertEqual(printed(code_wait.wait_review, repo).strip(), "No review output was written.")

    def test_a_running_review_says_to_run_again(self):
        repo, _ = self.repo_with_pid(os.getpid())

        with mock.patch.object(code_wait, "WAIT_SECONDS", 0):
            self.assertEqual(printed(code_wait.wait_review, repo).strip(), code_wait.STILL_WORKING)

    def test_a_linked_worktree_keeps_its_pid_file_in_its_own_git_dir(self):
        main_repo = temp_dir(self)
        init_repo(main_repo)
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com"}
        subprocess.run(["git", "-C", str(main_repo), "commit", "-q", "--allow-empty", "-m", "start"], check=True,
                       env=env)
        linked = temp_dir(self) / "linked"
        subprocess.run(["git", "-C", str(main_repo), "worktree", "add", "-q", str(linked)], check=True)

        phase_dir = code_wait.phase_dir(linked)
        phase_dir.mkdir()
        (phase_dir / "pid").write_text(str(os.getpid()))
        (phase_dir / "review.out").write_text("linked\n")

        self.assertNotEqual(phase_dir, main_repo / ".git" / "code-phase")
        self.assertTrue(code_wait.review_running(linked))
        self.assertFalse((main_repo / ".git" / "code-phase").exists())


class ReviewerRequestTest(unittest.TestCase):
    """The /code fork runs the loop's reviewers: `review` returns at each request, `agent --report-file` answers it."""

    def setUp(self):
        self.repo, self.phase_dir = WaitReviewTest.repo_with_pid(self, os.getpid())
        self.loop_dir = temp_dir(self)
        (self.phase_dir / code_wait.LOOP_DIR_FILE).write_text(f"{self.loop_dir}\n")
        self.entries = code_wait.reviewer_dispatch.write_round(
            self.loop_dir, 1, [("review1-code-reviewer", "code-reviewer", "Review app.py.")])
        self.projects = temp_dir(self)
        for name, value in (("PROJECTS", self.projects), ("WAIT_SECONDS", 0)):
            patcher = mock.patch.object(code_wait, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write_finished_reviewer(self, records):
        subagents = self.projects / "proj/session/subagents"
        subagents.mkdir(parents=True)
        transcript = subagents / f"agent-{AGENT_ID}.jsonl"
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        transcript.with_suffix(".meta.json").write_text(json.dumps({"finished": True}))

    def write_reviewer(self, agent_id, records, finished):
        subagents = self.projects / "proj/session/subagents"
        subagents.mkdir(parents=True, exist_ok=True)
        transcript = subagents / f"agent-{agent_id}.jsonl"
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        transcript.with_suffix(".meta.json").write_text(json.dumps({"finished": finished}))

    def run_main(self, *words):
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors), \
                mock.patch.object(code_wait.pathlib.Path, "cwd", return_value=self.repo):
            code = code_wait.main(["code_wait.py", *words])
        return code, output.getvalue(), errors.getvalue()

    def test_a_running_loop_that_asks_for_a_reviewer_prints_the_dispatch_and_the_review_wait(self):
        lines = printed(code_wait.wait_review, self.repo).splitlines()

        self.assertEqual(lines[0], "ACTION: dispatch-reviewer")
        self.assertIn("agent code-reviewer", lines[1])
        self.assertIn(self.entries[0]["report_file"], lines[1])
        self.assertIn("code_wait.py review <agentId> <report file>", lines[-1])

    def test_an_answered_request_lets_the_review_wait_go_on(self):
        pathlib.Path(self.entries[0]["report_file"]).write_text("## Fix\nNone\n")

        self.assertEqual(printed(code_wait.wait_review, self.repo).strip(), code_wait.STILL_WORKING)

    def test_a_loop_dir_from_before_the_run_named_one_is_no_request(self):
        (self.phase_dir / code_wait.LOOP_DIR_FILE).unlink()

        self.assertEqual(printed(code_wait.wait_review, self.repo).strip(), code_wait.STILL_WORKING)

    def test_a_finished_reviewer_writes_its_report_to_the_report_file(self):
        review = "## Fix\nNone\n\nOverall Assessment: PASS\n"
        self.write_finished_reviewer([{"type": "assistant", "message": {"content": [{"type": "text",
                                                                                     "text": review}]}}])
        report_file = self.entries[0]["report_file"]

        code, output, _ = self.run_main("review", AGENT_ID, report_file)

        self.assertEqual((code, output.strip()), (0, code_wait.STILL_WORKING))
        self.assertEqual(pathlib.Path(report_file).read_text(), review)
        self.assertEqual(code_wait.open_reviewer_requests(code_wait.phase_review(self.repo)), [])

    def test_a_named_reviewer_still_at_work_is_no_new_request(self):
        self.write_reviewer(AGENT_ID, [], finished=False)

        code, output, _ = self.run_main("review", AGENT_ID, self.entries[0]["report_file"])

        self.assertEqual((code, output.strip()), (0, code_wait.STILL_WORKING))

    def test_each_finished_reviewer_writes_its_report_while_a_slow_one_works(self):
        entries = code_wait.reviewer_dispatch.write_round(
            self.loop_dir, 2, [("review2-code-reviewer", "code-reviewer", "Review app.py."),
                               ("review2-test-reviewer", "test-reviewer", "Review the tests.")])
        slow_id = "a" + "1" * 16
        self.write_reviewer(AGENT_ID, [{"type": "assistant", "message": {"content": [{"type": "text",
                                                                                      "text": "fast"}]}}], True)
        self.write_reviewer(slow_id, [], finished=False)
        pathlib.Path(self.entries[0]["report_file"]).write_text("round one\n")

        code, output, _ = self.run_main("review", AGENT_ID, entries[0]["report_file"], slow_id,
                                        entries[1]["report_file"])

        self.assertEqual((code, output.strip()), (0, code_wait.STILL_WORKING))
        self.assertEqual(pathlib.Path(entries[0]["report_file"]).read_text(), "fast")
        self.assertFalse(pathlib.Path(entries[1]["report_file"]).exists())

    def test_a_reviewer_with_no_report_writes_nothing_and_exits_one(self):
        self.write_finished_reviewer([{"type": "assistant", "message": {"content": []}}])
        report_file = self.entries[0]["report_file"]

        code, output, _ = self.run_main("review", AGENT_ID, report_file)

        self.assertEqual(code, 1)
        self.assertIn(code_wait.NO_REPORT, output)
        self.assertIn(AGENT_ID, output)
        self.assertFalse(pathlib.Path(report_file).exists())

    def test_ids_joined_into_one_word_stop_loudly(self):
        # zsh does not split an unquoted $VAR, so a string of pairs arrives as one argument.
        joined = f"{AGENT_ID} {self.entries[0]['report_file']}"

        code, _, errors = self.run_main("review", joined, self.entries[0]["report_file"])

        self.assertEqual(code, 2)
        self.assertIn("is not an agent id", errors)

    def test_an_odd_word_count_stops_loudly(self):
        code, _, errors = self.run_main("review", AGENT_ID)

        self.assertEqual(code, 2)
        self.assertIn("pairs", errors)

    def test_a_report_file_no_request_names_stops_loudly(self):
        code, _, errors = self.run_main("review", AGENT_ID, str(self.loop_dir / "other.report.md"))

        self.assertEqual(code, 2)
        self.assertIn("no report file", errors)

    def test_a_bad_agent_id_for_agent_stops_loudly(self):
        code, _, errors = self.run_main("agent", f"{AGENT_ID} --report-file x")

        self.assertEqual(code, 2)
        self.assertIn("is not an agent id", errors)

    def test_a_launched_loop_that_asks_for_a_reviewer_names_its_folder_in_the_next_wait(self):
        (self.loop_dir / code_wait.reviewer_dispatch.PID_FILE).write_text(f"{os.getpid()}\n")

        code, output, _ = self.run_main("review", "--loop", str(self.loop_dir))

        lines = output.splitlines()
        self.assertEqual((code, lines[0]), (0, "ACTION: dispatch-reviewer"))
        self.assertIn(self.entries[0]["report_file"], lines[1])
        self.assertIn(f"code_wait.py review --loop {self.loop_dir} <agentId> <report file>", lines[-1])

    def test_a_launched_loop_writes_a_finished_reviewer_s_report(self):
        (self.loop_dir / code_wait.reviewer_dispatch.PID_FILE).write_text(f"{os.getpid()}\n")
        self.write_finished_reviewer([{"type": "assistant", "message": {"content": [{"type": "text",
                                                                                     "text": "PASS"}]}}])
        report_file = self.entries[0]["report_file"]

        code, output, _ = self.run_main("review", "--loop", str(self.loop_dir), AGENT_ID, report_file)

        self.assertEqual((code, output.strip()), (0, code_wait.STILL_WORKING))
        self.assertEqual(pathlib.Path(report_file).read_text(), "PASS")

    def test_an_ended_launched_loop_prints_the_packet_command(self):
        (self.loop_dir / code_wait.reviewer_dispatch.PID_FILE).write_text("999999999\n")
        (self.loop_dir / code_wait.reviewer_dispatch.LAUNCH_FILE).write_text(
            json.dumps({"packet_args": ["--skill", "fix", "--lane", "code"]}))
        pathlib.Path(self.entries[0]["report_file"]).write_text("PASS\n")

        code, output, _ = self.run_main("review", "--loop", str(self.loop_dir))

        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), "The review loop script finished. Run "
                         "`python3 ~/.claude/scripts/review/review_fix.py packet --skill fix --lane code` now.")

    def test_a_loop_folder_with_no_pid_stops_loudly(self):
        code, _, errors = self.run_main("review", "--loop", str(self.loop_dir))

        self.assertEqual(code, 2)
        self.assertIn("launch --detach", errors)

    def test_a_loop_flag_with_no_folder_stops_loudly(self):
        code, _, errors = self.run_main("review", "--loop")

        self.assertEqual(code, 2)
        self.assertIn("--loop needs the loop folder", errors)

    def test_every_wait_ends_before_the_harness_backgrounds_the_call(self):
        self.assertLess(code_wait.WAIT_SECONDS + code_wait.POLL_SECONDS, 180)


if __name__ == "__main__":
    unittest.main()
