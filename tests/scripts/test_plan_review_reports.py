import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

from toolkit_paths import TOOLS_DIR

SCRIPT = pathlib.Path(os.environ.get("PLAN_REVIEW_REPORTS_SCRIPT") or TOOLS_DIR / "plan_review_reports.py")


class PlanReviewReportsTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.task_dir = pathlib.Path(temp.name)

    def check(self, review_round):
        return subprocess.run([sys.executable, str(SCRIPT), "check", str(self.task_dir), str(review_round)],
                              capture_output=True, text=True)

    def test_round_one_needs_no_reports(self):
        self.assertEqual(self.check(1).returncode, 0)

    def test_round_two_fails_when_round_one_report_is_missing(self):
        result = self.check(2)
        self.assertEqual(result.returncode, 1)
        self.assertIn("review-round1-shard-", result.stdout)

    def test_round_two_fails_when_round_one_report_is_empty(self):
        (self.task_dir / "review-round1-shard-a.md").write_text("")
        self.assertEqual(self.check(2).returncode, 1)

    def test_round_two_passes_with_a_round_one_shard_report(self):
        (self.task_dir / "review-round1-shard-a.md").write_text("VERDICT: CLEAN\n")
        self.assertEqual(self.check(2).returncode, 0)

    def test_round_three_names_the_round_that_is_missing(self):
        (self.task_dir / "review-round1-shard-a.md").write_text("findings\n")
        result = self.check(3)
        self.assertEqual(result.returncode, 1)
        self.assertIn("round 2 has no report file", result.stdout)


if __name__ == "__main__":
    unittest.main()
