import os
import pathlib
import subprocess
import tempfile
import unittest

HOOK = os.environ.get("PRE_COMMIT_HOOK", str(pathlib.Path(__file__).resolve().parents[2] / ".githooks" / "pre-commit"))
CHANGE_FILE = "docs/changes/notes/2026-10-25-a-change.md"
TOOLKIT_FILES = (
    "claude/.claude/agents/coder.md",
    "claude/.claude/skills/code/SKILL.md",
    "claude/.claude/commands/x.md",
    "claude/.claude/hooks/gate.py",
    "claude/.claude/scripts/lib/util.py",
    "claude/.claude/CLAUDE.md",
)


class PreCommitHookTests(unittest.TestCase):
    def setUp(self):
        repo = tempfile.TemporaryDirectory()
        evals = tempfile.TemporaryDirectory()
        self.addCleanup(repo.cleanup)
        self.addCleanup(evals.cleanup)
        self.repo = pathlib.Path(repo.name)
        self.evals = pathlib.Path(evals.name)
        self.git("init", "-q")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True)

    def stage(self, relative_path, text="x\n"):
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", relative_path)

    def install_checker(self, exit_code):
        script = self.evals / "bin" / "build_changes.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            f"import sys\nprint('args', sys.argv[1:])\nsys.exit({exit_code})\n",
            encoding="utf-8",
        )

    def run_hook(self):
        env = {**os.environ, "AGENT_EVALS_DIR": str(self.evals)}
        return subprocess.run([HOOK], cwd=self.repo, env=env, capture_output=True, text=True)

    def test_toolkit_path_without_change_file_is_refused(self):
        self.install_checker(0)
        for path in TOOLKIT_FILES:
            with self.subTest(path=path):
                self.git("reset", "-q")
                self.stage(path)
                result = self.run_hook()
                self.assertEqual(result.returncode, 1)
                self.assertIn("build_changes.py new", result.stderr)
                self.assertIn(path, result.stderr)

    def test_a_toolkit_path_git_would_quote_is_refused_naming_the_real_path(self):
        self.install_checker(0)
        quoted_paths = [
            "claude/.claude/skills/tab\tname/SKILL.md",
            "claude/.claude/skills/café/SKILL.md",
            "claude/.claude/skills/new\nline/SKILL.md",
        ]
        for path in quoted_paths:
            with self.subTest(path=path):
                self.git("reset", "-q")
                self.stage(path)
                result = self.run_hook()
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(path, result.stderr)
                self.assertIn("change-file-check: the change set changes the toolkit", result.stderr)

    def test_toolkit_path_with_added_change_file_passes(self):
        self.install_checker(0)
        self.stage(TOOLKIT_FILES[0])
        self.stage(CHANGE_FILE)
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_change_file_index_alone_does_not_count(self):
        self.install_checker(0)
        self.stage(TOOLKIT_FILES[0])
        self.stage("docs/changes/index.md")
        self.assertEqual(self.run_hook().returncode, 1)

    def test_a_deleted_change_file_does_not_count(self):
        self.install_checker(0)
        self.stage(CHANGE_FILE)
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--no-verify", "-m", "seed")
        self.git("rm", "-q", CHANGE_FILE)
        self.stage(TOOLKIT_FILES[0])
        self.assertEqual(self.run_hook().returncode, 1)

    def test_commit_outside_the_toolkit_needs_no_change_file(self):
        self.install_checker(0)
        self.stage("README.md")
        self.assertEqual(self.run_hook().returncode, 0)

    def test_failing_check_refuses_and_runs_with_check_and_root(self):
        self.install_checker(1)
        self.stage("README.md")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'--check', '--root', 'docs/changes'", result.stdout)

    def test_missing_checker_warns_once_and_allows(self):
        self.stage("README.md")
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)
        self.assertIn("warning", result.stderr)

    def test_missing_checker_still_refuses_toolkit_path_without_change_file(self):
        self.stage(TOOLKIT_FILES[0])
        self.assertEqual(self.run_hook().returncode, 1)

    def install_drift_check(self, exit_code):
        """A stand-in toolkit_drift.py that prints the CLAUDE.md of the tree it was handed."""
        script = self.evals / "bin" / "toolkit_drift.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "import pathlib, sys\n"
            "tree = pathlib.Path(sys.argv[sys.argv.index('--toolkit') + 1])\n"
            "claude_md = tree / 'CLAUDE.md'\n"
            "print('drift', claude_md.read_text() if claude_md.is_file() else '')\n"
            f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )

    def test_a_drift_problem_in_a_staged_rule_file_refuses_the_commit(self):
        self.install_checker(0)
        self.install_drift_check(1)
        self.stage("claude/.claude/CLAUDE.md")
        self.stage(CHANGE_FILE)
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("toolkit_drift.py failed", result.stderr)

    def test_the_drift_check_reads_the_staged_text_not_the_work_tree(self):
        self.install_checker(0)
        self.install_drift_check(0)
        self.stage("claude/.claude/CLAUDE.md", "staged text\n")
        (self.repo / "claude/.claude/CLAUDE.md").write_text("unstaged text\n", encoding="utf-8")
        self.stage(CHANGE_FILE)
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("staged text", result.stdout)
        self.assertNotIn("unstaged text", result.stdout)

    def test_the_drift_check_skips_scripts_and_hooks(self):
        self.install_checker(0)
        self.install_drift_check(1)
        self.stage("claude/.claude/scripts/lib/util.py")
        self.stage(CHANGE_FILE)
        self.assertEqual(self.run_hook().returncode, 0)

    def install_line_drift_check(self, stray_line=None, silent_crash=False, pass_at_head=False):
        """A stand-in toolkit_drift.py: one problem line on stderr per CLAUDE.md line starting `stale`.

        silent_crash: exit 1 with no output when a line starts with `crash`.
        pass_at_head: on the HEAD tree, print the problem lines but exit 0.
        """
        script = self.evals / "bin" / "toolkit_drift.py"
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(
            "import pathlib, sys\n"
            "tree = pathlib.Path(sys.argv[sys.argv.index('--toolkit') + 1])\n"
            "claude_md = tree / 'CLAUDE.md'\n"
            "lines = claude_md.read_text().splitlines() if claude_md.is_file() else []\n"
            f"if {silent_crash!r} and any(line.startswith('crash') for line in lines):\n"
            "    sys.exit(1)\n"
            "problems = [line for line in lines if line.startswith('stale')]\n"
            "for line in problems:\n"
            "    print('toolkit_drift: ' + line, file=sys.stderr)\n"
            f"stray = {stray_line!r}\n"
            "if stray and any(line.startswith('crash') for line in lines):\n"
            "    print(stray, file=sys.stderr)\n"
            "    sys.exit(1)\n"
            f"at_head = {pass_at_head!r} and '/head/' in str(tree)\n"
            "sys.exit(1 if problems and not at_head else 0)\n",
            encoding="utf-8",
        )

    def commit_rule_file_at_head(self, text):
        self.stage("claude/.claude/CLAUDE.md", text)
        self.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--no-verify", "-m", "seed")

    def stage_rule_file_with_change_file(self, text):
        self.stage("claude/.claude/CLAUDE.md", text)
        self.stage(CHANGE_FILE)

    def test_drift_already_at_head_does_not_refuse_a_commit_that_adds_none(self):
        self.install_checker(0)
        self.install_line_drift_check()
        self.commit_rule_file_at_head("stale a\nstale b\n")
        self.stage_rule_file_with_change_file("stale a\nstale b\nfine\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("2 toolkit drift line(s) already at HEAD", result.stderr)

    def test_a_commit_that_adds_a_drift_line_is_refused_naming_only_that_line(self):
        self.install_checker(0)
        self.install_line_drift_check()
        self.commit_rule_file_at_head("stale a\n")
        self.stage_rule_file_with_change_file("stale a\nstale c\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("stale c", result.stderr)
        self.assertNotIn("stale a", result.stderr)

    def test_a_commit_that_shrinks_drift_passes(self):
        self.install_checker(0)
        self.install_line_drift_check()
        self.commit_rule_file_at_head("stale a\nstale b\n")
        self.stage_rule_file_with_change_file("stale a\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("1 toolkit drift line(s) already at HEAD", result.stderr)

    def test_a_staged_output_line_that_is_not_a_problem_line_is_refused(self):
        self.install_checker(0)
        self.install_line_drift_check(stray_line="Traceback: boom")
        self.commit_rule_file_at_head("stale a\n")
        self.stage_rule_file_with_change_file("stale a\ncrash\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("Traceback: boom", result.stderr)
        self.assertNotIn("stale a", result.stderr)
        self.assertNotIn("entries above", result.stderr)

    def test_a_failing_run_that_prints_nothing_is_refused_as_a_crash(self):
        self.install_checker(0)
        self.install_line_drift_check(silent_crash=True)
        self.commit_rule_file_at_head("fine\n")
        self.stage_rule_file_with_change_file("crash\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("printed no problem line", result.stderr)
        self.assertNotIn("entries above", result.stderr)

    def test_problems_count_as_added_when_the_head_run_passes(self):
        self.install_checker(0)
        self.install_line_drift_check(pass_at_head=True)
        self.commit_rule_file_at_head("stale x\n")
        self.stage_rule_file_with_change_file("stale x\nfine\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("stale x", result.stderr)

    def test_drift_with_no_head_commit_is_refused(self):
        self.install_checker(0)
        self.install_line_drift_check()
        self.stage_rule_file_with_change_file("stale a\n")
        result = self.run_hook()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("stale a", result.stderr)

    def test_a_missing_drift_check_notes_it_and_allows(self):
        self.install_checker(0)
        self.stage("claude/.claude/skills/code/SKILL.md")
        self.stage(CHANGE_FILE)
        result = self.run_hook()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("toolkit_drift.py not found", result.stderr)


if __name__ == "__main__":
    unittest.main()
