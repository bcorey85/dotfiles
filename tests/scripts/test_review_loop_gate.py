import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import fake_ledger
import toolkit_paths

SCRIPT = os.environ.get("REVIEW_LOOP_GATE_SCRIPT") or str(toolkit_paths.REVIEW_DIR / "review_loop_gate.py")
SCRIPTS_ROOT = str(toolkit_paths.SCRIPTS_DIR)
LOGGER = os.environ.get("LOG_REVIEW_FINDING_SCRIPT") or str(
    toolkit_paths.CLAUDE_DIR / "skills" / "review" / "log-review-finding"
)

ASYNC_RESULT = "Async agent launched successfully.\nagentId: a7bf12f9c51bc4875 (internal ID)"
FIXTURES = pathlib.Path(__file__).resolve().parent / "fixtures"


def background_shell(fixture_name):
    """A real shell call, its result that moved it to the background, and its task notification."""
    with open(FIXTURES / fixture_name, encoding="utf-8") as fh:
        call, moved, notified = map(json.loads, fh)
    return [user("review loop"), call, moved], notified


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def dispatch(tool_use_id, subagent_type):
    block = {"type": "tool_use", "id": tool_use_id, "name": "Agent",
             "input": {"subagent_type": subagent_type, "prompt": "go"}}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


def result(tool_use_id, text):
    block = {"type": "tool_result", "tool_use_id": tool_use_id, "content": [{"type": "text", "text": text}]}
    return {"type": "user", "message": {"role": "user", "content": [block]}}


def bash(command, tool_use_id="toolu_bash"):
    block = {"type": "tool_use", "id": tool_use_id, "name": "Bash", "input": {"command": command}}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


FULL_CHECK_CALL = "python3 ~/.claude/scripts/review/full_check.py /r/app --log /tmp/review-gate-feat.log -- 'npm test'"
FULL_CHECK_PASSED = "full check: passed\nsummary: 3 passed in 0.1s"


def full_check_run(output=FULL_CHECK_PASSED, command=FULL_CHECK_CALL, tool_use_id="toolu_full"):
    """A full_check.py shell call and the tool_result it printed."""
    return [bash(command, tool_use_id), result(tool_use_id, output)]


def send_message(to):
    block = {"type": "tool_use", "id": "toolu_send", "name": "SendMessage", "input": {"to": to, "message": "go on"}}
    return {"type": "assistant", "message": {"role": "assistant", "content": [block]}}


def notification(tool_use_id):
    prompt = (
        f"<task-notification>\n<task-id>t1</task-id>\n<tool-use-id>{tool_use_id}</tool-use-id>\n</task-notification>"
    )
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": prompt}}


