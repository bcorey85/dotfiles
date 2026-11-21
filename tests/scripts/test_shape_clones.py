"""Tests for shape_clones: renamed copies, near matches and the helper catalog, on Python and TypeScript bodies."""
import importlib.util
import os
import stat
import subprocess
import tempfile
import textwrap
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

import toolkit_paths

SHAPE_CLONES = toolkit_paths.CLAUDE_DIR / "skills" / "refactor" / "scripts" / "shape_clones.py"
module_spec = importlib.util.spec_from_file_location("shape_clones", SHAPE_CLONES)
shape_clones = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(shape_clones)
# shape_clones puts the refactor scripts folder on sys.path when it loads.
import clone_pairs  # noqa: E402
import tree_sitter_xml  # noqa: E402

Untracked = namedtuple("Untracked", ["path", "added_lines"])
DiffFile = namedtuple("DiffFile", ["path", "hunks"])
DiffHunk = namedtuple("DiffHunk", ["added"])


def typescript_available():
    command = tree_sitter_xml.tree_sitter_command()
    grammars = [tree_sitter_xml.parser_dir() / f"{name}.so" for name in ("typescript", "tsx")]
    return bool(command) and all(grammar.is_file() for grammar in grammars)


FIND_BY_KEY_PY = """\
def find_by_key(items, wanted):
    if not items:
        return None
    for item in items:
        if item.id == wanted:
            return item
    return None
"""

RENAMED_COPY_PY = """\
def get_node_from_plan(plan_nodes, node_id):
    if not plan_nodes:
        return None
    for node in plan_nodes:
        if node.key == node_id:
            return node
    return None
"""

# The same lookup with a lookup step and a guard on the plan: close, but not a copy.
DOMAIN_NAMED_PY = """\
def get_node_from_plan(plan, node_id):
    if plan is None:
        return None
    nodes = plan.nodes
    for node in nodes:
        if node.id == node_id:
            return node
    return None
"""

COUNT_UNDER_PY = """\
def count_under(values, limit):
    total = 0
    for value in values:
        if value < limit:
            total += 1
    return total
"""

COUNT_UP_TO_PY = COUNT_UNDER_PY.replace("count_under", "tally_up_to").replace("value < limit", "value <= limit")

FIND_BY_KEY_TS = """\
export function findByKey(items: Item[], wanted: string): Item | undefined {
  if (!items) {
    return undefined;
  }
  for (const item of items) {
    if (item.id === wanted) {
      return item;
    }
  }
  return undefined;
}
"""

RENAMED_COPY_TS = """\
export function getNodeFromPlan(planNodes: PlanNode[], nodeId: string): PlanNode | undefined {
  if (!planNodes) {
    return undefined;
  }
  for (const node of planNodes) {
    if (node.key === nodeId) {
      return node;
    }
  }
  return undefined;
}
"""

COUNT_UNDER_TS = """\
export function countUnder(values: number[], limit: number): number {
  let total = 0;
  for (const value of values) {
    if (value < limit) {
      total += 1;
    }
  }
  return total;
}
"""

COUNT_UP_TO_TS = COUNT_UNDER_TS.replace("countUnder", "tallyUpTo").replace("value < limit", "value <= limit")


class ShapeRepoTestCase(unittest.TestCase):
    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.root = Path(temp_dir.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)

    def write(self, name, text):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)

    def shapes(self, *changed_names):
        """The ShapeResult when each named file is the branch's work: every line of it counts as added."""
        untracked = []
        for name in changed_names:
            lines = (self.root / name).read_text().splitlines()
            untracked.append(Untracked(name, list(enumerate(lines, start=1))))
        return shape_clones.branch_shapes([], untracked, self.root)

    def pair_names(self, result):
        return [(pair.changed.name, pair.other.name, pair.distance) for pair in result.pairs]


