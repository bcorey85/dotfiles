import json
import os
import pathlib
import subprocess
import tempfile
import unittest

SCRIPT = pathlib.Path(os.environ.get("REVIEW_FIX_SCRIPT") or pathlib.Path.home() / ".claude" / "scripts" / "review-fix.py")
HANDBACK = SCRIPT.parent / "handback.py"
SESSION = "11111111-aaaa-bbbb-cccc-222222222222"
OTHER_SESSION = "99999999-aaaa-bbbb-cccc-888888888888"
CLAUDE_DIR = pathlib.Path(os.environ.get("REVIEW_FIX_CLAUDE_DIR") or pathlib.Path.home() / ".claude")

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

WITH_ASK = """status: converged
iter: 1
fixed: []
ask:
  - finding: "retry count looks arbitrary"
    file_line: src/retry.ts:10
    question: "Should retries be capped at 3 or configurable?"
    gate: code-reviewer
    class: smell
  - {finding: "no index", file_line: src/db.ts:5, question: "Add an index on tenant_id?", gate: perf-reviewer, class: perf}
class_closure: n/a - fixed[] empty
"""

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

CAP = """status: cap-reached
iter: 2 of 2
findings_remaining:
  - {disposition: fix, finding: "still racy", file_line: src/q.ts:7}
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
        tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(tempDir.cleanup)
        self.tempRoot = pathlib.Path(tempDir.name)
        self.repo = self.tempRoot / "myrepo"
        self.repo.mkdir()
        self.findingsFile = self.tempRoot / "findings.jsonl"
        self.escapesFile = self.tempRoot / "escapes.jsonl"
        self.jumpLog = self.tempRoot / "jump.log"
        self.ghLog = self.tempRoot / "gh.log"
        self.storeDir = self.tempRoot / "store"
        self.fakeJump = self.fake_command("nvim-jump", f'echo "$@" >> {self.jumpLog}\nexit "${{JUMP_EXIT:-0}}"')
        self.fakeGh = self.fake_command(
            "gh", f'echo "$@" >> {self.ghLog}\ncase "$1 $2" in "repo view") echo acme/web;; "pr view") echo 7;; esac\n'
                  'exit "${GH_EXIT:-0}"')
        self.git("init", "-q")
        (self.repo / "README.md").write_text("hi\n")
        self.git("add", "README.md")
        self.git("commit", "-q", "-m", "init")

    def fake_command(self, name, body):
        path = self.tempRoot / name
        path.write_text("#!/usr/bin/env bash\n" + body + "\n")
        path.chmod(0o755)
        return path

    def environment(self, **extra):
        return {**os.environ, **GIT_ENV, "REVIEW_FINDINGS_FILE": str(self.findingsFile),
                "REVIEW_ESCAPES_FILE": str(self.escapesFile), "REVIEW_FIX_NVIM_JUMP": str(self.fakeJump),
                "REVIEW_FIX_GH": str(self.fakeGh), "REVIEW_FIX_CLAUDE_DIR": str(CLAUDE_DIR),
                "HANDBACK_STORE_DIR": str(self.storeDir), "CLAUDE_CODE_SESSION_ID": SESSION,
                "CLAUDE_TOOLKIT_TELEMETRY": "1", **extra}

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True, capture_output=True)

    def run_script(self, args, stdin="", **extra):
        done = subprocess.run(["python3", "-I", str(SCRIPT), *args], cwd=self.repo, input=stdin, text=True,
                              capture_output=True, env=self.environment(**extra))
        return done.returncode, done.stdout + done.stderr

    def packet(self, text, *flags, skill="review", **extra):
        return self.run_script(["packet", "--skill", skill, *flags], text, **extra)

    def rows(self, path):
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    # ---------- routing ----------

    def test_converged_packet_renders_in_fixed_order_and_asks_for_the_gate_mark(self):
        code, output = self.packet(CONVERGED)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)
        self.assertIn("`~/.claude/scripts/review-gate-mark clean`", output)
        self.assertNotIn("bash ~/.claude/scripts/review-gate-mark", output)
        self.assertLess(output.index("[blocker] orders query lacked"), output.index("unused import"))
        self.assertIn("Class closure: enumerated every query", output)
        self.assertIn("### Skipped as false positives", output)
        self.assertIn("guarded two lines above", output)
        self.assertIn("auth.ts came back clean", output)
        self.assertNotIn("Do not present this run as clean", output)

    def test_converged_with_bare_none_class_closure_says_the_receipt_is_missing(self):
        code, output = self.packet(CONVERGED.replace(
            "class_closure: enumerated every query in orders.ts; the tenant filter now sits on all 3", "class_closure: none"))
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

    def test_cap_reached_stops_and_keeps_the_gate_dirty(self):
        code, output = self.packet(CAP)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("still racy", output)
        self.assertIn("stays blocked", output)

    def test_plan_impact_prints_the_modal_and_decide_builds_the_redispatch_with_both_counters(self):
        code, output = self.packet(PLAN_IMPACT)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: ask-user-plan-impact", output)
        self.assertIn("the queue is at-most-once", output)
        self.assertIn("Adopt plan change / Keep plan as written / Discuss", output)
        self.assertIn("iter=1 spec_iter=2", output)

        planFile = self.tempRoot / "plan.md"
        planFile.write_text("# Plan\n\n## Phase 1\n\nwork\n")
        code, output = self.run_script(["decide", "adopt", "--by", "user", "--ruling", "yes, add the table",
                                        "--plan", str(planFile)])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        self.assertIn("plan_impact: RESOLVED - Adopt plan change.", output)
        self.assertIn("iter=1", output)
        self.assertIn("spec_iter=2", output)
        planText = planFile.read_text()
        self.assertIn("## Plan Deviations", planText)
        self.assertIn("Adopt plan change | t", planText)

    def test_decide_appends_to_an_existing_plan_deviations_section_before_the_next_heading(self):
        self.packet(PLAN_IMPACT)
        planFile = self.tempRoot / "plan.md"
        planFile.write_text("# Plan\n\n## Plan Deviations\n\n- old entry\n\n## Phase 1\n\nwork\n")
        self.run_script(["decide", "keep", "--by", "user", "--ruling", "keep it", "--plan", str(planFile)])
        lines = planFile.read_text().splitlines()
        self.assertLess(lines.index("- old entry"), next(i for i, l in enumerate(lines) if "Keep plan as written" in l))
        self.assertLess(next(i for i, l in enumerate(lines) if "Keep plan as written" in l), lines.index("## Phase 1"))

    def test_decide_discuss_does_not_redispatch(self):
        self.packet(PLAN_IMPACT)
        code, output = self.run_script(["decide", "discuss"])
        self.assertIn("ACTION: discuss", output)
        self.assertNotIn("redispatch", output)

    def test_decide_discuss_prints_the_decide_commands_for_both_by_values(self):
        self.packet(PLAN_IMPACT)
        code, output = self.run_script(["decide", "discuss"])
        self.assertEqual(code, 0, output)
        for word in ("adopt", "keep"):
            for by in ("user", "session"):
                self.assertIn(f"review-fix.py decide {word} --by {by} --ruling", output)
        self.assertEqual(4, output.count("--plan <the plan path, when the handoff names one>"))

    def test_plan_impact_modal_names_the_by_form(self):
        code, output = self.packet(PLAN_IMPACT)
        self.assertIn("decide <adopt|keep> --by user --ruling", output)
        self.assertIn("pass `--by session`", output)
        self.assertIn("--plan <the plan path, when the handoff names one>", output)

    def test_decide_without_a_ruling_stops_with_the_usage_line_and_records_nothing(self):
        self.packet(PLAN_IMPACT)
        stageBefore = self.stored_stage()
        planFile = self.tempRoot / "plan.md"
        planFile.write_text("# Plan\n")
        for decision in ("adopt", "keep"):
            with self.subTest(decision=decision):
                code, output = self.run_script(["decide", decision, "--by", "user", "--plan", str(planFile)])
                self.assertEqual(code, 2)
                self.assertIn("ACTION: stop-usage", output)
                self.assertIn(f"decide {decision} needs --ruling", output)
                self.assertEqual(stageBefore, self.stored_stage())
                self.assertEqual("# Plan\n", planFile.read_text())

    def stored_stage(self):
        return json.loads((self.repo / ".git" / "review-fix" / "state.json").read_text())["stage"]

    def test_decide_without_by_stops_with_the_usage_line_and_leaves_the_state(self):
        self.packet(PLAN_IMPACT)
        stageBefore = self.stored_stage()
        planFile = self.tempRoot / "plan.md"
        planFile.write_text("# Plan\n")
        code, output = self.run_script(["decide", "adopt", "--ruling", "my call", "--plan", str(planFile)])
        self.assertEqual(code, 2)
        self.assertIn("ACTION: stop-usage", output)
        self.assertIn('decide <adopt|keep> --by <user|session> --ruling "<the user\'s answer>"', output)
        self.assertEqual(stageBefore, self.stored_stage())
        self.assertEqual("# Plan\n", planFile.read_text())

    def test_decide_with_a_bad_by_value_stops_with_the_usage_line(self):
        self.packet(PLAN_IMPACT)
        stageBefore = self.stored_stage()
        code, output = self.run_script(["decide", "keep", "--by", "maybe", "--ruling", "my call"])
        self.assertEqual(code, 2)
        self.assertIn("ACTION: stop-usage", output)
        self.assertIn("--by <user|session>", output)
        self.assertIn("needs --by user or --by session", output)
        self.assertEqual(stageBefore, self.stored_stage())

    def test_decide_by_with_no_value_stops_with_the_usage_line(self):
        self.packet(PLAN_IMPACT)
        stageBefore = self.stored_stage()
        code, output = self.run_script(["decide", "keep", "--by", "--ruling", "my call"])
        self.assertEqual(code, 2)
        self.assertIn("--by <user|session>", output)
        self.assertEqual(stageBefore, self.stored_stage())

    def test_decide_by_session_signs_as_the_session_not_the_user(self):
        self.packet(PLAN_IMPACT)
        planFile = self.tempRoot / "plan.md"
        planFile.write_text("# Plan\n")
        code, output = self.run_script(["decide", "adopt", "--by", "session", "--ruling", "my own call",
                                        "--plan", str(planFile)])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        self.assertIn("The session ruled, not the user.", output)
        self.assertIn("| the session, not the user | my own call", planFile.read_text())
        self.assertNotIn("| t |", planFile.read_text())

    def test_decide_by_user_signs_with_the_git_user_name(self):
        self.packet(PLAN_IMPACT)
        planFile = self.tempRoot / "plan.md"
        planFile.write_text("# Plan\n")
        code, output = self.run_script(["decide", "keep", "--by", "user", "--ruling", "keep it", "--plan", str(planFile)])
        self.assertEqual(code, 0, output)
        self.assertIn("| Keep plan as written | t | keep it", planFile.read_text())
        self.assertNotIn("The session ruled", output)

    def test_decide_without_a_waiting_plan_impact_fails(self):
        self.packet(CONVERGED)
        code, output = self.run_script(["decide", "adopt"])
        self.assertEqual(code, 2)
        self.assertIn("stop-usage", output)

    # ---------- asks ----------

    def test_asks_are_jumped_listed_and_logged_with_their_outcomes(self):
        code, output = self.packet(WITH_ASK, "--scope", "branch-exit")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: present-asks", output)
        self.assertIn("1. src/retry.ts:10", output)
        self.assertIn("Should retries be capped at 3 or configurable?", output)
        jump = self.jumpLog.read_text()
        self.assertIn("--note Should retries be capped at 3 or configurable? src/retry.ts:10", jump)
        self.assertIn("src/db.ts:5", jump)

        code, output = self.run_script(["asks-done", "accepted", "rejected:not worth it"])
        self.assertEqual(code, 0, output)
        rows = self.rows(self.findingsFile)
        self.assertEqual([row["ask_outcome"] for row in rows], ["accepted", "rejected"])
        self.assertEqual(rows[0]["gate"], "code-reviewer")
        self.assertEqual(rows[1]["gate"], "perf-reviewer")
        self.assertEqual(rows[1]["class"], "perf")
        self.assertEqual(rows[0]["scope"], "branch-exit")
        self.assertEqual(rows[0]["file"], "src/retry.ts")
        self.assertEqual(rows[0]["line"], 10)
        self.assertEqual(rows[0]["repo"], "myrepo")
        self.assertEqual(rows[1]["desc"], "ask resolved: not worth it")
        self.assertEqual(rows[0]["iter"], 1)

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
        self.assertEqual(self.rows(self.findingsFile), [])

    def test_asks_done_with_an_unknown_outcome_fails_loudly(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "accepted", "maybe"])
        self.assertEqual(code, 2)
        self.assertIn("accepted|rejected|modified", output)
        self.assertEqual(self.rows(self.findingsFile), [])

    def test_asks_done_without_waiting_asks_fails(self):
        self.packet(CONVERGED)
        code, output = self.run_script(["asks-done", "accepted"])
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
        rows = self.rows(self.escapesFile)
        self.assertEqual(len(rows), 1, output)
        self.assertEqual(rows[0]["stage_found"], "walkthrough")
        self.assertEqual(rows[0]["gate_missed"], "review")
        self.assertEqual(rows[0]["guard"], "convention")
        self.assertEqual(rows[0]["lane"], "code")
        self.assertEqual(rows[0]["file"], "src/orders.ts")

    def test_escape_from_a_cc_comment_is_not_logged(self):
        code, output = self.packet(CONVERGED, "--source", "cc", "--escape", self.escape_spec(), skill="fix")
        self.assertEqual(code, 0, output)
        self.assertEqual(self.rows(self.escapesFile), [])
        self.assertIn("not the conversation", output)

    def test_escape_for_a_file_with_no_fixed_entry_is_not_logged(self):
        code, output = self.packet(CONVERGED, "--source", "conversation",
                                   "--escape", self.escape_spec(file="src/other.ts"), skill="fix")
        self.assertEqual(self.rows(self.escapesFile), [])
        self.assertIn("no fixed[] entry names that file", output)

    def test_escape_with_a_bad_vocabulary_value_fails_before_anything_is_logged(self):
        code, output = self.packet(CONVERGED, "--source", "conversation",
                                   "--escape", self.escape_spec(guard="vibes"), skill="fix")
        self.assertEqual(code, 2)
        self.assertIn("guard='vibes'", output)
        self.assertEqual(self.rows(self.escapesFile), [])

    def test_escape_missing_a_field_fails_loudly(self):
        spec = self.escape_spec().replace("|severity=high", "")
        code, output = self.packet(CONVERGED, "--source", "conversation", "--escape", spec, skill="fix")
        self.assertEqual(code, 2)
        self.assertIn("lacks severity", output)

    def test_escape_on_a_non_converged_status_is_not_logged(self):
        code, output = self.packet(CAP, "--source", "conversation", "--escape", self.escape_spec(), skill="fix")
        self.assertEqual(self.rows(self.escapesFile), [])

    def test_escape_flag_on_review_is_refused(self):
        code, output = self.packet(CONVERGED, "--escape", self.escape_spec())
        self.assertEqual(code, 2)

    def test_aikido_replies_follow_fixed_skipped_and_other_dispositions(self):
        text = CONVERGED.replace("ask: []", 'ask: [{finding: "pick a cap", file_line: src/c.ts:4, question: "cap?", gate: code-reviewer, class: smell}]')
        code, output = self.packet(text, "--aikido", "src/orders.ts:42=111", "--aikido", "src/a.ts:9=222",
                                   "--aikido", "src/c.ts:4=333", skill="fix")
        self.assertEqual(code, 0, output)
        calls = self.ghLog.read_text().splitlines()
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
        code, output = self.packet(text, skill="fix")
        self.assertNotIn("Class closure", output)
        self.assertNotIn("receipt", output)

    # ---------- malformed packets: every one stops loudly ----------

    def assert_parse_failure(self, text, expected, skill="review"):
        code, output = self.packet(text, skill=skill)
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-parse-failure", output)
        self.assertIn(expected, output)
        self.assertIn("`~/.claude/scripts/review-gate-mark dirty`", output)
        self.assertNotIn("render-and-finish", output)
        self.assertEqual(self.rows(self.findingsFile), [])

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
        self.assert_parse_failure(CONVERGED.replace('finding: "orders query lacked a tenant filter", ', ""), "no finding")

    def test_ask_entry_without_a_question_is_a_parse_failure(self):
        self.assert_parse_failure(WITH_ASK.replace('finding: "no index", ', "").replace('question: "Add an index on tenant_id?", ', ""), "no question")

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

    def test_a_parse_failure_cancels_the_asks_of_the_previous_packet(self):
        self.packet(WITH_ASK)
        self.packet("status: bogus")
        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 2, output)
        self.assertEqual(self.rows(self.findingsFile), [])

    # ---------- whitespace and format tolerance ----------

    def test_extra_whitespace_and_a_code_fence_around_the_packet_still_parse(self):
        padded = "```\n" + "\n".join("   " + line + "   " if line else line for line in CONVERGED.splitlines()) + "\n\n\n```\n"
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

    def test_perf_entries_render_under_their_own_heading_with_the_principle(self):
        text = CLEAN_EMPTY + 'perf:\n  - {finding: "N+1 in loader", file_line: src/l.ts:3, principle: "batch the lookups"}\n'
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("### Perf findings", output)
        self.assertIn("Principle: batch the lookups", output)

    def test_finding_text_containing_a_comma_and_key_word_keeps_its_whole_text(self):
        text = CLEAN_EMPTY.replace("fixed: []", 'fixed: [{finding: "guard the read, then class: fix it", file_line: a.ts:1, blocker: false}]')
        code, output = self.packet(text)
        self.assertIn("guard the read, then class: fix it", output)

    # ---------- shapes seen in real review-loop hand-backs ----------

    def test_unbracketed_key_value_asks_with_dot_semicolon_and_pipe_separators_parse(self):
        text = CLEAN_EMPTY.replace("ask: []", "ask:\n"
            "- finding: cache lock spans the scan. file_line: serve.go:162,188. question: what staleness is fine? gate: code-reviewer. class: perf\n"
            "- finding: timeouts left unset; file_line: cli/serve.go:35; question: out of scope? gate: robustness; class: ops\n"
            "- finding: ReadHeaderTimeout question | file_line: cli/serve.go:35 | question: use an http.Server? | gate: robustness | class: ops")
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("what staleness is fine?", output)
        self.assertIn("use an http.Server?", output)

    def test_flow_ask_with_a_finding_but_no_question_uses_the_finding_as_the_question(self):
        text = CLEAN_EMPTY.replace("ask: []", 'ask:\n  - {finding: "Accept it as the contract and update the README?", file_line: "src/inventory.ts:103-110", gate: code-reviewer, class: docs}')
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("Accept it as the contract", output)

    def test_flow_ask_whose_keys_follow_a_period_parses(self):
        text = CLEAN_EMPTY.replace("ask: []", "ask:\n  - {finding: The rules file wants interface. file_line: backend/a.ts:1, question: Convert the shapes? gate: code-reviewer, class: docs}")
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("Convert the shapes?", output)

    def test_free_text_file_line_and_a_comma_list_of_lines_parse(self):
        text = CLEAN_EMPTY.replace("ask: []", "ask:\n- finding: parseDateOnly is unresolved | file_line: service.test.ts:1313 area | question: drop it? | gate: carried | class: carried")
        text = text.replace("fixed: []", 'fixed: [{finding: "spec gap", file_line: "spec.md:432, :1521-1523", blocker: false}]')
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
        self.assert_parse_failure("status: pending. This is not a convergence packet. The verification pass has not reported.\n\nDone so far:\n- fixed\n", "status is")

    def test_a_deferred_packet_with_asks_but_no_findings_remaining_is_a_parse_failure(self):
        text = "status: deferred\niter: 1\nfixed: []\nskipped_fp: []\nblockers: []\nfindings_remaining: []\nask:\n- {finding: x, file_line: a.ts:1, question: y?}\n"
        self.assert_parse_failure(text, "findings_remaining")

    def test_a_cap_reached_packet_with_an_empty_findings_remaining_is_a_parse_failure(self):
        self.assert_parse_failure("status: cap-reached\niter: 2\nfixed: []\nblockers: []\nfindings_remaining: [] (none open)\n", "findings_remaining")

    # ---------- no-paste: saved hand-back ----------

    def hook(self, event, which=None, **extra):
        arguments = ["hook", which] if which else ["hook"]
        done = subprocess.run(["python3", "-I", str(HANDBACK), *arguments], cwd=self.tempRoot,
                              input=json.dumps(event), text=True, capture_output=True, env=self.environment(**extra))
        return done.returncode, done.stdout + done.stderr

    def dispatch(self, session=SESSION, subagent="review-loop"):
        return self.hook({"session_id": session, "tool_name": "Agent", "tool_input": {"subagent_type": subagent}})

    def hand_back(self, message=CONVERGED, session=SESSION, agent="review-loop", agentId="a1"):
        return self.hook({"session_id": session, "tool_name": "SubagentHandback", "agent_type": agent,
                          "agent_id": agentId, "tool_input": {"message": message}})

    def seed(self, message=CONVERGED, session=SESSION):
        self.dispatch(session)
        self.hand_back(message, session)

    def test_saved_hand_back_is_read_when_stdin_is_empty(self):
        self.seed()
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_session_with_no_dispatch_on_record_is_refused(self):
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("no review-loop dispatch on record", output)
        self.assertIn("`~/.claude/scripts/review-gate-mark dirty`", output)

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
        self.hand_back(CLEAN_EMPTY, agentId="a2")
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

    def test_sessions_in_one_repo_keep_separate_miss_counts(self):
        self.dispatch(OTHER_SESSION)
        code, output = self.packet("", CLAUDE_CODE_SESSION_ID=OTHER_SESSION)
        self.assertIn("Re-dispatch review-loop once", output)
        self.dispatch()
        code, output = self.packet("")
        self.assertIn("Re-dispatch review-loop once", output)
        self.assertNotIn("Stop. Do not re-dispatch", output)

    def test_review_and_fix_keep_separate_miss_counts(self):
        self.seed(WITH_ASK)
        self.dispatch()
        self.packet("", skill="review")
        self.dispatch()
        code, output = self.packet("", skill="fix")
        self.assertIn("Re-dispatch review-loop once", output)
        self.dispatch()
        code, output = self.packet("", skill="review")
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
        self.hand_back(WITH_ASK, agentId="a2")
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: present-asks", output)
        self.assertEqual(len(self.jumpLog.read_text().splitlines()), 2)
        self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(len(self.rows(self.findingsFile)), 4)

    def test_re_running_packet_on_the_same_stored_hand_back_is_one_run(self):
        self.seed(WITH_ASK)
        self.packet("")
        self.run_script(["asks-done", "accepted", "accepted"])
        code, output = self.packet("")
        self.assertIn("ACTION: done", output)
        self.assertEqual(len(self.rows(self.findingsFile)), 2)

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
        codeStep = self.repo / ".git" / "code-step"
        codeStep.mkdir(exist_ok=True)
        (codeStep / "state.json").write_text(json.dumps(fields))
        return codeStep / "state.json"

    def test_code_step_state_of_the_same_session_blocks_a_saved_read_and_is_named(self):
        self.seed()
        path = self.write_code_step(stage="review", sessionId=SESSION)
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn(str(path), output)
        self.assertIn("code-step.py after-review", output)

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

    # ---------- shapes that broke on real hand-backs ----------

    NUMBERED = ("status: converged\niter: 1\nfixed: []\nask:\n"
                "1. finding: cap on retries | file_line: src/retry.ts:10 | question: cap at 3? | gate: code-reviewer | class: smell\n"
                "2) finding: add index | file_line: src/db.ts:5 | question: index tenant_id? | gate: perf-reviewer | class: perf\n"
                "class_closure: n/a - fixed[] empty\nThe loop found two questions.\n")

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

    def test_ask_with_an_unknown_class_and_a_gate_phrase_is_logged_as_other_with_the_raw_class_kept(self):
        text = CLEAN_EMPTY.replace("ask: []", "ask:\n  - {finding: x, file_line: \"a.ts:1, b.ts:2\", question: why?, "
                                   "gate: code-reviewer / robustness, class: ops}")
        self.packet(text)
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        row = self.rows(self.findingsFile)[0]
        self.assertEqual((row["class"], row["gate"], row["file"], row["line"]), ("other", "code-reviewer", "a.ts", 1))
        self.assertIn("[class: ops]", row["desc"])

    def test_a_plan_impact_ask_is_presented_but_not_logged(self):
        text = CLEAN_EMPTY.replace("ask: []", "ask:\n  - {finding: \"PLAN-IMPACT: queue is at-most-once\", "
                                   "file_line: a.ts:1, question: adopt?, gate: code-reviewer, class: plan-drift}\n"
                                   "  - {finding: real ask, file_line: b.ts:2, question: cap?, gate: code-reviewer, class: smell}")
        code, output = self.packet(text)
        self.assertIn("adopt?", output)
        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertEqual([row["file"] for row in self.rows(self.findingsFile)], ["b.ts"])

    def test_present_asks_prints_the_gate_mark_line(self):
        code, output = self.packet(WITH_ASK)
        self.assertIn("review-gate-mark clean", output)

    def test_empty_list_key_does_not_swallow_the_next_unindented_key(self):
        text = "status: converged\niter: 1\nfixed: []\nask: []\nclass_closure: all queries listed\nfiles_touched: []\n"
        code, output = self.packet(text)
        self.assertIn("Class closure: all queries listed", output)

    def test_bare_not_applicable_class_closure_with_empty_fixed_prints_one_line(self):
        code, output = self.packet(CLEAN_EMPTY.replace("n/a - fixed[] empty", "n/a"))
        self.assertEqual(output.count("Class closure"), 1)
        self.assertNotIn("receipt is missing", output)

    def test_findings_remaining_show_on_converged(self):
        code, output = self.packet(CONVERGED.replace("findings_remaining: []",
                                                     'findings_remaining: [{disposition: fix, finding: "left over", file_line: a.ts:1}]'))
        self.assertIn("### Findings remaining", output)
        self.assertIn("left over", output)

    # ---------- side effects happen once ----------

    def escape_ids(self):
        return [row["file"] for row in self.rows(self.escapesFile)]

    def posts(self):
        return [call for call in self.ghLog.read_text().splitlines() if call.startswith("api")] if self.ghLog.exists() else []

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
        self.assertEqual(len(self.jumpLog.read_text().splitlines()), 1)

    def test_packet_after_asks_done_logs_nothing_more_and_keeps_the_stage(self):
        self.packet(WITH_ASK)
        self.run_script(["asks-done", "accepted", "accepted"])
        code, output = self.packet(WITH_ASK)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertEqual(len(self.rows(self.findingsFile)), 2)

    def test_asks_done_twice_is_a_no_op(self):
        self.packet(WITH_ASK)
        self.run_script(["asks-done", "accepted", "accepted"])
        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertIn("already logged", output)
        self.assertEqual(len(self.rows(self.findingsFile)), 2)

    def test_asks_done_after_a_failed_row_retries_only_the_unlogged_ones(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "accepted", "accepted"], REVIEW_FIX_CLAUDE_DIR=str(self.tempRoot / "nowhere"))
        self.assertEqual(self.rows(self.findingsFile), [])
        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(len(self.rows(self.findingsFile)), 2)

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
            code, output = self.run_script(["escape", "--escape", self.escape_spec(file=path)])
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
            self.ghLog.write_text("") if self.ghLog.exists() else None
            code, output = self.packet(text, "--aikido", target, skill="fix")
            self.assertEqual(code, 0, output)
            self.assertTrue(output.startswith("ACTION: stop"), output)
            self.assertEqual(len(self.posts()), 1, output)
            self.assertIn("Not fixed in this pass", self.ghLog.read_text())

    # ---------- walk: every state and every verb ----------

    def test_every_verb_in_every_state_ends_with_an_action_line_and_no_traceback(self):
        states = {"none": None, "asks": WITH_ASK, "plan-impact": PLAN_IMPACT, "render": CONVERGED, "blocker": BLOCKER,
                  "parse-failed": "status: bogus"}
        verbs = {"packet": ["packet", "--skill", "review"], "escape": ["escape", "--escape", self.escape_spec()],
                 "asks-done": ["asks-done", "accepted", "accepted"], "decide": ["decide", "keep"]}
        for stateName, text in states.items():
            for verbName, arguments in verbs.items():
                with self.subTest(state=stateName, verb=verbName):
                    self.setUp_fresh_state(text)
                    code, output = self.run_script(arguments, CONVERGED if verbName == "packet" else "")
                    self.assertNotIn("Traceback", output)
                    self.assertIn(code, (0, 2), output)
                    self.assertIn("ACTION:", output)

    def setUp_fresh_state(self, text):
        stateFile = self.repo / ".git" / "review-fix" / "state.json"
        if stateFile.exists():
            stateFile.unlink()
        if text is not None:
            self.packet(text)

    def test_done_and_redispatch_stages_survive_every_verb(self):
        self.packet(PLAN_IMPACT)
        self.run_script(["decide", "keep", "--by", "user", "--ruling", "keep it"])
        for arguments in (["decide", "keep", "--by", "user", "--ruling", "keep it"], ["asks-done", "accepted"], ["escape", "--escape", self.escape_spec()]):
            code, output = self.run_script(arguments)
            self.assertNotIn("Traceback", output)
            self.assertIn("ACTION:", output)
        code, output = self.packet(PLAN_IMPACT)
        self.assertIn("ACTION: done", output)

    def test_usage_error_without_a_skill_stops_loudly(self):
        code, output = self.run_script(["packet"], CLEAN_EMPTY)
        self.assertEqual(code, 2)
        self.assertIn("stop-usage", output)

    def test_unknown_subcommand_prints_usage_and_fails(self):
        code, output = self.run_script(["nope"])
        self.assertEqual(code, 2)
        self.assertIn("review-fix.py", output)


if __name__ == "__main__":
    unittest.main()
