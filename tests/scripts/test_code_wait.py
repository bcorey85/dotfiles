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


if __name__ == "__main__":
    unittest.main()
