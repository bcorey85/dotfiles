"""Run the tree-sitter CLI over a list of files and read its `parse --xml` output. Standard library only.

Knows nothing about what the caller does with the syntax trees: it finds the CLI and the grammar folder and returns
the XML root, or a note that says why there is none.
"""
import os
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ElementTree
from pathlib import Path

TREE_SITTER_TIMEOUT_SECONDS = 60
TREE_SITTER_ENV = "TREE_SITTER_CLI"
PARSER_DIR_ENV = "TREE_SITTER_PARSER_DIR"
EXPECTED_XML_FORM = "an XML document `<sources>` holding one `<source name=...>` per file"


def tree_sitter_command():
    override = os.environ.get(TREE_SITTER_ENV)
    if override:
        return override
    return shutil.which("tree-sitter")


def parser_dir():
    override = os.environ.get(PARSER_DIR_ENV)
    if override:
        return Path(override)
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "nvim" / "site" / "parser"


def field_child(element, *fields):
    """The first child whose `field` attribute is one of `fields`, or None."""
    for child in element:
        if child.get("field") in fields:
            return child
    return None


def node_source_text(lines, element):
    """The source text of the element's span, whitespace collapsed to single spaces. `lines` is the file's bytes
    split on newlines; the element's srow, scol, erow and ecol are zero-based and the columns are byte offsets."""
    start_row, end_row = int(element.get("srow")), int(element.get("erow"))
    start_col, end_col = int(element.get("scol")), int(element.get("ecol"))
    if start_row == end_row:
        raw = lines[start_row][start_col:end_col]
    else:
        raw = b" ".join([lines[start_row][start_col:], *lines[start_row + 1:end_row], lines[end_row][:end_col]])
    return " ".join(raw.decode("utf-8", "replace").split())


def tree_sitter_not_parsed_note(reason):
    return f"tree-sitter output did not parse: {reason} (expected {EXPECTED_XML_FORM})"


def run_tree_sitter(command, grammar_file, language, absolute_paths):
    """(XML root element, note). Never raises: a failed run is a note."""
    with tempfile.TemporaryDirectory() as work_dir:
        list_file = Path(work_dir) / "paths.txt"
        list_file.write_text("\n".join(absolute_paths) + "\n")
        try:
            done = subprocess.run([command, "parse", "--lib-path", str(grammar_file), "--lang-name", language,
                                   "--xml", "--paths", str(list_file)],
                                  capture_output=True, text=True, timeout=TREE_SITTER_TIMEOUT_SECONDS,
                                  stdin=subprocess.DEVNULL)
        except (subprocess.TimeoutExpired, OSError) as error:
            return None, f"tree-sitter did not run: {type(error).__name__} {error}"
    # A file with a syntax error makes the exit status non-zero while the XML is still written.
    xml_start = done.stdout.find("<?xml")
    if xml_start < 0:
        return None, tree_sitter_not_parsed_note(f"no XML on stdout; stderr: {done.stderr.strip()[:200]}")
    try:
        root = ElementTree.fromstring(done.stdout[xml_start:])
    except ElementTree.ParseError as error:
        return None, tree_sitter_not_parsed_note(str(error))
    if root.tag != "sources":
        return None, tree_sitter_not_parsed_note(f"root element is <{root.tag}>")
    return root, ""
