"""Checks for directory_emptying_deletes.py: which directories a command's plain `rm` calls would empty."""
import os
import pathlib
import shutil
import sys
import tempfile
import unittest
import unittest.mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import directory_emptying_deletes
import hook_input


class EmptiedDirectoriesTest(unittest.TestCase):
    def setUp(self):
        # Fixtures live under a temp dir, and a folder under a temp root never counts as emptied. The patch makes
        # the code read the fixture as an ordinary folder; the temp-folder test stops it to use the real check.
        self.root = pathlib.Path(tempfile.mkdtemp(prefix="emptying-fixture-"))
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.temp_roots_patch = unittest.mock.patch.object(hook_input, "temp_roots", return_value=[])
        self.temp_roots_patch.start()
        self.addCleanup(self.temp_roots_patch.stop)
        self.folder = self.make_folder("d", ("a", "b"))

    def make_folder(self, name, files, parent=None):
        folder = (parent or self.root) / name
        folder.mkdir(parents=True)
        for file_name in files:
            (folder / file_name).write_text("x")
        return folder

    def emptied(self, command, directory=None):
        return directory_emptying_deletes.emptied_directories(command, str(directory or self.root))

    def test_a_delete_that_names_every_entry_empties_the_folder(self):
        for command in ("rm d/a d/b", "rm d/*", "rm -f d/a d/b", "rm -- d/a d/b", "rm d/a; rm d/b",
                        "rm d/a && rm d/b", "timeout 5 rm d/a d/b", "/bin/rm d/a d/b", f"rm {self.folder}/a d/b"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [str(self.folder)])

    def test_a_delete_after_a_cd_is_placed_in_that_folder(self):
        self.assertEqual(self.emptied("cd d && rm a b"), [str(self.folder)])
        self.assertEqual(self.emptied("rm a b", directory=self.folder), [str(self.folder)])

    def test_a_delete_that_leaves_an_entry_reports_nothing(self):
        for command in ("rm d/a", "rm d/a d/missing", "rm d/a; cd d; rm ../d/a", "rm d/[a]"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [])

    def test_a_hidden_entry_not_matched_by_a_glob_stays(self):
        (self.folder / ".keep").write_text("x")
        self.assertEqual(self.emptied("rm d/*"), [])

    def test_the_last_file_of_a_folder_empties_it(self):
        (self.folder / "a").unlink()
        self.assertEqual(self.emptied("rm d/b"), [str(self.folder)])

    def test_a_recursive_rm_is_left_to_the_recursive_delete_gate(self):
        for command in ("rm -r d", "rm -rf d", "rm -R d", "rm --recursive d", "rm -fr d/a d/b", "rm d/a d/b -r"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [])

    def test_a_temp_folder_or_a_build_folder_reports_nothing(self):
        temp_folder = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, temp_folder, ignore_errors=True)
        (temp_folder / "a").write_text("x")
        self.temp_roots_patch.stop()
        self.assertEqual(self.emptied(f"rm {temp_folder}/a"), [])
        self.temp_roots_patch.start()
        self.make_folder("node_modules", ("a", "b"))
        self.make_folder("src", ("a",), parent=self.root / "node_modules")
        self.assertEqual(self.emptied("rm node_modules/a node_modules/b"), [])
        self.assertEqual(self.emptied("rm node_modules/src/a"), [])

    def test_a_target_with_an_unread_mark_reports_nothing(self):
        # Each folder holds one entry named like the target, so only the skip of the mark keeps the result empty.
        marks = {"dollar": "$VAR", "backtick": "`x`", "brace": "{a,b}"}
        for label, entry_name in marks.items():
            with self.subTest(mark=label):
                self.make_folder(f"e_{label}", (entry_name,))
                self.assertEqual(self.emptied(f"rm e_{label}/{entry_name}"), [])
        for command in ("rm d/$VAR d/b", "rm d/`x` d/a", "rm ~root/a", "rm d/{a,b}"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [])

    def test_a_redirect_glued_to_the_last_target_is_not_part_of_it(self):
        for command in ("rm d/a d/b>/dev/null", "rm d/a 'd/b'>x"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [str(self.folder)])

    def test_quotes_are_removed_from_a_target(self):
        for command in ("rm \"d/a\" 'd/b'", "timeout 5 rm \"d/a\" d/b"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [str(self.folder)])

    def test_an_empty_target_does_not_name_the_current_folder(self):
        self.assertEqual(self.emptied("rm d/a d/b ''"), [str(self.folder)])
        self.assertEqual(self.emptied("rm ''", directory=self.folder), [])

    def test_a_command_with_an_unclosed_quote_reports_nothing(self):
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(self.emptied('rm d/a d/b "'), [])

    def test_two_folders_emptied_by_one_command_are_both_reported_sorted(self):
        other = self.make_folder("c", ("x",))
        # `c` sorts before `d` but comes after it in the command, so only the sort puts it first.
        self.assertEqual(self.emptied("rm d/a d/b c/x"), [str(other), str(self.folder)])

    def test_a_cd_to_an_unread_folder_leaves_later_deletes_unplaced(self):
        self.assertEqual(self.emptied("cd $SOMEWHERE && rm a b", directory=self.folder), [])

    def test_calls_that_are_not_plain_rm_report_nothing(self):
        for command in ("git rm d/a d/b", "echo rm d/a d/b", "echo 'rm d/a d/b'", "ls d/a d/b", "rmdir d"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [])

    def test_text_in_a_heredoc_body_or_a_comment_is_not_a_call(self):
        for command in ("cat <<EOF\nrm d/a d/b\nEOF", "echo x # rm d/a d/b"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [])

    def test_a_folder_that_cannot_be_listed_reports_nothing(self):
        with unittest.mock.patch("os.listdir", side_effect=PermissionError("denied")):
            self.assertEqual(self.emptied("rm d/a d/b"), [])

    def test_an_already_empty_folder_reports_nothing(self):
        (self.folder / "a").unlink()
        (self.folder / "b").unlink()
        self.assertEqual(self.emptied("rm d/x"), [])
        self.assertEqual(self.emptied("rm d/*"), [])

    def test_a_group_cd_ends_where_the_group_closes(self):
        self.assertEqual(self.emptied("(cd d && rm a b)"), [str(self.folder)])
        self.assertEqual(self.emptied("(cd d); rm a b"), [])

    def test_a_container_exec_rm_is_not_a_host_delete(self):
        self.assertEqual(self.emptied("docker exec c rm d/a d/b"), [])

    def test_a_redirect_target_is_not_a_delete_target(self):
        self.assertEqual(self.emptied("rm d/a > d/b"), [])
        self.assertEqual(self.emptied("rm d/a d/b 2>/dev/null"), [str(self.folder)])

    def test_each_simple_command_of_a_step_is_read_on_its_own(self):
        for command in ("echo $(rm d/a d/b)", "x=$(rm d/a d/b)", "echo $(rm d/a) && rm d/b", "rm d/a d/b|&cat",
                        "rm d/a |& rm d/b"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [str(self.folder)])
        self.assertEqual(self.emptied("rm d/a |& wc d/b"), [])

    def test_a_pycache_folder_is_not_a_safe_folder(self):
        self.make_folder("__pycache__", ("a", "b"))
        self.assertEqual(self.emptied("rm __pycache__/a __pycache__/b"), [str(self.root / "__pycache__")])

    def test_a_quoted_glob_is_a_literal_name(self):
        self.assertEqual(self.emptied("rm 'd/*'"), [])

    def test_a_quoted_tilde_is_a_literal_name_and_an_unquoted_one_is_home(self):
        literal = self.make_folder("~", ("a", "b"))
        home = self.make_folder("home", ("a", "b"))
        with unittest.mock.patch.dict(os.environ, {"HOME": str(home)}):
            self.assertEqual(self.emptied("rm '~/a' \"~/b\""), [str(literal)])
            self.assertEqual(self.emptied("rm ~/a ~/b"), [str(home)])

    def test_a_step_the_reader_cannot_parse_does_not_hide_a_later_delete(self):
        for command in ("echo 1 > x; rm d/a d/b", "ls 2 > x; rm d/a d/b", "echo a\\|b; rm d/a d/b"):
            with self.subTest(command=command), unittest.mock.patch("sys.stderr"):
                self.assertEqual(self.emptied(command), [str(self.folder)])

    def test_an_unread_step_with_a_cd_leaves_later_deletes_unplaced(self):
        with unittest.mock.patch("sys.stderr"):
            self.assertEqual(self.emptied("cd d\\|x; rm a b"), [])

    def test_a_folder_name_with_glob_characters_is_literal(self):
        bracketed = self.make_folder("p[1]", ())
        folder = self.make_folder("d", ("a", "b"), parent=bracketed)
        self.assertEqual(self.emptied("rm d/*", directory=bracketed), [str(folder)])

    def test_a_target_with_a_space_is_one_word_in_either_quoting(self):
        folder = self.make_folder("s", ("a b", "c"))
        for command in ("rm s/a\\ b s/c", "rm s/'a b' s/c"):
            with self.subTest(command=command):
                self.assertEqual(self.emptied(command), [str(folder)])
        (folder / "a").write_text("x")
        self.assertEqual(self.emptied("rm s/a\\ b s/c"), [])

    def test_every_safe_folder_name_is_allowed_by_the_recursive_delete_gate(self):
        gate_text = (toolkit_paths.SCRIPTS_DIR / "bash-safety-gate.sh").read_text()
        allow_lines = [line for line in gate_text.splitlines() if "git(\\s+-C" in line and "node_modules" in line]
        self.assertEqual(len(allow_lines), 1)
        for name in directory_emptying_deletes.SAFE_FOLDER_NAMES:
            with self.subTest(name=name):
                self.assertIn(name.replace(".", "\\."), allow_lines[0])
                self.make_folder(name, ("a", "b"))
                self.assertEqual(self.emptied(f"rm {name}/a {name}/b"), [])

    def test_a_glued_quote_target_is_one_word(self):
        folder = self.make_folder("g", ("ab", "b"))
        self.assertEqual(self.emptied("rm g/'a'b g/b"), [str(folder)])

    def test_a_quoted_glob_in_a_fallback_word_is_literal(self):
        folder = self.make_folder("q", ("a*", "x"))
        self.make_folder("r", ("a*",))
        self.assertEqual(self.emptied("rm 'q/a*' q/x"), [str(folder)])
        (folder / "ab").write_text("x")
        self.assertEqual(self.emptied("rm 'q/a*' q/x"), [])

    def test_an_unread_step_is_reported_on_stderr(self):
        with unittest.mock.patch("sys.stderr") as stderr:
            self.emptied("echo 1 > x")
        self.assertTrue(stderr.write.called)

    def test_a_symlink_target_names_the_link_not_what_it_points_at(self):
        outside = self.make_folder("outside", ("x",))
        os.symlink(outside / "x", self.folder / "link")
        (self.folder / "a").unlink()
        (self.folder / "b").unlink()
        self.assertEqual(self.emptied("rm d/link"), [str(self.folder)])
        self.assertTrue((outside / "x").exists())


if __name__ == "__main__":
    unittest.main()
