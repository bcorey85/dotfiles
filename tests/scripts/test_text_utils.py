"""Checks for text_utils.py: plain-text and file helpers that read no module table."""
import importlib.util
import os
import pathlib
import tempfile
import threading
import unittest

SCRIPT = pathlib.Path(os.environ.get("TEXT_UTILS_SCRIPT") or pathlib.Path.home() / ".claude" / "scripts" / "text_utils.py")
spec = importlib.util.spec_from_file_location("text_utils_under_test", str(SCRIPT))
text_utils = importlib.util.module_from_spec(spec)
spec.loader.exec_module(text_utils)


class TextUtilsTest(unittest.TestCase):
    def test_one_line_collapses_whitespace_and_cuts(self):
        self.assertEqual(text_utils.one_line("a \n  b\t c"), "a b c")
        self.assertEqual(text_utils.one_line("abcdef", 3), "abc")

    def test_unquote_strips_one_matching_pair_only(self):
        self.assertEqual(text_utils.unquote(' "x" '), "x")
        self.assertEqual(text_utils.unquote("'x'"), "x")
        self.assertEqual(text_utils.unquote("\"x'"), "\"x'")
        self.assertEqual(text_utils.unquote('""x""'), '"x"')

    def test_first_number(self):
        self.assertEqual(text_utils.first_number("2 of 3"), 2)
        self.assertIsNone(text_utils.first_number("two"))
        self.assertIsNone(text_utils.first_number(None))

    def test_unquoted_mask_blanks_quoted_spans(self):
        masked = text_utils.unquoted_mask('a: "b: c" d')
        self.assertNotIn("b: c", masked)
        self.assertEqual(len(masked), len('a: "b: c" d'))

    def test_top_level_braces_splits_flow_lists_and_ignores_quoted_braces(self):
        groups = text_utils.top_level_braces('{a: 1}, {b: {c: 2}}, {d: "}"}')
        self.assertEqual(groups, ["{a: 1}", "{b: {c: 2}}", '{d: "}"}'])

    def test_normalize_path_strips_ticks_dot_slash_and_line_suffix(self):
        self.assertEqual(text_utils.normalize_path("`./src/a.ts:12-20`"), "src/a.ts")
        self.assertEqual(text_utils.normalize_path("a.ts:1, b.ts:2"), "a.ts")
        self.assertEqual(text_utils.normalize_path("src/a.ts"), "src/a.ts")

    def test_split_location_returns_path_and_first_line(self):
        self.assertEqual(text_utils.split_location("a.ts:12-20, b.ts:3"), ("a.ts", 12))
        self.assertEqual(text_utils.split_location("a.ts"), ("a.ts", 0))
        self.assertEqual(text_utils.split_location("a.ts:x"), ("a.ts", 0))

    def test_paths_named_collects_the_first_path_and_every_path_line_token_once(self):
        paths = text_utils.paths_named("./a.ts:1", "see b.ts:2 and `c.ts:3-4` and a.ts:9", None)
        self.assertEqual(paths, ["a.ts", "b.ts", "c.ts"])

    def test_append_jsonl_and_read_jsonl_round_trip_and_skip_torn_lines(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name) / "deep" / "rows.jsonl"
        text_utils.append_jsonl(path, {"n": 1})
        text_utils.append_jsonl(path, {"n": 2})
        with open(str(path), "a") as handle:
            handle.write('{"torn": \n[1]\n')
        self.assertEqual(text_utils.read_jsonl(path), [{"n": 1}, {"n": 2}])
        self.assertEqual(text_utils.read_jsonl(path.parent / "missing.jsonl"), [])

    def test_concurrent_appends_never_interleave_inside_a_row(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = pathlib.Path(directory.name) / "rows.jsonl"
        threads = [threading.Thread(target=lambda n=n: [text_utils.append_jsonl(path, {"n": n, "pad": "x" * 500})
                                                        for _ in range(20)]) for n in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(text_utils.read_jsonl(path)), 160)


if __name__ == "__main__":
    unittest.main()
