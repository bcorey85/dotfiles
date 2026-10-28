"""Checks that every toolkit metrics writer obeys the metrics switch
(CLAUDE_TOOLKIT_TELEMETRY=1).

For each writer: with the switch absent it writes nothing and exits 0 (log-escape prints one line); with the
switch present it writes. log-review-finding's default `ledger write` happens with the switch off too; only an
`out=` redirect obeys the switch.

Every case copies the writer and its helpers into a temp layout (claude/scripts, claude/skills/review) and
runs it with HOME set to a temp dir, so no row reaches the real logs.

Script locations: TELEMETRY_SWITCH_DRAFT_DIR names one flat directory that holds every file under its final
name (the draft directory). Unset, the files under claude/.claude in this tree are used.
"""
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from typing import ClassVar

import toolkit_paths

REAL_CLAUDE = toolkit_paths.CLAUDE_DIR
DRAFT_DIR = os.environ.get("TELEMETRY_SWITCH_DRAFT_DIR")
RECEIPT_SKILL = pathlib.Path(
    os.environ.get("BRANCH_RECAP_SKILL") or REAL_CLAUDE / "skills" / "branch-recap" / "SKILL.md"
)
CALIBRATE_SKILL = pathlib.Path(
    os.environ.get("CALIBRATE_SKILL") or REAL_CLAUDE / "skills" / "calibrate" / "SKILL.md"
)
if DRAFT_DIR and not os.environ.get("BRANCH_RECAP_SKILL"):
    RECEIPT_SKILL = pathlib.Path(DRAFT_DIR) / "branch-recap-SKILL.md"

SCRIPT_FOLDERS = {"telemetry_enabled.sh": "telemetry", "telemetry_enabled.py": "telemetry", "hook_input.py": "lib",
                  "log_skill_use.py": "telemetry", "test_edit_telemetry.py": "telemetry",
                  "log-escape": "telemetry", "log-scan": "telemetry", "log-spec-run": "telemetry",
                  "coder_gate.py": "code", "script_utils.py": "lib", "_kv.sh": "lib", "_ledger.sh": "lib",
                  "ledger-write": "telemetry", "shell_command.py": "lib", "makefile_text.py": "lib"}
SCRIPTS = list(SCRIPT_FOLDERS)
REVIEW = ["log-review-metrics", "log-perf-finding", "log-review-finding", "review-scope"]
# hook_input.py is not part of this change: it always comes from the tree's copy.
INSTALLED_ONLY = {"hook_input.py"}

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

SKILL_POST = {"hook_event_name": "PostToolUse", "tool_name": "Skill", "tool_input": {"skill": "review"}}
SKILL_PROMPT = {"hook_event_name": "UserPromptSubmit", "prompt": "/review now"}
TEST_EDIT = {"hook_event_name": "PreToolUse", "tool_name": "Edit",
             "tool_input": {"file_path": "/work/repo/tests/test_x.py", "new_string": "assert x == 1"}}
CODER_BASH = {"hook_event_name": "PreToolUse", "agent_type": "coder", "cwd": "/work/repo",
              "tool_input": {"command": "npm test"}}


# The two edits the install makes to the branch-base review-scope (see INSTALL.md): define script_dir, and gate the
# caller= line on the helper run as a command.
REVIEW_SCOPE_SWITCH_LINES = [
    ('helper_dir=$(dirname -- "${BASH_SOURCE[0]}")\n'
     'source "$helper_dir/../../scripts/telemetry_enabled.sh" 2>/dev/null || telemetry_enabled() { return 1; }\n',
     'script_dir=$(dirname -- "${BASH_SOURCE[0]}")\n'),
    ('if [ -n "$caller" ] && telemetry_enabled; then',
     'if [ -n "$caller" ] && "$script_dir/../../scripts/telemetry_enabled.sh" 2>/dev/null; then'),
]


