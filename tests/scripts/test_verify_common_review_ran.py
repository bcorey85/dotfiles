"""Checks for verify_common.review_ran: it reads the branch's review trees from `ledger yield --review-trees`.

run: python3 tests/scripts/test_verify_common_review_ran.py
"""
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = pathlib.Path(os.environ.get("VERIFY_COMMON_SCRIPTS_DIR") or REPO_ROOT / "claude" / ".claude" / "scripts")
sys.path.insert(0, str(SCRIPTS_DIR))
import verify_common  # noqa: E402

PLANTED_TREE = "sha256:" + "ab12" * 16
OTHER_TREE = "sha256:" + "cd34" * 16


def plant_ledger(directory, body):
    stub = pathlib.Path(directory) / "ledger"
    stub.write_text("#!/bin/sh\n" + body)
    stub.chmod(0o755)


class ReviewRan(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        patcher = mock.patch.dict(os.environ, {"PATH": self.directory.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_planted_fingerprint_ran_and_other_did_not(self):
        plant_ledger(self.directory.name, f'[ "$*" = "yield --review-trees" ] || exit 64\nprintf "tree\\n{PLANTED_TREE}\\n"\n')

        ran, _ = verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)
        notRan, reason = verify_common.review_ran("some-repo", "some-branch", OTHER_TREE)

        self.assertTrue(ran)
        self.assertFalse(notRan)
        self.assertIn("differs", reason)

    def test_header_only_listing_did_not_run(self):
        plant_ledger(self.directory.name, 'printf "tree\\n"\n')

        ran, _ = verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertFalse(ran)

    def test_no_ledger_on_path_reports_not_installed(self):
        ran, reason = verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertEqual((ran, reason), (False, "ledger not installed"))

    def test_nonzero_exit_raises_fail_with_stderr_line(self):
        plant_ledger(self.directory.name, 'echo "ledger yield: not inside a git repository" >&2\nexit 1\n')

        with self.assertRaises(verify_common.Fail) as raised:
            verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertEqual(str(raised.exception), "ledger yield: not inside a git repository")


if __name__ == "__main__":
    unittest.main()
