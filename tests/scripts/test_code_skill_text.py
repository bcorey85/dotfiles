"""Text checks on the /code skill and the code-fork agent: neither hands the user a git command.

The fork writes the stop blocks and the main session relays them, so a `! git` line there is a subagent handing the user
a command. The blocks name the commit subject instead."""
import re
import unittest

import toolkit_paths

BANG_GIT_LINE = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)?`?!\s*git\b")
GIT_COMMIT_COMMAND = re.compile(r"\bgit\s+(?:-\S+\s+\S+\s+)*commit\b")


class CodeSkillTextTest(unittest.TestCase):
    def test_no_git_command_for_the_user(self):
        text_files = (
            toolkit_paths.CODE_SKILL_FILE,
            toolkit_paths.CODE_FORK_AGENT_FILE,
            toolkit_paths.CODE_PHASE_END_FILE,
        )
        for text_file in text_files:
            for number, line in enumerate(text_file.read_text().splitlines(), start=1):
                where = f"{text_file.name}:{number}"
                with self.subTest(where=where):
                    self.assertIsNone(BANG_GIT_LINE.search(line), f"{where} starts a `! git` command")
                    self.assertIsNone(GIT_COMMIT_COMMAND.search(line), f"{where} holds a `git commit` command")
                    self.assertNotIn("`! git", line, f"{where} holds a `! git` command")

    def test_stop_blocks_name_the_commit_subject(self):
        text = toolkit_paths.CODE_SKILL_FILE.read_text() + toolkit_paths.CODE_PHASE_END_FILE.read_text()
        self.assertGreaterEqual(text.count("Commit subject: <subject>"), 3)

    def test_the_resume_paragraph_demands_a_review_of_a_changed_diff(self):
        sentence = ("A resume whose feedback changes files runs step 3's `phase_start.py --resume` before its coder, "
                    "and step 5's review before any stop, unless the diff is empty.")
        self.assertIn(sentence, toolkit_paths.CODE_SKILL_FILE.read_text())

    def test_the_resume_paragraph_orders_phase_start_before_the_launch_and_writes_it_in_full(self):
        text = toolkit_paths.CODE_SKILL_FILE.read_text()
        self.assertIn("Run `phase_start.py --resume` before applying the asks.", text)
        self.assertIn("review_fix.py launch --fix <file> --user-ruled <N> --session-ruled <M> --repo <repo> --detach",
                      text)
        resume_paragraph = next(line for line in text.splitlines() if line.startswith("**Resume.**"))
        self.assertNotIn("…", resume_paragraph)

    def test_a_coder_prompt_holds_no_commit_and_a_denied_git_write_does_not_stop_the_run(self):
        text = toolkit_paths.CODE_SKILL_FILE.read_text()
        no_commit_rule = ("The coder's prompt holds no stage or commit step; a commit the task asks for becomes "
                          "the phase-end commit subject.")
        denied_write_rule = ("A coder's report of a denied git write is no STOP: go on to step 4 with the changes "
                             "uncommitted.")
        self.assertIn(no_commit_rule, text)
        self.assertIn(denied_write_rule, text)

    def test_the_phase_boundary_step_reads_the_phase_end_file_and_the_skill_holds_no_block(self):
        text = toolkit_paths.CODE_SKILL_FILE.read_text()
        self.assertIn("Read `~/.claude/skills/code/phase-end-block.md` and print the matching block", text)
        self.assertNotIn("## Phase-Complete Block", text)
        self.assertIn("## Phase-Complete Block", toolkit_paths.CODE_PHASE_END_FILE.read_text())


if __name__ == "__main__":
    unittest.main()
