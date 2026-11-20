"""The prompt file's header: the user-ruled lines and the iteration number."""
import json
import pathlib
import sys
import tempfile
import unittest
from typing import ClassVar

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_prompt_file


class UserRuledTimeTest(unittest.TestCase):
    def write_prompt(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        prompt_file = pathlib.Path(directory.name) / "prompt.txt"
        prompt_file.write_text(text)
        return prompt_file

    def test_a_user_ruled_line_with_no_user_ruled_at_line_stops_naming_file_and_line(self):
        prompt_file = self.write_prompt("lane: code\nuser-ruled: 1, 2\n\nhandoff\n")
        with self.assertRaises(review_loop_prompt_file.PromptFileError) as caught:
            review_loop_prompt_file.read_prompt(prompt_file)
        message = str(caught.exception)
        self.assertIn(f"{prompt_file}:2", message)
        self.assertIn("user-ruled-at: <time>", message)

    def test_a_user_ruled_line_with_its_time_is_read(self):
        prompt_file = self.write_prompt("lane: code\nuser-ruled: 1\nuser-ruled-at: 2026-01-01 00:00\n\nhandoff\n")
        header, _handoff = review_loop_prompt_file.read_prompt(prompt_file)
        self.assertEqual(header["user-ruled-at"], "2026-01-01 00:00")

    def test_a_prompt_with_no_ruling_needs_no_time(self):
        prompt_file = self.write_prompt("lane: code\n\nhandoff\n")
        header, handoff = review_loop_prompt_file.read_prompt(prompt_file)
        self.assertEqual(header, {"lane": "code"})
        self.assertEqual(handoff, "handoff")


class RuledOutHeaderTest(unittest.TestCase):
    def test_the_ruled_out_files_line_parses_to_its_paths(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        prompt_file = pathlib.Path(directory.name) / "prompt.txt"
        prompt_file.write_text("lane: code\nruled-out files: a.py, sub/b.py\n\nhandoff\n")

        header, _handoff = review_loop_prompt_file.read_prompt(prompt_file)

        self.assertEqual(review_loop_prompt_file.header_list(header, review_loop_prompt_file.RULED_OUT_FILES_KEY),
                         ["a.py", "sub/b.py"])

    def test_a_header_with_no_ruled_out_line_has_no_ruled_out_files(self):
        self.assertEqual(review_loop_prompt_file.header_list({"lane": "code"}, "ruled-out files"), [])


class HeaderHeldByTest(unittest.TestCase):
    ROW: ClassVar[dict] = {"path": "a.py", "session": "lane-b", "claim": "dirty at the run start"}

    def test_a_header_with_no_held_by_line_has_no_holders(self):
        self.assertEqual(review_loop_prompt_file.header_held_by({"lane": "code"}), {})

    def test_the_rows_are_read_by_path(self):
        header = {"held-by": json.dumps([self.ROW])}
        self.assertEqual(review_loop_prompt_file.header_held_by(header), {"a.py": self.ROW})

    def test_a_value_that_is_not_the_expected_json_stops_the_run(self):
        bad_values = ["not json", '{"path": "a.py"}', json.dumps([{"path": "a.py", "session": "s"}]),
                      json.dumps([{**self.ROW, "claim": " "}]), json.dumps(["a.py"])]
        for value in bad_values:
            with self.subTest(value), self.assertRaises(review_loop_prompt_file.PromptFileError):
                review_loop_prompt_file.header_held_by({"held-by": value})

    def test_the_line_survives_the_header_read_with_its_colons(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        prompt_file = pathlib.Path(directory.name) / "prompt.txt"
        prompt_file.write_text(f"lane: code\nheld-by: {json.dumps([self.ROW])}\n\nhandoff\n")
        header, _handoff = review_loop_prompt_file.read_prompt(prompt_file)
        self.assertEqual(review_loop_prompt_file.header_held_by(header), {"a.py": self.ROW})


class HeaderAdoptedTest(unittest.TestCase):
    ROW: ClassVar[dict] = {"number": 1, "text": "impact", "finding_text": None, "owner": "the user",
                           "ruled_at": "2026-11-19 10:00"}

    def test_a_header_with_no_adopted_line_has_no_rows(self):
        self.assertEqual(review_loop_prompt_file.header_adopted({"lane": "code"}, ["f"]), {})

    def test_a_row_is_read_by_the_finding_it_names(self):
        header = {"adopted": json.dumps([self.ROW])}
        self.assertEqual(review_loop_prompt_file.header_adopted(header, ["f"]), {"f": self.ROW})

    def test_a_value_that_is_not_the_expected_json_stops_the_run(self):
        missing_owner = {key: value for key, value in self.ROW.items() if key != "owner"}
        bad_values = ["not json", json.dumps(self.ROW), json.dumps([missing_owner]),
                      json.dumps([{**self.ROW, "number": 0}]), json.dumps([{**self.ROW, "number": 2}])]
        for value in bad_values:
            with self.subTest(value), self.assertRaises(review_loop_prompt_file.PromptFileError):
                review_loop_prompt_file.header_adopted({"adopted": value}, ["f"])


class HeaderIterTest(unittest.TestCase):
    def test_a_non_ascii_digit_is_a_prompt_file_error_not_a_value_error_crash(self):
        with self.assertRaises(review_loop_prompt_file.PromptFileError):
            review_loop_prompt_file.header_iter({"iter": "²"})

    def test_an_ascii_number_is_read(self):
        self.assertEqual(review_loop_prompt_file.header_iter({"iter": "3"}), 3)


if __name__ == "__main__":
    unittest.main()
