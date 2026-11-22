"""Checks for tests/changed_scope.py: only a change made wholly of skill or agent markdown skips the unit tests."""
import importlib.util
import os
import pathlib
import subprocess
import tempfile
import unittest

DEFAULT_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "changed_scope.py"
SCRIPT = pathlib.Path(os.environ.get("CHANGED_SCOPE_SCRIPT") or DEFAULT_SCRIPT)
SPEC = importlib.util.spec_from_file_location("changed_scope", SCRIPT)
changed_scope = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(changed_scope)

SKILL_FILE = "claude/.claude/skills/audit/SKILL.md"
AGENT_FILE = "claude/.claude/agents/coder.md"


class MarkdownOnlyTest(unittest.TestCase):
    def test_skill_and_agent_markdown_alone_is_markdown_only(self):
        self.assertTrue(changed_scope.is_markdown_only([SKILL_FILE, AGENT_FILE]))

    def test_any_other_path_makes_the_change_full(self):
        for other in ("claude/.claude/scripts/lib/x.py", "claude/.claude/skills/audit/scripts/run.py",
                      "claude/.claude/skills/audit/notes.txt", "docs/changes/x.md", "claude/.claude/CLAUDE.md",
                      "tests/run.sh"):
            with self.subTest(other=other):
                self.assertFalse(changed_scope.is_markdown_only([SKILL_FILE, other]))

    def test_no_change_is_full(self):
        self.assertFalse(changed_scope.is_markdown_only([]))
        self.assertFalse(changed_scope.is_markdown_only(None))


class ScopeOfARepoTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = pathlib.Path(self.tmp.name)
        self.git("init", "-q", "-b", "master")
        for name in (SKILL_FILE, AGENT_FILE, "claude/.claude/scripts/lib/x.py"):
            self.write(name, "one\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "base")
        self.git("update-ref", "refs/remotes/origin/master", "HEAD")
        self.git("checkout", "-q", "-b", "branch")
        changed_scope.REPO_ROOT = self.repo
        self.addCleanup(setattr, changed_scope, "REPO_ROOT", SCRIPT.parent.parent)

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.repo), "-c", "user.name=t", "-c", "user.email=t@t", *args],
                       check=True, capture_output=True)

    def write(self, name, text):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def test_an_unstaged_markdown_edit_is_markdown_only(self):
        self.write(SKILL_FILE, "two\n")

        self.assertEqual(changed_scope.scope(), "markdown-only")

    def test_a_committed_markdown_edit_plus_a_new_untracked_one_is_markdown_only(self):
        self.write(SKILL_FILE, "two\n")
        self.git("commit", "-q", "-am", "edit")
        self.write("claude/.claude/agents/new.md", "x\n")

        self.assertEqual(changed_scope.scope(), "markdown-only")

    def test_a_committed_python_change_stays_full_after_the_tree_is_clean(self):
        self.write("claude/.claude/scripts/lib/x.py", "two\n")
        self.git("commit", "-q", "-am", "edit")
        self.write(SKILL_FILE, "two\n")

        self.assertEqual(changed_scope.scope(), "full")

    def test_a_staged_python_change_with_markdown_is_full(self):
        self.write(SKILL_FILE, "two\n")
        self.write("claude/.claude/scripts/lib/x.py", "two\n")
        self.git("add", "-A")

        self.assertEqual(changed_scope.scope(), "full")

    def test_an_untracked_python_file_is_full(self):
        self.write("claude/.claude/scripts/lib/new.py", "x\n")

        self.assertEqual(changed_scope.scope(), "full")

    def test_a_clean_tree_is_full(self):
        self.assertEqual(changed_scope.scope(), "full")

    def test_a_repo_with_no_origin_master_is_full(self):
        self.git("update-ref", "-d", "refs/remotes/origin/master")
        self.write(SKILL_FILE, "two\n")

        self.assertEqual(changed_scope.scope(), "full")


class KeptTestsTest(unittest.TestCase):
    def test_every_kept_test_file_exists(self):
        tests_dir = SCRIPT.parent / "scripts"
        for name in changed_scope.PROMPT_READING_TESTS:
            with self.subTest(name=name):
                self.assertTrue((tests_dir / name).is_file())


if __name__ == "__main__":
    unittest.main()
