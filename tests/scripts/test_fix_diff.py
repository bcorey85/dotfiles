"""Tests for fix_diff.py: the close pass's fix diff, read with the user's index left as it was."""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


class FixDiffTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "T")
        (self.repo / "app.py").write_text("app v1\n")
        (self.repo / "lib.py").write_text("lib v1\n")
        (self.repo / "other.py").write_text("other v1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "files")
        (self.repo / "app.py").write_text("app staged\n")
        git(self.repo, "add", "app.py")
        (self.repo / "other.py").write_text("other unstaged\n")

    def run_script(self, verb):
        return subprocess.run([sys.executable, str(toolkit_paths.FIX_DIFF_SCRIPT), verb], cwd=self.repo,
                              capture_output=True, text=True, check=False)

    def test_show_lists_only_what_changed_after_mark_and_the_index_stays_as_it_was(self):
        staged_before = git(self.repo, "diff", "--cached", "--name-only")
        staged_content_before = git(self.repo, "diff", "--cached")
        status_before = git(self.repo, "status", "--porcelain")

        marked = self.run_script("mark")
        (self.repo / "lib.py").write_text("lib fixed\n")
        (self.repo / "new.py").write_text("new\n")
        shown = self.run_script("show")

        self.assertEqual(0, marked.returncode, marked.stderr)
        self.assertEqual(0, shown.returncode, shown.stderr)
        report = json.loads(shown.stdout)
        self.assertEqual(marked.stdout.strip(), report["reviewed_tree"])
        self.assertEqual(["lib.py", "new.py"], sorted(report["files"]))
        self.assertEqual(f"git diff {report['reviewed_tree']} {report['fixed_tree']}", report["diff_command"])
        self.assertEqual("app.py", staged_before)
        self.assertEqual(staged_before, git(self.repo, "diff", "--cached", "--name-only"))
        self.assertEqual(staged_content_before, git(self.repo, "diff", "--cached"))
        # The fix edits (lib.py, new.py) are the only change since the status taken before mark.
        self.assertEqual(sorted([*status_before.splitlines(), " M lib.py", "?? new.py"]),
                         sorted(git(self.repo, "status", "--porcelain").splitlines()))

    def test_show_right_after_mark_lists_no_files(self):
        self.run_script("mark")

        shown = self.run_script("show")

        self.assertEqual(0, shown.returncode, shown.stderr)
        self.assertEqual([], json.loads(shown.stdout)["files"])

    def test_show_lists_both_paths_of_a_moved_file(self):
        self.run_script("mark")
        git(self.repo, "mv", "lib.py", "lib_moved.py")

        shown = self.run_script("show")

        self.assertEqual(0, shown.returncode, shown.stderr)
        self.assertEqual(["lib.py", "lib_moved.py"], sorted(json.loads(shown.stdout)["files"]))

    def test_mark_and_show_work_in_a_linked_worktree(self):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "all")
        linked_parent = tempfile.TemporaryDirectory()
        self.addCleanup(linked_parent.cleanup)
        linked = pathlib.Path(linked_parent.name) / "linked"
        git(self.repo, "worktree", "add", "-q", "-b", "side", str(linked))
        (linked / "lib.py").write_text("lib fixed\n")

        def run_in_linked(verb):
            return subprocess.run([sys.executable, str(toolkit_paths.FIX_DIFF_SCRIPT), verb], cwd=linked,
                                  capture_output=True, text=True, check=False)

        marked = run_in_linked("mark")
        (linked / "app.py").write_text("app fixed\n")
        shown = run_in_linked("show")

        self.assertEqual(0, marked.returncode, marked.stderr)
        self.assertEqual(0, shown.returncode, shown.stderr)
        self.assertEqual(["app.py"], json.loads(shown.stdout)["files"])

    def test_a_missing_or_unknown_verb_exits_non_zero_with_usage(self):
        no_verb = subprocess.run([sys.executable, str(toolkit_paths.FIX_DIFF_SCRIPT)], cwd=self.repo,
                                 capture_output=True, text=True, check=False)
        unknown_verb = self.run_script("bogus")

        for done in (no_verb, unknown_verb):
            self.assertNotEqual(0, done.returncode)
            self.assertIn("usage: fix_diff.py", done.stderr)

    def test_mark_outside_a_git_checkout_exits_non_zero_with_no_traceback(self):
        with tempfile.TemporaryDirectory() as bare_folder:
            done = subprocess.run([sys.executable, str(toolkit_paths.FIX_DIFF_SCRIPT), "mark"], cwd=bare_folder,
                                  capture_output=True, text=True, check=False)

        self.assertNotEqual(0, done.returncode)
        self.assertIn("fix_diff.py:", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_show_before_mark_exits_2_and_names_mark(self):
        shown = self.run_script("show")

        self.assertEqual(2, shown.returncode)
        self.assertIn("fix_diff.py mark", shown.stderr)


if __name__ == "__main__":
    unittest.main()
