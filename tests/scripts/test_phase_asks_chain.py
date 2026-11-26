"""The phase-asks chain from end to end, each step a real process: code_review_start.py runs the review loop's own
entry (which builds the packet and writes the hand-back rows), code_wait.py opens the asks, `phase_asks.py list`
prints them with the rule command, that command rules on them, and the listing then reads them as ruled.

Only the loop's walk is a stand-in: `run_loop` returns a fixed converged outcome with two finding asks, so no
`claude -p` call is made. The test writes no store row itself."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

import fake_ledger
import toolkit_paths

SESSION = "33333333-aaaa-bbbb-cccc-444444444444"
FIRST_ID = "0ff295856f1a9ccc"
SECOND_ID = "1aa295856f1a9ddd"
PLACEHOLDER = "'accepted|rejected:<one-line reason>'"
ACCEPTED_WORD = "'accepted:fixes a defect in scope'"
REJECTED_WORD = "'rejected:changes a criterion'"
LOOP_ENTRY_IMPORT = "    import review_loop_main\n"
LOOP_WAIT_SECONDS = 60
OPEN_PART = "Rule on all 2 in order: `"
RULED_PART = "These asks are already ruled."
# The loop's walk, replaced: a converged outcome with two finding asks, in the keys Loop.outcome returns.
STAND_IN_SOURCE = f'''"""A fixed outcome in place of the review loop's walk, so the chain test makes no model call."""
import copy

import finding_record
import review_loop_packet


def finding_ask(text, line):
    return finding_record.Finding(text=text, path="base.py", line=line, finding_class="correctness", title="",
                                  identifiers=frozenset())


def run_loop(_request):
    first = finding_ask("Should an empty list count as none?", 1)
    second = finding_ask("Should the cap be 3?", 2)
    return {{
        **copy.deepcopy(review_loop_packet.EMPTY_OUTCOME),
        "status": "converged", "iter": 1, "review_round": 1, "asks": [first, second],
        "ask_ids": {{first: "{FIRST_ID}", second: "{SECOND_ID}"}},
        "ask_rows": [{{"file": "base.py", "line": 1, "finding_id": "{FIRST_ID}"}},
                     {{"file": "base.py", "line": 2, "finding_id": "{SECOND_ID}"}}],
        "class_closure": "n/a - fixed[] empty", "full_check": "passed", "full_check_command": "bash tests/run.sh",
        "full_check_summaries": ["1 tests, 0 failed"],
    }}
