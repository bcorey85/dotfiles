"""Tests for code_wait.py: the agent wait and the review wait of the /code fork."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import tempfile
import threading
import unittest
from unittest import mock

import toolkit_paths

module_spec = importlib.util.spec_from_file_location("code_wait", toolkit_paths.CODE_DIR / "code_wait.py")
code_wait = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(code_wait)

AGENT_ID = "a1817e9d1060d81ea"
REPORT = "Phase 0 is implemented."
STORE_SESSION = "sess-store"


def handback_records(report, call_id="toolu_1"):
    call = {"type": "tool_use", "id": call_id, "name": "SubagentHandback", "input": {"message": report}}
    result = {"type": "tool_result", "tool_use_id": call_id,
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


def patch_projects_and_waits(test):
    """Points the transcript folder at `test.projects` and zeroes the waits for the test's lifetime."""
    patchers = [mock.patch.object(code_wait.session_registry, "projects_dir", return_value=test.projects),
                mock.patch.object(code_wait, "WAIT_SECONDS", 0),
                mock.patch.object(code_wait, "SETTLE_SECONDS", 0)]
    for patcher in patchers:
        patcher.start()
        test.addCleanup(patcher.stop)


class WaitAgentTest(unittest.TestCase):
    def setUp(self):
        self.projects = temp_dir(self)
        patch_projects_and_waits(self)
        reports_patcher = mock.patch.object(code_wait, "AGENT_REPORTS_DIR", temp_dir(self) / "agent-reports")
        reports_patcher.start()
        self.addCleanup(reports_patcher.stop)
        self.repo = temp_dir(self)
        init_repo(self.repo)
        cwd_patcher = mock.patch.object(code_wait.pathlib.Path, "cwd", return_value=self.repo)
        cwd_patcher.start()
        self.addCleanup(cwd_patcher.stop)

    def write_transcript(self, records, finished=None):
        subagents = self.projects / "proj/session/subagents"
        subagents.mkdir(parents=True)
        transcript = subagents / f"agent-{AGENT_ID}.jsonl"
        transcript.write_text("".join(json.dumps(record) + "\n" for record in records))
        if finished is not None:
            transcript.with_suffix(".meta.json").write_text(json.dumps({"finished": finished}))

    def append_records(self, records):
        transcript = self.projects / f"proj/session/subagents/agent-{AGENT_ID}.jsonl"
        with transcript.open("a") as handle:
            handle.write("".join(json.dumps(record) + "\n" for record in records))

    def wait(self):
        return printed(code_wait.main, ["code_wait.py", "agent", AGENT_ID])

    def test_a_second_wait_does_not_print_the_report_an_earlier_wait_printed(self):
        self.write_transcript(handback_records(REPORT))

        first = self.wait()
        second = self.wait()

        self.assertEqual(first.strip(), REPORT)
        lines = second.strip().splitlines()
        self.assertEqual(lines[0], code_wait.STILL_WORKING)
        self.assertNotIn(REPORT, second)
        record_file = code_wait.printed_report_file(AGENT_ID)
        printed_line = json.loads(record_file.read_text())["line"]
        self.assertIn(f"line {printed_line + 1}", lines[1])
        self.assertIn(f"agent-{AGENT_ID}.jsonl", lines[1])

    def test_the_printed_report_record_does_not_depend_on_the_cwd(self):
        self.write_transcript(handback_records(REPORT))
        outside_a_checkout = temp_dir(self)
        elsewhere = temp_dir(self)
        init_repo(elsewhere)

        with mock.patch.object(code_wait.pathlib.Path, "cwd", return_value=outside_a_checkout):
            first = self.wait()
        with mock.patch.object(code_wait.pathlib.Path, "cwd", return_value=elsewhere):
            second = self.wait()

        self.assertEqual(first.strip(), REPORT)
        self.assertEqual(second.strip().splitlines()[0], code_wait.STILL_WORKING)
        self.assertNotIn(REPORT, second)

    def test_a_record_file_the_wait_cannot_read_stops_loudly(self):
        self.write_transcript(handback_records(REPORT))
        record_file = code_wait.printed_report_file(AGENT_ID)
        record_file.parent.mkdir(parents=True)
        bad_contents = {"not json": "not json", "no line": '{"time": "t"}', "no time": '{"line": 1}',
                        "line not a number": '{"line": "abc", "time": "t"}'}
        for name, contents in bad_contents.items():
            with self.subTest(name):
                record_file.write_text(contents)

                with self.assertRaises(SystemExit) as stop:
                    self.wait()

                self.assertIn(str(record_file), str(stop.exception))

    def test_a_finished_agent_with_no_report_records_nothing_printed(self):
        self.write_transcript([{"type": "assistant", "message": {"content": []}}], finished=True)

        output = self.wait()

        self.assertIn(code_wait.NO_REPORT, output)
        self.assertFalse(code_wait.printed_report_file(AGENT_ID).exists())

    def test_a_resumed_agent_s_second_hand_back_prints_as_the_next_report(self):
        self.write_transcript(handback_records(REPORT))
        self.wait()
        resume = {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "Do phase 1."}}
        self.append_records([resume, *handback_records("Phase 1 is implemented.", "toolu_2")])

        self.assertEqual(self.wait().strip(), "Phase 1 is implemented.")

    def test_a_resumed_agent_whose_meta_still_says_finished_keeps_working_without_a_new_hand_back(self):
        self.write_transcript(handback_records(REPORT), finished=True)
        self.wait()
        resume = {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "Do phase 1."}}
        more_text = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Working."}]}}
        self.append_records([resume, more_text])

        output = self.wait()

        self.assertEqual(output.strip().splitlines()[0], code_wait.STILL_WORKING)
        self.assertNotIn(REPORT, output)

    def test_a_resumed_agent_with_no_new_hand_back_keeps_working(self):
        self.write_transcript(handback_records(REPORT))
        self.wait()
        resume = {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "Do phase 1."}}
        self.append_records([resume])

        output = self.wait()

        self.assertEqual(output.strip().splitlines()[0], code_wait.STILL_WORKING)
        self.assertNotIn(REPORT, output)

    def test_a_last_text_with_no_hand_back_prints_once(self):
        self.write_transcript([{"type": "assistant", "message": {"content": [{"type": "text", "text": REPORT}]}}],
                              finished=True)

        first = self.wait()
        second = self.wait()

        self.assertEqual(first.strip(), REPORT)
        self.assertEqual(second.strip().splitlines()[0], code_wait.STILL_WORKING)
        self.assertNotIn(REPORT, second)

    def test_a_resumed_agent_s_new_text_after_a_last_text_report_prints_as_the_next_report(self):
        first_text = {"type": "assistant", "message": {"content": [{"type": "text", "text": REPORT}]}}
        self.write_transcript([first_text], finished=True)
        self.wait()
        resume = {"type": "attachment", "attachment": {"type": "queued_command", "prompt": "Do phase 1."}}
        more_text = {"type": "assistant", "message": {"content": [{"type": "text", "text": "Working."}]}}
        self.append_records([resume, more_text])

        self.assertEqual(self.wait().strip(), "Working.")

    def test_a_delivered_hand_back_prints_its_report(self):
        self.write_transcript(handback_records(REPORT))

        self.assertEqual(self.wait().strip(), REPORT)

    def test_an_agent_still_at_work_says_to_run_again(self):
        self.write_transcript([handback_records(REPORT)[0]], finished=False)

        self.assertEqual(self.wait().strip(), code_wait.STILL_WORKING)

    def test_an_agent_not_yet_written_says_to_run_again(self):
        self.assertEqual(self.wait().strip(), code_wait.STILL_WORKING)

    def test_a_finished_meta_without_a_hand_back_prints_the_last_text(self):
        self.write_transcript([{"type": "assistant", "message": {"content": [{"type": "text", "text": REPORT}]}}],
                              finished=True)

        self.assertEqual(self.wait().strip(), REPORT)

    def test_a_denied_hand_back_is_not_a_finish(self):
        records = handback_records(REPORT)
        records[1]["message"]["content"][0]["is_error"] = True
        self.write_transcript(records)

        self.assertEqual(self.wait().strip(), code_wait.STILL_WORKING)

    def test_a_denied_hand_back_message_is_not_the_report_of_a_finished_agent(self):
        later_text = "The real report."
        records = handback_records("Denied message.")
        records[1]["message"]["content"][0]["is_error"] = True
        records.append({"type": "assistant", "message": {"content": [{"type": "text", "text": later_text}]}})
        self.write_transcript(records, finished=True)

        self.assertEqual(self.wait().strip(), later_text)


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
        loop_folder = temp_dir(self)
        (phase_dir / code_wait.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: converged\n")

        self.assertEqual(printed(code_wait.wait_review, repo), "status: converged\n\n")

    def finished_review_in_a_store_repo(self, impacts, status="converged", blockers=()):
        """A repo whose review ended, with this session's dispatch and hand-back (holding `impacts`) in the real
        store, keyed as the commit gate keys them."""
        repo, phase_dir = self.repo_with_pid(999999999)
        packet = json.dumps({"status": status, "iter": 1, "fixed": [], "ask": [], "blockers": list(blockers),
                             "class_closure": "n/a - fixed[] empty", "plan_impacts": impacts})
        # code_review_start's real output: its exit line, then the packet.
        (phase_dir / "review.out").write_text(f"The review loop script exited 0.\n{packet}\n")
        loop_folder = temp_dir(self)
        (phase_dir / code_wait.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet + "\n")
        environment = mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(temp_dir(self)),
                                                   "CLAUDE_CODE_SESSION_ID": STORE_SESSION})
        environment.start()
        self.addCleanup(environment.stop)
        handback_store = code_wait.handback_store
        handback_store.record(STORE_SESSION, "dispatch", repo=str(repo.resolve()))
        handback_store.record(STORE_SESSION, "handback", status="converged", message=packet)
        return repo, packet

    def test_a_finished_review_lists_each_held_plan_impact_and_the_defer_sentence_and_not_an_adopted_one(self):
        held = {"text": "the queue is at-most-once; AC-2 drops the retry", "gate": "code-reviewer",
                "ac_change": True, "cause": "plan", "adopted": False}
        adopted = {"text": "the cap moves into the config", "gate": "smell-reviewer", "ac_change": False,
                   "cause": "plan", "adopted": True}
        repo, packet = self.finished_review_in_a_store_repo([held, adopted])

        with mock.patch.object(code_wait, "phase_asks_notice", return_value=[]):
            output = printed(code_wait.wait_review, repo)

        self.assertIn(packet, output)
        notice = output[len(packet):]
        self.assertIn("the queue is at-most-once; AC-2 drops the retry", notice)
        self.assertNotIn("ask the user", notice, "the /code skill defers held impacts and never stops on them")
        self.assertNotIn("decide", notice)
        handoff_file = code_wait.phase_dir(repo) / code_wait.HANDOFF_FILE
        self.assertIn("1 plan impact(s) wait for a ruling:", notice)
        self.assertIn(code_wait.defer_instruction(handoff_file), notice)
        self.assertIn(f"python3 ~/.claude/scripts/review/review_fix.py defer {handoff_file}", notice)
        self.assertNotIn("<run folder>", notice)
        self.assertIn("`RESOLVED: deferred to phase end by the session, <date>: <summary>`", notice)
        self.assertNotIn("ACTION line", notice)
        self.assertNotIn("the cap moves into the config", notice)

    def test_a_packet_that_is_not_clean_prints_no_defer_notice_for_its_held_impact(self):
        held = {"text": "the queue is at-most-once; AC-2 drops the retry", "gate": "code-reviewer",
                "ac_change": True, "cause": "plan", "adopted": False}
        repo, _packet = self.finished_review_in_a_store_repo([held], status="cap-reached",
                                                             blockers=["[critical] data loss"])

        self.assertEqual(code_wait.plan_impact_notice(repo), [])

    def test_the_notice_finds_the_hand_back_through_a_linked_path_to_the_repo(self):
        held = {"text": "the queue is at-most-once; AC-2 drops the retry", "gate": "code-reviewer",
                "ac_change": True, "cause": "plan", "adopted": False}
        repo, _packet = self.finished_review_in_a_store_repo([held])
        link = temp_dir(self) / "linked-repo"
        link.symlink_to(repo.resolve(), target_is_directory=True)

        notice = code_wait.plan_impact_notice(link)

        self.assertIn("1 plan impact(s) wait for a ruling:", notice[0])

    def test_the_review_wait_names_the_rulings_that_clear_the_gate_before_code_stops(self):
        held = {"text": "the queue is at-most-once; AC-2 drops the retry", "gate": "code-reviewer",
                "ac_change": True, "cause": "plan", "adopted": False}
        repo, _packet = self.finished_review_in_a_store_repo([held])
        with mock.patch.object(code_wait, "phase_asks_notice", return_value=[]):
            output = printed(code_wait.wait_review, repo)
        self.assertIsNotNone(code_wait.handback.false_clean_reason(STORE_SESSION), "the gate starts dirty")

        handoff_file = code_wait.phase_dir(repo) / code_wait.HANDOFF_FILE
        self.assertIn(f"review_fix.py defer {handoff_file}", output)
        handoff_file.write_text("plan_impact: RESOLVED: deferred to phase end by the session, 2026-11-19: "
                                "drop the retry\n", encoding="utf-8")

        script = toolkit_paths.REVIEW_DIR / "review_fix.py"
        finished = subprocess.run(["python3", "-I", str(script), "defer", str(handoff_file)], cwd=repo,
                                  capture_output=True, text=True, env=dict(os.environ))

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)
        self.assertIsNone(code_wait.handback.false_clean_reason(STORE_SESSION), "the defer clears the gate")

    def test_a_second_wait_after_a_plan_ruling_prints_no_notice(self):
        held = {"text": "the queue is at-most-once; AC-2 drops the retry", "gate": "code-reviewer",
                "ac_change": True, "cause": "plan", "adopted": False}
        repo, _packet = self.finished_review_in_a_store_repo([held])
        with mock.patch.object(code_wait, "phase_asks_notice", return_value=[]):
            self.assertIn("1 plan impact(s) wait for a ruling:", printed(code_wait.wait_review, repo))

            code_wait.handback_store.record(STORE_SESSION, code_wait.handback_store.PLAN_RULING, decision="keep")
            output = printed(code_wait.wait_review, repo)

        self.assertNotIn("plan impact(s) wait for a ruling", output)

    def test_a_fix_removed_change_packet_prints_the_stop_step_and_exits_one(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        packet = json.dumps({"status": "fix-removed-change", "blockers": ["the fix passes removed 24 of 41"]})
        (phase_dir / "review.out").write_text(packet + "\n")
        loop_folder = temp_dir(self)
        (phase_dir / code_wait.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet + "\n")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        self.assertEqual(code, 1)
        last_line = output.getvalue().strip().splitlines()[-1]
        self.assertTrue(last_line.startswith("STOP (fix-removed-change)"), last_line)
        self.assertIn(str(phase_dir / "stop.md"), last_line)
        self.assertIn("/code resume", last_line)

    def test_a_finished_review_with_no_output_file_says_so_and_exits_one(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue().strip(),
                         f"The review loop ended and left no packet in <loop dir>/packet.txt. "
                         f"Log: {phase_dir / 'review.out'}. {code_wait.PHASE_RESTART}")

    def test_a_launched_loop_that_ended_with_no_packet_and_no_request_says_so_and_exits_one(self):
        repo, _ = self.repo_with_pid(os.getpid())
        loop_folder = temp_dir(self)
        (loop_folder / code_wait.reviewer_dispatch.PID_FILE).write_text("999999999\n")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo, (), str(loop_folder))

        packet_file = loop_folder / code_wait.reviewer_dispatch.PACKET_FILE
        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue().strip(),
                         f"The review loop ended and left no packet in {packet_file}. {code_wait.LAUNCHED_RESTART}")

    def test_a_finished_review_with_a_named_loop_folder_and_no_packet_names_that_folder(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        (phase_dir / "review.out").write_text("No packet. Log: x\n")
        loop_folder = temp_dir(self)
        (phase_dir / code_wait.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        packet_file = loop_folder / code_wait.reviewer_dispatch.PACKET_FILE
        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue().strip(),
                         f"The review loop ended and left no packet in {packet_file}. "
                         f"Log: {phase_dir / 'review.out'}. {code_wait.PHASE_RESTART}")

    def test_a_loop_folder_named_after_the_run_was_built_is_the_one_the_message_names(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        run = code_wait.phase_review(repo)
        loop_folder = temp_dir(self)
        (phase_dir / code_wait.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")

        message = run.no_output()

        self.assertIn(str(loop_folder / code_wait.reviewer_dispatch.PACKET_FILE), message)

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
        self.assertIsNotNone(code_wait.running_review_pid(linked))
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
        patch_projects_and_waits(self)

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

    def test_a_hand_back_result_flushed_after_the_finished_meta_still_writes_the_report(self):
        call_record, result_record = handback_records(REPORT)
        self.write_finished_reviewer([call_record])
        transcript = self.projects / f"proj/session/subagents/agent-{AGENT_ID}.jsonl"
        def append_result():
            with transcript.open("a") as handle:
                handle.write(json.dumps(result_record) + "\n")

        flush = threading.Timer(0.3, append_result)
        flush.start()
        self.addCleanup(flush.cancel)
        report_file = self.entries[0]["report_file"]

        with mock.patch.object(code_wait, "SETTLE_SECONDS", 3):
            code, output, _ = self.run_main("review", AGENT_ID, report_file)

        self.assertEqual((code, output.strip()), (0, code_wait.STILL_WORKING))
        self.assertEqual(pathlib.Path(report_file).read_text(), REPORT)

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

    def test_a_loop_process_gone_with_a_named_reviewer_at_work_says_why_and_exits_one(self):
        (self.phase_dir / "pid").write_text("999999999")
        (self.phase_dir / code_wait.REVIEW_OUTPUT).write_text("")
        self.write_reviewer(AGENT_ID, [], finished=False)
        report_file = self.entries[0]["report_file"]

        code, output, _ = self.run_main("review", AGENT_ID, report_file)

        self.assertEqual(code, 1)
        self.assertIn(code_wait.LOOP_GONE, output)
        self.assertIn(report_file, output)
        self.assertIn("code_review_start.py", output)
        self.assertFalse(pathlib.Path(report_file).exists())

    def test_a_loop_that_ended_with_a_crash_packet_and_an_open_request_prints_the_packet(self):
        (self.phase_dir / "pid").write_text("999999999")
        (self.phase_dir / code_wait.REVIEW_OUTPUT).write_text("status: crashed\n")
        (self.loop_dir / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: crashed\n")

        code, output, _ = self.run_main("review")

        self.assertEqual((code, output.strip()), (0, "status: crashed"))

    def test_a_loop_killed_before_it_wrote_a_packet_says_why_though_review_out_has_text(self):
        (self.phase_dir / "pid").write_text("999999999")
        (self.phase_dir / code_wait.REVIEW_OUTPUT).write_text("No packet. Log: x\n")

        code, output, _ = self.run_main("review")

        self.assertEqual(code, 1)
        self.assertIn(code_wait.LOOP_GONE, output)
        self.assertIn(self.entries[0]["report_file"], output)

    def test_a_launched_loop_that_ended_with_a_packet_and_an_open_request_names_the_packet_command(self):
        (self.loop_dir / code_wait.reviewer_dispatch.PID_FILE).write_text("999999999\n")
        (self.loop_dir / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: crashed\n")
        packet_command = code_wait.reviewer_dispatch.packet_command(str(self.loop_dir))

        code, output, _ = self.run_main("review", "--loop", str(self.loop_dir))

        self.assertEqual(code, 0)
        self.assertEqual(output.strip(), f"The review loop script finished. Run `{packet_command}` now.")

    def test_a_loop_process_gone_with_an_unanswered_request_says_why_and_exits_one(self):
        (self.phase_dir / "pid").write_text("999999999")

        code, output, _ = self.run_main("review")

        self.assertEqual(code, 1)
        self.assertIn(code_wait.LOOP_GONE, output)
        self.assertNotIn("ACTION: dispatch-reviewer", output)

    def test_a_launched_loop_gone_with_an_open_request_names_its_launch_line(self):
        (self.loop_dir / code_wait.reviewer_dispatch.PID_FILE).write_text("999999999\n")

        code, output, _ = self.run_main("review", "--loop", str(self.loop_dir))

        self.assertEqual(code, 1)
        self.assertIn(code_wait.LOOP_GONE, output)
        self.assertIn("launch", output)

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
        (self.loop_dir / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: converged\n")
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
