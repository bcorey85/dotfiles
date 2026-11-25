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


class HeaderPostCapPassesTest(unittest.TestCase):
    def test_a_header_with_no_line_has_no_passes(self):
        self.assertEqual(review_loop_prompt_file.header_post_cap_passes({"lane": "code"}), [])

    def test_known_kinds_are_read_in_order(self):
        header = {"post_cap_passes": "final read, class closure"}
        self.assertEqual(review_loop_prompt_file.header_post_cap_passes(header), ["final read", "class closure"])

    def test_a_kind_outside_the_known_kinds_stops_the_run(self):
        header = {"post_cap_passes": "final read, tea break"}
        with self.assertRaises(review_loop_prompt_file.PromptFileError) as caught:
            review_loop_prompt_file.header_post_cap_passes(header)
        self.assertIn("tea break", str(caught.exception))

    def test_an_empty_kind_stops_the_run(self):
        for value in ("final read, , class closure", "final read, ", ", "):
            with self.subTest(value=value), self.assertRaises(review_loop_prompt_file.PromptFileError):
                review_loop_prompt_file.header_post_cap_passes({"post_cap_passes": value})


class CoderModelHeaderTest(unittest.TestCase):
    def test_the_coder_model_line_is_read_under_its_key(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        prompt_file = pathlib.Path(directory.name) / "prompt.txt"
        prompt_file.write_text("lane: code\ncoder-model: haiku\n\nhandoff\n")

        header, _handoff = review_loop_prompt_file.read_prompt(prompt_file)

        self.assertEqual(header[review_loop_prompt_file.CODER_MODEL_KEY], "haiku")


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


PLAN_PATH = "docs/plans/p/spec.md"
PLAN_TEXT = "\n".join(["# Plan", "", "## Phase 1: First", "", "one", "", "## Phase 2: Second", "", "two", ""])


class ReviewerBriefTest(unittest.TestCase):
    def repo_with_plan(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        repo = pathlib.Path(directory.name)
        (repo / PLAN_PATH).parent.mkdir(parents=True)
        (repo / PLAN_PATH).write_text(PLAN_TEXT)
        return repo

    def test_the_diff_command_and_the_untracked_files_leave_out_the_plan_folder(self):
        header = {"plan": PLAN_PATH, "phase": "1", "base": "abc1234"}

        brief = review_loop_prompt_file.reviewer_brief(header, "the handoff", self.repo_with_plan())

        self.assertIn("`git diff abc1234 -- . ':(exclude)docs/plans/p/'`", brief)
        self.assertIn("untracked files outside docs/plans/p/", brief)
        self.assertIn("The files under docs/plans/p/ are plan documents, not the change", brief)
        self.assertTrue(brief.endswith("Handoff:\nthe handoff"))

    def test_the_brief_names_the_plan_lines_of_the_phase(self):
        repo = self.repo_with_plan()

        brief = review_loop_prompt_file.reviewer_brief({"plan": PLAN_PATH, "phase": "2"}, "the handoff", repo)

        self.assertIn("Phase 2 is the `## Phase 2: Second` section of the plan, lines 7-9 at the run's start. "
                      "Read only that section of it.", brief)
        self.assertIn("open none of them but the plan section named here, `acceptance-criteria.md` and "
                      "`00-ticket.md`.", brief)

    def test_a_phase_with_no_section_or_a_plan_not_on_disk_gets_no_line_range(self):
        repo = self.repo_with_plan()
        for header in ({"plan": PLAN_PATH, "phase": "9"}, {"plan": "docs/plans/gone/spec.md", "phase": "1"},
                       {"plan": PLAN_PATH}):
            with self.subTest(header=header):
                brief = review_loop_prompt_file.reviewer_brief(header, "the handoff", repo)
                self.assertNotIn("section of the plan", brief)

    def test_a_brief_with_no_line_range_still_lets_the_reviewer_open_the_plan(self):
        repo = self.repo_with_plan()

        brief = review_loop_prompt_file.reviewer_brief({"plan": PLAN_PATH, "phase": "9"}, "the handoff", repo)

        self.assertIn(f"open none of them but `{PLAN_PATH}`, `acceptance-criteria.md` and `00-ticket.md`.", brief)
        self.assertNotIn("plan section named here", brief)

    def test_a_review_with_no_plan_keeps_the_whole_diff(self):
        brief = review_loop_prompt_file.reviewer_brief({"base": "abc1234"}, "the handoff", "/nowhere")

        self.assertEqual(brief, "Review every change since abc1234, commits included: `git diff abc1234` plus "
                                "untracked files.\nHandoff:\nthe handoff")


if __name__ == "__main__":
    unittest.main()