'''


class PhaseAsksChainTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.scripts = self.tmp / "claude" / "scripts"
        shutil.copytree(toolkit_paths.SCRIPTS_DIR, self.scripts, ignore=shutil.ignore_patterns("__pycache__"))
        # review_loop_nearest finds the refactor skill's scripts two folders above the review scripts.
        shutil.copytree(toolkit_paths.CLAUDE_DIR / "skills" / "refactor" / "scripts",
                        self.tmp / "claude" / "skills" / "refactor" / "scripts",
                        ignore=shutil.ignore_patterns("__pycache__"))
        self.plant_loop_stand_in()
        self.ledger_env = fake_ledger.install(self.tmp)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "base.py").write_text("one\ntwo\n")
        self.git("add", "base.py")
        self.git("commit", "-q", "-m", "base")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "base.py").write_text("one changed\ntwo changed\n")
        self.handoff = self.tmp / "handoff.txt"
        self.handoff.write_text("  Phase 1 is done.\n")

    def plant_loop_stand_in(self):
        loop_script = self.scripts / "review" / "review_loop_script.py"
        source = loop_script.read_text()
        self.assertEqual(source.count(LOOP_ENTRY_IMPORT), 1, "the loop's entry lines changed; update the stand-in")
        stand_in_lines = ("    import chain_stand_in\n\n"
                          "    review_loop_main.run_loop = chain_stand_in.run_loop\n")
        loop_script.write_text(source.replace(LOOP_ENTRY_IMPORT, LOOP_ENTRY_IMPORT + stand_in_lines))
        (self.scripts / "review" / "chain_stand_in.py").write_text(STAND_IN_SOURCE)

    def environment(self, telemetry, session=SESSION):
        return {"PATH": self.ledger_env["PATH"], "FAKE_LEDGER_ROWS": self.ledger_env["FAKE_LEDGER_ROWS"],
                "HOME": str(self.home), "TMPDIR": str(self.tmp), "CLAUDE_CODE_SESSION_ID": session,
                "REVIEW_FIX_CLAUDE_DIR": str(toolkit_paths.CLAUDE_DIR), "CLAUDE_TOOLKIT_TELEMETRY": telemetry,
                "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_SYSTEM": "/dev/null"}

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=True,
                              env=self.environment("0"))

    def run_step(self, argv, telemetry, session=SESSION):
        return subprocess.run(argv, cwd=self.repo, capture_output=True, text=True,
                              env=self.environment(telemetry, session))

    def list_asks(self, telemetry, session=SESSION):
        listing = self.scripts / "review" / "phase_asks.py"
        finished = self.run_step([sys.executable, str(listing), "list"], telemetry, session)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout

    def wait_for_the_loop_to_end(self):
        pid = int((self.repo / ".git/code-phase/pid").read_text())
        deadline = time.monotonic() + LOOP_WAIT_SECONDS
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except OSError:
                return
            time.sleep(0.05)
        self.fail(f"the detached review loop (pid {pid}) still runs after {LOOP_WAIT_SECONDS} s")

    def review_the_phase(self, telemetry):
        """A coder dispatch, then the /code phase review as the skill runs it: start detached, then wait. Returns
        what the wait printed."""
        start = self.scripts / "code" / "code_review_start.py"
        started = self.run_step([sys.executable, str(start), "code", "-", "1", str(self.handoff), "--base", self.base,
                                 "--detach"], telemetry)
        self.assertEqual(started.returncode, 0, started.stderr)
        self.wait_for_the_loop_to_end()
        wait = self.scripts / "code" / "code_wait.py"
        waited = self.run_step([sys.executable, str(wait), "review"], telemetry)
        self.assertEqual(waited.returncode, 0, waited.stdout + waited.stderr)
        self.assertIn("The review loop script exited 0.", waited.stdout, self.loop_logs())
        return waited.stdout

    def loop_logs(self):
        logs = sorted((self.repo / ".git/code-step/loop-script").glob("*/script.log"))
        return "\n".join(log.read_text() for log in logs)

    def listed_rule_command(self, telemetry, session=SESSION):
        """The rule command the listing of the open asks prints, placeholders and all."""
        listing = self.list_asks(telemetry, session)
        self.assertIn(OPEN_PART, listing)
        self.assertIn("Should an empty list count as none?", listing)
        self.assertIn("Should the cap be 3?", listing)
        command = listing.partition(OPEN_PART)[2].partition("`")[0]
        self.assertEqual(command.count(PLACEHOLDER), 2, listing)
        return command

    def rule(self, command, telemetry):
        return subprocess.run(["bash", "-c", command], cwd=self.repo, capture_output=True, text=True,
                              env=self.environment(telemetry))

    def outcome_rows(self):
        return [row for row in fake_ledger.recorded_rows(self.ledger_env) if "ask_outcome" in row]

    def assert_asks_ruled(self, telemetry, session=SESSION):
        self.assertIn(RULED_PART, self.list_asks(telemetry, session))

    def test_the_printed_rule_command_rules_on_both_asks_and_each_outcome_is_logged(self):
        waited = self.review_the_phase("1")
        self.assertIn('"status": "converged"', waited)
        self.assertIn("2 finding ask(s) await your ruling", waited)

        command = self.listed_rule_command("1")
        ruling = command.replace(PLACEHOLDER, ACCEPTED_WORD, 1).replace(PLACEHOLDER, REJECTED_WORD, 1)
        ruled = self.rule(ruling, "1")

        self.assertEqual(ruled.returncode, 0, ruled.stderr)
        self.assertIn("Ruled 2 ask(s)", ruled.stdout)
        self.assert_asks_ruled("1")
        rows = self.outcome_rows()
        self.assertEqual([(row["finding_id"], row["ask_outcome"], row["ask_decided_by"]) for row in rows],
                         [(FIRST_ID, "accepted", "session"), (SECOND_ID, "rejected", "session")])
        self.assertEqual({(row["lane"], row["scope"], row["phase"]) for row in rows}, {("code", "phase", "1")})

    def test_with_the_telemetry_switch_off_the_ruling_stands(self):
        """log-review-finding's `ledger write` ignores the switch (test_telemetry_switch.py), so the outcome rows
        land with it off too."""
        self.review_the_phase("0")
        command = self.listed_rule_command("0")
        ruling = command.replace(PLACEHOLDER, ACCEPTED_WORD, 1).replace(PLACEHOLDER, REJECTED_WORD, 1)

        ruled = self.rule(ruling, "0")

        self.assertEqual(ruled.returncode, 0, ruled.stderr)
        self.assert_asks_ruled("0")
        self.assertEqual([row["finding_id"] for row in self.outcome_rows()], [FIRST_ID, SECOND_ID])

    def test_with_no_ledger_the_ruling_stands(self):
        self.review_the_phase("1")
        command = self.listed_rule_command("1")
        ruling = command.replace(PLACEHOLDER, ACCEPTED_WORD, 1).replace(PLACEHOLDER, REJECTED_WORD, 1)
        failing_ledger = {"FAKE_LEDGER_WRITE_EXIT": "2"}

        ruled = subprocess.run(["bash", "-c", ruling], cwd=self.repo, capture_output=True, text=True,
                               env={**self.environment("1"), **failing_ledger})

        self.assertEqual(ruled.returncode, 0, ruled.stderr)
        self.assertEqual(self.outcome_rows(), [])
        self.assert_asks_ruled("1")

    def test_a_new_session_id_after_the_review_still_meets_the_open_asks_and_can_rule_on_them(self):
        self.review_the_phase("1")
        after_clear = "44444444-aaaa-bbbb-cccc-555555555555"

        self.listed_rule_command("1", after_clear)
        rule = self.scripts / "review" / "phase_asks.py"
        ruled = self.run_step([sys.executable, str(rule), "rule", "accepted:fixes a defect in scope",
                               "rejected:changes a criterion"], "1", after_clear)
        self.assertEqual(ruled.returncode, 0, ruled.stderr)
        self.assert_asks_ruled("1", after_clear)

    def test_a_ruling_with_one_outcome_for_two_asks_is_refused_and_the_asks_stay_open(self):
        self.review_the_phase("1")
        command = self.listed_rule_command("1")
        one_word = command.replace(PLACEHOLDER, ACCEPTED_WORD, 1).replace(f" {PLACEHOLDER}", "", 1)

        refused = self.rule(one_word, "1")

        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("2 finding ask(s) are open but 1 outcome(s) were given", refused.stderr)
        self.assertEqual(self.outcome_rows(), [])
        self.listed_rule_command("1")


if __name__ == "__main__":
    unittest.main()
