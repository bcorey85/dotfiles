import glob
import importlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import fake_ledger

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
REAL_CLAUDE = REPO_ROOT / "claude" / ".claude"
REAL_HOME = pathlib.Path.home()
SCRIPT_DIR = pathlib.Path(os.environ.get("VERIFY_BRANCH_SCRIPT_DIR") or REAL_CLAUDE / "scripts" / "review")
PLAN_FORMAT_DIR = os.environ.get("PLAN_FORMAT_DIR")
PREP = SCRIPT_DIR / "verify-prep"
LOG = SCRIPT_DIR / "verify-log"
RESOLVER = pathlib.Path(
    os.environ.get("RESOLVE_TASK_DIR_SCRIPT") or REAL_CLAUDE / "scripts" / "tools" / "resolve-task-dir.sh"
)
FINDER = pathlib.Path(
    os.environ.get("LOG_REVIEW_FINDING_SCRIPT") or REAL_CLAUDE / "skills" / "review" / "log-review-finding"
)
ESCAPER = pathlib.Path(os.environ.get("LOG_ESCAPE_SCRIPT") or REAL_CLAUDE / "scripts" / "telemetry" / "log-escape")
REPO_NAMER = pathlib.Path(os.environ.get("REPO_NAME_SCRIPT") or REAL_CLAUDE / "scripts" / "tools" / "repo-name")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}

# A logger that honors `--check` as its first argument (validate, write nothing), wrapped around a real logger.
# STUB_REFUSE refuses any call (check or write) with an argument containing that text; STUB_FAIL_WRITE fails only
# the real write.
STUB_LOGGER = """#!/usr/bin/env bash
check=0
if [ "$1" = "--check" ]; then check=1; shift; fi
if [ "$check" = 0 ] && [ -n "$STUB_ARGV_LOG" ]; then printf '%s\\0' "$@" >> "$STUB_ARGV_LOG"; fi
for arg in "$@"; do
  if [ -n "$STUB_REFUSE" ] && [[ "$arg" == *"$STUB_REFUSE"* ]]; then echo "refused: $arg" >&2; exit 1; fi
  if [ "$check" = 0 ] && [ -n "$STUB_FAIL_WRITE" ] && [[ "$arg" == *"$STUB_FAIL_WRITE"* ]]; then
    echo "write failed: $arg" >&2; exit 1
  fi
done
if [ "$check" = 1 ]; then exec bash REAL --check "$@"; fi
exec bash REAL "$@"
"""

TICKET = """# LED-9: Thing

## Work

- do it

## Acceptance

- First thing works
- Second thing
  wraps onto a second line
  - nested detail is not its own criterion
- Third thing

---

## Technical Notes

- not a criterion
"""

SPEC = """# Plan

## Contracts

### Success Criteria

#### Manual Verification (human-only, Brandon):

- [ ] Brandon reads the contract

#### Manual Verification:

- [ ] agent can drive this
- [ ] **Manual-verified** (human-only): read the thing
"""

MOVED_PLAN = """# Plan

## Phase Status

- [ ] Phase 1: Local work (risk: low)
- [-] Phase 2: Mac runs (risk: high) — moved to LED-16, per the user 2026-10-20

## Phase 1: Local work

#### Manual Verification (human-only):

- [ ] human-only: kept item

## Phase 2: Mac runs — moved to LED-16

#### Manual Verification (human-only):

- [ ] human-only: Mac item
- [ ] human-only: second Mac item
- [x] human-only: done Mac item

## Plan Deviations

- 2026-10-20: Phase 2 moves to LED-16.
"""

CRITERIA = """# Acceptance Criteria

- **AC1** — First thing works.
- **AC2** — Second thing.
- **AC3** — Third thing.

## Manual only

- **AC3** — needs a real machine.
"""

LEGACY_TICKET = "# RES-2: Queue\n\n## Acceptance\n\n- Queue shows\n- Queue sorts\n"
LEGACY_PLAN = "# Plan\n\n## Queue\n\n#### Manual Verification:\n\n- [ ] human-only: look at it\n"


def load_common():
    for directory in (PLAN_FORMAT_DIR, str(PREP.parent)):
        if directory and directory not in sys.path:
            sys.path.insert(0, directory)
    return importlib.import_module("verify_common")


def subprocess_env(base):
    env = dict(base)
    if PLAN_FORMAT_DIR:
        env["PYTHONPATH"] = PLAN_FORMAT_DIR
    return env


class VerifyBranchBase(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name)
        home_dir = tempfile.TemporaryDirectory()
        self.addCleanup(home_dir.cleanup)
        self.home = pathlib.Path(home_dir.name)
        (self.home / ".claude").mkdir()
        self.repo = self.temp_root / "myrepo"
        self.repo.mkdir()
        self.ledger_env = fake_ledger.install(self.temp_root)
        self.findings = pathlib.Path(self.ledger_env["FAKE_LEDGER_ROWS"])
        self.escapes = self.temp_root / "escapes.jsonl"
        finder_stub = self.stub_logger("finder", FINDER)
        escaper_stub = self.stub_logger("escaper", ESCAPER)
        self.env = subprocess_env({
            **os.environ, **GIT_ENV, **self.ledger_env, "HOME": str(self.home),
            "CLAUDE_TOOLKIT_TELEMETRY": "1",
            "VERIFY_STATE_DIR": str(self.temp_root / "state"), "REVIEW_ESCAPES_FILE": str(self.escapes),
            "RESOLVE_TASK_DIR_SCRIPT": str(RESOLVER), "LOG_REVIEW_FINDING_SCRIPT": str(finder_stub),
            "LOG_ESCAPE_SCRIPT": str(escaper_stub), "REPO_NAME_SCRIPT": str(REPO_NAMER)})
        self.git("init", "-q", "-b", "master")
        self.write("README.md", "hello\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "init")
        self.git("checkout", "-q", "-b", "LED-9-thing")
        self.write("src/a.py", "print(1)\n" * 5)
        self.git("add", ".")
        self.git("commit", "-q", "-m", "work")

    def stub_logger(self, name, real_logger):
        path = self.temp_root / f"stub-{name}"
        path.write_text(STUB_LOGGER.replace("REAL", str(real_logger)))
        return path

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, env=self.env, check=True, capture_output=True,
                              text=True).stdout

    def write(self, rel_path, body):
        path = self.repo / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path

    def task_dir(self, name="LED-9-thing", ticket=TICKET, spec=SPEC, criteria=CRITERIA):
        self.write(f"docs/plans/{name}/00-ticket.md", ticket)
        if spec is not None:
            self.write(f"docs/plans/{name}/spec.md", spec)
        if criteria is not None:
            self.write(f"docs/plans/{name}/acceptance-criteria.md", criteria)

    def commit_all(self, message="more"):
        self.git("add", ".")
        self.git("commit", "-q", "-m", message)

    def prep(self, *args, extra_env=None, cwd=None):
        env = {**self.env, **(extra_env or {})}
        return subprocess.run([str(PREP), *args], cwd=cwd or self.repo, env=env, capture_output=True, text=True)

    def log(self, *args, stdin=None, extra_env=None, cwd=None):
        env = {**self.env, **(extra_env or {})}
        return subprocess.run([str(LOG), *args], cwd=cwd or self.repo, env=env, capture_output=True, text=True,
                              input=stdin)

    def log_review(self, findings="[]", result="PASS", *extra, **kwargs):
        return self.log("review", "--result", result, "--rows", "-", *extra, stdin=findings, **kwargs)

    def escape_rows(self):
        """Every `review_escape` row log-escape sent to `ledger write`, oldest first."""
        return fake_ledger.recorded_rows(self.ledger_env, "review_escape")

    def jsonl(self, path):
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def verifier_rows(self):
        return [row for row in self.jsonl(self.findings) if row.get("gate") == "plan-verifier"]

    def context(self):
        return json.loads(next((self.temp_root / "state").glob("*.json")).read_text())

    def failing_reads_env(self, stderr_line, exit_code):
        """Env with a `ledger` first on PATH whose reads print stderr_line and exit exit_code; writes go through."""
        reads_dir = self.temp_root / f"ledger-reads-exit-{exit_code}-bin"
        reads_dir.mkdir(exist_ok=True)
        reads = reads_dir / "ledger"
        writer = shutil.which("ledger", path=self.ledger_env["PATH"])
        reads.write_text(f"#!/bin/sh\nif [ \"$1\" = yield ]; then echo '{stderr_line}' >&2; exit {exit_code}; fi\n"
                         f"exec '{writer}' \"$@\"\n")
        reads.chmod(0o755)
        return {"PATH": f"{reads_dir}{os.pathsep}{self.env['PATH']}", "LEDGER_READ_BACKOFF_SECONDS": "0"}

    def busy_ledger_env(self):
        """Reads exit 75, as when the ledger cache is behind."""
        return self.failing_reads_env("ledger: cache behind, retry", 75)

    def reviewed_tree(self):
        """A committed plan, one more source file, and a logged branch-wide review of exactly that tree."""
        self.task_dir()
        self.write("src/b.py", "print('b')\n" * 3)
        self.commit_all("plan and b")
        self.assertIn("NOT run", self.prep().stdout)
        logged = self.log_review()
        self.assertEqual(logged.returncode, 0, logged.stderr)
        self.assertIn("REVIEW: ran", self.prep().stdout)


