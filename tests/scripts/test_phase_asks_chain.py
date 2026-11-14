"""The phase-asks chain from end to end, each step a real process: code_review_start.py runs the review loop's own
entry (which builds the packet and writes the hand-back rows), code_wait.py opens the asks, the commit gate hook
denies the commit, the command the denial prints rules on them, and the gate then passes.

Only the loop's walk is a stand-in: `run_loop` returns a fixed converged outcome with two finding asks, so no
`claude -p` call is made. The test writes no store row itself."""
import json
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
DENIED_PART = "2 ask(s) that you have not ruled on"
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

    def environment(self, telemetry):
        return {"PATH": self.ledger_env["PATH"], "FAKE_LEDGER_ROWS": self.ledger_env["FAKE_LEDGER_ROWS"],
                "HOME": str(self.home), "TMPDIR": str(self.tmp), "CLAUDE_CODE_SESSION_ID": SESSION,
                "REVIEW_FIX_CLAUDE_DIR": str(toolkit_paths.CLAUDE_DIR), "CLAUDE_TOOLKIT_TELEMETRY": telemetry,
                "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null",
                "GIT_CONFIG_SYSTEM": "/dev/null"}

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.repo), *args], capture_output=True, text=True, check=True,
                              env=self.environment("0"))

    def run_step(self, argv, telemetry):
        return subprocess.run(argv, cwd=self.repo, capture_output=True, text=True, env=self.environment(telemetry))

    def fire_gate(self, payload, telemetry):
        gate = self.scripts / "review" / "review_commit_gate.py"
        event = {"session_id": SESSION, "cwd": str(self.repo), **payload}
        return subprocess.run([sys.executable, str(gate)], input=json.dumps(event), capture_output=True, text=True,
                              cwd=self.repo, env=self.environment(telemetry))

    def commit_attempt(self, telemetry):
        return self.fire_gate({"hook_event_name": "PreToolUse", "tool_name": "Bash",
                               "tool_input": {"command": "git commit -a -m x"}}, telemetry)

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
        dispatched = self.fire_gate({"hook_event_name": "PostToolUse", "tool_name": "Agent",
                                     "tool_input": {"subagent_type": "coder"}, "tool_response": {"agentId": "a0"}},
                                    telemetry)
        self.assertEqual((dispatched.returncode, dispatched.stdout), (0, ""), dispatched.stderr)
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

    def denied_rule_command(self, telemetry):
        """The rule command the gate's denial of a commit prints, placeholders and all."""
        finished = self.commit_attempt(telemetry)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny")
        reason = decision["permissionDecisionReason"]
        self.assertIn(DENIED_PART, reason)
        self.assertIn("Should an empty list count as none?", reason)
        self.assertIn("Should the cap be 3?", reason)
        command = reason.partition("rule on them first, with `")[2].partition("`")[0]
        self.assertEqual(command.count(PLACEHOLDER), 2, reason)
        return command

    def rule(self, command, telemetry):
        return subprocess.run(["bash", "-c", command], cwd=self.tmp, capture_output=True, text=True,
                              env=self.environment(telemetry))

    def outcome_rows(self):
        return [row for row in fake_ledger.recorded_rows(self.ledger_env) if "ask_outcome" in row]

    def assert_commit_passes(self, telemetry):
        finished = self.commit_attempt(telemetry)
        self.assertEqual((finished.returncode, finished.stdout), (0, ""), finished.stderr)

    def test_the_commit_is_denied_until_the_printed_rule_command_rules_on_both_asks_and_each_outcome_is_logged(self):
        waited = self.review_the_phase("1")
        self.assertIn('"status": "converged"', waited)
        self.assertIn("2 finding ask(s) await your ruling", waited)

        command = self.denied_rule_command("1")
        ruling = command.replace(PLACEHOLDER, ACCEPTED_WORD, 1).replace(PLACEHOLDER, REJECTED_WORD, 1)
        ruled = self.rule(ruling, "1")

        self.assertEqual(ruled.returncode, 0, ruled.stderr)
        self.assertIn("Ruled 2 ask(s)", ruled.stdout)
        self.assert_commit_passes("1")
        rows = self.outcome_rows()
        self.assertEqual([(row["finding_id"], row["ask_outcome"], row["ask_decided_by"]) for row in rows],
                         [(FIRST_ID, "accepted", "session"), (SECOND_ID, "rejected", "session")])
        self.assertEqual({(row["lane"], row["scope"], row["phase"]) for row in rows}, {("code", "phase", "1")})

    def test_with_the_telemetry_switch_off_the_ruling_stands_and_the_commit_passes(self):
        """log-review-finding's `ledger write` ignores the switch (test_telemetry_switch.py), so the outcome rows
        land with it off too."""
        self.review_the_phase("0")
        command = self.denied_rule_command("0")
        ruling = command.replace(PLACEHOLDER, ACCEPTED_WORD, 1).replace(PLACEHOLDER, REJECTED_WORD, 1)

        ruled = self.rule(ruling, "0")

        self.assertEqual(ruled.returncode, 0, ruled.stderr)
        self.assert_commit_passes("0")
        self.assertEqual([row["finding_id"] for row in self.outcome_rows()], [FIRST_ID, SECOND_ID])

    def test_with_no_ledger_the_ruling_stands_and_the_commit_passes(self):
        self.review_the_phase("1")
        command = self.denied_rule_command("1")
        ruling = command.replace(PLACEHOLDER, ACCEPTED_WORD, 1).replace(PLACEHOLDER, REJECTED_WORD, 1)
        failing_ledger = {"FAKE_LEDGER_WRITE_EXIT": "2"}

        ruled = subprocess.run(["bash", "-c", ruling], cwd=self.tmp, capture_output=True, text=True,
                               env={**self.environment("1"), **failing_ledger})

        self.assertEqual(ruled.returncode, 0, ruled.stderr)
        self.assertEqual(self.outcome_rows(), [])
        self.assert_commit_passes("1")

    def test_a_ruling_with_one_outcome_for_two_asks_is_refused_and_the_commit_stays_denied(self):
        self.review_the_phase("1")
        command = self.denied_rule_command("1")
        one_word = command.replace(PLACEHOLDER, ACCEPTED_WORD, 1).replace(f" {PLACEHOLDER}", "", 1)

        refused = self.rule(one_word, "1")

        self.assertEqual(refused.returncode, 2, refused.stdout)
        self.assertIn("2 finding ask(s) are open but 1 outcome(s) were given", refused.stderr)
        self.assertEqual(self.outcome_rows(), [])
        self.denied_rule_command("1")


if __name__ == "__main__":
    unittest.main()
