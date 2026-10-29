"""Checks that log-review-finding saves a dirty reviewed tree as a commit and leaves the user's tree alone.

A row logged on a dirty tree carries `snapshot`, a commit on HEAD of the working tree kept under
refs/review-snapshots/<id>. Every case runs in a temp git repo with the stand-in ledger on PATH.

Script location: LOG_REVIEW_FINDING_SCRIPT, defaulting to the script in this tree.
"""

import os
import pathlib
import subprocess
import tempfile
import unittest

import fake_ledger
import toolkit_paths

LOG_REVIEW_FINDING = pathlib.Path(
    os.environ.get("LOG_REVIEW_FINDING_SCRIPT") or toolkit_paths.CLAUDE_DIR / "skills" / "review" / "log-review-finding"
)
GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}
RUN_ARGS = ["kind=run", "gate=code-reviewer", "n_findings=1", "lane=none"]
FINDING_ARGS = ["kind=finding", "gate=code-reviewer", "disposition=ask", "class=bug", "lane=none", "actioned=ask"]


class LoggerRepoCase(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.temp_root = pathlib.Path(temp_dir.name).resolve()
        self.repo = self.temp_root / "planted-repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "kept.txt").write_text("one\n")
        self.git("add", "kept.txt")
        self.git("commit", "-q", "-m", "base")
        self.ledger_env = fake_ledger.install(self.temp_root)

    def git(self, *args, extra_env=None):
        git_env = {**os.environ, **GIT_ENV, **(extra_env or {})}
        done = subprocess.run(["git", *args], cwd=self.repo, env=git_env, check=True, capture_output=True, text=True)
        return done.stdout.strip()

    def log(self, args, extra_env=None, expected_exit=0, cwd=None):
        caller_env = {key: value for key, value in os.environ.items() if not key.startswith(("CLAUDE_", "REVIEW_"))}
        env = {
            **caller_env,
            **GIT_ENV,
            "HOME": str(self.temp_root),
            "PATH": self.ledger_env["PATH"],
            "FAKE_LEDGER_ROWS": self.ledger_env["FAKE_LEDGER_ROWS"],
            **(extra_env or {}),
        }
        command = ["bash", str(LOG_REVIEW_FINDING), *args]
        done = subprocess.run(command, cwd=cwd or self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(done.returncode, expected_exit, done.stderr)
        return done

    def make_dirty(self):
        """An unstaged edit, a staged new file and an untracked file."""
        (self.repo / "kept.txt").write_text("two\n")
        (self.repo / "staged.txt").write_text("staged\n")
        self.git("add", "staged.txt")
        (self.repo / "untracked.txt").write_text("untracked\n")

    def user_tree_state(self):
        file_texts = {path.name: path.read_text() for path in sorted(self.repo.glob("*.txt"))}
        return self.git("ls-files", "--stage"), self.git("status", "--porcelain"), file_texts

    def snapshot_refs(self):
        return self.git("for-each-ref", "--format=%(refname)", "refs/review-snapshots/").splitlines()


class ReviewSnapshotTest(LoggerRepoCase):
    def test_a_dirty_tree_is_saved_as_a_commit_on_head_and_the_index_and_working_tree_do_not_change(self):
        self.make_dirty()
        before = self.user_tree_state()
        done = self.log(RUN_ARGS)

        self.assertEqual(self.user_tree_state(), before)
        (run_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_run")
        snapshot = run_row["snapshot"]
        self.assertEqual(done.stdout.strip(), f"run_id={run_row['run_id']}")
        self.assertEqual(self.git("rev-parse", f"refs/review-snapshots/{run_row['run_id']}"), snapshot)
        self.assertEqual(self.git("rev-parse", f"{snapshot}^"), self.git("rev-parse", "HEAD"))
        file_names = ("kept.txt", "staged.txt", "untracked.txt")
        saved_files = {name: self.git("show", f"{snapshot}:{name}") for name in file_names}
        self.assertEqual(saved_files, {"kept.txt": "two", "staged.txt": "staged", "untracked.txt": "untracked"})

    def test_a_clean_tree_sends_no_snapshot_and_saves_no_ref(self):
        self.log(RUN_ARGS)

        (run_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_run")
        self.assertNotIn("snapshot", run_row)
        self.assertEqual(self.snapshot_refs(), [])

    def test_a_later_row_for_the_same_finding_sends_the_commit_its_first_row_saved(self):
        self.make_dirty()
        done = self.log(FINDING_ARGS)
        finding_id = done.stdout.strip().removeprefix("finding_id=")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "fixed")
        self.log([*FINDING_ARGS, f"finding_id={finding_id}", "ask_outcome=accepted"])

        ask_row, outcome_row = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        self.assertEqual(outcome_row["dirty"], "0")
        self.assertEqual(outcome_row["snapshot"], ask_row["snapshot"])

    def test_a_ledger_build_without_the_field_gets_the_row_without_it_and_the_ref_is_deleted(self):
        self.make_dirty()
        done = self.log(RUN_ARGS, extra_env={"FAKE_LEDGER_UNKNOWN_FIELDS": "snapshot"})

        (run_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_run")
        self.assertNotIn("snapshot", run_row)
        self.assertEqual(self.snapshot_refs(), [])
        self.assertIn("does not store snapshot", done.stderr)
        self.assertNotIn("field_unknown", done.stderr)

    def test_a_ledger_build_without_ask_decided_by_gets_the_row_without_it(self):
        done = self.log([*FINDING_ARGS, "ask_decided_by=session"],
                        extra_env={"FAKE_LEDGER_UNKNOWN_FIELDS": "ask_decided_by"})

        (finding_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        self.assertNotIn("ask_decided_by", finding_row)
        self.assertIn("does not store ask_decided_by", done.stderr)
        self.assertNotIn("field_unknown", done.stderr)

    def test_a_ledger_build_without_either_field_gets_the_row_without_both_whatever_order_it_names_them(self):
        for refused in ("snapshot,ask_decided_by", "ask_decided_by,snapshot"):
            with self.subTest(refused):
                self.make_dirty()
                rows_before = len(fake_ledger.recorded_rows(self.ledger_env, "review_finding"))

                refusing_ledger = {"FAKE_LEDGER_UNKNOWN_FIELDS": refused}
                done = self.log([*FINDING_ARGS, "ask_decided_by=user"], extra_env=refusing_ledger)

                new_row = fake_ledger.recorded_rows(self.ledger_env, "review_finding")[rows_before]
                self.assertNotIn("ask_decided_by", new_row)
                self.assertNotIn("snapshot", new_row)
                self.assertNotIn("field_unknown", done.stderr)
                self.assertEqual(self.snapshot_refs(), [])
                self.git("checkout", "-q", "--", ".")
                self.git("clean", "-fdq")
                self.git("reset", "-q")

    def test_a_new_snapshot_prunes_the_refs_older_than_90_days(self):
        old_date = {"GIT_COMMITTER_DATE": "2020-01-01T00:00:00Z"}
        tree = self.git("rev-parse", "HEAD^{tree}")
        old_commit = self.git("commit-tree", tree, "-m", "old snapshot", extra_env=old_date)
        self.git("update-ref", "refs/review-snapshots/old", old_commit)
        self.make_dirty()
        self.log(RUN_ARGS)

        (run_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_run")
        self.assertEqual(self.snapshot_refs(), [f"refs/review-snapshots/{run_row['run_id']}"])


TEST_AUDIT_RUN_ARGS = ["kind=run", "gate=test-intent-reviewer", "n_findings=2", "lane=test-audit", "scope=branch-exit"]
TEST_AUDIT_FINDING_ARGS = ["kind=finding", "gate=test-intent-reviewer", "disposition=fix", "class=weak-assertion",
                           "lane=test-audit", "scope=branch-exit", "actioned=fixed"]


class TestAuditRowTest(LoggerRepoCase):
    def make_branch_with_uncommitted_fixes(self):
        """A branch commit of 2 added lines, then an unstaged 1-line edit and an untracked 3-line file."""
        self.git("checkout", "-q", "-b", "feature")
        (self.repo / "branch.txt").write_text("a\nb\n")
        self.git("add", "branch.txt")
        self.git("commit", "-q", "-m", "branch work")
        (self.repo / "kept.txt").write_text("fixed\n")
        (self.repo / "added_test.txt").write_text("x\ny\nz\n")

    def test_diff_base_measures_the_branch_and_the_working_tree_and_is_not_stored(self):
        self.make_branch_with_uncommitted_fixes()
        before = self.user_tree_state()
        self.log([*TEST_AUDIT_RUN_ARGS, "diff_base=main"])

        self.assertEqual(self.user_tree_state(), before)
        (run_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_run")
        self.assertEqual(run_row["diff_loc"], "7")
        self.assertNotIn("diff_base", run_row)

    def test_diff_base_with_a_typed_diff_loc_is_refused(self):
        done = self.log([*TEST_AUDIT_RUN_ARGS, "diff_base=main", "diff_loc=40"], expected_exit=1)

        self.assertIn("not both", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env, "review_run"), [])

    def test_diff_base_naming_no_ref_is_refused(self):
        done = self.log([*TEST_AUDIT_RUN_ARGS, "diff_base=planted-missing-ref"], expected_exit=1)

        self.assertIn("cannot measure", done.stderr)
        self.assertIn(f"names no commit in {self.repo}", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env, "review_run"), [])

    def test_root_logs_a_run_on_a_dirty_tree_from_another_folder_with_a_base_of_the_form_ref_tilde_n(self):
        (self.repo / "kept.txt").write_text("one\ntwo\n")
        self.git("commit", "-q", "-am", "integration work")
        self.git("checkout", "-q", "-b", "integration-base", "main~1")
        self.make_branch_with_uncommitted_fixes()
        outside = self.temp_root / "outside"
        outside.mkdir()

        self.log([*TEST_AUDIT_RUN_ARGS, f"root={self.repo}", "diff_base=main~1"], cwd=outside)

        (run_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_run")
        self.assertEqual((run_row["diff_loc"], run_row["head"]), ("7", self.git("rev-parse", "HEAD")))
        self.assertEqual(run_row["_cwd"], str(self.repo))
        self.assertNotIn("root", run_row)
        self.assertEqual(self.git("rev-parse", f"refs/review-snapshots/{run_row['run_id']}"), run_row["snapshot"])

    def test_a_root_that_cannot_be_entered_is_refused_and_no_row_is_sent(self):
        done = self.log([*TEST_AUDIT_RUN_ARGS, f"root={self.temp_root / 'planted-missing'}"], expected_exit=1)

        self.assertIn("cannot enter root=", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env), [])

    def test_an_unlocated_finding_is_sent_with_no_file_and_no_line(self):
        self.log([*TEST_AUDIT_FINDING_ARGS, "file=unlocated"])

        (finding_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        self.assertNotIn("path_key", finding_row)
        self.assertNotIn("line", finding_row)

    def test_an_unlocated_finding_with_a_line_is_sent_without_the_line_and_warns(self):
        done = self.log([*TEST_AUDIT_FINDING_ARGS, "file=unlocated", "line=4"])

        (finding_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        self.assertNotIn("path_key", finding_row)
        self.assertNotIn("line", finding_row)
        self.assertIn("line=4 dropped", done.stderr)

    def test_a_test_intent_finding_with_line_0_or_no_file_is_refused(self):
        for location_args in (["file=src/app.test.ts", "line=0"], ["line=12"]):
            with self.subTest(location_args=location_args):
                done = self.log([*TEST_AUDIT_FINDING_ARGS, *location_args], expected_exit=1)

                self.assertIn("file=unlocated", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env, "review_finding"), [])

    def test_a_test_intent_finding_with_its_test_file_and_line_is_sent(self):
        self.log([*TEST_AUDIT_FINDING_ARGS, "file=src/app.test.ts", "line=12"])

        (finding_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        self.assertEqual((finding_row["path_key"], finding_row["line"]), ("src/app.test.ts", "12"))

    def test_an_unquoted_spaced_result_is_refused_and_no_row_is_sent(self):
        done = self.log([*RUN_ARGS, "result=NEEDS", "CHANGES"], expected_exit=1)

        self.assertIn("'CHANGES' is not key=value", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env), [])

    def test_an_empty_or_non_numeric_int_field_is_refused_and_no_row_is_sent(self):
        int_cases = (
            [*FINDING_ARGS, "file=src/app.ts", "line="],
            [*FINDING_ARGS, "file=src/app.ts", "line=$4"],
            [*RUN_ARGS, "iter="],
            [*RUN_ARGS, "diff_loc=many"],
        )
        for args in int_cases:
            with self.subTest(args=args):
                done = self.log(args, expected_exit=1)

                self.assertIn("is not a whole number", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env), [])

    def test_whole_number_int_fields_and_a_null_n_findings_are_sent(self):
        self.log([*FINDING_ARGS, "file=src/app.ts", "line=12", "iter=2"])
        self.log([*RUN_ARGS, "n_findings=null", "diff_loc=40"])

        (finding_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_finding")
        (run_row,) = fake_ledger.recorded_rows(self.ledger_env, "review_run")
        self.assertEqual((finding_row["line"], finding_row["iter"]), ("12", "2"))
        self.assertEqual((run_row["n_findings"], run_row["diff_loc"]), (None, "40"))

    def test_a_result_outside_the_verdicts_is_refused_and_no_row_is_sent(self):
        done = self.log([*RUN_ARGS, "result=plan-impact"], expected_exit=1)

        self.assertIn("result=plan-impact is not PASS", done.stderr)
        self.assertEqual(fake_ledger.recorded_rows(self.ledger_env), [])

    def test_each_verdict_token_is_sent_as_given(self):
        for verdict in ("PASS", "PASS_WITH_WARNINGS", "NEEDS_CHANGES", "NOT_DISPATCHED"):
            with self.subTest(verdict=verdict):
                self.log([*RUN_ARGS, f"result={verdict}"])

        run_rows = fake_ledger.recorded_rows(self.ledger_env, "review_run")
        self.assertEqual([run_row["result"] for run_row in run_rows],
                         ["PASS", "PASS_WITH_WARNINGS", "NEEDS_CHANGES", "NOT_DISPATCHED"])

    def test_help_prints_usage_and_writes_nothing(self):
        for flag in ("--help", "-h"):
            with self.subTest(flag=flag):
                done = self.log([flag])
                self.assertEqual(done.stderr, "")
                self.assertIn("usage: log-review-finding kind=run|finding", done.stdout)
                self.assertEqual(fake_ledger.recorded_rows(self.ledger_env), [])


if __name__ == "__main__":
    unittest.main()
