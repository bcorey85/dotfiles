import importlib.util
import json
import os
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


class ReviewLoopGateTest(unittest.TestCase):
    def stop(self, records, **extra):
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
        self.assertEqual(proc.stderr, "")
        return proc.stdout

    def test_open_background_dispatch_passes(self):
        self.assertEqual(self.stop(coder_and_background_reviewer()), "")

    def test_reported_background_dispatch_blocks_without_full_check(self):
        out = self.stop([*coder_and_background_reviewer(), notification("toolu_rev")])
        self.assertIn("No full check ran", json.loads(out)["reason"])

    def test_agent_message_counts_as_reported(self):
        message = user('<agent-message from="a7bf12f9c51bc4875">findings</agent-message>')
        out = self.stop([*coder_and_background_reviewer(), message])
        self.assertIn("No full check ran", json.loads(out)["reason"])

    def test_foreground_dispatch_blocks(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "agentId: a7bf12f9c51bc4875")]
        self.assertIn("No full check ran", json.loads(self.stop(records))["reason"])

    def test_full_check_after_reviewed_coder_passes(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "ok"),
                   bash("npm test > /tmp/review-gate.log 2>&1")]
        self.assertEqual(self.stop(records), "")

    def test_a_fix_coder_after_the_last_review_needs_only_the_full_check(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "ok"),
                   dispatch("toolu_fix", "coder"), result("toolu_fix", "done")]
        self.assertIn("No full check ran", json.loads(self.stop(records))["reason"])
        self.assertEqual(self.stop([*records, bash("npm test > /tmp/review-gate.log 2>&1")]), "")

    def test_a_message_to_a_coder_after_the_full_check_counts_as_a_code_change(self):
        records = [user("review loop"),
                   dispatch("toolu_coder", "coder"), result("toolu_coder", "agentId: acoder1"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", "ok"),
                   bash("npm test > /tmp/review-gate.log 2>&1")]
        self.assertEqual(self.stop(records), "")
        out = self.stop([*records, send_message("acoder1")])
        self.assertIn("No full check ran", json.loads(out)["reason"])

    def test_stop_hook_active_passes(self):
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done")]
        self.assertEqual(self.stop(records, stop_hook_active=True), "")

    def test_a_foreground_report_that_quotes_the_launch_text_is_not_an_open_dispatch(self):
        report = "Reviewed the gate. It counts `Async agent launched` results as open dispatches.\nagentId: arev1"
        records = [user("review loop"), dispatch("toolu_coder", "coder"), result("toolu_coder", "done"),
                   dispatch("toolu_rev", "code-reviewer"), result("toolu_rev", report)]
        self.assertIn("No full check ran", json.loads(self.stop(records))["reason"])


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
                    bash("npm test > /tmp/review-gate.log 2>&1")]
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
        checked = [*unchecked, bash("npm test > /tmp/review-gate.log 2>&1")]
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
        self.assertEqual((torn.stdout, missing.stdout), ("", ""))
        self.assertIn("skipped", torn.stderr)
        self.assertIn("skipped", missing.stderr)
        self.assertEqual(self.open_counts(store), [1, 0, 0])

    def test_a_resume_result_with_only_the_short_id_matches_the_launched_agent_by_prefix(self):
        store = self.new_store()
        short_only = [*resume_background_coder()[:-1], result("toolu_resume", "Resuming agent a5bc2eb")]
        self.stop_in_session(short_only, store)
        self.stop_in_session([*short_only, notification("toolu_resume")], store)
        self.assertEqual(self.open_counts(store), [1, 0])

    def test_a_non_object_transcript_line_writes_a_zero_row_and_still_fails_open(self):
        store = self.new_store()
        self.stop_in_session(coder_and_background_reviewer(), store)
        done = self.stop_in_session([*coder_and_background_reviewer(), "[]"], store)
        self.assertEqual(done.stdout, "")
        self.assertIn("skipped", done.stderr)
        self.assertEqual(self.open_counts(store), [1, 0])

    def test_a_background_resume_is_open_until_a_later_notification_or_agent_message(self):
        store = self.new_store()
        resumed = resume_background_coder()
        self.stop_in_session(resumed, store)
        self.stop_in_session([*resumed, notification("toolu_resume")], store)
        message = user('<agent-message from="a5bc2ebfa0d6aeaf8">done</agent-message>')
        self.stop_in_session([*resumed, message], store)
        self.assertEqual(self.open_counts(store), [1, 0, 0])


class FullCheckTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("review_loop_gate_under_test", SCRIPT)
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def assert_full(self, command):
        self.assertTrue(self.gate.full_check(command), command)

    def assert_scoped(self, command):
        self.assertFalse(self.gate.full_check(command), command)

    def test_the_commands_two_loops_ran_as_their_full_check_count(self):
        self.assert_full("cargo test --manifest-path /home/brandon/dev/agent-ledger-LED-12/Cargo.toml"
                        " > /tmp/review-gate.log 2>&1; echo exit=$?")
        self.assert_full("cargo test --manifest-path /home/brandon/dev/agent-ledger-LED-2/Cargo.toml"
                        " > /tmp/review-gate.log 2>&1; echo exit=$?; tail -4 /tmp/review-gate.log")

    def test_the_value_of_a_package_or_project_flag_does_not_scope_a_run(self):
        for command in ("cargo test --manifest-path=/r/a/Cargo.toml",
                        "cargo test --manifest-path /r/a/Cargo.toml --release",
                        "cargo test -p core",
                        "cargo test -p crates/core",
                        "cargo test --package ledger-core --release",
                        "cargo test --package crates/core",
                        "cargo test --workspace",
                        "cargo clippy --workspace -- -D warnings",
                        "npx tsc --project packages/web/tsconfig.json",
                        "npx tsc --project=packages/web/tsconfig.json --noEmit",
                        "cargo test --manifest-path '/r/my app/Cargo.toml'"):
            with self.subTest(command=command):
                self.assert_full(command)

    def test_each_checker_ignores_the_value_of_the_flags_that_name_its_package_or_project(self):
        for command in ("pytest -p plugins/x",
                        "go vet -p pkg/x",
                        "mypy -p ledger/core",
                        "pyright -p packages/web",
                        "npx tsc -p packages/web",
                        "npx vitest --project packages/web",
                        "dotnet test --project src/App"):
            with self.subTest(command=command):
                self.assert_full(command)

    def test_a_test_name_filter_or_a_trailing_test_target_still_scopes_a_run(self):
        for command in ("pytest -k login",
                        "pytest -p xdist tests/a.py",
                        "pytest -p xdist -k login",
                        "npx jest --grep slow",
                        "go test -run TestX ./...",
                        "cargo test --manifest-path /r/a/Cargo.toml tests/foo.rs",
                        "cargo test --manifest-path /r/a/Cargo.toml -- --exact parser::tests::empty",
                        "cargo test -p core parser::tests",
                        "cargo test --package core -- --exact a::b",
                        "npm test --workspace packages/web"):
            with self.subTest(command=command):
                self.assert_scoped(command)

    def test_a_flag_that_names_a_package_for_one_checker_can_name_a_test_file_for_another(self):
        for command in ("bats -p test/login.bats",
                        "rspec -p spec/models/user_spec.rb",
                        "bundle exec rspec -p spec/models/user_spec.rb",
                        "cargo test --project foo/bar",
                        "pytest --project a/b",
                        "npx vitest -p a/b"):
            with self.subTest(command=command):
                self.assert_scoped(command)

    def test_a_flag_value_in_one_command_does_not_hide_a_scope_in_the_next(self):
        self.assert_scoped("cargo test -p core && cargo test tests/foo.rs")

    def test_a_flag_at_the_end_of_its_command_takes_no_value_from_the_next_one(self):
        self.assert_scoped("cargo test -p; pytest tests/a.py")


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
        return [user("review loop\nlane: code\nphase: 2")] + [rec for step in steps for rec in step] + [
            bash("npm test > /tmp/review-gate.log 2>&1")]

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
                   result("t_code", indented(CODE_REPORT)), bash("npm test > /tmp/review-gate.log 2>&1")]
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

    def test_a_run_row_is_dropped_with_one_writer_line_and_no_file_while_ledger_is_off_path(self):
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        path_with_ledger = self.env["PATH"]
        self.env["PATH"] = fake_ledger.path_without_ledger(path_with_ledger)
        self.assertIsNone(shutil.which("ledger", path=self.env["PATH"]))
        findings_file = os.path.join(self.home, ".claude", toolkit_paths.local_stream_file("review-findings"))
        self.quiet = False
        self.stop(records)
        self.assertEqual([], self.rows())
        self.assertIn("ledger not on PATH; review_run row dropped", self.stderr)
        self.assertFalse(os.path.exists(findings_file))
        self.env["PATH"] = path_with_ledger
        self.stop(records)
        self.assertEqual(1, len(self.rows()))

    def test_a_missing_telemetry_script_skips_the_row_with_a_stderr_line(self):
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        claude_dir = self.env["REVIEW_LOOP_GATE_CLAUDE_DIR"]
        scripts_link = os.path.join(claude_dir, "scripts")
        os.remove(scripts_link)
        os.makedirs(scripts_link)
        for name in os.listdir(SCRIPTS_ROOT):
            if name != "telemetry":
                os.symlink(os.path.join(SCRIPTS_ROOT, name), os.path.join(scripts_link, name))
        telemetry_link = os.path.join(scripts_link, "telemetry")
        os.makedirs(telemetry_link)
        for name in os.listdir(os.path.join(SCRIPTS_ROOT, "telemetry")):
            if name != "telemetry_enabled.sh":
                os.symlink(os.path.join(SCRIPTS_ROOT, "telemetry", name), os.path.join(telemetry_link, name))
        self.quiet = False
        self.stop(records)
        self.assertEqual([], self.rows())
        self.assertIn("telemetry_enabled.sh is missing", self.stderr)

    def test_a_run_row_goes_through_ledger_write_and_no_findings_file_is_written(self):
        records = self.loop([dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))])
        self.stop(records)
        self.assertEqual(1, len(self.rows()))
        self.assertEqual([], fake_ledger.recorded_rows(self.env, "review_finding"))
        findings_file = os.path.join(self.home, ".claude", toolkit_paths.local_stream_file("review-findings"))
        self.assertFalse(os.path.exists(findings_file))

    def test_open_background_dispatch_writes_nothing(self):
        records = self.loop(
            [dispatch("t_code", "code-reviewer"), result("t_code", "Async agent launched\nagentId: acode")]
        )
        self.stop(records)
        self.assertEqual([], self.rows())

    def test_a_blocked_stop_writes_nothing(self):
        records = [user("review loop"), dispatch("t_coder", "coder"), result("t_coder", "done"),
                   dispatch("t_code", "code-reviewer"), result("t_code", indented(CODE_REPORT))]
        self.assertIn("No full check ran", json.loads(self.stop(records))["reason"])
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

    def test_lines_inside_code_fences_are_not_findings_or_headings(self):
        report = """## Code Review Summary

**Overall Assessment**: NEEDS CHANGES

### Fix
- a.py:1 — real
```
- b.py:2 — quoted in a fence
### Ask
```
- c.py:3 — also real

### Ask
None."""
        self.assertEqual("2", self.counted(report))

    def test_a_deeper_heading_stays_inside_the_findings_section(self):
        report = """## Code Review Summary

**Overall Assessment**: NEEDS CHANGES

### Fix
#### Correctness
- a.py:1 — one
#### Tests
- b.py:2 — two"""
        self.assertEqual("2", self.counted(report))

    def test_bold_and_plural_section_headings_are_findings_sections(self):
        report = """## Code Review Summary

**Overall Assessment**: NEEDS CHANGES

### **Fix**
- a.py:1 — one

### Fixes
- b.py:2 — two"""
        self.assertEqual("2", self.counted(report))

    def test_a_none_marker_counts_only_when_it_is_the_whole_line(self):
        report = """## Code Review Summary

**Overall Assessment**: NEEDS CHANGES

### Ask
None of the above is a blocker, but this is:
- a.py:1 — real"""
        self.assertEqual("1", self.counted(report))

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


