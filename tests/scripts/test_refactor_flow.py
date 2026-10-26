import importlib.machinery
import importlib.util
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import fake_ledger
import toolkit_paths

SCRIPT = pathlib.Path(
    os.environ.get("REFACTOR_FLOW_PATH")
    or toolkit_paths.CLAUDE_DIR / "skills" / "refactor" / "scripts" / "refactor_flow.py"
)
REAL_CLAUDE_DIR = os.environ.get("REFACTOR_CLAUDE_DIR") or str(toolkit_paths.CLAUDE_DIR)
REAL_SCRIPTS_DIR = pathlib.Path(REAL_CLAUDE_DIR) / "scripts"
BRANCH_BASE = os.environ.get("BRANCH_BASE_SCRIPT") or str(REAL_SCRIPTS_DIR / "tools" / "branch-base")
LOG_ESCAPE = os.environ.get("REFACTOR_LOG_ESCAPE") or str(REAL_SCRIPTS_DIR / "telemetry" / "log-escape")

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}

# Captured from a real jscpd run (consoleFull reporter, --min-tokens 70) over src/a.js and
# "src/sub dir/b copy.js": site paths are relative to the target, one site path has a space,
# and code lines follow with a box-drawing bar.
JSCPD_REAL = (
    "\x1b[1mClone found (javascript)\x1b[22m\n"
    " - a.js [1:1 - 48:2]\n"
    "   sub dir/b copy.js [1:1 - 48:2]\n"
    "\x1b[90m   1 │ \x1b[39mexport function step0(orders, limit) {\n"
    "\x1b[90m   2 │ \x1b[39m  const kept = orders.filter((o) => o.total > limit * 0);\n"
    "\x1b[90m   3 │ \x1b[39m  return kept.map((o) => ({ id: o.id, total: o.total + 0, tag: 'x0' }));\n"
    "\x1b[90m     … 28 more lines\x1b[39m\n"
)


