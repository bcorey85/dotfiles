"""Checks for verify_common.review_ran and review_state.

review_ran reads the branch's review trees from `ledger yield --review-trees`.

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
sys.path.insert(0, str(SCRIPTS_DIR / "review"))
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))
import script_utils
import verify_common

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
        plant_ledger(
            self.directory.name, f'[ "$*" = "yield --review-trees" ] || exit 64\nprintf "tree\\n{PLANTED_TREE}\\n"\n'
        )

        ran, _ = verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)
        not_ran, reason = verify_common.review_ran("some-repo", "some-branch", OTHER_TREE)

        self.assertTrue(ran)
        self.assertFalse(not_ran)
        self.assertIn("differs", reason)

    def test_header_only_listing_did_not_run(self):
        plant_ledger(self.directory.name, 'printf "tree\\n"\n')

        ran, _ = verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertFalse(ran)

    def test_no_ledger_on_path_raises_unread(self):
        with self.assertRaises(script_utils.LedgerNotInstalledError):
            verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

    def test_nonzero_exit_raises_unread_with_stderr_line(self):
        plant_ledger(self.directory.name, 'echo "ledger yield: not inside a git repository" >&2\nexit 1\n')

        with self.assertRaises(script_utils.LedgerUnreadError) as raised:
            verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertEqual(str(raised.exception),
                         "ledger yield --review-trees: ledger yield: not inside a git repository")


class ReviewStateWithoutLedger(unittest.TestCase):
    """With no ledger on PATH, the checkout's own record of the logged review decides."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        patcher = mock.patch.dict(os.environ, {"PATH": directory.name})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_review_logged_here_counts(self):
        review = verify_common.review_state("some-repo", "some-branch", PLANTED_TREE, PLANTED_TREE)

        self.assertEqual((review["read"], review["ran"]), (False, True))
        self.assertIn("ledger not installed", review["reason"])

    def test_no_review_logged_here_did_not_run(self):
        review = verify_common.review_state("some-repo", "some-branch", PLANTED_TREE, None)

        self.assertEqual((review["read"], review["ran"]), (False, False))


class BusyLedger(unittest.TestCase):
    """The ledger exits 75 after waiting on its lock. The stub logs each call so a test counts the tries."""

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.calls = pathlib.Path(self.directory.name) / "calls"
        patcher = mock.patch.dict(os.environ, {
            "PATH": os.pathsep.join([self.directory.name, "/usr/bin", "/bin"]),
            script_utils.LEDGER_BACKOFF_ENV: "0", script_utils.LEDGER_CALL_TIMEOUT_ENV: "10"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def plant_script(self, body):
        plant_ledger(self.directory.name, f'echo x >> "{self.calls}"\ntries=$(wc -l < "{self.calls}")\n{body}')

    def tries(self):
        return len(self.calls.read_text().split())

    def test_a_busy_ledger_is_tried_again_and_the_clear_answer_is_used(self):
        self.plant_script(f'[ "$tries" -lt 3 ] && exit 75\nprintf "tree\\n{PLANTED_TREE}\\n"\n')

        ran, _ = verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertTrue(ran)
        self.assertEqual(self.tries(), 3)

    def test_a_ledger_that_stays_busy_raises_ledger_busy_with_its_own_line_and_never_reads_as_no_review(self):
        self.plant_script("echo 'ledger: cache behind, retry' >&2\nexit 75\n")

        with self.assertRaises(script_utils.LedgerBusyError) as raised:
            verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertIn("ledger yield --review-trees", str(raised.exception))
        self.assertIn("ledger: cache behind, retry", str(raised.exception))
        self.assertEqual(self.tries(), script_utils.attempts_within(script_utils.LEDGER_WAIT_SECONDS,
                                                                    script_utils.LEDGER_BACKOFF_SECONDS))

    def test_the_busy_message_names_the_time_spent_waiting(self):
        self.plant_script("exit 75\n")

        with self.assertRaises(script_utils.LedgerBusyError) as raised:
            verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertRegex(str(raised.exception), r"\d+ s of pauses")

    def test_a_ledger_that_does_not_answer_in_time_raises_ledger_busy(self):
        self.plant_script("exec sleep 30\n")
        os.environ[script_utils.LEDGER_CALL_TIMEOUT_ENV] = "0.3"

        with self.assertRaises(script_utils.LedgerBusyError) as raised:
            verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertIn("no answer within", str(raised.exception))

    def test_a_real_failure_is_not_tried_again(self):
        self.plant_script("echo 'ledger yield: broken schema' >&2\nexit 1\n")

        with self.assertRaises(script_utils.LedgerUnreadError) as raised:
            verify_common.review_ran("some-repo", "some-branch", PLANTED_TREE)

        self.assertEqual(str(raised.exception), "ledger yield --review-trees: ledger yield: broken schema")
        self.assertEqual(self.tries(), 1)


if __name__ == "__main__":
    unittest.main()