# Stands in for the `ledger` binary on PATH: records each `ledger write` call (its arguments and the row on stdin)
# as one JSON line in $LEDGER_STUB_CALLS, so a test sees what the real ledger-write script sent.
LEDGER_STUB = """#!{python}
import json, os, sys
with open(os.environ["LEDGER_STUB_CALLS"], "a") as calls:
    calls.write(json.dumps({{"args": sys.argv[1:], "row": json.loads(sys.stdin.read())}}) + "\\n")
"""


def source_file(name, subdir):
    if DRAFT_DIR and name not in INSTALLED_ONLY:
        return pathlib.Path(DRAFT_DIR) / name
    return REAL_CLAUDE / subdir / name


class SwitchTest(unittest.TestCase):
    def script_path(self, name):
        return self.scripts / SCRIPT_FOLDERS[name] / name

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name).resolve()
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.scripts = self.root / "claude" / "scripts"
        self.review = self.root / "claude" / "skills" / "review"
        self.scripts.mkdir(parents=True)
        self.review.mkdir(parents=True)
        for name in SCRIPTS:
            target = self.script_path(name)
            target.parent.mkdir(exist_ok=True)
            shutil.copy2(source_file(name, "scripts/" + SCRIPT_FOLDERS[name]), target)
        for name in REVIEW:
            shutil.copy2(source_file(name, "skills/review"), self.review / name)
        if DRAFT_DIR:
            self.add_review_scope_switch_lines()
        self.work = self.root / "work"
        self.work.mkdir()
        self.switch = self.home / ".claude" / "toolkit-telemetry"
        self.switch_is_on = False
        self.stub_bin = self.root / "bin"
        self.stub_bin.mkdir()
        self.ledger_calls_file = self.root / "ledger-calls.jsonl"
        stub_path = self.stub_bin / "ledger"
        stub_path.write_text(LEDGER_STUB.format(python=sys.executable))
        stub_path.chmod(0o755)

    def add_review_scope_switch_lines(self):
        """The draft review-scope predates the switch helper's command form. The install adds the switch lines to
        the branch-base review-scope instead; this applies those same lines to the temp copy."""
        scope_path = self.review / "review-scope"
        scope_text = scope_path.read_text()
        for old_text, new_text in REVIEW_SCOPE_SWITCH_LINES:
            self.assertEqual(scope_text.count(old_text), 1, old_text)
            scope_text = scope_text.replace(old_text, new_text)
        scope_path.write_text(scope_text)

    def turn(self, state):
        self.switch_is_on = state == "on"

    def leave_old_switch_file(self, present):
        # The file ~/.claude/toolkit-telemetry no longer decides anything; cases leave it behind to prove that.
        if present:
            self.switch.touch()
        else:
            self.switch.unlink(missing_ok=True)

    def environment(self, extra=None):
        environment = {key: value for key, value in os.environ.items()
                       if not key.endswith("_FILE")
                       and key not in ("CLAUDE_PROJECT_DIR", "CLAUDE_SKIP_HOOKS", "CLAUDE_TOOLKIT_TELEMETRY")}
        environment.update(GIT_ENV)
        environment.update(HOME=str(self.home), TMPDIR=str(self.root), LEDGER_STUB_CALLS=str(self.ledger_calls_file),
                           PATH=str(self.stub_bin) + os.pathsep + environment.get("PATH", ""))
        if self.switch_is_on:
            environment["CLAUDE_TOOLKIT_TELEMETRY"] = "1"
        environment.update(extra or {})
        return environment

    def run_command(self, command, stdin=None, cwd=None, extra=None):
        return subprocess.run(command, input=stdin, capture_output=True, text=True, cwd=str(cwd or self.work),
                              env=self.environment(extra))

    def home_file(self, name):
        return self.home / ".claude" / name

    def lines(self, name):
        path = self.home_file(name)
        return path.read_text().splitlines() if path.exists() else []

    def ledger_calls(self):
        """Every `ledger write` call the stub has recorded, oldest first."""
        if not self.ledger_calls_file.exists():
            return []
        return [json.loads(line) for line in self.ledger_calls_file.read_text().splitlines()]

    def assert_ledger_switch(self, row_type, run, quiet=True):
        """run() invokes the writer once. Off: exit 0, no output (unless quiet is False), no `ledger write` call and
        no jsonl file. On: exit 0 and exactly one `ledger write <row_type>` call. Returns the finished run and the
        call's row."""
        self.turn("off")
        finished = run()
        self.assertEqual(finished.returncode, 0, finished.stderr)
        if quiet:
            self.assertEqual((finished.stdout, finished.stderr), ("", ""))
        self.assertEqual(self.ledger_calls(), [], "ledger written while the switch was absent")
        self.assertEqual(list((self.home / ".claude").glob("*.jsonl")), [])
        self.turn("on")
        finished = run()
        self.assertEqual(finished.returncode, 0, finished.stderr)
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1, "ledger not written while the switch was present")
        self.assertEqual(calls[0]["args"][:2], ["write", row_type])
        self.assertEqual(list((self.home / ".claude").glob("*.jsonl")), [])
        return finished, calls[0]["row"]

    def assert_switch(self, name, run, quiet=True):
        """run() invokes the writer once. Off: name is not created, exit 0, no output. On: name gets a row."""
        self.turn("off")
        finished = run()
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertFalse(self.home_file(name).exists(), name + " written while the switch was absent")
        if quiet:
            self.assertEqual((finished.stdout, finished.stderr), ("", ""))
        self.turn("on")
        finished = run()
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(len(self.lines(name)), 1, name + " not written while the switch was present")
        return finished

    def test_four_switch_cases_for_every_writer_language(self):
        """The helper decides for bash and Python writers alike: var=1 logs, var unset does not even with the old
        switch file present, and var=0 does not."""
        cases = [("var=1, no file", {"CLAUDE_TOOLKIT_TELEMETRY": "1"}, False, True),
                 ("var unset, file present", {}, True, False),
                 ("neither", {}, False, False),
                 ("var=0, no file", {"CLAUDE_TOOLKIT_TELEMETRY": "0"}, False, False)]
        scan_arguments = ["repo=r", "scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"]
        self.turn("off")
        for case_name, extra, file_present, expect_row in cases:
            with self.subTest(case=case_name, writer="log-scan"):
                self.leave_old_switch_file(file_present)
                self.ledger_calls_file.unlink(missing_ok=True)
                finished = self.run_command(["bash", str(self.script_path("log-scan")), *scan_arguments], extra=extra)
                self.assertEqual(finished.returncode, 0, finished.stderr)
                self.assertEqual(len(self.ledger_calls()), 1 if expect_row else 0)

    def test_helper_four_cases_as_command_and_import(self):
        """The two helper forms agree on the four cases."""
        cases = [({"CLAUDE_TOOLKIT_TELEMETRY": "1"}, False, 0), ({}, True, 1), ({}, False, 1),
                 ({"CLAUDE_TOOLKIT_TELEMETRY": "0"}, False, 1)]
        self.turn("off")
        for extra, with_file, expected_code in cases:
            with self.subTest(extra=extra, with_file=with_file):
                self.leave_old_switch_file(with_file)
                shell_run = self.run_command(["bash", str(self.script_path("telemetry_enabled.sh"))], extra=extra)
                self.assertEqual(shell_run.returncode, expected_code, shell_run.stderr)
                python_run = self.run_command(
                    [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]);"
                     " from telemetry_enabled import telemetry_enabled; sys.exit(0 if telemetry_enabled() else 1)",
                     str(self.scripts / "telemetry")], extra=extra)
                self.assertEqual(python_run.returncode, expected_code, python_run.stderr)

    def hook(self, script, payload):
        command = (
            [sys.executable, str(self.script_path(script))]
            if script.endswith(".py")
            else ["bash", str(self.script_path(script))]
        )
        return lambda: self.run_command(command, json.dumps(payload))

    # ---- hooks

    def test_skill_use_py_model(self):
        self.assert_switch("skill-usage.jsonl", self.hook("log_skill_use.py", SKILL_POST))

    def test_skill_use_py_prompt(self):
        self.assert_switch("skill-usage.jsonl", self.hook("log_skill_use.py", SKILL_PROMPT))

    def test_test_edit_telemetry_py(self):
        self.assert_switch("test-edit-telemetry.jsonl", self.hook("test_edit_telemetry.py", TEST_EDIT))

    def test_coder_gate_whole_package_deny_still_denies_when_off(self):
        command = [sys.executable, str(self.script_path("coder_gate.py")), "bash-hook"]
        decisions = []

        def run():
            finished = self.run_command(command, json.dumps(CODER_BASH))
            decisions.append(json.loads(finished.stdout)["hookSpecificOutput"]["permissionDecision"])
            return finished

        _, row = self.assert_ledger_switch("coder_gate", run, quiet=False)
        self.assertEqual(decisions, ["deny", "deny"])
        self.assertEqual(row["result"], "whole-package-deny")

    def test_coder_gate_handback_log(self):
        repo = self.work / "repo"
        repo.mkdir()
        self.run_command(["git", "init", "-q"], cwd=repo)
        self.run_command(
            ["git", "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo
        )
        gate = [sys.executable, str(self.script_path("coder_gate.py"))]
        set_gate = self.run_command([*gate, "set", "true"], cwd=repo)
        self.assertEqual(set_gate.returncode, 0, set_gate.stderr)
        handback = {"hook_event_name": "PreToolUse", "agent_type": "coder", "agent_id": "a1", "cwd": str(repo),
                    "tool_input": {"message": "done"}}

        def run():
            finished = self.run_command([*gate, "hook"], json.dumps(handback), cwd=repo)
            self.assertIn("HAND-BACK GATE: pass", finished.stdout)
            return finished

        _, row = self.assert_ledger_switch("coder_gate", run, quiet=False)
        self.assertEqual(row["result"], "pass")

    # ---- scripts

    def test_log_review_metrics_default_file(self):
        script = str(self.review / "log-review-metrics")
        _, row = self.assert_ledger_switch(
            "review_metrics", lambda: self.run_command([script, "iter=1", "result=PASS"])
        )
        self.assertEqual(row, {"iter": "1", "result": "PASS"})

    def test_log_review_metrics_has_no_second_draft_route(self):
        script = str(self.review / "log-review-metrics")
        self.turn("on")
        finished = self.run_command([script, "iter=1", "second_draft=1"])
        self.assertEqual(finished.returncode, 0, finished.stderr)
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["args"][:2], ["write", "review_metrics"])
        self.assertEqual(list((self.home / ".claude").glob("*.jsonl")), [])

    def install_skill_helpers(self):
        """Puts the switch helper and ledger-write where a skill's bash block finds them under $HOME/.claude."""
        for name in ("telemetry_enabled.sh", "ledger-write", "_kv.sh", "_ledger.sh"):
            installed = self.home / ".claude" / "scripts" / SCRIPT_FOLDERS[name] / name
            installed.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.script_path(name), installed)

    def calibrate_log_block(self):
        text = CALIBRATE_SKILL.read_text()
        found = re.search(r"## Step 6: Log\n\n```bash\n(.*?)```", text, re.S)
        self.assertIsNotNone(found, "log block not found in calibrate SKILL.md")
        block = found.group(1)
        for placeholder, value in (("<sonnet|deep>", "sonnet"), ("<defect class>", "bug"),
                                   ("<caught|missed>", "caught"), ("<n>", "0")):
            block = block.replace(placeholder, value)
        return block

    def test_calibrate_log_step_writes_review_calibration(self):
        self.install_skill_helpers()
        block = self.calibrate_log_block()
        _, row = self.assert_ledger_switch("review_calibration",
                                           lambda: self.run_command(["bash", "-c", block]))
        self.assertEqual(row, {"reviewer": "sonnet", "class": "bug", "result": "caught", "other_findings": 0})

    def test_log_perf_finding(self):
        script = str(self.review / "log-perf-finding")
        args = [script, "repo=r", "file_line=a.py:1", "finding=slow", "principle=n-plus-one"]
        self.turn("off")
        finished = self.run_command(args)
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))
        self.assertFalse(self.home_file("backend-perf-findings.md").exists())
        self.turn("on")
        finished = self.run_command(args)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        text = self.home_file("backend-perf-findings.md").read_text()
        self.assertTrue(text.startswith("# Backend Perf"))
        self.assertIn("`a.py:1` — slow", text)

    def test_log_perf_finding_validation_still_runs_when_off(self):
        self.turn("off")
        finished = self.run_command([str(self.review / "log-perf-finding"), "repo=r"])
        self.assertEqual(finished.returncode, 1)
        self.assertIn("missing required arg", finished.stderr)

    ESCAPE_ARGS: ClassVar[list[str]] = [
        "gate_missed=code-reviewer",
        "stage_found=human-pr",
        "severity=high",
        "class=bug",
        "guard=none",
        "desc=a bug",
    ]

    def test_log_escape_prints_one_line_when_off(self):
        script = str(self.script_path("log-escape"))
        args = [script, *self.ESCAPE_ARGS]
        self.turn("off")
        finished = self.run_command(args)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout, "not logged: toolkit telemetry is off\n")
        self.assertEqual(self.ledger_calls(), [])
        self.turn("on")
        finished = self.run_command(args)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout, "")
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["args"][:2], ["write", "review_escape"])
        self.assertFalse(self.home_file(toolkit_paths.local_stream_file("review-escapes")).exists())

    def test_log_escape_validation_still_runs_when_off(self):
        self.turn("off")
        script = str(self.script_path("log-escape"))
        finished = self.run_command([script, "class=nonsense"])
        self.assertEqual(finished.returncode, 1)
        self.assertIn("refusing to log", finished.stderr)
        finished = self.run_command([script, "class=nonsense", "guard=none"])
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout, "not logged: toolkit telemetry is off\n")

    # ---- --check: the same validation, no write, switch ignored

    def finding_check_args(self):
        return [str(self.review / "log-review-finding"), "kind=finding", "gate=code-reviewer", "class=bug",
                "disposition=fix", "desc=a bug"]

    def escape_check_args(self):
        return [str(self.script_path("log-escape")), *self.ESCAPE_ARGS]

    def checkers(self):
        """(label, argument list) for each logger that accepts --check, with arguments a real call accepts."""
        return [("log-review-finding", self.finding_check_args()), ("log-escape", self.escape_check_args())]

    def with_check(self, args):
        return [args[0], "--check", *args[1:]]

    def invalid(self, args):
        """The same arguments with one value the logger itself refuses: a missing guard for log-escape, a kind
        outside run|finding for log-review-finding (both pass an unknown class on to `ledger write`, which stores
        it as other)."""
        return [argument.replace("kind=finding", "kind=nonsense") for argument in args if argument != "guard=none"]

    def test_check_valid_arguments_exit_zero_and_write_nothing_with_switch_on(self):
        self.turn("on")
        for label, args in self.checkers():
            with self.subTest(logger=label):
                finished = self.run_command(self.with_check(args))
                self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))
                self.assertEqual(list((self.home / ".claude").glob("*.jsonl")), [])
                self.assertEqual(self.ledger_calls(), [])

    def test_check_valid_arguments_exit_zero_with_switch_off(self):
        self.turn("off")
        for label, args in self.checkers():
            with self.subTest(logger=label):
                finished = self.run_command(self.with_check(args))
                self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def test_check_invalid_arguments_fail_with_the_text_of_a_real_call(self):
        for state in ("on", "off"):
            self.turn(state)
            for label, args in self.checkers():
                with self.subTest(logger=label, switch=state):
                    bad_args = self.invalid(args)
                    real_call = self.run_command(bad_args)
                    check_call = self.run_command(self.with_check(bad_args))
                    self.assertNotEqual(real_call.returncode, 0)
                    self.assertIn("refusing to log", real_call.stderr)
                    self.assertEqual(check_call.returncode, real_call.returncode)
                    self.assertEqual(check_call.stderr, real_call.stderr)
                    self.assertEqual(check_call.stdout, real_call.stdout)

    def test_review_finding_passes_an_unknown_class_to_the_ledger_as_given(self):
        """The class vocabulary lives in `ledger write`, so log-review-finding exits 0 and sends the value as given;
        --check refuses nothing for it either."""
        self.turn("on")
        bad_args = self.finding_check_args()
        bad_args[bad_args.index("class=bug")] = "class=nonsense"
        check_call = self.run_command(self.with_check(bad_args))
        self.assertEqual((check_call.returncode, check_call.stdout, check_call.stderr), (0, "", ""))
        real_call = self.run_command(bad_args)
        self.assertEqual(real_call.returncode, 0, real_call.stderr)
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["row"]["class"], "nonsense")

    def test_review_finding_refuses_a_missing_kind_a_missing_gate_and_a_value_with_a_space(self):
        """Malformed input (no kind, no gate, a space in a value) exits nonzero with the switch on or off and sends
        nothing to the ledger."""
        finding = str(self.review / "log-review-finding")
        no_kind = [finding, "gate=code-reviewer", "class=bug", "disposition=fix"]
        no_gate = [finding, "kind=finding", "class=bug", "disposition=fix"]
        spaced_value = [finding, "kind=finding", "gate=code-reviewer", "class=bug", "disposition=fix",
                       "repo=two words"]
        for state in ("on", "off"):
            self.turn(state)
            for label, args, message in (("no kind", no_kind, "kind=run|finding is required"),
                                         ("no gate", no_gate, "gate=<agent name> is required"),
                                         ("space in a value", spaced_value, "contains a space")):
                with self.subTest(case=label, switch=state):
                    finished = self.run_command(args)
                    self.assertEqual(finished.returncode, 1)
                    self.assertIn(message, finished.stderr)
                    self.assertEqual(self.ledger_calls(), [])

    def test_check_writes_nothing_even_with_the_switch_on(self):
        self.turn("on")
        redirected = self.root / "redirected.jsonl"
        for label, args in self.checkers():
            with self.subTest(logger=label):
                self.run_command(self.with_check(args), extra={"REVIEW_FINDINGS_FILE": str(redirected),
                                                               "REVIEW_ESCAPES_FILE": str(redirected)})
                self.assertFalse(redirected.exists())
                self.assertEqual(list((self.home / ".claude").glob("*.jsonl")), [])
                self.assertEqual(self.ledger_calls(), [])
        self.run_command(self.with_check([*self.finding_check_args(), f"out={redirected}"]))
        self.assertFalse(redirected.exists())
        self.assertEqual(self.ledger_calls(), [])

    def test_check_flag_after_the_first_argument_is_not_the_check_mode(self):
        self.turn("on")
        args = self.escape_check_args()
        finished = self.run_command([args[0], args[1], "--check", *args[2:]])
        self.assertEqual(finished.returncode, 0)
        self.assertIn("skipping malformed arg", finished.stderr)
        self.assertEqual(len(self.ledger_calls()), 1)

    def test_log_scan(self):
        script = str(self.script_path("log-scan"))
        args = [script, "repo=r", "scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"]
        _, row = self.assert_ledger_switch("scan_run", lambda: self.run_command(args))
        self.assertEqual(row["scan"], "prohibition")

    def test_log_spec_run(self):
        script = str(self.script_path("log-spec-run"))
        args = [script, "slug=my-plan", "verdict=finalized", "criteria=3"]
        finished, row = self.assert_ledger_switch("spec_run", lambda: self.run_command(args))
        self.assertEqual(row, {"verdict": "finalized", "criteria": "3"})
        self.assertEqual(finished.stdout, "")

    # ---- review-scope and log-review-finding

    def test_review_scope_skill_usage_line_only(self):
        script = str(self.review / "review-scope")
        self.turn("off")
        finished = self.run_command([script, "caller=review"])
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("ROOT=", finished.stdout)
        self.assertEqual(self.ledger_calls(), [])
        self.assertFalse(self.home_file(toolkit_paths.local_stream_file("skill-usage")).exists())
        self.turn("on")
        finished = self.run_command([script, "caller=review"])
        self.assertIn("ROOT=", finished.stdout)
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["args"][:2], ["write", "review_scope"])
        self.assertEqual(calls[0]["row"], {"skill": "review-loop", "caller": "review"})
        self.assertFalse(self.home_file(toolkit_paths.local_stream_file("skill-usage")).exists())

    def finding_args(self, *extra):
        return [str(self.review / "log-review-finding"), "kind=run", "gate=code-reviewer", "n_findings=0", *extra]

    def assert_run_row_sent(self, finished):
        """The one recorded call is the run row for finding_args(), and stdout names the id the row carries."""
        calls = self.ledger_calls()
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["args"][:2], ["write", "review_run"])
        row = calls[0]["row"]
        self.assertEqual((row["gate"], row["n_findings"]), ("code-reviewer", "0"))
        self.assertEqual(finished.stdout, f"run_id={row['run_id']}\n")

    def test_review_findings_default_path_is_kept_when_off(self):
        self.turn("off")
        finished = self.run_command(self.finding_args())
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assert_run_row_sent(finished)
        self.assertEqual(list((self.home / ".claude").glob("*.jsonl")), [])

    def test_review_findings_env_file_is_ignored_and_row_still_sent_when_off(self):
        target = self.root / "queue.jsonl"
        self.turn("off")
        finished = self.run_command(self.finding_args(), extra={"REVIEW_FINDINGS_FILE": str(target)})
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assert_run_row_sent(finished)
        self.assertFalse(target.exists())

    def test_review_findings_out_redirect_obeys_switch(self):
        target = self.root / "redirect.jsonl"
        finished, row = self.assert_ledger_switch(
            "review_run", lambda: self.run_command(self.finding_args(f"out={target}")), quiet=False)
        self.assertEqual(finished.stdout, f"run_id={row['run_id']}\n")
        self.assertFalse(target.exists())
        self.assertEqual(self.lines(toolkit_paths.local_stream_file("review-findings")), [])

    # ---- branch-recap receipt line

    def receipt_block(self):
        text = RECEIPT_SKILL.read_text()
        found = re.search(r"Persist \(non-blocking[^\n]*\n\n```bash\n(.*?)```", text, re.S)
        self.assertIsNotNone(found, "receipt block not found in branch-recap SKILL.md")
        block = found.group(1)
        for placeholder, value in (("<clean|culled|no_receipt>", "clean"), ("<n culled>", "0"),
                                   ("<n coverage lost>", "0"), ("<unstaged count>", "0"),
                                   ("<changed-file count>", "0")):
            block = block.replace(placeholder, value)
        return block

    def test_branch_recap_receipt(self):
        repo = self.work / "repo"
        repo.mkdir()
        self.run_command(["git", "init", "-q"], cwd=repo)
        self.run_command(
            ["git", "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo
        )
        self.install_skill_helpers()
        block = self.receipt_block()
        _, row = self.assert_ledger_switch("branch_recap",
                                           lambda: self.run_command(["bash", "-c", block], cwd=repo))
        self.assertEqual({key: row[key] for key in ("test_audit", "culled", "coverage_lost", "residue", "files")},
                         {"test_audit": "clean", "culled": 0, "coverage_lost": 0, "residue": 0, "files": 0})
        self.assertTrue(row["branch_key"])

    # ---- helpers

    def test_helper_bash(self):
        helper = str(self.script_path("telemetry_enabled.sh"))
        self.turn("off")
        self.assertEqual(self.run_command([helper]).returncode, 1)
        self.turn("on")
        self.assertEqual(self.run_command([helper]).returncode, 0)

    def test_helper_python(self):
        command = [
            sys.executable,
            "-c",
            "import telemetry_enabled, sys; sys.exit(0 if telemetry_enabled.telemetry_enabled() else 1)",
        ]
        self.turn("off")
        self.assertEqual(self.run_command(command, extra={"PYTHONPATH": str(self.scripts / "telemetry")}).returncode, 1)
        self.turn("on")
        self.assertEqual(self.run_command(command, extra={"PYTHONPATH": str(self.scripts / "telemetry")}).returncode, 0)

    def test_missing_helper_keeps_bash_writer_off(self):
        (self.script_path("telemetry_enabled.sh")).unlink()
        self.turn("on")
        scan_arguments = ["repo=r", "scan=other", "stage=manual", "exit=2"]
        finished = self.run_command([str(self.script_path("log-scan")), *scan_arguments])
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertFalse(self.home_file(toolkit_paths.local_stream_file("scan-runs")).exists())
        self.assertEqual(self.ledger_calls(), [])

    def test_missing_helper_keeps_log_escape_off(self):
        (self.script_path("telemetry_enabled.sh")).unlink()
        self.turn("on")
        finished = self.run_command([str(self.script_path("log-escape")), *self.ESCAPE_ARGS])
        self.assertEqual((finished.returncode, finished.stdout), (0, "not logged: toolkit telemetry is off\n"))
        self.assertFalse(self.home_file(toolkit_paths.local_stream_file("review-escapes")).exists())
        self.assertEqual(self.ledger_calls(), [])

    def test_missing_python_helper_keeps_logging_hooks_off(self):
        (self.script_path("telemetry_enabled.py")).unlink()
        self.turn("on")
        cases = [("log_skill_use.py", SKILL_POST, "skill-usage.jsonl"),
                 ("test_edit_telemetry.py", TEST_EDIT, "test-edit-telemetry.jsonl")]
        for script, payload, log_name in cases:
            with self.subTest(hook=script):
                finished = self.hook(script, payload)()
                self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))
                self.assertFalse(self.home_file(log_name).exists())

    def test_missing_python_helper_coder_gate_still_denies_and_logs_nothing(self):
        (self.script_path("telemetry_enabled.py")).unlink()
        self.turn("on")
        command = [sys.executable, str(self.script_path("coder_gate.py")), "bash-hook"]
        finished = self.run_command(command, json.dumps(CODER_BASH))
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(self.ledger_calls(), [])

    def test_missing_python_helper_coder_gate_handback_still_runs_and_logs_nothing(self):
        (self.script_path("telemetry_enabled.py")).unlink()
        self.turn("on")
        repo = self.work / "repo"
        repo.mkdir()
        self.run_command(["git", "init", "-q"], cwd=repo)
        self.run_command(
            ["git", "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo
        )
        gate = [sys.executable, str(self.script_path("coder_gate.py"))]
        self.assertEqual(self.run_command([*gate, "set", "true"], cwd=repo).returncode, 0)
        handback = {"hook_event_name": "PreToolUse", "agent_type": "coder", "agent_id": "a1", "cwd": str(repo),
                    "tool_input": {"message": "done"}}
        finished = self.run_command([*gate, "hook"], json.dumps(handback), cwd=repo)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("HAND-BACK GATE: pass", finished.stdout)
        self.assertEqual(self.ledger_calls(), [])


if __name__ == "__main__":
    unittest.main()
