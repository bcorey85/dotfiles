"""Tests for tree_sitter_xml: finding the tree-sitter CLI and grammar folder, and reading `parse --xml` output."""
import importlib.util
import os
import stat
import tempfile
import unittest
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from unittest import mock

import toolkit_paths

MODULE_PATH = toolkit_paths.LIB_DIR / "tree_sitter_xml.py"
module_spec = importlib.util.spec_from_file_location("tree_sitter_xml", MODULE_PATH)
tree_sitter_xml = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(tree_sitter_xml)


class TreeSitterXmlTest(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name)

    def stub(self, script_body):
        stub = self.root / "stub-tree-sitter"
        stub.write_text(f"#!/bin/sh\n{script_body}\n")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        return str(stub)

    def run_stub(self, script_body):
        return tree_sitter_xml.run_tree_sitter(self.stub(script_body), self.root / "g.so", "typescript", ["/a.ts"])

    def test_the_cli_override_wins_over_the_path(self):
        with mock.patch.dict(os.environ, {tree_sitter_xml.TREE_SITTER_ENV: "/custom/tree-sitter"}):
            self.assertEqual("/custom/tree-sitter", tree_sitter_xml.tree_sitter_command())

    def test_the_parser_folder_override_wins_over_the_data_home(self):
        with mock.patch.dict(os.environ, {tree_sitter_xml.PARSER_DIR_ENV: "/custom/parsers"}):
            self.assertEqual(Path("/custom/parsers"), tree_sitter_xml.parser_dir())

    def test_the_parser_folder_defaults_under_the_data_home(self):
        env = {"XDG_DATA_HOME": "/data"}
        with mock.patch.dict(os.environ, env):
            os.environ.pop(tree_sitter_xml.PARSER_DIR_ENV, None)
            self.assertEqual(Path("/data/nvim/site/parser"), tree_sitter_xml.parser_dir())

    def test_xml_after_a_noisy_prefix_gives_the_sources_root(self):
        xml_line = "<?xml version=\"1.0\"?><sources><source name=\"/a.ts\"/></sources>"

        root, note = self.run_stub(f"echo noise; echo '{xml_line}'")

        self.assertEqual("", note)
        self.assertEqual("sources", root.tag)

    def test_output_with_no_xml_is_a_note_with_the_expected_form(self):
        root, note = self.run_stub("echo plain")

        self.assertIsNone(root)
        self.assertIn(tree_sitter_xml.EXPECTED_XML_FORM, note)

    def test_a_root_that_is_not_sources_is_a_note(self):
        root, note = self.run_stub("echo '<?xml version=\"1.0\"?><other/>'")

        self.assertIsNone(root)
        self.assertIn("root element is <other>", note)

    def test_field_child_returns_the_first_child_with_one_of_the_fields_or_none(self):
        element = ElementTree.fromstring('<a><b field="x"/><c field="y"/><d field="y"/></a>')

        self.assertEqual("c", tree_sitter_xml.field_child(element, "y", "z").tag)
        self.assertEqual("b", tree_sitter_xml.field_child(element, "z", "x").tag)
        self.assertIsNone(tree_sitter_xml.field_child(element, "missing"))

    def test_node_source_text_joins_a_multi_line_span_and_collapses_whitespace(self):
        lines = b"x = (a,\n      b,\n  c) + 1".split(b"\n")
        one_row = ElementTree.fromstring('<n srow="0" scol="0" erow="0" ecol="1"/>')
        three_rows = ElementTree.fromstring('<n srow="0" scol="4" erow="2" ecol="4"/>')

        self.assertEqual("x", tree_sitter_xml.node_source_text(lines, one_row))
        self.assertEqual("(a, b, c)", tree_sitter_xml.node_source_text(lines, three_rows))

    def test_node_source_text_counts_columns_as_bytes(self):
        lines = "é = f(a)".encode().split(b"\n")
        element = ElementTree.fromstring('<n srow="0" scol="6" erow="0" ecol="9"/>')

        self.assertEqual("(a)", tree_sitter_xml.node_source_text(lines, element))


if __name__ == "__main__":
    unittest.main()
