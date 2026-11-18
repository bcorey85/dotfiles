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
        for text_file in (toolkit_paths.CODE_SKILL_FILE, toolkit_paths.CODE_FORK_AGENT_FILE):
            for number, line in enumerate(text_file.read_text().splitlines(), start=1):
                where = f"{text_file.name}:{number}"
                with self.subTest(where=where):
                    self.assertIsNone(BANG_GIT_LINE.search(line), f"{where} starts a `! git` command")
                    self.assertIsNone(GIT_COMMIT_COMMAND.search(line), f"{where} holds a `git commit` command")
                    self.assertNotIn("`! git", line, f"{where} holds a `! git` command")

    def test_stop_blocks_name_the_commit_subject(self):
        text = toolkit_paths.CODE_SKILL_FILE.read_text()
        self.assertGreaterEqual(text.count("Commit subject: <subject>"), 3)


if __name__ == "__main__":
    unittest.main()