def coder_and_background_reviewer():
    return [user("review loop"),
            dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
            dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", ASYNC_RESULT)]


def resume_background_coder():
    """A background coder launched and already notified, then resumed with a SendMessage that came back as a resume."""
    send = {"type": "tool_use", "id": "toolu_resume", "name": "SendMessage",
            "input": {"to": "a5bc2ebfa0d6aeaf8", "message": "fix it"}}
    resumed = json.dumps({"success": True, "message": "Resuming agent a5bc2eb", "resumedAgentId": "a5bc2ebfa0d6aeaf8"})
    return [user("review loop"),
            dispatch("toolu_coder", "coder"),
            result("toolu_coder", "Async agent launched\nagentId: a5bc2ebfa0d6aeaf8"),
            notification("toolu_coder"),
            {"type": "assistant", "message": {"role": "assistant", "content": [send]}},
            result("toolu_resume", resumed)]


class StopHookMixin:
    def stop(self, records, old_packet_form=False, **extra):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "loop.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
        hook = {"hook_event_name": "SubagentStop", "agent_type": "review-loop", "agent_transcript_path": path}
        hook.update(extra)
        proc = subprocess.run([sys.executable, "-B", SCRIPT], input=json.dumps(hook), capture_output=True,
                              text=True, check=True)
        if old_packet_form:
            self.assertIn("old free-text packet", proc.stderr)
        else:
            self.assertEqual(proc.stderr, "")
        return proc.stdout


class ReviewLoopGateTest(StopHookMixin, unittest.TestCase):
    def test_reported_background_dispatch_blocks_without_full_check(self):
        out = self.stop([*coder_and_background_reviewer(), notification("toolu_rev")])
        self.assertIn("No passed full_check.py result", json.loads(out)["reason"])

    def test_agent_message_counts_as_reported(self):
        message = user('<agent-message from="a7bf12f9c51bc4875">findings</agent-message>')
        out = self.stop([*coder_and_background_reviewer(), message])
        self.assertIn("No passed full_check.py result", json.loads(out)["reason"])

    def test_foreground_dispatch_blocks(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "agentId: a7bf12f9c51bc4875")]
        self.assertIn("No passed full_check.py result", json.loads(self.stop(records))["reason"])

    def test_a_delivered_hand_back_ends_the_full_check_block_but_a_stop_without_one_keeps_it(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        handing_back = {"type": "tool_use", "id": "toolu_hb", "name": "SubagentHandback",
                        "input": {"message": '{"status": "converged"}'}}
        delivered = [{"type": "assistant", "message": {"role": "assistant", "content": [handing_back]}},
                     result("toolu_hb", "delivered")]
        self.assertIn("No passed full_check.py result", json.loads(self.stop(records))["reason"])
        self.assertEqual(self.stop([*records, *delivered]), "")

    def test_a_denied_hand_back_does_not_end_the_full_check_block(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        handing_back = {"type": "tool_use", "id": "toolu_hb", "name": "SubagentHandback",
                        "input": {"message": '{"status": "converged"}'}}
        denied = [{"type": "assistant", "message": {"role": "assistant", "content": [handing_back]}},
                  {"type": "user", "message": {"role": "user", "content": [
                      {"type": "tool_result", "tool_use_id": "toolu_hb", "content": "denied", "is_error": True}]}}]
        self.assertIn("No passed full_check.py result", json.loads(self.stop([*records, *denied]))["reason"])

    def test_a_plan_impact_report_owes_no_full_check(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        self.assertIn("No passed full_check.py result", json.loads(self.stop(records))["reason"])
        out = self.stop(records, old_packet_form=True,
                        last_assistant_message="status: plan-impact\niter: 1\nplan_impact: a, b\n")
        self.assertNotIn("No passed full_check.py result", out)

    def test_a_json_plan_impact_report_owes_no_full_check(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        packet = json.dumps({"status": "plan-impact", "iter": 1, "plan_impact": "a, b"})
        padded = [json.dumps({"status": status, "iter": 1}) for status in
                  ("plan-impact (needs ruling)", "`plan-impact`", " plan-impact")]
        for message in (packet, f"```json\n{packet}\n```", json.dumps({"iter": 1, "status": "plan-impact"}, indent=2),
                        *padded):
            with self.subTest(message=message):
                out = self.stop(records, last_assistant_message=message)
                self.assertNotIn("No passed full_check.py result", out)

    def test_a_json_converged_report_still_owes_a_full_check(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        packet = json.dumps({"status": "converged", "iter": 1, "fixed": [], "plan_impact": '"status": "plan-impact"'})
        out = self.stop(records, last_assistant_message=packet)
        self.assertIn("No passed full_check.py result", json.loads(out)["reason"])

    def test_a_check_the_phase_declares_expected_red_counts_as_run(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   *full_check_run("full check: not run (expected red until Phase 3)\n"
                                   "expected red: `make test` until Phase 3")]
        self.assertEqual(self.stop(records), "")

    def test_full_check_after_reviewed_coder_passes(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "ok"),
                   *full_check_run()]
        self.assertEqual(self.stop(records), "")

    def test_a_full_check_script_call_whose_result_is_not_passed_is_blocked(self):
        coder = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        results = ("full check: failed (exit 1)\nFAILED tests/test_a.py::test_x",
                   "full check: unverified (exit 0, no runner summary)\nsummary: not found",
                   "full check: setup fault (exit 127)\nnpm: command not found",
                   "full check: not run (timeout)",
                   "full check: not run (check-command error: no such file tests/x)",
                   "full check: not run (environment gap: No module named 'x')",
                   "full check: pre-existing failure (the check fails the same way without this diff)",
                   "full check: passed-ish",
                   "the output quotes full check: passed mid-line",
                   "full check: failed (exit 1)\nfull check: passed",
                   "")
        for output in results:
            with self.subTest(output=output):
                records = [*coder, *full_check_run(output)]
                reason = json.loads(self.stop(records))["reason"]
                self.assertIn("No passed full_check.py result", reason)
                self.assertIn("If a full_check.py result already follows the last code change and was not passed, "
                              "do not run it again: follow Step 6's route for that result and return the packet. "
                              "Otherwise run the Step 6 execution gate now.", reason)

    def test_a_bare_checker_command_with_a_passing_looking_output_is_blocked(self):
        coder = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        for command in ("npm test", "npm test > /tmp/review-gate.log 2>&1", "pytest -q"):
            with self.subTest(command=command):
                records = [*coder, bash(command, "toolu_bare"), result("toolu_bare", FULL_CHECK_PASSED)]
                self.assertIn("No passed full_check.py result", json.loads(self.stop(records))["reason"])

    def test_a_passed_line_with_no_result_for_the_call_or_for_another_call_is_blocked(self):
        coder = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        unanswered = [bash(FULL_CHECK_CALL, "toolu_full")]
        elsewhere = [bash(FULL_CHECK_CALL, "toolu_full"), result("toolu_other", FULL_CHECK_PASSED)]
        for run in (unanswered, elsewhere):
            with self.subTest(run=run):
                self.assertIn("No passed full_check.py result", json.loads(self.stop([*coder, *run]))["reason"])

    def test_a_full_check_result_is_read_from_its_own_call_when_other_shell_calls_come_between(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   bash(FULL_CHECK_CALL, "toolu_full"), bash("git status", "toolu_git"),
                   result("toolu_git", "clean"), result("toolu_full", FULL_CHECK_PASSED)]
        self.assertEqual(self.stop(records), "")

    def test_a_command_of_two_full_check_calls_counts_only_when_each_call_printed_passed(self):
        coder = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        second_call = FULL_CHECK_CALL.replace("/r/app", "/r/lib").replace("'npm test'", "'npm run lint'")
        command = f"{FULL_CHECK_CALL} ; {second_call}"
        failed = "full check: failed (exit 1)\nFAIL src/a.test.ts"
        blocked_by_output = {FULL_CHECK_PASSED: True,
                             FULL_CHECK_PASSED + "\n" + failed: True,
                             FULL_CHECK_PASSED + "\n" + FULL_CHECK_PASSED: False}

        for output, blocked in blocked_by_output.items():
            with self.subTest(output=output):
                out = self.stop([*coder, *full_check_run(output, command)])

                self.assertEqual(bool(out), blocked)

    def test_a_fix_coder_after_the_last_review_needs_only_the_full_check(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "ok"),
                   dispatch("toolu_fix", "coder"), result("toolu_fix", "done")]
        self.assertIn("No passed full_check.py result", json.loads(self.stop(records))["reason"])
        self.assertEqual(self.stop([*records, *full_check_run()]), "")

    def test_a_message_to_a_coder_after_the_full_check_counts_as_a_code_change(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "agentId: acoder1"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "ok"),
                   *full_check_run()]
        self.assertEqual(self.stop(records), "")
        out = self.stop([*records, send_message("acoder1")])
        self.assertIn("No passed full_check.py result", json.loads(out)["reason"])

    def test_stop_hook_active_passes(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        self.assertEqual(self.stop(records, stop_hook_active=True), "")

    def repo_with_claude_md(self, claude_md):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        subprocess.run(["git", "init", "-q", tmp.name], check=True)
        pathlib.Path(tmp.name, "CLAUDE.md").write_text(claude_md)
        return tmp.name

    def test_a_repo_whose_full_suite_runs_in_ci_owes_no_full_check(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        repo = self.repo_with_claude_md("# Repo\n\n- Full suite: CI\n")

        self.assertEqual(self.stop(records, cwd=repo), "")

    def test_a_loop_reviewing_a_repo_whose_full_suite_runs_in_ci_owes_no_full_check_from_another_cwd(self):
        reviewed = self.repo_with_claude_md("# Repo\n\n- Full suite: CI\n")
        other = self.repo_with_claude_md("# Other repo\n")
        records = [user(f"review loop\nrepo: {reviewed}"), dispatch("toolu_coder", "coder"),
                   result("toolu_coder", "done")]

        self.assertEqual(self.stop(records, cwd=other), "")

    def test_a_loop_reviewing_a_repo_without_the_ci_line_owes_a_full_check_though_the_cwd_has_it(self):
        reviewed = self.repo_with_claude_md("# Repo\n")
        other = self.repo_with_claude_md("- Full suite: CI\n")
        records = [user(f"review loop\nrepo: {reviewed}"), dispatch("toolu_coder", "coder"),
                   result("toolu_coder", "done")]

        self.assertIn("No passed full_check.py result", json.loads(self.stop(records, cwd=other))["reason"])

    def test_a_repo_without_the_exact_full_suite_line_still_owes_a_full_check(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        for claude_md in ("# Repo\n", "Full suite: ci\n", "Full-suite: CI\n", "The full suite: CI\n"):
            with self.subTest(claude_md=claude_md):
                repo = self.repo_with_claude_md(claude_md)

                self.assertIn("No passed full_check.py result", json.loads(self.stop(records, cwd=repo))["reason"])

    def test_a_foreground_report_that_quotes_the_launch_text_is_not_an_open_dispatch(self):
        report = "Reviewed the gate. It counts `Async agent launched` results as open dispatches.\nagentId: arev1"
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", report)]
        self.assertIn("No passed full_check.py result", json.loads(self.stop(records))["reason"])


class StopRowTest(unittest.TestCase):
    def stop_in_session(self, records, store_dir, transcript_path=None, **extra):
        # The hook runs with its own store folder so the test never writes the real ~/.claude/state.
        env = {**os.environ, "HANDBACK_STORE_DIR": store_dir}
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "loop.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(rec if isinstance(rec, str) else json.dumps(rec))
                fh.write("\n")
        hook = {"hook_event_name": "SubagentStop", "agent_type": "review-loop",
                "agent_transcript_path": transcript_path or path, "session_id": "s-stop", "agent_id": "loop-1",
                **extra}
        return subprocess.run([sys.executable, "-B", SCRIPT], input=json.dumps(hook), capture_output=True,
                              text=True, check=True, env=env)

    def new_store(self):
        store = tempfile.TemporaryDirectory()
        self.addCleanup(store.cleanup)
        return store.name

    def open_counts(self, store_dir):
        return [row["open_dispatches"] for row in self.stored_stops(store_dir)]

    def stored_stops(self, store_dir):
        with open(os.path.join(store_dir, "s-stop.jsonl"), encoding="utf-8") as fh:
            return [row for row in map(json.loads, fh) if row["kind"] == "stop"]

    def test_a_stop_stores_the_loop_agent_and_its_open_dispatch_count(self):
        store = tempfile.TemporaryDirectory()
        self.addCleanup(store.cleanup)
        waiting = self.stop_in_session(coder_and_background_reviewer(), store.name)
        self.assertEqual(waiting.stdout, "")
        finished = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                    *full_check_run()]
        self.stop_in_session(finished, store.name)
        stops = self.stored_stops(store.name)
        self.assertEqual([(row["agent_id"], row["open_dispatches"]) for row in stops],
                         [("loop-1", 1), ("loop-1", 0)])

    def logged_ask_rows(self, command, printed):
        store = self.new_store()
        self.stop_in_session([user("review loop"), bash(command, "toolu_log"), result("toolu_log", printed)], store)
        [stop] = self.stored_stops(store)
        return stop.get("ask_rows")

    def test_a_stop_stores_the_id_the_log_helper_printed_for_each_ask_row(self):
        command = ('cd ~/.claude/skills/review && L="lane=none scope=standalone iter=2 gate=code-reviewer"; '
                   'D=docs/guide\n'
                   './log-review-finding kind=run $L n_findings=3 diff_loc=9 result=PASS\n'
                   './log-review-finding kind=finding $L disposition=fix class=bug file=src/a.ts line=4 '
                   'actioned=fixed\n'
                   './log-review-finding kind=finding $L disposition=ask class=docs file=$D/spec.md line=314 '
                   'actioned=ask\n'
                   './log-review-finding kind=finding $L disposition=ask class=smell file="src/b.ts" line=7 '
                   'actioned=ask && echo done')
        printed = ("run_id=18ece5ac665dfd8e\nfinding_id=6087ff2824ca37b6\nfinding_id=712b01a68fd88a12\n"
                   "finding_id=b220bc228d6edb04")
        self.assertEqual(self.logged_ask_rows(command, printed),
                         [{"file": "spec.md", "line": 314, "finding_id": "712b01a68fd88a12"},
                          {"file": "src/b.ts", "line": 7, "finding_id": "b220bc228d6edb04"}])

    def test_a_command_whose_printed_ids_do_not_match_its_finding_calls_pairs_nothing(self):
        command = ('./log-review-finding kind=finding lane=none disposition=ask class=docs file=a.ts line=1 '
                   'actioned=ask\n'
                   './log-review-finding kind=finding lane=none disposition=ask class=docs file=b.ts line=2 '
                   'actioned=ask')
        self.assertEqual(self.logged_ask_rows(command, "finding_id=6087ff2824ca37b6\nlog-review-finding: failed"), [])

    def test_a_helper_path_held_in_a_shell_variable_still_counts_as_a_finding_call(self):
        command = ('L=~/.claude/skills/review/log-review-finding; D=docs/guide\n'
                   '$L kind=finding lane=none disposition=fix class=bug file=src/a.ts line=4 actioned=fixed\n'
                   '${L} kind=finding lane=none disposition=ask class=docs file=$D/spec.md line=314 actioned=ask')
        printed = "finding_id=6087ff2824ca37b6\nfinding_id=712b01a68fd88a12"
        self.assertEqual(self.logged_ask_rows(command, printed),
                         [{"file": "spec.md", "line": 314, "finding_id": "712b01a68fd88a12"}])

    def test_a_command_that_mixes_the_variable_form_and_the_path_form_pairs_each_call_with_its_own_id(self):
        command = ('L=~/.claude/skills/review/log-review-finding\n'
                   '$L kind=finding lane=none disposition=ask class=docs file=a.ts line=1 actioned=ask\n'
                   './log-review-finding kind=finding lane=none disposition=fix class=bug file=b.ts line=2 '
                   'actioned=fixed\n'
                   '$L kind=finding lane=none disposition=ask class=docs file=c.ts line=3 actioned=ask')
        printed = "finding_id=6087ff2824ca37b6\nfinding_id=712b01a68fd88a12\nfinding_id=b220bc228d6edb04"
        self.assertEqual(self.logged_ask_rows(command, printed),
                         [{"file": "a.ts", "line": 1, "finding_id": "6087ff2824ca37b6"},
                          {"file": "c.ts", "line": 3, "finding_id": "b220bc228d6edb04"}])

    def test_a_stop_the_gate_blocked_is_stored_as_blocked_and_a_passing_stop_is_not(self):
        store = self.new_store()
        unchecked = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        checked = [*unchecked, *full_check_run()]
        blocked_out = self.stop_in_session(unchecked, store)
        self.stop_in_session(checked, store)
        self.assertIn("block", blocked_out.stdout)
        self.assertEqual([bool(row.get("blocked")) for row in self.stored_stops(store)], [True, False])

    def test_a_stop_with_no_ask_call_stores_no_ask_rows(self):
        self.assertEqual(self.logged_ask_rows("ls", "ok"), [])

    def test_a_store_write_error_never_blocks_the_stop(self):
        store = tempfile.TemporaryDirectory()
        self.addCleanup(store.cleanup)
        blocked = os.path.join(store.name, "file")
        with open(blocked, "w", encoding="utf-8") as fh:
            fh.write("not a folder")
        done = self.stop_in_session(coder_and_background_reviewer(), blocked)
        self.assertEqual(done.stdout, "")
        self.assertIn("stop row skipped", done.stderr)

    def test_a_stop_with_an_unreadable_transcript_writes_a_zero_row_and_still_fails_open(self):
        store = self.new_store()
        self.stop_in_session(coder_and_background_reviewer(), store)
        half_written = [*coder_and_background_reviewer(), '{"type": "user", "mess']
        torn = self.stop_in_session(half_written, store)
        missing = self.stop_in_session([], store, transcript_path=os.path.join(store, "no-such-loop.jsonl"))
        not_an_object = self.stop_in_session([*coder_and_background_reviewer(), "[]"], store)
        self.assertEqual((torn.stdout, missing.stdout, not_an_object.stdout), ("", "", ""))
        self.assertIn("skipped", torn.stderr)
        self.assertIn("skipped", missing.stderr)
        self.assertIn("skipped", not_an_object.stderr)
        self.assertEqual(self.open_counts(store), [1, 0, 0, 0])

    def test_a_resume_result_with_only_the_short_id_matches_the_launched_agent_by_prefix(self):
        store = self.new_store()
        short_only = [*resume_background_coder()[:-1], result("toolu_resume", "Resuming agent a5bc2eb")]
        self.stop_in_session(short_only, store)
        self.stop_in_session([*short_only, notification("toolu_resume")], store)
        self.assertEqual(self.open_counts(store), [1, 0])

    def test_a_background_resume_is_open_until_a_later_notification_or_agent_message(self):
        store = self.new_store()
        resumed = resume_background_coder()
        self.stop_in_session(resumed, store)
        self.stop_in_session([*resumed, notification("toolu_resume")], store)
        message = user('<agent-message from="a5bc2ebfa0d6aeaf8">done</agent-message>')
        self.stop_in_session([*resumed, message], store)
        self.assertEqual(self.open_counts(store), [1, 0, 0])

    def test_a_shell_moved_to_the_background_is_open_until_its_task_notification(self):
        for fixture_name in ("loop_shell_moved_to_background_by_timeout.jsonl", "loop_shell_run_in_background.jsonl"):
            with self.subTest(fixture_name):
                store = self.new_store()
                waiting, notified = background_shell(fixture_name)

                waiting_stop = self.stop_in_session(waiting, store)
                self.stop_in_session([*waiting, notified], store)

                self.assertEqual(waiting_stop.stdout, "")
                self.assertEqual(self.open_counts(store), [1, 0])

    def test_a_reviewer_the_rate_limit_killed_is_closed_by_its_task_id_notification(self):
        store = self.new_store()
        waiting = coder_and_background_reviewer()
        killed = ("<task-notification>\n<task-id>a7bf12f9c51bc4875</task-id>\n<status>failed</status>\n"
                  "<summary>Agent \"code-reviewer\" failed: rate limit reached</summary>\n</task-notification>")
        notified = {"type": "attachment", "attachment": {"type": "queued_command", "prompt": killed}}

        self.stop_in_session(waiting, store)
        self.stop_in_session([*waiting, notified], store)

        self.assertEqual(self.open_counts(store), [1, 0])

    def test_a_background_resume_is_closed_by_a_later_task_id_only_notification(self):
        store = self.new_store()
        resumed = resume_background_coder()
        killed = (
            "<task-notification>\n<task-id>a5bc2ebfa0d6aeaf8</task-id>\n"
            "<status>failed</status>\n</task-notification>"
        )
        notified = {"type": "attachment", "attachment": {"type": "queued_command", "prompt": killed}}

        self.stop_in_session(resumed, store)
        self.stop_in_session([*resumed, notified], store)

        self.assertEqual(self.open_counts(store), [1, 0])


def indented(report):
    """A report as the harness hands it over: framed, every line indented two spaces."""
    frame = "[Subagent hand-back] The text below is the final report of a subagent.\nThe report follows:\n"
    return frame + "\n".join("  " + line for line in report.splitlines())


CODE_REPORT = """## Code Review Summary

**Files Reviewed**: a.py
**Overall Assessment**: NEEDS CHANGES

### Fix
[blocker] a.py:10 — bug one — do this
1. `b.py:3-4` — bug two
   continued on a second line

### Ask
src/c.ts — which way? — pick

### Nit
one combined nit line"""
SMELL_REPORT = """## Structure Review Summary

**Overall Assessment**: PASS WITH WARNINGS

### Fix
a.py:5 — [smell] copy of helper"""
CLEAN_REPORT = """## Code Review Summary

**Files Reviewed**: a.py
**Overall Assessment**: PASS"""
COMPLEXITY_REPORT = """## Simplification Review

**Bound**: a.py

### Findings
a.py:1 — [complexity] x
a.py:2 — [complexity] y"""


def agent_message(agent_id, report):
    return user(
        f'Another Claude session sent a message while you were working:\n<agent-message from="{agent_id}">\n'
        f'{indented(report)}'
    )


def notification_with_result(tool_use_id, report):
    prompt = (
        f"<task-notification>\n<task-id>t1</task-id>\n<tool-use-id>{tool_use_id}</tool-use-id>\n<result>{indented(report)}</result>\n"
        "</task-notification>"
    )
    return {"type": "attachment", "attachment": {"type": "queued_command", "prompt": prompt}}


class RunRowTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(self.home)
        self.transcript = os.path.join(self.tmp.name, "loop.jsonl")
        claude_dir = os.path.join(self.tmp.name, "claude")
        os.makedirs(os.path.join(claude_dir, "skills", "review"))
        shutil.copy2(LOGGER, os.path.join(claude_dir, "skills", "review", "log-review-finding"))
        os.symlink(SCRIPTS_ROOT, os.path.join(claude_dir, "scripts"))
        self.script, self.quiet, self.stderr = SCRIPT, True, ""
        self.env = {**os.environ, "HOME": self.home, **fake_ledger.install(self.tmp.name),
                    "REVIEW_LOOP_GATE_STATE_DIR": os.path.join(self.tmp.name, "state"),
                    "REVIEW_LOOP_GATE_CLAUDE_DIR": claude_dir,
                    "CLAUDE_TOOLKIT_TELEMETRY": "1"}

    def stop(self, records, **extra):
        with open(self.transcript, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
        hook = {"hook_event_name": "SubagentStop", "agent_type": "review-loop", "session_id": "s1",
                "agent_transcript_path": self.transcript}
        hook.update(extra)
        proc = subprocess.run([sys.executable, "-B", self.script], input=json.dumps(hook), capture_output=True,
                              text=True, check=True, env=self.env, cwd=self.tmp.name)
        self.stderr = proc.stderr
        if self.quiet:
            self.assertEqual(proc.stderr, "")
        return proc.stdout

    def rows(self):
        # The logger sends every value but a null count as a JSON string; the real `ledger write` types the
        # numbers, which the stand-in does not, so counts and phase read back as strings here.
        return fake_ledger.recorded_rows(self.env, "review_run")

    def loop(self, *steps):
        return [user("review loop\nlane: code\nphase: 2")] + [rec for step in steps for rec in step] + full_check_run()

    def test_foreground_reports_each_write_a_row_with_their_own_count(self):
        records = self.loop([dispatch("t_smell", "smell-reviewer"), result("t_smell", indented(SMELL_REPORT))],
                            [dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        self.assertEqual(self.stop(records), "")
        rows = {row["gate"]: row for row in self.rows()}
        self.assertEqual({"smell-reviewer": "1", "code-reviewer": "3"},
                         {gate: row["n_findings"] for gate, row in rows.items()})
        code = rows["code-reviewer"]
        self.assertEqual(("review_run", "NEEDS_CHANGES", "code", "2", "s1"),
                         (code["_type"], code["result"], code["lane"], code["phase"], code["_session"]))
        self.assertEqual("PASS_WITH_WARNINGS", rows["smell-reviewer"]["result"])

    def test_a_fix_loop_dispatched_from_a_test_audit_writes_its_run_rows_under_the_test_audit_lane(self):
        records = [user("review loop\nlane: test-audit"), dispatch("t_code", "code-reviewer"),
                   result("t_code", indented(CODE_REPORT)), *full_check_run()]
        self.assertEqual(self.stop(records), "")

        (code,) = self.rows()
        self.assertEqual("test-audit", code["lane"])

    def test_background_reports_arrive_in_the_opposite_order_and_keep_their_own_count(self):
        records = self.loop(
            [dispatch("t_smell", "smell-reviewer"), result("t_smell", "Async agent launched\nagentId: asmell")],
            [dispatch("t_code", "code-reviewer"), result("t_code", "Async agent launched\nagentId: acode")],
            [agent_message("acode", CODE_REPORT)],
            [agent_message("asmell", SMELL_REPORT)],
        )
        self.stop(records)
        counts = {row["gate"]: row["n_findings"] for row in self.rows()}
        self.assertEqual({"smell-reviewer": "1", "code-reviewer": "3"}, counts)

    def test_task_notification_result_and_a_clean_report_with_no_sections(self):
        records = self.loop(
            [dispatch("t_code", "code-reviewer"), result("t_code", "Async agent launched\nagentId: acode")],
            [notification_with_result("t_code", CLEAN_REPORT)],
            [dispatch("t_cx", "complexity-reviewer-deep"), result("t_cx", indented(COMPLEXITY_REPORT))],
        )
        self.stop(records)
        rows = {row["gate"]: row for row in self.rows()}
        self.assertEqual("0", rows["code-reviewer"]["n_findings"])
        self.assertEqual("PASS", rows["code-reviewer"]["result"])
        self.assertEqual("2", rows["complexity-reviewer-deep"]["n_findings"])
        self.assertNotIn("result", rows["complexity-reviewer-deep"])

    def test_a_repeat_stop_on_the_same_dispatches_writes_no_duplicate(self):
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        self.stop(records)
        self.stop(records)
        self.assertEqual(1, len(self.rows()))
        more = [*records, dispatch("t_next", "code-reviewer"), result("t_next", indented(CLEAN_REPORT))]
        self.stop(more)
        self.assertEqual(["3", "0"], [row["n_findings"] for row in self.rows()])

    def test_nothing_is_written_while_the_telemetry_switch_is_off_and_it_is_written_once_on(self):
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        del self.env["CLAUDE_TOOLKIT_TELEMETRY"]
        self.quiet = False
        self.stop(records)
        self.assertEqual([], self.rows())
        self.assertIn("telemetry is off", self.stderr)
        self.quiet = True
        self.env["CLAUDE_TOOLKIT_TELEMETRY"] = "1"
        self.stop(records)
        self.assertEqual(1, len(self.rows()))

    def test_a_run_row_goes_to_the_findings_file_while_ledger_is_off_path_and_is_written_once(self):
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        self.env["PATH"] = fake_ledger.path_without_ledger(self.env["PATH"])
        self.assertIsNone(shutil.which("ledger", path=self.env["PATH"]))
        findings_file = os.path.join(self.home, ".claude", "review-findings.jsonl")
        self.quiet = False
        self.stop(records)
        self.assertEqual([], self.rows())
        self.assertIn("row appended to " + findings_file, self.stderr)
        with open(findings_file, encoding="utf-8") as handle:
            logged = [json.loads(line) for line in handle]
        self.assertEqual(1, len(logged))
        self.assertEqual(("run", "code-reviewer", "s1"), (logged[0]["kind"], logged[0]["gate"], logged[0]["session"]))
        self.stop(records)
        with open(findings_file, encoding="utf-8") as handle:
            self.assertEqual(1, len(handle.readlines()))

    def test_a_row_the_fallback_could_not_append_is_retried_on_the_next_stop(self):
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        self.env["PATH"] = fake_ledger.path_without_ledger(self.env["PATH"])
        findings_file = os.path.join(self.home, ".claude", "review-findings.jsonl")
        os.makedirs(findings_file)
        self.quiet = False
        self.stop(records)
        self.assertIn("row dropped", self.stderr)
        os.rmdir(findings_file)
        self.stop(records)
        with open(findings_file, encoding="utf-8") as handle:
            self.assertEqual(1, len(handle.readlines()))

    def reviewed_worktree(self):
        """A git worktree on its own branch, outside the session cwd."""
        worktree = os.path.join(self.tmp.name, "shop-api-feature")
        os.makedirs(worktree)
        git_env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
        for args in (["init", "-q", "-b", "main"], ["checkout", "-q", "-b", "feature-x"]):
            subprocess.run(["git", *args], cwd=worktree, env=git_env, check=True, capture_output=True)
        return worktree

    def test_a_review_of_a_worktree_outside_the_cwd_logs_that_worktrees_repo_and_branch(self):
        worktree = self.reviewed_worktree()
        review = [dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT)),
                  *full_check_run()]
        scope_call = [bash(f"~/.claude/skills/review/review-scope caller=review root={worktree}", "t_scope"),
                      result("t_scope", f"ROOT={worktree}\nMODE=worktree\n")]
        cases = {"the review-scope ROOT= line": ([user("review loop\nlane: code")], scope_call),
                 "the prompt's repo: line": ([user(f"review loop\nlane: code\nrepo: {worktree}")], [])}
        for case, (prompt, scope) in cases.items():
            with self.subTest(case=case):
                state_dir = os.path.join(self.tmp.name, "state")
                shutil.rmtree(state_dir, ignore_errors=True)
                pathlib.Path(self.env["FAKE_LEDGER_ROWS"]).unlink(missing_ok=True)

                self.assertEqual(self.stop([*prompt, *scope, *review]), "")

                (row,) = self.rows()
                self.assertEqual((row["_cwd"], row["branch_key"]), (os.path.realpath(worktree), "feature-x"))

    def test_a_prompt_repo_that_does_not_exist_writes_the_row_quietly(self):
        review = [dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT)),
                  *full_check_run()]
        missing = os.path.join(self.tmp.name, "no-such-repo")

        self.assertEqual(self.stop([user(f"review loop\nlane: code\nrepo: {missing}"), *review]), "")

        self.assertEqual(1, len(self.rows()))

    def test_the_scope_root_wins_over_a_prompt_repo_on_another_branch(self):
        worktree = self.reviewed_worktree()
        other_repo = os.path.join(self.tmp.name, "other-repo")
        os.makedirs(other_repo)
        git_env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
        subprocess.run(["git", "init", "-q", "-b", "other-branch"], cwd=other_repo, env=git_env, check=True,
                       capture_output=True)
        scope_call = [bash(f"~/.claude/skills/review/review-scope caller=review root={worktree}", "t_scope"),
                      result("t_scope", f"ROOT={worktree}\nMODE=worktree\n")]
        review = [dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT)),
                  *full_check_run()]

        self.assertEqual(self.stop([user(f"review loop\nlane: code\nrepo: {other_repo}"), *scope_call, *review]), "")

        (row,) = self.rows()
        self.assertEqual(row["branch_key"], "feature-x")

    def test_a_run_row_goes_through_ledger_write_and_no_findings_file_is_written(self):
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        self.stop(records)
        self.assertEqual(1, len(self.rows()))
        self.assertEqual([], fake_ledger.recorded_rows(self.env, "review_finding"))
        self.assertFalse(os.path.exists(os.path.join(self.home, ".claude", "review-findings.jsonl")))

    def stop_rows_after_hand_back(self, hand_back_is_error):
        """Stop the loop whose shell moved to the background before its hand-back; return the stop rows."""
        store = os.path.join(self.tmp.name, "store")
        self.env["HANDBACK_STORE_DIR"] = store
        fixture = FIXTURES / "loop_shell_moved_to_background_by_timeout.jsonl"
        with open(fixture, encoding="utf-8") as fh:
            call, moved, _ = map(json.loads, fh)
        hand_back = {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "toolu_handback", "name": "SubagentHandback", "input": {"message": "done"}}]}}
        hand_back_result = {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "toolu_handback", "content": "ok",
             "is_error": hand_back_is_error}]}}
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))],
                            [call, moved, hand_back, hand_back_result])

        self.stop(records)

        with open(os.path.join(store, "s1.jsonl"), encoding="utf-8") as fh:
            return [row for row in map(json.loads, fh) if row["kind"] == "stop"]

    def test_a_shell_moved_to_the_background_before_the_hand_back_does_not_hold_the_run_rows(self):
        stops = self.stop_rows_after_hand_back(hand_back_is_error=False)

        self.assertEqual([0], [row["open_dispatches"] for row in stops])
        self.assertEqual(["code-reviewer"], [row["gate"] for row in self.rows()])

    def test_a_shell_moved_to_the_background_before_a_denied_hand_back_stays_open(self):
        stops = self.stop_rows_after_hand_back(hand_back_is_error=True)

        self.assertEqual([1], [row["open_dispatches"] for row in stops])

    def test_open_background_dispatch_writes_nothing(self):
        records = self.loop(
            [dispatch("t_code", "code-reviewer"), result("t_code", "Async agent launched\nagentId: acode")]
        )
        self.stop(records)
        self.assertEqual([], self.rows())

    def test_a_blocked_stop_writes_nothing(self):
        records = [user("review loop"), dispatch("t_coder", "coder"), result("t_coder", "done"),
                   dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))]
        self.assertIn("No passed full_check.py result", json.loads(self.stop(records))["reason"])
        self.assertEqual([], self.rows())

    def test_a_report_that_cannot_be_counted_still_writes_its_row_with_null(self):
        prose = "## Code Review Summary\n\n### Fix\nThe fix section has prose and no entry."
        records = self.loop(
            [dispatch("t_code", "code-reviewer"), result("t_code", indented(prose))],
            [dispatch("t_other", "perf-reviewer"), result("t_other", "free text, no review heading")],
            [dispatch("t_async", "smell-reviewer"), result("t_async", "Async agent launched\nagentId: alost")],
            [agent_message("alost", "I ran out of budget before I wrote a report.")],
            [dispatch("t_deep", "security-reviewer-deep"), result("t_deep", indented(CODE_REPORT))],
        )
        self.stop(records)
        counts = {row["gate"]: row["n_findings"] for row in self.rows()}
        self.assertEqual({"code-reviewer": None, "perf-reviewer": None, "smell-reviewer": None,
                          "security-reviewer-deep": "3"}, counts)
        self.assertTrue(all("n_findings" in row for row in self.rows()))

    def counted(self, report, gate="code-reviewer"):
        tool_use_id = f"t_{len(self.rows())}"
        self.stop(self.loop([dispatch(tool_use_id, gate), result(tool_use_id, indented(report))]))
        return self.rows()[-1]["n_findings"]

    def test_findings_are_counted_by_section_shape_not_by_lines_that_look_like_findings(self):
        header = "## Code Review Summary\n\n**Overall Assessment**: NEEDS CHANGES\n\n"
        cases = {
            "lines inside code fences are not findings or headings": (
                header + "### Fix\n- a.py:1 — real\n```\n- b.py:2 — quoted in a fence\n### Ask\n```\n"
                "- c.py:3 — also real\n\n### Ask\nNone.", "2"),
            "a deeper heading stays inside the findings section": (
                header + "### Fix\n#### Correctness\n- a.py:1 — one\n#### Tests\n- b.py:2 — two", "2"),
            "bold and plural section headings are findings sections": (
                header + "### **Fix**\n- a.py:1 — one\n\n### Fixes\n- b.py:2 — two", "2"),
            "a none marker counts only when it is the whole line": (
                header + "### Ask\nNone of the above is a blocker, but this is:\n- a.py:1 — real", "1"),
        }

        for name, (report, expected) in cases.items():
            with self.subTest(name):
                self.assertEqual(expected, self.counted(report))

    def test_zero_entries_under_a_failing_assessment_is_uncounted(self):
        needs = "## Code Review Summary\n\n**Overall Assessment**: NEEDS CHANGES\n\n### Fix\nNone.\n\n### Nit\n- a nit"
        self.assertIsNone(self.counted(needs))
        warned = "## Code Review Summary\n\n**Overall Assessment**: PASS WITH WARNINGS\n\n### Fix\nNone."
        self.assertIsNone(self.counted(warned))
        nit_only = "## Structure Review Summary\n\n**Overall Assessment**: PASS WITH WARNINGS\n\n### Nit\none nit line"
        self.assertEqual("0", self.counted(nit_only))
        clean = "## Code Review Summary\n\n**Overall Assessment**: PASS\n\n### Fix\nNone."
        self.assertEqual("0", self.counted(clean))

    def test_two_notifications_in_one_record_do_not_lend_a_result_across_the_boundary(self):
        both = ("<task-notification><tool-use-id>t_smell</tool-use-id><status>killed</status></task-notification>"
                f"<task-notification><tool-use-id>t_code</tool-use-id><result>{indented(CODE_REPORT)}</result></task-notification>")
        records = self.loop(
            [dispatch("t_smell", "smell-reviewer"), result("t_smell", "Async agent launched\nagentId: asmell")],
            [dispatch("t_code", "code-reviewer"), result("t_code", "Async agent launched\nagentId: acode")],
            [{"type": "attachment", "attachment": {"type": "queued_command", "prompt": both}}],
        )
        self.stop(records)
        counts = {row["gate"]: row["n_findings"] for row in self.rows()}
        self.assertEqual({"smell-reviewer": None, "code-reviewer": "3"}, counts)

    def test_an_agent_message_ends_at_the_next_agent_message(self):
        both = user(
            '<agent-message from="asmell">\n{}\n<agent-message from="acode">\n{}'.format(
                "I stopped early.", indented(CODE_REPORT)
            )
        )
        records = self.loop(
            [dispatch("t_smell", "smell-reviewer"), result("t_smell", "Async agent launched\nagentId: asmell")],
            [dispatch("t_code", "code-reviewer"), result("t_code", "Async agent launched\nagentId: acode")],
            [both],
        )
        self.stop(records)
        counts = {row["gate"]: row["n_findings"] for row in self.rows()}
        self.assertEqual({"smell-reviewer": None, "code-reviewer": "3"}, counts)

    def test_an_unwritable_state_folder_skips_the_row_and_the_stop_still_passes(self):
        blocker = os.path.join(self.tmp.name, "blocker")
        with open(blocker, "w") as fh:
            fh.write("a file where the folder should go")
        self.env["REVIEW_LOOP_GATE_STATE_DIR"] = os.path.join(blocker, "state")
        self.quiet = False
        out = self.stop(self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))]))
        self.assertEqual("", out)
        self.assertEqual([], self.rows())
        self.assertIn("run rows skipped", self.stderr)

    def test_logger_stores_null_and_digit_counts_and_still_refuses_a_run_row_without_the_key(self):
        logger = os.path.join(self.env["REVIEW_LOOP_GATE_CLAUDE_DIR"], "skills", "review", "log-review-finding")

        def log(*args):
            return subprocess.run(["bash", logger, "kind=run", "gate=code-reviewer", *args],
                                  capture_output=True, text=True, env=self.env, cwd=self.tmp.name)

        self.assertEqual(0, log("n_findings=null").returncode)
        self.assertEqual(0, log("n_findings=0").returncode)
        self.assertEqual(0, log("n_findings=4").returncode)
        refused = log()
        self.assertEqual(1, refused.returncode)
        self.assertIn("needs n_findings", refused.stderr)
        self.assertEqual([None, "0", "4"], [row["n_findings"] for row in self.rows()])

    def test_prose_before_between_and_after_entries_does_not_stop_the_count(self):
        report = """## Code Review Summary

**Overall Assessment**: NEEDS CHANGES

### Fix
These are the flagged items, in order.
- **a.py:10** [gate: x] the first entry
  - sub bullet detail that is not a finding
Some prose between entries.
- [fix | gate: y] b.py:4 — the second entry, a bullet with its tags first
- bare bullet with no path at all

### Ask
None.
- not a finding, the section opened with none

### Nit
- a nit"""
        self.stop(self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(report))]))
        self.assertEqual(["3"], [row["n_findings"] for row in self.rows()])

    def test_test_reviewer_counts_the_items_of_every_topic_section_but_the_action_summary(self):
        report = """## Test Review Report

**Scope**: branch
**Overall health**: ADEQUATE

All tests pass. Two gaps.

---

### Assertions the Spec Does Not Support

None.
The edited assertions match:
- line 678 matches D9

### Coverage Gaps in Business Logic

1. `fix`: **x has no test.** In a.rs it is gated.

2. `ask`: **y** is unclear.
   - **Add** a test.

### Test Hygiene Issues (`nit`)

- tests/a.rs:3 — name does not state the outcome

---

### Summary of Recommended Actions

1. Do the first thing.
2. Do the second thing."""
        self.stop(self.loop([dispatch("t_tr", "test-reviewer"), result("t_tr", indented(report))]))
        row = self.rows()[0]
        self.assertEqual(("test-reviewer", "3"), (row["gate"], row["n_findings"]))

    def test_test_intent_audit_counts_its_finding_sections_and_not_the_aligned_count(self):
        report = """## Test-Intent Audit

**Verdict**: BUG-PINNING DETECTED

### BUG-PINNING — assertion encodes current output, not intent
- a_test.py:10 — pins 3, spec says 4

### CULL — no bug would fail this test
- a_test.py:20 — constant echo
- a_test.py:30 — mock echo

### INTENT-ALIGNED (summary count)
- 14 assertions are fine

### Recommended actions
1. Change the first one.
2. Delete the other two."""
        self.stop(self.loop([dispatch("t_ti", "test-intent-reviewer"), result("t_ti", indented(report))]))
        self.assertEqual(["3"], [row["n_findings"] for row in self.rows()])

    def test_a_non_reviewer_dispatch_writes_no_row(self):
        records = self.loop([dispatch("t_other", "general-purpose"), result("t_other", indented(CODE_REPORT))])
        self.stop(records)
        self.assertEqual([], self.rows())


