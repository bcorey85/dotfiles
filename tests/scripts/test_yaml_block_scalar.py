"""Checks for yaml_block_scalar.py, the reader of YAML block scalar text."""
import sys
import unittest

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import yaml_block_scalar


def read(lines, header_text):
    header = yaml_block_scalar.BLOCK_HEADER.match(header_text)
    return yaml_block_scalar.block_scalar_text(lines, 0, 2, header)


class BlockScalarTextTest(unittest.TestCase):
    def test_literal_block_keeps_its_line_breaks_and_the_last_one(self):
        self.assertEqual(read(["  exclude: |", "    a", "    b", "  next: 1"], "|"), "a\nb\n")

    def test_dash_header_cuts_the_last_line_break(self):
        self.assertEqual(read(["  exclude: |-", "    a", "    b"], "|-"), "a\nb")

    def test_folded_block_joins_lines_with_a_space(self):
        self.assertEqual(read(["  exclude: >", "    a", "    b"], ">"), "a b\n")

    def test_line_indented_further_keeps_its_extra_spaces(self):
        self.assertEqual(read(["  exclude: |", "    a", "      b"], "|"), "a\n  b\n")

    def test_block_with_no_body_line_is_empty(self):
        self.assertEqual(read(["  exclude: |", "  next: 1"], "|"), "")


class FoldLinesTest(unittest.TestCase):
    def test_blank_line_between_two_lines_stays_one_line_break(self):
        self.assertEqual(yaml_block_scalar.fold_lines(["a", "", "b"]), "a\nb")


if __name__ == "__main__":
    unittest.main()
