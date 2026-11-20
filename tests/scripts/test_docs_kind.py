"""Checks for the `docs_kind` label on a docs-class review finding row.

lib/diff_ranges.py `added_ranges` and review/review_loop_docs_kind.py compute it, review_loop_script.py puts it on
the rows of each round, and log-review-finding validates it and keeps it when the ledger refuses the field.

Script locations: REVIEW_LOOP_SCRIPT and LOG_REVIEW_FINDING_SCRIPT, as in the test files this one borrows from.
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import fake_ledger
import test_log_review_finding as logger_tests
import test_review_loop_script as loop_tests
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import diff_ranges
import review_loop_docs_kind
from finding_record import parse_finding

STALE = review_loop_docs_kind.STALE
NEW = review_loop_docs_kind.NEW
MIXED_DIFF = """\
--- a/src/mod.py
+++ b/src/mod.py
@@ -3,2 +3,0 @@
-gone one
-gone two
@@ -10,1 +8,2 @@
-old
+new one
+new two
@@ -20,0 +19,1 @@
+added
--- a/src/trimmed.py
+++ b/src/trimmed.py
@@ -1,1 +0,0 @@
-gone
"""
GIT_ENV = logger_tests.GIT_ENV
FILE_BEFORE = "one\ntwo\nthree\nfour\n"
FILE_EDITED = "one\ntwo changed\nthree\nfour\nfive\n"


class AddedRangesTest(unittest.TestCase):
    def test_only_the_runs_that_add_a_line_are_ranges(self):
        added = diff_ranges.added_ranges(MIXED_DIFF)

        self.assertEqual(added["src/mod.py"], [(8, 9), (19, 19)])

    def test_a_file_the_diff_only_removes_lines_from_keeps_its_key_with_no_range(self):
        added = diff_ranges.added_ranges(MIXED_DIFF)

        self.assertEqual(added["src/trimmed.py"], [])

    def test_changed_ranges_still_names_the_line_of_a_removal(self):
        changed = diff_ranges.changed_ranges(MIXED_DIFF)

        self.assertEqual(changed["src/mod.py"], [(4, 4), (8, 9), (19, 19)])


class ScratchRepoCase(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name).resolve() / "planted-repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")

    def git(self, *args):
        git_env = {**os.environ, **GIT_ENV}
        done = subprocess.run(["git", *args], cwd=self.repo, env=git_env, check=True, capture_output=True, text=True)
        return done.stdout.strip()

    def commit(self, files, message="files"):
        for name, text in files.items():
            file_path = self.repo / name
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(text)
        self.git("add", *files)
        self.git("commit", "-q", "-m", message)


class ChangeAddedRangesTest(ScratchRepoCase):
    def test_an_edit_of_a_tracked_file_gives_its_added_lines(self):
        self.commit({"kept.py": FILE_BEFORE})
        (self.repo / "kept.py").write_text(FILE_EDITED)

        added = review_loop_docs_kind.change_added_ranges(self.repo)

        self.assertEqual(added, {"kept.py": [(2, 2), (5, 5)]})

    def test_an_untracked_file_and_a_staged_new_file_are_added_whole(self):
        self.commit({"kept.py": FILE_BEFORE})
        (self.repo / "untracked.py").write_text("a\nb\n")
        (self.repo / "staged.py").write_text("a\nb\nc\n")
        self.git("add", "staged.py")

        added = review_loop_docs_kind.change_added_ranges(self.repo)

        self.assertTrue(diff_ranges.in_ranges(added["untracked.py"], 2, slack=0))
        self.assertEqual(added["staged.py"], [(1, 3)])

    def test_a_renamed_file_adds_only_the_lines_edited_after_the_move(self):
        self.commit({"old_name.py": FILE_BEFORE * 5})
        self.git("mv", "old_name.py", "new_name.py")
        (self.repo / "new_name.py").write_text(FILE_BEFORE * 5 + "tail\n")
        self.git("add", "new_name.py")

        added = review_loop_docs_kind.change_added_ranges(self.repo)

        self.assertEqual(added, {"new_name.py": [(21, 21)]})

    def test_a_base_commit_adds_the_branch_commits_to_the_working_tree_edits(self):
        self.commit({"kept.py": FILE_BEFORE})
        base = self.git("rev-parse", "HEAD")
        self.commit({"kept.py": FILE_BEFORE + "five\n"}, "branch work")
        (self.repo / "kept.py").write_text(FILE_BEFORE + "five\nsix\n")

        added = review_loop_docs_kind.change_added_ranges(self.repo, base)

        self.assertEqual(added, {"kept.py": [(5, 6)]})

    def test_a_repo_with_no_commit_gives_none(self):
        (self.repo / "kept.py").write_text(FILE_BEFORE)

        self.assertIsNone(review_loop_docs_kind.change_added_ranges(self.repo))


class DocsKindTest(ScratchRepoCase):
    def setUp(self):
        super().setUp()
        self.commit({"kept.py": FILE_BEFORE})
        (self.repo / "kept.py").write_text(FILE_EDITED)
        self.added = review_loop_docs_kind.change_added_ranges(self.repo)

    def kind(self, finding_text):
        return review_loop_docs_kind.docs_kind(self.repo, self.added, parse_finding(finding_text))

    def test_a_docs_finding_on_an_added_line_is_new_and_on_any_other_line_is_stale(self):
        self.assertEqual(self.kind("`kept.py:2` [docs] the comment is wrong"), NEW)
        self.assertEqual(self.kind("`kept.py:5` [docs] the comment is wrong"), NEW)
        self.assertEqual(self.kind("`kept.py:3` [docs] the comment is wrong"), STALE)

    def test_a_line_next_to_an_added_line_is_stale(self):
        self.assertEqual(self.kind("`kept.py:1` [docs] the comment is wrong"), STALE)

    def test_a_docs_finding_in_a_file_the_diff_leaves_alone_is_stale(self):
        self.commit({"other.md": "a\nb\n"})

        self.assertEqual(self.kind("`other.md:2` [docs] the guide names the old flag"), STALE)

    def test_a_finding_of_another_class_gets_no_label(self):
        self.assertEqual(self.kind("`kept.py:2` [bug] the value is wrong"), "")
        self.assertEqual(self.kind("`kept.py:2` the value is wrong"), "")

    def test_a_finding_the_script_cannot_place_gets_no_label(self):
        self.assertEqual(self.kind("[docs] the plan promise has no note"), "")
        self.assertEqual(self.kind("`kept.py:6` [docs] the line is past the end"), "")
        self.assertEqual(self.kind("`gone.py:1` [docs] the file is not in the tree"), "")
        self.assertEqual(self.kind("`src/kept.py:2` [docs] the path is not the tree's"), "")

    def test_an_absolute_path_inside_the_repo_reads_the_same_ranges(self):
        cited = self.repo / "kept.py"

        self.assertEqual(self.kind(f"`{cited}:2-3` [docs] the comment is wrong"), NEW)
        self.assertEqual(self.kind(f"`{cited}:3-4` [docs] the comment is wrong"), STALE)

    def test_an_absolute_path_outside_the_repo_gets_no_label(self):
        outside = self.repo.parent / "outside.py"
        outside.write_text("a\nb\n")
        self.addCleanup(outside.unlink)

        self.assertEqual(self.kind(f"`{outside}:1` [docs] the comment is wrong"), "")

    def test_a_round_with_no_diff_gets_no_label(self):
        finding = parse_finding("`kept.py:2` [docs] the comment is wrong")

        self.assertEqual(review_loop_docs_kind.docs_kind(self.repo, None, finding), "")


def review_of(*fixes):
    lines = "".join(f"- {fix}\n" for fix in fixes)
    return f"## Fix\n{lines}\n## Ask\nNone\n\n## Nit\nNone\n"


# The harness tree edits app.py line 5 and leaves notes.py alone; APP_FIXED rewrites app.py lines 2 and 5.
ROUND_ONE_REVIEW = review_of("`app.py:5` [docs] the edited line has a wrong comment",
                             "`app.py:1` [docs] the old line names a gone flag",
                             "`app.py:3` [bug] the limit is wrong")
ROUND_TWO_REVIEW = review_of("`app.py:2` [docs] the fix wrote a wrong comment",
                             "`notes.py:1` [docs] the fix made the note false")
# A run whose round budget ends on a coder pass gets one more reviewer read of that pass.
FINAL_READ = {"result": loop_tests.CLEAN_REVIEW}
FIX_CODER = {"result": "Fixed.", "edits": {"app.py": loop_tests.APP_FIXED}}
NOTES_CODER = {"result": "Fixed.", "edits": {"notes.py": "value = {'a': 1}\n"}}


class LoopRowsTest(loop_tests.ReviewLoopHarness, unittest.TestCase):
    def kinds_by_spot(self, scenario, header_extra=""):
        completed = self.run_script(scenario, header_extra=header_extra)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return {(row["iter"], row["path_key"], row["line"]): row.get("docs_kind", "") for row in self.finding_rows()}

    def test_round_one_labels_each_docs_row_against_the_change_under_review(self):
        reviews = [{"result": ROUND_ONE_REVIEW}, {"result": loop_tests.CLEAN_REVIEW}]

        kinds = self.kinds_by_spot({"code-reviewer": reviews, "coder": [FIX_CODER],
                                    "closure": [{"result": loop_tests.CLOSED}]})

        self.assertEqual(kinds, {("1", "app.py", "5"): NEW, ("1", "app.py", "1"): STALE, ("1", "app.py", "3"): ""})

    def test_round_two_labels_each_docs_row_against_the_fix_diff(self):
        reviews = [{"result": loop_tests.FIX_REVIEW}, {"result": ROUND_TWO_REVIEW}, FINAL_READ]
        kinds = self.kinds_by_spot({"code-reviewer": reviews, "coder": [FIX_CODER, NOTES_CODER],
                                    "closure": [{"result": loop_tests.CLOSED}]})

        self.assertEqual(kinds[("2", "app.py", "2")], NEW)
        self.assertEqual(kinds[("2", "notes.py", "1")], STALE)

    def test_a_resumed_loop_whose_round_has_no_diff_logs_its_docs_rows_without_the_label(self):
        kinds = self.kinds_by_spot({"code-reviewer": [{"result": ROUND_TWO_REVIEW}, FINAL_READ], "coder": [NOTES_CODER],
                                    "closure": [{"result": loop_tests.CLOSED}]}, header_extra="iter: 1\n")

        self.assertEqual(set(kinds.values()), {""})
        self.assertEqual(len(kinds), 2)

    def test_a_docs_finding_filed_again_under_another_class_is_logged_without_the_label(self):
        first = review_of("`app.py:1` [docs] the old line names a gone flag")
        again = review_of("`app.py:1` [correctness] the old line names a gone flag")

        completed = self.run_script({"code-reviewer": [{"result": first}, {"result": again}, FINAL_READ],
                                     "coder": [FIX_CODER, NOTES_CODER], "closure": [{"result": loop_tests.CLOSED}]})

        self.assertEqual(completed.returncode, 0, completed.stderr)
        (row,) = [row for row in self.finding_rows() if row["path_key"] == "app.py"]
        self.assertEqual((row["class"], row.get("docs_kind", "")), ("correctness", ""))


DOCS_FINDING_ARGS = ["kind=finding", "gate=code-reviewer", "disposition=fix", "class=docs", "lane=none",
                     "actioned=fixed"]


class LoggerLabelTest(logger_tests.LoggerRepoCase):
    def test_each_listed_value_is_stored_on_a_docs_row(self):
        for value in review_loop_docs_kind.DOCS_KINDS:
            self.log([*DOCS_FINDING_ARGS, f"docs_kind={value}"])

        rows = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        self.assertEqual([row["docs_kind"] for row in rows], list(review_loop_docs_kind.DOCS_KINDS))

    def test_a_value_off_the_list_is_refused(self):
        done = self.log([*DOCS_FINDING_ARGS, "docs_kind=old"], expected_exit=1)

        self.assertIn("stale|new", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env, "review_finding"), [])

    def test_the_label_on_a_row_of_another_class_is_refused(self):
        done = self.log([*logger_tests.FINDING_ARGS, "docs_kind=stale"], expected_exit=1)

        self.assertIn("class=docs", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env, "review_finding"), [])

    def test_a_ledger_that_refuses_the_field_gets_the_row_without_it_and_the_label_is_kept_by_finding_id(self):
        old_ledger = {"FAKE_LEDGER_UNKNOWN_FIELDS": "docs_kind"}

        self.log([*DOCS_FINDING_ARGS, "docs_kind=stale"], extra_env=old_ledger)

        (row,) = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        self.assertNotIn("docs_kind", row)
        labels_file = self.temp_root / ".claude" / "review-finding-labels.jsonl"
        (label,) = [json.loads(line) for line in labels_file.read_text().splitlines()]
        self.assertEqual((label["finding_id"], label["docs_kind"]), (row["finding_id"], STALE))

    def test_a_ledger_that_refuses_three_optional_fields_still_gets_the_row(self):
        old_ledger = {"FAKE_LEDGER_UNKNOWN_FIELDS": "docs_kind,snapshot,ask_decided_by"}
        self.make_dirty()

        self.log([*DOCS_FINDING_ARGS, "docs_kind=new", "ask_decided_by=user"], extra_env=old_ledger)

        (row,) = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        self.assertEqual(row["class"], "docs")

    def test_with_no_ledger_the_local_row_carries_the_label(self):
        no_ledger = {"PATH": fake_ledger.path_without_ledger(os.environ["PATH"]),
                     "CARGO_HOME": str(self.temp_root / "no-cargo")}

        self.log([*DOCS_FINDING_ARGS, "docs_kind=new"], extra_env=no_ledger)

        findings_file = self.temp_root / ".claude" / "review-findings.jsonl"
        (row,) = [json.loads(line) for line in findings_file.read_text().splitlines()]
        self.assertEqual(row["docs_kind"], NEW)
        self.assertFalse((self.temp_root / ".claude" / "review-finding-labels.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
