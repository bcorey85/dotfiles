import os
import pathlib
import subprocess
import tempfile
import unittest

HOOK = os.environ.get("PRE_COMMIT_HOOK", str(pathlib.Path(__file__).resolve().parents[2] / ".githooks" / "pre-commit"))
CHANGE_FILE = "docs/changes/2026-10-25-a-change.md"
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
        stubs = tempfile.TemporaryDirectory()
        self.addCleanup(stubs.cleanup)
        self.stubs = pathlib.Path(stubs.name)
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

    def install_ledger_stub(self, guard_exit):
        """A `ledger` that exits `guard_exit` for `guard --staged`; returns its folder."""
        stub = self.stubs / "ledger"
        stub.parent.mkdir(parents=True, exist_ok=True)
        stub.write_text(f'#!/bin/sh\n[ "$*" = "guard --staged" ] || exit 64\nexit {guard_exit}\n', encoding="utf-8")
        stub.chmod(0o755)
        return str(self.stubs)

    def path_without_ledger(self):
        folders = [folder for folder in os.environ["PATH"].split(os.pathsep)
                   if not (pathlib.Path(folder) / "ledger").exists()]
        return os.pathsep.join(folders)

    def run_hook(self, guard_exit=0, ledger_on_path=True):
        path = self.install_ledger_stub(guard_exit) + os.pathsep + os.environ["PATH"] if ledger_on_path \
            else self.path_without_ledger()
        env = {**os.environ, "AGENT_EVALS_DIR": str(self.evals), "PATH": path}
        return subprocess.run([HOOK], cwd=self.repo, env=env, capture_output=True, text=True)

    def test_no_ledger_on_path_refuses_and_names_the_install_command(self):
        self.install_checker(0)
        self.stage("README.md")
        result = self.run_hook(ledger_on_path=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("cargo install --path ~/dev/agent-ledger", result.stderr)

    def test_a_guard_that_refuses_refuses_the_commit(self):
        self.install_checker(0)
        self.stage("README.md")
        result = self.run_hook(guard_exit=1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ledger guard refused", result.stderr)

    def test_a_refusing_guard_stops_before_the_missing_checker_warning_and_any_checker_runs(self):
        home = self.stubs / "home"
        decoy_checker = home / "agent-evals" / "bin" / "build_changes.py"
        decoy_checker.parent.mkdir(parents=True)
        sentinel = self.stubs / "checker-ran"
        decoy_checker.write_text(
            f"import pathlib\npathlib.Path({str(sentinel)!r}).write_text('ran')\n", encoding="utf-8")
        self.stage(TOOLKIT_FILES[0])
        env = {**os.environ, "HOME": str(home), "AGENT_EVALS_DIR": str(self.evals),
               "PATH": self.install_ledger_stub(1) + os.pathsep + os.environ["PATH"]}
        result = subprocess.run([HOOK], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("ledger guard refused", result.stderr)
        self.assertNotIn("warning", result.stderr)
        self.assertNotIn("build_changes.py new", result.stderr)
        self.assertFalse(sentinel.exists())

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


if __name__ == "__main__":
    unittest.main()
