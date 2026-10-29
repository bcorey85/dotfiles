import json
import os
import pathlib
import subprocess
import tempfile
import time
import unittest

import fake_ledger
import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("REVIEW_FIX_SCRIPT") or toolkit_paths.REVIEW_DIR / "review_fix.py")
HANDBACK = SCRIPT.parent / "handback.py"
LOOP_GATE = SCRIPT.parent / "review_loop_gate.py"
SESSION = "11111111-aaaa-bbbb-cccc-222222222222"
OTHER_SESSION = "99999999-aaaa-bbbb-cccc-888888888888"
CLAUDE_DIR = pathlib.Path(os.environ.get("REVIEW_FIX_CLAUDE_DIR") or toolkit_paths.CLAUDE_DIR)

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}

CONVERGED = """status: converged
iter: 1
fixed: [{finding: "orders query lacked a tenant filter", file_line: src/orders.ts:42, blocker: true},
        {finding: "unused import", file_line: src/util.ts:3, blocker: false}]
skipped_fp: [{item: "src/a.ts:9 possible null", reason: "guarded two lines above"}]
blockers: []
findings_remaining: []
plan_impact:
ask: []
class_closure: enumerated every query in orders.ts; the tenant filter now sits on all 3
files_touched: [src/orders.ts, src/util.ts]
nit: ["rename tmp: skipped: out of scope"]
load_bearing_clean: auth.ts came back clean but is load-bearing
"""

CLEAN_EMPTY = """status: converged
iter: 0
fixed: []
skipped_fp: []
ask: []
class_closure: n/a - fixed[] empty
files_touched: []
nit: []
"""

WITH_ASK = (
    """status: converged
iter: 1
fixed: []
ask:
  - finding: "retry count looks arbitrary"
    finding_id: a1b2c3d4e5f60001
    file_line: src/retry.ts:10
    question: "Should retries be capped at 3 or configurable?"
    change: "cap retries at 3"
    gate: code-reviewer
    class: smell
"""
    '  - {finding: "no index", finding_id: a1b2c3d4e5f60002, file_line: src/db.ts:5, '
    'question: "Add an index on tenant_id?", change: "add an index on tenant_id", gate: perf-reviewer, '
    'class: perf}\n'
    """class_closure: n/a - fixed[] empty
"""
)

PLAN_IMPACT = """status: plan-impact
iter: 1
spec_iter: 2
plan_impact: |
  PLAN-IMPACT:
    assumed: the queue is at-least-once
    found: the queue is at-most-once
    changes: phase 3 needs a dedupe table
"""

BLOCKER = """status: critical-blocker
iter: 1
blockers:
  - "auth bypass needs a design decision: src/auth.ts:12"
  - "public API field rename"
"""

SETUP_FAULT = """status: setup-fault
iter: 1
blockers:
  - "the full check could not run: no package.json"
"""

CAP = """status: cap-reached
iter: 2 of 2
findings_remaining:
  - {disposition: fix, finding: "still racy", file_line: src/q.ts:7}
"""

CAP_WITH_AN_OPEN_CLASS = """status: cap-reached
iter: 2 of 2
fixed:
  - {finding: "a log with no timestamp compared as equal", file_line: src/logs.ts:12}
findings_remaining:
  - {disposition: fix, finding: "a log with a trailing blank line compares as different", file_line: src/logs.ts:30}
class_closure: log shapes the comparison takes - no timestamp closed; trailing blank line still open
files_touched:
  - src/logs.ts
"""

DEFERRED = """status: deferred
iter: 1
fixed: []
findings_remaining:
  - {disposition: fix, finding: "needs the shared helper", file_line: src/h.ts:1}
ask: []
class_closure: n/a - fixed[] empty
"""


class ReviewFixScriptTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name)
        self.repo = self.temp_root / "myrepo"
        self.repo.mkdir()
        self.ledger_env = fake_ledger.install(self.temp_root)
        self.escapes_file = self.temp_root / "escapes.jsonl"
        self.jump_log = self.temp_root / "jump.log"
        self.gh_log = self.temp_root / "gh.log"
        self.store_dir = self.temp_root / "store"
        self.fake_jump = self.fake_command("nvim-jump", f'echo "$@" >> {self.jump_log}\nexit "${{JUMP_EXIT:-0}}"')
        self.fake_gh = self.fake_command(
            "gh", f'echo "$@" >> {self.gh_log}\ncase "$1 $2" in "repo view") echo acme/web;; "pr view") echo 7;; esac\n'
                  'exit "${GH_EXIT:-0}"')
        self.git("init", "-q")
        (self.repo / "README.md").write_text("hi\n")
        self.git("add", "README.md")
        self.git("commit", "-q", "-m", "init")

    def fake_command(self, name, body):
        path = self.temp_root / name
        path.write_text("#!/usr/bin/env bash\n" + body + "\n")
        path.chmod(0o755)
        return path

    def environment(self, **extra):
        return {**os.environ, **GIT_ENV, **self.ledger_env,
                "REVIEW_ESCAPES_FILE": str(self.escapes_file), "REVIEW_FIX_NVIM_JUMP": str(self.fake_jump),
                "REVIEW_FIX_GH": str(self.fake_gh), "REVIEW_FIX_CLAUDE_DIR": str(CLAUDE_DIR),
                "HANDBACK_STORE_DIR": str(self.store_dir), "CLAUDE_CODE_SESSION_ID": SESSION,
                "CLAUDE_TOOLKIT_TELEMETRY": "1", **extra}

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True, capture_output=True)

    def run_script(self, args, stdin="", cwd=None, **extra):
        done = subprocess.run(["python3", "-I", str(SCRIPT), *args], cwd=cwd or self.repo, input=stdin, text=True,
                              capture_output=True, env=self.environment(**extra))
        return done.returncode, done.stdout + done.stderr

    def packet(self, text, *flags, skill="review", **extra):
        return self.run_script(["packet", "--skill", skill, *flags], text, **extra)

    def rows(self, path):
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def ledger_writes(self):
        """Every `ledger write` call log-review-finding made, oldest first. Each is the row the writer piped in:
        strings, the file path raw in path_key, and no date, repo, session or desc, plus the stand-in's _type,
        _cwd and _session. The review_escape rows log-escape sends are read by escape_rows."""
        return [row for row in fake_ledger.recorded_rows(self.ledger_env) if row["_type"] != "review_escape"]

    def escape_rows(self):
        """Every `review_escape` row log-escape sent to `ledger write`, oldest first; the file path is in path_key."""
        return fake_ledger.recorded_rows(self.ledger_env, "review_escape")

    # ---------- routing ----------

    def test_converged_packet_renders_in_fixed_order_and_asks_for_the_gate_mark(self):
        code, output = self.packet(CONVERGED)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)
        self.assertIn("`~/.claude/scripts/review/review-gate-mark clean`", output)
        self.assertNotIn("bash ~/.claude/scripts/review/review-gate-mark", output)
        self.assertLess(output.index("[blocker] orders query lacked"), output.index("unused import"))
        self.assertIn("Class closure: enumerated every query", output)
        self.assertIn("### Skipped as false positives", output)
        self.assertIn("guarded two lines above", output)
        self.assertIn("auth.ts came back clean", output)
        self.assertNotIn("Do not present this run as clean", output)

    def test_with_no_ledger_the_report_tells_the_user_the_rows_went_to_the_jsonl_files(self):
        home = self.temp_root / "home"
        home.mkdir()
        bare_path = fake_ledger.path_without_ledger(os.environ["PATH"])

        code, output = self.packet(CONVERGED, PATH=bare_path, HOME=str(home), CARGO_HOME=str(home / ".cargo"))

        self.assertEqual(code, 0, output)
        user_text = output.split("BEGIN USER TEXT", 1)[1].split("END USER TEXT", 1)[0]
        self.assertIn("### Ledger", user_text)
        self.assertIn(
            "No ledger found on PATH or in the cargo bin folder ($CARGO_HOME/bin, default ~/.cargo/bin)",
            user_text,
        )

    def test_with_a_ledger_the_report_has_no_ledger_section(self):
        code, output = self.packet(CONVERGED)

        self.assertEqual(code, 0, output)
        self.assertNotIn("### Ledger", output)

    def test_converged_with_bare_none_class_closure_says_the_receipt_is_missing(self):
        code, output = self.packet(
            CONVERGED.replace(
                "class_closure: enumerated every query in orders.ts; the tenant filter now sits on all 3",
                "class_closure: none",
            )
        )
        self.assertEqual(code, 0, output)
        self.assertIn("receipt is missing", output)

    def test_converged_without_a_class_closure_line_says_the_receipt_is_missing(self):
        text = "\n".join(line for line in CONVERGED.splitlines() if not line.startswith("class_closure"))
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("Class closure: MISSING", output)
        self.assertIn("receipt is missing", output)

    def test_empty_converged_review_prints_the_nothing_outstanding_line(self):
        code, output = self.packet(CLEAN_EMPTY)
        self.assertEqual(code, 0, output)
        self.assertIn("No issues found that warrant auto-fix. Ready for `/commit`.", output)
        self.assertIn("- none", output)

    def test_deferred_packet_lists_remaining_findings_and_asks_for_the_mark(self):
        code, output = self.packet(DEFERRED)
        self.assertEqual(code, 0, output)
        self.assertIn("### Deferred to branch exit", output)
        self.assertIn("needs the shared helper", output)
        self.assertIn("review-gate-mark clean", output)

    def test_critical_blocker_stops_without_a_mark(self):
        code, output = self.packet(BLOCKER)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("auth bypass needs a design decision", output)
        self.assertIn("public API field rename", output)
        self.assertIn("Do not mark the gate", output)
        self.assertNotIn("render-and-finish", output)

    def test_a_setup_fault_stops_without_a_mark_and_says_it_is_not_a_code_failure(self):
        code, output = self.packet(SETUP_FAULT)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("no package.json", output)
        self.assertIn("toolkit or environment fault, not a code failure", output)
        self.assertIn("Do not mark the gate", output)
        self.assertNotIn("render-and-finish", output)

    def test_cap_reached_stops_and_keeps_the_gate_dirty(self):
        code, output = self.packet(CAP)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("still racy", output)
        self.assertIn("stays blocked", output)

    def test_a_cap_reached_with_an_open_class_routes_the_next_run_to_the_files_the_fixes_touched_only(self):
        code, output = self.packet(CAP_WITH_AN_OPEN_CLASS)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("files the capped run's fixes touched", output)
        self.assertIn("Dispatch lines (pass exactly these):", output)
        self.assertIn("    - path: src/logs.ts", output)
        self.assertIn("trailing blank line compares as different", output)
        self.assertIn("iter=0", output)
        self.assertNotIn("Do not re-dispatch", output)

    def test_a_cap_reached_with_every_class_closed_keeps_the_plain_stop(self):
        closed_receipts = ["closed", "closed, none left open", "closed; open members: none",
                           "closed (was left open in iter 1)"]
        for receipt in closed_receipts:
            with self.subTest(receipt):
                closed = CAP_WITH_AN_OPEN_CLASS.replace("still open", receipt)
                code, output = self.packet(closed)
                self.assertEqual(code, 0, output)
                self.assertIn("Do not re-dispatch", output)
                self.assertNotIn("files the capped run's fixes touched", output)

    def test_a_cap_reached_with_an_open_class_and_no_files_touched_keeps_the_plain_stop(self):
        no_files = CAP_WITH_AN_OPEN_CLASS.replace("files_touched:\n  - src/logs.ts\n", "files_touched: []\n")
        code, output = self.packet(no_files)
        self.assertEqual(code, 0, output)
        self.assertIn("Do not re-dispatch", output)
        self.assertNotIn("files the capped run's fixes touched", output)
        self.assertNotIn("Dispatch lines", output)

    def test_plan_impact_prints_the_modal_and_decide_builds_the_redispatch_with_both_counters(self):
        code, output = self.packet(PLAN_IMPACT)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: ask-user-plan-impact", output)
        self.assertIn("the queue is at-most-once", output)
        self.assertIn("Adopt plan change / Keep plan as written / Discuss", output)
        self.assertIn("Without that tool, ask the same question in plain text", output)
        self.assertIn("iter=1 spec_iter=2", output)

        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n\n## Phase 1\n\nwork\n")
        code, output = self.run_script(["decide", "adopt", "--by", "user", "--ruling", "yes, add the table",
                                        "--plan", str(plan_file)])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        self.assertIn("plan_impact: RESOLVED - Adopt plan change.", output)
        self.assertIn("iter=1", output)
        self.assertIn("spec_iter=2", output)
        plan_text = plan_file.read_text()
        self.assertIn("## Plan Deviations", plan_text)
        ruling_heading = r"- \d{4}-\d\d-\d\d: Adopt plan change\. Ruled by .+ at \d{4}-\d\d-\d\d \d\d:\d\d\."
        self.assertRegex(plan_text, ruling_heading)
        self.assertIn("  The ruling: yes, add the table", plan_text)
        self.assertIn("  The disagreement:", plan_text)

    def test_decide_appends_to_an_existing_plan_deviations_section_before_the_next_heading(self):
        self.packet(PLAN_IMPACT)
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n\n## Plan Deviations\n\n- old entry\n\n## Phase 1\n\nwork\n")
        self.run_script(["decide", "keep", "--by", "user", "--ruling", "keep it", "--plan", str(plan_file)])
        lines = plan_file.read_text().splitlines()
        self.assertLess(
            lines.index("- old entry"), next(i for i, line in enumerate(lines) if "Keep plan as written" in line)
        )
        self.assertLess(
            next(i for i, line in enumerate(lines) if "Keep plan as written" in line), lines.index("## Phase 1")
        )

    def test_decide_discuss_does_not_redispatch(self):
        self.packet(PLAN_IMPACT)
        _code, output = self.run_script(["decide", "discuss"])
        self.assertIn("ACTION: discuss", output)
        self.assertNotIn("redispatch", output)

    def test_decide_discuss_prints_the_decide_commands_for_both_by_values(self):
        self.packet(PLAN_IMPACT)
        code, output = self.run_script(["decide", "discuss"])
        self.assertEqual(code, 0, output)
        for word in ("adopt", "keep"):
            for by in ("user", "session"):
                self.assertIn(f"review_fix.py decide {word} --by {by} --ruling", output)
        self.assertEqual(4, output.count("--plan <the plan path, when the handoff names one>"))
        self.assertEqual(2, output.count('--ruling "<the decision in one line>"'))

    def test_the_script_usage_asks_for_the_decision_in_one_line(self):
        code, output = self.run_script([])

        self.assertEqual(2, code)
        self.assertIn('decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>" [--plan <path>]',
                      output)

    def test_plan_impact_modal_names_the_by_form(self):
        _code, output = self.packet(PLAN_IMPACT)
        self.assertIn('decide <adopt|keep> --by user --ruling "<the decision in one line>"', output)
        self.assertIn("pass `--by session`", output)
        self.assertIn("--plan <the plan path, when the handoff names one>", output)

    def test_decide_without_a_ruling_stops_with_the_usage_line_and_records_nothing(self):
        self.packet(PLAN_IMPACT)
        stage_before = self.stored_stage()
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")
        for decision in ("adopt", "keep"):
            with self.subTest(decision=decision):
                code, output = self.run_script(["decide", decision, "--by", "user", "--plan", str(plan_file)])
                self.assertEqual(code, 2)
                self.assertIn("ACTION: stop-usage", output)
                self.assertIn(f"decide {decision} needs --ruling", output)
                self.assertEqual(stage_before, self.stored_stage())
                self.assertEqual("# Plan\n", plan_file.read_text())

    def stored_stage(self):
        return json.loads((self.repo / ".git" / "review-fix" / "state.json").read_text())["stage"]

    def test_decide_without_by_stops_with_the_usage_line_and_leaves_the_state(self):
        self.packet(PLAN_IMPACT)
        stage_before = self.stored_stage()
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")
        code, output = self.run_script(["decide", "adopt", "--ruling", "my call", "--plan", str(plan_file)])
        self.assertEqual(code, 2)
        self.assertIn("ACTION: stop-usage", output)
        self.assertIn('decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"', output)
        self.assertEqual(stage_before, self.stored_stage())
        self.assertEqual("# Plan\n", plan_file.read_text())

    def test_decide_with_a_bad_by_value_stops_with_the_usage_line(self):
        self.packet(PLAN_IMPACT)
        stage_before = self.stored_stage()
        code, output = self.run_script(["decide", "keep", "--by", "maybe", "--ruling", "my call"])
        self.assertEqual(code, 2)
        self.assertIn("ACTION: stop-usage", output)
        self.assertIn("--by <user|session>", output)
        self.assertIn("needs --by user or --by session", output)
        self.assertEqual(stage_before, self.stored_stage())

    def test_decide_by_with_no_value_stops_with_the_usage_line(self):
        self.packet(PLAN_IMPACT)
        stage_before = self.stored_stage()
        code, output = self.run_script(["decide", "keep", "--by", "--ruling", "my call"])
        self.assertEqual(code, 2)
        self.assertIn("--by <user|session>", output)
        self.assertEqual(stage_before, self.stored_stage())

    def test_decide_by_session_signs_as_the_session_not_the_user(self):
        self.packet(PLAN_IMPACT)
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")
        code, output = self.run_script(["decide", "adopt", "--by", "session", "--ruling", "my own call",
                                        "--plan", str(plan_file)])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        self.assertIn("The session ruled, not the user.", output)
        self.assertIn("Ruled by the session, not the user at", plan_file.read_text())
        self.assertIn("The ruling: my own call", plan_file.read_text())

    def test_decide_by_user_signs_with_the_git_user_name(self):
        self.packet(PLAN_IMPACT)
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")
        code, output = self.run_script(
            ["decide", "keep", "--by", "user", "--ruling", "keep it", "--plan", str(plan_file)],
            GIT_CONFIG_COUNT="1", GIT_CONFIG_KEY_0="user.name", GIT_CONFIG_VALUE_0="Pat Signer",
        )
        self.assertEqual(code, 0, output)
        self.assertIn("Keep plan as written. Ruled by Pat Signer at", plan_file.read_text())
        self.assertNotIn("The session ruled", output)

    def test_decide_without_a_waiting_plan_impact_fails(self):
        self.packet(CONVERGED)
        code, output = self.run_script(["decide", "adopt"])
        self.assertEqual(code, 2)
        self.assertIn("stop-usage", output)

    # ---------- asks ----------

    def test_asks_done_from_another_repo_names_the_directory_it_looked_in(self):
        other_repo = self.temp_root / "otherrepo"
        other_repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=other_repo, env={**os.environ, **GIT_ENV}, check=True,
                       capture_output=True)
        self.packet(WITH_ASK)

        code, output = self.run_script(["asks-done", "accepted", "rejected"], cwd=other_repo)

        self.assertEqual(code, 2, output)
        self.assertIn(f"no packet was processed in {other_repo}/.git/review-fix", output)
        self.assertIn("run this call there", output)

    def test_asks_are_jumped_listed_and_logged_with_their_outcomes(self):
        code, output = self.packet(WITH_ASK, "--scope", "branch-exit")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: present-asks", output)
        self.assertIn("1. src/retry.ts:10", output)
        self.assertIn("Should retries be capped at 3 or configurable?", output)
        jump = self.jump_log.read_text()
        self.assertIn("--note Should retries be capped at 3 or configurable? src/retry.ts:10", jump)
        self.assertIn("src/db.ts:5", jump)

        code, output = self.run_script(["asks-done", "accepted", "rejected:not worth it"])
        self.assertEqual(code, 0, output)
        finding_rows = self.ledger_writes()
        self.assertEqual([row["_type"] for row in finding_rows], ["review_finding"] * 2)
        self.assertEqual([row["_session"] for row in finding_rows], [SESSION] * 2)
        self.assertEqual([row["ask_outcome"] for row in finding_rows], ["accepted", "rejected"])
        self.assertEqual([row["finding_id"] for row in finding_rows], ["a1b2c3d4e5f60001", "a1b2c3d4e5f60002"])
        self.assertEqual(finding_rows[0]["gate"], "code-reviewer")
        self.assertEqual(finding_rows[1]["gate"], "perf-reviewer")
        self.assertEqual(finding_rows[1]["class"], "perf")
        self.assertEqual(finding_rows[0]["scope"], "branch-exit")
        self.assertEqual(finding_rows[0]["path_key"], "src/retry.ts")
        self.assertEqual(finding_rows[0]["line"], "10")
        self.assertNotIn("repo", finding_rows[0])
        self.assertEqual([os.path.realpath(row["_cwd"]) for row in finding_rows], [os.path.realpath(self.repo)] * 2)
        self.assertNotIn("desc", finding_rows[1])
        self.assertEqual(finding_rows[0]["iter"], "1")

    STOP_ASKS = (
        "ask:\n"
        "  - {finding: retry count, finding_id: a1b2c3d4e5f60021, file_line: src/retry.ts:10, "
        "question: cap at 3?, change: cap at 3, gate: code-reviewer, class: smell}\n"
        "  - {finding: no index, finding_id: a1b2c3d4e5f60022, file_line: src/db.ts:5, "
        "question: add an index?, change: add the index, gate: perf-reviewer, class: perf}\n"
    )

    def assert_stop_packet_asks_are_printed_and_logged(self, text):
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("Do not re-dispatch", output)
        self.assertIn("1. src/retry.ts:10  [code-reviewer/smell]", output)
        self.assertIn("2. src/db.ts:5  [perf-reviewer/perf]", output)
        self.assertIn("Proposed change: add the index", output)
        self.assertIn("asks-done <outcome> x2", output)
        self.assertNotIn("review-gate-mark clean", output)

        code, output = self.run_script(["asks-done", "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        rows = self.ledger_writes()
        self.assertEqual([row["ask_outcome"] for row in rows], ["accepted", "rejected"])
        self.assertEqual([row["finding_id"] for row in rows], ["a1b2c3d4e5f60021", "a1b2c3d4e5f60022"])
        self.assertEqual(self.stored_stage(), "done")

    def test_a_cap_reached_packet_with_asks_prints_them_and_asks_done_logs_their_outcomes(self):
        self.assert_stop_packet_asks_are_printed_and_logged(CAP + self.STOP_ASKS)

    def test_a_critical_blocker_packet_with_asks_prints_them_and_asks_done_logs_their_outcomes(self):
        self.assert_stop_packet_asks_are_printed_and_logged(BLOCKER + self.STOP_ASKS)

    ONE_ASK = CLEAN_EMPTY.replace(
        "ask: []", "ask:\n  - {finding: first, finding_id: a1b2c3d4e5f60031, file_line: one.ts:1, question: first?, "
                  "change: c, gate: code-reviewer, class: smell}")

    def stored_state(self):
        return json.loads((self.repo / ".git" / "review-fix" / "state.json").read_text())

    def test_a_second_packet_keeps_the_first_packets_unanswered_asks_and_asks_done_names_the_packet(self):
        self.packet(self.ONE_ASK)
        first_id = self.stored_state()["packet_id"]
        code, output = self.packet(WITH_ASK)
        second_id = self.stored_state()["packet_id"]
        self.assertNotEqual(first_id, second_id)
        self.assertIn(f"asks-done --packet {second_id} <outcome> x2", output)
        code, output = self.packet(WITH_ASK)
        self.assertIn(f"asks-done --packet {second_id} <outcome> x2", output)
        self.assertEqual([waiting["packet_id"] for waiting in self.stored_state()["waiting_packets"]], [first_id])

        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 2, output)
        self.assertIn(first_id, output)
        self.assertIn(second_id, output)
        self.assertIn("one.ts:1 first?", output)
        self.assertIn("src/retry.ts:10", output)
        self.assertEqual(self.ledger_writes(), [])

        code, output = self.run_script(["asks-done", "--packet", first_id, "accepted"])
        self.assertEqual(code, 0, output)
        self.assertEqual([row["finding_id"] for row in self.ledger_writes()], ["a1b2c3d4e5f60031"])
        self.assertEqual(self.stored_state()["waiting_packets"], [])

        code, output = self.run_script(["asks-done", "--packet", second_id, "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        rows = self.ledger_writes()
        self.assertEqual([row["finding_id"] for row in rows],
                         ["a1b2c3d4e5f60031", "a1b2c3d4e5f60001", "a1b2c3d4e5f60002"])
        self.assertEqual(self.stored_stage(), "done")

        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertIn("already logged", output)

    def ask_packet_numbered(self, number):
        return CLEAN_EMPTY.replace(
            "ask: []", f"ask:\n  - {{finding: f{number}, finding_id: a1b2c3d4e5f6004{number}, "
                      f"file_line: n{number}.ts:1, question: q{number}?, change: c, gate: code-reviewer, "
                      "class: smell}")

    def test_three_packets_in_a_row_all_keep_their_unanswered_asks(self):
        packet_ids = []
        for number in (1, 2, 3):
            self.packet(self.ask_packet_numbered(number))
            packet_ids.append(self.stored_state()["packet_id"])
        self.assertEqual(3, len(set(packet_ids)))

        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 2, output)
        for packet_id in packet_ids:
            self.assertIn(packet_id, output)

    def test_asks_done_refuses_a_packet_id_that_is_not_waiting_and_logs_nothing(self):
        self.packet(self.ONE_ASK)
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "--packet", "no-such-packet", "accepted"])
        self.assertEqual(code, 2, output)
        self.assertIn("is not a packet with unanswered asks", output)
        self.assertEqual(self.ledger_writes(), [])

    def test_a_held_packet_whose_rows_failed_to_log_stays_held(self):
        self.packet(self.ONE_ASK)
        first_id = self.stored_state()["packet_id"]
        self.packet(WITH_ASK)

        _code, output = self.run_script(["asks-done", "--packet", first_id, "accepted"], FAKE_LEDGER_WRITE_EXIT="2")
        self.assertIn("Failures", output)
        held_ids = [kept["packet_id"] for kept in self.stored_state()["waiting_packets"]]
        self.assertEqual([first_id], held_ids)

    def test_a_packet_that_fails_to_parse_keeps_the_previous_packets_unanswered_asks(self):
        self.packet(self.ONE_ASK)
        first_id = self.stored_state()["packet_id"]
        code, output = self.packet("status: bogus")
        self.assertEqual(code, 2, output)
        self.assertEqual(first_id, self.stored_state()["packet_id"])

        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertEqual([row["finding_id"] for row in self.ledger_writes()], ["a1b2c3d4e5f60031"])

    def test_the_next_good_packet_after_a_parse_failure_carries_the_earlier_packets_asks(self):
        self.packet(self.ONE_ASK)
        first_id = self.stored_state()["packet_id"]
        code, output = self.packet("status: bogus")
        self.assertEqual(code, 2, output)

        self.packet(WITH_ASK)
        held_ids = [kept["packet_id"] for kept in self.stored_state()["waiting_packets"]]
        self.assertEqual([first_id], held_ids)

    def test_nvim_jump_with_no_owner_is_silent_and_still_lists_the_asks(self):
        code, output = self.packet(WITH_ASK, JUMP_EXIT="1")
        self.assertEqual(code, 0, output)
        self.assertIn("no nvim owns this directory", output)
        self.assertIn("2. src/db.ts:5", output)

    def test_missing_nvim_jump_does_not_stop_the_run(self):
        code, output = self.packet(WITH_ASK, REVIEW_FIX_NVIM_JUMP="/nonexistent/nvim-jump")
        self.assertEqual(code, 0, output)
        self.assertIn("nvim-jump is not installed", output)

    def test_asks_done_with_the_wrong_number_of_outcomes_fails_loudly_and_logs_nothing(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 2)
        self.assertIn("2 ask(s) waiting but 1 outcome(s) given", output)
        self.assertEqual(self.ledger_writes(), [])

    def test_asks_done_logs_the_outcome_of_an_ask_that_names_no_file(self):
        first_ask = WITH_ASK.split("  - {finding")[0].replace("src/retry.ts:10", "unlocated")
        unlocated_ask = first_ask + "class_closure: n/a - fixed[] empty\n"
        self.packet(unlocated_ask)
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("Failures", output)
        self.assertEqual([row["ask_outcome"] for row in self.ledger_writes()], ["accepted"])

    def test_asks_done_with_an_unknown_outcome_fails_loudly(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "accepted", "maybe"])
        self.assertEqual(code, 2)
        self.assertIn("accepted|rejected|modified", output)
        self.assertEqual(self.ledger_writes(), [])

    def test_asks_done_by_session_logs_who_ruled_and_says_so(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "--by", "session", "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        self.assertIn("The session ruled, not the user.", output)
        self.assertEqual([row["ask_decided_by"] for row in self.ledger_writes()], ["session"] * 2)

    def test_asks_done_without_by_logs_the_user_as_the_one_who_ruled(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("The session ruled", output)
        self.assertEqual([row["ask_decided_by"] for row in self.ledger_writes()], ["user"] * 2)

    def test_asks_done_with_a_bad_by_value_fails_loudly_and_logs_nothing(self):
        self.packet(WITH_ASK)
        for by_words in (["--by", "robot"], ["--by"]):
            with self.subTest(by_words):
                code, output = self.run_script(["asks-done", *by_words, "accepted", "rejected"])
                self.assertEqual(code, 2)
                self.assertIn("user or session", output)
                self.assertEqual(self.ledger_writes(), [])

    def test_the_asks_packet_tells_the_session_when_it_may_decide_the_asks_itself(self):
        code, output = self.packet(WITH_ASK)
        self.assertEqual(code, 0, output)
        self.assertIn("hands ask decisions to the session", output)
        self.assertIn("--by session", output)

    def test_asks_done_without_waiting_asks_fails(self):
        self.packet(CONVERGED)
        code, _output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 2)

    # ---------- /fix extras ----------

    def escape_spec(self, **overrides):
        fields = {"file": "src/orders.ts", "class": "bug", "severity": "high", "gate_missed": "review",
                  "guard": "convention", "desc": "orders lacked a tenant filter"}
        fields.update(overrides)
        return "|".join(f"{key}={value}" for key, value in fields.items())

    def test_walkthrough_escape_logs_only_for_a_conversation_finding_that_was_applied(self):
        code, output = self.packet(CONVERGED, "--source", "conversation", "--escape", self.escape_spec(), skill="fix")
        self.assertEqual(code, 0, output)
        rows = self.escape_rows()
        self.assertEqual(len(rows), 1, output)
        self.assertEqual(rows[0]["stage_found"], "walkthrough")
        self.assertEqual(rows[0]["gate_missed"], "review")
        self.assertEqual(rows[0]["guard"], "convention")
        self.assertEqual(rows[0]["lane"], "code")
        self.assertEqual(rows[0]["path_key"], "src/orders.ts")

    def test_escape_from_a_cc_comment_is_not_logged(self):
        code, output = self.packet(CONVERGED, "--source", "cc", "--escape", self.escape_spec(), skill="fix")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.escape_rows(), [])
        self.assertIn("not the conversation", output)

    def test_escape_for_a_file_with_no_fixed_entry_is_not_logged(self):
        _code, output = self.packet(CONVERGED, "--source", "conversation",
                                   "--escape", self.escape_spec(file="src/other.ts"), skill="fix")
        self.assertEqual(self.escape_rows(), [])
        self.assertIn("no fixed[] entry names that file", output)

    def test_escape_the_ledger_refuses_is_noted_and_not_logged(self):
        code, output = self.packet(CONVERGED, "--source", "conversation",
                                   "--escape", self.escape_spec(), skill="fix",
                                   FAKE_LEDGER_WRITE_EXIT="2")
        self.assertEqual(code, 0, output)
        self.assertIn("escape log FAILED for src/orders.ts", output)
        self.assertEqual(self.escape_rows(), [])

    def test_unknown_guard_reaches_the_ledger_as_given(self):
        code, output = self.packet(CONVERGED, "--source", "conversation",
                                   "--escape", self.escape_spec(guard="vibes"), skill="fix")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.escape_rows()[0]["guard"], "vibes")

    def test_escape_missing_a_field_fails_loudly(self):
        spec = self.escape_spec().replace("|severity=high", "")
        code, output = self.packet(CONVERGED, "--source", "conversation", "--escape", spec, skill="fix")
        self.assertEqual(code, 2)
        self.assertIn("lacks severity", output)

    def test_escape_on_a_non_converged_status_is_not_logged(self):
        _code, _output = self.packet(CAP, "--source", "conversation", "--escape", self.escape_spec(), skill="fix")
        self.assertEqual(self.escape_rows(), [])

    def test_escape_flag_on_review_is_refused(self):
        code, _output = self.packet(CONVERGED, "--escape", self.escape_spec())
        self.assertEqual(code, 2)

    def test_aikido_replies_follow_fixed_skipped_and_other_dispositions(self):
        text = CONVERGED.replace(
            "ask: []",
            'ask: [{finding: "pick a cap", file_line: src/c.ts:4, question: "cap?", change: "cap at 3", '
            'gate: code-reviewer, class: smell}]',
        )
        code, output = self.packet(text, "--aikido", "src/orders.ts:42=111", "--aikido", "src/a.ts:9=222",
                                   "--aikido", "src/c.ts:4=333", skill="fix")
        self.assertEqual(code, 0, output)
        calls = self.gh_log.read_text().splitlines()
        posts = [call for call in calls if call.startswith("api")]
        self.assertEqual(len(posts), 3)
        self.assertIn("repos/acme/web/pulls/7/comments/111/replies", posts[0])
        self.assertIn("body=Fixed — orders query lacked a tenant filter", posts[0])
        self.assertIn("body=@AikidoSec ignore: guarded two lines above", posts[1])
        self.assertIn("body=Not fixed in this pass: converged — cap?", posts[2])
        self.assertIn("### Aikido replies", output)

    def test_aikido_reply_failure_is_reported_and_does_not_stop_the_render(self):
        code, output = self.packet(CONVERGED, "--aikido", "src/orders.ts:42=111", skill="fix", GH_EXIT="1")
        self.assertEqual(code, 0, output)
        self.assertIn("NOT posted", output)
        self.assertIn("### Fixed", output)

    def test_aikido_target_without_a_numeric_comment_id_fails_loudly(self):
        code, output = self.packet(CONVERGED, "--aikido", "src/orders.ts:42=abc", skill="fix")
        self.assertEqual(code, 2)
        self.assertIn("numeric comment id", output)

    def test_fix_render_has_no_class_closure_line_unless_the_packet_carries_one(self):
        text = "\n".join(line for line in CONVERGED.splitlines() if not line.startswith("class_closure"))
        _code, output = self.packet(text, skill="fix")
        self.assertNotIn("Class closure", output)
        self.assertNotIn("receipt", output)

    # ---------- malformed packets: every one stops loudly ----------

    def assert_parse_failure(self, text, expected, skill="review"):
        code, output = self.packet(text, skill=skill)
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-parse-failure", output)
        self.assertIn(expected, output)
        self.assertIn("`~/.claude/scripts/review/review-gate-mark dirty`", output)
        self.assertNotIn("render-and-finish", output)
        self.assertEqual(self.ledger_writes(), [])

    def test_empty_stdin_is_a_parse_failure(self):
        self.assert_parse_failure("", "no review-loop dispatch on record")

    def test_prose_with_no_packet_is_a_parse_failure(self):
        self.assert_parse_failure("I reviewed the diff and it looks fine.", "status is 'missing'")

    def test_unknown_status_is_a_parse_failure(self):
        self.assert_parse_failure(CONVERGED.replace("status: converged", "status: done"), "status is 'done'")

    def test_missing_iter_is_a_parse_failure(self):
        self.assert_parse_failure(CONVERGED.replace("iter: 1\n", ""), "iter is missing")

    def test_iter_without_a_number_is_a_parse_failure(self):
        self.assert_parse_failure(CONVERGED.replace("iter: 1", "iter: two"), "iter is missing")

    def test_converged_without_fixed_is_a_parse_failure(self):
        text = "\n".join(line for line in CLEAN_EMPTY.splitlines() if not line.startswith("fixed"))
        self.assert_parse_failure(text, "fixed is missing")

    def test_fixed_entry_without_a_finding_is_a_parse_failure(self):
        self.assert_parse_failure(
            CONVERGED.replace('finding: "orders query lacked a tenant filter", ', ""), "no finding"
        )

    def test_ask_entry_without_a_question_is_a_parse_failure(self):
        self.assert_parse_failure(
            WITH_ASK.replace('finding: "no index", ', "").replace('question: "Add an index on tenant_id?", ', ""),
            "no question",
        )

    def test_ask_entry_without_a_file_line_is_a_parse_failure(self):
        self.assert_parse_failure(WITH_ASK.replace("file_line: src/db.ts:5, ", ""), "no file_line")

    def test_ask_with_keys_but_no_finding_or_question_is_a_parse_failure(self):
        text = CLEAN_EMPTY.replace("ask: []", "ask:\n  - {file_line: a.ts:1, gate: code-reviewer, class: bug}")
        self.assert_parse_failure(text, "ask entry has no question")

    def test_plain_text_ask_without_a_file_line_still_reaches_the_user(self):
        code, output = self.packet(CLEAN_EMPTY.replace("ask: []", "ask:\n  - see the thread above"))
        self.assertEqual(code, 0, output)
        self.assertIn("see the thread above", output)

    def test_plan_impact_with_an_empty_block_is_a_parse_failure(self):
        self.assert_parse_failure("status: plan-impact\niter: 1\nspec_iter: 0\nplan_impact:\n", "plan_impact is empty")

    def test_critical_blocker_without_blockers_is_a_parse_failure(self):
        self.assert_parse_failure("status: critical-blocker\niter: 1\nblockers: []\n", "blockers is empty")

    def test_cap_reached_without_findings_remaining_is_a_parse_failure(self):
        self.assert_parse_failure("status: cap-reached\niter: 2\n", "findings_remaining is missing")

    def test_deferred_with_empty_findings_remaining_is_a_parse_failure(self):
        self.assert_parse_failure("status: deferred\niter: 1\nfixed: []\nfindings_remaining: []\n",
                                  "findings_remaining is missing or empty")

    def test_spec_iter_without_a_number_is_a_parse_failure(self):
        self.assert_parse_failure(PLAN_IMPACT.replace("spec_iter: 2", "spec_iter: many"), "spec_iter has no number")

    # ---------- whitespace and format tolerance ----------

    def test_extra_whitespace_and_a_code_fence_around_the_packet_still_parse(self):
        padded = (
            "```\n"
            + "\n".join("   " + line + "   " if line else line for line in CONVERGED.splitlines())
            + "\n\n\n```\n"
        )
        code, output = self.packet(padded)
        self.assertEqual(code, 0, output)
        self.assertIn("[blocker] orders query lacked a tenant filter - src/orders.ts:42", output)

    def test_status_with_trailing_words_and_extra_spaces_parses(self):
        code, output = self.packet(CLEAN_EMPTY.replace("status: converged", "status:    converged   (all clear)"))
        self.assertEqual(code, 0, output)
        self.assertIn("render-and-finish", output)

    def test_status_in_backticks_and_upper_case_parses(self):
        code, output = self.packet(CLEAN_EMPTY.replace("status: converged", "status: `CONVERGED`"))
        self.assertEqual(code, 0, output)

    def test_closing_prose_after_the_packet_is_kept_as_a_trailer_not_a_field(self):
        code, output = self.packet(CLEAN_EMPTY + "\nThe second pass found nothing more.\n")
        self.assertEqual(code, 0, output)
        self.assertIn("The second pass found nothing more.", output)

    def test_json_style_lists_parse(self):
        text = CLEAN_EMPTY.replace("fixed: []", 'fixed: [{"finding": "x", "file_line": "a.ts:1", "blocker": false}]')
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("- x - a.ts:1", output)

    def test_finding_text_containing_a_comma_and_key_word_keeps_its_whole_text(self):
        text = CLEAN_EMPTY.replace(
            "fixed: []", 'fixed: [{finding: "guard the read, then class: fix it", file_line: a.ts:1, blocker: false}]'
        )
        _code, output = self.packet(text)
        self.assertIn("guard the read, then class: fix it", output)

    # ---------- shapes seen in real review-loop hand-backs ----------

    def test_unbracketed_key_value_asks_with_dot_semicolon_and_pipe_separators_parse(self):
        text = CLEAN_EMPTY.replace(
            "ask: []",
            "ask:\n"
            "- finding: cache lock spans the scan. file_line: serve.go:162,188. question: what staleness is fine? "
            "change: release the lock before the scan. gate: code-reviewer. class: perf\n"
            "- finding: timeouts left unset; file_line: cli/serve.go:35; question: out of scope? change: set the "
            "timeouts; gate: robustness; class: ops\n"
            "- finding: ReadHeaderTimeout question | file_line: cli/serve.go:35 | question: use an http.Server? | "
            "change: serve through an http.Server | gate: robustness | class: ops",
        )
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("what staleness is fine?", output)
        self.assertIn("use an http.Server?", output)

    def test_flow_ask_with_a_finding_but_no_question_uses_the_finding_as_the_question(self):
        text = CLEAN_EMPTY.replace(
            "ask: []",
            'ask:\n  - {finding: "Accept it as the contract and update the README?", file_line: '
            '"src/inventory.ts:103-110", change: "update the README", gate: code-reviewer, class: docs}',
        )
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("Accept it as the contract", output)

    def test_flow_ask_whose_keys_follow_a_period_parses(self):
        text = CLEAN_EMPTY.replace(
            "ask: []",
            "ask:\n  - {finding: The rules file wants interface. file_line: backend/a.ts:1, question: Convert the "
            "shapes? change: convert the shapes to interfaces, gate: code-reviewer, class: docs}",
        )
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("Convert the shapes?", output)

    def test_free_text_file_line_and_a_comma_list_of_lines_parse(self):
        text = CLEAN_EMPTY.replace(
            "ask: []",
            "ask:\n- finding: parseDateOnly is unresolved | file_line: service.test.ts:1313 area | question: drop it? "
            "| change: drop the parseDateOnly test | gate: carried | class: carried",
        )
        text = text.replace(
            "fixed: []", 'fixed: [{finding: "spec gap", file_line: "spec.md:432, :1521-1523", blocker: false}]'
        )
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)

    def test_fixed_entries_keyed_by_smell_or_starting_with_bare_text_parse(self):
        text = CLEAN_EMPTY.replace("fixed: []", "fixed:\n"
            "- {smell: literals extracted to constants, file_line: a.py:397-530, blocker: no}\n"
            "- {blank lines between steps in two helpers, file_line: a.py:346-474, blocker: no}\n"
            "- {summary overwrote the per-project total, serve.go summary, blocker: true}")
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("summary overwrote the per-project total", output)
        self.assertIn("blank lines between steps", output)

    def test_a_real_pending_report_is_a_parse_failure(self):
        self.assert_parse_failure(
            "status: pending. This is not a convergence packet. The verification pass has not reported.\n\nDone so "
            "far:\n- fixed\n",
            "status is",
        )

    def test_a_deferred_packet_with_asks_but_no_findings_remaining_is_a_parse_failure(self):
        text = (
            "status: deferred\niter: 1\nfixed: []\nskipped_fp: []\nblockers: []\nfindings_remaining: []\nask:\n- "
            "{finding: x, file_line: a.ts:1, question: y?}\n"
        )
        self.assert_parse_failure(text, "findings_remaining")

    def test_a_cap_reached_packet_with_an_empty_findings_remaining_is_a_parse_failure(self):
        self.assert_parse_failure(
            "status: cap-reached\niter: 2\nfixed: []\nblockers: []\nfindings_remaining: [] (none open)\n",
            "findings_remaining",
        )

    # ---------- no-paste: saved hand-back ----------

    def hook(self, event, which, **extra):
        done = subprocess.run(["python3", "-I", str(HANDBACK), "hook", which], cwd=self.temp_root,
                              input=json.dumps(event), text=True, capture_output=True, env=self.environment(**extra))
        return done.returncode, done.stdout + done.stderr

    def dispatch(self, session=SESSION, subagent="review-loop"):
        return self.hook({"session_id": session, "tool_name": "Agent", "tool_input": {"subagent_type": subagent}},
                         "dispatch")

    def hand_back(self, message=CONVERGED, session=SESSION, agent="review-loop", agent_id="a1"):
        self.hook({"session_id": session, "tool_name": "Agent", "agent_type": agent, "agent_id": agent_id,
                   "tool_input": {"subagent_type": "code-reviewer"}}, "dispatch")
        return self.hook({"session_id": session, "tool_name": "SubagentHandback", "agent_type": agent,
                          "agent_id": agent_id, "tool_input": {"message": message}}, "handback")

    def seed(self, message=CONVERGED, session=SESSION):
        self.dispatch(session)
        self.hand_back(message, session)

    def test_saved_hand_back_is_read_when_stdin_is_empty(self):
        self.seed()
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_a_clean_hand_back_flagged_as_unreviewed_stops_with_a_re_dispatch_instruction(self):
        self.unreviewed_loop("a1")
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-reviewer", output)
        self.assertNotIn("render-and-finish", output)

    def test_a_hand_back_with_no_reviewer_run_re_dispatches_with_the_round_count_kept(self):
        self.unreviewed_loop("a1", CONVERGED.replace("iter: 1", "iter: 2"))
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("Re-dispatch review-loop once", output)
        self.assertIn("\niter=2\n", output)

    def test_a_second_unreviewed_hand_back_in_a_row_says_stop_and_no_re_dispatch(self):
        self.unreviewed_loop("a1", CONVERGED.replace("iter: 1", "iter: 2"))
        self.packet("")
        self.unreviewed_loop("a2", CONVERGED.replace("iter: 1", "iter: 2"))
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-reviewer", output)
        self.assertIn("2 times in a row", output)
        self.assertIn("Do not re-dispatch again", output)
        self.assertNotIn("Re-dispatch review-loop once", output)

    def test_a_converged_hand_back_ending_on_a_fix_finishes_and_names_the_unreviewed_fix_files(self):
        self.dispatch()
        self.hand_back_after_steps(["code-reviewer", "coder"])
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)
        self.assertIn("### Last fix not reviewed", output)
        self.assertIn("Their files are among: src/orders.ts, src/util.ts", output)
        self.assertIn("Review-again is not advised: it ends on an unreviewed fix the same way.", output)

    def test_a_converged_hand_back_ending_on_a_reviewer_names_no_unreviewed_fix(self):
        self.dispatch()
        self.hand_back_after_steps(["coder", "code-reviewer"])
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertNotIn("Last fix not reviewed", output)

    def hand_back_after_steps(self, subagents, agent_id="a1"):
        for subagent in subagents:
            self.hook({"session_id": SESSION, "tool_name": "Agent", "agent_type": "review-loop", "agent_id": agent_id,
                       "tool_input": {"subagent_type": subagent}}, "dispatch")
        return self.hook({"session_id": SESSION, "tool_name": "SubagentHandback", "agent_type": "review-loop",
                          "agent_id": agent_id, "tool_input": {"message": CONVERGED}}, "handback")

    def unreviewed_loop(self, agent_id, message=CONVERGED):
        """A dispatched loop whose only step is a coder hands back clean twice: the hook denies the first and stores
        the second flagged unreviewed."""
        self.dispatch()
        coder = {"session_id": SESSION, "tool_name": "Agent", "agent_type": "review-loop", "agent_id": agent_id,
                 "tool_input": {"subagent_type": "coder"}}
        self.hook(coder, "dispatch")
        for _ in range(2):
            self.hook({"session_id": SESSION, "tool_name": "SubagentHandback", "agent_type": "review-loop",
                       "agent_id": agent_id, "tool_input": {"message": message}}, "handback")

    def test_session_with_no_dispatch_on_record_is_refused(self):
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("no review-loop dispatch on record", output)
        self.assertIn("`~/.claude/scripts/review/review-gate-mark dirty`", output)

    def test_another_sessions_hand_back_is_never_taken_as_current(self):
        self.seed(CONVERGED, session=OTHER_SESSION)
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("no review-loop dispatch on record", output)

    def test_a_hand_back_older_than_the_last_dispatch_is_refused(self):
        self.seed()
        self.dispatch()
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-handback", output)
        self.hand_back(CLEAN_EMPTY, agent_id="a2")
        code, output = self.packet("")
        self.assertEqual(code, 0, output)

    def saved_stage(self):
        return json.loads((self.repo / ".git" / "review-fix" / "state.json").read_text())["stage"]

    def test_a_loop_that_never_handed_back_says_re_dispatch_once_and_keeps_the_earlier_stage(self):
        self.seed(WITH_ASK)
        self.packet("")
        self.assertEqual(self.saved_stage(), "asks")
        self.dispatch()
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-handback", output)
        self.assertIn("Re-dispatch review-loop once", output)
        self.assertNotIn("stop-parse-failure", output)
        self.assertEqual(self.saved_stage(), "asks")

    def test_a_second_miss_in_a_row_says_stop_and_show_the_final_text(self):
        self.seed(WITH_ASK)
        self.packet("")
        self.dispatch()
        self.packet("")
        self.dispatch()
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-handback", output)
        self.assertIn("Show the user the loop's final text", output)
        self.assertNotIn("Re-dispatch review-loop once", output)
        self.assertEqual(self.saved_stage(), "asks")

    def stop_row(self, open_dispatches, session=SESSION, ts=1000.5, ask_rows=None):
        row = {"kind": "stop", "ts": ts, "session_id": session, "agent_id": "a1", "open_dispatches": open_dispatches}
        if ask_rows is not None:
            row["ask_rows"] = ask_rows
        with open(self.store_dir / (session + ".jsonl"), "a", encoding="utf-8") as store:
            store.write(json.dumps(row) + "\n")

    def misses(self):
        path = self.repo / ".git" / "review-fix" / "misses.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def test_a_loop_waiting_on_a_background_agent_gets_wait_for_loop_and_no_miss(self):
        self.dispatch()
        self.stop_row(1)
        code, output = self.packet("")
        self.assertEqual(code, 3, output)
        self.assertIn("ACTION: wait-for-loop", output)
        self.assertIn("Do not re-dispatch", output)
        self.assertNotIn("stop-no-handback", output)
        self.assertEqual(self.misses(), {})

    def test_a_loop_that_stops_on_a_shell_its_timeout_moved_to_the_background_gets_wait_for_loop(self):
        fixtures = pathlib.Path(__file__).resolve().parent / "fixtures"
        fixture = fixtures / "loop_shell_moved_to_background_by_timeout.jsonl"
        call_and_moved = fixture.read_text().splitlines()[:2]
        transcript = self.temp_root / "loop.jsonl"
        transcript.write_text("\n".join(call_and_moved) + "\n")
        stop = {"hook_event_name": "SubagentStop", "agent_type": "review-loop", "session_id": SESSION,
                "agent_id": "a1", "agent_transcript_path": str(transcript)}
        self.dispatch()

        subprocess.run(["python3", "-I", str(LOOP_GATE)], input=json.dumps(stop), text=True, capture_output=True,
                       env=self.environment(), check=True)
        code, output = self.packet("")

        self.assertEqual(code, 3, output)
        self.assertIn("ACTION: wait-for-loop", output)
        self.assertNotIn("stop-no-handback", output)

    def test_a_loop_that_hands_back_before_its_background_reviewer_reports_gets_wait_for_loop(self):
        full_check = {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t_full", "name": "Bash",
             "input": {"command": "npm test > /tmp/review-gate.log 2>&1"}}]}}
        launch = {"type": "assistant", "message": {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t_rev", "name": "Agent",
             "input": {"subagent_type": "code-reviewer", "prompt": "review"}}]}}
        launched = {"type": "user", "message": {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t_rev",
             "content": [{"type": "text", "text": "Async agent launched\nagentId: arev"}]}]}}
        transcript = self.temp_root / "loop.jsonl"
        transcript.write_text("".join(json.dumps(line) + "\n" for line in (full_check, launch, launched)))
        loop_event = {"session_id": SESSION, "agent_type": "review-loop", "agent_id": "a1",
                      "agent_transcript_path": str(transcript)}
        self.dispatch()

        _code, denied = self.hook({**loop_event, "tool_name": "SubagentHandback", "tool_input": {"message": BLOCKER}},
                                  "handback")
        subprocess.run(["python3", "-I", str(LOOP_GATE)], input=json.dumps({**loop_event,
                                                                            "hook_event_name": "SubagentStop"}),
                       text=True, capture_output=True, env=self.environment(), check=True)
        code, output = self.packet("")

        self.assertIn('"permissionDecision": "deny"', denied)
        self.assertEqual(code, 3, output)
        self.assertIn("ACTION: wait-for-loop", output)
        self.assertNotIn("ACTION: stop", output)

    def test_a_second_packet_on_the_same_stop_row_stops_and_a_new_stop_row_waits_again(self):
        self.dispatch()
        self.stop_row(1)
        self.packet("")
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop\n", output)
        clock = time.strftime("%H:%M:%S", time.localtime(1000.5))
        waited_on = "on an agent or shell it started in the background and has not handed back"
        self.assertIn(f"waiting since {clock} {waited_on}", output)
        self.assertNotIn("1000.5", output)
        self.assertIn("Do not re-dispatch", output)
        self.assertNotIn("wait-for-loop", output)
        self.assertEqual(self.misses(), {})
        self.stop_row(1, ts=2000.5)
        code, output = self.packet("")
        self.assertEqual(code, 3, output)
        self.assertIn("ACTION: wait-for-loop", output)

    def test_a_later_stop_with_nothing_open_and_no_hand_back_is_a_miss_again(self):
        self.dispatch()
        self.stop_row(1)
        self.stop_row(0)
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-handback", output)
        self.assertIn("Re-dispatch review-loop once", output)

    def test_a_hand_back_after_the_wait_is_read_normally(self):
        self.dispatch()
        self.stop_row(1)
        self.hand_back()
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_sessions_in_one_repo_keep_separate_miss_counts(self):
        self.dispatch(OTHER_SESSION)
        _, output = self.packet("", CLAUDE_CODE_SESSION_ID=OTHER_SESSION)
        self.assertIn("Re-dispatch review-loop once", output)
        self.dispatch()
        _code, output = self.packet("")
        self.assertIn("Re-dispatch review-loop once", output)
        self.assertNotIn("Stop. Do not re-dispatch", output)

    def test_review_and_fix_keep_separate_miss_counts(self):
        self.seed(WITH_ASK)
        self.dispatch()
        self.packet("", skill="review")
        self.dispatch()
        _, output = self.packet("", skill="fix")
        self.assertIn("Re-dispatch review-loop once", output)
        self.dispatch()
        _code, output = self.packet("", skill="review")
        self.assertIn("Show the user the loop's final text", output)

    def test_a_denied_dispatch_blocks_nothing_once_a_later_dispatch_hands_back(self):
        self.dispatch()
        self.dispatch()
        self.hand_back(CLEAN_EMPTY)
        code, output = self.packet("")
        self.assertEqual(code, 0, output)

    def test_two_dispatches_returning_the_same_text_are_two_runs(self):
        self.seed(WITH_ASK)
        self.packet("")
        self.run_script(["asks-done", "accepted", "accepted"])
        self.dispatch()
        self.hand_back(WITH_ASK, agent_id="a2")
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: present-asks", output)
        self.assertEqual(len(self.jump_log.read_text().splitlines()), 2)
        self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(len(self.ledger_writes()), 4)

    def test_re_running_packet_on_the_same_stored_hand_back_is_one_run(self):
        self.seed(WITH_ASK)
        self.packet("")
        self.run_script(["asks-done", "accepted", "accepted"])
        _code, output = self.packet("")
        self.assertIn("ACTION: done", output)
        self.assertEqual(len(self.ledger_writes()), 2)

    def test_dispatch_of_another_agent_does_not_make_the_hand_back_stale(self):
        self.seed()
        self.dispatch(subagent="coder")
        self.assertEqual(self.packet("")[0], 0)

    def test_hand_back_from_another_agent_is_not_stored(self):
        self.dispatch()
        code, output = self.hand_back(agent="coder")
        self.assertEqual((code, output), (0, ""))
        self.assertEqual(self.packet("")[0], 2)

    def test_stdin_packet_wins_over_a_saved_one(self):
        self.seed("status: pending")
        self.assertEqual(self.packet(CLEAN_EMPTY)[0], 0)

    def test_missing_session_id_env_refuses_a_saved_read(self):
        self.seed()
        code, output = self.packet("", CLAUDE_CODE_SESSION_ID="")
        self.assertEqual(code, 2, output)
        self.assertIn("CLAUDE_CODE_SESSION_ID is not set", output)

    # ---------- /code state ----------

    def write_code_step(self, **fields):
        code_step = self.repo / ".git" / "code-step"
        code_step.mkdir(exist_ok=True)
        (code_step / "state.json").write_text(json.dumps(fields))
        return code_step / "state.json"

    def test_code_step_state_of_the_same_session_blocks_a_saved_read_and_is_named(self):
        self.seed()
        path = self.write_launched_run("a1")
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn(str(path), output)
        self.assertIn("code_step.py resume", output)

    def test_code_step_state_pinned_to_another_session_does_not_block(self):
        self.seed()
        self.write_code_step(stage="review", sessionId=OTHER_SESSION)
        self.assertEqual(self.packet("")[0], 0)

    def test_code_step_state_pinned_to_no_session_does_not_block(self):
        self.seed()
        self.write_code_step(stage="review")
        self.assertEqual(self.packet("")[0], 0)

    def test_code_step_state_past_the_hook_stages_does_not_block(self):
        self.seed()
        self.write_code_step(stage="done", sessionId=SESSION)
        self.assertEqual(self.packet("")[0], 0)

    def test_every_stage_that_owns_review_hand_backs_blocks(self):
        for stage in ("coder", "asks-coder"):
            with self.subTest(stage=stage):
                self.seed()
                self.write_launched_run("a1", stage=stage)
                self.assertEqual(self.packet("")[0], 2)

    def test_plan_coder_stage_does_not_block(self):
        self.seed()
        self.write_code_step(stage="plan-coder", sessionId=SESSION)
        self.assertEqual(self.packet("")[0], 0)

    def write_launched_run(self, agent_id, stage="review", later_launch_id=None):
        path = self.write_code_step(stage=stage, sessionId=SESSION, runId="run1")
        events = self.repo / ".git" / "code-step" / "runs" / "run1" / "events.jsonl"
        events.parent.mkdir(parents=True, exist_ok=True)
        rows = [{"event": "dispatch", "id": "d1", "ts": 1, "agent_type": "review-loop", "stage": "review"},
                {"event": "launch", "dispatch": "d1", "ts": 2, "agent_id": agent_id}]
        if later_launch_id:
            rows += [{"event": "dispatch", "id": "d2", "ts": 3, "agent_type": "coder", "stage": "coder"},
                     {"event": "launch", "dispatch": "d2", "ts": 4, "agent_id": later_launch_id}]
        events.write_text("".join(json.dumps(row) + "\n" for row in rows))
        return path

    def test_standalone_review_hand_back_is_read_while_a_code_run_waits_on_another_agent(self):
        self.write_launched_run("run-agent")
        self.seed()
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_hand_back_of_the_agent_the_code_run_launched_is_still_refused(self):
        self.write_launched_run("a1")
        self.seed()
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("code_step.py resume", output)

    def test_pending_standalone_dispatch_after_the_code_run_s_hand_back_reports_no_hand_back_not_the_owner(self):
        self.write_launched_run("a1")
        self.seed()
        self.dispatch()
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-handback", output)
        self.assertNotIn("code_step.py resume", output)

    def test_pending_review_loop_dispatch_the_code_run_logged_after_its_hand_back_is_still_the_run_s(self):
        events = self.write_launched_run("a1").parent / "runs" / "run1" / "events.jsonl"
        self.seed()
        with events.open("a") as events_file:
            events_file.write(json.dumps({"event": "dispatch", "id": "d2", "ts": time.time() + 1,
                                          "agent_type": "review-loop", "stage": "review"}) + "\n")
        self.dispatch()
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("code_step.py resume", output)

    def test_standalone_review_hand_back_is_read_while_a_code_run_at_review_has_no_launch_row_yet(self):
        self.write_code_step(stage="review", sessionId=SESSION, runId="run1")
        self.seed()
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_earlier_review_loop_hand_back_after_a_later_coder_launch_is_still_refused(self):
        self.write_launched_run("a1", later_launch_id="coder-agent")
        self.seed()
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("code_step.py resume", output)

    def test_code_run_hand_back_after_a_standalone_review_is_still_refused(self):
        self.write_launched_run("run-agent")
        self.seed()
        self.assertEqual(self.packet("")[0], 0)
        self.dispatch()
        self.hand_back(CLEAN_EMPTY, agent_id="run-agent")
        self.assertEqual(self.packet("")[0], 2)

    def test_an_unreadable_code_step_state_does_not_block(self):
        self.seed()
        self.write_code_step().write_text("{")
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertNotIn("Traceback", output)

    # ---------- shapes that broke on real hand-backs ----------

    NUMBERED = (
        "status: converged\niter: 1\nfixed: []\nask:\n"
        "1. finding: cap on retries | file_line: src/retry.ts:10 | question: cap at 3? | change: cap at 3 | "
        "gate: code-reviewer | class: smell\n"
        "2) finding: add index | file_line: src/db.ts:5 | question: index tenant_id? | change: add the index | "
        "gate: perf-reviewer | class: perf\n"
        "class_closure: n/a - fixed[] empty\nThe loop found two questions.\n"
    )

    def test_numbered_asks_are_two_asks_and_the_closing_prose_stays_a_trailer(self):
        code, output = self.packet(self.NUMBERED)
        self.assertEqual(code, 0, output)
        self.assertIn("1. src/retry.ts:10", output)
        self.assertIn("2. src/db.ts:5", output)
        self.assertIn("The loop found two questions.", output.split("-----END USER TEXT-----")[0])

    def test_unmarked_ask_prose_is_one_ask_and_still_reaches_the_user(self):
        code, output = self.packet(CLEAN_EMPTY.replace("ask: []", "ask: see the thread above"))
        self.assertEqual(code, 0, output)
        self.assertIn("see the thread above", output)

    def test_ask_with_an_unknown_class_and_a_gate_phrase_is_logged_as_other_and_the_raw_class_is_not_sent(self):
        text = CLEAN_EMPTY.replace(
            "ask: []",
            'ask:\n  - {finding: x, finding_id: a1b2c3d4e5f60003, file_line: "a.ts:1, b.ts:2", question: why?, '
            "change: c, gate: code-reviewer / robustness, class: ops}",
        )
        self.packet(text)
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        row = self.ledger_writes()[0]
        self.assertEqual(
            (row["class"], row["gate"], row["path_key"], row["line"]), ("other", "code-reviewer", "a.ts", "1")
        )
        self.assertNotIn("ops", row.values())
        self.assertNotIn("desc", row)

    def test_a_plan_impact_ask_is_presented_but_not_logged(self):
        text = CLEAN_EMPTY.replace(
            "ask: []",
            'ask:\n  - {finding: "PLAN-IMPACT: queue is at-most-once", '
            "file_line: a.ts:1, question: adopt?, change: adopt it, gate: code-reviewer, class: plan-drift}\n"
            "  - {finding: real ask, finding_id: a1b2c3d4e5f60004, file_line: b.ts:2, question: cap?, change: cap "
            "at 3, gate: code-reviewer, class: smell}",
        )
        code, output = self.packet(text)
        self.assertIn("adopt?", output)
        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertEqual([row["path_key"] for row in self.ledger_writes()], ["b.ts"])

    ASK_WITHOUT_FINDING_ID = CLEAN_EMPTY.replace(
        "ask: []", "ask:\n  - {finding: x, file_line: a.ts:1, question: cap?, change: cap at 3, gate: code-reviewer, "
                   "class: smell}")

    def test_an_ask_the_loop_logged_without_writing_its_id_gets_its_outcome_under_the_logged_id(self):
        self.seed(self.ASK_WITHOUT_FINDING_ID)
        self.stop_row(0, ask_rows=[{"file": "a.ts", "line": 1, "finding_id": "a1b2c3d4e5f60010"}])
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertIn("Logged 1 of 1 ask outcome row(s).", output)
        self.assertNotIn("without a valid finding_id", output)
        [outcome_row] = self.ledger_writes()
        self.assertEqual((outcome_row["finding_id"], outcome_row["ask_outcome"]), ("a1b2c3d4e5f60010", "accepted"))

    def test_an_ask_the_loop_logged_under_a_placeholder_id_also_gets_the_logged_id(self):
        text = self.ask_packet_with_finding_id("none logged")
        self.seed(text)
        self.stop_row(0, ask_rows=[{"file": "a.ts", "line": 1, "finding_id": "a1b2c3d4e5f60011"}])
        self.packet("")
        self.run_script(["asks-done", "accepted"])
        self.assertEqual([row["finding_id"] for row in self.ledger_writes()], ["a1b2c3d4e5f60011"])

    def test_a_valid_id_the_loop_wrote_wins_over_a_logged_row_at_the_same_place(self):
        self.seed(self.ask_packet_with_finding_id("a1b2c3d4e5f60012"))
        self.stop_row(0, ask_rows=[{"file": "a.ts", "line": 1, "finding_id": "a1b2c3d4e5f60013"}])
        self.packet("")
        self.run_script(["asks-done", "accepted"])
        self.assertEqual([row["finding_id"] for row in self.ledger_writes()], ["a1b2c3d4e5f60012"])

    def test_an_ask_the_loop_never_logged_gets_its_ask_row_from_packet_and_one_outcome_under_the_same_id(self):
        self.packet(self.ASK_WITHOUT_FINDING_ID)
        [ask_row] = self.ledger_writes()
        self.assertRegex(ask_row["finding_id"], r"^[0-9a-f]{16}$")
        self.assertEqual((ask_row["actioned"], ask_row["disposition"], ask_row["path_key"], ask_row["line"]),
                         ("ask", "ask", "a.ts", "1"))
        self.assertNotIn("ask_outcome", ask_row)

        self.packet(self.ASK_WITHOUT_FINDING_ID)
        self.assertEqual(len(self.ledger_writes()), 1)

        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("without a valid finding_id", output)
        outcome_row = self.ledger_writes()[1]
        self.assertEqual((outcome_row["finding_id"], outcome_row["ask_outcome"]), (ask_row["finding_id"], "accepted"))
        self.assertEqual(len(self.ledger_writes()), 2)

    def test_a_logged_row_serves_one_ask_and_a_second_ask_at_the_same_place_is_logged_by_packet(self):
        text = CLEAN_EMPTY.replace(
            "ask: []",
            "ask:\n  - {finding: x, file_line: a.ts:1, question: cap?, change: c, gate: code-reviewer, class: smell}\n"
            "  - {finding: y, file_line: a.ts:1, question: cap?, change: c, gate: code-reviewer, class: smell}")
        self.seed(text)
        self.stop_row(0, ask_rows=[{"file": "a.ts", "line": 1, "finding_id": "a1b2c3d4e5f60014"}])
        self.packet("")
        self.run_script(["asks-done", "accepted", "rejected"])
        finding_ids = [row["finding_id"] for row in self.ledger_writes() if "ask_outcome" in row]
        self.assertEqual(len(set(finding_ids)), 2)
        self.assertEqual(finding_ids[0], "a1b2c3d4e5f60014")

    def ask_packet_with_finding_id(self, finding_id_text):
        return CLEAN_EMPTY.replace(
            "ask: []",
            "ask:\n  - {finding: x, finding_id: " + finding_id_text + ", file_line: a.ts:1, "
            "question: cap?, change: cap at 3, gate: code-reviewer, class: smell}",
        )

    def test_an_ask_whose_finding_id_is_a_placeholder_is_logged_by_packet_and_its_outcome_supersedes_that_row(self):
        placeholders = ["none logged", "not logged (no id was printed)", "none", "-", '""', "a1b2c3d4e5f6000",
                        "A1B2C3D4E5F60001", "a1b2c3d4e5f600011", "a1b2c3d4e5f6000g"]
        for finding_id_text in placeholders:
            with self.subTest(finding_id=finding_id_text):
                writes_before = len(self.ledger_writes())
                self.packet(self.ask_packet_with_finding_id(finding_id_text))
                code, output = self.run_script(["asks-done", "modified:tighten the cap"])
                self.assertEqual(code, 0, output)
                self.assertIn("Logged 1 of 1 ask outcome row(s).", output)
                self.assertNotIn("without a valid finding_id", output)
                ask_row, outcome_row = self.ledger_writes()[writes_before:]
                self.assertRegex(outcome_row["finding_id"], r"^[0-9a-f]{16}$")
                self.assertEqual(ask_row["finding_id"], outcome_row["finding_id"])
                self.assertEqual(outcome_row["ask_outcome"], "modified")
                code, output = self.run_script(["asks-done", "modified:tighten the cap"])
                self.assertEqual(code, 0, output)
                self.assertIn("The ask outcomes were already logged.", output)
                self.assertEqual(len(self.ledger_writes()), writes_before + 2)

    def test_an_ask_row_the_ledger_refuses_leaves_the_outcome_under_a_new_finding_id_and_says_so(self):
        self.packet(self.ASK_WITHOUT_FINDING_ID, FAKE_LEDGER_WRITE_EXIT="1")
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertEqual(len(self.ledger_writes()), 1)
        self.assertIn("1 ask(s) without a valid finding_id are logged under a new finding_id.", output)

    def test_an_ask_with_a_valid_finding_id_among_placeholder_asks_keeps_its_id(self):
        text = CLEAN_EMPTY.replace(
            "ask: []",
            "ask:\n"
            "  - {finding: x, finding_id: none logged, file_line: a.ts:1, question: cap?, change: cap at 3, "
            "gate: code-reviewer, class: smell}\n"
            "  - {finding: y, finding_id: a1b2c3d4e5f60005, file_line: b.ts:2, question: cap?, change: cap at 3, "
            "gate: code-reviewer, class: smell}",
        )
        self.packet(text)
        code, output = self.run_script(["asks-done", "modified:tighten the cap", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertIn("Logged 2 of 2 ask outcome row(s).", output)
        self.assertNotIn("without a valid finding_id", output)
        ask_row, new_id_row, kept_id_row = self.ledger_writes()
        self.assertNotIn("ask_outcome", ask_row)
        self.assertEqual(new_id_row["finding_id"], ask_row["finding_id"])
        self.assertEqual(kept_id_row["finding_id"], "a1b2c3d4e5f60005")
        self.assertEqual([row["ask_outcome"] for row in (new_id_row, kept_id_row)], ["modified", "accepted"])

    def test_a_valid_finding_id_with_surrounding_spaces_is_logged_without_them(self):
        self.packet(self.ask_packet_with_finding_id('" a1b2c3d4e5f60006 "'))
        code, output = self.run_script(["asks-done", "modified:tighten the cap"])
        self.assertEqual(code, 0, output)
        self.assertEqual([row["finding_id"] for row in self.ledger_writes()], ["a1b2c3d4e5f60006"])

    def test_present_asks_prints_the_gate_mark_line(self):
        _code, output = self.packet(WITH_ASK)
        self.assertIn("review-gate-mark clean", output)

    def test_present_asks_names_each_proposed_change_and_what_each_outcome_does(self):
        code, output = self.packet(WITH_ASK)
        self.assertEqual(code, 0, output)
        self.assertIn("Proposed change: cap retries at 3", output)
        self.assertIn("Proposed change: add an index on tenant_id", output)
        self.assertIn("accepted: make the proposed change", output)
        self.assertIn("rejected: leave the code as it stands", output)

    def test_an_either_or_ask_with_no_proposed_change_is_a_parse_failure(self):
        self.assert_parse_failure(WITH_ASK.replace('    change: "cap retries at 3"\n', ""), "ask entry has no change")

    def test_empty_list_key_does_not_swallow_the_next_unindented_key(self):
        text = "status: converged\niter: 1\nfixed: []\nask: []\nclass_closure: all queries listed\nfiles_touched: []\n"
        _code, output = self.packet(text)
        self.assertIn("Class closure: all queries listed", output)

    def test_bare_not_applicable_class_closure_with_empty_fixed_prints_one_line(self):
        _code, output = self.packet(CLEAN_EMPTY.replace("n/a - fixed[] empty", "n/a"))
        self.assertEqual(output.count("Class closure"), 1)
        self.assertNotIn("receipt is missing", output)

    def test_findings_remaining_show_on_converged(self):
        _code, output = self.packet(
            CONVERGED.replace(
                "findings_remaining: []",
                'findings_remaining: [{disposition: fix, finding: "left over", file_line: a.ts:1}]',
            )
        )
        self.assertIn("### Findings remaining", output)
        self.assertIn("left over", output)

    # ---------- side effects happen once ----------

    def escape_ids(self):
        return [row["path_key"] for row in self.escape_rows()]

    def posts(self):
        return (
            [call for call in self.gh_log.read_text().splitlines() if call.startswith("api")]
            if self.gh_log.exists()
            else []
        )

    def test_re_running_packet_posts_logs_and_jumps_nothing_twice(self):
        flags = ("--source", "conversation", "--escape", self.escape_spec(), "--aikido", "src/orders.ts:42=111")
        self.packet(CONVERGED, *flags, skill="fix")
        code, output = self.packet(CONVERGED, *flags, skill="fix")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.escape_ids(), ["src/orders.ts"])
        self.assertEqual(len(self.posts()), 1)
        self.assertIn("already posted", output)

    def test_re_running_packet_with_asks_does_not_jump_again(self):
        self.packet(WITH_ASK)
        self.packet(WITH_ASK)
        self.assertEqual(len(self.jump_log.read_text().splitlines()), 1)

    def test_packet_after_asks_done_logs_nothing_more_and_keeps_the_stage(self):
        self.packet(WITH_ASK)
        self.run_script(["asks-done", "accepted", "accepted"])
        code, output = self.packet(WITH_ASK)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertEqual(len(self.ledger_writes()), 2)

    def test_asks_done_twice_is_a_no_op(self):
        self.packet(WITH_ASK)
        self.run_script(["asks-done", "accepted", "accepted"])
        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertIn("already logged", output)
        self.assertEqual(len(self.ledger_writes()), 2)

    def test_asks_done_after_a_failed_row_retries_only_the_unlogged_ones(self):
        self.packet(WITH_ASK)
        self.run_script(["asks-done", "accepted", "accepted"], REVIEW_FIX_CLAUDE_DIR=str(self.temp_root / "nowhere"))
        self.assertEqual(self.ledger_writes(), [])
        _code, _output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(len(self.ledger_writes()), 2)

    def test_escape_verb_logs_from_the_saved_packet_once(self):
        self.packet(CONVERGED, "--source", "conversation", skill="fix")
        code, output = self.run_script(["escape", "--escape", self.escape_spec()])
        self.assertEqual(code, 0, output)
        self.assertEqual(self.escape_ids(), ["src/orders.ts"])
        code, output = self.run_script(["escape", "--escape", self.escape_spec()])
        self.assertIn("already logged", output)
        self.assertEqual(self.escape_ids(), ["src/orders.ts"])

    def test_escape_verb_after_a_review_packet_is_refused(self):
        self.packet(CONVERGED)
        code, output = self.run_script(["escape", "--escape", self.escape_spec()])
        self.assertEqual(code, 2, output)

    def test_escape_matches_normalised_paths_and_paths_named_in_the_finding_text(self):
        text = CLEAN_EMPTY.replace("fixed: []", 'fixed: [{finding: "tenant filter missing, also see lib/q.ts:9", '
                                   'file_line: "`./src/orders.ts:42`", blocker: false}]')
        self.packet(text, "--source", "conversation", skill="fix")
        for path in ("src/orders.ts:42", "./lib/q.ts"):
            _code, output = self.run_script(["escape", "--escape", self.escape_spec(file=path)])
            self.assertIn("escape logged", output)
        self.assertEqual(self.escape_ids(), ["src/orders.ts", "lib/q.ts"])

    def test_a_plain_text_skipped_entry_with_aikido_does_not_crash(self):
        text = CONVERGED.replace('skipped_fp: [{item: "src/a.ts:9 possible null", reason: "guarded two lines above"}]',
                                 "skipped_fp:\n  - src/a.ts:9 possible null")
        code, output = self.packet(text, "--aikido", "src/zzz.ts:1=5", skill="fix")
        self.assertEqual(code, 0, output)
        self.assertNotIn("Traceback", output)

    def test_critical_blocker_and_cap_reached_still_post_the_aikido_replies(self):
        for text, target in ((BLOCKER, "src/auth.ts:12=31"), (CAP, "src/q.ts:7=32")):
            self.gh_log.write_text("") if self.gh_log.exists() else None
            code, output = self.packet(text, "--aikido", target, skill="fix")
            self.assertEqual(code, 0, output)
            self.assertTrue(output.startswith("ACTION: stop"), output)
            self.assertEqual(len(self.posts()), 1, output)
            self.assertIn("Not fixed in this pass", self.gh_log.read_text())

    # ---------- walk: every state and every verb ----------

    def test_every_verb_in_every_state_ends_with_an_action_line_and_no_traceback(self):
        states = {"none": None, "asks": WITH_ASK, "plan-impact": PLAN_IMPACT, "render": CONVERGED, "blocker": BLOCKER,
                  "parse-failed": "status: bogus"}
        verbs = {"packet": ["packet", "--skill", "review"], "escape": ["escape", "--escape", self.escape_spec()],
                 "asks-done": ["asks-done", "accepted", "accepted"], "decide": ["decide", "keep"]}
        for state_name, text in states.items():
            for verb_name, arguments in verbs.items():
                with self.subTest(state=state_name, verb=verb_name):
                    self.set_up_fresh_state(text)
                    code, output = self.run_script(arguments, CONVERGED if verb_name == "packet" else "")
                    self.assertNotIn("Traceback", output)
                    self.assertIn(code, (0, 2), output)
                    self.assertIn("ACTION:", output)

    def set_up_fresh_state(self, text):
        state_file = self.repo / ".git" / "review-fix" / "state.json"
        if state_file.exists():
            state_file.unlink()
        if text is not None:
            self.packet(text)

    def test_done_and_redispatch_stages_survive_every_verb(self):
        self.packet(PLAN_IMPACT)
        self.run_script(["decide", "keep", "--by", "user", "--ruling", "keep it"])
        for arguments in (
            ["decide", "keep", "--by", "user", "--ruling", "keep it"],
            ["asks-done", "accepted"],
            ["escape", "--escape", self.escape_spec()],
        ):
            _, output = self.run_script(arguments)
            self.assertNotIn("Traceback", output)
            self.assertIn("ACTION:", output)
        _code, output = self.packet(PLAN_IMPACT)
        self.assertIn("ACTION: done", output)

    def test_usage_error_without_a_skill_stops_loudly(self):
        code, output = self.run_script(["packet"], CLEAN_EMPTY)
        self.assertEqual(code, 2)
        self.assertIn("stop-usage", output)

    def test_unknown_subcommand_prints_usage_and_fails(self):
        code, output = self.run_script(["nope"])
        self.assertEqual(code, 2)
        self.assertIn("review_fix.py", output)


if __name__ == "__main__":
    unittest.main()