class PythonShapeTest(ShapeRepoTestCase):
    def test_a_copy_with_renamed_names_and_attributes_is_a_renamed_copy_pair(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY)

        result = self.shapes("plan/nodes.py")

        self.assertEqual([("get_node_from_plan", "find_by_key", 0)], self.pair_names(result))

    def test_a_one_token_variant_is_a_near_match_pair(self):
        self.write("lib/counts.py", COUNT_UNDER_PY)
        self.write("plan/tally.py", COUNT_UP_TO_PY)

        result = self.shapes("plan/tally.py")

        self.assertEqual([("tally_up_to", "count_under", 1)], self.pair_names(result))

    def test_a_statement_moved_out_of_an_if_is_not_a_renamed_copy(self):
        inside = ("def f(x, y, z):\n    if x:\n        a(y)\n        b(z)\n    c = [x, y, z]\n"
                  "    return c, x, y, z, x, y, z\n")
        outside = ("def g(x, y, z):\n    if x:\n        a(y)\n    b(z)\n    c = [x, y, z]\n"
                   "    return c, x, y, z, x, y, z\n")
        self.write("lib/inside.py", inside)
        self.write("lib/outside.py", outside)

        result = self.shapes("lib/outside.py")

        self.assertNotIn(0, [pair.distance for pair in result.pairs])

    def test_an_argument_moved_out_of_a_nested_call_is_not_a_renamed_copy(self):
        nested_in = ("def f(a, b, c):\n    r = k(g(a, b), c)\n    s = [a, b, c]\n    t = (a, b, c)\n"
                     "    return r, s, t, a, b, c, r\n")
        nested_out = ("def h(a, b, c):\n    r = k(g(a), b, c)\n    s = [a, b, c]\n    t = (a, b, c)\n"
                      "    return r, s, t, a, b, c, r\n")
        self.write("lib/in.py", nested_in)
        self.write("lib/out.py", nested_out)

        result = self.shapes("lib/out.py")

        self.assertNotIn(0, [pair.distance for pair in result.pairs])

    def test_a_body_two_tokens_apart_is_no_pair(self):
        self.write("lib/counts.py", COUNT_UNDER_PY)
        self.write("plan/tally.py", COUNT_UP_TO_PY.replace("total += 1", "total -= 2"))

        self.assertEqual([], self.shapes("plan/tally.py").pairs)

    def test_a_function_the_branch_did_not_touch_is_not_a_changed_side(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY)
        self.write("other.py", "x = 1\n")

        self.assertEqual([], self.shapes("other.py").pairs)

    def test_a_body_under_the_token_floor_is_never_compared(self):
        self.write("lib/a.py", "def one(x):\n    return x.y\n")
        self.write("lib/b.py", "def two(a):\n    return a.b\n")

        self.assertEqual([], self.shapes("lib/b.py").pairs)

    def test_two_test_files_pair_with_nothing(self):
        self.write("tests/test_a.py", FIND_BY_KEY_PY)
        self.write("tests/test_b.py", RENAMED_COPY_PY)

        self.assertEqual([], self.shapes("tests/test_b.py").pairs)

    def test_an_added_domain_named_function_lists_the_generic_helper_as_its_nearest_entry(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", DOMAIN_NAMED_PY)

        result = self.shapes("plan/nodes.py")

        self.assertEqual(1, len(result.listings))
        listing = result.listings[0]
        self.assertEqual("get_node_from_plan", listing.added.name)
        self.assertEqual(["find_by_key"], [entry.name for entry, _score in listing.neighbours])
        self.assertEqual("find_by_key(items, wanted)", listing.neighbours[0][0].signature)

    def test_the_catalog_leaves_out_test_helpers(self):
        self.write("tests/helpers.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", DOMAIN_NAMED_PY)

        self.assertEqual([], self.shapes("plan/nodes.py").listings)

    def test_a_file_that_is_not_python_is_counted_in_a_note_and_the_rest_still_compares(self):
        self.write("broken.py", "def (:\n")
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY)

        result = self.shapes("plan/nodes.py")

        self.assertEqual(1, len(result.pairs))
        self.assertEqual(1, len(result.notes))
        self.assertIn("1 Python file(s) not read", result.notes[0])
        self.assertIn("broken.py", result.notes[0])

    def test_a_tracked_file_deleted_from_the_work_tree_is_no_note_and_the_rest_still_compares(self):
        self.write("gone.py", FIND_BY_KEY_PY)
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY)
        subprocess.run(["git", "add", "gone.py"], cwd=self.root, check=True)
        (self.root / "gone.py").unlink()

        result = self.shapes("plan/nodes.py")

        self.assertEqual([], result.notes)
        self.assertEqual([("get_node_from_plan", "find_by_key", 0)], self.pair_names(result))

    def test_a_docstring_and_annotations_do_not_change_the_body_tokens(self):
        plain = shape_clones.python_functions("a.py", FIND_BY_KEY_PY.encode())[0]
        annotated_source = FIND_BY_KEY_PY.replace("def find_by_key(items, wanted):",
                                                  'def find_by_key(items: list, wanted: int) -> int:\n'
                                                  '    """Find the item."""')
        annotated = shape_clones.python_functions("a.py", annotated_source.encode())[0]

        self.assertEqual(plain.tokens, annotated.tokens)

    def test_a_function_the_branch_only_edited_pairs_but_is_not_cataloged(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY)
        edited_line = DiffFile("plan/nodes.py", [DiffHunk([(3, RENAMED_COPY_PY.splitlines()[2])])])

        result = shape_clones.branch_shapes([edited_line], [], self.root)

        self.assertEqual([("get_node_from_plan", "find_by_key", 0)], self.pair_names(result))
        self.assertEqual([], result.listings)

    def test_a_function_outside_the_changed_lines_of_its_file_is_not_a_changed_side(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("lib/counts.py", COUNT_UNDER_PY)
        self.write("plan/both.py", RENAMED_COPY_PY + "\n" + COUNT_UP_TO_PY)
        first_function_lines = [(number, "") for number in range(1, 8)]

        result = shape_clones.branch_shapes([DiffFile("plan/both.py", [DiffHunk(first_function_lines)])], [],
                                            self.root)

        self.assertEqual([("get_node_from_plan", "find_by_key", 0)], self.pair_names(result))

    def test_an_async_function_pairs_with_a_renamed_copy(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY.replace("def get_node_from_plan", "async def get_node_later"))

        self.assertEqual([("get_node_later", "find_by_key", 0)], self.pair_names(self.shapes("plan/nodes.py")))

    def test_a_class_method_pairs_with_a_renamed_copy(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", "class Plan:\n" + textwrap.indent(RENAMED_COPY_PY, "    "))

        self.assertEqual([("get_node_from_plan", "find_by_key", 0)], self.pair_names(self.shapes("plan/nodes.py")))

    def test_a_function_added_by_the_branch_is_not_listed_as_an_existing_helper_of_another(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/first.py", DOMAIN_NAMED_PY)
        self.write("plan/second.py", DOMAIN_NAMED_PY.replace("get_node_from_plan", "pick_node"))

        result = self.shapes("plan/first.py", "plan/second.py")

        listed = {listing.added.name: [entry.name for entry, _score in listing.neighbours]
                  for listing in result.listings}
        self.assertEqual({"get_node_from_plan": ["find_by_key"], "pick_node": ["find_by_key"]}, listed)

    def test_a_function_with_only_its_def_line_changed_is_not_listed_as_added(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", DOMAIN_NAMED_PY)
        def_line = DOMAIN_NAMED_PY.splitlines()[0]
        edited_signature = DiffFile("plan/nodes.py", [DiffHunk([(1, def_line)])])

        result = shape_clones.branch_shapes([edited_signature], [], self.root)

        self.assertEqual([], result.listings)
        self.assertEqual(0, result.uncataloged)

    def test_nested_and_overlapping_functions_never_pair_with_each_other(self):
        tokens = ("a",) * shape_clones.MIN_BODY_TOKENS
        outer = shape_clones.FunctionShape("a.py", "outer", "outer()", 1, 20, tokens)
        inner = shape_clones.FunctionShape("a.py", "inner", "inner()", 5, 10, tokens)
        apart = shape_clones.FunctionShape("a.py", "apart", "apart()", 30, 40, tokens)

        nested_pairs = shape_clones.find_pairs([outer], [outer, inner])
        apart_pairs = shape_clones.find_pairs([outer], [outer, inner, apart])

        self.assertEqual([], nested_pairs)
        self.assertEqual(["apart"], [pair.other.name for pair in apart_pairs])

    def test_short_added_functions_do_not_use_up_catalog_places(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        names = []
        for number in range(shape_clones.MAX_CATALOG_FUNCTIONS):
            self.write(f"plan/a{number:02}.py", f"def small_{number}(x):\n    return x.y\n")
            names.append(f"plan/a{number:02}.py")
        self.write("plan/z.py", DOMAIN_NAMED_PY)

        result = self.shapes(*names, "plan/z.py")

        self.assertEqual(["get_node_from_plan"], [listing.added.name for listing in result.listings])
        self.assertEqual(0, result.uncataloged)

    def test_the_catalog_cap_counts_only_added_functions_that_can_be_listed(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        names = []
        for number in range(shape_clones.MAX_CATALOG_FUNCTIONS):
            self.write(f"plan/a{number:02}.py", f"def small_{number}(x):\n    return x.y\n")
            names.append(f"plan/a{number:02}.py")
        count = shape_clones.MAX_CATALOG_FUNCTIONS + 1
        for number in range(count):
            self.write(f"plan/n{number:02}.py", DOMAIN_NAMED_PY.replace("get_node_from_plan", f"get_node_{number}"))
            names.append(f"plan/n{number:02}.py")

        result = self.shapes(*names)

        self.assertEqual(shape_clones.MAX_CATALOG_FUNCTIONS, len(result.listings))
        self.assertEqual(1, result.uncataloged)

    def test_an_added_test_function_gets_no_catalog_listing_and_no_place_under_the_cap(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        names = []
        for number in range(shape_clones.MAX_CATALOG_FUNCTIONS):
            self.write(f"tests/test_a{number:02}.py", DOMAIN_NAMED_PY.replace("get_node_from_plan", f"check_{number}"))
            names.append(f"tests/test_a{number:02}.py")
        self.write("plan/z.py", DOMAIN_NAMED_PY)

        result = self.shapes(*names, "plan/z.py")

        self.assertEqual(["get_node_from_plan"], [listing.added.name for listing in result.listings])
        self.assertEqual(0, result.uncataloged)

    def test_a_cap_of_one_neighbour_keeps_the_closest_and_orders_by_score_then_path(self):
        self.write("lib/a_count.py", COUNT_UNDER_PY)
        self.write("lib/b_find.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", DOMAIN_NAMED_PY)

        with mock.patch.object(shape_clones, "NEIGHBOUR_FLOOR", 0.0):
            both = self.shapes("plan/nodes.py").listings[0].neighbours
            with mock.patch.object(shape_clones, "MAX_NEIGHBOURS", 1):
                capped = self.shapes("plan/nodes.py").listings[0].neighbours

        self.assertEqual(["find_by_key", "count_under"], [entry.name for entry, _score in both])
        self.assertGreater(both[0][1], both[1][1])
        self.assertEqual(["find_by_key"], [entry.name for entry, _score in capped])

    def test_a_helper_under_the_similarity_floor_is_not_a_neighbour(self):
        self.write("lib/counts.py", COUNT_UNDER_PY)
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", DOMAIN_NAMED_PY)

        neighbours = self.shapes("plan/nodes.py").listings[0].neighbours

        self.assertEqual(["find_by_key"], [entry.name for entry, _score in neighbours])
        self.assertTrue(all(score >= shape_clones.NEIGHBOUR_FLOOR for _entry, score in neighbours))

    def test_pairs_past_the_cap_are_counted_in_a_more_pairs_line(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("plan/n1.py", RENAMED_COPY_PY)
        self.write("plan/n2.py", RENAMED_COPY_PY.replace("get_node_from_plan", "get_node_two"))

        with mock.patch.object(shape_clones, "MAX_SHAPE_PAIRS", 1):
            result = self.shapes("plan/n1.py", "plan/n2.py")
            summary = shape_clones.shape_summary_line(result)
            with mock.patch("builtins.print") as printed:
                shape_clones.print_candidates(result)

        self.assertEqual(3, len(result.pairs))
        self.assertIn("(1 listed)", summary)
        self.assertIn("2 more pair(s) not listed", printed.call_args.args[0])

    def test_added_functions_past_the_catalog_cap_are_counted_and_said(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        count = shape_clones.MAX_CATALOG_FUNCTIONS + 1
        for number in range(count):
            self.write(f"plan/n{number}.py", DOMAIN_NAMED_PY.replace("get_node_from_plan", f"get_node_{number}"))
        names = [f"plan/n{number}.py" for number in range(count)]

        result = self.shapes(*names)
        summary = shape_clones.shape_summary_line(result)
        with mock.patch("builtins.print") as printed:
            shape_clones.print_candidates(result)

        self.assertEqual(1, result.uncataloged)
        self.assertIn("1 added function(s) past the first 12 not cataloged", summary)
        self.assertIn("1 added function(s) past the first 12 not cataloged", printed.call_args.args[0])

    def test_the_summary_line_of_listings_only_and_a_noted_none_form(self):
        function = shape_clones.python_functions("a.py", FIND_BY_KEY_PY.encode())[0]
        listing = shape_clones.CatalogListing(function, [(function, 0.9)])
        listings_only = shape_clones.ShapeResult([], [listing], [])
        none_with_note = shape_clones.ShapeResult([], [], ["a note"])

        self.assertEqual("- 0 renamed-copy and 0 near-match pair(s) on changed functions (0 listed), "
                         "1 added function(s) with nearest other functions, in the dispatch prompt below",
                         shape_clones.shape_summary_line(listings_only))
        self.assertEqual("- no renamed-copy or near-match pair on changed functions; a note",
                         shape_clones.shape_summary_line(none_with_note))

    def test_output_names_both_sites_and_both_kinds(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("lib/counts.py", COUNT_UNDER_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY)
        self.write("plan/tally.py", COUNT_UP_TO_PY)
        result = self.shapes("plan/nodes.py", "plan/tally.py")

        with mock.patch("builtins.print") as printed:
            shape_clones.print_candidates(result)
        text = printed.call_args.args[0]

        self.assertIn("plan/nodes.py:1-7 get_node_from_plan(plan_nodes, node_id) ~ "
                      "lib/finders.py:1-7 find_by_key(items, wanted)", text)
        self.assertIn("Near match", text)
        self.assertIn("[1 edit(s)]", text)

    def test_the_summary_line_counts_each_kind_and_the_skipped_form_names_its_reason(self):
        self.write("lib/finders.py", FIND_BY_KEY_PY)
        self.write("lib/counts.py", COUNT_UNDER_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY)
        self.write("plan/tally.py", COUNT_UP_TO_PY)

        found = shape_clones.shape_summary_line(self.shapes("plan/nodes.py", "plan/tally.py"))
        self.write("other.py", "x = 1\n")
        none = shape_clones.shape_summary_line(self.shapes("other.py"))
        skipped = shape_clones.shape_summary_line(shape_clones.skipped_result(clone_pairs.HEAD_MODE_NOTE))

        self.assertIn("1 renamed-copy and 1 near-match pair(s) on changed functions", found)
        self.assertEqual("- no renamed-copy or near-match pair on changed functions", none)
        self.assertEqual(f"- shape clones: {clone_pairs.HEAD_MODE_NOTE}", skipped)

    def test_nothing_to_judge_prints_nothing(self):
        with mock.patch("builtins.print") as printed:
            shape_clones.print_candidates(shape_clones.skipped_result("x"))

        printed.assert_not_called()


@unittest.skipUnless(typescript_available(), "tree-sitter CLI or the typescript/tsx grammar is not installed")
class TypeScriptShapeTest(ShapeRepoTestCase):
    def test_a_renamed_copy_with_other_types_is_a_renamed_copy_pair(self):
        self.write("lib/find.ts", FIND_BY_KEY_TS)
        self.write("plan/nodes.ts", RENAMED_COPY_TS)

        result = self.shapes("plan/nodes.ts")

        self.assertEqual([("getNodeFromPlan", "findByKey", 0)], self.pair_names(result))
        self.assertEqual([], result.notes)

    def test_a_one_token_variant_is_a_near_match_pair(self):
        self.write("lib/count.ts", COUNT_UNDER_TS)
        self.write("plan/tally.ts", COUNT_UP_TO_TS)

        self.assertEqual([("tallyUpTo", "countUnder", 1)], self.pair_names(self.shapes("plan/tally.ts")))

    def test_a_tsx_file_compares_with_a_ts_file(self):
        self.write("lib/find.ts", FIND_BY_KEY_TS)
        self.write("ui/Nodes.tsx", RENAMED_COPY_TS)

        self.assertEqual([("getNodeFromPlan", "findByKey", 0)], self.pair_names(self.shapes("ui/Nodes.tsx")))

    def test_a_domain_named_typescript_function_lists_the_generic_helper(self):
        domain_named = RENAMED_COPY_TS.replace("  if (!planNodes) {\n    return undefined;\n  }\n",
                                               "  const nodes = planNodes;\n  if (!nodes) {\n    return undefined;\n"
                                               "  }\n")
        self.write("lib/find.ts", FIND_BY_KEY_TS)
        self.write("plan/nodes.ts", domain_named)

        result = self.shapes("plan/nodes.ts")

        self.assertEqual(1, len(result.listings))
        self.assertEqual("getNodeFromPlan", result.listings[0].added.name)
        self.assertEqual("findByKey(items: Item[], wanted: string)", result.listings[0].neighbours[0][0].signature)

    def test_a_tracked_typescript_file_deleted_from_the_work_tree_is_no_note(self):
        self.write("gone.ts", FIND_BY_KEY_TS)
        self.write("lib/find.ts", FIND_BY_KEY_TS)
        self.write("plan/nodes.ts", RENAMED_COPY_TS)
        subprocess.run(["git", "add", "gone.ts"], cwd=self.root, check=True)
        (self.root / "gone.ts").unlink()

        result = self.shapes("plan/nodes.ts")

        self.assertEqual([], result.notes)
        self.assertEqual([("getNodeFromPlan", "findByKey", 0)], self.pair_names(result))

    def test_a_cast_type_and_jsx_text_are_placeholders_so_copies_differing_there_still_match(self):
        template = ("export function render(items, wanted) {\n  const first = wanted as %s;\n"
                    "  for (const item of items) {\n    if (item.id === wanted) { return <div>%s</div>; }\n  }\n"
                    "  return null;\n}\n")
        self.write("ui/A.tsx", template % ("Foo", "Hello world"))
        self.write("ui/B.tsx", (template % ("Bar", "Goodbye now")).replace("render", "show"))

        result = self.shapes("ui/B.tsx")

        self.assertEqual([("show", "render", 0)], self.pair_names(result))

    def test_an_arrow_function_takes_the_name_of_its_variable_and_an_anonymous_one_is_left_out(self):
        self.write("lib/arrows.ts", "export const pick = (items, wanted) => {\n  for (const item of items) {\n"
                                    "    if (item.id === wanted) { return item; }\n  }\n  return null;\n};\n"
                                    "items.map((item) => item.id);\n")

        names = [function.name for function in shape_clones.read_functions(self.root)[0]]

        self.assertEqual(["pick"], names)


TS_PLACEHOLDER_BODY = [("keyword", "for"), ("identifier", "item"), ("type_identifier", "Foo"),
                       ("jsx_text", "Hello"), ("property_identifier", "id"), ("number", "1"),
                       ("true", "true"), ("keyword", "return")] * 3


def ts_source_xml(root, path, name, params, body):
    """One canned `<source>` as tree-sitter prints it: a function with a name, parameters and leaf body nodes."""
    first_line = f"function {name}({params}) {{"
    start_col = first_line.index("(")
    end_col = first_line.index(")") + 1
    parameter_xml = ", ".join(f"<identifier>{parameter}</identifier>" for parameter in params.split(", "))
    body_xml = "".join(f"<{tag}>{text}</{tag}>" for tag, text in body)
    return (f'<source name="{root / path}"><function_declaration srow="0" scol="0" erow="1" ecol="1">function'
            f'<identifier field="name">{name}</identifier>'
            f'<formal_parameters field="parameters" srow="0" scol="{start_col}" erow="0" ecol="{end_col}">'
            f'({parameter_xml})</formal_parameters>{body_xml}</function_declaration></source>')


class StubbedTypeScriptTest(ShapeRepoTestCase):
    """The TypeScript path run against a stub `tree-sitter` that prints canned XML, so it runs without the CLI."""

    def setUp(self):
        super().setUp()
        self.stub_dir = self.root / "stub"
        self.stub_dir.mkdir()
        self.recorded_paths = self.stub_dir / "recorded-paths.txt"
        (self.stub_dir / "typescript.so").write_text("")

    def write_ts(self, path, name, params, body):
        self.write(path, f"function {name}({params}) {{\n}}\n")
        return ts_source_xml(self.root, path, name, params, body)

    def stub_env(self, script_body):
        stub = self.stub_dir / "tree-sitter"
        stub.write_text(f"#!/bin/sh\ncp \"$8\" '{self.recorded_paths}'\n{script_body}\n")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        return {tree_sitter_xml.TREE_SITTER_ENV: str(stub), tree_sitter_xml.PARSER_DIR_ENV: str(self.stub_dir)}

    def xml_stub_env(self, sources_xml, exit_code=0):
        fixture = self.stub_dir / "fixture.xml"
        fixture.write_text(f'<?xml version="1.0"?><sources>{sources_xml}</sources>')
        return self.stub_env(f"cat '{fixture}'\nexit {exit_code}")

    def shapes_with_env(self, env, *changed_names):
        with mock.patch.dict(os.environ, env):
            return self.shapes(*changed_names)

    def two_copies_xml(self, other_body):
        library = self.write_ts("lib/find.ts", "findByKey", "items, wanted", TS_PLACEHOLDER_BODY)
        plan = self.write_ts("plan/nodes.ts", "getNodeFromPlan", "planNodes, nodeId", other_body)
        return library + plan

    def test_a_renamed_copy_is_a_pair_even_when_tree_sitter_exits_non_zero(self):
        env = self.xml_stub_env(self.two_copies_xml(TS_PLACEHOLDER_BODY), exit_code=1)

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual([("getNodeFromPlan", "findByKey", 0)], self.pair_names(result))
        self.assertEqual([], result.notes)

    def test_cast_type_and_jsx_text_placeholders_hide_the_text_that_differs(self):
        other = [(tag, {"Foo": "Bar", "Hello": "Goodbye now"}.get(text, text)) for tag, text in TS_PLACEHOLDER_BODY]
        env = self.xml_stub_env(self.two_copies_xml(other))

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual([("getNodeFromPlan", "findByKey", 0)], self.pair_names(result))

    def test_copies_differing_only_in_a_boolean_or_null_literal_are_a_renamed_copy_pair(self):
        library_body = [*TS_PLACEHOLDER_BODY, ("null", "null")]
        swaps = {"true": ("false", "false"), "null": ("undefined", "undefined")}
        other = [swaps.get(text, (tag, text)) for tag, text in library_body]
        library = self.write_ts("lib/find.ts", "findByKey", "items, wanted", library_body)
        plan = self.write_ts("plan/nodes.ts", "getNodeFromPlan", "planNodes, nodeId", other)
        env = self.xml_stub_env(library + plan)

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual([("getNodeFromPlan", "findByKey", 0)], self.pair_names(result))

    def test_one_changed_keyword_is_a_near_match_pair(self):
        other = [("keyword", "while") if index == 0 else entry for index, entry in enumerate(TS_PLACEHOLDER_BODY)]
        env = self.xml_stub_env(self.two_copies_xml(other))

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual([("getNodeFromPlan", "findByKey", 1)], self.pair_names(result))

    def test_a_domain_named_function_lists_the_helper_with_its_signature(self):
        other = [*TS_PLACEHOLDER_BODY[:-1], ("keyword", "const"), *TS_PLACEHOLDER_BODY[-1:]]
        env = self.xml_stub_env(self.two_copies_xml(other))

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual(1, len(result.listings))
        self.assertEqual("findByKey(items, wanted)", result.listings[0].neighbours[0][0].signature)

    def test_a_declaration_file_is_never_passed_to_tree_sitter(self):
        library = self.write_ts("lib/find.ts", "findByKey", "items, wanted", TS_PLACEHOLDER_BODY)
        self.write("lib/types.d.ts", "declare function typed(a: number): void;\n")
        env = self.xml_stub_env(library)

        self.shapes_with_env(env, "lib/find.ts")

        recorded = self.recorded_paths.read_text().split()
        self.assertEqual([str(self.root / "lib/find.ts")], recorded)

    def test_a_source_name_that_was_not_asked_for_is_a_note(self):
        self.write_ts("plan/nodes.ts", "getNodeFromPlan", "planNodes, nodeId", TS_PLACEHOLDER_BODY)
        env = self.xml_stub_env('<source name="/elsewhere/other.ts"></source>')

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual(1, len(result.notes))
        self.assertIn("unexpected source name '/elsewhere/other.ts'", result.notes[0])

    def test_xml_with_another_root_is_a_note_naming_the_root(self):
        self.write_ts("plan/nodes.ts", "getNodeFromPlan", "planNodes, nodeId", TS_PLACEHOLDER_BODY)
        env = self.stub_env("echo '<?xml version=\"1.0\"?><other/>'")

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual(1, len(result.notes))
        self.assertIn("root element is <other>", result.notes[0])

    def test_truncated_xml_is_a_note(self):
        self.write_ts("plan/nodes.ts", "getNodeFromPlan", "planNodes, nodeId", TS_PLACEHOLDER_BODY)
        env = self.stub_env("echo '<?xml version=\"1.0\"?><sources><source name=\"x\">'")

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual(1, len(result.notes))
        self.assertIn("tree-sitter output did not parse", result.notes[0])

    def test_a_run_that_times_out_is_a_did_not_run_note(self):
        self.write_ts("plan/nodes.ts", "getNodeFromPlan", "planNodes, nodeId", TS_PLACEHOLDER_BODY)
        env = self.stub_env("exec sleep 5")

        with mock.patch.object(tree_sitter_xml, "TREE_SITTER_TIMEOUT_SECONDS", 0.2):
            result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual(1, len(result.notes))
        self.assertIn("tree-sitter did not run: TimeoutExpired", result.notes[0])

    def test_a_cli_that_cannot_start_is_a_did_not_run_note(self):
        self.write_ts("plan/nodes.ts", "getNodeFromPlan", "planNodes, nodeId", TS_PLACEHOLDER_BODY)
        env = {tree_sitter_xml.TREE_SITTER_ENV: str(self.stub_dir / "missing-cli"),
               tree_sitter_xml.PARSER_DIR_ENV: str(self.stub_dir)}

        result = self.shapes_with_env(env, "plan/nodes.ts")

        self.assertEqual(1, len(result.notes))
        self.assertIn("tree-sitter did not run: FileNotFoundError", result.notes[0])


class TypeScriptNoteTest(ShapeRepoTestCase):
    def setUp(self):
        super().setUp()
        self.write("lib/find.ts", FIND_BY_KEY_TS)
        self.write("lib/find.py", FIND_BY_KEY_PY)
        self.write("plan/nodes.py", RENAMED_COPY_PY)

    def result_with_env(self, **env):
        with mock.patch.dict(os.environ, env):
            return self.shapes("plan/nodes.py")

    def test_a_missing_cli_is_a_note_and_python_still_compares(self):
        with mock.patch.object(tree_sitter_xml.shutil, "which", return_value=None), \
                mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(tree_sitter_xml.TREE_SITTER_ENV, None)
            result = self.shapes("plan/nodes.py")

        self.assertEqual(["TypeScript functions not read: tree-sitter CLI not found"], result.notes)
        self.assertEqual(1, len(result.pairs))

    def test_a_missing_grammar_is_a_note_naming_the_file(self):
        empty = self.root / "no-grammars"
        empty.mkdir()

        result = self.result_with_env(**{tree_sitter_xml.TREE_SITTER_ENV: "tree-sitter",
                                         tree_sitter_xml.PARSER_DIR_ENV: str(empty)})

        self.assertEqual(1, len(result.notes))
        self.assertIn(str(empty / "typescript.so"), result.notes[0])

    def test_output_that_is_not_xml_is_a_note_that_names_the_expected_form(self):
        stub = self.root / "stub-tree-sitter"
        stub.write_text("#!/bin/sh\necho 'not xml at all'\n")
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        grammars = self.root / "grammars"
        grammars.mkdir()
        (grammars / "typescript.so").write_text("")

        result = self.result_with_env(**{tree_sitter_xml.TREE_SITTER_ENV: str(stub),
                                         tree_sitter_xml.PARSER_DIR_ENV: str(grammars)})

        self.assertEqual(1, len(result.notes))
        self.assertIn("tree-sitter output did not parse", result.notes[0])
        self.assertIn("<sources>", result.notes[0])
        self.assertEqual(1, len(result.pairs))


if __name__ == "__main__":
    unittest.main()
