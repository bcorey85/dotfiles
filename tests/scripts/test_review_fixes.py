"""One check per review finding on the Python hook ports, plus the crash-to-block path of run_gate.

Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.SCRIPTS_DIR)


def hook_script(file_name):
    """The script file under whichever scripts subfolder holds it."""
    return next(SCRIPTS_DIR.glob("*/" + file_name))


class HookRunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = pathlib.Path(self.tmp.name) / "home"
        (self.home / ".claude").mkdir(parents=True)
        self.work = pathlib.Path(self.tmp.name) / "work"
        self.work.mkdir()

    def run_hook(self, name, stdin, env_extra=None, **options):
        if isinstance(stdin, str):
            stdin = stdin.encode("utf-8")
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home), "TMPDIR": self.tmp.name,
                       "CLAUDE_TOOLKIT_TELEMETRY": "1"}
        environment.update(env_extra or {})
        return subprocess.run([sys.executable, str(hook_script(name.replace("-", "_") + ".py"))], input=stdin,
                              capture_output=True, env=environment, cwd=str(self.work), **options)

    def decision(self, finished):
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return json.loads(finished.stdout.decode("utf-8"))["hookSpecificOutput"]


class QualityCheckCapFindingsTest(HookRunTest):
    def fire(self, event, command, session="s1"):
        payload = {"hook_event_name": event, "tool_name": "Bash", "session_id": session, "cwd": str(self.work),
                   "tool_input": {"command": command}}
        return self.run_hook("quality-check-cap", json.dumps(payload))

    def test_unicode_letter_assignment_prefix_is_still_capped(self):
        # finding 2
        self.assertEqual(self.fire("PostToolUse", "é=1 pytest").returncode, 0)
        decision = self.decision(self.fire("PreToolUse", "é=1 pytest"))
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("[quality-check-cap]", decision["permissionDecisionReason"])

    def test_empty_session_id_stays_empty_and_missing_becomes_unknown(self):
        # finding 4
        root = self.home / ".claude" / "state" / "quality-check"
        self.fire("PostToolUse", "pytest", session="")
        self.assertEqual([path.name for path in root.glob("run-*")].__len__(), 1)
        self.assertFalse((root / "unknown").exists())
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Bash", "cwd": str(self.work),
                   "tool_input": {"command": "pytest"}}
        self.run_hook("quality-check-cap", json.dumps(payload))
        self.assertEqual(len(list((root / "unknown").glob("run-*"))), 1)
        for blank in (None, False):
            payload["session_id"] = blank
            self.run_hook("quality-check-cap", json.dumps(payload))
        self.assertEqual(len(list((root / "unknown").glob("run-*"))), 1)


class CalibrationGuardFindingsTest(HookRunTest):
    @unittest.skipIf(os.geteuid() == 0, "root reads any file")
    def test_unreadable_lock_prints_question_marks(self):
        # finding 5: `jq ... lock 2>/dev/null || echo '?'`
        lock = self.home / ".local" / "state" / "claude-calibration" / "lock.json"
        lock.parent.mkdir(parents=True)
        lock.write_text('{"file":"a.ts"}')
        lock.chmod(0)
        self.addCleanup(lock.chmod, stat.S_IRUSR | stat.S_IWUSR)
        finished = self.run_hook("calibration-guard", b"")
        self.assertEqual(finished.returncode, 0)
        text = finished.stdout.decode("utf-8")
        self.assertIn("may still be in:\n  ?\n", text)
        self.assertIn('cp "?" "?"', text)
        self.assertIn("A deliberate '?' mutation was applied at ?", text)
        self.assertIn("CALIBRATION SEED", text)


class InvalidUtf8StdinTest(HookRunTest):
    BAD = b"\xff"

    def test_comment_bloat_gate_blocks_an_added_comment_next_to_invalid_utf8(self):
        # finding 6
        subprocess.run(["git", "init", "-q", str(self.work)], check=True)
        source = self.work / "a.py"
        source.write_text("value = 0\n# note 1\n")
        body = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(source),
                                                              "new_string": "# note 1\n@@"}})
        stdin = body.encode("utf-8").replace(b"@@", self.BAD)
        finished = self.run_hook("comment-bloat-gate", stdin)
        self.assertEqual(finished.returncode, 2)
        self.assertIn(b"2: # note 1", finished.stderr)

    def test_spec_budget_gate_still_denies_next_to_invalid_utf8(self):
        # finding 6
        skill = self.work / "claude" / "skills" / "eng-spec" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("w\n")
        content = " ".join("w" for _ in range(1600)) + " @@"
        body = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(skill), "content": content}})
        finished = self.run_hook("spec-budget-gate", body.encode("utf-8").replace(b"@@", self.BAD))
        self.assertEqual(finished.returncode, 0)
        self.assertIn(b"resident load", finished.stdout)

class SpecBudgetWordCountTest(HookRunTest):
    def over_budget(self, separator):
        # finding 7: 1600 words split by the separator; wc -w counts them all, a whitespace-blind count sees one
        skill = self.work / "claude" / "skills" / "eng-spec" / "SKILL.md"
        skill.parent.mkdir(parents=True, exist_ok=True)
        skill.write_text("w\n")
        content = separator.join("w" for _ in range(1600))
        body = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(skill), "content": content}})
        return self.run_hook("spec-budget-gate", body)

    def test_unicode_spaces_split_words(self):
        for separator in (" ", " ", "　"):
            finished = self.over_budget(separator)
            self.assertEqual(finished.returncode, 0)
            self.assertIn(b"resident load", finished.stdout, repr(separator))


class IdeographicSpaceTest(HookRunTest):
    def test_comment_bloat_gate_reads_an_ideographic_space_as_indent(self):
        # finding 8: `[[:space:]]*` before the comment marker matches U+3000
        subprocess.run(["git", "init", "-q", str(self.work)], check=True)
        source = self.work / "a.py"
        source.write_text("value = 0\n　# note 1\n")
        body = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(source),
                                                              "new_string": "　# note 1\n"}})
        finished = self.run_hook("comment-bloat-gate", body)
        self.assertEqual(finished.returncode, 2)
        self.assertIn(b"2: # note 1", finished.stderr)

    def test_stale_citation_gate_reads_an_ideographic_space_as_indent(self):
        # finding 8
        repo = self.work / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        source = repo / "a.py"
        source.write_text("　# an earlier version said x\n")
        body = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(source)}})
        finished = self.run_hook("stale-citation-gate", body)
        self.assertEqual(finished.returncode, 0)
        self.assertIn(b"planning vocabulary", finished.stderr)


class LoneSurrogateLogTest(HookRunTest):
    def test_log_agent_usage_writes_the_row(self):
        # finding 9
        body = (b'{"hook_event_name":"PostToolUse","tool_input":{"description":"x\\ud800y","subagent_type":"coder"},'
                b'"tool_response":{"content":"ok"}}')
        finished = self.run_hook("log-agent-usage", body)
        self.assertEqual((finished.returncode, finished.stderr), (0, b""))
        row = json.loads((self.home / ".claude" / "agent-usage.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(row["desc"], "x?y")


class GitDisciplineAmendTest(HookRunTest):
    def test_amend_on_a_continuation_line_is_denied(self):
        # --amend sits at the start of its own line, which only the ^ alternative under re.M matches
        command = "git commit -m fix \\\n--amend"
        finished = self.run_hook("git-discipline-gate", json.dumps({"tool_input": {"command": command}}))
        decision = self.decision(finished)
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("--amend is blocked", decision["permissionDecisionReason"])


class RunGateTest(HookRunTest):
    PORTED = ("calibration-guard",
              "claudemd-linecount", "comment-bloat-gate", "emit-orchestration", "format-changed",
              "git-discipline-gate", "log-agent-usage", "quality-check-cap",
              "spec-budget-gate", "stale-citation-gate")
    GATES = ("quality-check-cap", "git-discipline-gate",
             "comment-bloat-gate", "spec-budget-gate")

    def test_crash_escaping_main_blocks_with_exit_2_and_one_line(self):
        driver = pathlib.Path(self.tmp.name) / "crashing-gate.py"
        shutil.copy(str(SCRIPTS_DIR / "lib" / "hook_input.py"), str(pathlib.Path(self.tmp.name) / "hook_input.py"))
        shutil.copy(str(SCRIPTS_DIR / "lib" / "script_utils.py"), str(pathlib.Path(self.tmp.name) / "script_utils.py"))
        shutil.copy(str(SCRIPTS_DIR / "lib" / "import_guard.py"), str(pathlib.Path(self.tmp.name) / "import_guard.py"))
        driver.write_text("import hook_input\n\n\ndef main():\n    raise RuntimeError('boom')\n\n\n"
                          "hook_input.run_gate(main)\n")
        finished = subprocess.run([sys.executable, str(driver)], input=b"{}", capture_output=True)
        self.assertEqual(finished.returncode, 2)
        self.assertEqual(finished.stdout, b"")
        self.assertEqual(
            finished.stderr.decode("utf-8"),
            "[crashing-gate] crashed while judging the call (RuntimeError: boom) - exit 2 (a call that has not run yet "
            "is blocked). Recovery: fix the file the error names with the Edit tool, or ask the user to run "
            "`git restore <file>`.\n"
        )

    def test_run_gate_passes_the_exit_code_of_main_through(self):
        driver = pathlib.Path(self.tmp.name) / "quiet-gate.py"
        shutil.copy(str(SCRIPTS_DIR / "lib" / "hook_input.py"), str(pathlib.Path(self.tmp.name) / "hook_input.py"))
        shutil.copy(str(SCRIPTS_DIR / "lib" / "script_utils.py"), str(pathlib.Path(self.tmp.name) / "script_utils.py"))
        shutil.copy(str(SCRIPTS_DIR / "lib" / "import_guard.py"), str(pathlib.Path(self.tmp.name) / "import_guard.py"))
        driver.write_text("import hook_input\nhook_input.run_gate(lambda: 3)\n")
        self.assertEqual(subprocess.run([sys.executable, str(driver)]).returncode, 3)

    def test_gate_whose_decision_cannot_be_written_blocks(self):
        # stdout closed: the deny cannot be printed, the crash escapes the port's own handler, run_gate exits 2
        payload = json.dumps({"tool_input": {"command": "git stash"}}).encode("utf-8")
        environment = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        process = subprocess.Popen([sys.executable, str(hook_script("git_discipline_gate.py"))],
                                   stdin=subprocess.PIPE, stderr=subprocess.PIPE, env=environment,
                                   cwd=str(self.work), preexec_fn=lambda: os.close(1))
        _, stderr = process.communicate(payload)
        self.assertEqual(process.returncode, 2)
        message = stderr.decode("utf-8")
        self.assertTrue(message.startswith("[git-discipline-gate] crashed while judging the call ("), stderr)

    def test_every_gate_imports_run_gate_and_is_executable(self):
        for name in self.GATES:
            path = hook_script(name.replace("-", "_") + ".py")
            self.assertIn("hook_input.run_gate(main)", path.read_text(), name)
        for name in self.PORTED:
            path = hook_script(name.replace("-", "_") + ".py")
            self.assertEqual(path.read_text().splitlines()[0], "#!/usr/bin/env python3", path.name)
            self.assertTrue(os.access(str(path), os.X_OK), path.name)


if __name__ == "__main__":
    unittest.main()
