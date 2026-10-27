"""Checks for deferred_push_check.py, the PreToolUse hook that lists a branch's unchanged deferred bug findings.

The findings are v_review_finding rows read through `ledger query`. A stand-in `ledger` answers `worker --once`,
`key path`, `key branch`, `repo` and `query` (it refuses a table or column the view lacks); it keys a name as
`p-<name>` or `b-<name>` and applies the query's actioned,
class, repo and branch_key conditions to the planted rows, so a row the real query would leave out is left out here.

Set DEFERRED_PUSH_CHECK_SCRIPT to run against another copy, such as a staged one."""
import importlib.util
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import fake_ledger
import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("DEFERRED_PUSH_CHECK_SCRIPT")
                      or toolkit_paths.REVIEW_DIR / "deferred_push_check.py")
REPO = "shop-api"
BRANCH = "feat"
FILE = "app.py"
FINDING_DATE = "2026-01-02T00:00:00Z"
LINES = [f"line {number}" for number in range(1, 61)]

STAND_IN_LEDGER = '''#!/usr/bin/env python3
import json
import os
import re
import sys

args = sys.argv[1:]
rows_path = os.environ["STAND_IN_LEDGER_ROWS"]
with open(rows_path + ".calls", "a") as calls:
    calls.write(" ".join(args[:2]) + "\\n")
VIEW = "v_review_finding"
VIEW_COLUMNS = {"finding_id", "gate", "class", "path_key", "line", "head", "dirty", "found_ts",
                "actioned", "repo", "branch_key"}

if args == ["worker", "--once"]:
    sys.exit(0)

if args == ["repo"]:
    if "STAND_IN_LEDGER_REPO" not in os.environ:
        sys.exit(64)
    print(os.environ["STAND_IN_LEDGER_REPO"])
    sys.exit(0)

if len(args) == 2 and args[0] == "key" and args[1] in ("path", "branch"):
    prefix = "p-" if args[1] == "path" else "b-"
    for name in sys.stdin.read().splitlines():
        print(prefix + name)
    sys.exit(0)

if len(args) == 4 and args[:3] == ["query", "--max-time", "2"]:
    sql = args[3]
    shape = re.match(r"SELECT (.+?) FROM (\\w+) WHERE ", sql)
    if shape is None or shape.group(2) != VIEW:
        print("unknown table in: " + sql, file=sys.stderr)
        sys.exit(1)
    COLUMNS = []
    for expression in shape.group(1).split(", "):
        source, _, alias = expression.partition(" AS ")
        if source not in VIEW_COLUMNS:
            print("unknown column " + source, file=sys.stderr)
            sys.exit(1)
        COLUMNS.append((source, alias or source))
    wanted_actioned = re.search(r"actioned = '([^']*)'", sql).group(1)
    wanted_classes = re.search(r"class IN \\(([^)]*)\\)", sql).group(1).replace("'", "").split(", ")
    wanted_repo = re.search(r"repo = '([^']*)'", sql).group(1)
    wanted_branch_key = re.search(r"branch_key = '([^']*)'", sql).group(1)
    with open(rows_path) as handle:
        rows = [json.loads(line) for line in handle if line.strip()]
    print("\\t".join(alias for _, alias in COLUMNS))
    for row in rows:
        kept = (row["actioned"] == wanted_actioned and row["class"] in wanted_classes
                and row["repo"] == wanted_repo and row["branch_key"] == wanted_branch_key)
        if kept:
            print("\\t".join("" if row.get(alias) is None else str(row[alias]) for _, alias in COLUMNS))
    sys.exit(0)

sys.exit(64)
'''


def install_stand_in(directory):
    """Plant the stand-in `ledger` under `directory`; return the env entries that put it first on PATH."""
    bin_directory = pathlib.Path(directory) / "stand-in-ledger-bin"
    bin_directory.mkdir(parents=True, exist_ok=True)
    ledger = bin_directory / "ledger"
    ledger.write_text(STAND_IN_LEDGER)
    ledger.chmod(0o755)
    return {
        "PATH": f"{bin_directory}{os.pathsep}{os.environ['PATH']}",
        "STAND_IN_LEDGER_ROWS": str(pathlib.Path(directory) / "stand-in-rows.jsonl"),
    }


def run_hook(stdin, env_entries, extra_env=None):
    env = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
    env.update(env_entries)
    env.update(extra_env or {})
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=env)


class DeferredPushCheckTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name)
        self.repo = self.scratch / REPO
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        self.ledger_env = install_stand_in(self.scratch)
        self.rows_path = pathlib.Path(self.ledger_env["STAND_IN_LEDGER_ROWS"])
        self.base_commit_made = False

    def git(self, *args, date=None):
        env = dict(os.environ)
        if date:
            env["GIT_COMMITTER_DATE"] = env["GIT_AUTHOR_DATE"] = date
        finished = subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, env=env)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout.strip()

    def commit(self, date, edits=None):
        # Rewrite the given 1-based lines of app.py, commit, and return the commit hash. The first commit lands on
        # main; the branch is cut from it, so app.py counts as a file the branch changes from the second commit on.
        lines = list(LINES)
        current = self.repo / FILE
        if current.exists():
            lines = current.read_text().splitlines()
        for number, text in (edits or {}).items():
            lines[number - 1] = text
        current.write_text("\n".join(lines) + "\n")
        self.git("add", FILE)
        self.git("commit", "-q", "-m", "change " + date, date=date)
        if not self.base_commit_made:
            self.base_commit_made = True
            self.git("checkout", "-q", "-b", BRANCH)
        return self.git("rev-parse", "HEAD")

    def finding(self, **overrides):
        row = {"date": FINDING_DATE, "repo": REPO, "branch_key": "b-" + BRANCH, "dirty": "0",
               "gate": "code-reviewer", "class": "bug", "path_key": "p-" + FILE, "line": 30,
               "actioned": "deferred", "finding_id": "f1"}
        row.update(overrides)
        return row

    def plant_findings(self, *rows):
        self.rows_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")

    def hook(self, command, cwd=None):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or self.repo)}
        return run_hook(json.dumps(payload), self.ledger_env)

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

    def two_commits(self, second_edits=None):
        # A commit on main, then one on the branch; returns the head of the first.
        first = self.commit("2026-01-01T00:00:00Z")
        self.commit("2026-01-01T12:00:00Z", {1: "branch change"})
        if second_edits:
            self.commit("2026-01-03T00:00:00Z", second_edits)
        return first

    def test_unchanged_committed_finding_is_listed_on_push(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head))
        text = self.assert_listed()
        self.assertIn("- app.py:30 (bug)", text)
        self.assertNotIn("code-reviewer", text)
        self.assertIn("1 deferred bug or correctness findings", text)
        self.assertTrue(text.endswith("This check never blocks."))
        self.assertIn("fix each one with /fix", text)

    def test_pr_create_and_git_global_option_trigger(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head))
        for command in ("gh pr create --fill", f"git -C {self.repo} push", "make build && git push origin feat"):
            with self.subTest(command=command):
                self.assertIn("app.py:30", self.assert_listed(command))

    def test_repo_name_comes_from_ledger_repo_not_the_directory_name(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head, repo="billing"))
        finished = run_hook(
            json.dumps({"tool_input": {"command": "git push"}, "cwd": str(self.repo)}),
            self.ledger_env, {"STAND_IN_LEDGER_REPO": "billing"})
        self.assertIn("app.py:30", json.loads(finished.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_unpushed_commit_on_the_default_branch_counts_as_a_branch_change(self):
        origin = self.scratch / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", "-b", "master", str(origin)], check=True)
        pushed = self.commit("2026-01-01T00:00:00Z")
        self.git("checkout", "-q", "main")
        self.git("branch", "-q", "-m", "master")
        self.git("branch", "-q", "-D", BRANCH)
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "-u", "origin", "master")
        self.commit_on_current_branch("2026-01-02T00:00:00Z")
        # a stale origin/main that already holds the unpushed commit would make origin/main...HEAD empty
        self.git("update-ref", "refs/remotes/origin/main", "HEAD")
        self.plant_findings(self.finding(head=pushed, branch_key="b-master"))
        self.assertIn("app.py:30", self.assert_listed())

    def commit_on_current_branch(self, date):
        (self.repo / FILE).write_text("\n".join(["unpushed change", *LINES[1:]]) + "\n")
        self.git("add", FILE)
        self.git("commit", "-q", "-m", "change " + date, date=date)

    def test_duplicate_finding_id_is_listed_once(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head), self.finding(head=head))
        self.assertEqual(self.assert_listed().count("app.py:30"), 1)

    def test_later_commit_on_the_lines_hides_the_finding(self):
        head = self.two_commits({32: "fixed line"})
        self.plant_findings(self.finding(head=head))
        self.assert_silent()

    def test_later_commit_on_distant_lines_keeps_the_finding(self):
        head = self.two_commits({3: "far away", 58: "also far"})
        self.plant_findings(self.finding(head=head))
        self.assertIn("app.py:30", self.assert_listed())

    def test_dirty_finding_uses_first_commit_after_it_as_base(self):
        self.commit("2026-01-01T00:00:00Z")
        self.commit("2026-01-03T00:00:00Z", {30: "code the finding was about"})
        self.plant_findings(self.finding(dirty="1", head=self.git("rev-parse", "HEAD~1")))
        self.assertIn("app.py:30", self.assert_listed())

    def test_dirty_finding_changed_after_landing_is_hidden(self):
        self.commit("2026-01-01T00:00:00Z")
        self.commit("2026-01-03T00:00:00Z", {30: "code the finding was about"})
        self.commit("2026-01-04T00:00:00Z", {31: "edited again"})
        self.plant_findings(self.finding(dirty="1"))
        self.assert_silent()

    def test_dirty_finding_never_committed_is_hidden(self):
        self.two_commits()
        self.plant_findings(self.finding(dirty="1", date="2026-02-01T00:00:00Z"))
        self.assert_silent()

    def test_rows_that_do_not_qualify_are_hidden(self):
        head = self.two_commits()
        cases = {
            "smell class": {"class": "smell"},
            "fixed": {"actioned": "fixed"},
            "other branch": {"branch_key": "b-other"},
            "other repo": {"repo": "billing"},
            "file the branch does not change": {"path_key": "p-elsewhere.py"},
            "no line": {"line": None},
        }
        for name, change in cases.items():
            with self.subTest(name):
                self.plant_findings(self.finding(head=head, **change))
                self.assert_silent()

    def test_correctness_class_is_listed(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head, **{"class": "correctness"}))
        self.assertIn("- app.py:30 (correctness)", self.assert_listed())

    def test_uncommitted_change_makes_the_file_one_the_branch_changes(self):
        head = self.commit("2026-01-01T00:00:00Z")
        (self.repo / FILE).write_text("\n".join([*LINES, "extra"]) + "\n")
        self.plant_findings(self.finding(head=head))
        self.assertIn("app.py:30", self.assert_listed())

    def test_non_trigger_commands_print_nothing(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head))
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

    def test_no_ledger_exits_zero_with_no_output(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head))
        payload = json.dumps({"tool_input": {"command": "git push"}, "cwd": str(self.repo)})
        bare_path = fake_ledger.path_without_ledger(os.environ["PATH"])
        finished = run_hook(payload, {"PATH": bare_path})
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))

    def test_busy_ledger_is_asked_once_without_a_cache_refresh(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head))
        stand_in = pathlib.Path(self.ledger_env["PATH"].split(os.pathsep)[0]) / "ledger"
        calls = self.scratch / "busy-calls"
        stand_in.write_text(f'#!/bin/sh\necho "$1" >> "{calls}"\n'
                            'case "$1" in key) while read name; do echo "k-$name"; done; exit 0;; esac\n'
                            "exit 75\n")
        self.assert_silent()
        asked = calls.read_text().split()
        self.assertEqual(1, asked.count("query"))
        self.assertNotIn("worker", asked)

    def test_ledger_findings_gives_each_ledger_call_its_own_timeout(self):
        module_spec = importlib.util.spec_from_file_location("deferred_push_check", SCRIPT)
        deferred_push_check = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(deferred_push_check)

        with mock.patch.object(deferred_push_check, "branch_changed_files", return_value=["app.py"]), \
                mock.patch.object(deferred_push_check.script_utils, "ledger_keys",
                                  side_effect=[["b-feat"], ["p-app.py"]]) as ledger_keys, \
                mock.patch.object(deferred_push_check.script_utils, "query_ledger_rows_once",
                                  return_value=[]) as query_once:
            deferred_push_check.ledger_findings("/repo", REPO, BRANCH)

        branch_call, path_call = ledger_keys.call_args_list
        self.assertEqual(5, branch_call.kwargs["timeout_seconds"])
        self.assertEqual(5, path_call.kwargs["timeout_seconds"])
        sql = deferred_push_check.finding_query(REPO, "b-feat")
        query_once.assert_called_once_with(sql, 2, 5)

    def test_failing_ledger_exits_zero_with_no_output(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head))
        stand_in = pathlib.Path(self.ledger_env["PATH"].split(os.pathsep)[0]) / "ledger"
        stand_in.write_text("#!/bin/sh\nexit 2\n")
        self.assert_silent()

    def test_bad_input_exits_zero_with_no_output(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head))
        garbage = run_hook("not json", self.ledger_env)
        self.assertEqual((garbage.returncode, garbage.stdout), (0, ""))

        outside = self.scratch / "plain"
        outside.mkdir()
        not_git = self.hook("git push", cwd=outside)
        self.assertEqual((not_git.returncode, not_git.stdout), (0, ""))

    def test_skip_hooks_prints_nothing(self):
        head = self.two_commits()
        self.plant_findings(self.finding(head=head))
        payload = json.dumps({"tool_input": {"command": "git push"}, "cwd": str(self.repo)})
        finished = run_hook(payload, self.ledger_env, {"CLAUDE_SKIP_HOOKS": "1"})
        self.assertEqual((finished.returncode, finished.stdout), (0, ""))


if __name__ == "__main__":
    unittest.main()
