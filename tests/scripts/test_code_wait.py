"""Tests for code_wait.py: the agent wait and the review wait of the /code fork."""
import contextlib
import importlib.util
import io
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import stop_file_names

module_spec = importlib.util.spec_from_file_location("code_wait", toolkit_paths.CODE_DIR / "code_wait.py")
code_wait = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(code_wait)

import reviewed_tree  # noqa: E402  (importable once code_wait has put the toolkit lib on sys.path)

AGENT_ID = "a1817e9d1060d81ea"
OTHER_AGENT_ID = "a2928f0e2171e92fb"
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
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: converged\n")

        self.assertEqual(printed(code_wait.wait_review, repo), "status: converged\n\n")

    def finished_review(self, scope_text=None):
        """A repo whose phase review ended with a clean packet; `scope_text` is the review-scope.json it left."""
        repo, phase_dir = self.repo_with_pid(999999999)
        (phase_dir / "review.out").write_text("status: converged\n")
        loop_folder = temp_dir(self)
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: converged\n")
        if scope_text is not None:
            (phase_dir / code_wait.SCOPE_FILE).write_text(scope_text)
        return repo

    def wait_code_and_output(self, repo, *args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo, *args)
        return code, output.getvalue()

    def test_the_phase_route_prints_the_tool_fault_line_after_the_packet(self):
        plain_code, _plain = self.wait_code_and_output(self.finished_review())

        code, output = self.wait_code_and_output(self.finished_review('{"held_changed": ["a.py"]}'))

        self.assertEqual(code, plain_code)
        self.assertTrue(output.startswith("status: converged"))
        self.assertTrue(output.rstrip().endswith("Tool fault: " + code_wait.held_fault_text(["a.py"])))
        self.assertTrue(output.rstrip().endswith("check them: a.py"))

    def test_the_phase_route_names_a_released_held_file_as_released_not_as_a_fault(self):
        _code, output = self.wait_code_and_output(
            self.finished_review('{"held_changed": [], "held_released": ["a.py"]}'))

        self.assertNotIn("Tool fault", output)
        self.assertTrue(output.rstrip().endswith(code_wait.held_released_text(["a.py"])))

    def test_the_phase_route_with_no_scope_file_prints_no_fault_line_and_does_not_exit(self):
        repo = self.finished_review()

        self.assertEqual(code_wait.held_fault_line(repo), "")
        _code, output = self.wait_code_and_output(repo)

        self.assertNotIn("Tool fault", output)

    def test_a_scope_file_that_is_not_json_prints_the_could_not_be_read_line_and_keeps_the_exit_code(self):
        plain_code, _plain = self.wait_code_and_output(self.finished_review())
        repo = self.finished_review("not json")

        code, output = self.wait_code_and_output(repo)

        self.assertEqual(code, plain_code)
        self.assertIn("could not be read for held-file faults", output)
        self.assertIn(str(code_wait.phase_dir(repo) / code_wait.SCOPE_FILE), output)
        self.assertIn("check the held files by hand.", output)

    def test_a_repo_outside_a_git_checkout_gives_a_line_naming_it_and_does_not_exit(self):
        outside = temp_dir(self)

        line = code_wait.held_fault_line(outside)

        self.assertIn(str(outside), line)
        self.assertIn("is not inside a git checkout", line)

    def test_a_scope_file_that_lists_no_held_changed_files_prints_no_fault_line(self):
        self.assertEqual(code_wait.held_fault_line(self.finished_review('{"held_changed": []}')), "")

    def test_the_held_changed_key_is_a_field_of_the_review_scope_the_start_script_writes(self):
        spec = importlib.util.spec_from_file_location("code_review_start_for_fields",
                                                      toolkit_paths.CODE_DIR / "code_review_start.py")
        start_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(start_module)

        self.assertIn(code_wait.HELD_CHANGED_FIELD, start_module.ReviewScope._fields)

    def test_an_unreadable_line_keeps_a_percent_sign_in_the_path_and_never_raises(self):
        scope_file = pathlib.Path("/tmp/100%s/review-scope.json")

        line = code_wait.unreadable_line(scope_file, "boom")

        self.assertIn(f"{scope_file} could not be read for held-file faults (boom)", line)

    def test_a_scope_file_field_of_the_wrong_type_names_the_file_and_the_error(self):
        cases = [('{"held_changed": "a.py"}', "held_changed is not a list of paths"),
                 ("{}", "held_changed is not a list of paths"),
                 ('{"held_changed": [1]}', "held_changed is not a list of paths"),
                 ("[]", "the top level is a list, not an object")]
        for scope_text, problem in cases:
            with self.subTest(scope_text=scope_text):
                repo = self.finished_review(scope_text)

                line = code_wait.held_fault_line(repo)

                self.assertIn(code_wait.SCOPE_FILE, line)
                self.assertIn(problem, line)

    def test_the_launched_loop_route_prints_no_fault_line_whatever_a_stale_phase_scope_file_holds(self):
        repo = self.finished_review('{"held_changed": ["a.py"]}')
        loop_folder = temp_dir(self)
        (loop_folder / code_wait.reviewer_dispatch.PID_FILE).write_text("999999999\n")

        _code, output = self.wait_code_and_output(repo, (), str(loop_folder))

        self.assertNotIn("Tool fault", output)

    def test_a_loop_dir_other_than_the_recorded_one_returns_no_packet_and_names_both_folders(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        (phase_dir / "review.out").write_text("status: converged\n")
        earlier_folder = temp_dir(self)
        this_folder = temp_dir(self)
        (earlier_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: converged\n")
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{earlier_folder}\n")
        code_wait.write_phase_run(repo, "lane-a", "2", this_folder)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        self.assertEqual(code, 1)
        self.assertNotIn("status: converged", output.getvalue())
        self.assertIn(str(earlier_folder), output.getvalue())
        self.assertIn(str(this_folder), output.getvalue())
        self.assertIn(code_wait.PHASE_RESTART_STEP, output.getvalue())
        self.assertNotIn("was stopped", output.getvalue())

    def test_a_live_review_with_a_mismatched_loop_folder_stops_without_waiting(self):
        repo, phase_dir = self.repo_with_pid(os.getpid())
        earlier_folder = temp_dir(self)
        this_folder = temp_dir(self)
        (earlier_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: converged\n")
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{earlier_folder}\n")
        code_wait.write_phase_run(repo, "lane-a", "2", this_folder)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        self.assertEqual(code, 1)
        self.assertIn(code_wait.PHASE_RESTART_STEP, output.getvalue())
        self.assertNotIn("status: converged", output.getvalue())

    def test_an_absent_loop_dir_with_a_recorded_folder_returns_no_packet(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        recorded_folder = temp_dir(self)
        (recorded_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: converged\n")
        (phase_dir / "review.out").write_text("status: converged\n")
        code_wait.write_phase_run(repo, "lane-a", "2", recorded_folder)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        self.assertEqual(code, 1)
        self.assertIn("No review of this phase has started.", output.getvalue())
        self.assertIn(code_wait.PHASE_RESTART_STEP, output.getvalue())
        self.assertNotIn("status: converged", output.getvalue())

    def test_the_recorded_loop_folder_returns_its_packet(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        (phase_dir / "review.out").write_text("status: converged\n")
        loop_folder = temp_dir(self)
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text("status: converged\n")
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        code_wait.write_phase_run(repo, "lane-a", "2", loop_folder)

        self.assertEqual(printed(code_wait.wait_review, repo), "status: converged\n\n")

    def finished_review_in_a_store_repo(self, impacts, status="converged", blockers=(), **extra_fields):
        """A repo whose review ended, with this session's dispatch and hand-back (holding `impacts`) in the real
        store, keyed as the review record keys them."""
        repo, phase_dir = self.repo_with_pid(999999999)
        packet = json.dumps({"status": status, "iter": 1, "fixed": [], "ask": [], "blockers": list(blockers),
                             "class_closure": "n/a - fixed[] empty", "plan_impacts": impacts, **extra_fields})
        # code_review_start's real output: its exit line, then the packet.
        (phase_dir / "review.out").write_text(f"The review loop script exited 0.\n{packet}\n")
        loop_folder = temp_dir(self)
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
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

    def test_a_cap_reached_packet_is_followed_by_the_fix_round_line_and_an_old_one_by_none(self):
        cases = {"with the keys": ({"fix_rounds": 2, "post_cap_passes": ["final read", "class closure"]},
                                   "cap reached after 2 fix round(s); post-cap passes: final read, class closure"),
                 "without the keys": ({}, None)}
        for message, (fields, summary) in cases.items():
            with self.subTest(message):
                remaining = [{"finding": "x", "file_line": "a.ts:1"}]
                repo, packet = self.finished_review_in_a_store_repo([], status="cap-reached",
                                                                    findings_remaining=remaining, **fields)
                with mock.patch.object(code_wait, "phase_asks_notice", return_value=[]):
                    output = printed(code_wait.wait_review, repo)
                self.assertIn(packet, output)
                if summary is None:
                    self.assertNotIn("cap reached after", output)
                else:
                    self.assertTrue(output.rstrip().splitlines()[-1].startswith("cap reached after"), output)
                    self.assertIn(summary, output)

    def test_a_converged_packet_with_the_keys_prints_no_fix_round_line(self):
        repo, _packet = self.finished_review_in_a_store_repo([], fix_rounds=1, post_cap_passes=["class closure"])
        with mock.patch.object(code_wait, "phase_asks_notice", return_value=[]):
            output = printed(code_wait.wait_review, repo)

        self.assertNotIn("cap reached after", output)

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
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet + "\n")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        self.assertEqual(code, 1)
        last_line = output.getvalue().strip().splitlines()[-1]
        self.assertTrue(last_line.startswith("STOP (fix-removed-change)"), last_line)
        self.assertIn(str(phase_dir / "stop.md"), last_line)
        self.assertIn("/code resume", last_line)

    def test_the_stop_line_is_the_last_line_when_the_scope_file_lists_a_held_released_path(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        packet = json.dumps({"status": "fix-removed-change", "blockers": ["the fix passes removed 24 of 41"]})
        (phase_dir / "review.out").write_text(packet + "\n")
        (phase_dir / code_wait.SCOPE_FILE).write_text('{"held_changed": [], "held_released": ["a.py"]}')
        loop_folder = temp_dir(self)
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet + "\n")

        code, output = self.wait_code_and_output(repo)

        lines = output.strip().splitlines()
        self.assertEqual(code, 1)
        self.assertIn(code_wait.held_released_text(["a.py"]), output)
        self.assertTrue(lines[-1].startswith("STOP (fix-removed-change)"), lines[-1])

    def test_the_restart_step_is_the_last_line_when_a_dead_loop_left_no_packet_and_a_path_was_released(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        (phase_dir / code_wait.SCOPE_FILE).write_text('{"held_changed": [], "held_released": ["a.py"]}')

        code, output = self.wait_code_and_output(repo)

        lines = output.strip().splitlines()
        self.assertEqual(code, 1)
        self.assertIn(code_wait.held_released_text(["a.py"]), output)
        self.assertEqual(lines[-1], code_wait.PHASE_RESTART_STEP)

    def capped_review_in_lane(self, reports_to, clean=False, malformed_lane_file=False, invalid_packet=False,
                              held_released=False, no_review_out=False):
        """Runs the review wait on a repo whose packet is cap-reached. By default it holds a blocker, so it stays
        cap-reached; `clean` writes a packet with no blocker, no open class and a passed full check of the current
        tree, which reads as deferred. `reports_to` None writes no lane entry; `malformed_lane_file` writes an
        unparsable lane file instead; `held_released` writes a scope file that lists a released path. Returns the
        exit code, the output lines and stderr; the run's phase folder is left in `self.capped_phase_dir`."""
        repo, phase_dir = self.repo_with_pid(999999999)
        self.capped_phase_dir = phase_dir
        if held_released:
            (phase_dir / code_wait.SCOPE_FILE).write_text('{"held_changed": [], "held_released": ["a.py"]}')
        fields = {"status": "cap-reached", "iter": 3, "fix_rounds": 2, "fixed": [], "ask": [],
                  "blockers": ["[critical] data loss"], "class_closure": "n/a - fixed[] empty",
                  "findings_remaining": [{"finding": "[critical] data loss"}]}
        if clean:
            # The fingerprint needs a commit to compare the work tree against.
            subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", "commit",
                            "-q", "--allow-empty", "-m", "base"], check=True)
            fields.update({"blockers": [], "findings_remaining": [{"finding": "[minor] naming"}],
                           "open_classes": [], "unrun_reviewer": "", "full_check": "passed",
                           "full_check_tree": reviewed_tree.fingerprint(repo)[1]})
        if invalid_packet:
            del fields["findings_remaining"]
        packet = json.dumps(fields)
        if not invalid_packet:
            # A packet that fails to parse prints no stop line, which would hide the deferred check under test.
            code_wait.handback.load(packet)
        if not no_review_out:
            (phase_dir / "review.out").write_text(packet + "\n")
        loop_folder = temp_dir(self)
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        (loop_folder / code_wait.reviewer_dispatch.PACKET_FILE).write_text(packet + "\n")
        environment = mock.patch.dict(os.environ, {"XDG_STATE_HOME": str(temp_dir(self))})
        environment.start()
        self.addCleanup(environment.stop)
        if reports_to is not None:
            code_wait.lane_entries.add_entry("cap-lane", str(repo.resolve()), str(repo.resolve()), "fix/cap",
                                             "brief", reports_to)
        if malformed_lane_file:
            lanes_dir = code_wait.lane_entries.lanes_dir()
            lanes_dir.mkdir(parents=True)
            (lanes_dir / "broken.json").write_text("{not json", encoding="utf-8")
        output = io.StringIO()
        errors = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = code_wait.wait_review(repo)
        return code, output.getvalue().strip().splitlines(), errors.getvalue()

    def assert_no_stop_line(self, lines):
        for line in lines:
            self.assertNotIn("STOP", line)
            self.assertNotIn("orch-1", line)

    def test_a_cap_reached_packet_in_a_lane_names_the_orchestrating_session_as_the_ruler(self):
        code, lines, _errors = self.capped_review_in_lane("orch-1")

        self.assertEqual(code, 1)
        self.assertTrue(lines[-1].startswith("STOP (cap-reached)"), lines[-1])
        self.assertIn("orch-1", lines[-1])
        self.assertIn(code_wait.cap_ruler_line("orch-1"), lines[-1])
        self.assertIn("Ruling: session orch-1", lines[-1])
        self.assertIn("this Ruling line", lines[-1])
        self.assertNotIn("Cap ruler", lines[-1])
        self.assertIn(str(self.capped_phase_dir / "stop.md"), lines[-1])
        self.assertIn("findings_remaining", lines[-1])
        self.assertIn("03-decisions.md", lines[-1])
        self.assertIn("## Plan Deviations", lines[-1])
        self.assertIn("when the run has a plan file", lines[-1])
        self.assertIn("/code resume", lines[-1])

    def test_the_cap_stop_line_is_the_last_line_when_the_scope_file_lists_a_held_released_path(self):
        code, lines, _errors = self.capped_review_in_lane("orch-1", held_released=True)

        self.assertEqual(code, 1)
        self.assertIn(code_wait.held_released_text(["a.py"]), "\n".join(lines))
        self.assertTrue(lines[-1].startswith("STOP (cap-reached)"), lines[-1])

    def test_a_cap_reached_packet_with_no_lane_entry_prints_no_stop_line(self):
        code, lines, _errors = self.capped_review_in_lane(None)

        self.assertEqual(code, 0)
        self.assert_no_stop_line(lines)

    def test_a_cap_reached_packet_in_a_lane_with_no_orchestrator_prints_no_stop_line(self):
        code, lines, _errors = self.capped_review_in_lane("")

        self.assertEqual(code, 0)
        self.assert_no_stop_line(lines)

    def test_an_invalid_cap_reached_packet_in_a_lane_prints_no_stop_line(self):
        code, lines, _errors = self.capped_review_in_lane("orch-1", invalid_packet=True)

        self.assertEqual(code, 0)
        self.assert_no_stop_line(lines)

    def test_the_cap_summary_and_the_asks_notice_print_before_the_cap_stop_line_in_a_lane(self):
        with mock.patch.object(code_wait, "phase_asks_notice", return_value=["ASKS NOTICE LINE"]):
            code, lines, _errors = self.capped_review_in_lane("orch-1")

        self.assertEqual(code, 1)
        self.assertTrue(lines[-1].startswith("STOP (cap-reached)"), lines[-1])
        self.assertIn("any finding asks code_wait printed", lines[-1])
        before_stop = lines[:-1]
        self.assertTrue(any(line.startswith("cap reached after") for line in before_stop), lines)
        self.assertIn("ASKS NOTICE LINE", before_stop)

    def test_a_cap_reached_packet_with_no_review_out_prints_the_restart_step_and_no_cap_summary(self):
        with mock.patch.object(code_wait, "phase_asks_notice", return_value=["ASKS NOTICE LINE"]) as notice:
            code, lines, _errors = self.capped_review_in_lane("orch-1", no_review_out=True)

        self.assertEqual(code, 1)
        self.assertEqual(lines[-1], code_wait.PHASE_RESTART_STEP)
        for line in lines:
            self.assertFalse(line.startswith("cap reached after"), line)
        notice.assert_not_called()

    def test_asks_that_cannot_be_opened_keep_their_rerun_step_as_the_last_line_in_a_lane(self):
        failure = OSError("store row damaged")
        with mock.patch.object(code_wait, "phase_asks_notice", side_effect=failure):
            code, lines, _errors = self.capped_review_in_lane("orch-1")

        self.assertEqual(code, 1)
        self.assertTrue(lines[-1].startswith("Run `"), lines[-1])
        self.assertTrue(lines[-1].endswith("again to open them for ruling."), lines[-1])
        self.assertTrue(any("could not be opened for ruling" in line for line in lines), lines)
        for line in lines:
            self.assertFalse(line.startswith("STOP (cap-reached)"), line)

    def test_a_clean_cap_reached_packet_that_reads_as_deferred_prints_no_stop_line_in_a_lane(self):
        code, lines, _errors = self.capped_review_in_lane("orch-1", clean=True)

        self.assertEqual(code, 0)
        # The summary line shows the packet parsed as cap-reached, so the no-stop result comes from the deferred read.
        self.assertIn("cap reached after 2 fix round(s)", "\n".join(lines))
        self.assert_no_stop_line(lines)

    def test_a_refused_lane_file_prints_no_stop_line_and_names_the_refusal_on_stderr(self):
        code, lines, errors = self.capped_review_in_lane(None, malformed_lane_file=True)

        self.assertEqual(code, 0)
        self.assert_no_stop_line(lines)
        self.assertIn("code_wait: a lane file is refused", errors)

    def test_a_finished_review_with_no_output_file_says_so_and_exits_one(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue().strip(),
                         f"No review of this phase has started. Log of the last start: {phase_dir / 'review.out'}.\n"
                         f"{code_wait.PHASE_RESTART_STEP}")

    def test_a_detached_child_that_died_before_writing_its_loop_dir_names_review_out(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        (phase_dir / "review.out").write_text("the child's error\n")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        self.assertEqual(code, 1)
        self.assertIn(str(phase_dir / "review.out"), output.getvalue())

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
                         f"The review loop ended and left no packet in {packet_file}.\n{code_wait.LAUNCHED_RESTART}")

    def test_a_finished_review_with_a_named_loop_folder_and_no_packet_names_that_folder(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        (phase_dir / "review.out").write_text("No packet. Log: x\n")
        loop_folder = temp_dir(self)
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = code_wait.wait_review(repo)

        packet_file = loop_folder / code_wait.reviewer_dispatch.PACKET_FILE
        self.assertEqual(code, 1)
        self.assertEqual(output.getvalue().strip(),
                         f"The review loop ended and left no packet in {packet_file}. "
                         f"Log: {phase_dir / 'review.out'}. {code_wait.PHASE_STOPPED}\n"
                         f"{code_wait.PHASE_RESTART_STEP}")

    def test_a_loop_folder_named_after_the_run_was_built_is_the_one_the_message_names(self):
        repo, phase_dir = self.repo_with_pid(999999999)
        run = code_wait.phase_review(repo)
        loop_folder = temp_dir(self)
        (phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{loop_folder}\n")

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
        (self.phase_dir / stop_file_names.LOOP_DIR_FILE).write_text(f"{self.loop_dir}\n")
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
        self.assertEqual(lines[1], "round 1: dispatch these 1 reviewer(s) now")
        self.assertIn("round 1: review1-code-reviewer; agent code-reviewer", lines[2])
        self.assertIn(self.entries[0]["report_file"], lines[2])
        self.assertIn("code_wait.py review <agentId> <report file>", lines[-1])
        self.assertTrue(lines[2].endswith(code_wait.CODE_WAIT_WRITES_NOTE), lines[2])

    def test_a_round_two_request_written_after_round_one_prints_from_the_same_wait_call(self):
        # The loop's fix pass runs between the rounds: the manifest of round 2 appears while the call waits.
        review = "## Fix\nOne\n"
        self.write_finished_reviewer([{"type": "assistant", "message": {"content": [{"type": "text",
                                                                                     "text": review}]}}])
        later = [("review2-code-reviewer", "code-reviewer", "Review app.py again."),
                 ("review2-test-reviewer", "test-reviewer", "Review the tests again.")]
        write_round_two = threading.Timer(0.3, code_wait.reviewer_dispatch.write_round, (self.loop_dir, 2, later))
        write_round_two.start()
        self.addCleanup(write_round_two.cancel)

        with mock.patch.object(code_wait, "WAIT_SECONDS", 5), mock.patch.object(code_wait, "POLL_SECONDS", 0.05):
            code, output, _ = self.run_main("review", AGENT_ID, self.entries[0]["report_file"])

        self.assertEqual(code, 0)
        lines = output.splitlines()
        self.assertEqual(lines[0], "ACTION: dispatch-reviewer")
        self.assertIn("round 2: dispatch these 2 reviewer(s) now", output)
        self.assertNotIn("round 1:", output)
        for role in ("review2-code-reviewer", "review2-test-reviewer"):
            line = next(line for line in lines if line.startswith(f"- round 2: {role}; agent "))
            self.assertIn(f"{role}.report.md", line)
        self.assertIn("A later round's lines come back from this same call.", lines[-1])

    def test_an_answered_request_lets_the_review_wait_go_on(self):
        pathlib.Path(self.entries[0]["report_file"]).write_text("## Fix\nNone\n")

        self.assertEqual(printed(code_wait.wait_review, self.repo).strip(), code_wait.STILL_WORKING)

    def test_a_loop_dir_from_before_the_run_named_one_is_no_request(self):
        (self.phase_dir / stop_file_names.LOOP_DIR_FILE).unlink()

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

    def fill_report(self, entry, agent_id):
        """Fills a request's report file the way a finished reviewer's wait does, and records who filled it."""
        pathlib.Path(entry["report_file"]).write_text("filled\n")
        code_wait.reviewer_dispatch.record_filled_by(self.loop_dir, entry["report_file"], agent_id)

    def test_a_new_agent_naming_a_report_another_agent_filled_is_refused_with_the_round_to_dispatch(self):
        self.fill_report(self.entries[0], AGENT_ID)
        code_wait.reviewer_dispatch.write_round(self.loop_dir, 2, [("review2-code-reviewer", "code-reviewer", "Go.")])

        code, output, errors = self.run_main("review", OTHER_AGENT_ID, self.entries[0]["report_file"])

        self.assertEqual(code, 1)
        self.assertNotIn(code_wait.__doc__.strip().splitlines()[0], errors, "the refusal is no usage error")
        lines = output.strip().splitlines()
        self.assertIn("round 1 is used: its report was filled by another agent; dispatch round 2", lines[0])
        self.assertIn("round 2: dispatch these 1 reviewer(s) now", output)
        last_request = [line for line in lines if line.startswith("- round ")][-1]
        self.assertIn("review2-code-reviewer", last_request)

    def test_the_agent_that_filled_a_report_run_again_after_round_two_opened_prints_round_two(self):
        self.fill_report(self.entries[0], AGENT_ID)
        code_wait.reviewer_dispatch.write_round(self.loop_dir, 2, [("review2-code-reviewer", "code-reviewer", "Go.")])

        code, output, _ = self.run_main("review", AGENT_ID, self.entries[0]["report_file"])

        self.assertEqual(code, 0)
        self.assertIn("round 2: dispatch these 1 reviewer(s) now", output)

    def test_a_finished_reviewer_is_recorded_as_the_filler_of_its_report(self):
        self.write_finished_reviewer([{"type": "assistant", "message": {"content": [{"type": "text",
                                                                                     "text": "## Fix\nNone\n"}]}}])
        report_file = self.entries[0]["report_file"]

        self.run_main("review", AGENT_ID, report_file)

        recorded = code_wait.reviewer_dispatch.all_requests(self.loop_dir)[0]
        self.assertEqual(recorded["filled_by"], AGENT_ID)

    def test_a_dispatch_for_a_round_no_manifest_holds_is_no_stale_dispatch(self):
        unknown_report = str(self.loop_dir / "unknown.report.md")
        problem = code_wait.reviewer_dispatch.used_round_problem(self.loop_dir, [(AGENT_ID, unknown_report)])

        self.assertEqual(problem, "")

    def test_a_filled_report_with_no_recorded_filler_is_not_refused(self):
        """Old-report gap: a manifest written before `filled_by` existed names no filler, so a report with text and
        no recorded filler is not refused as a used round."""
        pathlib.Path(self.entries[0]["report_file"]).write_text("round one\n")
        code_wait.reviewer_dispatch.write_round(self.loop_dir, 2, [("review2-code-reviewer", "code-reviewer", "Go.")])

        problem = code_wait.reviewer_dispatch.used_round_problem(
            self.loop_dir, [(OTHER_AGENT_ID, self.entries[0]["report_file"])])

        self.assertEqual(problem, "")

    def test_a_report_another_agent_filled_in_the_last_round_is_refused_with_no_round_open(self):
        self.fill_report(self.entries[0], AGENT_ID)

        problem = code_wait.reviewer_dispatch.used_round_problem(
            self.loop_dir, [(OTHER_AGENT_ID, self.entries[0]["report_file"])])

        self.assertEqual(problem, "round 1 is used: its report was filled by another agent; "
                                  "rerun the wait with no pairs to get the next round or the packet")

    def test_the_refusal_with_no_round_open_ends_on_a_step(self):
        self.fill_report(self.entries[0], AGENT_ID)

        code, output, _ = self.run_main("review", OTHER_AGENT_ID, self.entries[0]["report_file"])

        self.assertEqual(code, 1)
        self.assertEqual(output.strip().splitlines()[-1],
                         "round 1 is used: its report was filled by another agent; "
                         "rerun the wait with no pairs to get the next round or the packet")

    def test_the_same_pair_run_again_after_its_report_was_written_still_waits(self):
        report_file = self.entries[0]["report_file"]
        self.fill_report(self.entries[0], AGENT_ID)

        code, output, _ = self.run_main("review", AGENT_ID, report_file)

        self.assertEqual((code, output.strip()), (0, code_wait.STILL_WORKING))

    def test_a_call_that_also_names_an_open_request_passes_the_used_round_check(self):
        self.fill_report(self.entries[0], AGENT_ID)
        round_two = code_wait.reviewer_dispatch.write_round(self.loop_dir, 2,
                                                            [("review2-code-reviewer", "code-reviewer", "Go.")])

        problem = code_wait.reviewer_dispatch.used_round_problem(
            self.loop_dir, [(OTHER_AGENT_ID, self.entries[0]["report_file"]),
                            (OTHER_AGENT_ID, round_two[0]["report_file"])])

        self.assertEqual(problem, "")

    def test_a_filled_by_another_agent_request_whose_report_was_emptied_is_not_refused(self):
        self.fill_report(self.entries[0], AGENT_ID)
        pathlib.Path(self.entries[0]["report_file"]).write_text("")

        problem = code_wait.reviewer_dispatch.used_round_problem(
            self.loop_dir, [(OTHER_AGENT_ID, self.entries[0]["report_file"])])

        self.assertEqual(problem, "")

    def test_a_stale_pair_beside_a_pair_the_calling_agent_filled_is_not_refused(self):
        self.fill_report(self.entries[0], AGENT_ID)
        round_two = code_wait.reviewer_dispatch.write_round(self.loop_dir, 2,
                                                            [("review2-code-reviewer", "code-reviewer", "Go.")])
        self.fill_report(round_two[0], OTHER_AGENT_ID)

        problem = code_wait.reviewer_dispatch.used_round_problem(
            self.loop_dir, [(OTHER_AGENT_ID, self.entries[0]["report_file"]),
                            (OTHER_AGENT_ID, round_two[0]["report_file"])])

        self.assertEqual(problem, "")

    def test_several_used_rounds_are_named_in_the_plural(self):
        self.fill_report(self.entries[0], AGENT_ID)
        round_two = code_wait.reviewer_dispatch.write_round(self.loop_dir, 2,
                                                            [("review2-code-reviewer", "code-reviewer", "Go.")])
        self.fill_report(round_two[0], AGENT_ID)
        code_wait.reviewer_dispatch.write_round(self.loop_dir, 3, [("review3-code-reviewer", "code-reviewer", "Go.")])
        pairs = [(OTHER_AGENT_ID, self.entries[0]["report_file"]), (OTHER_AGENT_ID, round_two[0]["report_file"])]

        problem = code_wait.reviewer_dispatch.used_round_problem(self.loop_dir, pairs)

        self.assertEqual(problem, "rounds 1, 2 are used: their reports were filled by other agents; dispatch round 3")

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
        self.assertIn(code_wait.reviewer_dispatch.LOOP_GONE, output)
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
        self.assertIn(code_wait.reviewer_dispatch.LOOP_GONE, output)
        self.assertIn(self.entries[0]["report_file"], output)
        self.assertNotIn(code_wait.CODE_WAIT_WRITES_NOTE, output)
        prompt_file = self.entries[0]["prompt_file"]
        self.assertNotIn(prompt_file, output)
        self.assertNotIn(code_wait.reviewer_dispatch.AGENT_PROMPT.format(prompt_file=prompt_file), output)

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
        self.assertIn(code_wait.reviewer_dispatch.LOOP_GONE, output)
        self.assertNotIn("ACTION: dispatch-reviewer", output)

    def test_a_loop_process_gone_with_a_held_path_released_ends_on_the_restart_step(self):
        (self.phase_dir / "pid").write_text("999999999")
        (self.phase_dir / code_wait.SCOPE_FILE).write_text('{"held_changed": [], "held_released": ["a.py"]}')

        code, output, _ = self.run_main("review")

        self.assertEqual(code, 1)
        self.assertEqual(output.strip().splitlines()[-1], code_wait.PHASE_RESTART_STEP)
        self.assertIn(code_wait.reviewer_dispatch.LOOP_GONE, output)
        self.assertIn(code_wait.held_released_text(["a.py"]), output)

    def test_a_launched_loop_gone_with_an_open_request_names_its_launch_line(self):
        (self.loop_dir / code_wait.reviewer_dispatch.PID_FILE).write_text("999999999\n")

        code, output, _ = self.run_main("review", "--loop", str(self.loop_dir))

        self.assertEqual(code, 1)
        self.assertIn(code_wait.reviewer_dispatch.LOOP_GONE, output)
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
        self.assertIn(self.entries[0]["report_file"], lines[2])
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

    def test_a_loop_folder_whose_prompt_file_is_malformed_stops_naming_the_file(self):
        (self.loop_dir / code_wait.reviewer_dispatch.PID_FILE).write_text(str(os.getpid()))
        prompt_file = self.loop_dir / code_wait.reviewer_dispatch.PROMPT_FILE
        prompt_file.write_text("repo: /work/repo\n\nhandoff\n")

        code, _, errors = self.run_main("review", "--loop", str(self.loop_dir))

        self.assertEqual(code, 2)
        self.assertIn(str(prompt_file), errors)
        self.assertNotIn("Traceback", errors)

    def test_a_loop_flag_with_no_folder_stops_loudly(self):
        code, _, errors = self.run_main("review", "--loop")

        self.assertEqual(code, 2)
        self.assertIn("--loop needs the loop folder", errors)

    def test_every_wait_ends_before_the_harness_backgrounds_the_call(self):
        self.assertLess(code_wait.WAIT_SECONDS + code_wait.POLL_SECONDS, 180)


if __name__ == "__main__":
    unittest.main()
