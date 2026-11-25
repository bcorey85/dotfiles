"""Checks for the uncommitted change of a repo, read from git."""
import importlib.util
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("UNCOMMITTED_CHANGE_MODULE") or toolkit_paths.LIB_DIR / "uncommitted_change.py")
sys.path.insert(0, str(MODULE.parent))
module_spec = importlib.util.spec_from_file_location("uncommitted_change", MODULE)
uncommitted_change = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(uncommitted_change)

GIT_ENV = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}


class UncommittedChangeTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name)
        self.git("init", "-q")
        (self.repo / "a.txt").write_text("1\n2\n3\n4\n5\n6\n7\n8\n9\n10\n")
        (self.repo / "gone.txt").write_text("x\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, env=GIT_ENV, check=True, capture_output=True)

    def test_a_clean_tree_prints_one_line(self):
        self.assertEqual(uncommitted_change.hunk_lines(self.repo), ["no uncommitted change"])

    def test_a_path_git_quotes_in_the_diff_header_gets_one_changed_line(self):
        (self.repo / 'q"t.txt').write_text("1\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "quoted")
        (self.repo / 'q"t.txt').write_text("2\n")
        self.assertEqual(uncommitted_change.hunk_lines(self.repo), ['q"t.txt (changed)'])

    def test_each_run_deletion_and_untracked_file_gets_a_line(self):
        (self.repo / "a.txt").write_text("1\nTWO\n3\n4\n5\n6\n7\n8\nNINE\nTEN\n")
        (self.repo / "gone.txt").unlink()
        (self.repo / "new.txt").write_text("n\n")
        self.assertEqual(uncommitted_change.hunk_lines(self.repo),
                         ["a.txt:2", "a.txt:9-10", "gone.txt (deleted)", "new.txt (untracked)"])

    def test_a_binary_rewrite_a_mode_change_and_a_rename_each_get_a_changed_line(self):
        (self.repo / "bin.dat").write_bytes(b"\0\1\2")
        (self.repo / "s.sh").write_text("echo\n")
        (self.repo / "t.txt").write_text("keep this line\nand this one\nand a third\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "more")
        (self.repo / "bin.dat").write_bytes(b"\0\3\4\5")
        (self.repo / "s.sh").chmod(0o755)
        self.git("mv", "t.txt", "r.txt")
        self.assertEqual(uncommitted_change.hunk_lines(self.repo),
                         ["bin.dat (changed)", "r.txt (changed)", "s.sh (changed)"])

    def test_a_staged_new_file_gets_a_range_line_and_no_dev_null_line(self):
        (self.repo / "added.txt").write_text("a\nb\n")
        self.git("add", "added.txt")
        self.assertEqual(uncommitted_change.hunk_lines(self.repo), ["added.txt:1-2"])

    def test_a_diff_prefix_config_does_not_change_the_path_keys(self):
        self.git("config", "diff.mnemonicPrefix", "true")
        (self.repo / "a.txt").write_text("1\nTWO\n3\n4\n5\n6\n7\n8\n9\n10\n")
        self.assertEqual(uncommitted_change.hunk_lines(self.repo), ["a.txt:2"])

    def test_paths_are_relative_to_a_repo_folder_below_the_git_root(self):
        sub = self.repo / "sub"
        sub.mkdir()
        (sub / "inner.txt").write_text("1\n2\n")
        self.git("add", ".")
        self.git("commit", "-q", "-m", "sub")
        (sub / "inner.txt").write_text("1\nTWO\n")
        self.assertEqual(uncommitted_change.hunk_lines(sub), ["inner.txt:2"])

    def test_raw_entries_sort_into_changed_deleted_and_submodule_paths(self):
        raw = (":160000 160000 aaa bbb M\0sub\0:100644 100644 aaa bbb M\0a.txt\0"
               ":100644 100644 aaa bbb R100\0old.txt\0new.txt\0:100644 000000 aaa 000 D\0gone.txt\0"
               ":100644 100644 aaa bbb C75\0src.txt\0copy.txt\0:160000 000000 aaa 000 D\0oldsub\0")

        changes = uncommitted_change.parse_raw_changes(raw)

        self.assertEqual(changes.changed, {"sub", "a.txt", "new.txt", "gone.txt", "copy.txt", "oldsub"})
        self.assertEqual(changes.submodules, {"sub"}, "a path with mode 160000 is a submodule")
        self.assertEqual(changes.deleted, {"gone.txt", "oldsub"})

    def test_a_moved_submodule_commit_is_named_changed_with_no_line_run(self):
        sub_source = self.repo.parent / (self.repo.name + "-sub-source")
        sub_source.mkdir()
        self.addCleanup(shutil.rmtree, sub_source, True)
        subprocess.run(["git", "init", "-q"], cwd=sub_source, env=GIT_ENV, check=True, capture_output=True)
        (sub_source / "f.txt").write_text("1\n")
        subprocess.run(["git", "add", "."], cwd=sub_source, env=GIT_ENV, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-q", "-m", "s"], cwd=sub_source, env=GIT_ENV, check=True,
                       capture_output=True)
        self.git("-c", "protocol.file.allow=always", "submodule", "add", "-q", str(sub_source), "sub")
        self.git("commit", "-q", "-m", "add sub")
        (self.repo / "sub" / "f.txt").write_text("2\n")
        subprocess.run(["git", "commit", "-q", "-am", "move"], cwd=self.repo / "sub", env=GIT_ENV, check=True,
                       capture_output=True)

        self.assertEqual(uncommitted_change.hunk_lines(self.repo), ["sub (changed)"])

    def test_a_not_git_folder_says_the_change_was_not_read(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(uncommitted_change.hunk_lines(folder), [uncommitted_change.NOT_READ_LINE])


if __name__ == "__main__":
    unittest.main()
