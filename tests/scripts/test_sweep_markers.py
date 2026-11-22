"""Checks for the /refactor sweep_markers.py module. SWEEP_MARKERS_PATH overrides the module path; it defaults to the
one in the tree these tests sit in."""
import importlib.util
import os
import pathlib
import sys
import types
import unittest

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("SWEEP_MARKERS_PATH")
                      or toolkit_paths.CLAUDE_DIR / "skills" / "refactor" / "scripts" / "sweep_markers.py")
sys.path.insert(0, str(toolkit_paths.LIB_DIR))
module_spec = importlib.util.spec_from_file_location("sweep_markers", MODULE)
sweep_markers = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(sweep_markers)


def pairs(lines):
    return list(enumerate(lines, 1))


class HasCliEntryPointTest(unittest.TestCase):
    def test_each_trigger_alone_counts_and_lookalikes_do_not(self):
        cases = [
            ("import argparse", True), ("from argparse import X", True), ("def main():", True),
            ("async def main():", True), ("if __name__ == '__main__':", True),
            ("def main_helper():", False), ("    def main(self):", False), ("    import argparse", False),
            ("  if __name__ == '__main__':", False),
        ]
        for line, expected in cases:
            with self.subTest(line=line):
                self.assertEqual(sweep_markers.has_cli_entry_point("a.py", line + "\n"), expected)

    def test_a_non_python_file_is_never_a_cli(self):
        self.assertFalse(sweep_markers.has_cli_entry_point("a.js", "import argparse\n"))


class SweepAddedLinesTest(unittest.TestCase):
    def sweep(self, lines, path="a.py"):
        return sweep_markers.sweep_added_lines(path, pairs(lines), lines)

    def test_a_cli_fixture_string_does_not_silence_print(self):
        lines = ['F = """', 'if __name__ == "__main__":', '"""', "print(x)"]
        self.assertEqual([hit[1] for hit in self.sweep(lines)], [4])

    def test_commented_out_code_inside_string_data_is_no_hit(self):
        lines = ['F = """', "# import os", '"""', "# import sys"]
        hits = self.sweep(lines)
        self.assertEqual([(hit[1], hit[2]) for hit in hits], [(4, "commented-out code")])

    def test_a_cli_file_keeps_todo_and_string_data_print_stays_quiet(self):
        lines = ["import argparse", "print('report')", "# TODO tidy", 'S = """', "print(x)", '"""']
        self.assertEqual([hit[1] for hit in self.sweep(lines)], [3])

    def test_a_marker_between_apostrophes_in_prose_or_comment_text_is_a_hit(self):
        cases = [
            ("a.md", ["Don't ship this, TODO: it's broken"]),
            ("a.txt", ["It's a TODO list, don't"]),
            ("a.c", ["/* it's a TODO, isn't it */"]),
            ("b.js", ["/**", " * It's a TODO, isn't it", " */"]),
            ("b.py", ['"""', "It's a TODO, isn't it.", '"""']),
            ("c.py", ["x = 1  # it's a TODO, isn't it"]),
        ]
        for path, lines in cases:
            with self.subTest(path=path):
                hits = self.sweep(lines, path=path)
                self.assertEqual([hit[2] for hit in hits], ["marker"])

    def test_a_marker_between_apostrophes_is_a_hit_with_no_post_image(self):
        hits = sweep_markers.sweep_added_lines("a.md", [(1, "It's a TODO, isn't it")], None)
        self.assertEqual([hit[2] for hit in hits], ["marker"])

    def test_a_string_literal_is_no_hit_and_a_bare_print_is(self):
        self.assertEqual(self.sweep(['x = "print(1)"']), [])
        self.assertEqual([hit[1] for hit in self.sweep(["print(1)"])], [1])

    def test_a_closing_tail_string_holding_a_marker_is_no_hit(self):
        for tail in ('""", "TODO later")', '""", "print(1)")'):
            with self.subTest(tail=tail):
                self.assertEqual(self.sweep(['X = f("""', "body", tail]), [])

    def test_a_crlf_post_image_line_matches_a_diff_line_without_the_carriage_return(self):
        hits = sweep_markers.sweep_added_lines("a.py", [(1, "# TODO x")], ["# TODO x\r"])
        self.assertEqual([hit[2] for hit in hits], ["marker"])

    def test_a_diff_line_with_a_carriage_return_matches_a_post_image_without_it(self):
        self.assertEqual(sweep_markers.sweep_added_lines("a.py", [(1, "x\r")], ["x"]), [])

    def test_a_post_image_that_differs_from_the_diff_raises(self):
        with self.assertRaises(sweep_markers.PostImageMismatchError):
            sweep_markers.sweep_added_lines("a.py", [(1, "x = 1")], ["y = 2"])

    def test_a_line_past_the_post_image_raises(self):
        with self.assertRaises(sweep_markers.PostImageMismatchError):
            sweep_markers.sweep_added_lines("a.py", [(3, "x = 1")], ["x = 1"])

    def test_no_post_image_judges_each_added_line_alone(self):
        hits = sweep_markers.sweep_added_lines("link", [(1, "TODO-target")], None)
        self.assertEqual(hits, [("link", 1, "marker", "TODO-target")])

    def test_a_comment_with_apostrophes_is_a_hit_for_a_styled_path_with_no_post_image(self):
        hits = sweep_markers.sweep_added_lines("a.py", [(1, "# it's a TODO, isn't it")], None)
        self.assertEqual([hit[2] for hit in hits], ["marker"])

    def test_a_block_comment_or_docstring_with_apostrophes_is_a_hit_with_no_post_image(self):
        cases = [
            ("a.js", "/* it's a TODO, isn't it */"),
            ("a.py", '"""it\'s a TODO, isn\'t it"""'),
        ]
        for path, text in cases:
            with self.subTest(path=path):
                hits = sweep_markers.sweep_added_lines(path, [(1, text)], None)
                self.assertEqual(hits, [(path, 1, "marker", text)])

    def test_a_marker_in_a_string_is_no_hit_for_a_styled_path_with_no_post_image(self):
        self.assertEqual(sweep_markers.sweep_added_lines("a.py", [(1, 'x = "TODO"')], None), [])


