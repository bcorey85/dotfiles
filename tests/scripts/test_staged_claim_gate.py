"""Checks for staged_claim_gate.py, the Stop and SubagentStop hook that blocks a final message saying files are
staged when the index does not hold them."""
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = toolkit_paths.GATES_DIR / "staged_claim_gate.py"


def git(repo, *arguments):
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


class StagedClaimGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.make_repo("repo")
        self.outside = self.tmp / "outside"
        self.outside.mkdir()

    def make_repo(self, name):
        repo = self.tmp / name
        repo.mkdir()
        git(repo, "init", "-q")
        git(repo, "config", "user.email", "t@example.com")
        git(repo, "config", "user.name", "t")
        for file_name in ("a.txt", "b.txt"):
            (repo / file_name).write_text("x\n")
        git(repo, "add", "a.txt", "b.txt")
        git(repo, "commit", "-qm", "start")
        for file_name in ("a.txt", "b.txt"):
            (repo / file_name).write_text("y\n")
        return repo

    def run_gate(self, message, cwd=None, event="Stop", stop_hook_active=False):
        payload = {"hook_event_name": event, "cwd": str(cwd or self.repo), "last_assistant_message": message,
                   "stop_hook_active": stop_hook_active}
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                                  text=True, cwd=str(self.tmp))
        self.assertEqual((finished.returncode, finished.stderr), (0, ""))
        return finished.stdout

    def assert_blocked(self, message, **options):
        decision = json.loads(self.run_gate(message, **options))
        self.assertEqual(decision["decision"], "block")
        self.assertIn("git diff --cached --name-only", decision["reason"])
        return decision["reason"]

    def assert_passes(self, message, **options):
        self.assertEqual(self.run_gate(message, **options), "")

    def test_a_staged_claim_with_an_empty_index_is_blocked(self):
        for message in ("Done. The files are staged for you to commit.", "I staged the change.",
                        "All three edits are now staged."):
            with self.subTest(message=message):
                reason = self.assert_blocked(message)
                self.assertIn(str(self.repo), reason)
                self.assertIn("nothing", reason)

    def test_a_subagent_hand_back_is_checked_too(self):
        self.assert_blocked("Fix applied; the files are staged.", event="SubagentStop")

    def test_a_staged_claim_with_files_in_the_index_passes(self):
        git(self.repo, "add", "a.txt")
        self.assert_passes("The change is staged.")
        self.assert_passes("a.txt is staged.")

    def test_a_named_file_missing_from_the_index_is_blocked_by_name(self):
        git(self.repo, "add", "a.txt")
        reason = self.assert_blocked("a.txt and b.txt are staged.")
        self.assertIn("b.txt", reason)
        self.assertNotIn("a.txt", reason.replace(str(self.repo), ""))

    def test_a_claim_naming_another_repo_checks_that_repo(self):
        other = self.make_repo("other")
        self.assert_blocked(f"{other}/a.txt is staged.", cwd=self.outside)
        git(other, "add", "a.txt")
        self.assert_passes(f"{other}/a.txt is staged.", cwd=self.outside)

    def test_messages_without_a_staged_claim_pass(self):
        for message in ("Nothing is staged yet.", "The files are not staged.", "Stage a.txt when you are ready.",
                        "No files are staged.", "The unstaged edits stay in the tree.",
                        "The files were staged and committed as abc123.", ""):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_conditional_sentences_pass_with_an_empty_index(self):
        for message in ("Once the files are staged, run the commit line.", "After everything is staged, commit."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_a_conditional_word_after_the_claim_does_not_hide_it(self):
        for message in ("All four files are staged, so review the diff before you commit.",
                        "The edits are staged; commit when ready.", "I staged the fix after the tests passed."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_conditional_word_in_an_earlier_clause_does_not_hide_the_claim(self):
        for message in ("Once the tests passed, I staged the fix.",
                        "After the review I fixed two lines and all files are staged."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_staged_review_data_passes_with_an_empty_index(self):
        for message in ("The fix diffs are staged under fix-diffs.", "Two rows are staged for the ledger."):
            with self.subTest(message=message):
                self.assert_passes(message)

    def test_review_data_in_the_git_index_and_plain_files_still_block(self):
        for message in ("The diffs are staged in the git index.", "All files are staged.",
                        "Two rows are staged, and all files are staged.",
                        "The rows are staged. All files are staged.",
                        "The diff of the file is staged.", "The file for each finding is staged."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_negation_in_one_sentence_does_not_hide_a_claim_in_another(self):
        for message in ("The files are staged. No tests failed.", "I staged the fix.\nNothing else changed."):
            with self.subTest(message=message):
                self.assert_blocked(message)

    def test_a_file_named_relative_to_a_subdirectory_cwd_is_checked_in_the_index(self):
        sub = self.repo / "sub"
        sub.mkdir()
        (sub / "c.txt").write_text("x\n")
        git(self.repo, "add", "sub/c.txt")
        self.assert_passes("c.txt is staged.", cwd=sub)

        (sub / "c.txt").write_text("y\n")
        git(self.repo, "reset", "-q", "sub/c.txt")
        git(self.repo, "add", "a.txt")
        reason = self.assert_blocked("c.txt is staged.", cwd=sub)
        self.assertIn("sub/c.txt", reason)

    def test_a_second_stop_and_a_claim_outside_any_repo_pass(self):
        self.assert_passes("The files are staged.", stop_hook_active=True)
        self.assert_passes("The files are staged.", cwd=self.outside)


if __name__ == "__main__":
    unittest.main()
