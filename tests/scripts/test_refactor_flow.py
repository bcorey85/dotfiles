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

import fake_jscpd
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

# The duplicate a real jscpd 5.4.3 JSON report holds for src/a.js and "src/sub dir/b copy.js": names are
# relative to the target, and one name has a space.
JSCPD_REAL = [fake_jscpd.duplicate(("a.js", 1, 48), ("sub dir/b copy.js", 1, 48), "javascript")]


def load_script_module():
    loader = importlib.machinery.SourceFileLoader("refactor_flow_under_test", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def prune_log_inputs(folder):
    load_script_module()  # puts the scripts folder on sys.path
    import flow_common
    flow_common.prune_log_inputs(folder)


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
            # No test reaches the real jscpd (npx) unless it names a stub.
            "REFACTOR_JSCPD_CMD": "/nonexistent-jscpd",
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
               "desc": "same parse twice", "severity": "medium", "escape": True, "miss_reason": "overlooked"}
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
        merge_base = self.git("merge-base", "main", "HEAD").strip()
        self.assertIn(f"`git diff {merge_base}`", done.stdout)
        self.assertIn("cross-phase smells", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "NEXT:")

    def test_branch_prep_hands_the_plan_structure_and_deviations_to_the_smell_reviewer(self):
        # The shape of real /code plans: Changes Required entries with **File**: lines, and a Plan Deviations
        # section that records a re-export the plan kept on purpose.
        plan = ("# Plan\n\n## Phase Status\n\n- [x] Phase 1: package\n\n## Phase 1: package\n\n"
                "### Changes Required:\n\n#### 1. Re-exports\n\n**File**: `pkg/__init__.py`\n\n"
                "Re-export `parse` and `render` from the package root.\n\n"
                "## Plan Deviations\n\n- 2026-10-30, Phase 1: keep the `render` re-export though one caller "
                "uses it. Owner: the user.\n")
        self.branch_with({"pkg/__init__.py": "from .core import parse, render\n",
                          "docs/plans/T-1-pkg/spec.md": plan})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        prompt = done.stdout.split("## smell-reviewer dispatch prompt", 1)[1].split("\nNEXT:", 1)[0]
        self.assertIn("## Plan-required structure (`docs/plans/T-1-pkg/spec.md`)", prompt)
        self.assertIn("- pkg/__init__.py", prompt)
        self.assertIn("keep the `render` re-export though one caller uses it", prompt)
        self.assertIn("`### Ask` with the `[plan-structure]` tag, never under `### Fix`", prompt)
        self.assertIn("`plan_structure: true`", self.last_line(done))

    def test_branch_prep_without_a_plan_on_the_branch_prints_no_plan_section(self):
        self.branch_with({"a.py": "x = 1\n"})
        done = self.flow("branch-prep")
        self.assertNotIn("Plan-required structure", done.stdout)
        self.assertNotIn("[plan-structure]` tag", done.stdout)

    def test_log_refuses_a_plan_structure_finding_logged_as_a_fix(self):
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "convention"}}
        for disposition, actioned in (("fix", "fixed"), ("ask", "fixed"), ("fix", "none")):
            with self.subTest(disposition=disposition, actioned=actioned):
                finding = self.finding(disposition=disposition, actioned=actioned, plan_structure=True)
                done = self.log("branch", {**payload, "findings": [finding]})
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn("[plan-structure]", done.stderr)
        with self.subTest("a fix finding with a valid ruled_by"):
            ruled = self.finding(disposition="fix", actioned="fixed", plan_structure=True, escape=False,
                                 ruled_by="user")
            done = self.log("branch", {**payload, "findings": [ruled]})
            self.assertEqual(done.returncode, 1, done.stdout)
            self.assertIn("[plan-structure]", done.stderr)
        asked = self.finding(disposition="ask", actioned="ask", plan_structure=True)
        done = self.log("branch", {**payload, "findings": [asked]}, extra_env=None)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_log_refuses_an_escape_finding_with_a_missing_or_unlisted_miss_reason(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"}}
        for reason in (None, "unknown", "", "lazy", 3):
            with self.subTest(reason=reason):
                finding = self.finding(miss_reason=reason)
                done = self.log("branch", {**payload, "findings": [finding]})
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn("miss_reason", done.stderr)
        missing = {key: value for key, value in self.finding().items() if key != "miss_reason"}
        done = self.log("branch", {**payload, "findings": [missing]})
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("`miss_reason`", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        with self.subTest("a valid finding beside a refused escape row"):
            valid = self.finding(escape=False, file="valid.py")
            lazy = self.finding(miss_reason="lazy", file="lazy.py")
            done = self.log("branch", {**payload, "findings": [valid, lazy]})
            self.assertEqual(done.returncode, 1, done.stdout)
            self.assertEqual(self.finding_rows(), [])
            self.assertEqual(self.escape_rows(), [])

    def test_log_escape_row_carries_the_findings_miss_reason(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "findings": [self.finding(miss_reason="plan-gap")]}
        done = self.log("branch", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([row["miss_reason"] for row in self.escape_rows()], ["plan-gap"])

    def test_log_writes_nothing_when_the_run_writer_refuses_a_row(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "result": "MAYBE", "findings": [self.finding()]}
        done = self.log("branch", payload)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("writer refused the run row", done.stderr)
        self.assertEqual(self.escape_rows(), [])
        self.assertEqual(self.finding_rows(), [])

    def test_log_writes_a_ruled_plan_structure_finding_as_fixed_with_who_ruled(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code"}
        for ruled_by in ("session", "user"):
            with self.subTest(ruled_by=ruled_by):
                finding = self.finding(disposition="ask", actioned="fixed", plan_structure=True, escape=False,
                                       ruled_by=ruled_by, file=f"{ruled_by}.py")
                done = self.log("branch", {**payload, "findings": [finding]}, extra_env=None)
                self.assertEqual(done.returncode, 0, done.stderr)
                rows = [row for row in self.finding_rows()
                        if row["kind"] == "finding" and row["path_key"] == f"{ruled_by}.py"]
                self.assertEqual([row["actioned"] for row in rows], ["fixed"])
                self.assertEqual([row["ask_decided_by"] for row in rows], [ruled_by])
        self.assertEqual(self.escape_rows(), [])

    def test_log_refuses_an_unknown_ruled_by_and_still_refuses_fixed_without_one(self):
        payload = {"finder": "smell-reviewer", "lane": "code"}
        cases = (("a ruled_by outside user and session", {"ruled_by": "bot"}, "`ruled_by`"),
                 ("fixed with no ruled_by", {}, "[plan-structure]"),
                 ("a ruled_by on a fix row", {"ruled_by": "user", "disposition": "fix", "plan_structure": False},
                  "`ruled_by`"))
        for label, extra, fragment in cases:
            with self.subTest(label):
                fields = {"disposition": "ask", "actioned": "fixed", "plan_structure": True, "escape": False}
                finding = self.finding(**{**fields, **extra})
                done = self.log("branch", {**payload, "findings": [finding]})
                self.assertEqual(done.returncode, 1, done.stdout)
                self.assertIn(fragment, done.stderr)
        self.assertEqual(self.finding_rows(), [])

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

    def test_the_log_template_in_log_help_logs_on_the_first_call(self):
        flow = load_script_module()
        help_done = self.flow("log", "--help")
        self.assertEqual(help_done.returncode, 0, help_done.stderr)
        after_start = help_done.stdout.split(flow.refactor_log_input.TEMPLATE_START + "\n", 1)[1]
        template_text = after_start.split("\n" + flow.refactor_log_input.TEMPLATE_END, 1)[0]
        template = json.loads(template_text)
        self.pushed_feature_branch({"src/orders.py": "x = 1\n"})

        done = self.log("branch", template)

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        row_kinds = sorted(row["kind"] for row in self.finding_rows())
        self.assertEqual(row_kinds, ["finding", "run"])

    def test_the_log_grammar_lives_in_refactor_log_input(self):
        flow = load_script_module()
        self.assertIs(flow.RefactorFlowError, flow.refactor_log_input.RefactorFlowError)

    def test_refactor_flow_is_at_most_1000_lines(self):
        self.assertLessEqual(len(SCRIPT.read_text().splitlines()), 1000)

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

    def test_log_rerun_writes_no_second_row_even_after_a_new_commit_and_a_new_branch(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "none"},
                   "findings": [self.finding()], "handoff": self.handoff_input()}
        first = self.log("branch", payload)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual((len(self.escape_rows()), len(self.finding_rows())), (1, 2))
        second = self.log("branch", payload)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("3 already logged, skipped", second.stdout)
        self.assertIn("handoff:", second.stdout)
        self.write("b.py", "y = 2\ny = 3\n")
        self.commit_all("more")
        self.git("checkout", "-q", "-b", "renamed")
        again = self.log("branch", payload)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertIn("3 already logged, skipped", again.stdout)
        self.assertEqual((len(self.escape_rows()), len(self.finding_rows())), (1, 2))

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

    def test_log_simplify_accepts_a_target_the_branch_deleted_and_refuses_one_never_tracked(self):
        self.write("mod/a.py", "x = 1\n")
        self.write("mod/b.py", "y = 1\n")
        self.commit_all("add mod")
        self.git("rm", "-q", "mod/a.py")
        payload = {"finder": "complexity-reviewer", "lane": "code", "findings": []}
        deleted = self.log("simplify", {**payload, "target": ["mod/a.py", "mod/b.py"]})
        self.assertEqual(deleted.returncode, 0, deleted.stderr)
        self.assertIn("target `mod/a.py` is deleted", deleted.stdout)
        self.assertNotIn("mod/b.py` is deleted", deleted.stdout)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "2")
        never = self.log("simplify", {**payload, "target": ["mod/ghost.py"]})
        self.assertEqual(never.returncode, 1, never.stdout)
        self.assertIn("matches no file (tracked or untracked)", never.stderr)

    def test_log_simplify_counts_the_lines_of_untracked_files(self):
        self.write("mod/b.py", "y = 1\nz = 2\n")
        payload = {"finder": "complexity-reviewer", "lane": "code", "findings": [], "target": ["mod"]}
        done = self.log("simplify", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "2")

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

    def test_log_audit_counts_untracked_files_outside_the_cwd(self):
        self.write("pkg/mod/a.py", "a\nb\n")
        self.write("top/u.py", "x\ny\nz\n")
        payload = {"finder": "smell-reviewer", "lane": "code", "target": ["mod", "../top"], "findings": []}
        done = self.log("audit", payload, cwd=self.repo / "pkg")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "5")

    def test_log_simplify_adds_tracked_and_untracked_lines_of_one_target(self):
        self.write("mod/a.py", "a = 1\n")
        self.git("add", "mod/a.py")
        self.write("mod/b.py", "y = 1\nz = 2\n")
        payload = {"finder": "complexity-reviewer", "lane": "code", "findings": [], "target": ["mod"]}
        done = self.log("simplify", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "3")

    def test_bad_input_exits_1_and_writes_nothing(self):
        self.branch_with({"a.py": "x = 1\n"})
        guards = {"duplication": "none"}
        finder = {"finder": "smell-reviewer", "lane": "code"}
        log_cases = []
        for escape in ("false", "true", 1, 0, None, []):
            payload = {**finder, "guards": guards, "findings": [self.finding(escape=escape)]}
            log_cases.append((f"escape {escape!r}", "branch", payload, "`escape` must be true or false"))
        for override in ({"class": ""}, {"desc": "two\nlines"}, {"line": "3"}, {"line": True}, {"severity": None}):
            payload = {**finder, "guards": guards, "findings": [self.finding(**override)]}
            log_cases.append((f"finding {override!r}", "branch", payload, None))
        log_cases.append(("missing lane", "branch", {"finder": "smell-reviewer", "findings": []}, None))
        log_cases.append(("targeted with a finder", "targeted",
                          {**finder, "findings": [], "handoff": self.handoff_input()}, "finder"))
        for bad_finder in (["smell-reviewer"], {"a": 1}, 7):
            payload = {"finder": bad_finder, "lane": "code", "findings": []}
            log_cases.append((f"finder {bad_finder!r}", "branch", payload, "`finder` must be one of"))
        log_cases.append(("audit without a target", "audit", {**finder, "findings": []}, "`target`"))
        results = [(label, self.log(mode, payload), fragment) for label, mode, payload, fragment in log_cases]
        handoff_without_handoff = self.flow("handoff", "--input", self.log_input({"findings": []}))
        results.append(("handoff verb without a handoff", handoff_without_handoff, "handoff"))
        unreadable = self.flow("log", "--mode", "branch", "--input", str(self.temp_root / "missing.json"))
        results.append(("unreadable input", unreadable, None))

        for label, done, fragment in results:
            with self.subTest(label):
                self.assertEqual(done.returncode, 1, done.stderr)
                if fragment:
                    self.assertIn(fragment, done.stderr)
        self.assertEqual(self.escape_rows(), [])
        self.assertEqual(self.finding_rows(), [])

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

    def test_prep_calls_keep_only_the_newest_fifty_log_input_files_and_leave_other_files(self):
        self.branch_with({"a.py": "x = 1\n"})
        others = [self.log_input_dir / "notes.json", self.log_input_dir / "refactor-flow-notes.json"]
        for other in others:
            other.write_text("{}")
        for index in range(60):
            seeded = self.log_input_dir / f"refactor-flow-{index:012x}.json"
            seeded.write_text("{}")
            os.utime(seeded, (2000 - index, 2000 - index))
        next_line = self.last_line(self.flow("branch-prep"))
        named = pathlib.Path(re.search(r"--input (\S*refactor-flow-[0-9a-f]{12}\.json)", next_line).group(1))
        self.assertEqual(named.parent, self.log_input_dir)
        for other in others:
            self.assertTrue(other.exists(), other.name)
        kept = list(self.log_input_dir.glob("refactor-flow-[0-9a-f]*.json"))
        self.assertEqual(len(kept), 49)
        kept_times = sorted(path.stat().st_mtime for path in kept)
        self.assertEqual(kept_times, [2000.0 - index for index in range(48, -1, -1)])

    def test_binary_paths_lists_only_binary_files_and_a_renamed_one_under_its_new_path(self):
        module = load_script_module()
        numstat_text = "-\t-\tlogo.png\0" "-\t-\t\0old.bin\0new.bin\0" "3\t0\ttext.py\0" "2\t1\t\0a.py\0b.py\0"

        self.assertEqual({"logo.png", "new.bin"}, module.binary_paths(numstat_text))

    def test_binary_paths_skips_a_malformed_row_without_raising(self):
        module = load_script_module()
        numstat_text = "garbage\0" "-\t-\tlogo.png\0" "1\t2\t\0old.py"

        self.assertEqual({"logo.png"}, module.binary_paths(numstat_text))

    def test_prune_skips_a_file_deleted_between_the_glob_and_the_stat(self):
        for index in range(60):
            (self.log_input_dir / f"refactor-flow-{index:012x}.json").write_text("{}")
        vanished = self.log_input_dir / "refactor-flow-ffffffffffff.json"
        listed = [*self.log_input_dir.glob("refactor-flow-*.json"), vanished]
        with mock.patch.object(pathlib.Path, "glob", return_value=listed):
            prune_log_inputs(self.log_input_dir)
        kept = list(self.log_input_dir.glob("refactor-flow-*.json"))
        self.assertEqual(len(kept), 49)

    def test_prune_deletes_the_branch_diff_record_of_a_pruned_log_input(self):
        for index in range(60):
            (self.log_input_dir / f"refactor-flow-{index:012x}.json").write_text("{}")
            (self.log_input_dir / f"refactor-flow-{index:012x}.json.simplify-stat").write_text("{}")
        prune_log_inputs(self.log_input_dir)
        records = list(self.log_input_dir.glob("*.simplify-stat"))
        self.assertEqual(len(records), 49)

    def test_prune_deletes_a_branch_diff_record_whose_log_input_was_never_written(self):
        for index in range(60):
            (self.log_input_dir / f"refactor-flow-{index:012x}.json.simplify-stat").write_text("{}")
        prune_log_inputs(self.log_input_dir)
        records = list(self.log_input_dir.glob("*.simplify-stat"))
        self.assertEqual(len(records), 49)

    def test_prune_neither_counts_nor_deletes_a_directory_or_symlink_with_a_matching_name(self):
        directory = self.log_input_dir / "refactor-flow-aaaaaaaaaaaa.json"
        directory.mkdir()
        target = self.temp_root / "precious.json"
        target.write_text("{}")
        link = self.log_input_dir / "refactor-flow-bbbbbbbbbbbb.json"
        link.symlink_to(target)
        for index in range(60):
            (self.log_input_dir / f"refactor-flow-{index:012x}.json").write_text("{}")
        prune_log_inputs(self.log_input_dir)
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

    def test_branch_prep_covers_committed_uncommitted_and_untracked_files(self):
        self.branch_with({"committed.py": "x = 1\n"})
        self.write("README.md", "hello\n# TODO edited\n")
        self.write("new/fresh.py", "y = 2\nprint('new')\n")
        self.write("new/blob.bin", "\0binary")
        merge_base = self.git("merge-base", "main", "HEAD").strip()
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- committed.py\n", done.stdout)
        self.assertIn("- README.md\n", done.stdout)
        self.assertIn("- new/fresh.py (untracked)\n", done.stdout)
        self.assertIn("- new/blob.bin (untracked, binary)\n", done.stdout)
        self.assertIn("Changed files (4);", done.stdout)
        self.assertIn("README.md:2 [marker] # TODO edited", done.stdout)
        self.assertIn("new/fresh.py:2 [marker] print('new')", done.stdout)
        self.assertIn(f"`git diff {merge_base}`", done.stdout)
        after_bound = done.stdout.split("review bound", 1)[1]
        bound_line = after_bound.split("\n", 1)[0]
        self.assertIn("untracked", bound_line)
        self.assertNotIn("main...HEAD", done.stdout)

    def test_branch_prep_reads_an_untracked_plan_from_the_work_tree(self):
        plan = ("# Plan\n\n## Phase 1: package\n\n### Changes Required:\n\n#### 1. Re-exports\n\n"
                "**File**: `pkg/__init__.py`\n\nRe-export `parse`.\n")
        self.branch_with({"pkg/__init__.py": "from .core import parse\n"})
        self.write("docs/plans/T-1-pkg/spec.md", plan)
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("## Plan-required structure (`docs/plans/T-1-pkg/spec.md`)", done.stdout)

    @unittest.skipIf(os.geteuid() == 0, "root reads a mode-000 file")
    def test_branch_prep_names_an_unreadable_untracked_plan(self):
        self.branch_with({"pkg/__init__.py": "x = 1\n"})
        plan_path = "docs/plans/T-1-pkg/spec.md"
        self.write(plan_path, "# Plan\n")
        (self.repo / plan_path).chmod(0)
        self.addCleanup((self.repo / plan_path).chmod, 0o644)
        done = self.flow("branch-prep")
        self.assertNotEqual(done.returncode, 0)
        self.assertNotIn("Traceback", done.stderr)
        self.assertIn(plan_path, done.stderr)

    def test_branch_prep_lists_unreadable_and_non_text_untracked_files_as_binary(self):
        self.git("checkout", "-q", "-b", "feature")
        self.write("locked.py", "x = 1\n")
        (self.repo / "locked.py").chmod(0)
        self.addCleanup((self.repo / "locked.py").chmod, 0o644)
        self.write_bytes("latin.txt", b"caf\xe9\n")
        (self.repo / "link.py").symlink_to("latin.txt")
        self.write("plain.txt", "text\n")
        (self.repo / "text_link.py").symlink_to("plain.txt")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- latin.txt (untracked, binary)", done.stdout)
        self.assertIn("- link.py (untracked, symlink)", done.stdout)
        self.assertIn("- text_link.py (untracked, symlink)", done.stdout)
        if os.geteuid() != 0:
            self.assertIn("- locked.py (untracked, binary)", done.stdout)

    def test_branch_prep_labels_an_untracked_nested_repo_as_not_a_file(self):
        self.git("checkout", "-q", "-b", "feature")
        nested = self.repo / "nested"
        nested.mkdir()
        subprocess.run(["git", "init", "-q", str(nested)], check=True)
        self.write("nested/inner.py", "x = 1\n")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- nested/ (untracked, not a file)", done.stdout)

    def test_branch_prep_keeps_the_last_line_of_an_untracked_file_without_a_trailing_newline(self):
        self.git("checkout", "-q", "-b", "feature")
        self.write("tail.py", "a = 1\n# TODO last")
        done = self.flow("branch-prep")
        self.assertIn("tail.py:2 [marker] # TODO last", done.stdout)

    def test_branch_prep_only_untracked_files_is_not_an_empty_diff(self):
        self.git("checkout", "-q", "-b", "feature")
        self.write("new.py", "# TODO later\n")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("STOP: tell the user the branch diff is empty", done.stdout)
        self.assertIn("- new.py (untracked)", done.stdout)
        self.assertIn("new.py:1 [marker]", done.stdout)

    def test_branch_prep_with_head_ignores_the_work_tree(self):
        self.branch_with({"committed.py": "x = 1\n"})
        self.write("loose.py", "z = 3\n")
        done = self.flow("branch-prep", "--head", "feature")
        self.assertNotIn("loose.py", done.stdout)
        self.assertIn("`git diff main...feature`", done.stdout)

    # ------------------------------------------------- branch-prep census
    def test_branch_prep_prints_the_single_caller_census(self):
        source = (
            "def wrapper(value):\n    return helper(value)\n\n\n"
            "def helper(value):\n    return value + 1\n\n\n"
            "print(wrapper(1))\n"
        )
        self.branch_with({"mod.py": source})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("\nSingle-caller census (", done.stdout)
        self.assertNotIn("## Single-caller census", done.stdout)
        self.assertIn("mod.py:1 single-caller-forwarder `wrapper`", done.stdout)

    def test_branch_prep_says_none_when_the_branch_adds_no_forwarder(self):
        self.branch_with({"mod.py": "x = 1\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("judge each entry):\nnone", done.stdout)

    def test_branch_prep_with_head_says_the_census_reads_only_the_work_tree(self):
        self.branch_with({"mod.py": "x = 1\n"})
        done = self.flow("branch-prep", "--head", "feature")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("The census reads only the work tree", done.stdout)

    # ----------------------------------------------- branch-prep clone pairs
    def clone_stub(self, pairs, exit_code=0):
        """A jscpd stand-in that writes a JSON report of `pairs` (two (name, start, end) sites each) into its
        --output folder and records its argv and cwd."""
        duplicates = [fake_jscpd.duplicate(first, second) for first, second in pairs]
        return {"REFACTOR_JSCPD_CMD": fake_jscpd.stub_command(self.temp_root, duplicates, exit_code)}

    def branch_with_old_sibling(self, line_count=6, edit=lambda body: body.replace("line 5", "edited 5")):
        """Main holds old_a.py and old_b.py of `line_count` lines; the branch rewrites old_a.py with `edit(body)`."""
        body = "".join(f"line {number}\n" for number in range(1, line_count + 1))
        self.write("old_a.py", body)
        self.write("old_b.py", body)
        self.commit_all("siblings")
        self.git("checkout", "-q", "-b", "feature")
        self.write("old_a.py", edit(body))
        self.commit_all("edit")

    def test_branch_prep_lists_a_clone_pair_that_touches_a_changed_line(self):
        self.branch_with_old_sibling()
        env = self.clone_stub([(("old_a.py", 4, 6), ("old_b.py", 4, 6))])
        done = self.flow("branch-prep", extra_env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- 1 clone pair(s) on changed lines; 1 listed", done.stdout)
        prompt = done.stdout.split("dispatch prompt", 1)[1]
        self.assertIn("Candidate clone pairs (jscpd):", prompt)
        self.assertIn("- old_a.py [4 - 6]", prompt)
        self.assertIn("- old_b.py [4 - 6]", prompt)
        call = (self.temp_root / "jscpd_call.txt").read_text()
        self.assertIn("--min-tokens 40", call)
        self.assertEqual(call.splitlines()[1], str(self.repo.resolve()))

    def test_branch_prep_drops_a_clone_pair_on_unchanged_lines(self):
        self.branch_with_old_sibling()
        env = self.clone_stub([(("old_a.py", 1, 3), ("old_b.py", 1, 3))])
        done = self.flow("branch-prep", extra_env=env)
        self.assertIn("- jscpd found no clone pair on changed lines", done.stdout)
        self.assertNotIn("Candidate clone pairs", done.stdout)

    def test_branch_prep_keeps_a_pair_whose_other_site_is_a_file_the_branch_did_not_touch(self):
        self.write("lib/shared.py", "def helper():\n    return 1\n")
        self.commit_all("shared")
        self.branch_with({"tool/helper.py": "def helper():\n    return 1\n"})
        env = self.clone_stub([(("tool/helper.py", 1, 2), ("lib/shared.py", 1, 2))])
        done = self.flow("branch-prep", extra_env=env)
        self.assertIn("- tool/helper.py [1 - 2]", done.stdout)
        self.assertIn("- lib/shared.py [1 - 2]", done.stdout)

    def test_branch_prep_counts_every_line_of_an_untracked_file_as_changed(self):
        self.write("lib/shared.py", "def helper():\n    return 1\n")
        self.commit_all("shared")
        self.git("checkout", "-q", "-b", "feature")
        self.write("tool/new.py", "def helper():\n    return 1\n")
        env = self.clone_stub([(("tool/new.py", 1, 2), ("lib/shared.py", 1, 2))])
        done = self.flow("branch-prep", extra_env=env)
        self.assertIn("- 1 clone pair(s) on changed lines", done.stdout)
        self.assertIn("- tool/new.py [1 - 2]", done.stdout)

    def test_branch_prep_survives_a_failing_detector(self):
        self.branch_with({"a.py": "x = 1\n"})
        env = self.clone_stub([], exit_code=3)
        done = self.flow("branch-prep", extra_env=env)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- no mechanical detection — agent prior-art search only", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "NEXT:")

    # ----------------------------------------------- branch-prep shape clones
    SHAPE_FIND = ("def find_by_key(items, wanted):\n    if not items:\n        return None\n"
                  "    for item in items:\n        if item.id == wanted:\n            return item\n    return None\n")
    SHAPE_COPY = ("def get_node_from_plan(plan_nodes, node_id):\n    if not plan_nodes:\n        return None\n"
                  "    for node in plan_nodes:\n        if node.key == node_id:\n            return node\n"
                  "    return None\n")

    def test_branch_prep_lists_a_renamed_copy_of_an_existing_function(self):
        self.write("lib/finders.py", self.SHAPE_FIND)
        self.commit_all("finders")
        self.branch_with({"plan/nodes.py": self.SHAPE_COPY})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- 1 renamed-copy and 0 near-match pair(s) on changed functions", done.stdout)
        prompt = done.stdout.split("dispatch prompt", 1)[1]
        self.assertIn("plan/nodes.py:1-7 get_node_from_plan(plan_nodes, node_id) ~ "
                      "lib/finders.py:1-7 find_by_key(items, wanted)", prompt)
        self.assertLess(prompt.index("Candidate shape clones"), prompt.index("NEXT:"))

    def test_branch_prep_with_head_skips_shape_clones_and_says_so(self):
        self.write("lib/finders.py", self.SHAPE_FIND)
        self.commit_all("finders")
        self.branch_with({"plan/nodes.py": self.SHAPE_COPY})
        done = self.flow("branch-prep", "--head", "feature")
        self.assertIn("- shape clones: clone detection reads the work tree only; skipped with --head", done.stdout)
        self.assertNotIn("Candidate shape clones", done.stdout)

    def test_branch_prep_with_head_skips_clone_detection_and_says_so(self):
        self.branch_with({"a.py": "x = 1\n"})
        env = self.clone_stub([(("a.py", 1, 1), ("b.py", 1, 1))])
        done = self.flow("branch-prep", "--head", "feature", extra_env=env)
        self.assertIn("clone detection reads the work tree only", done.stdout)
        self.assertFalse((self.temp_root / "jscpd_call.txt").exists())

    def test_branch_prep_cuts_the_clone_list_at_the_cap(self):
        self.write("lib/shared.py", "x = 1\n")
        self.commit_all("shared")
        self.branch_with({"new.py": "x = 1\n"})
        pairs = [(("new.py", 1, 1), ("lib/shared.py", 1, 1)) for _ in range(45)]
        done = self.flow("branch-prep", extra_env=self.clone_stub(pairs))
        self.assertIn("45 clone pair(s) on changed lines; 40 listed", done.stdout)
        self.assertIn("5 more pair(s) not listed", done.stdout)
        prompt = done.stdout.split("dispatch prompt", 1)[1]
        self.assertEqual(prompt.count("Clone found"), 40)

    def test_branch_prep_says_so_when_the_jscpd_report_does_not_parse(self):
        self.branch_with({"a.py": "x = 1\n"})
        stub_dir = self.temp_root / "misshapen"
        stub_dir.mkdir()
        command = fake_jscpd.stub_command(stub_dir, [], report_text='{"duplicates": [{"format": "python"}]}')
        done = self.flow("branch-prep", extra_env={"REFACTOR_JSCPD_CMD": command})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- jscpd output did not parse: ", done.stdout)
        self.assertIn("jscpd-report.json", done.stdout)
        self.assertNotIn("found no clone pair", done.stdout)

    def test_branch_prep_drops_prose_format_pairs(self):
        self.branch_with_old_sibling()
        duplicates = [fake_jscpd.duplicate(("old_a.py", 4, 6), ("old_b.py", 4, 6), clone_format)
                      for clone_format in ("markdown", "text", "txt")]
        command = fake_jscpd.stub_command(self.temp_root, duplicates)
        done = self.flow("branch-prep", extra_env={"REFACTOR_JSCPD_CMD": command})
        self.assertIn("- jscpd found no clone pair on changed lines", done.stdout)

    def test_branch_prep_counts_a_pair_whose_only_changed_line_is_the_last_or_first_line(self):
        self.branch_with_old_sibling(line_count=8)
        for first, last in ((3, 5), (5, 7)):
            with self.subTest(first=first, last=last):
                env = self.clone_stub([(("old_a.py", first, last), ("old_b.py", first, last))])
                done = self.flow("branch-prep", extra_env=env)
                self.assertIn("- 1 clone pair(s) on changed lines", done.stdout)

    def test_branch_prep_reads_a_second_hunk_and_ignores_deleted_lines(self):
        self.branch_with_old_sibling(line_count=20,
                                     edit=lambda body: body.replace("line 2\n", "").replace("line 18", "edited 18"))
        cases = [("on the second hunk", (17, 19), "- 1 clone pair(s)"),
                 ("on a deletion only", (1, 1), "found no clone pair")]
        for label, (first, last), expected in cases:
            with self.subTest(label):
                env = self.clone_stub([(("old_a.py", first, last), ("old_b.py", first, last))])
                done = self.flow("branch-prep", extra_env=env)
                self.assertIn(expected, done.stdout)

    def test_branch_prep_empty_diff_stops(self):
        self.git("checkout", "-q", "-b", "feature")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0)
        self.assertIn("is empty and no file is untracked", done.stdout)
        self.assertIn("STOP:", done.stdout)
        self.assertNotIn("dispatch prompt", done.stdout)

    def test_branch_prep_empty_diff_with_head_keeps_the_old_message(self):
        self.git("checkout", "-q", "-b", "feature")
        self.write("loose.py", "z = 3\n")
        done = self.flow("branch-prep", "--head", "feature")
        self.assertIn("main...feature` is empty (base", done.stdout)
        self.assertNotIn("untracked", done.stdout)
        self.assertIn("STOP: tell the user the branch diff is empty", done.stdout)

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

    def test_branch_prep_sweep_flags_a_marker_word_and_never_an_identifier_that_holds_one(self):
        flagged = ["print(x)", "pprint(x)", "pprint.pprint(x)", "# TODO fix", "# FIXME", "# XXX", "# HACK: no",
                   "# TODOs",
                   "console.log(x)", "console.debug(x)", "debugger;", "binding.pry"]
        unflagged = ["tree_fingerprint(x)", "context_fingerprint(x)", "self.print(x)", "TODOS_DIR = 1",
                     "MY_TODO = 1", "FIXMES = 1", "XXXL = 1", "HACKATHON = 1", "myconsole.log(x)",
                     "console.logger(x)", "mydebugger = 1", "debuggers = 1", "binding.pryer = 1"]
        lines = [f"v{number} = 0  {text}" for number, text in enumerate([*flagged, *unflagged], 1)]
        self.branch_with({"a.py": "\n".join(lines) + "\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        marked = set(re.findall(r"a\.py:(\d+) \[marker\]", done.stdout))
        self.assertEqual(marked, {str(number) for number in range(1, len(flagged) + 1)})

    def test_branch_prep_sweep_ignores_a_marker_inside_a_string_and_keeps_a_bare_statement(self):
        body = ('message = "call print(x) later"\n'
                'other = "TODO in a string"\n'
                'doc = """\nprint(x)\nTODO inside\n"""\n'
                'print(value)\n'
                'name = "ok"  # TODO real\n')
        self.branch_with({"a.py": body})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        marked = set(re.findall(r"a\.py:(\d+) \[marker\]", done.stdout))
        self.assertEqual(marked, {"7", "8"})

    def test_branch_prep_sweep_skips_print_in_a_cli_script_but_keeps_todo_and_library_prints(self):
        cli = ("import argparse\n\ndef main():\n    print('report')\n    # TODO tidy\n\n"
               "if __name__ == '__main__':\n    main()\n")
        self.branch_with({"cli.py": cli, "lib.py": "def f():\n    print('debug')\n"})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("cli.py:4 [marker]", done.stdout)
        self.assertIn("cli.py:5 [marker]", done.stdout)
        self.assertIn("lib.py:2 [marker]", done.stdout)

    def test_branch_prep_sweep_silences_print_for_each_cli_trigger_alone_and_not_for_lookalikes(self):
        cases = [
            ("import argparse\n", True), ("from argparse import ArgumentParser\n", True),
            ("def main():\n    pass\n", True), ("async def main():\n    pass\n", True),
            ("if __name__ == '__main__':\n    pass\n", True),
            ("def main_helper():\n    pass\n", False), ("class A:\n    def main(self):\n        pass\n", False),
            ("def f():\n    import argparse\n", False),
            ("if True:\n    if __name__ == '__main__':\n        pass\n", False),
        ]
        files = {f"c{index}.py": header + "print('x')\n" for index, (header, _silenced) in enumerate(cases)}
        self.branch_with(files)
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        for index, (header, silenced) in enumerate(cases):
            with self.subTest(header=header):
                reported = re.search(rf"c{index}\.py:\d+ \[marker\] print", done.stdout) is not None
                self.assertEqual(reported, not silenced, done.stdout)

    def test_branch_prep_sweep_never_silences_print_in_a_non_python_file(self):
        self.branch_with({"a.js": "import argparse\nprint(x)\n"})
        done = self.flow("branch-prep")
        self.assertIn("a.js:2 [marker]", done.stdout)

    def test_branch_prep_sweep_ignores_a_cli_fixture_string_and_string_data_comments(self):
        body = ('FIXTURE = """\nif __name__ == "__main__":\n# import os\n"""\nprint("debug")\n')
        self.branch_with({"t.py": body})
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("t.py:5 [marker]", done.stdout)
        self.assertNotIn("commented-out code", done.stdout)

    def test_branch_prep_sweep_ignores_markers_in_an_untracked_file_string_data(self):
        self.branch_with({"a.py": "x = 1\n"})
        self.write("u.py", 's = "print(x)"\ndoc = """\nTODO\n# import os\n"""\n')
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Mechanical sweep (0 match(es))", done.stdout)
        self.assertNotIn("u.py:", done.stdout.split("Mechanical sweep", 1)[-1])

    def test_branch_prep_sweep_survives_a_dangling_symlink_and_a_gitlink(self):
        self.git("checkout", "-q", "-b", "feature")
        (self.repo / "dangling").symlink_to("TODO-missing-target")
        self.git("update-index", "--add", "--cacheinfo", "160000," + "a" * 40 + ",sub")
        self.commit_all("links")
        for head_args in ([], ["--head", "feature"]):
            with self.subTest(head_args=head_args):
                done = self.flow("branch-prep", *head_args)
                self.assertEqual(done.returncode, 0, done.stderr)
                self.assertIn("dangling:1 [marker] TODO-missing-target", done.stdout)

    def test_branch_prep_sweep_survives_a_symlink_to_a_directory(self):
        self.git("checkout", "-q", "-b", "feature")
        (self.repo / "TODO-dir").mkdir()
        self.write("TODO-dir/f.py", "x = 1\n")
        (self.repo / "linked").symlink_to("TODO-dir")
        self.commit_all("dir link")
        done = self.flow("branch-prep")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("linked:1 [marker] TODO-dir", done.stdout)

    def test_post_image_reader_raises_on_an_unreadable_work_tree_file(self):
        # Called directly: `git diff` itself fails first on an unreadable file, so the flow never reaches the reader.
        self.write("a.py", "# TODO tidy\n")
        unreadable = self.repo / "a.py"
        unreadable.chmod(0)
        self.addCleanup(unreadable.chmod, 0o644)
        if os.access(unreadable, os.R_OK):
            self.skipTest("file permissions do not stop this user from reading")
        module = load_script_module()
        read_post_image = module.post_image_reader(str(self.repo), None)
        with self.assertRaisesRegex(module.RefactorFlowError, "cannot read .*a.py for the sweep"):
            read_post_image("a.py")

    def test_post_image_reader_in_head_mode_raises_for_a_path_missing_at_head(self):
        self.branch_with({"a.py": "# TODO tidy\n"})
        module = load_script_module()
        previous_directory = os.getcwd()
        self.addCleanup(os.chdir, previous_directory)
        os.chdir(self.repo)
        read_post_image = module.post_image_reader(str(self.repo), "feature")
        with self.assertRaises(module.RefactorFlowError) as raised:
            read_post_image("missing.py")
        self.assertIn("feature:missing.py", str(raised.exception))

    def test_branch_prep_stops_when_the_file_read_differs_from_the_diff(self):
        self.git("config", "filter.swap.clean", "tr y x")
        self.git("config", "filter.swap.smudge", "tr x y")
        self.git("checkout", "-q", "-b", "feature")
        self.write(".gitattributes", "*.py filter=swap\n")
        self.write("a.py", "# TODO fix\n")
        self.commit_all("work")
        (self.repo / "a.py").unlink()
        self.git("checkout", "--", "a.py")
        done = self.flow("branch-prep")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("the sweep cannot trust the file it read: a.py:1 differs", done.stderr)

    def test_branch_prep_head_mode_reads_the_post_image_at_head(self):
        self.branch_with({"a.py": "s = 'print(x)'\nprint(y)\n"})
        self.write("a.py", "unrelated = 1\n")
        done = self.flow("branch-prep", "--head", "feature")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("a.py:1 [marker]", done.stdout)
        self.assertIn("a.py:2 [marker]", done.stdout)

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
        command = fake_jscpd.stub_command(self.temp_root, JSCPD_REAL)
        done = self.flow("audit-prep", "src", extra_env={"REFACTOR_JSCPD_CMD": command})
        self.assertEqual(done.returncode, 0, done.stderr)
        prompt = done.stdout.split("dispatch prompt", 1)[1]
        self.assertIn("Clone found (javascript)", prompt)
        self.assertIn("- src/a.js [1 - 48]", prompt)
        self.assertIn("- src/sub dir/b copy.js [1 - 48]", prompt)
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

    def test_audit_prep_says_jscpd_found_no_clone_pairs(self):
        self.write("src/a.py", "x = 1\n")
        self.git("add", "-A")
        command = fake_jscpd.stub_command(self.temp_root, [])
        done = self.flow("audit-prep", "src", extra_env={"REFACTOR_JSCPD_CMD": command})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- jscpd ran and found no clone pairs", done.stdout)

    def test_audit_prep_reports_a_misshapen_report_as_not_parsed(self):
        self.write("src/a.py", "x = 1\n")
        self.git("add", "-A")
        command = fake_jscpd.stub_command(self.temp_root, [], report_text='{"duplicates": 5}')
        done = self.flow("audit-prep", "src", extra_env={"REFACTOR_JSCPD_CMD": command})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("jscpd output did not parse", done.stdout)
        self.assertNotIn("found no clone pairs", done.stdout)

    def test_audit_prep_cuts_the_clone_list_at_a_pair_boundary_and_counts_the_rest(self):
        self.write("src/a.js", "x = 1\n")
        self.git("add", "-A")
        duplicates = [fake_jscpd.duplicate((f"a{i}.js", 1, 5), (f"b{i}.js", 1, 5), "javascript") for i in range(55)]
        command = fake_jscpd.stub_command(self.temp_root, duplicates)
        done = self.flow("audit-prep", "src", extra_env={"REFACTOR_JSCPD_CMD": command})
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
        command = fake_jscpd.stub_command(spaced_dir, JSCPD_REAL)
        done = self.flow("audit-prep", "src", extra_env={"REFACTOR_JSCPD_CMD": command})
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

    def test_simplify_prep_lists_tracked_and_untracked_files_of_a_target(self):
        self.write("mod/a.py", "x = 1\n")
        self.git("add", "-A")
        self.write("mod/b.py", "y = 2\n")
        done = self.flow("simplify-prep", "mod")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- mod/a.py", done.stdout)
        self.assertIn("- mod/b.py", done.stdout)

    def test_simplify_prep_lists_a_tracked_file_changed_in_the_work_tree_once(self):
        self.write("mod/a.py", "x = 1\n")
        self.git("add", "-A")
        self.write("mod/a.py", "x = 2\n")
        done = self.flow("simplify-prep", "mod")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.count("- mod/a.py"), 1)

    def test_simplify_prep_leaves_ignored_files_out(self):
        self.write(".gitignore", "*.log\n")
        self.write("mod/x.log", "noise\n")
        self.write("mod/a.py", "x = 1\n")
        done = self.flow("simplify-prep", "mod")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("mod/x.log", done.stdout)

    def test_simplify_prep_on_only_untracked_files_does_not_stop(self):
        self.write("mod/b.py", "y = 2\n")
        done = self.flow("simplify-prep", "mod")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertNotIn("STOP:", done.stdout)
        self.assertIn("- mod/b.py", done.stdout)

    def test_log_input_path_defaults_to_the_repo_git_dir(self):
        self.write("mod/a.py", "x = 1\n")
        done = self.flow("simplify-prep", "mod", extra_env={"REFACTOR_LOG_INPUT_DIR": ""})
        self.assertEqual(done.returncode, 0, done.stderr)
        named = pathlib.Path(re.search(r"--input (\S*refactor-flow-[0-9a-f]{12}\.json)", done.stdout).group(1))
        git_dir = pathlib.Path(self.git("rev-parse", "--absolute-git-dir").strip())
        self.assertEqual(named.parent.resolve(), (git_dir / "refactor-flow").resolve())
        self.assertTrue(named.parent.is_dir())

    def test_close_branch_step_five_names_the_branch_log_command(self):
        skill_text = (toolkit_paths.CLAUDE_DIR / "skills" / "close-branch" / "SKILL.md").read_text()
        self.assertIn("refactor_flow.py log", skill_text)
        self.assertIn("--mode branch", skill_text)

    def test_close_branch_step_five_points_to_log_help(self):
        skill_text = (toolkit_paths.CLAUDE_DIR / "skills" / "close-branch" / "SKILL.md").read_text()
        self.assertIn("log --help", skill_text)
        self.assertNotIn("refactor/SKILL.md` Step 5", skill_text)

    def test_the_refactor_skill_holds_no_log_json_template(self):
        skill_text = (SCRIPT.parent.parent / "SKILL.md").read_text()
        self.assertIsNone(re.search(r"^\s*`{3}json", skill_text, re.MULTILINE))
        self.assertNotIn("JSON as in step 5", skill_text)
        self.assertIn("refactor_flow.py log --help", skill_text)

    def test_the_refactor_skill_keeps_the_step_five_judgment_sentences_and_no_key_list(self):
        skill_text = (SCRIPT.parent.parent / "SKILL.md").read_text()
        for sentence in ("One entry per smell, not per file.",
                         "Never `escape` mechanical-sweep matches or legacy targets",
                         "a label from `escape-ratchet.md`; not `unknown`"):
            self.assertIn(sentence, skill_text)
        self.assertNotIn("{class, disposition", skill_text)
        self.assertIn("**Log and hand off", skill_text)
        self.assertIn("**Auto-dispatch review**", skill_text)
        step_five = skill_text.split("**Log and hand off", 1)[1].split("**Auto-dispatch review**", 1)[0]
        for key_text in ('"finder"', '"result"', "`finder`", "`result`"):
            self.assertNotIn(key_text, step_five)

    def test_simplify_prep_small_target_has_no_split_and_prompt_has_oracle(self):
        self.write("mod/a.py", "x = 1\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", "mod")
        self.assertNotIn("split into", done.stdout)
        self.assertIn("oracle and magnitude floor", done.stdout)
        self.assertIn("do NOT read the files", done.stdout)

    # ------------------------------------------------ simplify: branch diff and --diff bound
    def simplify_prep_input(self, *prep_args):
        """Run simplify-prep and return (its result, the log input path it named)."""
        done = self.flow("simplify-prep", *prep_args)
        self.assertEqual(done.returncode, 0, done.stderr)
        named = re.search(r"write the log input to (\S+)", done.stdout)
        self.assertIsNotNone(named, done.stdout)
        return done, named.group(1)

    def simplify_log(self, log_input, files, handoff=None):
        payload = {"finder": "complexity-reviewer", "lane": "code", "findings": [], "target": files}
        if handoff:
            payload["handoff"] = handoff
        pathlib.Path(log_input).write_text(json.dumps(payload))
        return self.flow("log", "--mode", "simplify", "--input", log_input)

    def test_simplify_log_stops_naming_the_files_that_grew_when_the_fix_adds_lines(self):
        self.branch_with({"mod/a.py": "x = 1\n", "mod/b.py": "y = 1\n"})
        prep, log_input = self.simplify_prep_input("mod")
        self.assertIn("Branch diff at prep", prep.stdout)
        self.write("mod/a.py", "x = 1\nx2 = 2\nx3 = 3\n")
        self.write("mod/c.py", "z = 1\n")
        done = self.simplify_log(log_input, ["mod/a.py", "mod/b.py"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- at prep: 2 file(s) changed, 2 insertion(s)(+), 0 deletion(s)(-)", done.stdout)
        self.assertIn("- at log:  3 file(s) changed, 5 insertion(s)(+), 0 deletion(s)(-)", done.stdout)
        last = self.last_line(done)
        self.assertTrue(last.startswith("STOP:"), done.stdout)
        self.assertIn("2 to 5", last)
        self.assertIn("mod/a.py (+2)", last)
        self.assertIn("mod/c.py (+1)", last)
        self.assertNotIn("mod/b.py", last)
        self.assertEqual(len(self.finding_rows()), 1, "the rows are still written")

    def test_simplify_log_stop_on_grown_diff_still_carries_the_review_step_when_a_handoff_is_given(self):
        self.branch_with({"mod/a.py": "x = 1\n"})
        _prep, log_input = self.simplify_prep_input("mod")
        self.write("mod/a.py", "x = 1\nx2 = 2\nx3 = 3\n")
        done = self.simplify_log(log_input, ["mod/a.py"], handoff=self.handoff_input())
        self.assertEqual(done.returncode, 0, done.stderr)
        last = self.last_line(done)
        self.assertTrue(last.startswith("STOP:"), done.stdout)
        self.assertIn("/review", last)

    def test_simplify_log_passes_when_the_fix_deletes_lines(self):
        self.branch_with({"mod/a.py": "x = 1\nx2 = 2\nx3 = 3\n", "mod/b.py": "y = 1\n"})
        _prep, log_input = self.simplify_prep_input("mod")
        self.write("mod/a.py", "x = 1\n")
        done = self.simplify_log(log_input, ["mod/a.py", "mod/b.py"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- at prep: 2 file(s) changed, 4 insertion(s)(+)", done.stdout)
        self.assertIn("- at log:  2 file(s) changed, 2 insertion(s)(+)", done.stdout)
        self.assertTrue(self.last_line(done).startswith("NEXT:"), done.stdout)

    def test_simplify_log_passes_when_the_fix_swaps_one_added_line_for_another(self):
        self.branch_with({"mod/a.py": "x = 1\nx2 = 2\n"})
        _prep, log_input = self.simplify_prep_input("mod")
        self.write("mod/a.py", "x = 1\nx3 = 3\n")
        done = self.simplify_log(log_input, ["mod/a.py"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- at prep: 1 file(s) changed, 2 insertion(s)(+)", done.stdout)
        self.assertIn("- at log:  1 file(s) changed, 2 insertion(s)(+)", done.stdout)
        self.assertTrue(self.last_line(done).startswith("NEXT:"), done.stdout)

    def test_simplify_log_without_a_prep_record_says_it_did_not_compare(self):
        self.write("mod/a.py", "x = 1\n")
        payload = {"finder": "complexity-reviewer", "lane": "code", "findings": [], "target": ["mod"]}
        done = self.log("simplify", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("no prep-time record for this input", done.stdout)
        self.assertTrue(self.last_line(done).startswith("NEXT:"), done.stdout)

    def test_simplify_log_refuses_a_branch_diff_record_it_cannot_read(self):
        self.write("mod/a.py", "x = 1\n")
        payload = {"finder": "complexity-reviewer", "lane": "code", "findings": [], "target": ["mod"]}
        log_input = self.log_input(payload)
        pathlib.Path(log_input + ".simplify-stat").write_text("{not json")
        done = self.flow("log", "--mode", "simplify", "--input", log_input)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("simplify-stat", done.stderr)
        self.assertEqual(self.finding_rows(), [], "nothing is written")

    def test_simplify_prep_diff_bounds_the_prompt_to_added_lines(self):
        self.write("mod/a.py", "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\n")
        self.write("mod/z.py", "z = 1\nz2 = 2\nz3 = 3\n")
        self.commit_all("base")
        self.git("checkout", "-q", "-b", "feature")
        self.write("mod/a.py", "a = 1\nB = 2\nc = 3\nd = 4\nE = 5\nf = 6\n")
        self.write("mod/z.py", "z = 1\nz3 = 3\n")
        self.commit_all("edit")
        done = self.flow("simplify-prep", "mod", "--diff", "main")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("diff-scoped", done.stdout)
        self.assertNotIn("Pre-existing shape IS the target", done.stdout)
        self.assertIn("- mod/a.py (added lines: 2, 5-6)", done.stdout)
        self.assertNotIn("mod/z.py", done.stdout)
        self.assertIn("added lines since `main`", done.stdout)

    def test_simplify_prep_diff_lists_only_files_with_added_lines_and_whole_untracked_files(self):
        self.write("mod/a.py", "a = 1\n")
        self.commit_all("untouched by the branch")
        self.branch_with({"mod/b.py": "b = 1\nb2 = 2\nb3 = 3\n", "mod/c.py": "c = 1\n"})
        self.write("mod/d.py", "d = 1\n")
        done = self.flow("simplify-prep", "mod", "--diff", "main")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- mod/b.py (added lines: 1-3)", done.stdout)
        self.assertIn("- mod/c.py (added lines: 1)", done.stdout)
        self.assertIn("- mod/d.py (added lines: untracked, whole file)", done.stdout)
        self.assertNotIn("- mod/a.py", done.stdout)

    def test_simplify_prep_diff_stops_when_no_file_of_the_target_changed(self):
        self.branch_with({"mod/a.py": "a = 1\n"})
        self.write("quiet/q.py", "q = 1\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        done = self.flow("simplify-prep", "quiet", "--diff", "HEAD")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("STOP: `quiet` holds no file with a line added since `HEAD`", done.stdout)
        self.assertNotIn("dispatch prompt", done.stdout)

    def unrelated_commit(self):
        """Commit on an orphan branch, then return to main: `lone` shares no history with HEAD."""
        self.git("checkout", "-q", "--orphan", "lone")
        self.write("lone.py", "x = 1\n")
        self.commit_all("lone")
        self.git("checkout", "-q", "main")

    def test_simplify_prep_diff_names_its_own_flag_when_the_ref_shares_no_history(self):
        self.write("mod/a.py", "a = 1\n")
        self.unrelated_commit()
        done = self.flow("simplify-prep", "mod", "--diff", "lone")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("STOP: lone and HEAD share no history", done.stdout)
        self.assertNotIn("--base", done.stdout)

    def test_simplify_prep_diff_skips_untracked_binary_files_and_symlinks(self):
        self.write("mod/a.py", "a = 1\n")
        self.commit_all("base")
        self.branch_with({"mod/b.py": "b = 1\n"})
        self.write_bytes("mod/bin.py", b"\x00\x01\x02")
        (self.repo / "mod" / "link.py").symlink_to("b.py")
        done = self.flow("simplify-prep", "mod", "--diff", "main")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- mod/b.py (added lines: 1)", done.stdout)
        self.assertNotIn("mod/bin.py", done.stdout)
        self.assertNotIn("mod/link.py", done.stdout)

    def test_simplify_log_leaves_an_untracked_binary_out_of_the_at_log_count(self):
        self.branch_with({"mod/a.py": "a = 1\n"})
        _prep, log_input = self.simplify_prep_input("mod")
        self.write_bytes("mod/bin.py", b"\x00\x01\x02")
        done = self.simplify_log(log_input, ["mod/a.py"])
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- at log:  1 file(s) changed, 1 insertion(s)(+)", done.stdout)
        self.assertTrue(self.last_line(done).startswith("NEXT:"), done.stdout)

    def test_simplify_prep_diff_lists_an_uncommitted_edit_of_a_tracked_file(self):
        self.write("mod/a.py", "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\ng = 7\nh = 8\n")
        self.commit_all("base")
        self.git("checkout", "-q", "-b", "feature")
        self.write("mod/a.py", "a = 1\nb = 2\nc = 3\nd = 4\ne = 5\nf = 6\nG = 7\nh = 8\n")
        done = self.flow("simplify-prep", "mod", "--diff", "main")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- mod/a.py (added lines: 7)", done.stdout)

    def test_simplify_prep_diff_lists_the_files_of_two_targets(self):
        self.write("other/o.py", "o = 1\n")
        self.commit_all("base")
        self.branch_with({"mod/a.py": "a = 1\n", "other/o.py": "o = 1\no2 = 2\n"})
        done = self.flow("simplify-prep", "mod", "other", "--diff", "main")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- mod/a.py (added lines: 1)", done.stdout)
        self.assertIn("- other/o.py (added lines: 2)", done.stdout)

    def test_simplify_prep_diff_stops_naming_the_target_with_no_added_lines_among_two(self):
        # Pins current behavior: one quiet target stops the whole prep.
        self.write("other/o.py", "o = 1\n")
        self.commit_all("base")
        self.branch_with({"mod/a.py": "a = 1\n"})
        done = self.flow("simplify-prep", "mod", "other", "--diff", "main")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("STOP: `other` holds no file with a line added since `main`", done.stdout)

    def test_simplify_prep_diff_keeps_a_file_under_a_folder_named_b(self):
        self.write("b/z.py", "z = 1\n")
        self.commit_all("base")
        self.branch_with({"b/m.py": "m = 1\n"})
        done = self.flow("simplify-prep", "b", "--diff", "main")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("- b/m.py (added lines: 1)", done.stdout)

    def test_final_line_keeps_the_next_step_after_a_grown_diff_stop_without_a_handoff(self):
        module = load_script_module()
        comparison = module.simplify_flow.BranchComparison([], "STOP: grew.")
        line = module.final_line(comparison, {"handoff": None}, "simplify")
        self.assertIn("STOP: grew. After they rule:", line)
        self.assertIn("no handoff given", line)

    def test_simplify_prep_without_a_base_still_prints_the_prompt_and_records_no_diff(self):
        self.write("mod/a.py", "a = 1\n")
        done = self.flow("simplify-prep", "mod")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Branch diff: not recorded", done.stdout)
        self.assertIn("no base found", done.stdout)
        self.assertEqual(list(self.log_input_dir.glob("*.simplify-stat")), [])
        self.assertIn("dispatch prompt", done.stdout)

    def test_simplify_prep_without_diff_survives_a_base_that_cannot_be_read(self):
        self.git("checkout", "-q", "--orphan", "lone")
        self.git("rm", "-rfq", "--cached", ".")
        self.write("mod/a.py", "a = 1\n")
        done = self.flow("simplify-prep", "mod")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("Branch diff: not recorded", done.stdout)
        self.assertIn("dispatch prompt", done.stdout)

    def test_simplify_prep_creates_a_missing_log_input_folder(self):
        self.branch_with({"mod/a.py": "a = 1\n"})
        inputs = self.temp_root / "new" / "inputs"
        done = self.flow("simplify-prep", "mod", extra_env={"REFACTOR_LOG_INPUT_DIR": str(inputs)})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(len(list(inputs.glob("*.simplify-stat"))), 1, done.stdout)

    def test_simplify_prep_diff_from_a_subfolder_matches_files_outside_the_cwd(self):
        self.branch_with({"mod/a.py": "a = 1\n", "sub/s.py": "s = 1\n"})
        done = self.flow("simplify-prep", "../mod", "--diff", "main", cwd=self.repo / "sub")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("added lines: 1", done.stdout)
        self.assertNotIn("holds no file with a line added", done.stdout)

    def test_simplify_prep_diff_refuses_a_ref_that_is_not_a_commit(self):
        self.write("mod/a.py", "a = 1\n")
        done = self.flow("simplify-prep", "mod", "--diff", "no-such-ref")
        self.assertEqual(done.returncode, 1)
        self.assertIn("--diff no-such-ref is not a commit", done.stderr)

    def test_simplify_prep_without_diff_keeps_the_whole_module_bound(self):
        self.branch_with({"mod/a.py": "a = 1\n"})
        done = self.flow("simplify-prep", "mod")
        self.assertIn("Pre-existing shape IS the target", done.stdout)
        self.assertNotIn("added lines:", done.stdout)

    def test_simplify_prep_slices_along_module_folders_and_drops_test_index_and_style_files(self):
        for module, count in (("a", 12), ("b", 12), ("c", 6)):
            for index in range(count):
                self.write(f"mod/{module}/f{index:02d}.py", "x = 1\n")
        self.write("mod/a/test_a.py", "x = 1\n")
        self.write("mod/b/index.ts", "x = 1\n")
        self.write("mod/c/theme.scss", "x {}\n")
        self.write("mod/__init__.py", "")
        self.git("add", "-A")
        listed = []
        outputs = []
        for number in ("1", "2"):
            done = self.flow("simplify-prep", "mod", "--slice", number)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("split into 2 slices", done.stdout)
            self.assertIn("1 test, 2 index, 1 style, 0 generated file(s)", done.stdout)
            self.assertIn("(30 source file(s))", done.stdout)
            outputs.append(done.stdout)
            listed.append(re.findall(r"^- (mod/\S+)$", done.stdout, re.M))
        self.assertIn("modules: mod/a, mod/b;", outputs[0])
        self.assertIn("modules: mod/c;", outputs[1])
        for name in ("test_a.py", "index.ts", "theme.scss", "__init__.py"):
            self.assertFalse(any(name in path for paths in listed for path in paths), name)
        self.assertEqual(sum(len(paths) for paths in listed), 30)
        for module in ("a", "b", "c"):
            self.assert_folder_whole(listed, f"mod/{module}/")
        self.assertEqual(self.flow("simplify-prep", "mod", "--slice", "3").returncode, 1)

    def test_simplify_prep_drops_generated_files_and_does_not_list_them(self):
        self.write("mod/a.py", "x = 1\n")
        self.write("mod/dist/bundle.js", "x = 1\n")
        self.write("mod/package-lock.json", "{}\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", "mod")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("0 test, 0 index, 0 style, 2 generated file(s)", done.stdout)
        self.assertIn("(1 source file(s))", done.stdout)
        self.assertNotIn("bundle.js", done.stdout)
        self.assertNotIn("package-lock.json", done.stdout)

    def test_simplify_prep_with_only_test_index_or_style_files_stops(self):
        self.write("mod/test_a.py", "x = 1\n")
        self.write("mod/index.js", "x = 1\n")
        self.write("mod/a.css", "x {}\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", "mod")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("STOP:", done.stdout)
        self.assertIn("`mod`", done.stdout)
        self.assertIn("only test, index, style or generated files", done.stdout)
        self.assertIn("1 test, 1 index, 1 style, 0 generated", done.stdout)
        self.assertNotIn("dispatch prompt", done.stdout)

    def listed_slices(self, *targets):
        """The files each slice lists, for every slice of a simplify-prep call, in slice order."""
        slices = []
        number = 1
        while True:
            done = self.flow("simplify-prep", *targets, "--slice", str(number))
            if done.returncode != 0:
                return slices
            files = re.findall(r"^- (\S.*)$", done.stdout, re.M)
            self.assertLessEqual(len(files), 25, f"slice {number} is over the file limit")
            slices.append(files)
            number += 1

    def assert_folder_whole(self, slices, folder):
        holders = [files for files in slices if any(path.startswith(folder) for path in files)]
        self.assertEqual(len(holders), 1, f"{folder} was cut across slices")

    def test_simplify_plan_rejects_a_listed_file_outside_its_target(self):
        module = load_script_module()
        with self.assertRaises(module.simplify_flow.simplify_slices.SliceError) as caught:
            module.simplify_flow.simplify_slices.plan_slices([("mod", ["other/a.py"])], 25)
        self.assertIn("other/a.py", str(caught.exception))
        self.assertIn("mod", str(caught.exception))

    def test_simplify_prep_reports_a_file_outside_its_target_as_a_flow_error(self):
        module = load_script_module()
        opts = mock.Mock(slice=1)
        with self.assertRaises(module.RefactorFlowError) as caught:
            module.simplify_flow.simplify_report(opts, [("mod", ["other/a.py"])], str(self.repo), None, "", {})
        self.assertIn("simplify-prep:", str(caught.exception))
        self.assertIn("other/a.py", str(caught.exception))

    def test_simplify_prep_splits_an_over_limit_module_by_its_subfolders(self):
        for folder in ("x", "y"):
            for index in range(15):
                self.write(f"mod/big/{folder}/f{index:02d}.py", "x = 1\n")
        self.write("mod/loose.py", "x = 1\n")
        self.git("add", "-A")
        slices = self.listed_slices("mod")
        self.assertEqual(len(slices), 2)
        self.assert_folder_whole(slices, "mod/big/x/")
        self.assert_folder_whole(slices, "mod/big/y/")
        self.assertEqual(sum(files.count("mod/loose.py") for files in slices), 1)
        self.assertEqual(sum(len(files) for files in slices), 31)
        self.assertEqual(sorted(slices[0]), [f"mod/big/x/f{index:02d}.py" for index in range(15)])
        self.assertEqual(
            sorted(slices[1]), sorted([f"mod/big/y/f{index:02d}.py" for index in range(15)] + ["mod/loose.py"])
        )

    def test_simplify_prep_dot_target_keeps_module_folders_whole(self):
        for folder in ("a", "b"):
            for index in range(15):
                self.write(f"{folder}/f{index:02d}.py", "x = 1\n")
        self.git("add", "-A")
        slices = self.listed_slices(".")
        self.assertEqual(len(slices), 2)
        self.assert_folder_whole(slices, "a/")
        self.assert_folder_whole(slices, "b/")

    def test_simplify_prep_absolute_target_keeps_module_folders_whole(self):
        for folder in ("a", "b"):
            for index in range(15):
                self.write(f"mod/{folder}/f{index:02d}.py", "x = 1\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", str(self.repo / "mod"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("modules: mod/a;", done.stdout)
        self.assertEqual(len(re.findall(r"^- mod/a/", done.stdout, re.M)), 15)

    def test_simplify_prep_stops_on_a_target_outside_the_repo(self):
        outside = self.temp_root / "elsewhere"
        outside.mkdir()
        (outside / "a.py").write_text("x = 1\n")
        self.write("mod/a.py", "x = 1\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", str(outside))
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("git ls-files failed", done.stderr)
        self.assertIn(str(outside), done.stderr)
        self.assertIn("outside repository", done.stderr)
        self.assertNotIn("dispatch prompt", done.stdout)

    def test_simplify_prep_counts_files_once_across_overlapping_folder_targets(self):
        for index in range(3):
            self.write(f"mod/a/f{index}.py", "x = 1\n")
        for index in range(2):
            self.write(f"mod/b/f{index}.py", "x = 1\n")
        self.git("add", "-A")
        done = self.flow("simplify-prep", "mod", "mod/a")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("(5 source file(s))", done.stdout)
        self.assertEqual(done.stdout.count("- mod/a/f0.py"), 1)

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
        self.assertIn("(2 source file(s))", done.stdout)

    # --------------------------------------------------------------------- log
    def test_log_branch_writes_escape_finder_and_handoff(self):
        self.branch_with({"a.py": "x = 1\n"})
        self.write("a.py", "x = 2\n")
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
        self.assertIn("      change: merged parse", done.stdout)
        self.assertIn("modifier `+fast`", done.stdout)
        self.assertEqual(self.last_line(done)[:5], "NEXT:")
        self.assertIn("Skill-invoke /review", self.last_line(done))

    def handoff_files_block(self, output):
        _, _, after = output.partition("  files:")
        return after.partition("  tests-run:")[0]

    def test_the_handoff_files_come_from_git_and_keep_the_listed_change_text(self):
        self.branch_with({"a.py": "x = 1\n", "b.py": "y = 1\n"})
        self.write("a.py", "x = 2\n")
        self.write("new_helper.py", "z = 1\n")
        handoff = self.handoff_input(files=[{"path": "a.py", "change": "merged parse"},
                                            {"path": "b.py", "change": "listed but not changed"}])
        done = self.flow("handoff", "--input", self.log_input({"handoff": handoff}))
        self.assertEqual(done.returncode, 0, done.stderr)
        block = self.handoff_files_block(done.stdout)
        self.assertIn("    - path: a.py\n      change: merged parse\n", block)
        self.assertIn("    - path: new_helper.py\n      change: changed in the working tree against HEAD\n", block)
        self.assertNotIn("b.py", block)

    def test_the_handoff_needs_no_files_list_and_names_the_changed_files(self):
        self.branch_with({"a.py": "x = 1\n"})
        self.write("a.py", "x = 2\n")
        handoff = {"tests_run": "none", "flagged": "none"}
        done = self.flow("handoff", "--input", self.log_input({"handoff": handoff}))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("    - path: a.py\n", done.stdout)

    def test_the_handoff_of_a_clean_tree_has_an_empty_files_list(self):
        self.branch_with({"a.py": "x = 1\n"})
        handoff = self.handoff_input(files=[{"path": "a.py", "change": "claimed but not on disk"}])
        done = self.flow("handoff", "--input", self.log_input({"handoff": handoff}))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIn("  files: []\n", done.stdout)
        self.assertNotIn("a.py", done.stdout)

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

    def test_log_result_outside_the_verdicts_writes_nothing_and_an_underscore_verdict_is_accepted(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "findings": [], "result": "NEEDS"}
        done = self.log("branch", payload)
        self.assertEqual(done.returncode, 1)
        self.assertIn("is not PASS, PASS_WITH_WARNINGS, NEEDS_CHANGES or NOT_DISPATCHED", done.stderr)
        self.assertEqual(self.finding_rows(), [])
        accepted = self.log("branch", {**payload, "result": "NEEDS_CHANGES"})
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(len(self.finding_rows()), 1)

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
        escape_base = ["stage_found=refactor", "gate_missed=review", "class=smell", "severity=low", "guard=none",
                       "miss_reason=unknown"]
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

    def test_log_reports_a_writer_refusal_and_a_rerun_writes_only_the_missing_rows(self):
        self.branch_with({"a.py": "x = 1\n"})
        payload = {"finder": "smell-reviewer", "lane": "code", "guards": {"duplication": "vibes"},
                   "findings": [self.finding()]}
        refusing = self.temp_root / "refusing-escape-writer"
        refusing.write_text('#!/usr/bin/env bash\n[ "$1" = --check ] && exit 0\nexit 1\n')
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

    def test_log_writer_failure_after_earlier_rows_still_hands_off_and_keeps_the_earlier_rows(self):
        self.branch_with({"a.py": "x = 1\n"})
        failing = self.temp_root / "failing-writer"
        failing.write_text('#!/usr/bin/env bash\n[ "$1" = --check ] && exit 0\nexit 7\n')
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
        failing.write_text('#!/usr/bin/env bash\n[ "$1" = --check ] && exit 0\nexit 7\n')
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
        state_file = self.home / ".claude" / "state" / "refactor-flow" / "written-rows.json"
        state_file.parent.mkdir(parents=True)
        seeded = {str((self.temp_root / f"run-{index}.json").resolve()): ["seeded"] for index in range(50)}
        state_file.write_text(json.dumps(seeded))
        done = self.flow("log", "--mode", "branch", "--input", self.log_input(payload, "run-50.json"))
        self.assertEqual(done.returncode, 0, done.stderr)
        state = json.loads(state_file.read_text())
        self.assertEqual(len(state), 50)
        self.assertNotIn(str((self.temp_root / "run-0.json").resolve()), state)
        self.assertIn(str((self.temp_root / "run-1.json").resolve()), state)
        self.assertIn(str((self.temp_root / "run-50.json").resolve()), state)

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

    def test_log_audit_diff_loc_counts_files_deleted_under_a_live_directory(self):
        self.write("mod/a.py", "a\n")
        self.write("mod/b.py", "c\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "add mod")
        self.git("rm", "-q", "mod/a.py")
        payload = {"finder": "smell-reviewer", "lane": "code", "target": ["mod"], "findings": []}
        done = self.log("audit", payload)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.finding_rows()[0]["diff_loc"], "2")

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
