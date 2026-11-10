import json
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from typing import ClassVar

import fake_ledger
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import handback
import handback_store
import review_loop_script
import reviewed_tree
import script_utils
from review_fix_asks import LAUNCH_COMMAND

LOGGED_MARK = "LOGGED / POSTED"

SCRIPT = pathlib.Path(os.environ.get("REVIEW_FIX_SCRIPT") or toolkit_paths.REVIEW_DIR / "review_fix.py")
HANDBACK = SCRIPT.parent / "handback.py"
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


def packet_text(fields, **changes):
    """The JSON packet of `fields` with `changes` laid over them; a change to None drops that key."""
    merged = {**fields, **changes}
    kept = {key: value for key, value in merged.items() if value is not None}
    return json.dumps(kept)


def ask_entry(finding, file_line, finding_id=None, question="cap?", change="cap at 3", gate="code-reviewer",
              ask_class="smell"):
    entry = {"finding": finding, "finding_id": finding_id, "file_line": file_line, "question": question,
             "change": change, "gate": gate, "class": ask_class}
    return {key: value for key, value in entry.items() if value is not None}


CONVERGED_FIELDS = {
    "status": "converged",
    "iter": 1,
    "fixed": [{"finding": "orders query lacked a tenant filter", "file_line": "src/orders.ts:42", "blocker": True},
              {"finding": "unused import", "file_line": "src/util.ts:3", "blocker": False}],
    "skipped_fp": [{"item": "src/a.ts:9 possible null", "reason": "guarded two lines above"}],
    "blockers": [],
    "findings_remaining": [],
    "plan_impact": "",
    "ask": [],
    "class_closure": "enumerated every query in orders.ts; the tenant filter now sits on all 3",
    "files_touched": ["src/orders.ts", "src/util.ts"],
    "nit": ["rename tmp: skipped: out of scope"],
    "load_bearing_clean": "auth.ts came back clean but is load-bearing",
}
CONVERGED = json.dumps(CONVERGED_FIELDS)

CLEAN_EMPTY_FIELDS = {"status": "converged", "iter": 0, "fixed": [], "skipped_fp": [], "ask": [],
                      "class_closure": "n/a - fixed[] empty", "files_touched": [], "nit": []}
CLEAN_EMPTY = json.dumps(CLEAN_EMPTY_FIELDS)

RETRY_ASK = ask_entry("retry count looks arbitrary", "src/retry.ts:10", finding_id="a1b2c3d4e5f60001",
                      question="Should retries be capped at 3 or configurable?", change="cap retries at 3")
INDEX_ASK = ask_entry("no index", "src/db.ts:5", finding_id="a1b2c3d4e5f60002", question="Add an index on tenant_id?",
                      change="add an index on tenant_id", gate="perf-reviewer", ask_class="perf")
WITH_ASK_FIELDS = {"status": "converged", "iter": 1, "fixed": [], "ask": [RETRY_ASK, INDEX_ASK],
                   "class_closure": "n/a - fixed[] empty"}
WITH_ASK = json.dumps(WITH_ASK_FIELDS)

UNASKABLE_ASK = {"file_line": "a.ts:1", "gate": "code-reviewer", "class": "bug"}
POINTER_ASK = {"text": "see the ask above", "file_line": "a.ts:1", "drop_reason": "ask only points back to another ask"}
DROPPED_ASK_WARNING = ("DROPPED ASKS (tell the user; the review went on without them):\n"
                       "- ask only points back to another ask, so it was dropped: 'see the ask above'")

HELD_IMPACT = {"text": "the queue is at-most-once; AC-2 drops the retry", "gate": "code-reviewer",
               "ac_change": True, "cause": "plan", "adopted": False}
CAP_ASK = {"question": "cap the retry at three?", "file_line": "src/retry.ts:10", "change": "cap the retry",
           "gate": "code-reviewer", "class": "smell"}
ADOPTED_IMPACT = {"text": "the cap moves into the config; acceptance_criteria: none", "gate": "smell-reviewer",
                  "ac_change": False, "cause": "plan", "adopted": True}
TOOLKIT_IMPACT = {"text": "the gate base is old", "gate": "coder", "ac_change": False, "cause": "toolkit",
                  "adopted": False}

PLAN_IMPACT_TEXT = ("PLAN-IMPACT:\n"
                    "  assumed: the queue is at-least-once\n"
                    "  found: the queue is at-most-once\n"
                    "  changes: phase 3 needs a dedupe table")
PLAN_IMPACT_FIELDS = {"status": "converged", "iter": 1, "spec_iter": 2, "fixed": [], "ask": [],
                      "class_closure": "n/a - fixed[] empty",
                      "plan_impacts": [{"text": PLAN_IMPACT_TEXT, "gate": "code-reviewer", "ac_change": True,
                                        "cause": "plan", "adopted": False}]}
PLAN_IMPACT = json.dumps(PLAN_IMPACT_FIELDS)


BLOCKER_FIELDS = {"status": "critical-blocker", "iter": 1,
                  "blockers": ["auth bypass needs a design decision: src/auth.ts:12", "public API field rename"]}
BLOCKER = json.dumps(BLOCKER_FIELDS)

SETUP_FAULT = json.dumps({"status": "setup-fault", "iter": 1,
                          "blockers": ["the full check could not run: no package.json"]})

FIX_REMOVED = json.dumps({"status": "fix-removed-change", "iter": 1,
                          "blockers": ["the fix passes removed 9 of the 10 source lines the change under review adds"]})

CAP_FIELDS = {"status": "cap-reached", "iter": "2 of 2",
              "findings_remaining": [{"disposition": "fix", "finding": "still racy", "file_line": "src/q.ts:7"}]}
CAP = json.dumps(CAP_FIELDS)

CAP_WITH_AN_OPEN_CLASS_FIELDS = {
    "status": "cap-reached",
    "iter": "2 of 2",
    "fixed": [{"finding": "a log with no timestamp compared as equal", "file_line": "src/logs.ts:12"}],
    "findings_remaining": [{"disposition": "fix", "finding": "a log with a trailing blank line compares as different",
                            "file_line": "src/logs.ts:30"}],
    "class_closure": "log shapes the comparison takes - no timestamp closed; trailing blank line still open",
    "open_classes": ["a log with a trailing blank line"],
    "files_touched": ["src/logs.ts"],
}
CAP_WITH_AN_OPEN_CLASS = json.dumps(CAP_WITH_AN_OPEN_CLASS_FIELDS)

