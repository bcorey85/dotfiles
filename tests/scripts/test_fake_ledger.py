import json
import os
import pathlib
import subprocess
import tempfile
import unittest

import fake_ledger

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com", "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
}

PLANTED_TREE = "sha256:" + "ab12" * 16
OTHER_BRANCH_TREE = "sha256:" + "cd34" * 16


class FakeLedgerTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = pathlib.Path(temp_dir.name)
        self.env = {**os.environ, **GIT_ENV, **fake_ledger.install(self.root)}
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "planted-branch"], cwd=self.repo, env=self.env, check=True)

    def ledger(self, *args, stdin=""):
        return subprocess.run(
            ["ledger", *args], cwd=self.repo, env=self.env, input=stdin, capture_output=True, text=True
        )

    def write(self, row_type, row, *extra):
        written = self.ledger("write", row_type, *extra, stdin=json.dumps(row))
        self.assertEqual(written.returncode, 0, written.stderr)

    def branch_review_run(self, tree, branch_key):
        return {"gate": "code-reviewer", "scope": "branch-exit", "source": "verify-branch", "tree": tree,
                "branch_key": branch_key}

    def test_write_records_the_row_with_its_type_session_and_cwd(self):
        self.write("spec_run", {"verdict": "planted"}, "--session", "planted-session")
        self.assertEqual(
            fake_ledger.recorded_rows(self.env),
            [
                {
                    "verdict": "planted",
                    "_type": "spec_run",
                    "_cwd": str(self.repo.resolve()),
                    "_session": "planted-session",
                }
            ],
        )

    def test_recorded_rows_filters_by_type(self):
        self.write("spec_run", {"verdict": "planted"})
        self.write("review_metrics", {"iter": "1"})
        self.assertEqual([row["iter"] for row in fake_ledger.recorded_rows(self.env, "review_metrics")], ["1"])

    def test_review_trees_lists_only_this_branchs_verify_branch_code_review_runs(self):
        self.write("review_run", self.branch_review_run(PLANTED_TREE, "planted-branch"))
        self.write("review_run", self.branch_review_run(OTHER_BRANCH_TREE, "other-branch"))
        self.write("review_run", {**self.branch_review_run(OTHER_BRANCH_TREE, "planted-branch"), "source": "round"})
        self.assertEqual(self.ledger("yield", "--review-trees").stdout, f"tree\n{PLANTED_TREE}\n")

    def test_any_other_command_exits_64(self):
        self.assertEqual(self.ledger("yield", "--deferred").returncode, 64)


if __name__ == "__main__":
    unittest.main()
