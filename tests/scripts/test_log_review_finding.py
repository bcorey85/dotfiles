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


class ReviewSnapshotTest(unittest.TestCase):
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

    def log(self, args, extra_env=None):
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
        done = subprocess.run(command, cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
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


if __name__ == "__main__":
    unittest.main()