class PrepTest(VerifyBranchBase):
    GATED_SPEC = SPEC + ("\n## Phase 1: Work\n\n#### Automated Verification:\n\n"
                         "- [ ] **Test-verified**: passes - `LEDGER_EDIT_WATCH_PY=/x/edit_watch.py cargo test`\n")

    def verifier_prompt(self, out):
        return out.split("STEP 2: dispatch Agent subagent_type=plan-verifier", 1)[1]

    def test_the_verifier_prompt_carries_the_gate_variables_the_plan_commands_start_with(self):
        self.task_dir(spec=self.GATED_SPEC)

        done = self.prep()

        self.assertEqual(done.returncode, 0, done.stderr)
        prompt = self.verifier_prompt(done.stdout)
        self.assertIn("  gate-env: LEDGER_EDIT_WATCH_PY=/x/edit_watch.py", prompt)
        self.assertIn("Put these variables before every test, check or build command you run.", prompt)
        self.assertEqual(["LEDGER_EDIT_WATCH_PY=/x/edit_watch.py"], self.context()["gateEnv"])

    def test_the_code_review_prompt_carries_the_gate_variables_too(self):
        self.task_dir(spec=self.GATED_SPEC)

        done = self.prep()

        self.assertEqual(done.returncode, 0, done.stderr)
        review_step = done.stdout.split("STEP 1:", 1)[1].split("STEP 2:", 1)[0]
        self.assertIn("subagent_type=code-reviewer", review_step)
        self.assertIn("  gate-env: LEDGER_EDIT_WATCH_PY=/x/edit_watch.py", review_step)
        self.assertIn("Put these variables before every test, check or build command you run.", review_step)

    def test_the_verifier_prompt_has_no_gate_env_line_when_no_plan_command_sets_a_variable(self):
        self.task_dir()

        done = self.prep()

        self.assertNotIn("gate-env:", done.stdout)
        self.assertEqual([], self.context()["gateEnv"])

    def test_task_dir_prints_review_step_then_verifier_payload(self):
        self.task_dir()
        done = self.prep()
        self.assertEqual(done.returncode, 0, done.stderr)
        out = done.stdout
        self.assertIn("ticket ACs: 3", out)
        self.assertIn("acceptance-criteria.md ids: 4 (1 manual-only)", out)
        self.assertNotIn("phases", out)
        self.assertIn("STEP 1: branch-wide code review has NOT run", out)
        self.assertIn("subagent_type=code-reviewer", out)
        self.assertIn("`actioned` is required", out)
        self.assertIn("This is the only review of cross-phase interactions.", out)
        self.assertIn("STEP 2: dispatch Agent subagent_type=plan-verifier", out)
        self.assertIn("scope: branch", out)
        context = self.context()
        self.assertEqual(context["baseRef"], "master")
        self.assertEqual(context["diff"]["diffLoc"], 5)
        self.assertEqual(context["diff"]["files"], 1)
        self.assertTrue(context["plan"].endswith("spec.md"))
        self.assertEqual(context["planRel"], "docs/plans/LED-9-thing/spec.md")
        self.assertEqual(context["excludeRel"], "docs/plans/LED-9-thing")
        self.assertTrue(context["fingerprint"].startswith("sha256:"))
        self.assertEqual(context["escapes"], [])
        self.assertIs(context["logged"], False)
        self.assertNotIn("runId", context)
        self.assertNotIn("head", context)
        self.assertNotIn("mode", context)
        self.assertNotIn("criteriaFile", context["criteria"])

    def test_ticket_criteria_wrapping_nesting_and_stop(self):
        common = load_common()
        found = common.ticket_criteria(TICKET)
        self.assertEqual([c["number"] for c in found], [1, 2, 3])
        self.assertEqual([c["label"] for c in found], ["Ticket #1", "Ticket #2", "Ticket #3"])
        self.assertIn("wraps onto a second line", found[1]["text"])
        self.assertIn("nested detail", found[1]["text"])

    def test_manual_verification_variants(self):
        common = load_common()
        items = common.manual_items(SPEC, "spec.md")
        flags = {item["text"]: item["humanOnly"] for item in items}
        self.assertTrue(flags["Brandon reads the contract"])
        self.assertFalse(flags["agent can drive this"])
        self.assertTrue(flags["**Manual-verified** (human-only): read the thing"])

    def test_unmarked_item_gets_the_same_humanonly_value_from_verify_branch_and_the_plan_reader(self):
        common = load_common()
        plan_format = importlib.import_module("plan_format")
        plan = ("## Queue\n\n#### Manual Verification:\n\n- [ ] open the page\n- [ ] **Agent-verified**: ran it\n"
                "- [ ] Human-only: judge the spacing\n")
        from_reader = [item["humanOnly"] for item in plan_format.manual_verification(plan, "plan.md")]
        from_verify_branch = [item["humanOnly"] for item in common.manual_items(plan, "plan.md")]
        self.assertEqual(from_verify_branch, from_reader)
        self.assertEqual(from_verify_branch, [False, False, True])

    def test_checked_manual_items_are_skipped(self):
        common = load_common()
        plan = "#### Manual Verification:\n\n- [x] human-only: already done\n- [ ] human-only: still open\n"
        self.assertEqual([item["text"] for item in common.manual_items(plan, "plan.md")],
                         ["human-only: still open"])

    def test_the_manual_items_of_a_moved_phase_are_not_missing_and_the_phase_is_named_with_its_ticket(self):
        common = load_common()
        self.assertEqual(
            ["human-only: kept item"], [item["text"] for item in common.manual_items(MOVED_PLAN, "plan.md")]
        )
        self.assertEqual(["Phase 2 moved to LED-16: 2 unchecked Manual Verification item(s) go with it"],
                         common.moved_phase_notes(MOVED_PLAN, "plan.md"))
        self.assertEqual([], common.moved_phase_notes(SPEC, "spec.md"))

    def test_a_moved_line_with_no_ticket_key_fails_instead_of_dropping_or_naming_the_phase(self):
        common = load_common()
        plan_text = MOVED_PLAN.replace("moved to LED-16, per the user", "deferred, per the user")
        for call in (common.manual_items, common.moved_phase_notes):
            with self.subTest(call=call.__name__):
                with self.assertRaises(common.VerifyError) as caught:
                    call(plan_text, "plan.md")
                self.assertTrue(str(caught.exception).startswith("plan.md:6:"), str(caught.exception))
                self.assertIn("moved to <KEY>", str(caught.exception))

    def test_a_moved_line_with_no_plan_deviations_entry_fails_instead_of_dropping_the_phase_items(self):
        common = load_common()
        plan_text = MOVED_PLAN.replace("- 2026-10-20: Phase 2 moves to LED-16.", "- 2026-10-20: Phase 1 changed.")
        for call in (common.manual_items, common.moved_phase_notes):
            with self.subTest(call=call.__name__):
                with self.assertRaises(common.VerifyError) as caught:
                    call(plan_text, "plan.md")
                self.assertTrue(str(caught.exception).startswith("plan.md:6:"), str(caught.exception))
                self.assertIn("Plan Deviations", str(caught.exception))

    def test_manual_verification_line_outside_the_grammar_fails_with_path_and_line(self):
        self.task_dir(spec="# Plan\n\n#### Manual Verification:\n\n| a | b |\n")
        done = self.prep()
        self.assertEqual(done.returncode, 2, done.stdout)
        self.assertIn("spec.md:5:", done.stderr)

    def test_heading_variants_match(self):
        common = load_common()
        for heading in ("## Acceptance criteria", "## Requirements", "## ACCEPTANCE", "### Acceptance"):
            found = common.ticket_criteria(f"# T\n\n{heading}\n\n1. **One** - x\n2. Two\n")
            self.assertEqual(len(found), 2, heading)

    def test_a_heading_that_only_starts_like_a_criteria_heading_fails_with_path_and_line(self):
        common = load_common()
        for heading in ("## Acceptance Stubs", "## Requirements and Constraints"):
            with self.assertRaises(common.VerifyError, msg=heading) as caught:
                common.ticket_criteria(f"# T\n\n{heading}\n\n- a stub\n", "ticket.md")
            self.assertIn("ticket.md:3:", str(caught.exception))

    def test_prose_line_in_the_criteria_section_fails_with_path_and_line(self):
        common = load_common()
        with self.assertRaises(common.VerifyError) as caught:
            common.ticket_criteria("# T\n\n## Acceptance\n\nThese hold:\n\n- one\n", "ticket.md")
        self.assertIn("ticket.md:5:", str(caught.exception))

    def test_blank_and_wordless_lines_in_the_criteria_section_are_not_prose(self):
        common = load_common()
        found = common.ticket_criteria("# T\n\n## Acceptance\n\n***\n\n- one\n")
        self.assertEqual(len(found), 1)

    def test_criteria_file_id_forms(self):
        common = load_common()
        text = ("- **AC20** — plain.\n"
                "- **AC21** (see note) — parenthetical after the bold.\n"
                "## Manual only\n"
                "- **AC14 (macOS half)** — qualifier inside the bold.\n"
                "- **AC2 (work half), AC4** — several ids in one bold.\n")
        entries, manual = common.parse_criteria_file(text)
        self.assertEqual([e["id"] for e in entries], ["AC20", "AC21"])
        self.assertEqual(entries[1]["text"], "parenthetical after the bold.")
        self.assertEqual([m["id"] for m in manual], ["AC14", "AC2", "AC4"])
        self.assertEqual(manual[1]["text"], "several ids in one bold.")

    def test_criteria_file_line_that_names_an_id_but_does_not_parse_fails(self):
        common = load_common()
        with self.assertRaises(common.VerifyError) as caught:
            common.parse_criteria_file("- **AC1** — fine.\n- **AC9** no dash here\n")
        self.assertIn(":2:", str(caught.exception))

    def test_criteria_file_skips_a_bold_id_in_the_middle_of_a_line(self):
        common = load_common()
        text = ("- **AC3** — first.\n"
                "  **Status: OPEN, waiting on LED-5.** Prose that says **AC4's main-skill part is OPEN** and more.\n"
                "- **AC4** — second.\n")
        entries, manual = common.parse_criteria_file(text)
        self.assertEqual([e["id"] for e in entries], ["AC3", "AC4"])
        self.assertEqual(manual, [])

    def test_criteria_file_fails_on_a_miswritten_criterion_line_whatever_the_line_start(self):
        common = load_common()
        malformed = [
            "**AC5** text with no dash",
            "- **AC5**: colon in place of a dash",
            "  - **AC5** no dash, indented",
            "1. **AC5** numbered, but the grammar takes only - or * markers",
            "* [ ] **AC5** checkbox, unsupported",
            "| **AC5** | text |",
            "Criterion **AC5** — text",
            "> **AC5** — text",
            "- *(new)* **AC5** — text",
            "- ~~**AC5**~~ — x",
            "-**AC5** — x",
        ]
        for line in malformed:
            with self.subTest(line=line):
                with self.assertRaises(common.VerifyError) as caught:
                    common.parse_criteria_file(f"- **AC1** — fine.\n{line}\n")
                self.assertIn(":2:", str(caught.exception))

    def test_criteria_file_parses_indented_and_starred_criterion_lines(self):
        common = load_common()
        entries, _ = common.parse_criteria_file("  - **AC1** — indented.\n* **AC2** — starred.\n")
        self.assertEqual([(e["id"], e["text"]) for e in entries], [("AC1", "indented."), ("AC2", "starred.")])

    def test_zero_criteria_fails_loudly(self):
        for ticket in ("# T\n\n## Work\n\n- a\n", "# T\n\n## Acceptance\n\n---\n- late bullet\n"):
            self.task_dir(ticket=ticket, criteria=None)
            done = self.prep()
            self.assertEqual(done.returncode, 2, done.stdout)
            self.assertIn("zero criteria", done.stderr)

    def test_unknown_option_and_second_positional_exit_2(self):
        self.task_dir()
        unknown = self.prep("--bogus")
        self.assertEqual(unknown.returncode, 2)
        self.assertIn("unknown option", unknown.stderr)
        second = self.prep("LED-9", "LED-10")
        self.assertEqual(second.returncode, 2)
        self.assertIn("second argument", second.stderr)

    def test_review_signal_fresh_then_stale_after_a_real_edit(self):
        self.reviewed_tree()
        row = self.jsonl(self.findings)[0]
        self.assertEqual((row["gate"], row["scope"], row["_type"]), ("code-reviewer", "branch-exit", "review_run"))
        self.assertEqual((row["source"], row["lane"]), ("verify-branch", "verify"))
        self.assertTrue(row["tree"].startswith("sha256:"))
        self.assertGreaterEqual(int(row["diff_loc"]), 5)
        self.assertEqual(row["branch_key"], "LED-9-thing")
        self.assertNotIn("repo", row)

        self.write("src/a.py", "print(2)\n")
        stale = self.prep().stdout
        self.assertIn("NOT run", stale)
        self.assertIn("tree differs", stale)

    def test_editing_the_task_dir_does_not_stale_the_review(self):
        self.reviewed_tree()
        self.write("docs/plans/LED-9-thing/spec.md", SPEC + "\n- [x] ticked off later\n")
        self.write("docs/plans/LED-9-thing/notes.md", "scratch\n")
        self.assertIn("REVIEW: ran", self.prep().stdout)

    def test_flat_plan_file_edit_does_not_stale_the_review(self):
        self.write("docs/plans/LED-9-flat.md", TICKET + "\n" + SPEC)
        self.assertIn("NOT run", self.prep("LED-9").stdout)
        self.assertEqual(self.log_review().returncode, 0)
        self.write("docs/plans/LED-9-flat.md", TICKET + "\n" + SPEC + "\n- [x] ticked\n")
        self.assertIn("REVIEW: ran", self.prep("LED-9").stdout)

    def test_mtime_alone_does_not_make_the_review_stale(self):
        self.reviewed_tree()
        future = time.time() + 600
        os.utime(self.repo / "src" / "a.py", (future, future))
        self.assertIn("REVIEW: ran", self.prep().stdout)

    def test_review_stale_after_a_file_is_deleted_and_committed(self):
        self.reviewed_tree()
        self.git("rm", "-q", "src/b.py")
        self.git("commit", "-q", "-m", "drop b")
        self.assertIn("NOT run", self.prep().stdout)

    def test_review_stale_after_a_rename_keeping_the_mtime(self):
        self.reviewed_tree()
        self.git("mv", "src/b.py", "src/c.py")
        self.git("commit", "-q", "-m", "rename b")
        self.assertIn("NOT run", self.prep().stdout)

    def test_review_stale_after_an_untracked_file_appears_or_changes(self):
        self.reviewed_tree()
        self.write("notes.txt", "one\n")
        self.assertIn("NOT run", self.prep().stdout)
        self.assertEqual(self.log_review().returncode, 0)
        self.assertIn("REVIEW: ran", self.prep().stdout)
        self.write("notes.txt", "two\n")
        self.assertIn("NOT run", self.prep().stdout)

    def test_review_stale_after_a_file_in_an_untracked_directory_changes(self):
        self.reviewed_tree()
        self.write("newdir/deep/x.txt", "one\n")
        self.assertEqual(self.prep().returncode, 0)
        self.assertEqual(self.log_review().returncode, 0)
        self.assertIn("REVIEW: ran", self.prep().stdout)
        self.write("newdir/deep/x.txt", "two\n")
        self.assertIn("NOT run", self.prep().stdout)

    def test_untracked_file_names_with_spaces_are_hashed(self):
        self.reviewed_tree()
        self.write("my notes.txt", "one\n")
        self.write("other file.txt", "x\n")
        self.assertEqual(self.log_review().returncode, 0)
        self.assertIn("REVIEW: ran", self.prep().stdout)
        self.write("my notes.txt", "two\n")
        self.assertIn("NOT run", self.prep().stdout)

    def test_a_busy_ledger_reads_the_review_this_checkout_logged_and_the_verifier_prompt_names_the_skip(self):
        self.reviewed_tree()

        done = self.prep(extra_env=self.busy_ledger_env())

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("REVIEW: ran", done.stdout)
        self.assertIn("ledger: cache behind", done.stdout)
        self.assertIn("subagent_type=plan-verifier", done.stdout)
        self.assertIn("review state: not read from the ledger", done.stdout)
        self.assertIs(self.context()["review"]["read"], False)

    def test_a_busy_ledger_with_no_review_logged_here_still_asks_for_the_review(self):
        self.task_dir()

        done = self.prep(extra_env=self.busy_ledger_env())

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("NOT run", done.stdout)
        self.assertIn("ledger: cache behind", done.stdout)

    def test_a_review_logged_while_the_ledger_is_busy_counts_on_the_next_prep(self):
        self.task_dir()
        busy_env = self.busy_ledger_env()
        self.assertEqual(self.prep(extra_env=busy_env).returncode, 0)

        logged = self.log_review(extra_env=busy_env)
        second = self.log_review(extra_env=busy_env)

        self.assertEqual(logged.returncode, 0, logged.stderr)
        self.assertEqual(second.returncode, 2)
        self.assertIn("already covers", second.stderr)
        self.assertIn("REVIEW: ran", self.prep(extra_env=busy_env).stdout)

    def test_a_failing_ledger_read_never_blocks_the_run(self):
        self.task_dir()
        failing_env = self.failing_reads_env("ledger yield: broken schema", 1)
        first_prep = self.prep(extra_env=failing_env)

        logged = self.log_review(extra_env=failing_env)
        second_prep = self.prep(extra_env=failing_env)

        self.assertEqual(first_prep.returncode, 0, first_prep.stderr)
        self.assertIn("NOT run", first_prep.stdout)
        self.assertEqual(logged.returncode, 0, logged.stderr)
        self.assertEqual(second_prep.returncode, 0, second_prep.stderr)
        self.assertIn("REVIEW: ran", second_prep.stdout)
        self.assertIn("ledger yield: broken schema", second_prep.stdout)
        self.assertIn("review state: not read from the ledger", second_prep.stdout)

    def test_review_row_for_old_head_with_no_content_change_still_counts(self):
        self.reviewed_tree()
        self.git("commit", "-q", "--allow-empty", "-m", "empty")
        self.assertIn("REVIEW: ran", self.prep().stdout)

    def test_review_loop_and_unmarked_rows_do_not_count_as_the_branch_review(self):
        self.reviewed_tree()
        self.findings.write_text("")
        head = self.git("rev-parse", "HEAD").strip()
        loop_rows = [
            {"_type": "review_run", "gate": "code-reviewer", "scope": "branch-exit", "iter": "2", "diff_loc": "0",
             "n_findings": "0", "result": "PASS", "branch_key": "LED-9-thing", "head": head},
            {"_type": "review_run", "gate": "code-reviewer", "scope": "branch-exit", "iter": "1", "diff_loc": "9",
             "n_findings": "2", "result": "NEEDS_CHANGES", "branch_key": "LED-9-thing", "head": head},
            {"_type": "review_run", "gate": "smell-reviewer", "scope": "branch-exit", "iter": "1", "diff_loc": "9",
             "n_findings": "0", "branch_key": "LED-9-thing", "head": head},
        ]
        self.findings.write_text("\n".join(json.dumps(row) for row in loop_rows) + "\n")
        self.assertIn("NOT run", self.prep().stdout)

    def test_review_row_of_another_branch_does_not_count(self):
        self.reviewed_tree()
        self.git("checkout", "-q", "-b", "LED-9-other")
        self.assertIn("NOT run", self.prep().stdout)

    def test_untracked_files_reach_both_prompts(self):
        self.task_dir()
        out = self.prep().stdout
        self.assertEqual(out.count("untracked files, not in any git diff"), 3)

    def test_renamed_file_hotspot_uses_the_new_path(self):
        self.git("mv", "README.md", "docs.md")
        self.write("docs.md", "hello\nworld\n")
        self.task_dir()
        self.commit_all("rename readme")
        self.assertEqual(self.prep().returncode, 0)
        hotspots = self.context()["diff"]["hotspots"]
        self.assertIn("docs.md", hotspots)
        self.assertFalse([name for name in hotspots if "=>" in name], hotspots)

    def test_detached_head_fails(self):
        self.task_dir()
        self.git("checkout", "-q", "--detach")
        done = self.prep()
        self.assertEqual(done.returncode, 2)
        self.assertIn("detached HEAD", done.stderr)

    def test_empty_diff_fails(self):
        self.task_dir()
        self.git("checkout", "-q", "-b", "LED-9-empty", "master")
        done = self.prep()
        self.assertEqual(done.returncode, 2)
        self.assertIn("is empty: nothing to verify", done.stderr)

    def test_outside_a_git_repository_fails(self):
        done = self.prep(cwd=self.temp_root)
        self.assertEqual(done.returncode, 2)
        self.assertIn("not inside a git repository", done.stderr)

    def test_legacy_eng_specs_layout_with_prefixed_file_names(self):
        self.git("checkout", "-q", "-b", "RES-2-queue")
        self.write("docs/eng-specs/RES-2-queue-tui/RES-2-00-ticket.md", LEGACY_TICKET)
        self.write("docs/eng-specs/RES-2-queue-tui/RES-2-05-plan.md", LEGACY_PLAN)
        done = self.prep()
        self.assertEqual(done.returncode, 0, done.stderr)
        context = self.context()
        self.assertTrue(context["ticket"].endswith("RES-2-00-ticket.md"))
        self.assertTrue(context["plan"].endswith("RES-2-05-plan.md"))
        self.assertIn("ticket ACs: 2", done.stdout)

    def test_ambiguous_task_dirs_exit_3(self):
        self.task_dir("LED-9-a")
        self.task_dir("LED-9-b")
        done = self.prep("LED-9")
        self.assertEqual(done.returncode, 3)
        self.assertIn("LED-9-a", done.stderr)

    def test_no_plan_exit_4_then_ticket_file_runs_plan_none(self):
        self.git("checkout", "-q", "-b", "NOPE-1-x")
        done = self.prep()
        self.assertEqual(done.returncode, 4)
        self.assertIn("--ticket-file", done.stderr)
        ticket = self.temp_root / "NOPE-1-ticket.md"
        ticket.write_text(TICKET)
        done = self.prep("--ticket-file", str(ticket))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("plan: none", done.stdout)
        self.assertIsNone(self.context()["excludeRel"])

    def test_legacy_flat_plan_exit_5_is_ticket_and_plan(self):
        self.write("docs/plans/LED-9-flat.md", TICKET + "\n" + SPEC)
        done = self.prep("LED-9")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("legacy flat plan", done.stdout)
        context = self.context()
        self.assertEqual(context["ticket"], context["plan"])
        self.assertEqual(context["excludeRel"], "docs/plans/LED-9-flat.md")

    def test_the_verifier_payload_lists_each_ticket_label_with_its_text_in_prep_order(self):
        self.task_dir(ticket=REQUIREMENTS_TICKET)

        done = self.prep()

        self.assertEqual(done.returncode, 0, done.stderr)
        payload = done.stdout.split("subagent_type=plan-verifier", 1)[1]
        self.assertIn("  Ticket #1: Requirement alpha\n  Ticket #2: Requirement beta\n", payload)
        self.assertNotIn("Criterion gamma", payload)

    def test_the_flat_mode_verifier_payload_lists_the_ticket_labels_too(self):
        self.write("docs/plans/LED-9-flat.md", REQUIREMENTS_TICKET + "\n" + SPEC)

        done = self.prep("LED-9")

        self.assertEqual(done.returncode, 0, done.stderr)
        payload = done.stdout.split("subagent_type=plan-verifier", 1)[1]
        self.assertIn("  Ticket #1: Requirement alpha\n  Ticket #2: Requirement beta\n", payload)

    def test_task_dir_without_spec_is_ticket_only(self):
        self.task_dir(spec=None, criteria=None)
        done = self.prep()
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("plan: none", done.stdout)

    def test_missing_base_fails(self):
        self.task_dir()
        done = self.prep("--base", "nonexistent-ref")
        self.assertEqual(done.returncode, 2)
        self.assertIn("pass --base", done.stderr)

    def test_runs_from_a_subdirectory_with_paths_relative_to_it(self):
        self.task_dir()
        subdir = self.repo / "src"
        done = self.prep("../docs/plans/LED-9-thing", cwd=subdir)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("ticket ACs: 3", done.stdout)
        self.assertEqual(self.context()["diff"]["diffLoc"], 5)
        bare = self.prep(cwd=subdir)
        self.assertEqual(bare.returncode, 0, bare.stderr)

    def test_ticket_file_path_is_relative_to_the_original_directory(self):
        self.git("checkout", "-q", "-b", "NOPE-1-x")
        subdir = self.repo / "src"
        (subdir / "ticket.md").write_text(TICKET)
        done = self.prep("--ticket-file", "ticket.md", cwd=subdir)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("plan: none", done.stdout)


