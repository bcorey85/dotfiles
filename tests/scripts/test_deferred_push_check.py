"""Checks for deferred_push_check.py, the PreToolUse hook that lists a branch's unchanged deferred bug findings.

Set DEFERRED_PUSH_CHECK_SCRIPT to run against another copy, such as a staged one."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("DEFERRED_PUSH_CHECK_SCRIPT")
                      or toolkit_paths.REVIEW_DIR / "deferred_push_check.py")
REPO = "shop-api"
BRANCH = "feat"
FILE = "app.py"
FINDING_DATE = "2026-01-02T00:00:00Z"
CLOSING = "This check never blocks."
LINES = [f"line {number}" for number in range(1, 61)]


def run_hook(stdin, findings_file=None, extra_env=None):
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
    env["REVIEW_FINDINGS_FILE"] = str(findings_file or "/nonexistent/review-findings.jsonl")
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env)


class DeferredPushCheckTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name)
        self.repo = self.scratch / REPO
        self.repo.mkdir()
        self.git("init", "-q", "-b", BRANCH)
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        self.findings = self.scratch / "review-findings.jsonl"

    def git(self, *args, date=None):
        env = dict(os.environ)
        if date:
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = date
        finished = subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, env=env)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout.strip()

    def commit(self, date, edits=None):
        # Rewrite the given 1-based lines of app.py, commit, and return the commit hash.
        lines = list(LINES)
        current = self.repo / FILE
        if current.exists():
            lines = current.read_text().splitlines()
        for number, text in (edits or {}).items():
            lines[number - 1] = text
        current.write_text("\n".join(lines) + "\n")
        self.git("add", FILE)
        self.git("commit", "-q", "-m", "change " + date, date=date)
        return self.git("rev-parse", "HEAD")

    def finding(self, **overrides):
        row = {"date": FINDING_DATE, "kind": "finding", "repo": REPO, "branch": BRANCH, "dirty": "0",
               "gate": "code-reviewer", "class": "bug", "file": FILE, "line": 30, "actioned": "deferred",
               "desc": "off by one in the total", "finding_id": "f1"}
        row.update(overrides)
        return row

    def write_findings(self, *rows):
        self.findings.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    def hook(self, command, cwd=None):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or self.repo)}
        return run_hook(json.dumps(payload), self.findings)

    def assert_listed(self, command="git push -u origin feat"):
        finished = self.hook(command)
        self.assertEqual(finished.returncode, 0)
        output = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", output)
        return output["additionalContext"]

    def assert_silent(self, command="git push -u origin feat"):
        finished = self.hook(command)
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")

    def test_unchanged_committed_finding_is_listed_on_push(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(head=head))
        text = self.assert_listed()
        self.assertIn("- app.py:30 [code-reviewer, bug] off by one in the total", text)
        self.assertIn("1 deferred bug or correctness findings", text)
        self.assertTrue(text.endswith("This check never blocks."))
        self.assertIn("fix each one with /fix", text)

    def test_pr_create_and_git_global_option_trigger(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(head=head))
        for command in ("gh pr create --fill", f"git -C {self.repo} push", "make build && git push origin feat"):
            with self.subTest(command=command):
                self.assertIn("app.py:30", self.assert_listed(command))

    def test_long_description_is_cut(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(head=head, desc="x" * 400))
        text = self.assert_listed()
        self.assertIn("x" * 160, text)
        self.assertNotIn("x" * 161, text)

    def test_duplicate_finding_id_is_listed_once(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(head=head), self.finding(head=head))
        self.assertEqual(self.assert_listed().count("app.py:30"), 1)

    def test_finding_fixed_later_at_same_place_is_hidden(self):
        head = self.commit("2026-01-01T00:00:00Z")
        deferred = self.finding(head=head, session="s1", finding_id="f1")
        fixed = self.finding(head=head, session="s1", finding_id="f2", actioned="fixed",
                             date="2026-01-02T00:05:00Z", file="./app.py")
        self.write_findings(deferred, fixed)
        self.assert_silent()

    def test_finding_fixed_in_a_later_iter_is_hidden(self):
        head = self.commit("2026-01-01T00:00:00Z")
        later = "2026-01-02T00:05:00Z"
        deferred = self.finding(head=head, session="s1", iter=1)
        fixed = self.finding(head=head, session="s1", finding_id="f2", actioned="fixed", iter=2, date=later)
        self.write_findings(deferred, fixed)
        self.assert_silent()

    def test_finding_fixed_in_a_later_review_run_with_a_smaller_iter_is_hidden(self):
        head = self.commit("2026-01-01T00:00:00Z")
        later = "2026-01-02T00:05:00Z"
        deferred = self.finding(head=head, session="s1", iter=3)
        fixed = self.finding(head=head, session="s1", finding_id="f2", actioned="fixed", iter=1, date=later)
        self.write_findings(deferred, fixed)
        self.assert_silent()

    def test_different_finding_fixed_in_the_same_pass_keeps_the_deferral(self):
        head = self.commit("2026-01-01T00:00:00Z")
        deferred = self.finding(head=head, session="s1", iter=1)
        same_pass = self.finding(head=head, session="s1", finding_id="f2", actioned="fixed", iter=1,
                                 date="2026-01-02T00:00:30Z")
        self.write_findings(deferred, same_pass)
        self.assertIn("app.py:30", self.assert_listed())

    def test_different_finding_fixed_with_the_same_date_keeps_the_deferral(self):
        head = self.commit("2026-01-01T00:00:00Z")
        deferred = self.finding(head=head, session="s1", iter=1)
        same_date = self.finding(head=head, session="s1", finding_id="f3", actioned="fixed")
        self.write_findings(deferred, same_date)
        self.assertIn("app.py:30", self.assert_listed())

    def test_rows_without_a_session_never_match(self):
        head = self.commit("2026-01-01T00:00:00Z")
        deferred = self.finding(head=head)
        fixed = self.finding(head=head, finding_id="f2", actioned="fixed", date="2026-01-02T00:05:00Z")
        self.write_findings(deferred, fixed)
        self.assertIn("app.py:30", self.assert_listed())

    def test_fixed_row_that_is_not_a_later_match_keeps_the_finding(self):
        head = self.commit("2026-01-01T00:00:00Z")
        deferred = self.finding(head=head, session="s1")
        later = "2026-01-02T00:05:00Z"
        others = [
            self.finding(head=head, session="s2", finding_id="f2", actioned="fixed", date=later),
            self.finding(head=head, session="s1", finding_id="f3", actioned="fixed", date=later, line=31),
            self.finding(head=head, session="s1", finding_id="f4", actioned="fixed", date=later, file="other.py"),
            self.finding(head=head, session="s1", finding_id="f5", actioned="fixed", date="2026-01-01T23:00:00Z"),
        ]
        self.write_findings(deferred, *others)
        self.assert_listed()

    def test_later_commit_on_the_lines_hides_the_finding(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.commit("2026-01-03T00:00:00Z", {32: "fixed line"})
        self.write_findings(self.finding(head=head))
        self.assert_silent()

    def test_later_commit_on_distant_lines_keeps_the_finding(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.commit("2026-01-03T00:00:00Z", {3: "far away", 58: "also far"})
        self.write_findings(self.finding(head=head))
        self.assertIn("app.py:30", self.assert_listed())

    def test_dirty_finding_uses_first_commit_after_it_as_base(self):
        self.commit("2026-01-01T00:00:00Z")
        self.commit("2026-01-03T00:00:00Z", {30: "code the finding was about"})
        self.write_findings(self.finding(dirty="1", head=self.git("rev-parse", "HEAD~1")))
        self.assertIn("app.py:30", self.assert_listed())

    def test_dirty_finding_changed_after_landing_is_hidden(self):
        self.commit("2026-01-01T00:00:00Z")
        self.commit("2026-01-03T00:00:00Z", {30: "code the finding was about"})
        self.commit("2026-01-04T00:00:00Z", {31: "edited again"})
        self.write_findings(self.finding(dirty="1"))
        self.assert_silent()

    def test_dirty_finding_never_committed_is_hidden(self):
        self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(dirty="1"))
        self.assert_silent()

    def test_rows_that_do_not_qualify_are_hidden(self):
        head = self.commit("2026-01-01T00:00:00Z")
        cases = {
            "docs class": {"class": "docs"},
            "fixed": {"actioned": "fixed"},
            "other branch": {"branch": "other"},
            "other repo": {"repo": "billing"},
            "run row": {"kind": "run"},
            "no line": {"line": None},
            "no file": {"file": ""},
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.write_findings(self.finding(head=head, **change))
                self.assert_silent()

    def test_correctness_class_is_listed(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(head=head, **{"class": "correctness"}))
        self.assertIn("[code-reviewer, correctness]", self.assert_listed())

    def test_non_trigger_commands_print_nothing(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(head=head))
        commands = [
            "git status",
            'echo "git push"',
            "cat <<EOF\ngit push\nEOF",
            "ls # git push",
            "git commit -m 'git push later'",
            "gh pr view",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assert_silent(command)

    def test_bad_input_exits_zero_with_no_output(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(head=head))
        garbage = run_hook("not json", self.findings)
        self.assertEqual((garbage.returncode, garbage.stdout), (0, ""))

        outside = self.scratch / "plain"
        outside.mkdir()
        not_git = self.hook("git push", cwd=outside)
        self.assertEqual((not_git.returncode, not_git.stdout), (0, ""))

        payload = json.dumps({"tool_input": {"command": "git push"}, "cwd": str(self.repo)})
        missing = run_hook(payload, self.scratch / "absent.jsonl")
        self.assertEqual((missing.returncode, missing.stdout), (0, ""))

    def test_skip_hooks_prints_nothing(self):
        head = self.commit("2026-01-01T00:00:00Z")
        self.write_findings(self.finding(head=head))
        payload = json.dumps({"tool_input": {"command": "git push"}, "cwd": str(self.repo)})
        finished = run_hook(payload, self.findings, {"CLAUDE_SKIP_HOOKS": "1"})
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
