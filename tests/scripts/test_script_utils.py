import importlib.util
import os
import pathlib
import tempfile
import threading
import time
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(os.environ.get("SCRIPT_UTILS_SCRIPT")
                      or REPO_ROOT / "claude" / ".claude" / "scripts" / "script_utils.py")
moduleSpec = importlib.util.spec_from_file_location("script_utils", SCRIPT)
script_utils = importlib.util.module_from_spec(moduleSpec)
moduleSpec.loader.exec_module(script_utils)


class FencedLineIndexesTest(unittest.TestCase):
    def test_lines_between_backtick_fences_and_the_fences_themselves_are_fenced(self):
        lines = ["# a", "```bash", "# not a heading", "```", "# b"]
        self.assertEqual({1, 2, 3}, script_utils.fenced_line_indexes(lines))

    def test_tilde_fence_is_closed_only_by_tildes(self):
        lines = ["~~~", "```", "# x", "~~~", "# y"]
        self.assertEqual({0, 1, 2, 3}, script_utils.fenced_line_indexes(lines))

    def test_a_longer_fence_is_not_closed_by_a_shorter_one(self):
        lines = ["````md", "```", "# x", "```", "````", "# y"]
        self.assertEqual({0, 1, 2, 3, 4}, script_utils.fenced_line_indexes(lines))

    def test_an_unclosed_fence_runs_to_the_end(self):
        self.assertEqual({1, 2}, script_utils.fenced_line_indexes(["# a", "```", "# b"]))

    def test_an_indented_fence_inside_a_list_item_counts(self):
        lines = ["- step", "    ```sh", "    # comment", "    ```", "# h"]
        self.assertEqual({1, 2, 3}, script_utils.fenced_line_indexes(lines))

    def test_text_with_no_fence_has_no_fenced_lines(self):
        self.assertEqual(set(), script_utils.fenced_line_indexes(["# a", "b `code` c"]))


class VisibleTextTest(unittest.TestCase):
    def test_a_line_without_comments_comes_back_whole(self):
        self.assertEqual(("plain text", False), script_utils.visible_text("plain text", False))

    def test_an_inline_comment_is_removed(self):
        self.assertEqual(("a  b", False), script_utils.visible_text("a <!-- x --> b", False))

    def test_an_unclosed_comment_hides_the_rest_and_stays_open(self):
        self.assertEqual(("a ", True), script_utils.visible_text("a <!-- x", False))

    def test_an_open_comment_closes_on_a_later_line(self):
        self.assertEqual((" tail", False), script_utils.visible_text("end --> tail", True))
        self.assertEqual(("", True), script_utils.visible_text("still inside", True))

    def test_a_comment_opener_inside_inline_code_opens_nothing(self):
        self.assertEqual(("write `<!--` to open", False), script_utils.visible_text("write `<!--` to open", False))

    def test_a_real_comment_after_an_inline_code_span_still_opens(self):
        self.assertEqual(("`a` ", True), script_utils.visible_text("`a` <!-- x", False))


class LinesAddedTest(unittest.TestCase):
    def test_a_new_line_is_added(self):
        self.assertEqual(["Also b."], script_utils.lines_added(["a", "c"], ["a", "Also b.", "c"]))

    def test_a_checkbox_tick_is_not_an_added_line(self):
        self.assertEqual([], script_utils.lines_added(["- [ ] check"], ["- [x] check"]))
        self.assertEqual([], script_utils.lines_added(["- [x] check"], ["- [X] check"]))

    def test_added_blank_lines_are_not_added_lines(self):
        self.assertEqual([], script_utils.lines_added(["a", "b"], ["a", "", "", "b"]))

    def test_whitespace_only_changes_are_not_added_lines(self):
        self.assertEqual([], script_utils.lines_added(["Do a."], ["Do a. "]))
        self.assertEqual([], script_utils.lines_added(["- x"], ["  - x"]))
        self.assertEqual([], script_utils.lines_added(["a  b"], ["a b"]))

    def test_a_reworded_line_is_added_in_its_new_form(self):
        self.assertEqual(["Do c."], script_utils.lines_added(["Do a."], ["Do c."]))

    def test_deleted_lines_add_nothing(self):
        self.assertEqual([], script_utils.lines_added(["a", "b"], ["a"]))


class WaitForTest(unittest.TestCase):
    def test_returns_the_value_the_check_finds_at_once(self):
        self.assertEqual("row", script_utils.wait_for(lambda: "row", 5, 0.01))

    def test_polls_until_the_check_finds_something(self):
        found = []
        threading.Timer(0.3, lambda: found.append("late")).start()
        result = script_utils.wait_for(lambda: found[0] if found else None, 5, 0.05)
        self.assertEqual("late", result)

    def test_gives_up_at_the_limit_with_none(self):
        started = time.monotonic()
        self.assertIsNone(script_utils.wait_for(lambda: None, 0.3, 0.05))
        self.assertLess(time.monotonic() - started, 2)

    def test_a_zero_limit_checks_once(self):
        calls = []
        self.assertIsNone(script_utils.wait_for(lambda: calls.append(1), 0, 0.05))
        self.assertEqual(1, len(calls))


class JoinedDistinctTest(unittest.TestCase):
    def test_equal_values_appear_once_and_empty_values_are_dropped(self):
        self.assertEqual("Q? (a.ts:3)", script_utils.joined_distinct(["Q? (a.ts:3)", "", "Q? (a.ts:3)"]))

    def test_different_values_are_joined_in_order(self):
        self.assertEqual("a - b", script_utils.joined_distinct(["a", "b"]))
        self.assertEqual("a | b", script_utils.joined_distinct(["a", "b"], " | "))


class LastChangeNsTest(unittest.TestCase):
    def test_a_renamed_file_with_an_old_mtime_reports_its_newer_ctime(self):
        tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(tempDir.cleanup)
        source = pathlib.Path(tempDir.name) / "source.md"
        source.write_text("x\n")
        os.utime(source, (50, 50))
        moved = pathlib.Path(tempDir.name) / "moved.md"
        source.rename(moved)

        self.assertEqual(50 * 10**9, moved.stat().st_mtime_ns)
        self.assertGreater(script_utils.last_change_ns(moved), 50 * 10**9)

    def test_a_file_whose_mtime_was_set_into_the_future_reports_the_mtime(self):
        tempDir = tempfile.TemporaryDirectory()
        self.addCleanup(tempDir.cleanup)
        path = pathlib.Path(tempDir.name) / "future.md"
        path.write_text("x\n")
        future = time.time() + 1000
        os.utime(path, (future, future))

        self.assertEqual(path.stat().st_mtime_ns, script_utils.last_change_ns(path))


if __name__ == "__main__":
    unittest.main()
