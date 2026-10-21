"""Checks that every toolkit metrics writer obeys the metrics switch
(CLAUDE_TOOLKIT_TELEMETRY=1, or the file ~/.claude/toolkit-telemetry).

For each writer: with the switch absent it writes nothing and exits 0 (log-escape prints one line); with the
switch present it writes. The kept logs (review-findings.jsonl's default path) write either way.

Every case copies the writer and its helpers into a temp layout (claude/scripts, claude/skills/review) and
runs it with HOME set to a temp dir, so no row reaches the real logs.

Script locations: TELEMETRY_SWITCH_DRAFT_DIR names one flat directory that holds every file under its final
name (the draft directory). Unset, the installed files under ~/.claude are used.
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

REAL_CLAUDE = pathlib.Path.home() / ".claude"
DRAFT_DIR = os.environ.get("TELEMETRY_SWITCH_DRAFT_DIR")
RECEIPT_SKILL = pathlib.Path(os.environ.get("BRANCH_RECAP_SKILL") or REAL_CLAUDE / "skills" / "branch-recap" / "SKILL.md")
if DRAFT_DIR and not os.environ.get("BRANCH_RECAP_SKILL"):
    RECEIPT_SKILL = pathlib.Path(DRAFT_DIR) / "branch-recap-SKILL.md"

SCRIPTS = ["telemetry_enabled.sh", "telemetry_enabled.py", "hook_input.py", "repo-name", "log-agent-usage.py",
           "log-skill-use.py", "test-edit-telemetry.py", "log-escape", "log-scan", "log-spec-run", "coder-gate.py"]
REVIEW = ["log-review-metrics", "log-perf-finding", "log-review-finding", "review-scope"]
# hook_input.py and repo-name are not part of this change: they always come from the installed copy.
INSTALLED_ONLY = {"hook_input.py", "repo-name"}

GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}

HOOK_POST = {"hook_event_name": "PostToolUse", "tool_name": "Agent",
             "tool_input": {"subagent_type": "coder", "model": "sonnet", "description": "Fix it"},
             "tool_response": {"content": [{"type": "text", "text": "done"}], "totalTokens": 5}}
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


def source_file(name, subdir):
    if DRAFT_DIR and name not in INSTALLED_ONLY:
        return pathlib.Path(DRAFT_DIR) / name
    return REAL_CLAUDE / subdir / name


class SwitchTest(unittest.TestCase):
    def setUp(self):
        tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(tempDir.cleanup)
        self.root = pathlib.Path(tempDir.name).resolve()
        self.home = self.root / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.scripts = self.root / "claude" / "scripts"
        self.review = self.root / "claude" / "skills" / "review"
        self.scripts.mkdir(parents=True)
        self.review.mkdir(parents=True)
        for name in SCRIPTS:
            shutil.copy2(source_file(name, "scripts"), self.scripts / name)
        for name in REVIEW:
            shutil.copy2(source_file(name, "skills/review"), self.review / name)
        if DRAFT_DIR:
            self.add_review_scope_switch_lines()
        self.work = self.root / "work"
        self.work.mkdir()
        self.switch = self.home / ".claude" / "toolkit-telemetry"

    def add_review_scope_switch_lines(self):
        """The draft review-scope predates the switch helper's command form. The install adds the switch lines to
        the branch-base review-scope instead; this applies those same lines to the temp copy."""
        scopePath = self.review / "review-scope"
        scopeText = scopePath.read_text()
        for oldText, newText in REVIEW_SCOPE_SWITCH_LINES:
            self.assertEqual(scopeText.count(oldText), 1, oldText)
            scopeText = scopeText.replace(oldText, newText)
        scopePath.write_text(scopeText)

    def turn(self, state):
        if state == "on":
            self.switch.touch()
        else:
            self.switch.unlink(missing_ok=True)

    def environment(self, extra=None):
        environment = {key: value for key, value in os.environ.items()
                       if not key.endswith("_FILE")
                       and key not in ("CLAUDE_PROJECT_DIR", "CLAUDE_SKIP_HOOKS", "CLAUDE_TOOLKIT_TELEMETRY")}
        environment.update(GIT_ENV)
        environment.update(HOME=str(self.home), TMPDIR=str(self.root))
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
        """The helper decides for bash and Python writers alike: var=1 logs, var unset with the file logs, neither
        does not, and var=0 with no file does not."""
        cases = [("var=1, no file", {"CLAUDE_TOOLKIT_TELEMETRY": "1"}, "off", True),
                 ("var unset, file present", {}, "on", True),
                 ("neither", {}, "off", False),
                 ("var=0, no file", {"CLAUDE_TOOLKIT_TELEMETRY": "0"}, "off", False)]
        scanArguments = ["repo=r", "scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"]
        writers = [("agent-usage.jsonl", "log-agent-usage.py", HOOK_POST, []),
                   ("scan-runs.jsonl", "log-scan", None, scanArguments)]
        for caseName, extra, fileState, expectRow in cases:
            for logName, script, payload, arguments in writers:
                with self.subTest(case=caseName, writer=script):
                    self.turn(fileState)
                    self.home_file(logName).unlink(missing_ok=True)
                    interpreter = [sys.executable] if script.endswith(".py") else ["bash"]
                    finished = self.run_command([*interpreter, str(self.scripts / script), *arguments],
                                                json.dumps(payload) if payload else None, extra=extra)
                    self.assertEqual(finished.returncode, 0, finished.stderr)
                    self.assertEqual(len(self.lines(logName)), 1 if expectRow else 0)

    def test_helper_four_cases_as_command_and_import(self):
        """The two helper forms agree on the four cases."""
        cases = [({"CLAUDE_TOOLKIT_TELEMETRY": "1"}, False, 0), ({}, True, 0), ({}, False, 1),
                 ({"CLAUDE_TOOLKIT_TELEMETRY": "0"}, False, 1)]
        for extra, withFile, expectedCode in cases:
            with self.subTest(extra=extra, withFile=withFile):
                self.turn("on" if withFile else "off")
                shellRun = self.run_command(["bash", str(self.scripts / "telemetry_enabled.sh")], extra=extra)
                self.assertEqual(shellRun.returncode, expectedCode, shellRun.stderr)
                pythonRun = self.run_command(
                    [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]);"
                     " from telemetry_enabled import telemetry_enabled; sys.exit(0 if telemetry_enabled() else 1)",
                     str(self.scripts)], extra=extra)
                self.assertEqual(pythonRun.returncode, expectedCode, pythonRun.stderr)

    def hook(self, script, payload):
        command = [sys.executable, str(self.scripts / script)] if script.endswith(".py") else ["bash", str(self.scripts / script)]
        return lambda: self.run_command(command, json.dumps(payload))

    # ---- hooks

    def test_agent_usage_py(self):
        self.assert_switch("agent-usage.jsonl", self.hook("log-agent-usage.py", HOOK_POST))

    def test_skill_use_py_model(self):
        self.assert_switch("skill-usage.jsonl", self.hook("log-skill-use.py", SKILL_POST))

    def test_skill_use_py_prompt(self):
        self.assert_switch("skill-usage.jsonl", self.hook("log-skill-use.py", SKILL_PROMPT))

    def test_test_edit_telemetry_py(self):
        self.assert_switch("test-edit-telemetry.jsonl", self.hook("test-edit-telemetry.py", TEST_EDIT))

    def test_coder_gate_whole_package_deny_still_denies_when_off(self):
        command = [sys.executable, str(self.scripts / "coder-gate.py"), "bash-hook"]
        self.turn("off")
        finished = self.run_command(command, json.dumps(CODER_BASH))
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertFalse(self.home_file("coder-gate.jsonl").exists())
        self.turn("on")
        finished = self.run_command(command, json.dumps(CODER_BASH))
        self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(json.loads(self.lines("coder-gate.jsonl")[0])["result"], "whole-package-deny")

    def test_coder_gate_handback_log(self):
        repo = self.work / "repo"
        repo.mkdir()
        self.run_command(["git", "init", "-q"], cwd=repo)
        self.run_command(["git", "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo)
        gate = [sys.executable, str(self.scripts / "coder-gate.py")]
        setGate = self.run_command(gate + ["set", "true"], cwd=repo)
        self.assertEqual(setGate.returncode, 0, setGate.stderr)
        handback = {"hook_event_name": "PreToolUse", "agent_type": "coder", "agent_id": "a1", "cwd": str(repo),
                    "tool_input": {"message": "done"}}
        self.turn("off")
        finished = self.run_command(gate + ["hook"], json.dumps(handback), cwd=repo)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("HAND-BACK GATE: pass", finished.stdout)
        self.assertFalse(self.home_file("coder-gate.jsonl").exists())
        self.turn("on")
        finished = self.run_command(gate + ["hook"], json.dumps(handback), cwd=repo)
        self.assertIn("HAND-BACK GATE: pass", finished.stdout)
        self.assertEqual(json.loads(self.lines("coder-gate.jsonl")[0])["result"], "pass")

    # ---- scripts

    def test_log_review_metrics_default_file(self):
        script = str(self.review / "log-review-metrics")
        self.assert_switch("review-metrics.jsonl", lambda: self.run_command([script, "iter=1", "result=PASS"]))

    def test_log_review_metrics_second_draft_route(self):
        script = str(self.review / "log-review-metrics")
        self.assert_switch("second-draft.jsonl", lambda: self.run_command([script, "iter=1", "second_draft=1"]))

    def test_log_review_metrics_calibration_redirect(self):
        script = str(self.review / "log-review-metrics")
        target = self.home_file("review-calibration.jsonl")
        self.assert_switch("review-calibration.jsonl",
                           lambda: self.run_command([script, f"out={target}", "reviewer=sonnet", "result=caught"]))

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

    ESCAPE_ARGS = ["gate_missed=code-reviewer", "stage_found=human-pr", "severity=high", "class=bug",
                   "guard=none", "desc=a bug"]

    def test_log_escape_prints_one_line_when_off(self):
        script = str(self.scripts / "log-escape")
        args = [script, *self.ESCAPE_ARGS]
        self.turn("off")
        finished = self.run_command(args)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertFalse(self.home_file("review-escapes.jsonl").exists())
        self.assertEqual(finished.stdout, "not logged: toolkit telemetry is off\n")
        self.turn("on")
        finished = self.run_command(args)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertTrue(finished.stdout.startswith("logged"))
        self.assertEqual(len(self.lines("review-escapes.jsonl")), 1)

    def test_log_escape_validation_still_runs_when_off(self):
        self.turn("off")
        finished = self.run_command([str(self.scripts / "log-escape"), "class=nonsense", "guard=none"])
        self.assertEqual(finished.returncode, 1)
        self.assertIn("refusing to log", finished.stderr)

    # ---- --check: the same validation, no write, switch ignored

    def finding_check_args(self):
        return [str(self.review / "log-review-finding"), "kind=finding", "gate=code-reviewer", "class=bug",
                "disposition=fix", "desc=a bug"]

    def escape_check_args(self):
        return [str(self.scripts / "log-escape"), *self.ESCAPE_ARGS]

    def checkers(self):
        """(label, argument list) for each logger that accepts --check, with arguments a real call accepts."""
        return [("log-review-finding", self.finding_check_args()), ("log-escape", self.escape_check_args())]

    def with_check(self, args):
        return [args[0], "--check", *args[1:]]

    def invalid(self, args):
        """The same arguments with one value the logger's vocabulary refuses."""
        return [argument.replace("class=bug", "class=nonsense") for argument in args]

    def test_check_valid_arguments_exit_zero_and_write_nothing_with_switch_on(self):
        self.turn("on")
        for label, args in self.checkers():
            with self.subTest(logger=label):
                finished = self.run_command(self.with_check(args))
                self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))
                self.assertEqual(list((self.home / ".claude").glob("*.jsonl")), [])

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
                    badArgs = self.invalid(args)
                    realCall = self.run_command(badArgs)
                    checkCall = self.run_command(self.with_check(badArgs))
                    self.assertNotEqual(realCall.returncode, 0)
                    self.assertIn("refusing to log", realCall.stderr)
                    self.assertEqual(checkCall.returncode, realCall.returncode)
                    self.assertEqual(checkCall.stderr, realCall.stderr)
                    self.assertEqual(checkCall.stdout, realCall.stdout)

    def test_check_writes_nothing_even_with_the_switch_on(self):
        self.turn("on")
        redirected = self.root / "redirected.jsonl"
        for label, args in self.checkers():
            with self.subTest(logger=label):
                self.run_command(self.with_check(args), extra={"REVIEW_FINDINGS_FILE": str(redirected),
                                                               "REVIEW_ESCAPES_FILE": str(redirected)})
                self.assertFalse(redirected.exists())
                self.assertEqual(list((self.home / ".claude").glob("*.jsonl")), [])
        self.run_command(self.with_check(self.finding_check_args() + [f"out={redirected}"]))
        self.assertFalse(redirected.exists())

    def test_check_flag_after_the_first_argument_is_not_the_check_mode(self):
        self.turn("on")
        args = self.escape_check_args()
        finished = self.run_command([args[0], args[1], "--check", *args[2:]])
        self.assertEqual(finished.returncode, 0)
        self.assertIn("skipping malformed arg", finished.stderr)
        self.assertEqual(len(self.lines("review-escapes.jsonl")), 1)

    def test_log_scan(self):
        script = str(self.scripts / "log-scan")
        args = [script, "repo=r", "scan=prohibition", "stage=manual", "exit=0", "candidates=2", "confirmed=1"]
        self.assert_switch("scan-runs.jsonl", lambda: self.run_command(args), quiet=False)

    def test_log_spec_run(self):
        script = str(self.scripts / "log-spec-run")
        args = [script, "slug=my-plan", "verdict=finalized", "criteria=3"]
        finished = self.assert_switch("spec-runs.jsonl", lambda: self.run_command(args), quiet=False)
        self.assertTrue(finished.stdout.startswith("logged"))

    # ---- review-scope and log-review-finding

    def test_review_scope_skill_usage_line_only(self):
        script = str(self.review / "review-scope")
        self.turn("off")
        finished = self.run_command([script, "caller=review"])
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("ROOT=", finished.stdout)
        self.assertFalse(self.home_file("skill-usage.jsonl").exists())
        self.turn("on")
        finished = self.run_command([script, "caller=review"])
        self.assertIn("ROOT=", finished.stdout)
        self.assertEqual(json.loads(self.lines("skill-usage.jsonl")[0])["caller"], "review")

    def finding_args(self, *extra):
        return [str(self.review / "log-review-finding"), "kind=run", "gate=code-reviewer", "n_findings=0", *extra]

    def test_review_findings_default_path_is_kept_when_off(self):
        self.turn("off")
        finished = self.run_command(self.finding_args())
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("logged", finished.stdout)
        self.assertEqual(len(self.lines("review-findings.jsonl")), 1)

    def test_review_findings_env_file_is_kept_when_off(self):
        target = self.root / "queue.jsonl"
        self.turn("off")
        finished = self.run_command(self.finding_args(), extra={"REVIEW_FINDINGS_FILE": str(target)})
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(len(target.read_text().splitlines()), 1)

    def test_review_findings_out_redirect_obeys_switch(self):
        target = self.home_file("review-calibration.jsonl")
        self.assert_switch("review-calibration.jsonl", lambda: self.run_command(self.finding_args(f"out={target}")))
        self.assertEqual(self.lines("review-findings.jsonl"), [])

    # ---- branch-recap receipt line

    def receipt_block(self):
        text = RECEIPT_SKILL.read_text()
        found = re.search(r"Persist \(non-blocking[^\n]*\n\n```bash\n(.*?)```", text, re.S)
        self.assertIsNotNone(found, "receipt block not found in branch-recap SKILL.md")
        block = found.group(1)
        for placeholder, value in (("<clean|n culled|n weak>", "clean"), ("<unstaged count>", "0"),
                                   ("<changed-file count>", "0")):
            block = block.replace(placeholder, value)
        return block

    def test_branch_recap_receipt(self):
        repo = self.work / "repo"
        repo.mkdir()
        self.run_command(["git", "init", "-q"], cwd=repo)
        self.run_command(["git", "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo)
        (self.home / ".claude" / "scripts").mkdir(exist_ok=True)
        shutil.copy2(self.scripts / "telemetry_enabled.sh", self.home / ".claude" / "scripts" / "telemetry_enabled.sh")
        block = self.receipt_block()
        self.assert_switch("branch-recap-receipts.jsonl", lambda: self.run_command(["bash", "-c", block], cwd=repo))

    # ---- helpers

    def test_helper_bash(self):
        helper = str(self.scripts / "telemetry_enabled.sh")
        self.turn("off")
        self.assertEqual(self.run_command([helper]).returncode, 1)
        self.turn("on")
        self.assertEqual(self.run_command([helper]).returncode, 0)

    def test_helper_python(self):
        command = [sys.executable, "-c", "import telemetry_enabled, sys; sys.exit(0 if telemetry_enabled.telemetry_enabled() else 1)"]
        self.turn("off")
        self.assertEqual(self.run_command(command, extra={"PYTHONPATH": str(self.scripts)}).returncode, 1)
        self.turn("on")
        self.assertEqual(self.run_command(command, extra={"PYTHONPATH": str(self.scripts)}).returncode, 0)

    def test_missing_helper_keeps_bash_writer_off(self):
        (self.scripts / "telemetry_enabled.sh").unlink()
        self.turn("on")
        finished = self.run_command([str(self.scripts / "log-scan"), "repo=r", "scan=other", "stage=manual", "exit=2"])
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertFalse(self.home_file("scan-runs.jsonl").exists())

    def test_missing_helper_keeps_log_escape_off(self):
        (self.scripts / "telemetry_enabled.sh").unlink()
        self.turn("on")
        finished = self.run_command([str(self.scripts / "log-escape"), *self.ESCAPE_ARGS])
        self.assertEqual((finished.returncode, finished.stdout), (0, "not logged: toolkit telemetry is off\n"))
        self.assertFalse(self.home_file("review-escapes.jsonl").exists())

    def test_missing_python_helper_keeps_logging_hooks_off(self):
        (self.scripts / "telemetry_enabled.py").unlink()
        self.turn("on")
        cases = [("log-agent-usage.py", HOOK_POST, "agent-usage.jsonl"),
                 ("log-skill-use.py", SKILL_POST, "skill-usage.jsonl"),
                 ("test-edit-telemetry.py", TEST_EDIT, "test-edit-telemetry.jsonl")]
        for script, payload, logName in cases:
            with self.subTest(hook=script):
                finished = self.hook(script, payload)()
                self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))
                self.assertFalse(self.home_file(logName).exists())

    def test_missing_python_helper_coder_gate_still_denies_and_logs_nothing(self):
        (self.scripts / "telemetry_enabled.py").unlink()
        self.turn("on")
        command = [sys.executable, str(self.scripts / "coder-gate.py"), "bash-hook"]
        finished = self.run_command(command, json.dumps(CODER_BASH))
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(json.loads(finished.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertFalse(self.home_file("coder-gate.jsonl").exists())

    def test_missing_python_helper_coder_gate_handback_still_runs_and_logs_nothing(self):
        (self.scripts / "telemetry_enabled.py").unlink()
        self.turn("on")
        repo = self.work / "repo"
        repo.mkdir()
        self.run_command(["git", "init", "-q"], cwd=repo)
        self.run_command(["git", "-c", "user.name=t", "-c", "user.email=t@x", "commit", "-q", "--allow-empty", "-m", "i"], cwd=repo)
        gate = [sys.executable, str(self.scripts / "coder-gate.py")]
        self.assertEqual(self.run_command(gate + ["set", "true"], cwd=repo).returncode, 0)
        handback = {"hook_event_name": "PreToolUse", "agent_type": "coder", "agent_id": "a1", "cwd": str(repo),
                    "tool_input": {"message": "done"}}
        finished = self.run_command(gate + ["hook"], json.dumps(handback), cwd=repo)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertIn("HAND-BACK GATE: pass", finished.stdout)
        self.assertFalse(self.home_file("coder-gate.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
