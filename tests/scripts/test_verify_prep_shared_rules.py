"""One criteria grammar for plan_check and verify-prep, and the review-neutral folder of the tree fingerprint."""
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import plan_format
import verify_common

PLAN_CHECK = toolkit_paths.CODE_DIR / "plan_check.py"
SPEC = ("## Phase Status\n\n- [ ] Phase 1: First (risk: low)\n\n## Phase 1: First\n\nx\n\n"
        "## Acceptance Criteria\n\nSee the criteria file.\n")
NUMBERED = "1. **AC1** — the first thing.\n2. **AC2** — the second thing.\n"
BULLETED = "- **AC1** — the first thing.\n- **AC2** — the second thing.\n"
SUFFIXED = "- **AC12** — base.\n- **AC12a** — first part.\n- **AC7b** — other.\n"
UNBOLDED = "1. AC1 — the first thing.\n"


def git(top, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=top, check=True,
                   capture_output=True)


class CriteriaGrammarTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = pathlib.Path(folder.name)
        (self.folder / "spec.md").write_text(SPEC)

    def final_check(self, criteria_text):
        (self.folder / plan_format.CRITERIA_FILE_NAME).write_text(criteria_text)
        return subprocess.run([sys.executable, str(PLAN_CHECK), "check", "--final", str(self.folder / "spec.md")],
                              capture_output=True, text=True, check=False)

    def test_plan_check_final_refuses_a_numbered_list_verify_prep_refuses(self):
        done = self.final_check(NUMBERED)

        self.assertEqual(done.returncode, 1)
        self.assertIn("acceptance-criteria.md:1:", done.stdout + done.stderr)
        with self.assertRaises(verify_common.VerifyError):
            verify_common.parse_criteria_file(NUMBERED)

    def test_plan_check_final_refuses_a_list_that_holds_no_id(self):
        done = self.final_check(UNBOLDED)

        self.assertEqual(done.returncode, 1)
        self.assertIn("holds no", done.stdout + done.stderr)

    def test_plan_check_final_passes_a_bulleted_list(self):
        done = self.final_check(BULLETED)

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIsNone(plan_format.criteria_file_failure(BULLETED))
        entries, manual = verify_common.parse_criteria_file(BULLETED)
        self.assertEqual([entry["id"] for entry in entries], ["AC1", "AC2"])
        self.assertEqual(manual, [])

    def test_a_letter_suffixed_id_passes_plan_check_and_verify_prep(self):
        done = self.final_check(SUFFIXED)

        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        entries, _manual = verify_common.parse_criteria_file(SUFFIXED)
        ids = [entry["id"] for entry in entries]
        self.assertEqual(ids, ["AC12", "AC12a", "AC7b"])
        self.assertEqual(sorted(ids, key=plan_format.criterion_id_order), ["AC7b", "AC12", "AC12a"])
        self.assertEqual(plan_format.criterion_ids_in("covers AC12a and ticket AC4"), ["AC12a"])
        self.assertEqual(plan_format.criteria_by_id(SUFFIXED)["AC12a"], "first part.")


class ReviewNeutralFolderTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name)
        git(self.repo, "init", "-q")
        (self.repo / "docs" / "changes").mkdir(parents=True)
        (self.repo / "docs" / "other").mkdir()
        (self.repo / "code.py").write_text("x = 1\n")
        (self.repo / "docs" / "changes" / "note.md").write_text("one\n")
        (self.repo / "docs" / "other" / "guide.md").write_text("one\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "base")
        self.base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo, capture_output=True, text=True,
                                   check=True).stdout.strip()

    def fingerprint(self):
        return verify_common.tree_fingerprint(self.repo, self.base)

    def test_a_commit_that_changes_only_a_change_note_keeps_the_fingerprint(self):
        before = self.fingerprint()
        (self.repo / "docs" / "changes" / "note.md").write_text("two\n")
        (self.repo / "docs" / "changes" / "new-note.md").write_text("new\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-q", "-m", "notes")

        self.assertEqual(self.fingerprint(), before)

    def test_a_code_change_changes_the_fingerprint(self):
        before = self.fingerprint()
        (self.repo / "code.py").write_text("x = 2\n")

        self.assertNotEqual(self.fingerprint(), before)

    def test_a_note_outside_the_neutral_folder_changes_the_fingerprint(self):
        before = self.fingerprint()
        (self.repo / "docs" / "other" / "guide.md").write_text("two\n")

        self.assertNotEqual(self.fingerprint(), before)


if __name__ == "__main__":
    unittest.main()