def run_dispatch_hook(prompt, **caller):
    """The gate's stdout for a review-loop Agent dispatch with this prompt, from the caller the fields name."""
    hook = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "session-1", **caller,
            "tool_input": {"subagent_type": "review-loop", "prompt": prompt}}
    environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
    proc = subprocess.run([sys.executable, "-B", SCRIPT], input=json.dumps(hook), capture_output=True,
                          text=True, check=True, env=environment)
    return proc.stdout


class HandoffDispatchTest(unittest.TestCase):
    def test_a_review_loop_dispatch_from_code_without_a_handoff_is_refused(self):
        denial = json.loads(run_dispatch_hook("caller: code\nno handoff"))
        self.assertIn("handoff", denial["hookSpecificOutput"]["permissionDecisionReason"])


REVIEW_PROMPT = "mode: review-first\ncaller: review"


class NestedDispatchTest(unittest.TestCase):
    def test_a_review_loop_dispatch_from_a_lane_subagent_is_refused_with_the_main_session_route(self):
        denial = json.loads(run_dispatch_hook(REVIEW_PROMPT, agent_id="lane-1", agent_type="general-purpose"))
        reason = denial["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertEqual("deny", denial["hookSpecificOutput"]["permissionDecision"])
        self.assertIn("main session", reason)

    def test_a_review_loop_dispatch_from_the_main_session_or_the_code_fork_passes(self):
        cases = [("the main session", {}),
                 ("the /code fork", {"agent_id": "fork-1", "agent_type": "code-fork"})]
        for message, caller in cases:
            with self.subTest(message):
                self.assertEqual("", run_dispatch_hook(REVIEW_PROMPT, **caller))


LOG_METRICS = "~/.claude/skills/review/log-review-metrics lane=code iter=1 fix=0 ask=0 nit=0 fixed=0 result=PASS"


class MetricsTimingTest(unittest.TestCase):
    def metrics_hook(self, records, command=LOG_METRICS, agent_type="review-loop"):
        """The gate's stdout for a Bash call from a loop whose transcript holds these records."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "loop.jsonl")
        with open(path, "w", encoding="utf-8") as fh:
            for rec in records:
                fh.write(json.dumps(rec) + "\n")
        hook = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "agent_type": agent_type,
                "agent_id": "loop-1", "agent_transcript_path": path, "tool_input": {"command": command}}
        environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
        proc = subprocess.run([sys.executable, "-B", SCRIPT], input=json.dumps(hook), capture_output=True,
                              text=True, check=True, env=environment)
        self.assertEqual(proc.stderr, "")
        return proc.stdout

    def assert_denied(self, output):
        denial = json.loads(output)["hookSpecificOutput"]
        self.assertEqual("deny", denial["permissionDecision"])
        self.assertIn("reviewer", denial["permissionDecisionReason"])

    def test_metrics_call_before_any_reviewer_dispatch_is_denied(self):
        self.assert_denied(self.metrics_hook([user("mode: review-first"), bash("git status")]))

    def test_metrics_call_while_the_reviewer_is_still_open_is_denied(self):
        records = [user("mode: review-first"), dispatch("toolu_rev", "code-reviewer"),
                   result("toolu_rev", ASYNC_RESULT)]
        self.assert_denied(self.metrics_hook(records))

    def test_metrics_call_after_the_reviewer_reported_passes(self):
        records = [user("mode: review-first"), dispatch("toolu_rev", "code-reviewer"),
                   result("toolu_rev", ASYNC_RESULT), notification("toolu_rev")]
        self.assertEqual("", self.metrics_hook(records))

    def test_metrics_call_in_no_review_mode_passes_with_no_reviewer(self):
        self.assertEqual("", self.metrics_hook([user("no-review\nlane: code")]))

    def test_a_call_that_logs_no_metrics_passes(self):
        self.assertEqual("", self.metrics_hook([user("mode: review-first")], command="git status"))

    def test_a_metrics_call_from_another_agent_passes(self):
        self.assertEqual("", self.metrics_hook([user("mode: review-first")], agent_type="coder"))


if __name__ == "__main__":
    unittest.main()


PACKET = json.dumps({"status": "converged", "iter": 1,
                     "fixed": [{"finding": "null deref", "file_line": "a.py:3", "blocker": False}],
                     "skipped_fp": [], "ask": [], "class_closure": "n/a - fixed[] empty",
                     "files_touched": ["a.py", "%s"], "nit": []})
FINDING_ROW = ("~/.claude/skills/review/log-review-finding kind=finding lane=code scope=phase iter=1 "
               "gate=code-reviewer disposition=fix class=bug file=a.py line=3 actioned=fixed")
METRICS_ROW = "~/.claude/skills/review/log-review-metrics lane=code iter=1 fix=1 ask=0 nit=0 fixed=1 result=PASS"


class LedgerRowsTest(StopHookMixin, unittest.TestCase):
    def loop(self, *rows, plan="spec.md"):
        return [user(f"review loop\nlane: code\nplan: {plan}"), *full_check_run(),
                *[bash(row) for row in rows]]

    def stop_with_packet(self, records, touched="spec.md"):
        return self.stop(records, last_assistant_message=PACKET % touched)

    def test_a_packet_with_a_fixed_finding_and_no_finding_row_is_blocked_once(self):
        records = self.loop(METRICS_ROW, plan="other.md")
        reason = json.loads(self.stop_with_packet(records, touched="b.py"))["reason"]
        self.assertIn("1 finding(s)", reason)
        self.assertIn("only 0 per-finding", reason)

    def test_a_missing_metrics_line_is_blocked(self):
        reason = json.loads(self.stop_with_packet(self.loop(FINDING_ROW, plan="other.md"), "b.py"))["reason"]
        self.assertIn("no metrics line", reason)

    def test_every_row_logged_passes(self):
        self.assertEqual(self.stop_with_packet(self.loop(FINDING_ROW, METRICS_ROW, plan="other.md"), "b.py"), "")

    def test_a_metrics_line_logged_before_the_last_reviewer_round_is_blocked(self):
        records = [user("review loop\nlane: code\nplan: other.md"), bash(METRICS_ROW),
                   dispatch("t_verify", "code-reviewer"), result("t_verify", "ok"),
                   *full_check_run(), bash(FINDING_ROW)]

        reason = json.loads(self.stop_with_packet(records, "b.py"))["reason"]

        self.assertIn("before the last reviewer round", reason)
        self.assertIn("fixed=1, skipped_fp=0", reason)
        self.assertEqual(self.stop_with_packet([*records, bash(METRICS_ROW)], "b.py"), "")

    def test_a_nit_with_no_nit_row_is_blocked_even_when_the_row_total_matches(self):
        packet = (PACKET % "b.py").replace('"nit": []', '"nit": ["b.py:4 rename x - applied"]')
        doubled = FINDING_ROW.replace("line=3", "line=5")
        records = self.loop(FINDING_ROW, doubled, METRICS_ROW, plan="other.md")

        reason = json.loads(self.stop(records, last_assistant_message=packet))["reason"]

        self.assertIn("1 nit(s) but only 0 `disposition=nit` row(s)", reason)
        nit_row = FINDING_ROW.replace("disposition=fix", "disposition=nit")
        self.assertEqual(self.stop(self.loop(FINDING_ROW, nit_row, METRICS_ROW, plan="other.md"),
                                   last_assistant_message=packet), "")

    def test_a_delivered_stop_with_missing_nit_rows_tells_the_loop_to_stop_not_return_the_packet(self):
        packet = (PACKET % "b.py").replace('"nit": []', '"nit": ["b.py:4 rename x - applied"]')
        doubled = FINDING_ROW.replace("line=3", "line=5")
        handing_back = {"type": "tool_use", "id": "toolu_hb", "name": "SubagentHandback",
                        "input": {"message": '{"status": "converged"}'}}
        delivered = [{"type": "assistant", "message": {"role": "assistant", "content": [handing_back]}},
                     result("toolu_hb", "delivered")]
        records = [*self.loop(FINDING_ROW, doubled, METRICS_ROW, plan="other.md"), *delivered]

        reason = json.loads(self.stop(records, last_assistant_message=packet))["reason"]

        self.assertIn("1 nit(s) but only 0 `disposition=nit` row(s)", reason)
        self.assertIn("already delivered", reason)
        self.assertNotIn("return the packet", reason)

    def test_a_metrics_line_whose_counts_differ_from_the_packet_is_blocked(self):
        undercount = METRICS_ROW.replace("fixed=1", "fixed=0 skipped_fp=0")

        reason = json.loads(self.stop_with_packet(self.loop(FINDING_ROW, undercount, plan="other.md"), "b.py"))

        self.assertIn("fixed=1, skipped_fp=0", reason["reason"])

    def test_a_metrics_count_mismatch_is_blocked_when_the_call_spans_lines_or_is_followed_by_another_command(self):
        cases = {
            "fixed on the second line": METRICS_ROW.replace("fixed=1", "\\\n  fixed=0 skipped_fp=0"),
            "fixed=1 in a command that follows": METRICS_ROW.replace("fixed=1", "fixed=0") + " && echo fixed=1",
            "skipped_fp alone differs": METRICS_ROW + " skipped_fp=2",
        }
        for case, metrics_call in cases.items():
            with self.subTest(case=case):
                records = self.loop(FINDING_ROW, metrics_call, plan="other.md")

                reason = json.loads(self.stop_with_packet(records, "b.py"))["reason"]

                self.assertIn("fixed=1, skipped_fp=0", reason)

    def test_a_metrics_call_the_logger_refused_does_not_count_as_logged(self):
        refusals = {"an error result": {"is_error": True, "text": "exit 2"},
                    "the refusal text": {"is_error": False, "text": "log-review-metrics: refusing to log: result='x'"}}
        for case, refusal in refusals.items():
            with self.subTest(case=case):
                refused = {"type": "tool_result", "tool_use_id": "t_metrics", "is_error": refusal["is_error"],
                           "content": [{"type": "text", "text": refusal["text"]}]}
                records = [*self.loop(FINDING_ROW, plan="other.md"), bash(METRICS_ROW, "t_metrics"),
                           {"type": "user", "message": {"role": "user", "content": [refused]}}]

                reason = json.loads(self.stop_with_packet(records, "b.py"))["reason"]

                self.assertIn("no metrics line", reason)

    def test_a_refused_metrics_call_chained_after_a_finding_call_does_not_count_as_logged(self):
        refused = {"type": "tool_result", "tool_use_id": "t_both", "is_error": True,
                   "content": [{"type": "text", "text": "log-review-metrics: refusing to log: result='bogus'"}]}
        chained = bash(FINDING_ROW + " && " + METRICS_ROW.replace("result=PASS", "result=bogus"), "t_both")
        records = [*self.loop(plan="other.md"), chained,
                   {"type": "user", "message": {"role": "user", "content": [refused]}}]

        reason = json.loads(self.stop_with_packet(records, "b.py"))["reason"]

        self.assertIn("no metrics line", reason)

    def test_a_nit_row_written_in_the_documented_multi_line_form_counts(self):
        packet = (PACKET % "b.py").replace('"nit": []', '"nit": ["b.py:4 rename x - applied"]')
        multi_line = FINDING_ROW.replace(" disposition=fix", " \\\n  disposition=%s")
        fix_row, nit_row = multi_line % "fix", multi_line % "nit"

        blocked = self.loop(FINDING_ROW, fix_row, METRICS_ROW, plan="other.md")
        reason = json.loads(self.stop(blocked, last_assistant_message=packet))["reason"]
        self.assertIn("1 nit(s) but only 0 `disposition=nit` row(s)", reason)

        logged = [user("review loop\nlane: code\nplan: other.md"), *full_check_run(),
                  bash(FINDING_ROW, "t_fix"), bash(nit_row, "t_nit"), bash(METRICS_ROW, "t_metrics")]
        self.assertEqual(self.stop(logged, last_assistant_message=packet), "")

    def test_a_nit_row_whose_disposition_is_a_shell_variable_leaves_the_nit_count_unclaimed(self):
        packet = (PACKET % "b.py").replace('"nit": []', '"nit": ["b.py:4 rename x - applied"]')
        variable_row = FINDING_ROW.replace("disposition=fix", "disposition=$D")
        records = [user("review loop\nlane: code\nplan: other.md"), *full_check_run(),
                   bash(FINDING_ROW, "t_fix"), bash(variable_row, "t_variable"), bash(METRICS_ROW, "t_metrics")]

        self.assertEqual(self.stop(records, last_assistant_message=packet), "")

    def test_a_second_stop_in_a_row_passes(self):
        records = self.loop(plan="other.md")
        self.assertEqual(self.stop(records, last_assistant_message=PACKET % "b.py", stop_hook_active=True), "")

    def test_a_plan_file_in_files_touched_is_blocked(self):
        records = self.loop(FINDING_ROW, METRICS_ROW)
        reason = json.loads(self.stop_with_packet(records))["reason"]
        self.assertIn("never edits the plan", reason)

    def test_a_plan_file_in_files_touched_after_a_delivered_hand_back_passes(self):
        handing_back = {"type": "tool_use", "id": "toolu_hb", "name": "SubagentHandback",
                        "input": {"message": '{"status": "converged"}'}}
        delivered = [{"type": "assistant", "message": {"role": "assistant", "content": [handing_back]}},
                     result("toolu_hb", "delivered")]

        self.assertEqual(self.stop_with_packet([*self.loop(FINDING_ROW, METRICS_ROW), *delivered]), "")

    def test_a_plan_path_that_ends_in_the_touched_path_is_blocked(self):
        records = self.loop(FINDING_ROW, METRICS_ROW, plan="/repo/docs/spec.md")
        self.assertIn("never edits the plan", json.loads(self.stop_with_packet(records, "docs/spec.md"))["reason"])
