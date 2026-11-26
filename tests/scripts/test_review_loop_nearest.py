"""Tests for the nearest-other-functions block of the review loop's smell-reviewer prompt."""
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
import review_loop_nearest
import review_loop_script

# The exported helper: returns the item or None.
SHARED_HELPER_PY = """\
def find_by_key(items, wanted):
    if not items:
        return None
    for item in items:
        if item.id == wanted:
            return item
    return None
"""

# The private helper a branch adds: another name, a lookup step and a guard on the plan, but not a renamed copy.
PRIVATE_HELPER_PY = """\
def _node_from_plan(plan, node_id):
    if plan is None:
        return None
    nodes = plan.nodes
    for node in nodes:
        if node.id == node_id:
            return node
    return None
"""

# A function whose token shape is far from the helpers above.
UNRELATED_HELPER_PY = """\
def render_table(rows, widths):
    lines = []
    for row in rows:
        cells = []
        for index, cell in enumerate(row):
            cells.append(str(cell).ljust(widths[index]))
        lines.append(" | ".join(cells))
    header = "=" * len(lines[0]) if lines else ""
    lines.insert(0, header)
    lines.append(header)
    print(len(lines), sum(widths))
    return "\\n".join(lines)
"""


def make_review_run(repo, review_base=""):
    """The few LoopRun fields review_request reads, with no loop around them."""
    return types.SimpleNamespace(
        repo=str(repo), review_base=review_base, prior_issues=[], round_two_fix_diff_path="", asks=[], brief="",
        test_strategy="", no_code_rulings=[], ruled_out=set(), iter_count=1)


class NearestFunctionsPromptTests(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name)
        self.git("init", "-q")
        self.write("lib/finders.py", SHARED_HELPER_PY)
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", "base")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True)

    def write(self, name, text):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def commit_all(self, message):
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", message)

    def prompt_of(self, agent, run=None):
        run = run or make_review_run(self.root)
        request = review_loop_script.LoopRun.review_request(run, (agent, ["plan/nodes.py"]))
        return request.prompt

    def test_the_smell_prompt_names_the_exported_helper_a_new_private_helper_resembles(self):
        self.write("plan/nodes.py", PRIVATE_HELPER_PY)

        prompt = self.prompt_of("smell-reviewer")

        self.assertIn("Nearest other functions for each function this change added:", prompt)
        self.assertIn("_node_from_plan", prompt)
        self.assertIn("find_by_key", prompt)

    def test_the_prompt_leaves_out_the_helper_of_a_file_the_reviewer_does_not_own(self):
        self.write("plan/nodes.py", PRIVATE_HELPER_PY)
        self.write("plan/other.py", PRIVATE_HELPER_PY.replace("_node_from_plan", "_other_from_plan"))

        request = review_loop_script.LoopRun.review_request(
            make_review_run(self.root), ("smell-reviewer", ["plan/nodes.py"]))

        self.assertIn("_node_from_plan", request.prompt)
        # The unowned helper may still show as a neighbour (indented); it must not head an entry of its own.
        self.assertNotIn("\n- plan/other.py", request.prompt)

    def test_a_later_round_does_not_run_the_shape_pass(self):
        self.write("plan/nodes.py", PRIVATE_HELPER_PY)
        run = make_review_run(self.root)
        run.round_two_fix_diff_path = "/tmp/round-one.diff"

        prompt = self.prompt_of("smell-reviewer", run)

        self.assertNotIn("Nearest other functions", prompt)
        self.assertIn("Bound: the round-one fix diff.", prompt)

    def test_the_review_base_reaches_the_diff(self):
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.root, check=True, capture_output=True,
                              text=True).stdout.strip()
        self.write("plan/nodes.py", PRIVATE_HELPER_PY)
        self.commit_all("helper")

        from_base = self.prompt_of("smell-reviewer", make_review_run(self.root, review_base=base))
        from_head = self.prompt_of("smell-reviewer", make_review_run(self.root))

        self.assertIn("_node_from_plan", from_base)
        self.assertNotIn("_node_from_plan", from_head)

    def test_a_function_in_a_file_the_reviewer_does_not_own_is_left_out(self):
        self.write("plan/nodes.py", PRIVATE_HELPER_PY)

        text = review_loop_nearest.nearest_functions_text(self.root, "", ["plan/other.py"])

        self.assertEqual("", text)

    def test_no_other_reviewer_prompt_carries_the_block(self):
        self.write("plan/nodes.py", PRIVATE_HELPER_PY)

        for agent in ("bug-reviewer", "test-reviewer"):
            with self.subTest(agent=agent):
                self.assertNotIn("Nearest other functions", self.prompt_of(agent))

    def test_a_tree_the_diff_cannot_read_gives_a_note_and_no_crash(self):
        text = review_loop_nearest.nearest_functions_text(self.root, "no-such-ref", ["plan/nodes.py"])

        self.assertTrue(text.startswith("Nearest other functions: not read"), text)

    def test_a_refactor_flow_error_gives_its_message_as_a_note(self):
        def fail(_repo):
            raise review_loop_nearest.refactor_flow.RefactorFlowError("boom")

        with mock.patch.object(review_loop_nearest.refactor_flow, "untracked_files", fail):
            text = review_loop_nearest.nearest_functions_text(self.root, "", ["plan/nodes.py"])

        self.assertEqual(review_loop_nearest.skipped_note("boom"), text)

    def test_a_shape_pass_that_cannot_list_files_says_so(self):
        self.write("plan/nodes.py", PRIVATE_HELPER_PY)

        with mock.patch.object(review_loop_nearest.script_utils, "repo_file_paths", return_value=None):
            text = review_loop_nearest.nearest_functions_text(self.root, "", ["plan/nodes.py"])

        self.assertIn("Nearest other functions: not read (git could not list the files", text)
        self.assertNotIn("partly read", text)

    def test_a_missing_tree_sitter_keeps_the_listing_and_adds_a_partial_note(self):
        self.write("web/app.ts", "export const one = 1;\n")
        self.commit_all("typescript file")
        self.write("plan/nodes.py", PRIVATE_HELPER_PY)

        with mock.patch.object(review_loop_nearest.shape_clones.tree_sitter_xml, "tree_sitter_command",
                               return_value=None):
            text = review_loop_nearest.nearest_functions_text(self.root, "", ["plan/nodes.py"])

        self.assertIn("find_by_key", text)
        self.assertIn(
            review_loop_nearest.partial_note("TypeScript functions not read: tree-sitter CLI not found"), text)
        self.assertNotIn("not read (", text)

    def test_an_added_function_with_no_neighbour_adds_nothing(self):
        self.write("plan/other.py", UNRELATED_HELPER_PY)

        text = review_loop_nearest.nearest_functions_text(self.root, "", ["plan/other.py"])

        self.assertEqual("", text)


if __name__ == "__main__":
    unittest.main()