def load_script_module():
    loader = importlib.machinery.SourceFileLoader("refactor_flow_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class RefactorFlowTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name)
        self.home = self.temp_root / "home"
        self.escapes = self.temp_root / "escapes.jsonl"
        self.ledger_env = fake_ledger.install(self.temp_root)
        self.log_input_dir = self.temp_root / "log-inputs"
        self.log_input_dir.mkdir()
        (self.home / ".claude").mkdir(parents=True)
        self.repo = self.make_repo("myrepo")

    def make_repo(self, name):
        repo = self.temp_root / name
        repo.mkdir()
        self.git("init", "-q", "-b", "main", cwd=repo)
        (repo / "README.md").write_text("hello\n")
        self.git("add", "-A", cwd=repo)
        self.git("commit", "-q", "-m", "init", cwd=repo)
        return repo

    def git(self, *args, cwd=None):
        env = {**os.environ, **GIT_ENV}
        return subprocess.run(["git", *args], cwd=cwd or self.repo, env=env, check=True, capture_output=True,
                              text=True).stdout

    def write(self, rel, body):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)

    def write_bytes(self, rel, body):
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)

    def commit_all(self, message):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def branch_with(self, files):
        self.git("checkout", "-q", "-b", "feature")
        for rel, body in files.items():
            self.write(rel, body)
        self.commit_all("work")

    def flow(self, *args, extra_env=None, cwd=None):
        env = {
            **os.environ,
            **GIT_ENV,
            "HOME": str(self.home),
            "CLAUDE_TOOLKIT_TELEMETRY": "1",
            "REFACTOR_CLAUDE_DIR": REAL_CLAUDE_DIR,
            "BRANCH_BASE_SCRIPT": BRANCH_BASE,
            "REVIEW_ESCAPES_FILE": str(self.escapes),
            "REFACTOR_LOG_INPUT_DIR": str(self.log_input_dir),
            **self.ledger_env,
            **(extra_env or {}),
        }
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], cwd=cwd or self.repo, env=env, capture_output=True, text=True
        )

    def finding_rows(self):
        """Every row log-review-finding sent to `ledger write`, oldest first, as the row the writer built plus a
        `kind` of run or finding taken from the row type. A file path is carried in path_key, raw, until the real
        ledger keys it."""
        return [
            {**row, "kind": row["_type"].removeprefix("review_")}
            for row in fake_ledger.recorded_rows(self.ledger_env)
            if row["_type"] in ("review_run", "review_finding")
        ]

    def escape_rows(self):
        """Every `review_escape` row log-escape sent to `ledger write`, oldest first. A file path is carried in
        path_key, raw, until the real ledger keys it."""
        return fake_ledger.recorded_rows(self.ledger_env, "review_escape")

    def log_input(self, payload, name="log-input.json"):
        path = self.temp_root / name
        path.write_text(json.dumps(payload))
        return str(path)

    def log(self, mode, payload, **kwargs):
        return self.flow("log", "--mode", mode, "--input", self.log_input(payload), **kwargs)

    def rows(self, path):
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def finding(self, **overrides):
        row = {"class": "duplication", "disposition": "fix", "actioned": "fixed", "file": "a.py", "line": 3,
               "desc": "same parse twice", "severity": "medium", "escape": True}
        return {**row, **overrides}

    def last_line(self, done):
        return [line for line in done.stdout.splitlines() if line.strip()][-1]

    def handoff_input(self, **overrides):
        handoff = {"files": [{"path": "a.py", "change": "c"}], "tests_run": "none", "flagged": "none"}
        return {**handoff, **overrides}

    # ------------------------------------------------------------ branch-prep
    def test_branch_prep_lists_files_sweep_and_prompt(self):
        self.branch_with({"a.py": "x = 1\n# TODO fix\n# if x:\nprint('hi')\n", "b.py": "y = 2\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- a.py", done.stdout)
        self.assertIn("- b.py", done.stdout)
        self.assertIn("a.py:2 [marker] # TODO fix", done.stdout)
        self.assertIn("a.py:3 [commented-out code]", done.stdout)
        self.assertIn("a.py:4 [marker] print('hi')", done.stdout)
        self.assertIn("`git diff main...HEAD`", done.stdout)
        self.assertIn("cross-phase smells", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "NEXT:")

    def test_branch_prep_next_names_test_audit_and_the_nothing_found_case(self):
        self.branch_with({"a.py": "x = 1\n"})
        done = self.flow("branch-prep")
        next_text = self.last_line(done)
        self.assertIn("test audit", next_text)
        self.assertIn("Nothing found", next_text)

    def test_branch_prep_next_passes_the_base_it_used_to_log(self):
        self.branch_with({"a.py": "x = 1\n"})
        done = self.flow("branch-prep")
        self.assertIn("`log --mode branch --base main --input ", self.last_line(done))
        explicit = self.flow("branch-prep", "--base", "HEAD~1")
        self.assertIn("`log --mode branch --base HEAD~1 --input ", explicit.stdout)

    def test_every_prep_verb_names_a_fresh_input_path_in_its_next_line(self):
        self.branch_with({"a.py": "x = 1\n", "mod/b.py": "y = 2\n"})
        pattern = r"--input \S*refactor-flow-[0-9a-f]{12}\.json"
        runs = (("branch-prep",), ("audit-prep", "mod", "--jscpd-timeout", "1"), ("simplify-prep", "mod"))
        for verb in runs:
            first = self.last_line(self.flow(*verb))
            second = self.last_line(self.flow(*verb))
            self.assertRegex(first, pattern, verb)
            first_path = re.search(pattern, first).group(0)
            second_path = re.search(pattern, second).group(0)
            self.assertNotEqual(first_path, second_path, verb)

    def test_branch_prep_lists_the_changed_files_once_inside_the_prompt(self):
        self.branch_with({"a.py": "x = 1\n", "b.py": "y = 2\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.stdout.count("- a.py"), 1)
        self.assertIn("Changed files (2);", done.stdout)
        prompt = done.stdout.split("dispatch prompt", 1)[1]
        self.assertIn("- a.py", prompt)
        self.assertIn("- b.py", prompt)

    def pushed_feature_branch(self, files):
        origin = self.temp_root / "origin.git"
        self.git("init", "-q", "--bare", "-b", "main", str(origin), cwd=self.temp_root)
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "-u", "origin", "main")
        self.git("remote", "set-head", "origin", "main")
        self.branch_with(files)
        self.git("push", "-q", "-u", "origin", "feature")

    def test_branch_prep_pushed_feature_branch_uses_the_default_branch_not_its_own_remote_copy(self):
        self.pushed_feature_branch({"a.py": "x = 1\n", "b.py": "y = 2\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("base `origin/main`", done.stdout)
        self.assertNotIn("diff is empty", done.stdout)
        self.assertIn("- a.py", done.stdout)
        self.assertIn("- b.py", done.stdout)
        named = self.flow("branch-prep", "--head", "feature")
        self.assertIn("base `origin/main`", named.stdout)
        self.assertIn("- b.py", named.stdout)

    def test_log_branch_on_a_pushed_feature_branch_counts_the_whole_branch(self):
        self.pushed_feature_branch({"a.py": "x = 1\ny = 2\n"})
        done = self.log("branch", {"finder": "smell-reviewer", "lane": "code", "findings": []})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "2")

    def test_branch_prep_with_no_base_passes_the_helper_stop_line_through(self):
        self.git("branch", "-m", "main", "work")
        self.git("checkout", "-q", "-b", "other")
        self.write("a.py", "x = 1\n")
        self.commit_all("work")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("STOP: no base found for other", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "STOP:")

    def track_origin(self):
        origin = self.temp_root / "own-origin.git"
        self.git("init", "-q", "--bare", "-b", "main", str(origin), cwd=self.temp_root)
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "-u", "origin", "main")

    def test_branch_prep_on_a_tracking_default_branch_lists_the_unpushed_commits(self):
        self.track_origin()
        in_sync = self.flow("branch-prep")
        self.assertEqual(in_sync.returncode, 0, in_sync.stderr)
        self.assertIn("diff is empty", in_sync.stdout)
        self.assertEqual(self.last_line(in_sync)[:5], "STOP:")

        self.write("a.py", "x = 1\n")
        self.commit_all("unpushed")
        ahead = self.flow("branch-prep")
        self.assertIn("base `origin/main` from own-upstream", ahead.stdout)
        self.assertIn("- a.py", ahead.stdout)
        self.assertEqual(self.last_line(ahead)[:5], "NEXT:")

    def test_log_rerun_after_a_new_commit_writes_no_second_row(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "findings": [self.finding(escape=False)]}
        first = self.log("branch", payload)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.write("b.py", "y = 2\ny = 3\n")
        self.commit_all("more")
        self.git("checkout", "-q", "-b", "renamed")
        again = self.log("branch", payload)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("2 already logged, skipped", again.stdout)
        finding_rows = self.finding_rows()
        self.assertEqual(len(finding_rows), 2)

    def test_log_rerun_after_the_input_loses_a_finding_writes_no_second_run_row(self):
        self.branch_with({"a.py": "x = 1\n"})
        two = {"finder": "smell-reviewer", "lane": "code",
               "findings": [self.finding(escape=False), self.finding(escape=False, file="b.py")]}
        first = self.log("branch", two)
        self.assertEqual(first.returncode, 0, first.stderr)
        one = {**two, "findings": two["findings"][:1]}
        again = self.log("branch", one)
        self.assertEqual(again.returncode, 0, again.stderr)
        finding_rows = self.finding_rows()
        run_rows = [row for row in finding_rows if row["kind"] == "run"]
        self.assertEqual(len(run_rows), 1)
        self.assertEqual(len(finding_rows), 3)

    def test_log_audit_target_is_matched_literally_not_as_a_glob(self):
        self.write("mod/[ab].py", "a\nb\nc\n")
        self.write("mod/a.py", "1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
        self.git("add", "-A")
        payload = {"finder": "smell-reviewer", "lane": "code", "target": ["mod/[ab].py"], "findings": []}
        done = self.log("audit", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        finding_rows = self.finding_rows()
        self.assertEqual(finding_rows[0]["diff_loc"], "3")

    def test_log_audit_diff_loc_ignores_relative_config(self):
        config = self.temp_root / "gitconfig"
        config.write_text("[diff]\n\trelative = true\n")
        self.write("pkg/mod/a.py", "a\nb\nc\nd\n")
        self.write("top/b.py", "x\ny\n")
        self.git("add", "-A")
        payload = {"finder": "smell-reviewer", "lane": "code", "target": ["mod", "../top"], "findings": []}
        done = self.log("audit", payload, cwd=self.repo / "pkg", extra_env={"GIT_CONFIG_GLOBAL": str(config)})
        self.assertEqual(done.returncode, 0, done.stderr)
        finding_rows = self.finding_rows()
        self.assertEqual(finding_rows[0]["diff_loc"], "6")

    def test_log_escape_flag_must_be_a_boolean(self):
        self.branch_with({"a.py": "x = 1\n"})
        for escape in ("false", "true", 1, 0, None, []):
            payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                       "findings": [self.finding(escape=escape)]}
            done = self.log("branch", payload)
            self.assertEqual(done.returncode, 1, escape)
            self.assertIn("`escape` must be true or false", done.stderr)
        self.assertEqual(self.escape_rows(), [])

    def test_branch_prep_in_a_repo_with_no_commits_says_head_is_unborn(self):
        unborn = self.temp_root / "unborn"
        unborn.mkdir()
        self.git("init", "-q", "-b", "main", cwd=unborn)
        done = self.flow("branch-prep", cwd=unborn)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("unborn", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "STOP:")
        named = self.flow("branch-prep", "--head", "main", cwd=unborn)
        self.assertEqual(named.returncode, 1)
        self.assertIn("not a commit", named.stderr)

    def test_log_branch_with_no_base_stops_and_writes_nothing(self):
        done = self.log("branch", {"finder": "smell-reviewer", "lane": "code", "findings": []})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.last_line(done)[:5], "STOP:")
        self.assertEqual(self.finding_rows(), [])

    def test_log_orphan_branch_stops_and_writes_nothing(self):
        self.git("checkout", "-q", "--orphan", "lone")
        self.write("a.py", "x = 1\n")
        self.commit_all("lone")
        done = self.log("branch", {"finder": "smell-reviewer", "lane": "code", "findings": []})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("share no history", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "STOP:")
        self.assertEqual(self.escape_rows(), [])
        self.assertEqual(self.finding_rows(), [])

    def test_prep_calls_keep_only_the_newest_fifty_log_input_files(self):
        self.branch_with({"a.py": "x = 1\n"})
        pattern = r"--input (\S*refactor-flow-[0-9a-f]{12}\.json)"
        for index in range(51):
            next_line = self.last_line(self.flow("branch-prep"))
            written = pathlib.Path(re.search(pattern, next_line).group(1))
            self.assertEqual(written.parent, self.log_input_dir)
            written.write_text("{}")
            os.utime(written, (1000 + index, 1000 + index))
        kept = sorted(self.log_input_dir.glob("refactor-flow-*.json"))
        self.assertEqual(len(kept), 50)
        kept_times = sorted(path.stat().st_mtime for path in kept)
        self.assertEqual(kept_times, [1000.0 + index for index in range(1, 51)])

    def test_prep_prune_leaves_files_the_pattern_does_not_match(self):
        self.branch_with({"a.py": "x = 1\n"})
        others = [self.log_input_dir / "notes.json", self.log_input_dir / "refactor-flow-notes.json"]
        for other in others:
            other.write_text("{}")
        for index in range(60):
            (self.log_input_dir / f"refactor-flow-{index:012x}.json").write_text("{}")
        self.flow("branch-prep")
        for other in others:
            self.assertTrue(other.exists(), other.name)
        kept = list(self.log_input_dir.glob("refactor-flow-[0-9a-f]*.json"))
        self.assertEqual(len(kept), 49)

    def test_prune_skips_a_file_deleted_between_the_glob_and_the_stat(self):
        module = load_script_module()
        for index in range(60):
            (self.log_input_dir / f"refactor-flow-{index:012x}.json").write_text("{}")
        vanished = self.log_input_dir / "refactor-flow-ffffffffffff.json"
        listed = [*self.log_input_dir.glob("refactor-flow-*.json"), vanished]
        with mock.patch.object(pathlib.Path, "glob", return_value=listed):
            module.prune_log_inputs(self.log_input_dir)
        kept = list(self.log_input_dir.glob("refactor-flow-*.json"))
        self.assertEqual(len(kept), 49)

    def test_prune_neither_counts_nor_deletes_a_directory_or_symlink_with_a_matching_name(self):
        module = load_script_module()
        directory = self.log_input_dir / "refactor-flow-aaaaaaaaaaaa.json"
        directory.mkdir()
        target = self.temp_root / "precious.json"
        target.write_text("{}")
        link = self.log_input_dir / "refactor-flow-bbbbbbbbbbbb.json"
        link.symlink_to(target)
        for index in range(60):
            (self.log_input_dir / f"refactor-flow-{index:012x}.json").write_text("{}")
        module.prune_log_inputs(self.log_input_dir)
        self.assertTrue(directory.is_dir())
        self.assertTrue(link.is_symlink())
        self.assertTrue(target.exists())
        regular = [path for path in self.log_input_dir.glob("refactor-flow-*.json")
                   if path.is_file() and not path.is_symlink()]
        self.assertEqual(len(regular), 49)

    def test_branch_prep_reports_a_failing_base_helper(self):
        broken = self.temp_root / "broken-base"
        broken.write_text("#!/usr/bin/env bash\necho boom >&2\nexit 2\n")
        done = self.flow("branch-prep", extra_env={"BRANCH_BASE_SCRIPT": str(broken)})
        self.assertEqual(done.returncode, 1)
        self.assertIn("boom", done.stderr)

    def test_branch_prep_survives_diff_relative_config_from_a_subdirectory(self):
        config = self.temp_root / "gitconfig"
        config.write_text("[diff]\n\trelative = true\n")
        self.branch_with({"pkg/a.py": "# TODO here\n", "top.py": "t = 1\n"})
        done = self.flow("branch-prep", cwd=self.repo / "pkg", extra_env={"GIT_CONFIG_GLOBAL": str(config)})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- top.py", done.stdout)
        self.assertIn("- pkg/a.py", done.stdout)

    def test_branch_prep_empty_diff_stops(self):
        self.git("checkout", "-q", "-b", "feature")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0)
        self.assertIn("branch diff is empty", done.stdout)
        self.assertIn("STOP:", done.stdout)
        self.assertNotIn("dispatch prompt", done.stdout)

    def test_branch_prep_falls_back_to_master(self):
        self.git("branch", "-m", "main", "master")
        self.branch_with({"a.py": "x = 1\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("base `master`", done.stdout)

    def test_branch_prep_head_ref_leaves_checkout_alone(self):
        self.branch_with({"a.py": "x = 1\n"})
        self.git("checkout", "-q", "main")
        done = self.flow("branch-prep", "--head", "feature")
        self.assertIn("- a.py", done.stdout)
        self.assertEqual(self.git("branch", "--show-current").strip(), "main")

    def test_branch_prep_fails_loud_outside_repo_and_on_bad_ref(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)
        done = self.flow("branch-prep", cwd=outside.name)
        self.assertEqual(done.returncode, 1)
        self.assertIn("not inside a git repository", done.stderr)
        bad = self.flow("branch-prep", "--head", "nope")
        self.assertEqual(bad.returncode, 1)
        self.assertIn("nope", bad.stderr)

    def test_branch_prep_marker_in_filename_header_is_not_a_match(self):
        self.branch_with({"TODO_notes.txt": "plain\n"})
        done = self.flow("branch-prep")
        self.assertIn("(0 match(es))", done.stdout)

    def test_branch_prep_added_line_that_looks_like_a_file_header_is_still_swept(self):
        self.branch_with({"a.py": "++ TODO in the added text\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("a.py:1 [marker]", done.stdout)

    def test_branch_prep_non_ascii_and_spaced_paths_are_listed_and_swept(self):
        self.branch_with({"café.py": "# TODO accent\n", "a b.py": "# TODO space\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- café.py", done.stdout)
        self.assertIn("- a b.py", done.stdout)
        self.assertIn("café.py:1 [marker]", done.stdout)
        self.assertIn("a b.py:1 [marker]", done.stdout)

    def test_branch_prep_sweeps_paths_git_c_quotes_even_with_quote_path_off(self):
        self.branch_with({'q"uote.py': "# TODO quote\n", "back\\slash.py": "# TODO slash\n",
                         "tab\tname.py": "# TODO tab\n", "plain.py": "# TODO plain\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn('q"uote.py:1 [marker]', done.stdout)
        self.assertIn("back\\slash.py:1 [marker]", done.stdout)
        self.assertIn("tab\tname.py:1 [marker]", done.stdout)
        self.assertIn("(4 match(es))", done.stdout)

    def test_branch_prep_sweeps_a_whole_line_that_holds_a_form_feed_or_lone_carriage_return(self):
        self.branch_with({"a.py": "page = 1\x0c# TODO after the feed\nkept = 2\rprint('after the return')\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("a.py:1 [marker] page = 1\x0c# TODO after the feed", done.stdout)
        # The flow's stdout is read in text mode, which turns the carriage return into a newline.
        self.assertIn("a.py:2 [marker] kept = 2\nprint('after the return')", done.stdout)

    def test_branch_prep_survives_user_git_config(self):
        config = self.temp_root / "gitconfig"
        config.write_text("[diff]\n\tnoprefix = true\n\texternal = /bin/false\n[core]\n\tquotePath = true\n"
                          "[color]\n\tui = always\n[diff \"one\"]\n\ttextconv = /bin/echo\n")
        self.branch_with({"café.py": "# TODO accent\n", "a.py": "# TODO plain\n", ".gitattributes": "*.py diff=one\n"})
        done = self.flow("branch-prep", extra_env={"GIT_CONFIG_GLOBAL": str(config)})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("(2 match(es))", done.stdout)
        self.assertIn("café.py:1 [marker]", done.stdout)

    def test_branch_prep_labels_deleted_renamed_and_binary_files(self):
        self.write("old.py", "old = 1\n")
        self.commit_all("add old")
        self.git("checkout", "-q", "-b", "feature")
        self.git("rm", "-q", "old.py")
        self.git("mv", "README.md", "NOTES.md")
        self.write_bytes("blob.dat", b"\x00\x01\n\n\n")
        self.commit_all("work")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- old.py (deleted)", done.stdout)
        self.assertIn("- NOTES.md (renamed from README.md)", done.stdout)
        self.assertIn("- blob.dat (binary)", done.stdout)

    def test_branch_prep_orphan_branch_stops_with_no_shared_history(self):
        self.git("checkout", "-q", "--orphan", "lone")
        self.write("a.py", "x = 1\n")
        self.commit_all("lone")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("STOP:", done.stdout)
        self.assertIn("share no history", done.stdout)
        self.assertIn("--base", done.stdout)

    def test_branch_prep_stale_local_main_does_not_pull_teammate_code_into_scope(self):
        origin = self.temp_root / "origin.git"
        self.git("init", "-q", "--bare", "-b", "main", str(origin), cwd=self.temp_root)
        self.git("remote", "add", "origin", str(origin))
        self.git("push", "-q", "-u", "origin", "main")
        self.git("remote", "set-head", "origin", "main")
        mate = self.temp_root / "mate"
        self.git("clone", "-q", str(origin), str(mate), cwd=self.temp_root)
        (mate / "teammate.py").write_text("t = 1\n")
        self.git("add", "-A", cwd=mate)
        self.git("commit", "-q", "-m", "teammate", cwd=mate)
        self.git("push", "-q", "origin", "main", cwd=mate)
        self.branch_with({"a.py": "x = 1\n"})
        self.git("fetch", "-q", "origin")
        self.git("merge", "-q", "--no-edit", "origin/main")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("base `origin/main`", done.stdout)
        self.assertIn("- a.py", done.stdout)
        self.assertNotIn("teammate.py", done.stdout)

    def test_branch_prep_upstream_beats_main(self):
        self.git("branch", "develop")
        self.git("checkout", "-q", "develop")
        self.write("dev.py", "d = 1\n")
        self.commit_all("develop work")
        self.git("checkout", "-q", "-b", "feature")
        self.git("branch", "--set-upstream-to=develop")
        self.write("a.py", "x = 1\n")
        self.commit_all("work")
        done = self.flow("branch-prep")
        self.assertIn("base `develop` from upstream", done.stdout)
        self.assertNotIn("dev.py", done.stdout)

    def test_branch_prep_from_subdirectory_lists_root_relative_paths(self):
        self.branch_with({"pkg/a.py": "# TODO here\n"})
        done = self.flow("branch-prep", cwd=self.repo / "pkg")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- pkg/a.py", done.stdout)
        self.assertIn("pkg/a.py:1 [marker]", done.stdout)

    # -------------------------------------------------------------- audit-prep
    def test_audit_prep_lists_real_jscpd_clones_inside_the_prompt_with_target_prefixed_paths(self):
        self.write("src/a.js", "x = 1\n")
        self.write("src/sub dir/b copy.js", "x = 1\n")
        self.git("add", "-A")
        stub = self.temp_root / "jscpd_real_output.py"
        stub.write_text(f"import sys\nsys.stdout.write({JSCPD_REAL!r})\n")
        done = self.flow("audit-prep", "src", extra_env={"REFACTOR_JSCPD_CMD": f"{sys.executable} {stub}"})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("\x1b", done.stdout)
        prompt = done.stdout.split("dispatch prompt", 1)[1]
        self.assertIn("Clone found (javascript)", prompt)
        self.assertIn("- src/a.js [1:1 - 48:2]", prompt)
        self.assertIn("- src/sub dir/b copy.js [1:1 - 48:2]", prompt)
        self.assertNotIn("export function step0", done.stdout)
        self.assertNotIn("jscpd output above", done.stdout)
        self.assertIn("anti-churn line", prompt)
        self.assertEqual(self.last_line(done)[:5], "NEXT:")

    def test_audit_prep_detector_failure_is_a_note_not_a_stop(self):
        self.write("src/a.py", "x = 1\n")
        self.git("add", "-A")
        failing = self.temp_root / "fail_stub.py"
        failing.write_text("import sys\nsys.exit(3)\n")
        done = self.flow("audit-prep", "src", extra_env={"REFACTOR_JSCPD_CMD": f"{sys.executable} {failing}"})
        self.assertEqual(done.returncode, 0)
        self.assertIn("no mechanical detection — agent prior-art search only", done.stdout)
        self.assertNotIn("anti-churn line", done.stdout)

    def test_audit_prep_cuts_the_clone_list_at_a_pair_boundary_and_counts_the_rest(self):
        self.write("src/a.js", "x = 1\n")
        self.git("add", "-A")
        output = "".join(f"Clone found (javascript)\n - a{i}.js [1:1 - 5:2]\n   b{i}.js [1:1 - 5:2]\n"
                         for i in range(55))
        stub = self.temp_root / "many_clones.py"
        stub.write_text(f"import sys\nsys.stdout.write({output!r})\n")
        done = self.flow("audit-prep", "src", extra_env={"REFACTOR_JSCPD_CMD": f"{sys.executable} {stub}"})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("55 clone pair(s); 40 listed", done.stdout)
        self.assertEqual(done.stdout.count("Clone found"), 40)
        self.assertEqual(done.stdout.count("- src/a"), 40)
        self.assertEqual(done.stdout.count("- src/b"), 40)
        self.assertIn("15 more pair(s) not listed", done.stdout)

    def test_audit_prep_splits_the_detector_command_like_a_shell(self):
        self.write("src/a.js", "x = 1\n")
        self.git("add", "-A")
        spaced_dir = self.temp_root / "dir with space"
        spaced_dir.mkdir()
        stub = spaced_dir / "stub.py"
        stub.write_text(f"import sys\nsys.stdout.write({JSCPD_REAL!r})\n")
        done = self.flow("audit-prep", "src",
                         extra_env={"REFACTOR_JSCPD_CMD": f"{sys.executable} '{stub}'"})
        self.assertIn("1 clone pair(s)", done.stdout)

    def test_audit_prep_untracked_target_stops(self):
        done = self.flow("audit-prep", "nothing-here")
        self.assertEqual(done.returncode, 0)
        self.assertIn("STOP:", done.stdout)

    # ----------------------------------------------------------- simplify-prep
    def test_simplify_prep_splits_over_25_files(self):
        for index in range(30):
            self.write(f"mod/f{index:02d}.py", "x = 1\n")
        self.git("add", "-A")
        first = self.flow("simplify-prep", "mod")
        self.assertIn("slice 1 of 2 (25 files)", first.stdout)
        self.assertIn("mod/f00.py", first.stdout)
        self.assertNotIn("mod/f29.py", first.stdout)
        second = self.flow("simplify-prep", "mod", "--slice", "2")
        self.assertIn("mod/f29.py", second.stdout)
        self.assertNotIn("mod/f00.py", second.stdout)
        out_of_range = self.flow("simplify-prep", "mod", "--slice", "3")
        self.assertEqual(out_of_range.returncode, 1)

    def test_simplify_prep_small_target_has_no_split_and_prompt_has_oracle(self):
        self.write("mod/a.py", "x = 1\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", "mod")
        self.assertNotIn("split into", done.stdout)
        self.assertIn("oracle and magnitude floor", done.stdout)
        self.assertIn("do NOT read the files", done.stdout)

    def test_simplify_prep_names_a_missing_target_in_a_multi_target_call(self):
        self.write("mod/a.py", "x = 1\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", "mod", "ghost")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("STOP:", done.stdout)
        self.assertIn("ghost", done.stdout)
        self.assertNotIn("dispatch prompt", done.stdout)

    def test_simplify_prep_lists_non_ascii_and_spaced_files_and_dedupes_overlap(self):
        self.write("mod/café.py", "x = 1\n")
        self.write("mod/a b.py", "x = 1\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", "mod", "mod/café.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.count("- mod/café.py"), 1)
        self.assertIn("- mod/a b.py", done.stdout)
        self.assertIn("(2 tracked file(s))", done.stdout)

    # --------------------------------------------------------------------- log
    def test_log_branch_writes_escape_finder_and_handoff(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {
            "finder": "smell-reviewer", "lane": "code",
            "findings": [self.finding(), self.finding(file="b.py", line=0, desc="second", escape=False,
                                                      disposition="ask", actioned="ask")],
            "guards": {"duplication": "convention"},
            "handoff": self.handoff_input(tests_run="pytest → exit 0", files=[{"path": "a.py",
                                                                              "change": "merged parse"}]),
            "modifier": "+fast",
        }
        done = self.log("branch", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        escapes = self.escape_rows()
        self.assertEqual(len(escapes), 1)
        self.assertEqual(escapes[0]["stage_found"], "refactor")
        self.assertEqual(escapes[0]["gate_missed"], "review")
        self.assertEqual(escapes[0]["guard"], "convention")
        self.assertEqual(escapes[0]["class"], "duplication")
        self.assertNotIn("desc", escapes[0])
        self.assertEqual(escapes[0]["line"], "3")
        finding_rows = self.finding_rows()
        run_row = next(row for row in finding_rows if row["kind"] == "run")
        self.assertEqual(run_row["gate"], "smell-reviewer")
        self.assertEqual(run_row["scope"], "branch-exit")
        self.assertEqual(run_row["n_findings"], "2")
        self.assertEqual(run_row["diff_loc"], "1")
        self.assertEqual(run_row["result"], "NEEDS_CHANGES")
        self.assertEqual(len([row for row in finding_rows if row["kind"] == "finding"]), 2)
        self.assertIn("  iter: 0", done.stdout)
        self.assertIn("- path: a.py", done.stdout)
        self.assertIn("modifier `+fast`", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "NEXT:")
        self.assertIn("Skill-invoke /review", self.last_line(done))

    def test_log_escape_row_without_a_line_carries_no_line_field(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "findings": [self.finding(line=0)]}
        done = self.log("branch", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("line", self.escape_rows()[0])

    def test_log_writes_no_escape_row_while_the_telemetry_switch_is_off(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "findings": [self.finding()]}
        done = self.log("branch", payload, extra_env={"CLAUDE_TOOLKIT_TELEMETRY": "0"})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([row["kind"] for row in self.finding_rows()], ["run", "finding"])
        self.assertEqual(self.escape_rows(), [])

    def test_log_empty_handed_still_writes_run_row(self):
        self.branch_with({"a.py": "x = 1\n"})
        done = self.log("branch", {"finder": "smell-reviewer", "lane": "code", "findings": []})
        self.assertEqual(done.returncode, 0, done.stderr)
        finding_rows = self.finding_rows()
        self.assertEqual(len(finding_rows), 1)
        self.assertEqual(finding_rows[0]["n_findings"], "0")
        self.assertEqual(finding_rows[0]["result"], "PASS")
        self.assertEqual(self.escape_rows(), [])

    def test_log_missing_guard_writes_nothing(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "findings": [self.finding()], "guards": {}}
        done = self.log("branch", payload)
        self.assertEqual(done.returncode, 1)
        self.assertIn("needs guards", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        self.assertEqual(self.finding_rows(), [])

    def test_log_one_guard_serves_a_whole_class_group(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"smell": "none"},
                   "findings": [self.finding(**{"class": "smell"}), self.finding(**{"class": "smell"}, file="c.py")]}
        done = self.log("branch", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([row["guard"] for row in self.escape_rows()], ["none", "none"])

    def test_log_rejects_bad_shapes_and_writes_nothing(self):
        self.branch_with({"a.py": "x = 1\n"})
        bad_findings = ({"class": ""}, {"desc": "two\nlines"}, {"line": "3"}, {"line": True},
                        {"severity": None})
        for override in bad_findings:
            payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                       "findings": [self.finding(**override)]}
            done = self.log("branch", payload)
            self.assertEqual(done.returncode, 1, override)
        missing_lane = {"finder": "smell-reviewer", "findings": []}
        self.assertEqual(self.log("branch", missing_lane).returncode, 1)
        self.assertEqual(self.finding_rows(), [])
        self.assertEqual(self.escape_rows(), [])

    def test_log_writes_a_file_path_with_spaces_whole_into_both_logs(self):
        self.branch_with({"a.py": "x = 1\n"})
        spaced = "src/my dir/a b.py"
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "findings": [self.finding(file=spaced)]}
        done = self.log("branch", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([row["path_key"] for row in self.escape_rows()], [spaced])
        finding_files = [row["path_key"] for row in self.finding_rows() if row["kind"] == "finding"]
        self.assertEqual(finding_files, [spaced])

    def test_log_refuses_a_file_path_that_would_swallow_a_second_field(self):
        self.branch_with({"a.py": "x = 1\n"})
        swallowing = ("a.py lane=code", "a.py\tlane=code", "a b.py severity=high")
        for file in swallowing:
            payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                       "findings": [self.finding(file=file)]}
            done = self.log("branch", payload)
            self.assertEqual(done.returncode, 1, file)
            self.assertIn("`file` must not contain a space followed by `name=`", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        self.assertEqual(self.finding_rows(), [])

    def test_log_refuses_a_file_path_with_a_line_break(self):
        self.branch_with({"a.py": "x = 1\n"})
        for file in ("a.py\nb.py", "a.py\rb.py"):
            payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                       "findings": [self.finding(file=file)]}
            done = self.log("branch", payload)
            self.assertEqual(done.returncode, 1, repr(file))
            self.assertIn("`file` must be one line", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        self.assertEqual(self.finding_rows(), [])

    def log_writers(self, telemetry="1"):
        """Each log writer as (name, run(*extra), logged rows), so one rule is asserted against both."""
        escape_writer = LOG_ESCAPE
        finding_writer = os.environ.get("REFACTOR_LOG_FINDING") or str(
            pathlib.Path(REAL_CLAUDE_DIR) / "skills" / "review" / "log-review-finding")
        env = {**os.environ, "HOME": str(self.home), "CLAUDE_TOOLKIT_TELEMETRY": telemetry,
               "REVIEW_ESCAPES_FILE": str(self.escapes), **self.ledger_env}
        escape_base = ["stage_found=refactor", "gate_missed=review", "class=smell", "severity=low", "guard=none"]
        finding_base = ["kind=finding", "gate=smell-reviewer", "lane=code", "scope=standalone", "phase=-", "iter=0",
                        "disposition=fix", "class=smell", "line=1", "actioned=none"]

        def runner(writer, base):
            def run(*extra):
                return subprocess.run(["bash", writer, *base, *extra], env=env, cwd=self.repo,
                                      capture_output=True, text=True)
            return run

        return [("log-escape", runner(escape_writer, escape_base),
                 lambda: [{**row, "file": row["path_key"]} for row in self.escape_rows()]),
                ("log-review-finding", runner(finding_writer, finding_base),
                 lambda: [{**row, "file": row["path_key"]} for row in self.finding_rows()])]

    def test_log_writers_refuse_a_space_in_any_value_but_free_text_and_a_clean_file_path(self):
        for name, run, rows in self.log_writers():
            for pair in ("lane=two words", "severity=very high", "file=a.py lane=code"):
                self.assertEqual(run(pair).returncode, 1, f"{name} {pair}")
            self.assertEqual(rows(), [], name)
            done = run("file=a b.py", "desc=free text, with spaces")
            self.assertEqual(done.returncode, 0, f"{name} {done.stderr}")
            self.assertEqual(rows()[0]["file"], "a b.py", name)

    def test_log_review_finding_with_an_out_redirect_sends_one_row_while_the_switch_is_on_and_none_while_off(self):
        run_on = {name: run for name, run, _ in self.log_writers()}["log-review-finding"]
        run_off = {name: run for name, run, _ in self.log_writers("0")}["log-review-finding"]
        sink = self.temp_root / "sink.jsonl"
        on = run_on("file=a.py", f"out={sink}")
        self.assertEqual(on.returncode, 0, on.stderr)
        finding_rows = fake_ledger.recorded_rows(self.ledger_env)
        self.assertEqual([row["_type"] for row in finding_rows], ["review_finding"])
        self.assertEqual(finding_rows[0]["path_key"], "a.py")
        off = run_off("file=a.py", f"out={sink}")
        self.assertEqual(off.returncode, 0, off.stderr)
        self.assertEqual(len(fake_ledger.recorded_rows(self.ledger_env)), 1)

    def test_log_writers_refuse_a_file_path_with_whitespace_then_a_name_or_a_line_break(self):
        swallowing = ("a.py\tlane=code", "a.py\nlane=code", "a.py\rb.py", "a.py\nb.py", "a.py \tlane=code")
        for name, run, rows in self.log_writers():
            for file in swallowing:
                done = run(f"file={file}", "desc=x")
                self.assertEqual(done.returncode, 1, f"{name} {file!r}")
                self.assertIn("file= holds a line break or whitespace then a name=", done.stderr, f"{name} {file!r}")
            self.assertEqual(rows(), [], name)

    def test_log_reports_a_ledger_refusal_and_a_rerun_writes_only_the_missing_rows(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "vibes"},
                   "findings": [self.finding()]}
        refusing = self.temp_root / "refusing-escape-writer"
        refusing.write_text(f'#!/usr/bin/env bash\nFAKE_LEDGER_WRITE_EXIT=2 exec "{LOG_ESCAPE}" "$@"\n')
        first = self.log("branch", payload, extra_env={"REFACTOR_LOG_ESCAPE": str(refusing)})
        self.assertEqual(first.returncode, 2)
        self.assertRegex(first.stdout, r"writer refused \d+ row\(s\), tell the user which")
        self.assertEqual(first.stdout.count("NEXT:"), 1)
        self.assertIn("no handoff given", self.last_line(first))
        self.assertEqual(self.escape_rows(), [])
        self.assertEqual(sorted(row["kind"] for row in self.finding_rows()), ["finding", "run"])

        second = self.log("branch", payload)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("2 already logged, skipped", second.stdout)
        escape_rows = self.escape_rows()
        self.assertEqual(len(escape_rows), 1)
        self.assertEqual(escape_rows[0]["guard"], "vibes")
        finding_rows = self.finding_rows()
        self.assertEqual(sorted(row["kind"] for row in finding_rows), ["finding", "run"])
        self.assertEqual([row["class"] for row in finding_rows if row["kind"] == "finding"], ["duplication"])

    def test_log_run_twice_writes_nothing_the_second_time(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "findings": [self.finding()], "handoff": self.handoff_input()}
        first = self.log("branch", payload)
        self.assertEqual(first.returncode, 0, first.stderr)
        escape_rows = self.escape_rows()
        finding_rows = self.finding_rows()
        escape_count = len(escape_rows)
        finding_count = len(finding_rows)
        self.assertEqual((escape_count, finding_count), (1, 2))
        second = self.log("branch", payload)
        self.assertEqual(second.returncode, 0, second.stderr)
        escape_rows_after = self.escape_rows()
        finding_rows_after = self.finding_rows()
        self.assertEqual(len(escape_rows_after), escape_count)
        self.assertEqual(len(finding_rows_after), finding_count)
        self.assertIn("3 already logged, skipped", second.stdout)
        self.assertIn("handoff:", second.stdout)

    def test_log_writer_failure_after_earlier_rows_still_hands_off_and_keeps_the_earlier_rows(self):
        self.branch_with({"a.py": "x = 1\n"})
        failing = self.temp_root / "failing-writer"
        failing.write_text("#!/usr/bin/env bash\nexit 7\n")
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "findings": [self.finding()], "handoff": self.handoff_input()}
        done = self.log("branch", payload, extra_env={"REFACTOR_LOG_FINDING": str(failing)})
        self.assertEqual(done.returncode, 2)
        self.assertIn("writer refused", done.stderr)
        self.assertIn("handoff:", done.stdout)
        self.assertEqual(done.stdout.count("NEXT:"), 1)
        self.assertIn("writer refused 2 row(s), tell the user which", done.stdout)
        self.assertIn("Skill-invoke /review", self.last_line(done))
        escape_rows = self.escape_rows()
        self.assertEqual(len(escape_rows), 1)

    def test_log_audit_refusal_does_not_point_at_review(self):
        self.write("src/a.py", "a\n")
        self.git("add", "-A")
        failing = self.temp_root / "failing-writer"
        failing.write_text("#!/usr/bin/env bash\nexit 7\n")
        payload = {"finder": "smell-reviewer", "lane": "code", "target": ["src"], "findings": []}
        done = self.log("audit", payload, extra_env={"REFACTOR_LOG_FINDING": str(failing)})
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stdout.count("NEXT:"), 1)
        self.assertIn("No coders, no /review", self.last_line(done))

    def test_log_same_rows_from_a_new_input_file_are_written_again(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "findings": []}
        self.assertEqual(self.log("branch", payload).returncode, 0)
        again = self.flow("log", "--mode", "branch", "--input", self.log_input(payload, "second-run.json"))
        self.assertEqual(again.returncode, 0, again.stderr)
        rows_after_new_file = self.finding_rows()
        self.assertEqual(len(rows_after_new_file), 2)
        same_file = self.log("branch", payload)
        self.assertIn("1 already logged, skipped", same_file.stdout)
        rows_after_same_file = self.finding_rows()
        self.assertEqual(len(rows_after_same_file), 2)

    def test_log_state_keeps_one_entry_per_input_path_and_a_bounded_number_of_paths(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "findings": []}
        for index in range(55):
            done = self.flow("log", "--mode", "branch", "--input", self.log_input(payload, f"run-{index}.json"))
            self.assertEqual(done.returncode, 0, done.stderr)
        state = json.loads((self.home / ".claude" / "state" / "refactor-flow" / "written-rows.json").read_text())
        self.assertEqual(len(state), 50)
        self.assertNotIn(str((self.temp_root / "run-0.json").resolve()), state)
        self.assertIn(str((self.temp_root / "run-54.json").resolve()), state)

    def test_log_targeted_refuses_a_finder(self):
        done = self.log("targeted", {"finder": "smell-reviewer", "lane": "code", "findings": [],
                                     "handoff": self.handoff_input()})
        self.assertEqual(done.returncode, 1)
        self.assertIn("finder", done.stderr)
        self.assertEqual(self.finding_rows(), [])

    def test_log_refuses_a_finder_that_is_not_a_string(self):
        for finder in (["smell-reviewer"], {"a": 1}, 7):
            done = self.log("branch", {"finder": finder, "lane": "code", "findings": []})
            self.assertEqual(done.returncode, 1, finder)
            self.assertIn("`finder` must be one of", done.stderr)

    def test_log_target_that_matches_no_tracked_file_exits_1_and_writes_nothing(self):
        self.write("src/a.py", "a\n")
        self.git("add", "-A")
        for mode, finder in (("audit", "smell-reviewer"), ("simplify", "complexity-reviewer")):
            payload = {"finder": finder, "lane": "code", "target": ["src", "ghost"], "findings": []}
            done = self.log(mode, payload)
            self.assertEqual(done.returncode, 1, mode)
            self.assertIn("ghost", done.stderr)
        self.assertEqual(self.finding_rows(), [])

    def test_log_works_in_a_sha256_repository(self):
        probe = subprocess.run(["git", "init", "-q", "--object-format=sha256", str(self.temp_root / "probe")],
                               capture_output=True, text=True)
        if probe.returncode != 0:
            self.skipTest("this git has no sha256 object format")
        sha256_repo = self.temp_root / "sha256repo"
        sha256_repo.mkdir()
        self.git("init", "-q", "--object-format=sha256", "-b", "main", cwd=sha256_repo)
        (sha256_repo / "src").mkdir()
        (sha256_repo / "src" / "a.py").write_text("a\nb\n")
        self.git("add", "-A", cwd=sha256_repo)
        payload = {"finder": "smell-reviewer", "lane": "code", "target": ["src"], "findings": []}
        done = self.log("audit", payload, cwd=sha256_repo)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "2")

    def test_log_simplify_escape_error_names_the_finding(self):
        self.write("mod/a.py", "a\n")
        self.git("add", "-A")
        payload = {"finder": "complexity-reviewer", "lane": "code", "target": ["mod"],
                   "guards": {"smell": "type"}, "findings": [self.finding(**{"class": "smell"})]}
        done = self.log("simplify", payload)
        self.assertEqual(done.returncode, 1)
        self.assertIn("findings[0]: simplify escape rows must be class=complexity", done.stderr)

    def test_log_works_in_a_repo_whose_directory_name_has_a_space(self):
        spaced = self.make_repo("my repo")
        self.git("checkout", "-q", "-b", "feature", cwd=spaced)
        (spaced / "a.py").write_text("x = 1\n")
        self.git("add", "-A", cwd=spaced)
        self.git("commit", "-q", "-m", "work", cwd=spaced)
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "findings": [self.finding()], "handoff": self.handoff_input()}
        done = self.log("branch", payload, cwd=spaced)
        self.assertEqual(done.returncode, 0, done.stderr)
        escape_rows = self.escape_rows()
        finding_rows = self.finding_rows()
        self.assertEqual(len(escape_rows), 1)
        self.assertEqual(len(finding_rows), 2)
        self.assertIn("handoff:", done.stdout)

    def test_log_multi_line_plan_impact_uses_the_block_form(self):
        payload = {"findings": [], "handoff": self.handoff_input(plan_impact="first line\nsecond line")}
        done = self.log("targeted", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("  plan_impact: |\n    first line\n    second line\n  iter: 0", done.stdout)

    def test_log_rejects_a_newline_in_a_handoff_scalar(self):
        for handoff in (self.handoff_input(files=[{"path": "a.py", "change": "two\nlines"}]),
                        self.handoff_input(tests_run="a\nb"), self.handoff_input(flagged="a\nb")):
            done = self.log("targeted", {"findings": [], "handoff": handoff})
            self.assertEqual(done.returncode, 1)
            self.assertIn("one line", done.stderr)

    def test_log_audit_has_no_escape_rows_and_no_handoff(self):
        self.write("src/a.py", "a\nb\nc\n")
        self.write_bytes("src/blob.dat", b"\x00\n\n\n\n\n")
        self.git("add", "-A")
        payload = {"finder": "smell-reviewer", "lane": "code", "target": ["src"],
                   "findings": [self.finding(escape=False)]}
        done = self.log("audit", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        run_row = next(row for row in self.finding_rows() if row["kind"] == "run")
        self.assertEqual(run_row["scope"], "standalone")
        self.assertEqual(run_row["diff_loc"], "3")
        self.assertEqual(self.escape_rows(), [])
        self.assertIn("No coders, no /review", done.stdout)
        with_handoff = {**payload, "handoff": self.handoff_input()}
        self.assertEqual(self.log("audit", with_handoff).returncode, 1)
        escape_in_audit = {**payload, "guards": {"duplication": "none"}, "findings": [self.finding()]}
        self.assertEqual(self.log("audit", escape_in_audit).returncode, 1)

    def test_log_audit_diff_loc_from_a_subdirectory_counts_the_target_files(self):
        self.write("pkg/mod/a.py", "a\nb\nc\nd\n")
        self.git("add", "-A")
        payload = {"finder": "smell-reviewer", "lane": "code", "target": ["mod"], "findings": []}
        done = self.log("audit", payload, cwd=self.repo / "pkg")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "4")

    def test_log_audit_requires_target(self):
        done = self.log("audit", {"finder": "smell-reviewer", "lane": "code", "findings": []})
        self.assertEqual(done.returncode, 1)
        self.assertIn("`target`", done.stderr)

    def test_log_simplify_escape_must_be_complexity(self):
        self.write("mod/a.py", "a\n")
        self.git("add", "-A")
        base = {"finder": "complexity-reviewer", "lane": "code", "target": ["mod"],
                "guards": {"complexity": "type"}}
        good = {**base, "findings": [self.finding(**{"class": "complexity"})]}
        done = self.log("simplify", good)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.escape_rows()[0]["class"], "complexity")
        bad = {**base, "guards": {"smell": "type"}, "findings": [self.finding(**{"class": "smell"})]}
        self.assertEqual(self.log("simplify", bad).returncode, 1)

    def test_sliced_simplify_then_log_counts_only_the_slice_files(self):
        for index in range(30):
            self.write(f"mod/f{index:02d}.py", "x = 1\ny = 2\n")
        self.git("add", "-A")
        prep = self.flow("simplify-prep", "mod", "--slice", "2")
        slice_files = [line[2:] for line in prep.stdout.splitlines() if line.startswith("- mod/")]
        self.assertEqual(len(slice_files), 5)
        payload = {"finder": "complexity-reviewer", "lane": "code", "target": slice_files, "findings": []}
        done = self.log("simplify", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "10")

    def test_log_targeted_without_finder_writes_only_the_handoff(self):
        payload = {"findings": [], "handoff": self.handoff_input()}
        done = self.log("targeted", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows(), [])
        self.assertIn("handoff:", done.stdout)

    def test_log_without_handoff_points_at_the_handoff_verb_and_that_verb_writes_nothing(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "findings": []}
        logged = self.log("branch", payload)
        self.assertIn("handoff --input", self.last_line(logged))
        self.assertNotIn("re-run `log`", self.last_line(logged))
        rows_before = self.finding_rows()

        with_handoff = {**payload, "handoff": self.handoff_input(), "modifier": "+deep"}
        done = self.flow("handoff", "--input", self.log_input(with_handoff))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("handoff:", done.stdout)
        self.assertIn("modifier `+deep`", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "NEXT:")
        self.assertEqual(self.finding_rows(), rows_before)
        self.assertEqual(self.escape_rows(), [])

    def test_handoff_verb_requires_a_handoff(self):
        done = self.flow("handoff", "--input", self.log_input({"findings": []}))
        self.assertEqual(done.returncode, 1)
        self.assertIn("handoff", done.stderr)

    def test_log_unreadable_input_fails_loud(self):
        done = self.flow("log", "--mode", "branch", "--input", str(self.temp_root / "missing.json"))
        self.assertEqual(done.returncode, 1)

    # -------------------------------------------------------------------- walk
    def test_walk_every_state_and_verb_ends_with_next_or_stop(self):
        empty_log = {"finder": "smell-reviewer", "lane": "code", "findings": []}
        targeted_log = {"findings": [], "handoff": self.handoff_input()}
        def push_feature():
            origin = self.temp_root / "walk-origin.git"
            self.git("init", "-q", "--bare", "-b", "main", str(origin), cwd=self.temp_root)
            self.git("remote", "add", "origin", str(origin))
            self.git("push", "-q", "origin", "main")
            self.git("push", "-q", "-u", "origin", "feature")

        def checkout_orphan():
            self.git("checkout", "-q", "--orphan", "lone")
            self.write("lone.py", "z = 1\n")
            self.commit_all("lone")

        cases = [("clean main", None),
                 ("feature branch", lambda: self.branch_with({"feature.py": "x = 1\n"})),
                 ("pushed feature branch", push_feature),
                 ("orphan branch", checkout_orphan)]
        for state, setup in cases:
            if setup:
                setup()
            self.write("src/a.py", "x = 1\n")
            self.git("add", "-A")
            verbs = [
                ("branch-prep",),
                ("audit-prep", "src"),
                ("audit-prep", "ghost"),
                ("simplify-prep", "src"),
                ("simplify-prep", "src", "ghost"),
                ("log", "--mode", "branch", "--input", self.log_input(empty_log, "empty.json")),
                ("log", "--mode", "targeted", "--input", self.log_input(targeted_log, "targeted.json")),
                ("handoff", "--input", self.log_input(targeted_log, "targeted.json")),
            ]
            for verb in verbs:
                done = self.flow(*verb, extra_env={"REFACTOR_JSCPD_CMD": "/nonexistent-jscpd"})
                label = f"{state}: {' '.join(verb[:4])}"
                self.assertEqual(done.returncode, 0, f"{label}: {done.stderr}")
                self.assertRegex(self.last_line(done), r"^(NEXT|STOP): ", label)

            if state == "pushed feature branch":
                pushed = self.flow("branch-prep")
                self.assertIn("- feature.py", pushed.stdout)
                self.assertIn("base `origin/main`", pushed.stdout)

            # a second pass over the log verbs repeats no row and still ends.
            findings_before = self.finding_rows()
            escapes_before = self.escape_rows()
            for verb in verbs[-3:]:
                done = self.flow(*verb)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertRegex(self.last_line(done), r"^(NEXT|STOP): ")
            self.assertEqual(findings_before, self.finding_rows())
            self.assertEqual(escapes_before, self.escape_rows())


if __name__ == "__main__":
    unittest.main()
