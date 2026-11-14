"""The prompt file's header: the user-ruled lines and the iteration number."""
import pathlib
import sys
import tempfile
import unittest

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


class HeaderIterTest(unittest.TestCase):
    def test_a_non_ascii_digit_is_a_prompt_file_error_not_a_value_error_crash(self):
        with self.assertRaises(review_loop_prompt_file.PromptFileError):
            review_loop_prompt_file.header_iter({"iter": "²"})

    def test_an_ascii_number_is_read(self):
        self.assertEqual(review_loop_prompt_file.header_iter({"iter": "3"}), 3)


if __name__ == "__main__":
    unittest.main()
