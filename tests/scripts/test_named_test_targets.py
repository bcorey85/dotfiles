"""Checks for lib/named_test_targets.py."""
import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import named_test_targets

TEST_FILE = "tests/test_app.py"
TARGET = f"{TEST_FILE}::test_limit"
WITH_NAMED_TEST = "def test_limit():\n    assert True\n\n\ndef test_other():\n    assert True\n"
WITHOUT_NAMED_TEST = "def test_other():\n    assert True\n"


class NamedTargetsTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repo = pathlib.Path(directory.name)
        (self.repo / "tests").mkdir()
        (self.repo / TEST_FILE).write_text(WITH_NAMED_TEST)
        (self.repo / "tests" / "test_b.py").write_text(WITH_NAMED_TEST)
        (self.repo / "app.py").write_text("limit = 1\n")

    def test_the_targets_are_the_existing_test_files_and_node_ids_the_test_commands_name(self):
        commands = [f"python3 -m pytest tests/test_b.py {TARGET}", f"python3 -m pytest {TARGET}",
                    "grep -q limit app.py", "pytest tests/test_gone.py::test_z"]

        targets = named_test_targets.named_targets(commands, self.repo)

        self.assertEqual(targets, ["tests/test_b.py", TARGET])

    def test_only_the_words_of_test_running_steps_are_targets(self):
        commands = ["pytest tests/test_b.py && cat tests/test_app.py"]

        targets = named_test_targets.named_targets(commands, self.repo)

        self.assertEqual(targets, ["tests/test_b.py"])

    def test_a_class_node_on_an_untouched_tree_is_named_and_not_missing(self):
        (self.repo / TEST_FILE).write_text("class TestApp:\n    def test_limit(self):\n        pass\n")
        class_target = f"{TEST_FILE}::TestApp"
        method_target = f"{TEST_FILE}::TestApp::test_limit"

        targets = named_test_targets.named_targets([f"pytest {class_target} {method_target}"], self.repo)

        self.assertEqual(targets, [class_target, method_target])
        self.assertEqual(named_test_targets.missing_targets(targets, self.repo), [])

    def test_a_node_the_definition_pattern_cannot_see_is_never_named(self):
        (self.repo / TEST_FILE).write_text(WITHOUT_NAMED_TEST)

        targets = named_test_targets.named_targets([f"pytest {TARGET}"], self.repo)

        self.assertEqual(targets, [])

    def test_a_target_is_missing_when_its_file_or_its_definition_is_gone(self):
        cases = [
            (TARGET, WITH_NAMED_TEST, False, "a python def is present"),
            (TARGET, WITHOUT_NAMED_TEST, True, "the python def is absent"),
            (TARGET, "fn test_limit() {}\n", False, "a rust fn is present"),
            (TARGET, "test('test_limit', () => {})\n", False, "a js test call names it"),
            (TARGET, "def test_limit_more():\n    pass\n", True, "a longer name is another test"),
            (TARGET, "test('test_limit_more', () => {})\n", True, "a js test with a longer name is another test"),
            (f"{TEST_FILE}::TestApp::test_limit[a-1]", WITH_NAMED_TEST, False, "the last node, no parameters"),
            (TEST_FILE, WITHOUT_NAMED_TEST, False, "a whole-file target needs only the file"),
        ]
        for target, text, is_missing, message in cases:
            with self.subTest(message):
                (self.repo / TEST_FILE).write_text(text)

                missing = named_test_targets.missing_targets([target], self.repo)

                self.assertEqual(missing, [target] if is_missing else [])

    def test_a_target_whose_file_is_deleted_is_missing(self):
        (self.repo / TEST_FILE).unlink()

        self.assertEqual(named_test_targets.missing_targets([TARGET, TEST_FILE], self.repo), [TARGET, TEST_FILE])


if __name__ == "__main__":
    unittest.main()