class HasSweepCandidateTest(unittest.TestCase):
    def test_only_a_line_that_could_be_a_hit_is_a_candidate(self):
        cases = [(["x = 1", "y = 2"], False), (["x = 1  # TODO"], True), (["# import os"], True),
                 (['"""  # import os'], True)]
        for lines, expected in cases:
            with self.subTest(lines=lines):
                self.assertEqual(sweep_markers.has_sweep_candidate(pairs(lines)), expected)


def diff_file(path, added):
    return types.SimpleNamespace(path=path, hunks=[types.SimpleNamespace(added=added)])


class SweepMatchesTest(unittest.TestCase):
    def test_a_file_with_no_candidate_is_never_read(self):
        def read_post_image(_path):
            raise AssertionError("the post-image of a candidate-free file was read")
        self.assertEqual(sweep_markers.sweep_matches([diff_file("a.py", pairs(["x = 1"]))], read_post_image), [])

    def test_no_post_image_judges_each_line_alone(self):
        hits = sweep_markers.sweep_matches([diff_file("link", pairs(["TODO-target"]))], lambda _path: None)
        self.assertEqual(hits, [("link", 1, "marker", "TODO-target")])

    def test_a_closing_tail_comment_is_reported_with_or_without_another_candidate(self):
        lines = ['X = """', "data", '"""  # import os', "# TODO later"]
        only_tail = [diff_file("a.py", [(3, lines[2])])]
        with_todo = [diff_file("a.py", [(3, lines[2]), (4, lines[3])])]
        kinds_alone = [hit[2] for hit in sweep_markers.sweep_matches(only_tail, lambda _path: lines)]
        kinds_with_todo = [hit[2] for hit in sweep_markers.sweep_matches(with_todo, lambda _path: lines)
                           if hit[1] == 3]
        self.assertEqual(kinds_alone, ["commented-out code"])
        self.assertEqual(kinds_with_todo, ["commented-out code"])


class UntrackedMatchesTest(unittest.TestCase):
    def test_every_line_is_added_and_string_data_is_skipped(self):
        entry = types.SimpleNamespace(path="u.py", added_lines=pairs(['S = """', "TODO", '"""', "# TODO real"]))
        hits = sweep_markers.untracked_matches([entry])
        self.assertEqual([(hit[1], hit[2]) for hit in hits], [(4, "marker")])


if __name__ == "__main__":
    unittest.main()
