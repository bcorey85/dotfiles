import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.CODE_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_prompts
import single_caller_census

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}
FORWARDER_SOURCE = (
    "def wrapper(value):\n    return helper(value)\n\n\n"
    "def helper(value):\n    return value + 1\n\n\n"
    "print(wrapper(1))\n"
)


class CensusInReviewerPromptTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.repo = pathlib.Path(temp_dir.name)
        self.git("init", "-q", "-b", "main")
        (self.repo / "README.md").write_text("hello\n")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

    def git(self, *args):
        env = {**os.environ, **GIT_ENV}
        subprocess.run(["git", *args], cwd=self.repo, env=env, check=True, capture_output=True, text=True)

    def add_forwarder_file(self):
        (self.repo / "mod.py").write_text(FORWARDER_SOURCE)

    def test_the_smell_reviewer_prompt_lists_a_forwarder_the_work_tree_adds(self):
        self.add_forwarder_file()
        prompt = review_loop_prompts.reviewer_prompt(str(self.repo), "smell-reviewer", ["mod.py"], [])
        self.assertIn(single_caller_census.CENSUS_HEADING, prompt)
        self.assertIn("mod.py:1 single-caller-forwarder `wrapper`", prompt)

    def test_a_reviewer_other_than_the_smell_reviewer_gets_no_census(self):
        self.add_forwarder_file()
        prompt = review_loop_prompts.reviewer_prompt(str(self.repo), "code-reviewer", ["mod.py"], [])
        self.assertNotIn(single_caller_census.CENSUS_HEADING, prompt)
        self.assertNotIn("single-caller-forwarder", prompt)

    def test_a_round_with_a_fix_diff_gets_no_census(self):
        self.add_forwarder_file()
        prompt = review_loop_prompts.reviewer_prompt(
            str(self.repo), "smell-reviewer", ["mod.py"], [], fix_diff_path="/tmp/fix.diff"
        )
        self.assertNotIn(single_caller_census.CENSUS_HEADING, prompt)

    def test_an_entry_in_a_file_the_reviewer_does_not_own_is_left_out(self):
        self.add_forwarder_file()
        prompt = review_loop_prompts.reviewer_prompt(str(self.repo), "smell-reviewer", ["other.py"], [])
        self.assertNotIn("single-caller-forwarder", prompt)

    def test_a_census_that_cannot_run_says_so_in_the_prompt(self):
        prompt = review_loop_prompts.reviewer_prompt(str(self.repo / "missing"), "smell-reviewer", ["a.py"], [])
        self.assertIn("The census did not run:", prompt)

    def test_census_base_moves_the_range_the_census_reads(self):
        self.add_forwarder_file()
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "branch work")
        at_head = review_loop_prompts.reviewer_prompt(str(self.repo), "smell-reviewer", ["mod.py"], [])
        self.assertNotIn("single-caller-forwarder", at_head)
        self.assertIn(single_caller_census.CENSUS_HEADING + "\nnone", at_head)
        from_main = review_loop_prompts.reviewer_prompt(
            str(self.repo), "smell-reviewer", ["mod.py"], [], census_base="HEAD~1"
        )
        self.assertIn("single-caller-forwarder `wrapper`", from_main)


if __name__ == "__main__":
    unittest.main()
