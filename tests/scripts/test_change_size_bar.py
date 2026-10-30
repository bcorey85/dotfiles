"""The /code follow-up check and the review loop read one working-tree scan and one small-change bar: the same change
gets the same small-or-large answer and the same added-line count from both."""
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path[:0] = [str(toolkit_paths.SCRIPTS_DIR), *(str(folder) for folder in (
    toolkit_paths.CODE_DIR, toolkit_paths.REVIEW_DIR, toolkit_paths.LIB_DIR, toolkit_paths.TELEMETRY_DIR))]
import code_step_boundary  # noqa: E402
import code_step_review  # noqa: E402

REVIEW_LOOP_SCRIPT = pathlib.Path(os.environ.get("REVIEW_LOOP_SCRIPT")
                                  or toolkit_paths.REVIEW_DIR / "review_loop_script.py")


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def load_review_loop():
    loader = importlib.util.spec_from_file_location("review_loop_script_for_size_bar", REVIEW_LOOP_SCRIPT)
    module = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(module)
    return module


class ChangeSizeBarTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "T")
        (self.repo / "NOTES.md").write_text("notes\n")
        (self.repo / "app.py").write_text("app = 1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "files")
        self.review_loop = load_review_loop()

    def review_loop_finds_it_small(self):
        dispatches = self.review_loop.first_round_plan(self.review_loop.scope(self.repo))
        return "smell-reviewer" not in [agent for agent, _ in dispatches]

    def test_a_follow_up_that_adds_forty_lines_of_docs_is_small_for_both_sides(self):
        before = code_step_review.change_snapshot(self.repo)
        (self.repo / "NOTES.md").write_text("".join(f"note {number}\n" for number in range(41)))

        after = code_step_review.change_snapshot(self.repo)

        self.assertTrue(self.review_loop_finds_it_small())
        self.assertTrue(code_step_review.follow_up_is_small(before, after))

    def test_a_follow_up_that_adds_forty_lines_of_source_is_large_for_both_sides(self):
        before = code_step_review.change_snapshot(self.repo)
        # Forty new lines replace the one committed line: git counts +40 -1.
        (self.repo / "app.py").write_text("".join(f"value_{number} = {number}\n" for number in range(40)))

        after = code_step_review.change_snapshot(self.repo)

        self.assertEqual(40, after["added"]["app.py"])
        self.assertFalse(self.review_loop_finds_it_small())
        self.assertFalse(code_step_review.follow_up_is_small(before, after))

    def test_a_follow_up_that_adds_thirty_nine_lines_of_source_is_small_for_both_sides(self):
        before = code_step_review.change_snapshot(self.repo)
        (self.repo / "app.py").write_text("".join(f"value_{number} = {number}\n" for number in range(39)))

        after = code_step_review.change_snapshot(self.repo)

        self.assertTrue(self.review_loop_finds_it_small())
        self.assertTrue(code_step_review.follow_up_is_small(before, after))

    def test_a_staged_new_source_file_is_large_for_both_sides_however_short(self):
        before = code_step_review.change_snapshot(self.repo)
        (self.repo / "helper.py").write_text("x = 1\n")
        git(self.repo, "add", "helper.py")

        after = code_step_review.change_snapshot(self.repo)

        self.assertFalse(self.review_loop_finds_it_small())
        self.assertFalse(code_step_review.follow_up_is_small(before, after))

    def test_an_intent_to_add_source_file_is_new_and_large_for_both_sides(self):
        before = code_step_review.change_snapshot(self.repo)
        (self.repo / "helper.py").write_text("x = 1\n")
        git(self.repo, "add", "-N", "helper.py")

        after = code_step_review.change_snapshot(self.repo)

        self.assertEqual(["helper.py"], after["newFiles"])
        self.assertFalse(self.review_loop_finds_it_small())
        self.assertFalse(code_step_review.follow_up_is_small(before, after))

    def test_a_new_lockfile_is_small_for_both_sides_because_it_is_not_counted_source(self):
        before = code_step_review.change_snapshot(self.repo)
        (self.repo / "package-lock.json").write_text("{}\n")

        after = code_step_review.change_snapshot(self.repo)

        self.assertTrue(self.review_loop_finds_it_small())
        self.assertTrue(code_step_review.follow_up_is_small(before, after))

    def test_a_pure_rename_of_a_fifty_line_source_file_adds_no_lines_and_is_small_for_both_sides(self):
        (self.repo / "long.py").write_text("".join(f"value_{number} = {number}\n" for number in range(50)))
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "long file")
        before = code_step_review.change_snapshot(self.repo)
        git(self.repo, "mv", "long.py", "renamed.py")

        after = code_step_review.change_snapshot(self.repo)

        self.assertEqual(0, after["added"]["renamed.py"])
        self.assertTrue(self.review_loop_finds_it_small())
        self.assertTrue(code_step_review.follow_up_is_small(before, after))

    def test_diff_stat_rows_print_zero_counts_for_a_changed_binary_file_and_a_clean_file(self):
        (self.repo / "bin.dat").write_bytes(b"\0\1\2")
        (self.repo / "clean.py").write_text("clean = 1\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "more files")
        (self.repo / "bin.dat").write_bytes(b"\0\3\4\5")

        rows = code_step_boundary.diff_stat_rows(self.repo, ["bin.dat", "clean.py"])

        self.assertEqual(["bin.dat | +0 -0", "clean.py | +0 -0"], rows)

    def test_an_untracked_file_without_a_final_newline_counts_every_line_on_both_sides(self):
        (self.repo / "tail.txt").write_text("one\ntwo\nthree")

        snapshot = code_step_review.change_snapshot(self.repo)

        self.assertEqual(3, self.review_loop.scope(self.repo)["tail.txt"][0])
        self.assertEqual(3, snapshot["added"]["tail.txt"])


if __name__ == "__main__":
    unittest.main()