def ticket_rows(rows):
    """A `done` row for each of the TICKET fixture's three criteria (`Ticket #1`..`Ticket #3`) the rows do not name."""
    named = " ".join(row["item"] for row in rows)
    return [{"item": f"Ticket #{n}: criterion {n}", "verdict": "done", "file": f"src/t{n}.py", "line": 1,
             "evidence": "e"} for n in (1, 2, 3) if f"Ticket #{n}" not in named]


REQUIREMENTS_TICKET = """# LED-9: Thing

## Requirements

- Requirement alpha
- Requirement beta

## Acceptance Criteria

- Criterion gamma
"""


class TicketOnlyLogTest(VerifyBranchBase):
    """A task dir with no criteria file still owes a verdict row for every ticket criterion."""

    def setUp(self):
        super().setUp()
        self.task_dir(spec=None, criteria=None)
        self.assertEqual(self.prep().returncode, 0)
        self.assertEqual(self.log_review().returncode, 0)
        self.assertEqual(self.prep().returncode, 0)

    def test_rows_that_skip_a_ticket_criterion_exit_2_and_write_nothing(self):
        rows = json.dumps([{"item": "Ticket #1: First thing works", "verdict": "done"}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 2)
        self.assertIn("no verdict row for Ticket #2, Ticket #3", done.stderr)
        self.assertNotIn("CLEAN", done.stdout)
        self.assertEqual(self.verifier_rows(), [])

    def test_rows_naming_every_ticket_criterion_are_logged_clean(self):
        done = self.log("--rows", "-", stdin=json.dumps(ticket_rows([])))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("CLEAN", done.stdout)

    def test_result_na_skips_the_ticket_check(self):
        done = self.log("--rows", "-", "--result", "NA", stdin="[]")
        self.assertEqual(done.returncode, 3)


class ReviewGateTest(VerifyBranchBase):
    """verify-log refuses to write unless a marked branch review covers the tree prep measured."""

    def setUp(self):
        super().setUp()
        self.task_dir()
        self.assertEqual(self.prep().returncode, 0)

    def rows(self):
        built = [{"item": f"AC{n}: item", "verdict": "done", "file": f"src/f{n}.py", "line": 1,
                  "evidence": "e"} for n in (1, 2, 3)]
        return json.dumps([*built, *ticket_rows(built)])

    def test_no_review_logged_exits_2_and_writes_nothing(self):
        done = self.log("--rows", "-", stdin=self.rows())
        self.assertEqual(done.returncode, 2)
        self.assertIn("rerun verify-prep", done.stderr)
        self.assertNotIn("CLEAN", done.stdout)
        self.assertEqual(self.jsonl(self.findings), [])
        self.assertIs(self.context()["logged"], False)

    def test_a_busy_ledger_logs_the_verifier_rows_when_this_checkout_logged_the_review(self):
        self.assertEqual(self.log_review().returncode, 0)
        busy_env = self.busy_ledger_env()
        self.assertEqual(self.prep(extra_env=busy_env).returncode, 0)

        done = self.log("--rows", "-", stdin=self.rows(), extra_env=busy_env)

        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("review check read from this checkout's record", done.stderr)
        self.assertNotEqual(self.verifier_rows(), [])

    def test_a_busy_ledger_with_no_review_logged_here_exits_2_and_writes_nothing(self):
        busy_env = self.busy_ledger_env()
        self.assertEqual(self.prep(extra_env=busy_env).returncode, 0)

        done = self.log("--rows", "-", stdin=self.rows(), extra_env=busy_env)

        self.assertEqual(done.returncode, 2)
        self.assertIn("rerun verify-prep", done.stderr)
        self.assertEqual(self.verifier_rows(), [])

    def test_review_row_without_the_marker_does_not_pass_the_gate(self):
        head = self.git("rev-parse", "HEAD").strip()
        row = {"_type": "review_run", "gate": "code-reviewer", "scope": "branch-exit", "iter": "1", "diff_loc": "5",
               "n_findings": "0", "result": "PASS", "branch_key": "LED-9-thing", "head": head}
        self.findings.write_text(json.dumps(row) + "\n")
        self.assertEqual(self.log("--rows", "-", stdin=self.rows()).returncode, 2)

    def test_tree_edited_after_prep_exits_2_even_with_a_review_logged(self):
        self.assertEqual(self.log_review().returncode, 0)
        self.assertEqual(self.prep().returncode, 0)
        self.write("src/a.py", "print(99)\n")
        done = self.log("--rows", "-", stdin=self.rows())
        self.assertEqual(done.returncode, 2)
        self.assertIn("rerun verify-prep", done.stderr)
        self.assertEqual(self.verifier_rows(), [])

    def test_review_logged_for_a_new_tree_without_a_new_prep_exits_2(self):
        self.write("src/a.py", "print(2)\n")
        self.assertEqual(self.log_review().returncode, 0)
        done = self.log("--rows", "-", stdin=self.rows())
        self.assertEqual(done.returncode, 2)
        self.assertIn("changed since verify-prep", done.stderr)
        self.assertEqual(self.verifier_rows(), [])

    def test_untracked_file_added_after_prep_exits_2(self):
        self.assertEqual(self.log_review().returncode, 0)
        self.assertEqual(self.prep().returncode, 0)
        self.write("late.txt", "x\n")
        self.assertEqual(self.log("--rows", "-", stdin=self.rows()).returncode, 2)

    def test_task_dir_edit_after_prep_does_not_block_logging(self):
        self.assertEqual(self.log_review().returncode, 0)
        self.assertEqual(self.prep().returncode, 0)
        self.write("docs/plans/LED-9-thing/spec.md", SPEC + "\n- [x] ticked\n")
        done = self.log("--rows", "-", stdin=self.rows())
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_escapes_only_with_no_full_run_exits_2(self):
        self.assertEqual(self.log_review().returncode, 0)
        self.assertEqual(self.prep().returncode, 0)
        rows = json.dumps([{"item": "x", "verdict": "missing", "guard": "check"}])
        done = self.log("--rows", "-", "--escapes-only", stdin=rows)
        self.assertEqual(done.returncode, 2)
        self.assertIn("none was logged", done.stderr)
        self.assertEqual(self.escape_rows(), [])


class LogTest(VerifyBranchBase):
    def setUp(self):
        super().setUp()
        self.task_dir()
        self.assertEqual(self.prep().returncode, 0)
        reviewed = self.log_review()
        self.assertEqual(reviewed.returncode, 0, reviewed.stderr)
        self.assertEqual(self.prep().returncode, 0)
        self.assertIn("REVIEW: ran", self.prep().stdout)

    def rows(self, *verdicts, extra=None):
        built = [{"item": f"AC{n}: item {n}", "verdict": verdict, "file": f"src/f{n}.py", "line": n,
                  "evidence": "e"} for n, verdict in enumerate(verdicts, 1)]
        for row, more in zip(built, extra or [], strict=False):
            row.update(more)
        return self.dump(built)

    def dump(self, built):
        """Rows as JSON, with a `done` row for each criteria-file id (AC1..AC3) the rows do not name."""
        covered = set(re.findall(r"AC\d+", " ".join(row["item"] for row in built)))
        for n in (1, 2, 3):
            if f"AC{n}" not in covered:
                built.append({"item": f"AC{n}: item {n}", "verdict": "done", "file": f"src/p{n}.py", "line": 1,
                              "evidence": "e"})
        built.extend(ticket_rows(built))
        return json.dumps(built)

    def test_an_id_with_no_verdict_row_exits_2_names_it_and_writes_nothing(self):
        rows = json.dumps([{"item": "AC1: item", "verdict": "done"}, {"item": "AC2: item", "verdict": "done"}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 2)
        self.assertIn("no verdict row for AC3", done.stderr)
        self.assertNotIn("CLEAN", done.stdout)
        self.assertEqual(self.verifier_rows(), [])
        self.assertEqual(self.jsonl(self.escapes), [])
        self.assertIsNot(self.context().get("logged"), True)

    def test_a_ticket_criterion_with_no_verdict_row_exits_2_names_it_and_writes_nothing(self):
        built = [{"item": f"AC{n}: item", "verdict": "done"} for n in (1, 2, 3)]
        built.append({"item": "Ticket #1: First thing works", "verdict": "done"})
        done = self.log("--rows", "-", stdin=json.dumps(built))
        self.assertEqual(done.returncode, 2)
        self.assertIn("no verdict row for Ticket #2, Ticket #3", done.stderr)
        self.assertNotIn("CLEAN", done.stdout)
        self.assertEqual(self.verifier_rows(), [])
        self.assertIsNot(self.context().get("logged"), True)

    def test_a_ticket_label_inside_a_longer_label_does_not_count_as_covered(self):
        built = [{"item": f"AC{n}: item", "verdict": "done"} for n in (1, 2, 3)]
        built.extend({"item": f"Ticket #{n}2: other", "verdict": "done"} for n in (1, 2, 3))
        done = self.log("--rows", "-", stdin=json.dumps(built))
        self.assertEqual(done.returncode, 2)
        self.assertIn("no verdict row for Ticket #1, Ticket #2, Ticket #3", done.stderr)

    def test_a_bold_or_backticked_label_at_the_start_of_a_row_covers_its_criterion(self):
        built = [{"item": f"AC{n}: item", "verdict": "done", "file": f"src/a{n}.py", "line": 1, "evidence": "e"}
                 for n in (1, 2, 3)]
        built.append({"item": "**Ticket #1**: First thing works", "verdict": "done", "file": "src/t1.py",
                      "line": 1, "evidence": "e"})
        built.append({"item": "`Ticket #2`: Second thing", "verdict": "done", "file": "src/t2.py",
                      "line": 1, "evidence": "e"})
        built.append({"item": "Ticket #3: Third thing", "verdict": "done", "file": "src/t3.py",
                      "line": 1, "evidence": "e"})
        done = self.log("--rows", "-", stdin=json.dumps(built))
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_label_named_only_mid_text_in_another_row_does_not_cover_it(self):
        built = [{"item": f"AC{n}: item", "verdict": "done"} for n in (1, 2, 3)]
        built.append({"item": "Ticket #1: First thing works", "verdict": "done"})
        built.append({"item": "Ticket #3: same as Ticket #2 for admins", "verdict": "done"})
        done = self.log("--rows", "-", stdin=json.dumps(built))
        self.assertEqual(done.returncode, 2)
        self.assertIn("no verdict row for Ticket #2", done.stderr)
        self.assertEqual(self.verifier_rows(), [])

    def test_missing_ids_and_ticket_labels_are_named_in_one_message(self):
        done = self.log("--rows", "-", stdin=json.dumps([{"item": "AC2: item", "verdict": "done"}]))
        self.assertEqual(done.returncode, 2)
        self.assertEqual(1, done.stderr.count("no verdict row for"))
        self.assertIn("AC1, AC3, Ticket #1, Ticket #2, Ticket #3", done.stderr)

    def test_every_absent_id_is_named(self):
        rows = json.dumps([{"item": "AC2: item", "verdict": "done"}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 2)
        self.assertIn("no verdict row for AC1, AC3", done.stderr)

    def test_a_missing_row_for_every_id_is_accepted_and_logged_as_a_gap(self):
        built = [{"item": f"AC{n}: item", "verdict": "missing", "guard": "check", "severity": "medium"}
                 for n in (1, 2, 3)]
        rows = json.dumps([*built, *ticket_rows(built)])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("GAPS: 3", done.stdout)
        self.assertIs(self.context()["logged"], True)

    def test_a_call_that_exited_2_for_an_absent_id_can_be_sent_again_complete(self):
        partial = json.dumps([{"item": "AC1: item", "verdict": "done"}])
        self.assertEqual(self.log("--rows", "-", stdin=partial).returncode, 2)
        done = self.log("--rows", "-", stdin=self.rows("done", "done", "done"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("CLEAN", done.stdout)

    def test_an_id_named_inside_a_longer_id_does_not_count_as_covered(self):
        rows = json.dumps([{"item": "AC10: item", "verdict": "done"}, {"item": "AC2: item", "verdict": "done"},
                           {"item": "AC3: item", "verdict": "done"}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 2)
        self.assertIn("no verdict row for AC1", done.stderr)

    def test_whitespace_only_signoff_is_a_gap(self):
        rows = self.rows("overridden", extra=[{"signoff": "  \n "}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertIn("GAPS: 1", done.stdout)

    def test_escapes_carry_across_a_new_prep_so_they_are_not_logged_twice(self):
        rows = self.rows("missing", extra=[{"guard": "rule", "severity": "high"}])
        self.assertEqual(self.log("--rows", "-", stdin=rows).returncode, 0)
        self.assertEqual(self.prep().returncode, 0)
        again = self.log("--rows", "-", stdin=rows)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("already recorded", again.stdout)
        self.assertEqual(len(self.escape_rows()), 1)

    def test_gaps_write_run_findings_and_escapes(self):
        rows = self.rows("done", "partial", "missing",
                         extra=[{}, {"guard": "check", "severity": "medium"}, {"guard": "none", "severity": "medium"}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 0, done.stderr)
        logged = self.verifier_rows()
        run = logged[0]
        self.assertEqual((run["_type"], run["gate"], run["scope"], run["n_findings"], run["result"]),
                         ("review_run", "plan-verifier", "branch-exit", "2", "NEEDS_CHANGES"))
        self.assertEqual(run["lane"], "verify")
        self.assertNotIn("tree", run)
        self.assertEqual(run["diff_loc"], "5")
        findings = logged[1:]
        self.assertEqual([f["class"] for f in findings], ["plan-drift", "plan-drift"])
        self.assertEqual([f["lane"] for f in findings], ["verify", "verify"])
        self.assertEqual([f["path_key"] for f in findings], ["src/f2.py", "src/f3.py"])
        escapes = self.escape_rows()
        self.assertEqual([e["guard"] for e in escapes], ["check", "none"])
        self.assertEqual([e["severity"] for e in escapes], ["medium", "medium"])
        self.assertEqual(escapes[0]["gate_missed"], "drift-gate")
        self.assertIn("GAPS: 2", done.stdout)
        self.assertIs(self.context()["logged"], True)
        self.assertEqual(len(self.context()["escapes"]), 2)

    def test_gap_without_a_file_logs_the_repo_relative_plan_path(self):
        rows = self.dump([{"item": "x", "verdict": "missing"}])
        self.assertEqual(self.log("--rows", "-", stdin=rows).returncode, 0)
        self.assertEqual(self.verifier_rows()[1]["path_key"], "docs/plans/LED-9-thing/spec.md")

    def test_gap_without_guard_asks_and_escapes_only_follows_up(self):
        rows = self.rows("missing")
        done = self.log("--rows", "-", stdin=rows)
        self.assertIn("NEEDS GUARD", done.stdout)
        self.assertEqual(self.escape_rows(), [])
        again = self.log("--rows", "-", stdin=rows)
        self.assertEqual(again.returncode, 2)
        self.assertIn("already logged", again.stderr)
        fixed = self.rows("missing", extra=[{"guard": "rule", "severity": "high"}])
        follow_up = self.log("--rows", "-", "--escapes-only", stdin=fixed)
        self.assertEqual(follow_up.returncode, 0, follow_up.stderr)
        self.assertIn("escapes logged: 1", follow_up.stdout)
        for absent in ("verdicts:", "GAPS", "CLEAN", "Smoke-test"):
            self.assertNotIn(absent, follow_up.stdout)
        self.assertEqual(len(self.escape_rows()), 1)
        self.assertEqual(len(self.verifier_rows()), 2)

    def test_repeated_escapes_only_does_not_log_the_same_escape_twice(self):
        self.assertEqual(self.log("--rows", "-", stdin=self.rows("missing")).returncode, 0)
        fixed = self.rows("missing", extra=[{"guard": "rule", "severity": "high"}])
        self.assertEqual(self.log("--rows", "-", "--escapes-only", stdin=fixed).returncode, 0)
        second = self.log("--rows", "-", "--escapes-only", stdin=fixed)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("already recorded", second.stdout)
        self.assertEqual(len(self.escape_rows()), 1)

    def test_escapes_only_does_not_reread_the_plan(self):
        self.assertEqual(self.log("--rows", "-", stdin=self.rows("missing")).returncode, 0)
        (self.repo / "docs" / "plans" / "LED-9-thing" / "spec.md").unlink()
        no_gaps = self.rows("done")
        follow_up = self.log("--rows", "-", "--escapes-only", stdin=no_gaps)
        self.assertEqual(follow_up.returncode, 0, follow_up.stderr)
        self.assertIn("escapes logged: 0", follow_up.stdout)

    def test_escape_already_logged_in_the_full_run_is_not_logged_by_escapes_only(self):
        rows = self.rows("missing", extra=[{"guard": "rule", "severity": "high"}])
        self.assertEqual(self.log("--rows", "-", stdin=rows).returncode, 0)
        self.assertEqual(self.log("--rows", "-", "--escapes-only", stdin=rows).returncode, 0)
        self.assertEqual(len(self.escape_rows()), 1)

    def test_overridden_without_signoff_is_a_gap(self):
        rows = self.rows("overridden", "overridden", extra=[{"signoff": "Brandon, 2026-10-20: ok"}, {}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertIn("GAPS: 1", done.stdout)
        self.assertEqual(self.verifier_rows()[0]["n_findings"], "1")

    def test_failed_automated_check_is_a_gap_not_a_clean_pass(self):
        rows = self.rows("done", "failed-check", extra=[{}, {"guard": "check", "severity": "high"}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("GAPS: 1", done.stdout)
        self.assertNotIn("CLEAN", done.stdout)
        logged = self.verifier_rows()
        self.assertEqual((logged[0]["result"], logged[0]["n_findings"]), ("NEEDS_CHANGES", "1"))
        self.assertEqual(logged[1]["class"], "plan-drift")
        self.assertEqual(self.escape_rows()[0]["severity"], "high")

    def test_clean_logs_pass_and_prints_checklist(self):
        rows = self.rows("done", "done", "needs-manual")
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.verifier_rows()[0]["result"], "PASS")
        self.assertEqual(len(self.verifier_rows()), 1)
        for expected in ("- [ ] Ticket #1: First thing works", "- [ ] Ticket #3: Third thing",
                         "(manual-only) AC3: needs a real machine.", "(human-only) Brandon reads the contract",
                         "(human-only) **Manual-verified** (human-only): read the thing",
                         "(needs-manual) AC3: item 3", "src/a.py", "src/f1.py:1"):
            self.assertIn(expected, done.stdout)
        self.assertNotIn("- [ ] AC1:", done.stdout)
        self.assertNotIn("AC3 (manual-only)", done.stdout)
        self.assertNotIn("agent can drive this", done.stdout)

    def test_manual_only_entries_come_from_the_criteria_file_not_ticket_ordinals(self):
        criteria = (
            "- **AC1** — a.\n- **AC2** — b.\n## Manual only\n- **AC2** — only on a phone.\n- **AC7** — only on a Mac.\n"
        )
        self.task_dir(criteria=criteria)
        self.assertEqual(self.prep().returncode, 0)
        covering = self.dump([{"item": f"{ac_id}: x", "verdict": "done"} for ac_id in ("AC1", "AC2", "AC7")])
        done = self.log("--rows", "-", stdin=covering)
        self.assertIn("(manual-only) AC7: only on a Mac.", done.stdout)
        self.assertIn("(manual-only) AC2: only on a phone.", done.stdout)
        self.assertNotIn("AC1 (manual-only)", done.stdout)
        self.assertIn("- [ ] Ticket #1: First thing works", done.stdout)

    def test_manual_items_added_to_the_plan_after_prep_reach_the_checklist(self):
        plan_path = self.repo / "docs" / "plans" / "LED-9-thing" / "spec.md"
        plan_path.write_text(
            SPEC + "\n#### Manual Verification (human-only):\n\n- [ ] human-only: late item — needs a phone\n"
            "- [x] human-only: ticked item — done\n"
        )
        done = self.log("--rows", "-", stdin=self.rows("done"))
        self.assertIn("late item", done.stdout)
        self.assertNotIn("ticked item", done.stdout)

    def test_a_moved_phase_is_listed_with_its_ticket_and_its_items_are_not_in_the_checklist(self):
        plan_path = self.repo / "docs" / "plans" / "LED-9-thing" / "spec.md"
        plan_path.write_text(MOVED_PLAN)
        done = self.log("--rows", "-", stdin=self.rows("done"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("(human-only) human-only: kept item", done.stdout)
        self.assertNotIn("Mac item", done.stdout)
        self.assertIn("## Moved phases", done.stdout)
        self.assertIn("- Phase 2 moved to LED-16: 2 unchecked Manual Verification item(s) go with it", done.stdout)

    def test_a_moved_line_with_no_ticket_key_or_no_deviation_entry_stops_verify_log_with_the_line(self):
        plan_path = self.repo / "docs" / "plans" / "LED-9-thing" / "spec.md"
        no_key = MOVED_PLAN.replace("moved to LED-16, per the user", "deferred, per the user")
        no_deviation = MOVED_PLAN.replace("- 2026-10-20: Phase 2 moves to LED-16.", "- 2026-10-20: Phase 1 changed.")
        for name, plan_text in (("no key", no_key), ("no deviation", no_deviation)):
            with self.subTest(name):
                plan_path.write_text(plan_text)
                done = self.log("--rows", "-", stdin=self.rows("done"))
                self.assertNotEqual(done.returncode, 0, done.stdout)
                self.assertIn("spec.md:6:", done.stderr)

    def test_ticket_edited_after_prep_reaches_the_checklist(self):
        ticket_path = self.repo / "docs" / "plans" / "LED-9-thing" / "00-ticket.md"
        ticket_path.write_text(TICKET.replace("First thing works", "Reworded first thing"))
        done = self.log("--rows", "-", stdin=self.rows("done"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Ticket #1: Reworded first thing", done.stdout)
        self.assertNotIn("First thing works", done.stdout)

    def test_line_range_is_normalized_before_anything_is_logged(self):
        rows = self.dump([{"item": "x", "verdict": "missing", "file": "src/a.py", "line": "12-20"}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 0, done.stderr)
        logged = self.verifier_rows()
        self.assertEqual([row["_type"] for row in logged], ["review_run", "review_finding"])
        self.assertEqual(logged[1]["line"], "12")
        self.assertIs(self.context()["logged"], True)

    def test_unparseable_line_fails_before_the_run_row_is_written(self):
        rows = json.dumps([{"item": "ok", "verdict": "done", "line": 3},
                           {"item": "x", "verdict": "missing", "file": "src/a.py", "line": "abc"}])
        done = self.log("--rows", "-", stdin=rows)
        self.assertEqual(done.returncode, 2)
        self.assertIn("row 1", done.stderr)
        self.assertEqual(self.verifier_rows(), [])
        self.assertFalse(self.context()["logged"])

    def test_empty_rows_without_na_fail_and_log_nothing(self):
        done = self.log("--rows", "-", stdin="[]")
        self.assertEqual(done.returncode, 2)
        self.assertIn("--result NA", done.stderr)
        self.assertEqual(self.verifier_rows(), [])

    def test_empty_rows_with_na_log_a_run_row_with_no_result_and_exit_3(self):
        done = self.log("--rows", "-", "--result", "NA", stdin="[]")
        self.assertEqual(done.returncode, 3)
        self.assertIn("NOT a pass", done.stdout)
        run = self.verifier_rows()[0]
        self.assertNotIn("result", run)
        self.assertEqual(run["n_findings"], "0")

    def test_bad_rows_fail_loudly(self):
        for bad in ("not json", '[{"item":"x","verdict":"maybe"}]'):
            self.assertEqual(self.log("--rows", "-", stdin=bad).returncode, 2, bad)
        self.assertEqual(self.verifier_rows(), [])

    def test_a_guard_the_logger_refuses_stops_the_run_before_any_write(self):
        rows = self.dump([{"item": "x", "verdict": "missing", "guard": "wish"}])
        done = self.log("--rows", "-", stdin=rows, extra_env={"STUB_REFUSE": "guard=wish"})
        self.assertEqual(done.returncode, 2)
        self.assertIn("logger failed", done.stderr)
        self.assertIn("nothing was written", done.stderr)
        self.assertEqual(self.verifier_rows(), [])
        self.assertEqual(self.escape_rows(), [])
        self.assertFalse(self.context()["logged"])

    def test_a_logger_failing_mid_run_names_the_rows_not_logged_and_keeps_what_was_written(self):
        rows = self.rows("missing", "missing", extra=[{}, {}])
        done = self.log("--rows", "-", stdin=rows, extra_env={"STUB_FAIL_WRITE": "desc=AC2"})
        self.assertEqual(done.returncode, 2)
        self.assertIn("logger failed", done.stderr)
        self.assertIn("NOT logged: plan-drift finding: AC2: item 2", done.stderr)
        self.assertNotIn("NOT logged: plan-verifier run row", done.stderr)
        self.assertEqual([row["_type"] for row in self.verifier_rows()], ["review_run", "review_finding"])
        self.assertIs(self.context()["logged"], True)

    def test_unknown_flag_exits_2_and_logs_nothing(self):
        done = self.log("--rows", "-", "--bogus", stdin=self.rows("done"))
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown argument", done.stderr)
        self.assertEqual(self.verifier_rows(), [])

    def test_trailing_option_without_a_value_fails_loudly(self):
        done = self.log("--rows")
        self.assertEqual(done.returncode, 2)
        self.assertIn("needs a value", done.stderr)

    def test_multiline_desc_is_one_line(self):
        rows = self.dump([{"item": 'has "quotes"\nand a newline', "verdict": "missing", "guard": "none"}])
        argv_log = self.temp_root / "finder-argv"
        self.assertEqual(self.log("--rows", "-", stdin=rows, extra_env={"STUB_ARGV_LOG": str(argv_log)}).returncode, 0)
        descs = [arg for arg in argv_log.read_text().split("\0") if arg.startswith("desc=")]
        self.assertTrue(descs)
        for desc in descs:
            self.assertNotIn("\n", desc)
            self.assertNotIn('"', desc)

    def test_detached_head_fails(self):
        self.git("checkout", "-q", "--detach")
        done = self.log("--rows", "-", stdin=self.rows("done"))
        self.assertEqual(done.returncode, 2)
        self.assertIn("detached HEAD", done.stderr)
        self.assertEqual(self.verifier_rows(), [])

    def test_runs_from_a_subdirectory(self):
        rows = self.rows("missing", extra=[{"guard": "rule", "severity": "low"}])
        done = self.log("--rows", "-", stdin=rows, cwd=self.repo / "src")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(self.verifier_rows()), 2)
        self.assertEqual(len(self.escape_rows()), 1)


class ReviewLogTest(VerifyBranchBase):
    def setUp(self):
        super().setUp()
        self.task_dir()
        self.assertEqual(self.prep().returncode, 0)

    def test_every_reviewer_finding_gets_a_finding_row(self):
        findings = json.dumps([
            {"desc": "off by one", "file": "src/a.py", "line": 3, "class": "bug", "actioned": "fixed"},
            {"desc": "dup helper", "file": "src/a.py", "line": "7-9", "class": "duplication", "actioned": "fixed"},
        ])
        done = self.log_review(findings, "NEEDS CHANGES", "--findings", "2")
        self.assertEqual(done.returncode, 0, done.stderr)
        run, first, second = self.jsonl(self.findings)
        self.assertEqual((run["_type"], run["n_findings"], run["result"]), ("review_run", "2", "NEEDS_CHANGES"))
        for row in (run, first, second):
            self.assertEqual((row["gate"], row["scope"], row["lane"]), ("code-reviewer", "branch-exit", "verify"))
        self.assertEqual((first["_type"], first["class"], first["actioned"], first["line"]),
                         ("review_finding", "bug", "fixed", "3"))
        self.assertEqual((second["class"], second["line"], second["disposition"]), ("duplication", "7", "fix"))

    def test_actioned_is_required(self):
        findings = json.dumps([{"desc": "x", "file": "src/a.py", "line": 1, "class": "bug"}])
        done = self.log_review(findings)
        self.assertEqual(done.returncode, 2)
        self.assertIn("actioned", done.stderr)
        self.assertEqual(self.jsonl(self.findings), [])

    def test_a_fix_finding_cannot_be_actioned_none(self):
        findings = json.dumps([{"desc": "x", "file": "src/a.py", "line": 1, "actioned": "none"}])
        done = self.log_review(findings)
        self.assertEqual(done.returncode, 2)
        self.assertIn("cannot have actioned `none`", done.stderr)
        self.assertEqual(self.jsonl(self.findings), [])

    def test_findings_count_must_match_the_rows(self):
        findings = json.dumps([{"desc": "x", "file": "src/a.py", "line": 1, "actioned": "fixed"}])
        self.assertEqual(self.log_review(findings, "PASS", "--findings", "2").returncode, 2)
        self.assertEqual(self.log_review("[]", "PASS", "--findings", "two").returncode, 2)
        self.assertEqual(self.jsonl(self.findings), [])

    def test_review_without_rows_or_with_a_bad_result_fails(self):
        self.assertEqual(self.log("review", "--result", "PASS").returncode, 2)
        self.assertEqual(self.log("review", "--result", "FINE", "--rows", "-", stdin="[]").returncode, 2)
        self.assertEqual(self.log("review", "--result").returncode, 2)
        self.assertEqual(self.jsonl(self.findings), [])

    def test_unknown_flag_fails(self):
        done = self.log_review("[]", "PASS", "--bogus")
        self.assertEqual(done.returncode, 2)
        self.assertIn("unknown argument", done.stderr)
        self.assertEqual(self.jsonl(self.findings), [])

    def test_bad_finding_fails_before_the_run_row(self):
        bad = json.dumps([{"desc": "x", "file": "src/a.py", "class": "wish", "actioned": "fixed"}])
        done = self.log_review(bad, extra_env={"STUB_REFUSE": "class=wish"})
        self.assertEqual(done.returncode, 2)
        self.assertIn("nothing was written", done.stderr)
        self.assertEqual(self.jsonl(self.findings), [])

    def test_a_second_review_for_a_covered_tree_exits_2(self):
        self.assertEqual(self.log_review().returncode, 0)
        again = self.log_review()
        self.assertEqual(again.returncode, 2)
        self.assertIn("already covers this tree", again.stderr)
        self.assertEqual(len(self.jsonl(self.findings)), 1)

    def test_a_review_after_a_fix_is_allowed(self):
        self.assertEqual(self.log_review().returncode, 0)
        self.write("src/a.py", "print(3)\n")
        self.assertEqual(self.log_review().returncode, 0)
        self.assertEqual(len(self.jsonl(self.findings)), 2)

    def test_runs_from_a_subdirectory(self):
        done = self.log_review(cwd=self.repo / "src")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("REVIEW: ran", self.prep(cwd=self.repo / "src").stdout)


class RealPlansTest(unittest.TestCase):
    """Every real task dir under ~/dev/*/docs/{plans,eng-specs}/: the criteria parse, and no id is silently dropped."""

    BOLD_ID_LINE = re.compile(r"^\s*[-*]\s+\*\*(AC[^*]*)\*\*", re.M)

    def task_dirs(self):
        dirs = set()
        for root in ("plans", "eng-specs"):
            for pattern in ("00-ticket.md", "*-00-ticket.md"):
                found = glob.glob(str(REAL_HOME / "dev" / "*" / "docs" / root / "*" / pattern))
                dirs.update(pathlib.Path(p).parent for p in found)
        return sorted(dirs)

    def ticket_path(self, task_dir):
        fixed = task_dir / "00-ticket.md"
        return fixed if fixed.is_file() else sorted(task_dir.glob("*-00-ticket.md"))[0]

    def test_every_real_ticket_yields_criteria_and_every_criteria_id_parses(self):
        common = load_common()
        dirs = self.task_dirs()
        if not dirs:
            self.skipTest("no real plans on this machine")
        counts = []
        for task_dir in dirs:
            with self.subTest(task_dir=str(task_dir)):
                found = common.ticket_criteria(self.ticket_path(task_dir).read_text(), str(task_dir))
                self.assertGreaterEqual(len(found), 1)
                criteria_path = task_dir / "acceptance-criteria.md"
                if criteria_path.is_file():
                    text = criteria_path.read_text()
                    entries, manual = common.parse_criteria_file(text, str(criteria_path))
                    parsed = len(entries) + len(manual)
                    expected = sum(len(re.findall(r"AC\d+", span)) for span in self.BOLD_ID_LINE.findall(text))
                    plain = len(re.findall(r"\*\*AC\d+\*\*", text))
                    counts.append((str(task_dir), parsed, expected, plain))
                    self.assertGreaterEqual(parsed, 1)
                    self.assertEqual(parsed, expected)
                    self.assertGreaterEqual(parsed, plain)
                plans = [task_dir / "spec.md", *task_dir.glob("*-05-plan.md")]
                for plan_path in plans:
                    if plan_path.is_file():
                        common.manual_items(plan_path.read_text(), str(plan_path))
        for name, parsed, expected, plain in counts:
            print(f"{name}: parsed {parsed} ids; bold-id lines hold {expected}; **ACn** occurrences {plain}",
                  file=sys.stderr)

    def test_single_file_plans_with_a_stub_list_fail_loudly_not_misread(self):
        common = load_common()
        plans = sorted(glob.glob(str(REAL_HOME / "dev" / "residuum" / "docs" / "eng-specs" / "RES-[3-6]-*.md")))
        if not plans:
            self.skipTest("no single-file plans on this machine")
        for plan_path in plans:
            with self.subTest(plan=plan_path):
                with self.assertRaises(common.VerifyError) as caught:
                    common.ticket_criteria(pathlib.Path(plan_path).read_text(), plan_path)
                self.assertIn("Acceptance Stubs", str(caught.exception))
                self.assertIn(f"{plan_path}:", str(caught.exception))

    def repo_with_history(self, task_dir):
        for candidate in (task_dir, *task_dir.parents):
            if (candidate / ".git").exists():
                return candidate
        return None

    def test_prep_runs_end_to_end_on_every_real_task_dir(self):
        dirs = self.task_dirs()
        if not dirs:
            self.skipTest("no real plans on this machine")
        parsed = 0
        ran = 0
        detached = 0
        for task_dir in dirs:
            repo_root = self.repo_with_history(task_dir)
            if repo_root is None:
                continue
            with self.subTest(task_dir=str(task_dir)):
                temp_dir = tempfile.TemporaryDirectory()
                self.addCleanup(temp_dir.cleanup)
                temp_home = pathlib.Path(temp_dir.name) / "home"
                (temp_home / ".claude").mkdir(parents=True)
                env = subprocess_env({**os.environ, "HOME": str(temp_home), "VERIFY_STATE_DIR": temp_dir.name,
                                      "GIT_OPTIONAL_LOCKS": "0", "REPO_NAME_SCRIPT": str(REPO_NAMER),
                                      "RESOLVE_TASK_DIR_SCRIPT": str(RESOLVER),
                                      **fake_ledger.install(temp_dir.name)})
                roots_run = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=repo_root, env=env,
                                          capture_output=True, text=True)
                roots = roots_run.stdout.split()
                if roots_run.returncode != 0 or not roots:
                    continue

                branch_run = subprocess.run(["git", "symbolic-ref", "-q", "HEAD"], cwd=repo_root, env=env,
                                           capture_output=True, text=True)
                if branch_run.returncode != 0:
                    detached += 1
                    continue

                ran += 1
                done = subprocess.run([str(PREP), str(task_dir), "--base", roots[-1]], cwd=repo_root, env=env,
                                      capture_output=True, text=True)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("STEP 1", done.stdout)
                parsed += 1
        print(f"parsed {parsed} of {len(dirs)} real task dirs ({ran} had a repo with commits, "
              f"{detached} skipped on a detached HEAD, which verify-prep refuses by design)", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
