"""Checks for makefile_text.py: reading a Makefile and a make command line as text."""
import os
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or (HERE if (HERE / "makefile_text.py").exists()
                                                                  else toolkit_paths.LIB_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from makefile_text import Makefile, load_makefile, parse_make_arguments


class ParseMakeArgumentsTest(unittest.TestCase):
    def test_options_that_take_a_value_do_not_leak_into_the_targets(self):
        arguments = parse_make_arguments(["-j", "4", "-sk", "-C", "sub", "--file=ci.mk", "-I", "inc", "test", "lint"])

        self.assertEqual("sub", arguments.directory)
        self.assertEqual(["ci.mk"], arguments.files)
        self.assertEqual(["test", "lint"], arguments.targets)
        self.assertFalse(arguments.has_variable_assignment)

    def test_a_load_option_takes_the_next_word_when_it_starts_with_a_digit_or_a_dot(self):
        for words, targets in ((["-l", "test"], ["test"]), (["--max-load", "test"], ["test"]),
                               (["--load-average", "test"], ["test"]), (["-l", "2.5", "test"], ["test"]),
                               (["-l2.5", "test"], ["test"]), (["--max-load", "2.5", "test"], ["test"]),
                               (["--load-average=2.5", "test"], ["test"]), (["-sl", "test"], ["test"]),
                               (["-l", "2x"], []), (["-l", ".t", "test"], ["test"]), (["--jobs", "4"], []),
                               (["--jobs", "test"], ["test"])):
            with self.subTest(words=words):
                self.assertEqual(targets, parse_make_arguments(words).targets)

    def test_attached_option_values_are_read(self):
        arguments = parse_make_arguments(["-Csub", "-fci.mk", "-j4", "test"])

        self.assertEqual("sub", arguments.directory)
        self.assertEqual(["ci.mk"], arguments.files)
        self.assertEqual(["test"], arguments.targets)

    def test_a_directory_option_relative_to_an_earlier_one_adds_to_it(self):
        arguments = parse_make_arguments(["-C", "a", "--directory", "b"])

        self.assertEqual("a/b", arguments.directory)

    def test_a_name_value_word_is_a_variable_assignment_not_a_target(self):
        arguments = parse_make_arguments(["test", "FILE=x", "CC:=gcc"])

        self.assertTrue(arguments.has_variable_assignment)
        self.assertEqual(["test"], arguments.targets)

    def test_words_after_a_double_dash_are_targets(self):
        self.assertEqual(["-odd"], parse_make_arguments(["--", "-odd"]).targets)

    def test_options_that_run_no_recipe_are_read_alone_and_in_a_cluster(self):
        for option in ("-n", "--dry-run", "--just-print", "--recon", "-q", "--question", "--help", "-h", "-t",
                       "--touch", "-nk", "-sn", "-knj4"):
            with self.subTest(option=option):
                self.assertTrue(parse_make_arguments([option, "test"]).runs_no_recipe)

    def test_other_options_and_option_values_run_a_recipe(self):
        for words in (["-s", "test"], ["-j", "4", "test"], ["-C", "n", "test"], ["-f", "q", "test"], ["-Cn", "test"],
                      ["--directory=n", "test"], ["-sk", "test"], ["--", "-n"], ["-p", "test"],
                      ["--print-data-base", "test"], ["-Onone", "test"], ["-sOnone", "test"]):
            with self.subTest(words=words):
                self.assertFalse(parse_make_arguments(words).runs_no_recipe)


class MakefileTest(unittest.TestCase):
    def test_default_goal_is_the_first_target_not_starting_with_a_dot(self):
        makefile = Makefile(".PHONY: lint\n.SUFFIXES:\nlint test: src\n\truff check\n")

        self.assertEqual("lint", makefile.default_goal)

    def test_default_goal_variable_overrides_the_first_target(self):
        makefile = Makefile("a:\n\tx\n.DEFAULT_GOAL = b\nb:\n\ty\n")

        self.assertEqual("b", makefile.default_goal)

    def test_recipe_commands_lose_their_prefix_and_expand_variables(self):
        makefile = Makefile("RUN = uv run\nOUT := $(RUN) out\n"
                            "t: dep.txt\n\t@-+$(RUN) pytest $@ $< $${HOME}\n\t${OUT}\n")

        self.assertEqual(["uv run pytest t dep.txt ${HOME}", "uv run out"], makefile.recipe_commands("t"))

    def test_variable_assignment_operators(self):
        makefile = Makefile("A = 1\nA ?= 2\nB ?= 3\nC := $(A)\nA = 9\nC += $(B)\nt:\n\t$(A) $(B) $(C)\n")

        self.assertEqual(["9 3 1 3"], makefile.recipe_commands("t"))

    def test_a_self_referencing_variable_ends(self):
        makefile = Makefile("A = $(A) x\nt:\n\t$(A)\n")

        commands = makefile.recipe_commands("t")

        self.assertEqual(1, len(commands))
        self.assertTrue(commands[0].endswith("x"))

    def test_a_function_call_is_left_as_written(self):
        makefile = Makefile("t:\n\t$(shell echo pytest)\n")

        self.assertEqual(["$(shell echo pytest)"], makefile.recipe_commands("t"))

    def test_the_recipe_lines_of_every_conditional_branch_belong_to_the_target(self):
        makefile = Makefile("test:\nifeq ($(CI),1)\n\tpytest --junit\nelse ifdef LOCAL\n\tpytest -x\nelse\n\tpytest\n"
                            "endif\n")

        self.assertEqual(["pytest --junit", "pytest -x", "pytest"], makefile.recipe_commands("test"))

    def test_an_inline_recipe_and_a_continued_line_are_read(self):
        makefile = Makefile("a: ; echo one\nb:\n\techo \\\n\t  two\n")

        self.assertEqual(["echo one"], makefile.recipe_commands("a"))
        self.assertEqual(["echo two"], makefile.recipe_commands("b"))

    def test_order_only_prerequisites_and_comments_are_dropped(self):
        makefile = Makefile("# note\nt: a b | dir # trailing\n\techo\n")

        self.assertEqual(["a", "b"], makefile.prerequisites["t"])
        self.assertEqual(["dir"], makefile.order_only_prerequisites["t"])
        self.assertEqual(["a", "b", "dir"], makefile.all_prerequisites("t"))

    def test_pattern_rules_and_target_specific_variables_make_no_target(self):
        makefile = Makefile("%.o: %.c\n\tcc\nt: FLAG=1\n\techo\n")

        self.assertFalse(makefile.has_rule("%.o"))
        self.assertFalse(makefile.has_rule("t"))


class LoadMakefileTest(unittest.TestCase):
    def setUp(self):
        temp_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temp_directory.cleanup)
        self.folder = pathlib.Path(temp_directory.name)

    def test_the_first_default_file_name_found_is_read(self):
        (self.folder / "Makefile").write_text("a:\n")
        (self.folder / "GNUmakefile").write_text("b:\n")

        makefile = load_makefile(self.folder)

        self.assertTrue(makefile.has_rule("b"))
        self.assertFalse(makefile.has_rule("a"))

    def test_no_file_or_an_unreadable_file_is_none(self):
        self.assertIsNone(load_makefile(self.folder))
        self.assertIsNone(load_makefile(self.folder, ["missing.mk"]))


if __name__ == "__main__":
    unittest.main()
