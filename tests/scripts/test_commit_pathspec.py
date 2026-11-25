"""Checks for lib/commit_pathspec.py (what a `git commit` names) and lib/shared_clones.py (the clone list)."""
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

import commit_pathspec
import shared_clones

BARE = (
    ("-m x", ["-m", "x"]),
    ("-am with message", ["-am", "x"]),
    ("--all", ["--all", "-m", "x"]),
    ("-a after other flags", ["-nsa", "-m", "x", "--", "f"]),
    ("-i with a path", ["-i", "-m", "x", "--", "a"]),
    ("--include with a path", ["--include", "-m", "x", "--", "a"]),
    ("--inc abbreviation", ["--inc", "-m", "x", "--", "a"]),
    ("--am is not --amend here", ["--am", "-a", "-m", "x"]),
    ("-m takes the -- as its value", ["-m", "--", "a.txt"]),
    ("path word without --", ["-m", "x", "a.txt"]),
    ("empty separator", ["-m", "x", "--"]),
    ("-F value is no path", ["-F", "--", "f"]),
    ("-c value is no path", ["-c", "--", "f"]),
    ("-C value is no path", ["-C", "--", "f"]),
    ("-t value is no path", ["-t", "--", "f"]),
    ("--author value is no path", ["--author", "--", "f"]),
    ("--cleanup value is no path", ["--cleanup", "--", "f"]),
    ("--file value is no path", ["--file", "--", "f"]),
    ("-m then -F", ["-m", "x", "-F", "--", "f"]),
    ("--pathspec-from-file with -a", ["--pathspec-from-file=l", "-a", "-m", "x"]),
    ("--date is not --dry-run", ["--date=2020-01-01", "-m", "x"]),
    ("whole-tree dot pathspec", ["-m", "x", "--", "."]),
    ("whole-tree colon-slash pathspec", ["-m", "x", "--", ":/"]),
    ("whole-tree dot-slash pathspec", ["-m", "x", "--", "./"]),
    ("whole-tree :(top) pathspec", ["-m", "x", "--", ":(top)"]),
    ("whole-tree glob pathspec", ["-m", "x", "--", "*"]),
    ("whole-tree dot beside a file", ["-m", "x", "--", "bin/a.py", "."]),
)
NAMED = (
    ("path after --", ["-m", "x", "--", "a"]),
    ("--pathspec-from-file=", ["-m", "x", "--pathspec-from-file=l"]),
    ("--pathspec-fr abbreviation", ["-m", "x", "--pathspec-fr=l"]),
    ("--pathspec-from-file with a separate value", ["--pathspec-from-file", "l", "-m", "x"]),
    ("glued value holding an a", ["-mall", "--", "f"]),
    ("glued value holding an i", ["-mini", "--", "f"]),
    ("glued -C value holding an a", ["-Cabc", "--", "f"]),
    ("-u value holding an a", ["-uall", "-m", "x", "--", "f"]),
    ("-S value holding an a", ["-Sabc", "-m", "x", "--", "f"]),
    ("--message= value", ["--message=a", "--", "f"]),
    ("--message value that looks like --all", ["--message", "--all", "--", "f"]),
    ("exact --amend", ["--amend", "--no-edit"]),
    ("--dry-run", ["--dry-run", "-m", "x"]),
    ("--dr abbreviation", ["--dr", "-m", "x"]),
    ("--short implies --dry-run", ["--short"]),
    ("--porcelain implies --dry-run", ["--porcelain"]),
    ("--long implies --dry-run", ["--long"]),
    ("--l abbreviation of --long", ["--l"]),
    ("--por abbreviation of --porcelain", ["--por"]),
    ("--sh abbreviation of --short", ["--sh"]),
    ("--in is ambiguous, not --include", ["--in", "-m", "x", "--", "a"]),
    ("--help", ["--help"]),
    ("-h", ["-h"]),
)


class IsBareCommitTest(unittest.TestCase):
    def test_commits_that_take_the_whole_index_are_bare(self):
        for label, arguments in BARE:
            with self.subTest(label):
                self.assertTrue(commit_pathspec.is_bare_commit(arguments), arguments)

    def test_commits_that_name_their_files_are_not_bare(self):
        for label, arguments in NAMED:
            with self.subTest(label):
                self.assertFalse(commit_pathspec.is_bare_commit(arguments), arguments)


class SharedClonesTest(unittest.TestCase):
    def test_default_list_expands_home(self):
        home = pathlib.Path(os.environ.get("TMPDIR", "/tmp")).resolve()
        with unittest.mock.patch.dict(os.environ, {"HOME": str(home)}):
            os.environ.pop(shared_clones.SHARED_CLONES_ENV, None)
            roots = shared_clones.shared_clone_roots()
        self.assertEqual(roots, [home / "agent-evals", home / "dotfiles"])

    def test_override_replaces_the_default_and_splits_on_pathsep(self):
        value = os.pathsep.join(["/tmp/one", "", "/tmp/two"])
        with unittest.mock.patch.dict(os.environ, {shared_clones.SHARED_CLONES_ENV: value}):
            roots = shared_clones.shared_clone_roots()
        self.assertEqual(roots, [pathlib.Path("/tmp/one").resolve(), pathlib.Path("/tmp/two").resolve()])

    def test_a_folder_outside_any_work_tree_is_not_a_shared_clone(self):
        with (
            tempfile.TemporaryDirectory() as outside,
            unittest.mock.patch.dict(os.environ, {shared_clones.SHARED_CLONES_ENV: "/tmp/one"}),
        ):
            self.assertFalse(shared_clones.is_shared_clone(outside))

    def test_a_repo_root_and_its_subfolder_match_through_a_symlinked_override(self):
        with tempfile.TemporaryDirectory() as parent:
            real = pathlib.Path(parent).resolve() / "real"
            real.mkdir()
            subprocess.run(["git", "init", "-q", str(real)], check=True)
            (real / "sub").mkdir()
            link = pathlib.Path(parent).resolve() / "link"
            link.symlink_to(real)
            with unittest.mock.patch.dict(os.environ, {shared_clones.SHARED_CLONES_ENV: str(link)}):
                self.assertTrue(shared_clones.is_shared_clone(real))
                self.assertTrue(shared_clones.is_shared_clone(real / "sub"))

    def test_a_git_that_cannot_run_reads_as_not_shared_and_says_so_on_stderr(self):
        failures = (OSError("no git"), subprocess.TimeoutExpired("git", 10))
        for failure in failures:
            with self.subTest(type(failure).__name__):
                stderr = io.StringIO()
                with (
                    unittest.mock.patch.object(shared_clones.subprocess, "run", side_effect=failure),
                    unittest.mock.patch.object(shared_clones.sys, "stderr", stderr),
                ):
                    self.assertFalse(shared_clones.is_shared_clone("/tmp/somewhere"))
                self.assertIn("[shared_clones] git -C /tmp/somewhere rev-parse failed (", stderr.getvalue())
                self.assertIn("); reading the folder as not shared", stderr.getvalue())

    def test_empty_override_lists_no_clone(self):
        with unittest.mock.patch.dict(os.environ, {shared_clones.SHARED_CLONES_ENV: ""}):
            self.assertEqual(shared_clones.shared_clone_roots(), [])


if __name__ == "__main__":
    unittest.main()