class HandoffDispatchTest(unittest.TestCase):
    def test_a_review_loop_dispatch_from_code_without_a_handoff_is_refused(self):
        hook = {"hook_event_name": "PreToolUse", "tool_name": "Agent",
                "tool_input": {"subagent_type": "review-loop", "prompt": "caller: code\nno handoff"}}
        environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
        proc = subprocess.run([sys.executable, "-B", SCRIPT], input=json.dumps(hook), capture_output=True,
                              text=True, check=True, env=environment)
        self.assertIn("handoff", json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()


PACKET = """status: converged
iter: 1
fixed: [{finding: "null deref", file_line: "a.py:3", blocker: no}]
skipped_fp: []
ask: []
class_closure: n/a — fixed[] empty
files_touched: [a.py, %s]
nit: []"""
FINDING_ROW = ("~/.claude/skills/review/log-review-finding kind=finding lane=code scope=phase iter=1 "
               "gate=code-reviewer disposition=fix class=bug file=a.py line=3 actioned=fixed")
METRICS_ROW = "~/.claude/skills/review/log-review-metrics lane=code iter=1 fix=1 ask=0 nit=0 fixed=1 result=PASS"


class LedgerRowsTest(ReviewLoopGateTest):
    def loop(self, *rows, plan="spec.md"):
        return [user(f"review loop\nlane: code\nplan: {plan}"), bash("npm test > /tmp/review-gate.log 2>&1"),
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

    def test_a_second_stop_in_a_row_passes(self):
        records = self.loop(plan="other.md")
        self.assertEqual(self.stop(records, last_assistant_message=PACKET % "b.py", stop_hook_active=True), "")

    def test_a_plan_file_in_files_touched_is_blocked(self):
        records = self.loop(FINDING_ROW, METRICS_ROW)
        reason = json.loads(self.stop_with_packet(records))["reason"]
        self.assertIn("never edits the plan", reason)

    def test_a_plan_path_that_ends_in_the_touched_path_is_blocked(self):
        records = self.loop(FINDING_ROW, METRICS_ROW, plan="/repo/docs/spec.md")
        self.assertIn("never edits the plan", json.loads(self.stop_with_packet(records, "docs/spec.md"))["reason"])
