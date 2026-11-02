import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import handoff_files
import script_utils

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


class ChangedFilesTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name)
        self.git("init", "-q")
        self.write(".gitignore", "ignored.log\n")
        self.write("kept.py", "a\n")
        self.write("gone.py", "a\n")
        self.write("edited.py", "a\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, env={**os.environ, **GIT_ENV}, check=True, capture_output=True)

    def write(self, name, body):
        target = self.repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)

    def test_changed_files_lists_edits_and_untracked_files_but_not_deletions_or_ignored_files(self):
        self.write("edited.py", "b\n")
        self.write("src/new.py", "n\n")
        self.write("ignored.log", "x\n")
        (self.repo / "gone.py").unlink()
        self.assertEqual(script_utils.changed_files(self.repo), ["edited.py", "src/new.py"])

    def test_changed_files_against_an_earlier_commit_includes_committed_changes(self):
        base = script_utils.git_output(self.repo, "rev-parse", "HEAD")
        self.write("edited.py", "b\n")
        self.git("commit", "-q", "-am", "edit")
        self.assertEqual(script_utils.changed_files(self.repo), [])
        self.assertEqual(script_utils.changed_files(self.repo, base), ["edited.py"])


class FileEntryLinesTest(unittest.TestCase):
    def test_a_listed_path_keeps_its_change_text_and_any_other_path_gets_the_default(self):
        lines = handoff_files.file_entry_lines(["a.py", "b.py"], {"a.py": "merged parse"}, "stock")
        self.assertEqual(lines, ["    - path: a.py", "      change: merged parse",
                                 "    - path: b.py", "      change: stock"])

    def test_extra_lines_follow_the_entry_of_their_path_only(self):
        lines = handoff_files.file_entry_lines(["a.py", "b.py"], {}, "stock", {"b.py": ["      why:"]})
        self.assertEqual(lines, ["    - path: a.py", "      change: stock",
                                 "    - path: b.py", "      change: stock", "      why:"])

    def test_no_paths_give_no_lines(self):
        self.assertEqual(handoff_files.file_entry_lines([], {"a.py": "x"}, "stock"), [])


if __name__ == "__main__":
    unittest.main()
