"""The review loop's first smell-reviewer prompt carries the single-caller census read against the review base."""
import sys
import tempfile
import unittest

import toolkit_paths
from test_review_loop_nearest import make_review_run
from test_single_caller_census import BRANCH_SOURCE, WORK_SOURCE, make_repo

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_script


class ReviewLoopCensusTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repo = directory.name
        # The branch commit adds old_helper; the uncommitted change adds its replacement and the second call.
        self.base = make_repo(self.repo, BRANCH_SOURCE, WORK_SOURCE)

    def smell_prompt(self, review_base):
        run = make_review_run(self.repo, review_base)
        request = review_loop_script.LoopRun.review_request(run, ("smell-reviewer", ["app.py"]))
        return request.prompt

    def test_a_based_review_lists_the_helper_a_commit_before_head_added(self):
        prompt = self.smell_prompt(self.base)

        self.assertIn("old_helper", prompt)
        self.assertIn("forwarder", prompt)

    def test_a_review_with_no_base_reads_only_the_work_tree(self):
        prompt = self.smell_prompt("")

        self.assertNotIn("old_helper", prompt)
        self.assertIn("none (read against HEAD)", prompt)


if __name__ == "__main__":
    unittest.main()
