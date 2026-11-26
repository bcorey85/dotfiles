import pathlib
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_prompts


def prompt_for(repo, agent):
    return review_loop_prompts.reviewer_prompt(repo, agent, ["src/app.py"], [])


class UnrunTestsRuleTest(unittest.TestCase):
    def make_repo(self, claude_md):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        (pathlib.Path(folder.name) / "CLAUDE.md").write_text(claude_md)
        return folder.name

    def test_the_test_reviewer_of_a_ci_only_repo_gets_the_unrun_tests_rule(self):
        repo = self.make_repo("# Notes\n\nFull suite: CI\n")
        prompt = prompt_for(repo, "test-reviewer")
        self.assertIn(review_loop_prompts.UNRUN_TESTS_RULE, prompt)

    def test_another_reviewer_of_a_ci_only_repo_gets_no_unrun_tests_rule(self):
        repo = self.make_repo("# Notes\n\nFull suite: CI\n")
        prompt = prompt_for(repo, "bug-reviewer")
        self.assertIn("src/app.py", prompt)
        self.assertNotIn(review_loop_prompts.UNRUN_TESTS_RULE, prompt)

    def test_the_test_reviewer_of_a_repo_that_runs_its_suite_locally_gets_no_unrun_tests_rule(self):
        repo = self.make_repo("# Notes\n\nQuality check: make test\n")
        prompt = prompt_for(repo, "test-reviewer")
        self.assertIn("Source under test", prompt)
        self.assertNotIn(review_loop_prompts.UNRUN_TESTS_RULE, prompt)

    def test_the_test_reviewer_of_a_repo_with_a_quality_check_and_a_ci_suite_line_gets_the_rule(self):
        repo = self.make_repo("# Notes\n\nQuality check: make test\n\nFull suite: CI\n")
        prompt = prompt_for(repo, "test-reviewer")
        self.assertIn(review_loop_prompts.UNRUN_TESTS_RULE, prompt)


if __name__ == "__main__":
    unittest.main()