DEFERRED = json.dumps({
    "status": "deferred",
    "iter": 1,
    "fixed": [],
    "findings_remaining": [{"disposition": "fix", "finding": "needs the shared helper", "file_line": "src/h.ts:1"}],
    "ask": [],
    "class_closure": "n/a - fixed[] empty",
})


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
            "gh", f'echo "$@" >> {self.gh_log}\ncase "$1 $2" in "repo view") echo acme/web;; '
                  '"pr view") echo 7; exit "${GH_PR_VIEW_EXIT:-${GH_EXIT:-0}}";; esac\n'
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

    def false_clean_reason(self):
        """Why the gate refuses a clean mark for the session, read from this test's hand-back store."""
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store_dir)}):
            return handback.false_clean_reason(SESSION)

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

    def test_converged_packet_renders_counts_in_place_of_the_fixed_nit_and_skipped_lists(self):
        code, output = self.packet(CONVERGED)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)
        self.assertNotIn("review-gate-mark", output)
        self.assertIn("Fixed 2, nits 1, skipped 1", output)
        for listed in ("### Fixed", "### Nits", "### Skipped", "orders query lacked", "guarded two lines above",
                       "rename tmp"):
            self.assertNotIn(listed, output, listed)
        self.assertIn("Class closure: enumerated every query", output)
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
        code, output = self.packet(packet_text(CONVERGED_FIELDS, class_closure="none"))
        self.assertEqual(code, 0, output)
        self.assertIn("receipt is missing", output)

    def test_converged_without_a_class_closure_line_says_the_receipt_is_missing(self):
        code, output = self.packet(packet_text(CONVERGED_FIELDS, class_closure=None))
        self.assertEqual(code, 0, output)
        self.assertIn("Class closure: MISSING", output)
        self.assertIn("receipt is missing", output)

    def test_empty_converged_review_prints_the_nothing_outstanding_line(self):
        code, output = self.packet(CLEAN_EMPTY)
        self.assertEqual(code, 0, output)
        self.assertIn("No issues found that warrant auto-fix. Ready for `/commit`.", output)
        self.assertIn("Fixed 0, nits 0, skipped 0", output)

    def test_deferred_packet_lists_remaining_findings_and_asks_for_no_mark(self):
        code, output = self.packet(DEFERRED)
        self.assertEqual(code, 0, output)
        self.assertIn("### Deferred to branch exit", output)
        self.assertIn("needs the shared helper", output)
        self.assertNotIn("review-gate-mark", output)

    def test_critical_blocker_stops_without_a_mark_line(self):
        code, output = self.packet(BLOCKER)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("auth bypass needs a design decision", output)
        self.assertIn("public API field rename", output)
        self.assertNotIn("review-gate-mark", output)
        self.assertNotIn("render-and-finish", output)

    def test_a_setup_fault_stops_and_says_it_is_not_a_code_failure(self):
        code, output = self.packet(SETUP_FAULT)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("no package.json", output)
        self.assertIn("toolkit or environment fault, not a code failure", output)
        self.assertNotIn("review-gate-mark", output)
        self.assertNotIn("render-and-finish", output)

    def test_a_fix_that_removed_the_change_stops_for_direction(self):
        code, output = self.packet(FIX_REMOVED)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("removed 9 of the 10", output)
        self.assertIn("removed half or more of the change under review", output)
        self.assertIn("Do not re-dispatch", output)
        self.assertNotIn("render-and-finish", output)

    def test_a_plan_impact_status_stops_and_shows_the_plan_impact_text(self):
        packet = json.dumps({"status": "plan-impact", "iter": 1, "plan_impact": "X"})
        code, output = self.packet(packet)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("no longer emits plan-impact", output)
        self.assertIn("X", output)
        self.assertNotIn("render-and-finish", output)

    def test_cap_reached_stops_and_keeps_the_commit_blocked(self):
        code, output = self.packet(CAP)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("still racy", output)
        self.assertIn("stays blocked", output)

    def capped_packet(self, tree="current", dispatched=True, **fields):
        """A cap-reached packet with no blocker whose passed full check covered `tree`, with the dispatch of this
        repo stored for the session (none stored when `dispatched` is False)."""
        if tree == "current":
            tree = reviewed_tree.fingerprint(self.repo)[1]
        if dispatched:
            self.store_dir.mkdir(exist_ok=True)
            dispatch = {"kind": "dispatch", "session_id": SESSION, "ts": time.time(),
                        "repo": str(self.repo.resolve())}
            (self.store_dir / f"{SESSION}.jsonl").write_text(json.dumps(dispatch) + "\n")
        packet = {"status": "cap-reached", "iter": 2, "full_check": "passed", "full_check_tree": tree,
                  "fixed": [{"finding": "retry loop", "file_line": "src/retry.ts:4", "blocker": False}],
                  "files_touched": ["src/retry.ts", "src/queue.ts"],
                  "findings_remaining": [{"disposition": "fix", "finding": "edge case in the retry parser",
                                          "file_line": "src/retry.ts:9", "blocker": False}], **fields}
        return json.dumps(packet)

    def test_a_cap_reached_with_no_blocker_and_a_passed_check_of_the_final_tree_renders_as_deferred(self):
        code, output = self.packet(self.capped_packet())
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)
        self.assertNotIn("ACTION: stop", output)
        self.assertIn("Deferred to branch exit", output)
        self.assertIn("edge case in the retry parser", output)
        self.assertEqual("deferred", self.stored_state()["status"])

    def test_a_capped_packet_with_no_dispatch_on_record_stays_a_stop(self):
        code, output = self.packet(self.capped_packet(dispatched=False))
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertNotIn("render-and-finish", output)

    def test_a_capped_packet_is_fingerprinted_in_the_dispatched_repo_not_in_the_cwd(self):
        other_repo = self.temp_root / "other"
        other_repo.mkdir()
        (other_repo / "other.txt").write_text("other\n")
        for argv in (["init", "-q"], ["add", "other.txt"], ["commit", "-q", "-m", "init"]):
            subprocess.run(["git", *argv], cwd=other_repo, env={**os.environ, **GIT_ENV}, check=True,
                           capture_output=True)

        code, output = self.run_script(["packet", "--skill", "review"], self.capped_packet(), cwd=other_repo)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_a_deferred_from_cap_packet_names_the_files_the_loop_touched_in_the_user_text(self):
        code, output = self.packet(self.capped_packet())
        self.assertEqual(code, 0, output)
        user_text, _, _logged = output.partition(LOGGED_MARK)
        self.assertIn("### Deferred at the review cap", user_text)
        self.assertIn("src/retry.ts, src/queue.ts", user_text)

    def test_a_cap_reached_whose_check_is_older_than_the_last_fix_or_that_holds_a_blocker_stays_a_stop(self):
        blocker = {"disposition": "fix", "finding": "data loss", "file_line": "src/q.ts:1", "blocker": True}
        cases = {"old check": {"tree": "sha256:0"}, "blocker": {"findings_remaining": [blocker]},
                 "check not passed": {"full_check": "failed (exit 1)"}}
        for label, fields in cases.items():
            with self.subTest(label):
                code, output = self.packet(self.capped_packet(**fields))
                self.assertEqual(code, 0, output)
                self.assertIn("ACTION: stop", output)
                self.assertNotIn("render-and-finish", output)

    def write_dirty(self, *paths):
        """Create each path as an untracked file in the test repo, as a fix leaves it."""
        for path in paths:
            target = self.repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("changed\n")

    def dispatch_lines(self, output):
        _, _, dispatch = output.partition("Handoff lines (write exactly these):")
        return dispatch.partition("  tests-run:")[0]

    def test_a_cap_reached_with_an_open_class_and_a_passed_check_of_the_final_tree_keeps_the_scoped_rerun(self):
        self.write_dirty("src/retry.ts", "src/queue.ts")
        code, output = self.packet(self.capped_packet(open_classes=["a log with a trailing blank line"]))
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("files the capped run's fixes touched", output)
        self.assertNotIn("render-and-finish", output)

    def test_a_cap_reached_with_an_open_class_routes_the_next_run_to_the_files_the_fixes_touched_only(self):
        self.write_dirty("src/logs.ts")
        code, output = self.packet(CAP_WITH_AN_OPEN_CLASS)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("files the capped run's fixes touched", output)
        self.assertIn("Handoff lines (write exactly these):", output)
        self.assertIn("    - path: src/logs.ts", output)
        self.assertIn("trailing blank line compares as different", output)
        self.assertIn("launch --repo", output)
        self.assertIn("--iter 0 --file src/logs.ts", output)
        self.assertNotIn("Do not re-dispatch", output)

    def test_the_scoped_rerun_files_come_from_git_not_from_the_packets_files_touched(self):
        self.write_dirty("src/logs.ts", "src/added_by_a_coder_and_unreported.ts")
        (self.repo / "README.md").write_text("edited\n")
        code, output = self.packet(CAP_WITH_AN_OPEN_CLASS)
        self.assertEqual(code, 0, output)
        dispatch = self.dispatch_lines(output)
        self.assertIn("    - path: README.md\n      change: changed in the working tree against HEAD", dispatch)
        self.assertIn("    - path: src/added_by_a_coder_and_unreported.ts\n", dispatch)
        self.assertIn("    - path: src/logs.ts\n      change: touched by the capped run's fixes", dispatch)

    def test_the_scoped_rerun_drops_a_file_the_fixes_touched_that_git_shows_unchanged(self):
        self.write_dirty("src/other.ts")
        code, output = self.packet(CAP_WITH_AN_OPEN_CLASS)
        self.assertEqual(code, 0, output)
        dispatch = self.dispatch_lines(output)
        self.assertNotIn("src/logs.ts", dispatch)
        self.assertIn("    - path: src/other.ts\n", dispatch)

    def test_a_cap_reached_with_an_open_class_and_a_clean_tree_keeps_the_plain_stop(self):
        code, output = self.packet(CAP_WITH_AN_OPEN_CLASS)
        self.assertEqual(code, 0, output)
        self.assertIn("Do not re-dispatch", output)
        self.assertNotIn("Handoff lines", output)

    def test_a_cap_reached_with_every_class_closed_keeps_the_plain_stop(self):
        closed_closure = CAP_WITH_AN_OPEN_CLASS_FIELDS["class_closure"].replace("still open", "closed")
        closed = packet_text(CAP_WITH_AN_OPEN_CLASS_FIELDS, class_closure=closed_closure, open_classes=[])
        code, output = self.packet(closed)
        self.assertEqual(code, 0, output)
        self.assertIn("Do not re-dispatch", output)
        self.assertNotIn("files the capped run's fixes touched", output)

    def test_open_classes_alone_routes_the_scoped_rerun(self):
        self.write_dirty("src/logs.ts")
        closed_closure = CAP_WITH_AN_OPEN_CLASS_FIELDS["class_closure"].replace("still open", "closed")
        code, output = self.packet(packet_text(CAP_WITH_AN_OPEN_CLASS_FIELDS, class_closure=closed_closure))
        self.assertEqual(code, 0, output)
        self.assertIn("files the capped run's fixes touched", output)

    def test_a_cap_reached_with_an_open_class_and_no_files_touched_keeps_the_plain_stop(self):
        no_files = packet_text(CAP_WITH_AN_OPEN_CLASS_FIELDS, files_touched=[])
        code, output = self.packet(no_files)
        self.assertEqual(code, 0, output)
        self.assertIn("Do not re-dispatch", output)
        self.assertNotIn("files the capped run's fixes touched", output)
        self.assertNotIn("Handoff lines", output)

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

    def impacts_packet(self, impacts, **fields):
        message = {"status": "converged", "iter": 2, "fixed": [], "ask": [], "class_closure": "n/a - fixed[] empty",
                   "plan_impacts": impacts, **fields}
        return self.packet(json.dumps(message))

    def test_a_converged_packet_with_only_adopted_plan_impacts_prints_the_deviation_lines_and_holds_no_gate(self):
        code, output = self.impacts_packet([ADOPTED_IMPACT])

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)
        self.assertIn("ACTION: show-plan-impacts", output)
        self.assertLess(output.index("END USER TEXT"), output.index("ACTION: show-plan-impacts"))
        self.assertIn("## Plan Deviations", output)
        self.assertIn("the cap moves into the config", output)
        self.assertNotIn("ask-user-plan-impact", output)
        self.assertNotIn("Gate: do not commit yet", output)

    def test_a_held_plan_impact_is_asked_once_after_the_review_result_and_keeps_the_gate_dirty(self):
        code, output = self.impacts_packet([ADOPTED_IMPACT, HELD_IMPACT])

        self.assertEqual(code, 0, output)
        self.assertEqual(output.count("ACTION: ask-user-plan-impact"), 1)
        self.assertLess(output.index("END USER TEXT"), output.index("ACTION: ask-user-plan-impact"))
        self.assertIn("the queue is at-most-once", output)
        self.assertIn("the cap moves into the config", output)
        self.assertIn("Adopt plan change / Keep plan as written / Discuss", output)
        self.assertIn("Gate: do not commit yet", output)
        self.assertIn("1 plan impact(s) wait for a ruling", output)
        self.assertNotIn("Nothing is outstanding", output)
        self.assertNotIn("ACTION: redispatch", output)

    def test_a_held_plan_impact_whose_edits_are_in_the_tree_says_to_revert_them_when_the_plan_is_kept(self):
        code, output = self.impacts_packet([{**HELD_IMPACT, "applied": True}])

        self.assertEqual(code, 0, output)
        self.assertIn("edits are already in the tree", output)
        self.assertNotIn("stay unapplied", output)

        code, output = self.run_script(["decide", "keep", "--by", "user", "--ruling", "no, keep the retry"])

        self.assertEqual(code, 0, output)
        self.assertIn("revert them", output)
        self.assertNotIn("the held fix is not applied", output)

    def test_a_toolkit_cause_plan_impact_prints_as_a_fault_with_no_question(self):
        code, output = self.impacts_packet([TOOLKIT_IMPACT])

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: show-plan-impacts", output)
        self.assertIn("Toolkit fault, not a plan change", output)
        self.assertIn("the gate base is old", output)
        self.assertNotIn("ask-user-plan-impact", output)

    def test_adopting_a_held_plan_impact_redispatches_once_with_the_plan_impact_resolved(self):
        self.impacts_packet([HELD_IMPACT])

        code, output = self.run_script(["decide", "adopt", "--by", "user", "--ruling", "yes, drop the retry"])

        self.assertEqual(code, 0, output)
        self.assertEqual(output.count("ACTION: redispatch"), 1)
        self.assertIn("plan_impact: RESOLVED - Adopt plan change.", output)
        self.assertIn("iter=2", output)
        self.assertIn("the queue is at-most-once", output)

    def test_keeping_the_plan_as_written_ends_with_no_redispatch_and_lets_the_review_count_as_clean(self):
        message = json.dumps({"status": "converged", "iter": 2, "fixed": [], "ask": [],
                              "class_closure": "n/a - fixed[] empty", "plan_impacts": [HELD_IMPACT]})
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store_dir)}):
            handback_store.record(SESSION, "dispatch")
            handback_store.record(SESSION, "handback", status="converged", message=message)
        self.packet(message)
        held_reason = self.false_clean_reason()

        code, output = self.run_script(["decide", "keep", "--by", "user", "--ruling", "no, keep the retry"])

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertNotIn("ACTION: redispatch", output)
        self.assertNotIn("plan_impact: RESOLVED", output)
        self.assertIn("the commit gate counts the review as clean", output)
        self.assertIn("1 plan impact(s) that await a ruling", held_reason)
        self.assertIsNone(self.false_clean_reason())

    def test_a_plan_impact_deferred_to_phase_end_lets_the_commit_through(self):
        message = json.dumps({"status": "converged", "iter": 2, "fixed": [], "ask": [],
                              "class_closure": "n/a - fixed[] empty", "plan_impacts": [HELD_IMPACT]})
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store_dir)}):
            handback_store.record(SESSION, "dispatch")
            handback_store.record(SESSION, "handback", status="converged", message=message)
        held_reason = self.false_clean_reason()
        bare_handoff = self.temp_root / "bare-handoff.txt"
        bare_handoff.write_text("plan_impact: none\n", encoding="utf-8")
        adopted_handoff = self.temp_root / "adopted-handoff.txt"
        adopted_handoff.write_text("plan_impact: RESOLVED - Adopt.\n", encoding="utf-8")
        deferred_handoff = self.temp_root / "handoff.txt"
        deferred_handoff.write_text("plan_impact: RESOLVED: deferred to phase end by the session, 2026-10-31: "
                                    "drop the retry\n", encoding="utf-8")

        bare_code, bare_output = self.run_script(["defer", str(bare_handoff)])
        bare_reason = self.false_clean_reason()
        adopted_code, adopted_output = self.run_script(["defer", str(adopted_handoff)])
        adopted_reason = self.false_clean_reason()
        code, output = self.run_script(["defer", str(deferred_handoff)])

        self.assertIn("1 plan impact(s) that await a ruling", held_reason)
        self.assertNotEqual(bare_code, 0, bare_output)
        self.assertIn("holds no `plan_impact: RESOLVED", bare_output)
        self.assertIsNotNone(bare_reason)
        self.assertNotEqual(adopted_code, 0, adopted_output)
        self.assertIsNotNone(adopted_reason)
        self.assertEqual(code, 0, output)
        self.assertIn("the commit gate counts the review as clean", output)
        self.assertIsNone(self.false_clean_reason())

    def test_decide_after_a_defer_says_the_gate_is_clear_and_where_the_ruling_goes(self):
        message = json.dumps({"status": "converged", "iter": 2, "fixed": [], "ask": [],
                              "class_closure": "n/a - fixed[] empty", "plan_impacts": [HELD_IMPACT]})
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store_dir)}):
            handback_store.record(SESSION, "dispatch")
            handback_store.record(SESSION, "handback", status="converged", message=message)
        self.packet(json.dumps({"status": "converged", "iter": 2, "fixed": [], "ask": [],
                                "class_closure": "n/a - fixed[] empty"}))
        deferred_handoff = self.temp_root / "handoff.txt"
        deferred_handoff.write_text("plan_impact: RESOLVED: deferred to phase end by the session, 2026-10-31: "
                                    "drop the retry\n", encoding="utf-8")
        defer_code, defer_output = self.run_script(["defer", str(deferred_handoff)])

        code, output = self.run_script(["decide", "keep", "--by", "user", "--ruling", "no, keep the retry"])

        self.assertEqual(defer_code, 0, defer_output)
        self.assertNotEqual(code, 0, output)
        self.assertIn("the commit gate is already clear", output)
        self.assertIn("decision log", output)
        self.assertIn("this session", output)

    def test_a_ruling_that_keeps_the_plan_leaves_the_asks_of_the_same_packet_to_asks_done(self):
        self.impacts_packet([HELD_IMPACT], ask=[CAP_ASK])
        code, output = self.run_script(["decide", "keep", "--by", "user", "--ruling", "no, keep the retry"])
        self.assertEqual(code, 0, output)

        code, output = self.run_script(["asks-done", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertNotIn("no asks are waiting", output)
        outcomes = [row["ask_outcome"] for row in self.ledger_writes() if "ask_outcome" in row]
        self.assertEqual(outcomes, ["accepted"])

    def test_a_ruling_that_adopts_the_plan_change_keeps_the_asks_of_the_same_packet_open(self):
        self.impacts_packet([HELD_IMPACT], ask=[CAP_ASK])
        code, output = self.run_script(["decide", "adopt", "--by", "user", "--ruling", "yes, drop the retry"])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)

        code, output = self.run_script(["asks-done", "accepted"])

        self.assertEqual(code, 0, output)
        self.assertNotIn("no asks are waiting", output)
        outcomes = [row["ask_outcome"] for row in self.ledger_writes() if "ask_outcome" in row]
        self.assertEqual(outcomes, ["accepted"])

    def test_a_plan_impact_never_prints_a_redispatch_or_a_question_before_the_review_result(self):
        for impacts in ([HELD_IMPACT], [ADOPTED_IMPACT], [TOOLKIT_IMPACT]):
            with self.subTest(impacts[0]["text"]):
                code, output = self.impacts_packet(impacts)

                self.assertEqual(code, 0, output)
                self.assertNotIn("ACTION: redispatch", output)
                self.assertLess(output.index("END USER TEXT"), output.rindex("ACTION:"))

    def test_adopting_a_held_impact_carries_the_remaining_findings_and_the_impact_text(self):
        open_finding = {"finding": "parity script compares the wrong column", "file_line": "bin/parity.py:40",
                        "disposition": "fix"}
        self.impacts_packet([HELD_IMPACT], findings_remaining=[open_finding])

        code, output = self.run_script(["decide", "adopt", "--by", "user", "--ruling", "yes, drop the retry"])

        self.assertEqual(code, 0, output)
        carried = output.split("carried-findings:", 1)[1]
        self.assertIn("  - finding: parity script compares the wrong column - bin/parity.py:40", carried)
        self.assertIn("  - plan impact: the queue is at-most-once", carried)

    def test_a_cap_reached_packet_prints_its_adopted_deviation_lines_and_its_held_impact(self):
        code, output = self.impacts_packet([ADOPTED_IMPACT, HELD_IMPACT], status="cap-reached", iter="2 of 2",
                                           findings_remaining=CAP_FIELDS["findings_remaining"])

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("the cap moves into the config", output)
        self.assertIn("ACTION: ask-user-plan-impact", output)
        self.assertIn("the queue is at-most-once", output)
        self.assertIn("Gate: do not commit yet", output)

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
                self.assertNotIn("review-gate-mark", output)
                self.assertEqual(stage_before, self.stored_stage())
                self.assertEqual("# Plan\n", plan_file.read_text())

    def stored_stage(self):
        return json.loads((self.repo / ".git" / "review-fix" / "state.json").read_text())["stage"]

    def test_decide_with_a_missing_or_bad_by_stops_with_the_usage_line_and_leaves_the_state(self):
        plan_file = self.temp_root / "plan.md"
        cases = {
            "no by": (
                ["decide", "adopt", "--ruling", "my call", "--plan", str(plan_file)],
                ["ACTION: stop-usage",
                 'decide <adopt|keep> --by <user|session> --ruling "<the decision in one line>"']),
            "a bad by value": (
                ["decide", "keep", "--by", "maybe", "--ruling", "my call"],
                ["ACTION: stop-usage", "--by <user|session>", "needs --by user or --by session"]),
            "by with no value": (
                ["decide", "keep", "--by", "--ruling", "my call"],
                ["--by <user|session>"]),
        }

        for name, (argv, expected) in cases.items():
            with self.subTest(name):
                self.packet(PLAN_IMPACT)
                stage_before = self.stored_stage()
                plan_file.write_text("# Plan\n")

                code, output = self.run_script(argv)

                self.assertEqual(code, 2)
                for text in expected:
                    self.assertIn(text, output)
                self.assertNotIn("review-gate-mark", output)
                self.assertEqual(stage_before, self.stored_stage())
                self.assertEqual("# Plan\n", plan_file.read_text())

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
        self.assertNotIn("review-gate-mark", output)

    def plant_held_hand_back(self):
        message = json.dumps({"status": "converged", "iter": 2, "fixed": [], "ask": [],
                              "class_closure": "n/a - fixed[] empty", "plan_impacts": [HELD_IMPACT]})
        self.store_dir.mkdir(exist_ok=True)
        dispatch = {"kind": "dispatch", "session_id": SESSION, "ts": time.time(), "repo": str(self.repo.resolve())}
        (self.store_dir / f"{SESSION}.jsonl").write_text(json.dumps(dispatch) + "\n")
        with unittest.mock.patch.dict(os.environ, {"HANDBACK_STORE_DIR": str(self.store_dir)}):
            handback_store.record(SESSION, "handback", status="converged", message=message)

    def test_decide_keep_with_no_state_rules_on_the_held_impact_in_the_hand_back(self):
        self.plant_held_hand_back()
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")

        code, output = self.run_script(["decide", "keep", "--by", "session", "--ruling", "keep the retry",
                                        "--plan", str(plan_file)])

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertNotIn("ACTION: redispatch", output)
        self.assertIsNone(self.false_clean_reason())
        self.assertIn("The ruling: keep the retry", plan_file.read_text())
        self.assertIn("the queue is at-most-once", plan_file.read_text())

    def test_decide_adopt_with_no_state_logs_the_deviation_and_stops_for_the_callers_own_loop(self):
        self.plant_held_hand_back()
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")

        code, output = self.run_script(["decide", "adopt", "--by", "session", "--ruling", "drop the retry",
                                        "--plan", str(plan_file)])

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("/code resume", output)
        self.assertNotIn("ACTION: redispatch", output)
        self.assertIn("The ruling: drop the retry", plan_file.read_text())
        self.assertIsNotNone(self.false_clean_reason())

    def test_decide_with_no_state_and_no_hand_back_keeps_the_no_packet_error(self):
        code, output = self.run_script(["decide", "keep", "--by", "session", "--ruling", "x"])

        self.assertEqual(code, 2, output)
        self.assertIn("no packet was processed", output)

    def test_decide_with_an_unreadable_state_file_raises_its_own_error_and_ignores_the_hand_back(self):
        self.plant_held_hand_back()
        state_file = self.repo / ".git" / "review-fix" / "state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text("not json {")
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")

        code, output = self.run_script(["decide", "keep", "--by", "session", "--ruling", "keep the retry",
                                        "--plan", str(plan_file)])

        self.assertEqual(code, 2, output)
        self.assertIn("is not readable JSON", output)
        self.assertEqual(plan_file.read_text(), "# Plan\n")

    def test_decide_keep_with_no_session_id_records_no_ruling_and_says_the_gate_stays_dirty(self):
        self.plant_held_hand_back()
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")

        code, output = self.run_script(["decide", "keep", "--by", "session", "--ruling", "x"],
                                       CLAUDE_CODE_SESSION_ID="")
        self.assertEqual(code, 2, output)
        self.assertIn("no packet was processed", output)
        self.assertIsNotNone(self.false_clean_reason())

    def test_decide_keep_from_saved_state_with_no_session_id_records_no_ruling(self):
        self.plant_held_hand_back()
        state_file = self.repo / ".git" / "review-fix" / "state.json"
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps({"stage": "plan-impact", "plan_impact": "- the queue is at-most-once",
                                          "plan_impact_held": True, "iter": 2}))

        code, output = self.run_script(["decide", "keep", "--by", "session", "--ruling", "x"],
                                       CLAUDE_CODE_SESSION_ID="")

        self.assertEqual(code, 0, output)
        self.assertIn("still counts the review as dirty", output)
        self.assertIsNotNone(self.false_clean_reason())

    def test_a_repeat_decide_on_an_already_ruled_hand_back_logs_no_second_deviation(self):
        self.plant_held_hand_back()
        plan_file = self.temp_root / "plan.md"
        plan_file.write_text("# Plan\n")
        arguments = ["decide", "keep", "--by", "session", "--ruling", "keep the retry", "--plan", str(plan_file)]

        first_code, first_output = self.run_script(arguments)
        second_code, second_output = self.run_script(arguments)

        self.assertEqual(first_code, 0, first_output)
        self.assertEqual(second_code, 2, second_output)
        self.assertEqual(plan_file.read_text().count("The ruling: keep the retry"), 1)

    # ---------- asks ----------

    def test_asks_done_from_another_repo_names_the_directory_it_looked_in(self):
        other_repo = self.temp_root / "otherrepo"
        other_repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=other_repo, env={**os.environ, **GIT_ENV}, check=True,
                       capture_output=True)
        self.packet(WITH_ASK)

        code, output = self.run_script(["asks-done", "accepted", "rejected"], cwd=other_repo)

        self.assertEqual(code, 2, output)
        resolved_repo = other_repo.resolve()
        self.assertIn(f"no packet was processed in {resolved_repo}/.git/review-fix", output)
        self.assertIn("run this call there", output)

    def test_a_packet_rerun_from_another_repo_does_not_offer_asks_already_logged(self):
        other_repo = self.temp_root / "otherrepo"
        other_repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=other_repo, env={**os.environ, **GIT_ENV}, check=True,
                       capture_output=True)
        self.packet(WITH_ASK)
        self.run_script(["asks-done", "accepted", "rejected"])
        logged_before = len(self.ledger_writes())

        code, output = self.run_script(["packet", "--skill", "review"], WITH_ASK, cwd=other_repo)

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertIn(os.path.realpath(self.repo), output)
        self.assertNotIn("present-asks", output)
        self.assertEqual(len(self.ledger_writes()), logged_before)

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

    STOP_ASKS: ClassVar[list] = [
        ask_entry("retry count", "src/retry.ts:10", finding_id="a1b2c3d4e5f60021", question="cap at 3?"),
        ask_entry("no index", "src/db.ts:5", finding_id="a1b2c3d4e5f60022", question="add an index?",
                  change="add the index", gate="perf-reviewer", ask_class="perf"),
    ]

    def assert_stop_packet_asks_are_printed_and_logged(self, text):
        code, output = self.packet(text)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: stop", output)
        self.assertIn("Do not re-dispatch", output)
        self.assertIn("1. src/retry.ts:10  [code-reviewer/smell]", output)
        self.assertIn("2. src/db.ts:5  [perf-reviewer/perf]", output)
        self.assertIn("Proposed change: add the index", output)
        self.assertIn("asks-done <outcome-1> <outcome-2>", output)
        self.assertNotIn("review-gate-mark", output)

        code, output = self.run_script(["asks-done", "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        rows = self.ledger_writes()
        self.assertEqual([row["ask_outcome"] for row in rows], ["accepted", "rejected"])
        self.assertEqual([row["finding_id"] for row in rows], ["a1b2c3d4e5f60021", "a1b2c3d4e5f60022"])
        self.assertEqual(self.stored_stage(), "done")

    def test_a_cap_reached_packet_with_asks_prints_them_and_asks_done_logs_their_outcomes(self):
        self.assert_stop_packet_asks_are_printed_and_logged(packet_text(CAP_FIELDS, ask=self.STOP_ASKS))

    def test_a_critical_blocker_packet_with_asks_prints_them_and_asks_done_logs_their_outcomes(self):
        self.assert_stop_packet_asks_are_printed_and_logged(packet_text(BLOCKER_FIELDS, ask=self.STOP_ASKS))

    ONE_ASK = packet_text(CLEAN_EMPTY_FIELDS, ask=[ask_entry("first", "one.ts:1", finding_id="a1b2c3d4e5f60031",
                                                             question="first?", change="c")])

    def stored_state(self):
        return json.loads((self.repo / ".git" / "review-fix" / "state.json").read_text())

    def test_a_second_packet_keeps_the_first_packets_unanswered_asks_and_asks_done_names_the_packet(self):
        self.packet(self.ONE_ASK)
        first_id = self.stored_state()["packet_id"]
        code, output = self.packet(WITH_ASK)
        second_id = self.stored_state()["packet_id"]
        self.assertNotEqual(first_id, second_id)
        self.assertIn(f"asks-done --packet {second_id} <outcome-1> <outcome-2>", output)
        code, output = self.packet(WITH_ASK)
        self.assertIn(f"asks-done --packet {second_id} <outcome-1> <outcome-2>", output)
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
        numbered_ask = ask_entry(f"f{number}", f"n{number}.ts:1", finding_id=f"a1b2c3d4e5f6004{number}",
                                 question=f"q{number}?", change="c")
        return packet_text(CLEAN_EMPTY_FIELDS, ask=[numbered_ask])

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
        unlocated_ask = packet_text(WITH_ASK_FIELDS, ask=[{**RETRY_ASK, "file_line": "unlocated"}])
        self.packet(unlocated_ask)
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("Failures", output)
        self.assertEqual([row["ask_outcome"] for row in self.ledger_writes()], ["accepted"])

    def test_a_json_packet_with_n_asks_some_without_file_line_logs_n_outcome_rows(self):
        asks = [{"question": f"question {number}?", "change": "edit", "gate": "code-reviewer", "class": "smell",
                 **({"file_line": f"src/a{number}.ts:1"} if number % 2 == 0 else {})} for number in range(4)]
        message = json.dumps({"status": "converged", "iter": 1, "fixed": [], "ask": asks,
                              "class_closure": "n/a - fixed[] empty"})
        code, output = self.packet(message)
        self.assertEqual(code, 0, output)
        self.assertIn("asks-done <outcome-1> <outcome-2> <outcome-3> <outcome-4>", output)
        code, output = self.run_script(["asks-done", "accepted", "accepted", "rejected", "accepted"])
        self.assertEqual(code, 0, output)
        outcome_rows = [row for row in self.ledger_writes() if "ask_outcome" in row]
        self.assertEqual([row["ask_outcome"] for row in outcome_rows], ["accepted", "accepted", "rejected", "accepted"])

    def test_the_printed_asks_done_call_runs_once_each_outcome_is_filled_in(self):
        code, output = self.packet(packet_text(CAP_FIELDS, ask=self.STOP_ASKS))
        self.assertEqual(code, 0, output)
        printed_line = next(line for line in output.splitlines() if "review_fix.py asks-done" in line)
        printed_call = printed_line.split("review_fix.py asks-done ", 1)[1].split("  (", 1)[0]
        filled_args = [re.sub(r"^<outcome-\d+>$", "accepted", word) for word in printed_call.split()]

        code, output = self.run_script(["asks-done", *filled_args])

        self.assertEqual(code, 0, output)
        self.assertEqual([row["ask_outcome"] for row in self.ledger_writes()], ["accepted", "accepted"])

    def test_asks_done_with_an_unknown_outcome_fails_loudly(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "accepted", "maybe"])
        self.assertEqual(code, 2)
        self.assertIn("accepted|rejected|modified", output)
        self.assertEqual(self.ledger_writes(), [])

    def test_an_accepted_plan_impact_ask_prints_its_change_as_a_deviation_line_with_no_fix_run(self):
        plan_ask = {**RETRY_ASK, "question": "PLAN-IMPACT: the retry cap contradicts the plan?",
                    "change": "move the retry cap into the config"}
        self.packet(packet_text(WITH_ASK_FIELDS, ask=[plan_ask]))
        code, output = self.run_script(["asks-done", "--by", "session", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertIn("## Plan Deviations", output)
        self.assertIn("  move the retry cap into the config", output)
        self.assertIn("Ruled by the session, not the user", output)

    def test_a_rejected_plan_impact_ask_prints_no_deviation_line(self):
        plan_ask = {**RETRY_ASK, "question": "PLAN-IMPACT: the retry cap contradicts the plan?"}
        self.packet(packet_text(WITH_ASK_FIELDS, ask=[plan_ask]))
        code, output = self.run_script(["asks-done", "rejected"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("## Plan Deviations", output)

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

    def test_escape_the_ledger_refuses_is_kept_in_the_local_file(self):
        code, output = self.packet(CONVERGED, "--source", "conversation",
                                   "--escape", self.escape_spec(), skill="fix",
                                   FAKE_LEDGER_WRITE_EXIT="2")
        self.assertEqual(code, 0, output)
        self.assertIn("escape logged for src/orders.ts", output)
        self.assertEqual(self.escape_rows(), [])
        local_rows = [json.loads(line) for line in self.escapes_file.read_text().splitlines()]
        self.assertEqual([row["file"] for row in local_rows], ["src/orders.ts"])

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
        text = packet_text(CONVERGED_FIELDS, ask=[ask_entry("pick a cap", "src/c.ts:4")])
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
        self.assertIn("Fixed 2, nits 1, skipped 1", output)

    def test_an_explicit_pr_number_posts_the_aikido_replies_where_gh_cannot_name_the_pr(self):
        code, output = self.packet(CONVERGED, "--aikido", "src/orders.ts:42=111", "--pr", "12", skill="fix",
                                   GH_PR_VIEW_EXIT="1")
        self.assertEqual(code, 0, output)
        calls = self.gh_log.read_text().splitlines()
        self.assertFalse([call for call in calls if call.startswith("pr view")])
        posts = [call for call in calls if call.startswith("api")]
        self.assertEqual(len(posts), 1)
        self.assertIn("repos/acme/web/pulls/12/comments/111/replies", posts[0])
        self.assertNotIn("NOT posted", output)

    def test_a_pr_number_that_is_not_a_number_fails_loudly(self):
        code, output = self.packet(CONVERGED, "--aikido", "src/orders.ts:42=111", "--pr", "#12", skill="fix")
        self.assertEqual(code, 2)
        self.assertIn("--pr", output)

    def test_aikido_target_without_a_numeric_comment_id_fails_loudly(self):
        code, output = self.packet(CONVERGED, "--aikido", "src/orders.ts:42=abc", skill="fix")
        self.assertEqual(code, 2)
        self.assertIn("numeric comment id", output)

    def test_fix_render_has_no_class_closure_line_unless_the_packet_carries_one(self):
        _code, output = self.packet(packet_text(CONVERGED_FIELDS, class_closure=None), skill="fix")
        self.assertNotIn("Class closure", output)
        self.assertNotIn("receipt", output)

    # ---------- malformed packets: every one stops loudly ----------

    def assert_parse_failure(self, text, expected, skill="review"):
        code, output = self.packet(text, skill=skill)
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-parse-failure", output)
        self.assertIn(expected, output)
        self.assertNotIn("review-gate-mark", output)
        self.assertNotIn("render-and-finish", output)
        self.assertEqual(self.ledger_writes(), [])

    def test_a_malformed_packet_is_a_parse_failure(self):
        fixed_without_a_finding = [{"file_line": "src/orders.ts:42", "blocker": True}, CONVERGED_FIELDS["fixed"][1]]
        cases = {
            "empty stdin": ("", "no review-loop dispatch on record"),
            "prose with no packet": ("I reviewed the diff and it looks fine.", "must be one JSON object"),
            "a free-text packet": ("status: converged\niter: 1\nfixed: []\n", "must be one JSON object"),
            "unknown status": (packet_text(CONVERGED_FIELDS, status="done"), "status is 'done'"),
            "missing iter": (packet_text(CONVERGED_FIELDS, iter=None), "iter is missing"),
            "iter without a number": (packet_text(CONVERGED_FIELDS, iter="two"), "iter is missing"),
            "converged without fixed": (packet_text(CLEAN_EMPTY_FIELDS, fixed=None), "fixed is missing"),
            "fixed entry without a finding": (
                packet_text(CONVERGED_FIELDS, fixed=fixed_without_a_finding), "no finding"),
            "plan impact with an empty block": (
                json.dumps({"status": "plan-impact", "iter": 1, "spec_iter": 0, "plan_impact": ""}),
                "plan_impact is empty"),
            "critical blocker without blockers": (
                json.dumps({"status": "critical-blocker", "iter": 1, "blockers": []}), "blockers is empty"),
            "cap reached without findings remaining": (
                json.dumps({"status": "cap-reached", "iter": 2}), "findings_remaining is missing"),
            "deferred with empty findings remaining": (
                json.dumps({"status": "deferred", "iter": 1, "fixed": [], "findings_remaining": []}),
                "findings_remaining is missing or empty"),
            "spec iter without a number": (
                packet_text(PLAN_IMPACT_FIELDS, spec_iter="many"), "spec_iter has no number"),
            "deferred with asks but no findings remaining": (
                json.dumps({"status": "deferred", "iter": 1, "fixed": [], "skipped_fp": [], "blockers": [],
                            "findings_remaining": [],
                            "ask": [{"finding": "x", "file_line": "a.ts:1", "question": "y?"}]}),
                "findings_remaining"),
            "cap reached with an empty findings remaining": (
                json.dumps({"status": "cap-reached", "iter": 2, "fixed": [], "blockers": [],
                            "findings_remaining": []}),
                "findings_remaining"),
        }

        for name, (text, expected) in cases.items():
            with self.subTest(name):
                self.assert_parse_failure(text, expected)

    def test_ask_entry_without_a_question_or_a_change_is_a_parse_failure(self):
        self.assert_parse_failure(packet_text(WITH_ASK_FIELDS, ask=[RETRY_ASK, UNASKABLE_ASK]), "ask[1]")

    def test_a_pointer_ask_is_dropped_and_the_other_ask_is_presented(self):
        code, output = self.packet(packet_text(WITH_ASK_FIELDS, ask=[RETRY_ASK, POINTER_ASK]))

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: present-asks", output)
        self.assertIn("Should retries be capped at 3 or configurable?", output)
        self.assertIn(DROPPED_ASK_WARNING, output)

    def test_a_pointer_ask_alone_is_dropped_and_the_review_finishes(self):
        code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[POINTER_ASK]))

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)
        self.assertIn(DROPPED_ASK_WARNING, output)

    def test_a_plain_text_ask_is_a_parse_failure(self):
        self.assert_parse_failure(packet_text(CLEAN_EMPTY_FIELDS, ask=["see the thread above"]), "ask")

    # ---------- whitespace and format tolerance ----------

    def test_extra_whitespace_and_a_code_fence_around_the_packet_still_parse(self):
        padded = "\n  ```json\n" + json.dumps(CONVERGED_FIELDS, indent=2) + "\n```\n\n\n"
        code, output = self.packet(padded)
        self.assertEqual(code, 0, output)
        self.assertIn("Fixed 2, nits 1, skipped 1", output)

    def test_a_status_with_trailing_words_extra_spaces_backticks_or_upper_case_parses(self):
        for status in ("   converged   (all clear)", "`CONVERGED`"):
            with self.subTest(status):
                code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, status=status))

                self.assertEqual(code, 0, output)
                self.assertIn("render-and-finish", output)

    # ---------- shapes seen in real review-loop hand-backs ----------

    def test_ask_with_a_finding_but_no_question_uses_the_finding_as_the_question(self):
        contract_ask = {"finding": "Accept it as the contract and update the README?",
                        "file_line": "src/inventory.ts:103-110", "change": "update the README",
                        "gate": "code-reviewer", "class": "docs"}
        code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[contract_ask]))
        self.assertEqual(code, 0, output)
        self.assertIn("Accept it as the contract", output)

    def test_a_file_line_with_trailing_words_and_a_comma_list_of_lines_parse(self):
        carried_ask = ask_entry("parseDateOnly is unresolved", "service.test.ts:1313 area", question="drop it?",
                                change="drop the parseDateOnly test", gate="carried", ask_class="carried")
        spec_gap = {"finding": "spec gap", "file_line": "spec.md:432, :1521-1523", "blocker": False}
        code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, fixed=[spec_gap], ask=[carried_ask]))
        self.assertEqual(code, 0, output)

    # ---------- no-paste: saved hand-back ----------

    def hook(self, event, which, **extra):
        done = subprocess.run(["python3", "-I", str(HANDBACK), "hook", which], cwd=self.temp_root,
                              input=json.dumps(event), text=True, capture_output=True, env=self.environment(**extra))
        return done.returncode, done.stdout + done.stderr

    def dispatch(self, session=SESSION, subagent="review-loop", prompt=""):
        return self.hook({"session_id": session, "tool_name": "Agent",
                          "tool_input": {"subagent_type": subagent, "prompt": prompt}}, "dispatch")

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
        self.assertNotIn("review-gate-mark", output)

    def test_a_hand_back_with_no_reviewer_run_re_dispatches_with_the_round_count_kept(self):
        self.unreviewed_loop("a1", packet_text(CONVERGED_FIELDS, iter=2))
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("Run `launch` once more with the same flags plus `--iter 2`", output)
        self.assertNotIn("review-gate-mark", output)

    def test_a_second_unreviewed_hand_back_in_a_row_says_stop_and_no_re_dispatch(self):
        self.unreviewed_loop("a1", packet_text(CONVERGED_FIELDS, iter=2))
        self.packet("")
        self.unreviewed_loop("a2", packet_text(CONVERGED_FIELDS, iter=2))
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-reviewer", output)
        self.assertIn("2 times in a row", output)
        self.assertIn("Do not re-dispatch again", output)
        self.assertNotIn("Run `launch` once more", output)
        self.assertNotIn("review-gate-mark", output)

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
        self.assertNotIn("review-gate-mark", output)

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
        self.assertIn("Run `launch` once more", output)
        self.assertNotIn("stop-parse-failure", output)
        self.assertNotIn("review-gate-mark", output)
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
        self.assertNotIn("Run `launch` once more", output)
        self.assertNotIn("review-gate-mark", output)
        self.assertEqual(self.saved_stage(), "asks")

    def stop_row(self, session=SESSION, ts=1000.5, ask_rows=None, **old_fields):
        row = {"kind": "stop", "ts": ts, "session_id": session, "agent_id": "a1", **old_fields}
        if ask_rows is not None:
            row["ask_rows"] = ask_rows
        with open(self.store_dir / (session + ".jsonl"), "a", encoding="utf-8") as store:
            store.write(json.dumps(row) + "\n")

    def misses(self):
        path = self.repo / ".git" / "review-fix" / "misses.json"
        return json.loads(path.read_text()) if path.exists() else {}

    def test_an_old_stop_row_with_open_dispatches_and_no_hand_back_is_a_miss_not_a_wait(self):
        self.dispatch()
        self.stop_row(open_dispatches=1)
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-handback", output)
        self.assertNotIn("wait-for-loop", output)
        self.assertIn("Run `launch` once more", output)
        self.assertEqual(self.misses()["review"]["count"], 1)

    def test_a_hand_back_after_a_stop_row_is_read_normally(self):
        self.dispatch()
        self.stop_row()
        self.hand_back()
        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_sessions_in_one_repo_keep_separate_miss_counts(self):
        self.dispatch(OTHER_SESSION)
        _, output = self.packet("", CLAUDE_CODE_SESSION_ID=OTHER_SESSION)
        self.assertIn("Run `launch` once more", output)
        self.dispatch()
        _code, output = self.packet("")
        self.assertIn("Run `launch` once more", output)
        self.assertNotIn("Stop. Do not re-dispatch", output)

    def test_review_and_fix_keep_separate_miss_counts(self):
        self.seed(WITH_ASK)
        self.dispatch()
        self.packet("", skill="review")
        self.dispatch()
        _, output = self.packet("", skill="fix")
        self.assertIn("Run `launch` once more", output)
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

    # ---------- shapes that broke on real hand-backs ----------

    def test_ask_with_an_unknown_class_and_a_gate_phrase_is_logged_as_other_and_the_raw_class_is_not_sent(self):
        ops_ask = ask_entry("x", "a.ts:1, b.ts:2", finding_id="a1b2c3d4e5f60003", question="why?", change="c",
                            gate="code-reviewer / robustness", ask_class="ops")
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[ops_ask]))
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        row = self.ledger_writes()[0]
        self.assertEqual(
            (row["class"], row["gate"], row["path_key"], row["line"]), ("other", "code-reviewer", "a.ts", "1")
        )
        self.assertNotIn("ops", row.values())
        self.assertNotIn("desc", row)

    def test_a_plan_impact_ask_is_presented_but_not_logged(self):
        impact_ask = ask_entry("PLAN-IMPACT: queue is at-most-once", "a.ts:1", question="adopt?", change="adopt it",
                               ask_class="plan-drift")
        real_ask = ask_entry("real ask", "b.ts:2", finding_id="a1b2c3d4e5f60004")
        code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[impact_ask, real_ask]))
        self.assertIn("adopt?", output)
        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertEqual([row["path_key"] for row in self.ledger_writes()], ["b.ts"])

    ASK_WITHOUT_FINDING_ID = packet_text(CLEAN_EMPTY_FIELDS, ask=[ask_entry("x", "a.ts:1")])

    def test_an_ask_the_loop_logged_without_writing_its_id_gets_its_outcome_under_the_logged_id(self):
        self.seed(self.ASK_WITHOUT_FINDING_ID)
        self.stop_row(ask_rows=[{"file": "a.ts", "line": 1, "finding_id": "a1b2c3d4e5f60010"}])
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
        self.stop_row(ask_rows=[{"file": "a.ts", "line": 1, "finding_id": "a1b2c3d4e5f60011"}])
        self.packet("")
        self.run_script(["asks-done", "accepted"])
        self.assertEqual([row["finding_id"] for row in self.ledger_writes()], ["a1b2c3d4e5f60011"])

    def test_a_valid_id_the_loop_wrote_wins_over_a_logged_row_at_the_same_place(self):
        self.seed(self.ask_packet_with_finding_id("a1b2c3d4e5f60012"))
        self.stop_row(ask_rows=[{"file": "a.ts", "line": 1, "finding_id": "a1b2c3d4e5f60013"}])
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
        two_asks_at_one_place = [ask_entry("x", "a.ts:1", change="c"), ask_entry("y", "a.ts:1", change="c")]
        self.seed(packet_text(CLEAN_EMPTY_FIELDS, ask=two_asks_at_one_place))
        self.stop_row(ask_rows=[{"file": "a.ts", "line": 1, "finding_id": "a1b2c3d4e5f60014"}])
        self.packet("")
        self.run_script(["asks-done", "accepted", "rejected"])
        finding_ids = [row["finding_id"] for row in self.ledger_writes() if "ask_outcome" in row]
        self.assertEqual(len(set(finding_ids)), 2)
        self.assertEqual(finding_ids[0], "a1b2c3d4e5f60014")

    def ask_packet_with_finding_id(self, finding_id_text):
        return packet_text(CLEAN_EMPTY_FIELDS, ask=[ask_entry("x", "a.ts:1", finding_id=finding_id_text)])

    def test_an_ask_whose_finding_id_is_a_placeholder_is_logged_by_packet_and_its_outcome_supersedes_that_row(self):
        placeholders = ["none logged", "not logged (no id was printed)", "none", "-", "", "a1b2c3d4e5f6000",
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
        placeholder_id_ask = ask_entry("x", "a.ts:1", finding_id="none logged")
        kept_id_ask = ask_entry("y", "b.ts:2", finding_id="a1b2c3d4e5f60005")
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[placeholder_id_ask, kept_id_ask]))
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
        self.packet(self.ask_packet_with_finding_id(" a1b2c3d4e5f60006 "))
        code, output = self.run_script(["asks-done", "modified:tighten the cap"])
        self.assertEqual(code, 0, output)
        self.assertEqual([row["finding_id"] for row in self.ledger_writes()], ["a1b2c3d4e5f60006"])

    def test_present_asks_prints_no_gate_mark_line(self):
        code, output = self.packet(WITH_ASK)
        self.assertEqual(code, 0, output)
        self.assertIn("asks-done", output)
        self.assertNotIn("review-gate-mark", output)

    def test_present_asks_names_each_proposed_change_and_what_each_outcome_does(self):
        code, output = self.packet(WITH_ASK)
        self.assertEqual(code, 0, output)
        self.assertIn("Proposed change: cap retries at 3", output)
        self.assertIn("Proposed change: add an index on tenant_id", output)
        self.assertIn("accepted: make the proposed change", output)
        self.assertIn("rejected: leave the code as it stands", output)

    def test_present_asks_indents_a_multi_line_asks_later_lines_under_its_number(self):
        jobs_ask = ask_entry("jobs count changed", "plan.md:12", finding_id="a1b2c3d4e5f60031",
                             question="the plan says -j8\nwhich one holds?", change="restore -j8")
        code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[jobs_ask]))
        self.assertEqual(code, 0, output)
        self.assertIn("\n   which one holds?\n", output)

    def test_present_asks_indents_a_multi_line_proposed_changes_later_lines_under_its_number(self):
        jobs_ask = ask_entry("jobs count changed", "plan.md:12", finding_id="a1b2c3d4e5f60031",
                             question="which one holds?", change="restore -j8\nand log the count")
        code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[jobs_ask]))
        self.assertEqual(code, 0, output)
        self.assertIn("\n   Proposed change: restore -j8\n   and log the count\n", output)

    def test_an_either_or_ask_with_no_proposed_change_is_a_parse_failure(self):
        either_or_ask = {key: value for key, value in RETRY_ASK.items() if key != "change"}
        self.assert_parse_failure(packet_text(WITH_ASK_FIELDS, ask=[either_or_ask, INDEX_ASK]),
                                  "ask entry has no change")

    def test_bare_not_applicable_class_closure_with_empty_fixed_prints_one_line(self):
        _code, output = self.packet(packet_text(CLEAN_EMPTY_FIELDS, class_closure="n/a"))
        self.assertEqual(output.count("Class closure"), 1)
        self.assertNotIn("receipt is missing", output)

    def test_findings_remaining_show_on_converged(self):
        left_over = {"disposition": "fix", "finding": "left over", "file_line": "a.ts:1"}
        _code, output = self.packet(packet_text(CONVERGED_FIELDS, findings_remaining=[left_over]))
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

    def test_packet_from_another_repo_stops_when_the_asks_were_logged_in_the_first(self):
        self.packet(WITH_ASK)
        self.run_script(["asks-done", "accepted", "accepted"])
        second = self.temp_root / "second"
        second.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=second, env={**os.environ, **GIT_ENV}, check=True,
                       capture_output=True)
        writes_before = len(self.ledger_writes())

        code, output = self.packet(WITH_ASK, cwd=second)

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertIn(os.path.realpath(self.repo), output)
        self.assertNotIn("present-asks", output)
        self.assertEqual(len(self.ledger_writes()), writes_before)

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
        tenant_fix = {"finding": "tenant filter missing, also see lib/q.ts:9", "file_line": "`./src/orders.ts:42`",
                      "blocker": False}
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, fixed=[tenant_fix]), "--source", "conversation", skill="fix")
        for path in ("src/orders.ts:42", "./lib/q.ts"):
            _code, output = self.run_script(["escape", "--escape", self.escape_spec(file=path)])
            self.assertIn("escape logged", output)
        self.assertEqual(self.escape_ids(), ["src/orders.ts", "lib/q.ts"])

    def test_escape_naming_a_bare_file_is_logged_when_files_touched_holds_its_full_path(self):
        bare_fix = {"finding": "tenant filter missing", "file_line": "orders.ts:42", "blocker": False}
        fields = dict(CLEAN_EMPTY_FIELDS, fixed=[bare_fix], files_touched=["src/lib/orders.ts"])
        self.packet(packet_text(fields), "--source", "conversation", skill="fix")

        _code, output = self.run_script(["escape", "--escape", self.escape_spec(file="orders.ts")])
        _code, again_output = self.run_script(["escape", "--escape", self.escape_spec(file="src/lib/orders.ts")])

        self.assertIn("escape logged", output)
        self.assertIn("already logged", again_output)
        self.assertEqual(self.escape_ids(), ["src/lib/orders.ts"])

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

    def test_a_stray_parse_failure_leaves_a_finished_packet_finished(self):
        self.packet(PLAN_IMPACT)
        self.run_script(["decide", "keep", "--by", "user", "--ruling", "keep it"])
        _code, output = self.packet(PLAN_IMPACT)
        self.assertIn("ACTION: done", output)

        _code, output = self.packet("status: bogus")
        self.assertIn("ACTION: stop-parse-failure", output)

        _code, output = self.packet(PLAN_IMPACT)
        self.assertIn("ACTION: done", output)
        self.assertNotIn("render-and-finish", output)

    def test_usage_error_without_a_skill_stops_loudly(self):
        code, output = self.run_script(["packet"], CLEAN_EMPTY)
        self.assertEqual(code, 2)
        self.assertIn("stop-usage", output)

    def test_unknown_subcommand_prints_usage_and_fails(self):
        code, output = self.run_script(["nope"])
        self.assertEqual(code, 2)
        self.assertIn("review_fix.py", output)

    # ---------- launch ----------

    def loop_stub(self, message=CONVERGED):
        """A stand-in loop script: records its arguments and hands back through the real write_handback_rows, so the
        rows it writes are the ones `packet` reads."""
        stub = self.temp_root / "loop_stub.py"
        stub.write_text(
            "import json, pathlib, sys\n"
            f"sys.path[:0] = [{str(toolkit_paths.REVIEW_DIR)!r}, {str(toolkit_paths.CODE_DIR)!r}, "
            f"{str(toolkit_paths.LIB_DIR)!r}, {str(toolkit_paths.TELEMETRY_DIR)!r}]\n"
            "import review_loop_packet, review_loop_script\n"
            "argv = sys.argv[1:]\n"
            "options = dict(zip(argv[1::2], argv[2::2]))\n"
            "args = review_loop_script.parse_review_loop_arguments(argv)\n"
            "print(json.dumps({'argv': argv, 'repo': argv[0], **options}))\n"
            "loop_folder = pathlib.Path(args.state_dir) / 'loop-script' / args.agent_id\n"
            f"(loop_folder / 'packet.txt').write_text({message!r} + '\\n')\n"
            f"review_loop_packet.write_handback_rows(args, {message!r}, 'converged', [], False)\n")
        return stub

    def launch(self, *flags, message=CONVERGED, **extra):
        (self.repo / "README.md").write_text("hi, edited\n")
        return self.run_script(["launch", *flags], REVIEW_FIX_LOOP_SCRIPT=str(self.loop_stub(message)), **extra)

    def test_a_deferred_plan_impact_credits_the_tree_the_review_covered_and_not_a_later_edit(self):
        self.assert_ruling_credits_the_reviewed_tree(["defer", "HANDOFF"])

    def test_a_kept_plan_impact_credits_the_tree_the_review_covered_and_not_a_later_edit(self):
        self.assert_ruling_credits_the_reviewed_tree(["decide", "keep", "--by", "user", "--ruling", "keep it"])

    def test_a_clean_loop_the_commit_gate_does_not_credit_says_why(self):
        held = json.dumps({**CONVERGED_FIELDS, "plan_impacts": [HELD_IMPACT]})
        home = self.temp_root / "home"
        code, output = self.launch(message=held, HOME=str(home))
        self.assertEqual(code, 0, output)

        code, output = self.packet(held, HOME=str(home))

        self.assertIn("COMMIT CREDIT: the commit gate does not credit this review yet: the review-loop handed back "
                      "1 plan impact(s) that await a ruling.", output)

    def test_a_clean_loop_the_commit_gate_credits_prints_no_refusal(self):
        home = self.temp_root / "home"
        code, output = self.launch(HOME=str(home))
        self.assertEqual(code, 0, output)

        code, output = self.packet(CONVERGED, HOME=str(home))

        self.assertEqual(code, 0, output)
        self.assertNotIn("COMMIT CREDIT", output)

    def test_a_capped_packet_prints_no_commit_credit_line(self):
        home = self.temp_root / "home"
        capped = json.dumps({**CONVERGED_FIELDS, "status": "cap-reached", "iter": "2 of 2",
                             "blockers": [{"finding": "orders query lacked a tenant filter",
                                           "file_line": "src/orders.ts:42"}]})
        code, output = self.launch(message=capped, HOME=str(home))
        self.assertEqual(code, 0, output)

        code, output = self.packet(capped, HOME=str(home))

        self.assertNotIn("COMMIT CREDIT", output)

    def test_a_converged_packet_without_a_session_id_prints_no_commit_credit_line(self):
        home = self.temp_root / "home"
        code, output = self.launch(HOME=str(home))
        self.assertEqual(code, 0, output)

        code, output = self.packet(CONVERGED, HOME=str(home), CLAUDE_CODE_SESSION_ID="")

        self.assertNotIn("COMMIT CREDIT", output)

    def test_a_ruling_on_a_review_that_stays_dirty_says_the_gate_still_counts_it_dirty(self):
        home = self.temp_root / "home"
        capped = json.dumps({**CONVERGED_FIELDS, "status": "cap-reached", "iter": "2 of 2",
                             "blockers": [{"finding": "orders query lacked a tenant filter",
                                           "file_line": "src/orders.ts:42"}],
                             "plan_impacts": [HELD_IMPACT]})
        code, output = self.launch(message=capped, HOME=str(home))
        self.assertEqual(code, 0, output)
        handoff = self.temp_root / "handoff.txt"
        handoff.write_text("plan_impact: RESOLVED: deferred to phase end by the session, 2026-11-01: "
                           "drop the retry\n", encoding="utf-8")

        code, output = self.run_script(["defer", str(handoff)], HOME=str(home))

        self.assertEqual(code, 0, output)
        self.assertIn("still counts the review as dirty", output)
        self.assertNotIn("counts the review as clean", output)

    def assert_ruling_credits_the_reviewed_tree(self, ruling_args):
        home = self.temp_root / "home"
        held = json.dumps({**CONVERGED_FIELDS, "plan_impacts": [HELD_IMPACT]})
        code, output = self.launch(message=held, HOME=str(home))
        self.assertEqual(code, 0, output)
        if ruling_args[0] == "decide":
            code, output = self.packet(held, HOME=str(home))
            self.assertEqual(code, 0, output)
        late = self.repo / "late.py"
        late.write_text("written after the review\n")
        handoff = self.temp_root / "handoff.txt"
        handoff.write_text("plan_impact: RESOLVED: deferred to phase end by the session, 2026-11-01: "
                           "drop the retry\n", encoding="utf-8")

        code, output = self.run_script([str(handoff) if arg == "HANDOFF" else arg for arg in ruling_args],
                                       HOME=str(home))

        self.assertEqual(code, 0, output)
        with unittest.mock.patch.object(pathlib.Path, "home", return_value=home):
            with_late_file = reviewed_tree.is_reviewed(SESSION, self.repo)
            late.unlink()
            reviewed_tree_only = reviewed_tree.is_reviewed(SESSION, self.repo)
        self.assertEqual((with_late_file, reviewed_tree_only), (False, True))

    def crashing_stub(self):
        stub = self.temp_root / "crashing_stub.py"
        stub.write_text("import sys\nsys.exit(1)\n")
        return stub

    def dispatch_rows(self):
        return [row for row in self.rows(self.store_dir / f"{SESSION}.jsonl") if row["kind"] == "dispatch"]

    def test_launch_without_a_session_refuses_and_launches_nothing(self):
        code, output = self.launch(CLAUDE_CODE_SESSION_ID="")
        self.assertEqual(code, 2, output)
        self.assertIn("CLAUDE_CODE_SESSION_ID is not set", output)
        self.assertEqual(list(self.store_dir.glob("*")), [])

    def test_launch_records_the_dispatch_writes_the_prompt_and_packet_reads_the_hand_back(self):
        subfolder = self.repo / "src"
        subfolder.mkdir()
        code, output = self.launch(cwd=subfolder)
        self.assertEqual(code, 0, output)
        lines = output.splitlines()
        loop_root = script_utils.git_path(self.repo, "review-script") / "loop-script"
        log_path = next(loop_root.glob("review-script-*/script.log"))
        self.assertIn(str(log_path), lines[0])
        self.assertIn("exited 0", lines[-1])
        self.assertIn("packet --skill review", lines[-1])

        dispatches = self.dispatch_rows()
        self.assertEqual(len(dispatches), 1)
        self.assertEqual(dispatches[0]["repo"], str(self.repo.resolve()))
        self.assertIs(dispatches[0]["no_review"], False)

        prompt = (log_path.parent / "prompt.txt").read_text()
        self.assertEqual(prompt, "mode: review-first\ncaller: review\nlane: none\n\n"
                         "Review the working tree against HEAD.\n")
        called_with = json.loads(log_path.read_text().splitlines()[0])
        self.assertEqual(called_with["--session"], SESSION)
        self.assertEqual(called_with["--state-dir"], str(loop_root.parent))
        self.assertTrue(called_with["--agent-id"].startswith("review-script-"))
        # The loop script's own parser must accept the argv the launcher builds.
        parsed = review_loop_script.parse_review_loop_arguments(called_with["argv"])
        self.assertEqual(parsed.session, SESSION)
        self.assertEqual(parsed.prompt_file, str(log_path.parent / "prompt.txt"))
        self.assertEqual(parsed.reviewers, review_loop_script.REVIEWERS_MAIN)

        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_launch_with_a_repo_flag_reviews_that_repo_and_keeps_state_in_it(self):
        second = self.temp_root / "second"
        second.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=second, env={**os.environ, **GIT_ENV}, check=True,
                       capture_output=True)
        (second / "notes.md").write_text("new\n")
        code, output = self.launch("--repo", str(second), cwd=self.repo)
        self.assertEqual(code, 0, output)
        loop_root = script_utils.git_path(second, "review-script") / "loop-script"
        log_path = next(loop_root.glob("review-script-*/script.log"))
        self.assertIn(str(log_path), output.splitlines()[0])
        called_with = json.loads(log_path.read_text().splitlines()[0])
        self.assertEqual(called_with["repo"], str(second.resolve()))
        dispatches = self.dispatch_rows()
        self.assertEqual(len(dispatches), 1)
        self.assertEqual(dispatches[0]["repo"], str(second.resolve()))
        self.assertFalse(script_utils.git_path(self.repo, "review-script").exists())

    def test_launch_with_detach_returns_at_once_and_the_fork_wait_names_the_packet_command(self):
        code, output = self.launch("--detach")
        self.assertEqual(code, 0, output)
        loop_dir, _prompt, _packet_args = self.launched_run()
        wait_command = f"python3 ~/.claude/scripts/code/code_wait.py review --loop {loop_dir}"
        self.assertIn(f"Run `{wait_command}` now", output.splitlines()[-1])

        waited = subprocess.run([sys.executable, str(toolkit_paths.CODE_DIR / "code_wait.py"), "review", "--loop",
                                 str(loop_dir)], cwd=self.repo, capture_output=True, text=True, check=False)

        self.assertEqual(waited.returncode, 0, waited.stderr)
        self.assertEqual(waited.stdout.strip(), "The review loop script finished. Run "
                         "`python3 ~/.claude/scripts/review/review_fix.py packet --skill review --lane none "
                         f"--launch {loop_dir / 'launch.json'}` now.")

    def test_the_packet_command_keeps_a_repo_path_with_a_space_as_one_argument(self):
        self.use_repo_with_a_space()
        code, output = self.launch("--detach")
        self.assertEqual(code, 0, output)
        loop_dir, _prompt, _packet_args = self.launched_run()
        self.assertIn(" ", str(loop_dir))

        waited = subprocess.run([sys.executable, str(toolkit_paths.CODE_DIR / "code_wait.py"), "review", "--loop",
                                 str(loop_dir)], cwd=self.repo, capture_output=True, text=True, check=False)

        self.assertEqual(waited.returncode, 0, waited.stderr)
        packet_command = waited.stdout.split("`")[1]
        self.assertEqual(shlex.split(packet_command)[2:],
                         ["packet", "--skill", "review", "--lane", "none", "--launch",
                          str(loop_dir / "launch.json")])

    def use_repo_with_a_space(self):
        self.repo = self.temp_root / "my repo"
        self.repo.mkdir()
        self.git("init", "-q")
        (self.repo / "README.md").write_text("hi\n")
        self.git("add", "README.md")
        self.git("commit", "-q", "-m", "init")

    def test_the_asks_done_launch_line_keeps_a_repo_path_with_a_space_as_one_argument(self):
        self.use_repo_with_a_space()
        home = str(self.temp_root / "home")
        code, output = self.answer_asks_of_a_launched_review(home, "accepted", "rejected")
        self.assertEqual(code, 0, output)
        launch_args = shlex.split(output.splitlines()[-1])[2:]
        self.assertEqual(launch_args[launch_args.index("--repo") + 1], str(self.repo.resolve()))

    def launched_run(self):
        loop_root = script_utils.git_path(self.repo, "review-script") / "loop-script"
        loop_dir = next(loop_root.glob("review-script-*"))
        prompt = (loop_dir / "prompt.txt").read_text()
        packet_args = json.loads((loop_dir / "launch.json").read_text())["packet_args"]
        return loop_dir, prompt, packet_args

    def test_launch_with_fix_writes_the_findings_and_hands_packet_the_fix_skill(self):
        findings = self.temp_root / "findings.md"
        findings.write_text("- README.md:1 the greeting is wrong\n  and too short\n\n- README.md:2 second\n")
        code, output = self.launch("--fix", str(findings), "--no-review")
        self.assertEqual(code, 0, output)
        self.assertIn("packet --skill fix --lane code", output.splitlines()[-1])

        loop_dir, prompt, packet_args = self.launched_run()
        self.assertEqual(packet_args, ["--skill", "fix", "--lane", "code", "--launch", str(loop_dir / "launch.json")])
        findings_json = loop_dir / "findings.json"
        self.assertIn("mode: fix-first\ncaller: fix\nlane: code\n", prompt)
        self.assertIn(f"findings: {findings_json}\nno-review: yes\n", prompt)
        self.assertEqual(json.loads(findings_json.read_text()),
                         ["README.md:1 the greeting is wrong and too short", "README.md:2 second"])
        self.assertIs(self.dispatch_rows()[0]["no_review"], True)

    def test_launch_with_a_findings_line_out_of_form_stops_naming_the_line(self):
        findings = self.temp_root / "findings.md"
        findings.write_text("- README.md:1 the greeting is wrong\nREADME.md:2 no dash\n")
        code, output = self.launch("--fix", str(findings))
        self.assertEqual(code, 2, output)
        self.assertIn(f"{findings}:2", output)
        self.assertFalse(script_utils.git_path(self.repo, "review-script").exists())

    def test_launch_with_no_review_and_no_fix_stops(self):
        code, output = self.launch("--no-review")
        self.assertEqual(code, 2, output)
        self.assertIn("--no-review needs --fix", output)
        self.assertFalse(script_utils.git_path(self.repo, "review-script").exists())

    def test_launch_with_base_file_fast_and_iter_writes_each_header_and_the_branch_exit_packet(self):
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, capture_output=True, text=True,
                              check=True).stdout.strip()
        code, output = self.launch("--base", "HEAD", "--file", "README.md", "--fast", "--iter", "1")
        self.assertEqual(code, 0, output)
        self.assertIn("packet --skill review --scope branch-exit --lane none", output.splitlines()[-1])

        loop_dir, prompt, packet_args = self.launched_run()
        self.assertEqual(packet_args, ["--skill", "review", "--scope", "branch-exit", "--lane", "none", "--launch",
                                       str(loop_dir / "launch.json")])
        self.assertIn(f"base: {base}\nfiles: README.md\nreviewer-model: haiku\niter: 1\n", prompt)
        self.assertIn("Review only these files: README.md.", prompt)
        relaunch_args = json.loads((loop_dir / "launch.json").read_text())["relaunch_args"]
        self.assertEqual(relaunch_args, ["--repo", str(self.repo.resolve()), "--base", "HEAD", "--file", "README.md",
                                         "--fast", "--lane", "none", "--handoff", str(loop_dir / "handoff.txt")])

    def test_launch_with_deep_records_it_in_the_relaunch_args(self):
        code, output = self.launch("--deep")
        self.assertEqual(code, 0, output)
        loop_dir, _prompt, _packet_args = self.launched_run()
        relaunch_args = json.loads((loop_dir / "launch.json").read_text())["relaunch_args"]
        self.assertEqual(relaunch_args, ["--repo", str(self.repo.resolve()), "--deep", "--lane", "none", "--handoff",
                                         str(loop_dir / "handoff.txt")])

    def test_launch_with_two_files_records_each_in_the_relaunch_args_in_order(self):
        (self.repo / "second.txt").write_text("second\n")
        subprocess.run(["git", "add", "second.txt"], cwd=self.repo, check=True)
        code, output = self.launch("--file", "README.md", "--file", "second.txt")
        self.assertEqual(code, 0, output)
        loop_dir, _prompt, _packet_args = self.launched_run()
        relaunch_args = json.loads((loop_dir / "launch.json").read_text())["relaunch_args"]
        self.assertEqual(relaunch_args, ["--repo", str(self.repo.resolve()), "--file", "README.md", "--file",
                                         "second.txt", "--lane", "none", "--handoff",
                                         str(loop_dir / "handoff.txt")])

    def test_packet_with_a_launch_file_that_holds_no_relaunch_args_stops(self):
        bad_files = {
            "missing": None,
            "no key": json.dumps({"packet_args": []}),
            "not a list": json.dumps({"relaunch_args": "--fast"}),
            "not strings": json.dumps({"relaunch_args": ["--fast", 3]}),
        }
        for label, content in bad_files.items():
            with self.subTest(label):
                launch_file = self.temp_root / f"{label.replace(' ', '-')}.json"
                if content is not None:
                    launch_file.write_text(content)
                code, output = self.run_script(["packet", "--skill", "review", "--launch", str(launch_file)],
                                               CLEAN_EMPTY)
                self.assertEqual(code, 2, output)
                self.assertIn(str(launch_file), output)
                self.assertIn("relaunch_args", output)

    def loop_dirs(self):
        """The launched runs' loop dirs, oldest first: their ids sort by time."""
        loop_root = script_utils.git_path(self.repo, "review-script") / "loop-script"
        return sorted(loop_root.glob("review-script-*"))

    def launched_review_with_asks(self, home):
        """Launches a review that hands back WITH_ASK and runs its packet. Returns the packet arguments."""
        handoff = self.temp_root / "handoff.md"
        handoff.write_text("Review the greeting change.\n")
        code, output = self.launch("--file", "README.md", "--handoff", str(handoff), message=WITH_ASK, HOME=home)
        self.assertEqual(code, 0, output)
        packet_command = output.splitlines()[-1].split("`")[1]
        packet_args = shlex.split(packet_command)[2:]
        code, output = self.run_script(packet_args, HOME=home)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: present-asks", output)
        return packet_args

    def answer_asks_of_a_launched_review(self, home, *outcomes, **extra):
        """Launches a review that hands back WITH_ASK, runs its packet, and answers the asks. Returns asks-done's
        (exit code, output)."""
        self.launched_review_with_asks(home)
        return self.run_script(["asks-done", *outcomes], HOME=home, **extra)

    def test_asks_done_retried_after_a_logging_failure_prints_done_and_no_second_fix_run(self):
        home = str(self.temp_root / "home")
        code, output = self.answer_asks_of_a_launched_review(home, "accepted", "rejected", FAKE_LEDGER_WRITE_EXIT="2")
        self.assertIn("ACTION: redispatch", output)
        self.assertIn("Failures", output)
        first_launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(first_launch_lines), 1, output)
        findings_file = script_utils.git_path(self.repo, "review-fix") / "ask-findings.md"
        findings_before = findings_file.read_text()

        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertIn("The first asks-done printed this fix run; run it now unless it already ran.", output)
        self.assertEqual([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)],
                         first_launch_lines)
        self.assertEqual(findings_file.read_text(), findings_before)

    def test_a_repeat_asks_done_after_a_clean_first_call_prints_the_stored_launch_line_again(self):
        home = str(self.temp_root / "home")
        code, output = self.answer_asks_of_a_launched_review(home, "accepted", "rejected")
        first_launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(first_launch_lines), 1, output)

        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertIn("The first asks-done printed this fix run; run it now unless it already ran.", output)
        self.assertEqual([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)],
                         first_launch_lines)

    def test_the_fix_run_lists_each_file_the_first_run_touched_beside_the_files_it_was_scoped_to(self):
        home = str(self.temp_root / "home")
        handoff = self.temp_root / "handoff.md"
        handoff.write_text("Review the greeting change.\n")
        message = packet_text(WITH_ASK_FIELDS, files_touched=["README.md", "src/fixed_by_coder.ts"])
        code, output = self.launch("--file", "README.md", "--handoff", str(handoff), message=message, HOME=home)
        self.assertEqual(code, 0, output)
        packet_args = shlex.split(output.splitlines()[-1].split("`")[1])[2:]
        code, output = self.run_script(packet_args, HOME=home)
        self.assertEqual(code, 0, output)

        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)

        launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        words = shlex.split(launch_lines[0])
        file_flags = [words[index + 1] for index, word in enumerate(words) if word == "--file"]
        self.assertEqual(file_flags, ["README.md", "src/fixed_by_coder.ts"])

    def test_a_packet_run_again_after_a_logging_failure_keeps_the_fix_run_printed_once(self):
        home = str(self.temp_root / "home")
        packet_args = self.launched_review_with_asks(home)
        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home, FAKE_LEDGER_WRITE_EXIT="2")
        self.assertIn("ACTION: redispatch", output)
        first_launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(first_launch_lines), 1, output)

        code, output = self.run_script(packet_args, HOME=home)
        self.assertEqual(code, 0, output)
        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertEqual([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)],
                         first_launch_lines)

    def test_a_packet_run_again_without_launch_keeps_the_launch_record_for_asks_done(self):
        home = str(self.temp_root / "home")
        packet_args = self.launched_review_with_asks(home)
        launch_index = packet_args.index("--launch")
        args_without_launch = packet_args[:launch_index] + packet_args[launch_index + 2:]

        code, output = self.run_script(args_without_launch, HOME=home)
        self.assertEqual(code, 0, output)
        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)
        self.assertEqual(code, 0, output)
        self.assertNotIn("ACTION: launch-fix-run", output)
        self.assertTrue([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)])

    def test_a_different_packet_run_with_no_launch_drops_the_earlier_runs_launch_record(self):
        home = str(self.temp_root / "home")
        self.launched_review_with_asks(home)
        code, output = self.packet(self.ONE_ASK, HOME=home)
        self.assertEqual(code, 0, output)
        self.assertNotIn("relaunch_args", self.stored_state())
        new_id = self.stored_state()["packet_id"]

        code, output = self.run_script(["asks-done", "--packet", new_id, "accepted"], HOME=home)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: launch-fix-run", output)

    def test_a_different_packet_run_with_its_own_launch_uses_that_launches_relaunch_args(self):
        home = str(self.temp_root / "home")
        self.launched_review_with_asks(home)
        code, output = self.launch("--file", "README.md", message=self.ONE_ASK, HOME=home)
        self.assertEqual(code, 0, output)
        second_loop = self.loop_dirs()[-1]
        packet_args = shlex.split(output.splitlines()[-1].split("`")[1])[2:]
        code, output = self.run_script(packet_args, HOME=home)
        self.assertEqual(code, 0, output)
        new_id = self.stored_state()["packet_id"]

        code, output = self.run_script(["asks-done", "--packet", new_id, "accepted"], HOME=home)
        self.assertEqual(code, 0, output)
        launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(launch_lines), 1, output)
        self.assertIn(str(second_loop / "handoff.txt"), launch_lines[0])

    def test_a_plan_impact_ask_accepted_alone_writes_no_findings_and_ends_with_done(self):
        impact_ask = ask_entry("PLAN-IMPACT: queue is at-most-once", "a.ts:1", question="adopt?", change="adopt it",
                               ask_class="plan-drift")
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[impact_ask]))
        code, output = self.run_script(["asks-done", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertFalse((script_utils.git_path(self.repo, "review-fix") / "ask-findings.md").exists())

    def test_a_plan_impact_ask_is_left_out_of_the_findings_beside_an_accepted_ask(self):
        impact_ask = ask_entry("PLAN-IMPACT: queue is at-most-once", "a.ts:1", question="adopt?", change="adopt it",
                               ask_class="plan-drift")
        real_ask = ask_entry("real ask", "b.ts:2", finding_id="a1b2c3d4e5f60004")
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[impact_ask, real_ask]))
        self.run_script(["asks-done", "accepted", "accepted"])
        findings_file = script_utils.git_path(self.repo, "review-fix") / "ask-findings.md"
        self.assertEqual(findings_file.read_text(), "- b.ts:2 cap? Proposed change: cap at 3\n")

    def test_a_long_question_and_a_multi_line_note_reach_the_findings_file_whole_on_one_item(self):
        long_question = "why " * 100 + "end"
        long_ask = ask_entry("long", "b.ts:2", finding_id="a1b2c3d4e5f60004", question=long_question,
                             change="change " * 60 + "done")
        self.packet(packet_text(CLEAN_EMPTY_FIELDS, ask=[long_ask]))
        self.run_script(["asks-done", "modified:first line\n  second line"])
        findings_file = script_utils.git_path(self.repo, "review-fix") / "ask-findings.md"
        findings = findings_file.read_text()
        self.assertEqual(len(findings.splitlines()), 1, findings)
        self.assertIn(long_question.strip(), findings)
        self.assertIn("done The user changed it", findings)
        self.assertTrue(findings.endswith("make this change in its place: first line second line\n"), findings)

    def test_an_accepted_ask_relaunches_the_review_as_a_fix_run_whose_converged_hand_back_earns_commit_credit(self):
        home = str(self.temp_root / "home")
        code, output = self.answer_asks_of_a_launched_review(home, "accepted", "rejected")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        self.assertNotIn("dispatch a coder", output)
        first_loop = self.loop_dirs()[0]
        findings_file = script_utils.git_path(self.repo, "review-fix") / "ask-findings.md"
        self.assertEqual(findings_file.read_text(), "- src/retry.ts:10 Should retries be capped at 3 or configurable? "
                         "Proposed change: cap retries at 3\n")
        launch_line = output.splitlines()[-1]
        self.assertEqual(shlex.split(launch_line)[2:], [
            "launch", "--fix", str(findings_file), "--iter", "1", "--repo", str(self.repo.resolve()), "--file",
            "README.md", "--lane", "none", "--handoff", str(first_loop / "handoff.txt"), "--detach"])

        code, output = self.run_script(shlex.split(launch_line)[2:], HOME=home,
                                       REVIEW_FIX_LOOP_SCRIPT=str(self.loop_stub(CONVERGED)))
        self.assertEqual(code, 0, output)
        fix_loop = self.loop_dirs()[-1]
        waited = subprocess.run([sys.executable, str(toolkit_paths.CODE_DIR / "code_wait.py"), "review", "--loop",
                                 str(fix_loop)], cwd=self.repo, capture_output=True, text=True, check=False)
        self.assertEqual(waited.returncode, 0, waited.stderr)
        prompt = (fix_loop / "prompt.txt").read_text()
        self.assertIn("mode: fix-first\ncaller: fix\nlane: none\n", prompt)
        self.assertIn("files: README.md\n", prompt)
        self.assertIn("iter: 1\n", prompt)
        self.assertIn("Review the greeting change.", prompt)
        self.assertEqual(json.loads((fix_loop / "findings.json").read_text()),
                         ["src/retry.ts:10 Should retries be capped at 3 or configurable? Proposed change: cap "
                          "retries at 3"])

        packet_command = waited.stdout.split("`")[1]
        packet_args = shlex.split(packet_command)[2:]
        code, output = self.run_script(packet_args, HOME=home)
        self.assertEqual(code, 0, output)
        self.assertNotIn("COMMIT CREDIT", output)
        self.assertIn("ACTION: render-and-finish", output)
        self.assertIsNone(self.false_clean_reason())
        with unittest.mock.patch.object(pathlib.Path, "home", return_value=pathlib.Path(home)):
            self.assertTrue(reviewed_tree.is_reviewed(SESSION, self.repo))

    def test_adopting_a_held_plan_impact_of_a_launched_review_prints_a_ready_launch_line_that_reaches_converged(self):
        home = str(self.temp_root / "home")
        handoff = self.temp_root / "handoff.md"
        handoff.write_text("Review the greeting change.\n")
        held = json.dumps({**CONVERGED_FIELDS, "files_touched": ["README.md"], "plan_impacts": [HELD_IMPACT]})
        code, output = self.launch("--base", "HEAD", "--file", "README.md", "--deep", "--handoff", str(handoff),
                                   message=held, HOME=home)
        self.assertEqual(code, 0, output)
        first_loop = self.loop_dirs()[0]
        packet_args = shlex.split(output.splitlines()[-1].split("`")[1])[2:]
        code, output = self.run_script(packet_args, HOME=home)
        self.assertEqual(code, 0, output)

        code, output = self.run_script(["decide", "adopt", "--by", "user", "--ruling", "yes, drop the retry"],
                                       HOME=home)

        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        adopt_handoff = script_utils.git_path(self.repo, "review-fix") / "adopt-handoff.md"
        launch_line = output.splitlines()[-1]
        self.assertEqual(shlex.split(launch_line)[2:], [
            "launch", "--iter", "1", "--repo", str(self.repo.resolve()), "--base", "HEAD", "--file", "README.md",
            "--deep", "--lane", "none", "--handoff", str(adopt_handoff), "--detach"])
        handoff_text = adopt_handoff.read_text()
        self.assertTrue(handoff_text.startswith((first_loop / "handoff.txt").read_text().rstrip() + "\n"),
                        handoff_text)
        self.assertIn("plan_impact: RESOLVED - Adopt plan change. Ruling: yes, drop the retry\niter=1\n",
                      handoff_text)

        code, output = self.run_script(shlex.split(launch_line)[2:], HOME=home,
                                       REVIEW_FIX_LOOP_SCRIPT=str(self.loop_stub(CONVERGED)))
        self.assertEqual(code, 0, output)
        second_loop = self.loop_dirs()[-1]
        waited = subprocess.run([sys.executable, str(toolkit_paths.CODE_DIR / "code_wait.py"), "review", "--loop",
                                 str(second_loop)], cwd=self.repo, capture_output=True, text=True, check=False)
        self.assertEqual(waited.returncode, 0, waited.stderr)
        self.assertIn("plan_impact: RESOLVED - Adopt plan change.", (second_loop / "prompt.txt").read_text())
        packet_args = shlex.split(waited.stdout.split("`")[1])[2:]
        code, output = self.run_script(packet_args, HOME=home)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_a_modified_ask_carries_the_users_change_into_the_findings_file(self):
        home = str(self.temp_root / "home")
        code, output = self.answer_asks_of_a_launched_review(home, "rejected", "modified:index tenant_id and region")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        findings_file = script_utils.git_path(self.repo, "review-fix") / "ask-findings.md"
        self.assertEqual(findings_file.read_text(), "- src/db.ts:5 Add an index on tenant_id? Proposed change: add an "
                         "index on tenant_id The user changed it; make this change in its place: index tenant_id "
                         "and region\n")

    def test_all_rejected_asks_end_the_run_with_no_fix_run(self):
        home = str(self.temp_root / "home")
        code, output = self.answer_asks_of_a_launched_review(home, "rejected", "rejected")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertFalse([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)])
        self.assertFalse((script_utils.git_path(self.repo, "review-fix") / "ask-findings.md").exists())

    def test_a_modified_ask_with_no_note_stops_and_logs_nothing(self):
        self.packet(WITH_ASK)
        writes_before = len(self.ledger_writes())
        code, output = self.run_script(["asks-done", "accepted", "modified"])
        self.assertEqual(code, 2, output)
        self.assertIn("outcome 2 is modified with no note", output)
        self.assertEqual(len(self.ledger_writes()), writes_before)

    def test_an_accepted_ask_of_a_run_launch_did_not_start_prints_a_launch_line_for_the_findings_file(self):
        self.packet(packet_text(WITH_ASK_FIELDS, iter=3))
        code, output = self.run_script(["asks-done", "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        findings_file = script_utils.git_path(self.repo, "review-fix") / "ask-findings.md"
        self.assertIn("ACTION: launch-fix-run", output)
        self.assertIn(str(findings_file), output)
        launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(launch_lines), 1, output)
        launch_words = shlex.split(launch_lines[0])
        self.assertEqual(launch_words[launch_words.index("--fix") + 1], str(findings_file))
        self.assertEqual(launch_words[launch_words.index("--repo") + 1], str(self.repo))
        self.assertEqual(launch_words[launch_words.index("--iter") + 1], "3")
        self.assertIn("--detach", launch_words)
        self.assertTrue(findings_file.read_text().startswith("- src/retry.ts:10 "))

    def test_a_repeat_asks_done_with_no_launch_record_prints_the_same_launch_line(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        first_launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(first_launch_lines), 1, output)

        code, output = self.run_script(["asks-done", "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertEqual([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)],
                         first_launch_lines)

    def test_a_whole_tree_launch_gives_the_fix_run_no_file_flag(self):
        home = str(self.temp_root / "home")
        handoff = self.temp_root / "handoff.md"
        handoff.write_text("Review the greeting change.\n")
        message = packet_text(WITH_ASK_FIELDS, files_touched=["src/fixed_by_coder.ts"])
        code, output = self.launch("--handoff", str(handoff), message=message, HOME=home)
        self.assertEqual(code, 0, output)
        packet_args = shlex.split(output.splitlines()[-1].split("`")[1])[2:]
        code, output = self.run_script(packet_args, HOME=home)
        self.assertEqual(code, 0, output)

        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)

        launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(launch_lines), 1, output)
        self.assertNotIn("--file", shlex.split(launch_lines[0]))

    def test_asks_done_retried_after_a_logging_failure_with_no_launch_record_stops_again(self):
        self.packet(WITH_ASK)
        code, output = self.run_script(["asks-done", "accepted", "rejected"], FAKE_LEDGER_WRITE_EXIT="2")
        self.assertIn("ACTION: launch-fix-run", output)

        first_launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(first_launch_lines), 1, output)

        code, output = self.run_script(["asks-done", "accepted", "rejected"])
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertEqual([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)],
                         first_launch_lines)

    def test_a_repeat_asks_done_after_the_kept_packet_was_answered_last_prints_the_kept_packets_line(self):
        home = str(self.temp_root / "home")
        self.launched_review_with_asks(home)
        older_id = self.stored_state()["packet_id"]
        code, output = self.packet(self.ONE_ASK, HOME=home)
        self.assertEqual(code, 0, output)

        current_id = self.stored_state()["packet_id"]
        code, output = self.run_script(["asks-done", "--packet", current_id, "accepted"], HOME=home)
        self.assertEqual(code, 0, output)
        current_launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        code, output = self.run_script(["asks-done", "--packet", older_id, "accepted", "rejected"], HOME=home)
        self.assertEqual(code, 0, output)
        kept_launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(kept_launch_lines), 1, output)
        self.assertNotEqual(kept_launch_lines, current_launch_lines)

        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)
        self.assertEqual(code, 0, output)
        self.assertEqual([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)],
                         kept_launch_lines)

    def test_the_kept_packet_answered_by_id_keeps_its_launch_record_and_prints_the_fix_run_once(self):
        home = str(self.temp_root / "home")
        self.launched_review_with_asks(home)
        older_id = self.stored_state()["packet_id"]
        code, output = self.packet(self.ONE_ASK, HOME=home)
        self.assertEqual(code, 0, output)
        self.assertEqual([kept["packet_id"] for kept in self.stored_state()["waiting_packets"]], [older_id])

        code, output = self.run_script(["asks-done", "--packet", older_id, "accepted", "rejected"], HOME=home,
                                       FAKE_LEDGER_WRITE_EXIT="2")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        first_launch_lines = [line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)]
        self.assertEqual(len(first_launch_lines), 1, output)

        code, output = self.run_script(["asks-done", "--packet", older_id, "accepted", "rejected"], HOME=home)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: done", output)
        self.assertEqual([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)],
                         first_launch_lines)

    def plan_impact_beside_a_real_ask(self, change):
        impact_ask = ask_entry("PLAN-IMPACT: queue is at-most-once", "a.ts:1", question="adopt?", change=change,
                               ask_class="plan-drift")
        real_ask = ask_entry("real ask", "b.ts:2", finding_id="a1b2c3d4e5f60004")
        return packet_text(CLEAN_EMPTY_FIELDS, ask=[impact_ask, real_ask])

    def test_asks_done_retried_after_a_logging_failure_prints_the_plan_deviation_lines_once(self):
        self.packet(self.plan_impact_beside_a_real_ask("adopt it"))
        code, output = self.run_script(["asks-done", "accepted", "accepted"], FAKE_LEDGER_WRITE_EXIT="2")
        self.assertEqual(code, 0, output)
        self.assertIn("## Plan Deviations", output)
        self.assertIn("Failures", output)

        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("## Plan Deviations", output)
        self.assertNotIn("  adopt it", output)

    def test_a_packet_run_again_after_a_logging_failure_prints_the_plan_deviation_lines_once(self):
        packet_text_with_impact = self.plan_impact_beside_a_real_ask("adopt it")
        self.packet(packet_text_with_impact)
        code, output = self.run_script(["asks-done", "accepted", "accepted"], FAKE_LEDGER_WRITE_EXIT="2")
        self.assertIn("## Plan Deviations", output)

        code, output = self.packet(packet_text_with_impact)
        self.assertEqual(code, 0, output)
        code, output = self.run_script(["asks-done", "accepted", "accepted"])
        self.assertEqual(code, 0, output)
        self.assertNotIn("## Plan Deviations", output)

    def test_a_failed_findings_write_leaves_the_fix_run_unlatched_for_the_retry(self):
        home = str(self.temp_root / "home")
        self.launched_review_with_asks(home)
        findings_file = script_utils.git_path(self.repo, "review-fix") / "ask-findings.md"
        findings_file.mkdir(parents=True)

        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)
        self.assertNotEqual(code, 0, output)
        self.assertIn(str(findings_file), output)
        self.assertNotIn("asks_redispatched", self.stored_state())
        self.assertEqual(self.ledger_writes(), [])

        findings_file.rmdir()
        code, output = self.run_script(["asks-done", "accepted", "rejected"], HOME=home)
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: redispatch", output)
        self.assertTrue([line for line in output.splitlines() if line.startswith(LAUNCH_COMMAND)])

    def test_a_modified_plan_impact_ask_records_the_users_note_as_the_ruling(self):
        self.packet(self.plan_impact_beside_a_real_ask("adopt it"))
        code, output = self.run_script(["asks-done", "modified", "rejected"])
        self.assertEqual(code, 2, output)
        self.assertIn("outcome 1 is modified with no note", output)

        code, output = self.run_script(["asks-done", "modified:keep the queue but add a retry", "rejected"])
        self.assertEqual(code, 0, output)
        self.assertIn("keep the queue but add a retry", output)
        self.assertNotIn("Adopted the proposed plan change.", output)
        self.assertIn("  adopt it", output)

    def test_each_launch_reviews_the_working_tree_and_has_its_own_ids(self):
        loop_root = script_utils.git_path(self.repo, "review-script") / "loop-script"
        for _ in range(2):
            code, output = self.launch()
            self.assertEqual(code, 0, output)
        logs = sorted(loop_root.glob("*/script.log"))
        self.assertEqual(len(logs), 2)
        agent_ids = [json.loads(log.read_text().splitlines()[0])["--agent-id"] for log in logs]
        self.assertNotEqual(agent_ids[0], agent_ids[1])
        prompts = sorted(loop_root.glob("*/prompt.txt"))
        self.assertEqual(len(prompts), 2)

    def test_launch_on_a_clean_tree_stops_naming_the_empty_scope_and_the_base_route(self):
        code, output = self.run_script(["launch"], REVIEW_FIX_LOOP_SCRIPT=str(self.loop_stub()))
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-usage", output)
        self.assertIn("review scope is empty", output)
        self.assertIn("--base <ref>", output)
        self.assertEqual(self.dispatch_rows(), [])
        self.assertFalse(script_utils.git_path(self.repo, "review-script").exists())

    def test_launch_with_a_clean_repo_flag_stops_even_when_the_cwd_is_dirty(self):
        second = self.temp_root / "second"
        second.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=second, env={**os.environ, **GIT_ENV}, check=True,
                       capture_output=True)
        (self.repo / "README.md").write_text("hi, edited\n")
        code, output = self.run_script(["launch", "--repo", str(second)], cwd=self.repo,
                                       REVIEW_FIX_LOOP_SCRIPT=str(self.loop_stub()))
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-usage", output)
        self.assertIn(str(second.resolve()), output)
        self.assertEqual(self.dispatch_rows(), [])

    def test_launch_help_prints_usage_and_launches_nothing(self):
        code, output = self.run_script(["launch", "--help"], REVIEW_FIX_LOOP_SCRIPT=str(self.loop_stub()))
        self.assertEqual(code, 0, output)
        self.assertIn("usage: review_fix.py launch", output)
        self.assertIn("--repo", output)
        self.assertEqual(self.dispatch_rows(), [])

    def test_launch_with_a_loop_that_crashes_exits_0_and_packet_reports_no_hand_back(self):
        (self.repo / "README.md").write_text("hi, edited\n")
        code, output = self.run_script(["launch"], REVIEW_FIX_LOOP_SCRIPT=str(self.crashing_stub()))
        self.assertEqual(code, 0, output)
        self.assertIn("exited 1", output)
        code, output = self.packet("")
        self.assertEqual(code, 2, output)
        self.assertIn("ACTION: stop-no-handback", output)

    def dispatching_stub(self):
        """A stand-in loop script that asks the main session for one reviewer, waits for its report, records the
        report it read, then hands back."""
        stub = self.temp_root / "dispatching_stub.py"
        stub.write_text(
            "import pathlib, sys\n"
            f"sys.path[:0] = [{str(toolkit_paths.REVIEW_DIR)!r}, {str(toolkit_paths.CODE_DIR)!r}, "
            f"{str(toolkit_paths.LIB_DIR)!r}, {str(toolkit_paths.TELEMETRY_DIR)!r}]\n"
            "import review_loop_packet, review_loop_script, reviewer_dispatch\n"
            "args = review_loop_script.parse_review_loop_arguments(sys.argv[1:])\n"
            "out = pathlib.Path(args.state_dir) / 'loop-script' / args.agent_id\n"
            "replies = reviewer_dispatch.request_round(out, 1, [('review1-code-reviewer', 'code-reviewer', "
            "'review it')], timeout=60, poll=0.05)\n"
            "(out / 'read.txt').write_text(args.reviewers + '|' + replies[0][0])\n"
            f"review_loop_packet.write_handback_rows(args, {CONVERGED!r}, 'converged', [], False)\n")
        return stub

    def test_launch_hands_the_reviewers_to_the_main_session_and_wait_reports_the_finish(self):
        (self.repo / "README.md").write_text("hi, edited\n")
        code, output = self.run_script(["launch"], REVIEW_FIX_LOOP_SCRIPT=str(self.dispatching_stub()))
        self.assertEqual(code, 0, output)
        lines = output.splitlines()
        self.assertIn("ACTION: dispatch-reviewer", lines)
        request = next(line for line in lines if line.startswith("- agent code-reviewer; prompt "))
        prompt_file = pathlib.Path(request.split("; prompt ")[1].split("; report ")[0])
        report_file = pathlib.Path(request.split("; report ")[1])
        self.assertEqual(prompt_file.read_text(), "review it")
        loop_dir = report_file.parent.parent
        self.assertIn(f"reviewer_dispatch.py wait {loop_dir}", lines[-1])

        report_file.write_text("## Fix\n\nnone\n")
        waited = subprocess.run(["python3", "-I", str(toolkit_paths.REVIEW_DIR / "reviewer_dispatch.py"), "wait",
                                 str(loop_dir)], capture_output=True, text=True, timeout=60)
        self.assertEqual(waited.returncode, 0, waited.stderr)
        self.assertIn("finished", waited.stdout)
        self.assertIn("packet --skill review", waited.stdout)
        self.assertEqual((loop_dir / "read.txt").read_text(), "main|## Fix\n\nnone\n")

        code, output = self.packet("")
        self.assertEqual(code, 0, output)
        self.assertIn("ACTION: render-and-finish", output)

    def test_launch_with_a_repo_outside_git_stops_with_no_dispatch(self):
        outside = self.temp_root / "plain"
        outside.mkdir()
        code, output = self.launch("--repo", str(outside))
        self.assertEqual(code, 2, output)
        self.assertIn("is not inside a git work tree", output)
        self.assertNotIn("Traceback", output)
        self.assertEqual(self.dispatch_rows(), [])


if __name__ == "__main__":
    unittest.main()
