"""Checks for inplace_edit.py (the files an in-place editor names)."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))

from inplace_edit import UNKNOWN_OPERAND, file_operands, find_editor_word, has_unseen_files


class FileOperandsTest(unittest.TestCase):
    def test_the_operands_follow_the_script(self):
        cases = {
            ("sed -i 's/a/b/' f.txt g.txt", "sed"): ["f.txt", "g.txt"],
            ("sed -i -e 's/a/b/' f.txt", "sed"): ["f.txt"],
            ("sed -i.bak --expression=x f.txt", "sed"): ["f.txt"],
            ("perl -pi -e 's/a/b/' f.txt", "perl"): ["f.txt"],
            ("awk -i inplace '{print}' f.txt", "awk"): ["f.txt"],
            ("sed -i -- 's/a/b/' f.txt", "sed"): ["f.txt"],
            ("sed -E -i 's/a/b/' f.txt", "sed"): ["f.txt"],
            ("sed -i -E 's/a/b/' f.txt", "sed"): ["f.txt"],
            ("sed -n -e 'p' f.txt", "sed"): ["f.txt"],
            ("sed -ne 'p' f.txt", "sed"): ["f.txt"],
            ("perl -pi -E 'say 1' f.txt", "perl"): ["f.txt"],
            ("sed -i '' 's/a/b/' f.txt", "sed"): ["f.txt"],
            ("sed -i '' -e 's/a/b/' f.txt", "sed"): ["f.txt"],
            ('sed -i "" s/a/b/ f.txt', "sed"): ["f.txt"],
            ("sed -i '' s/a/b/ f.txt", "sed"): ["f.txt"],
            ("gawk -i inplace -e a -e b f", "gawk"): ["f"],
            ("gawk -i inplace --source a --source b f", "gawk"): ["f"],
        }
        for (segment, editor), expected in cases.items():
            self.assertEqual(file_operands(segment, editor), expected, segment)

    def test_a_file_list_the_gate_cannot_see_is_an_unknown_operand(self):
        cases = {
            "find . -exec sed -i 's/a/b/' {} ;": ["{}"],
            "find . -exec sed -i s/a/b/ {} /tmp/x \\;": ["{}", "/tmp/x"],
            "find . -exec sed -i s/a/b/ {} +": ["{}"],
            "ls | xargs sed -i s/a/b/": ["(the files its invoker passes in)"],
            "ls | parallel sed -i s/a/b/ f.txt": ["f.txt", "(the files its invoker passes in)"],
            "fd md -x sed -i s/a/b/ /tmp/x": ["/tmp/x", "(the files its invoker passes in)"],
            "fd md --exec-batch sed -i s/a/b/ /tmp/x": ["/tmp/x", "(the files its invoker passes in)"],
        }
        for segment, expected in cases.items():
            self.assertEqual(file_operands(segment, "sed"), expected, segment)

    def test_assignments_are_files_for_sed_and_not_for_awk(self):
        self.assertEqual(file_operands("sed -i 's/a/b/' f.txt FOO=1", "sed"), ["f.txt", "FOO=1"])
        self.assertEqual(file_operands("awk -i inplace '{print}' f.txt FOO=1", "awk"), ["f.txt"])

    def test_a_redirect_inside_the_operand_list_is_no_operand(self):
        for segment in ("sed -i s/a/b/ f.txt > out.log", "sed -i s/a/b/ f.txt 2>&1"):
            self.assertEqual(file_operands(segment, "sed"), ["f.txt"], segment)

    def test_a_quoted_or_escaped_redirect_look_alike_never_hides_the_next_operand(self):
        for look_alike in ("'>&'", '">&"', "'2>&'", "'>'", "'2>'", "\\>"):
            segment = f"gawk -i inplace 1 /tmp/x {look_alike} CLAUDE.md"
            operands = file_operands(segment, "gawk")
            self.assertTrue("CLAUDE.md" in operands or has_unseen_files(operands), segment)

    def test_a_real_redirect_with_a_find_terminator_is_no_scratch_proof(self):
        operands = file_operands("find . -exec sed -i s/a/b/ {} /tmp/x \\; > out.log", "sed")
        self.assertTrue(has_unseen_files(operands))

    def test_has_unseen_files_names_the_lists_the_gate_cannot_read(self):
        self.assertTrue(has_unseen_files(["{}"]))
        self.assertTrue(has_unseen_files(["/tmp/x", UNKNOWN_OPERAND]))
        self.assertFalse(has_unseen_files(["/tmp/x", "f.txt"]))
        self.assertFalse(has_unseen_files([]))

    def test_an_fd_exec_flag_counts_only_for_fd(self):
        self.assertEqual(file_operands("grep -x gawk -i inplace 1 f", "gawk"), ["f"])
        self.assertEqual(file_operands("ssh -X host gawk -i inplace 1 f", "gawk"), ["f"])
        self.assertEqual(file_operands("fdfind -x gawk -i inplace 1", "gawk"), [UNKNOWN_OPERAND])
        self.assertEqual(file_operands("fd md -Hx gawk -i inplace 1", "gawk"), [UNKNOWN_OPERAND])

    def test_find_editor_word_counts_an_fd_exec_flag_only_for_fd(self):
        self.assertIsNone(find_editor_word("grep -x gawk -i inplace notes.txt"))
        self.assertIsNone(find_editor_word("ssh -X host gawk -i inplace 1 /etc/x"))
        for command in ("fd -x gawk -i inplace 1", "fd -X gawk -i inplace 1", "fd --exec gawk -i inplace 1",
                        "fd --exec-batch gawk -i inplace 1", "fdfind -x gawk -i inplace 1",
                        "fd md -Hx sed -i s/a/b/"):
            self.assertIsNotNone(find_editor_word(command), command)

    def test_no_operand_gives_an_empty_list(self):
        self.assertEqual(file_operands("sed -i 's/a/b/'", "sed"), [])
        self.assertEqual(file_operands("echo hi", "sed"), [])

    def test_a_line_joined_by_a_backslash_adds_no_operand(self):
        segment = "sed -i \\\n -e 's|a|b|' \\\n -e 's|c|d|' \\\n docs/plan.md"
        self.assertEqual(file_operands(segment, "sed"), ["docs/plan.md"])


if __name__ == "__main__":
    unittest.main()
