"""Checks for source_text.py: reading unified diffs and the comment lines of source files as plain text.
SOURCE_TEXT_MODULE overrides the module path; it defaults to the installed one."""
import importlib.util
import os
import pathlib
import unittest

import toolkit_paths

MODULE = pathlib.Path(os.environ.get("SOURCE_TEXT_MODULE") or toolkit_paths.LIB_DIR / "source_text.py")
module_spec = importlib.util.spec_from_file_location("source_text", MODULE)
source_text = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(source_text)

DIFF = """diff --git a/src/a.ts b/src/a.ts
index 111..222 100644
--- src/a.ts
+++ src/a.ts
@@ -3 +3 @@ export function outer() {
-  return 1;
\\ No newline at end of file
+  return 2;
\\ No newline at end of file
@@ -10,2 +10,0 @@ class Box
--- a decrement line
-const gone = 1;
diff --git a/old.py b/old.py
deleted file mode 100644
--- old.py
+++ /dev/null
@@ -1 +0,0 @@
-def old(): pass
diff --git a/docs/my guide.md b/docs/my guide.md
--- docs/my guide.md\t
+++ docs/my guide.md\t
@@ -2 +2 @@
-old line
+new line
diff --git a/img.png b/img.png
Binary files a/img.png and b/img.png differ
"""


class ParseUnifiedDiffTest(unittest.TestCase):
    def test_hunks_carry_context_line_numbers_and_text(self):
        files = source_text.parse_unified_diff(DIFF)

        self.assertEqual(["src/a.ts", "old.py", "docs/my guide.md"], [file_diff.path for file_diff in files])
        first = files[0].hunks[0]
        self.assertEqual("export function outer() {", first.context)
        self.assertEqual([(3, "  return 1;")], first.removed)
        self.assertEqual([(3, "  return 2;")], first.added)
        self.assertEqual([(2, "old line")], files[2].hunks[0].removed)

    def test_a_removed_line_that_looks_like_a_file_header_stays_in_its_hunk(self):
        second = source_text.parse_unified_diff(DIFF)[0].hunks[1]

        self.assertEqual([(10, "-- a decrement line"), (11, "const gone = 1;")], second.removed)
        self.assertEqual("class Box", second.context)

    def test_deleted_file_is_named_by_its_old_path(self):
        deleted = source_text.parse_unified_diff(DIFF)[1]

        self.assertEqual([(1, "def old(): pass")], deleted.hunks[0].removed)

    def test_a_c_quoted_path_in_the_file_headers_is_decoded(self):
        diff = '--- "src/q\\"x.ts"\n+++ "src/q\\"x.ts"\n@@ -1 +1 @@\n-a\n+b\n'

        self.assertEqual(['src/q"x.ts'], [file_diff.path for file_diff in source_text.parse_unified_diff(diff)])

    def test_empty_diff_has_no_files(self):
        self.assertEqual([], source_text.parse_unified_diff(""))


class UnquoteCPathTest(unittest.TestCase):
    def test_decodes_the_escapes_git_writes(self):
        self.assertEqual('q"uote', source_text.unquote_c_path('"q\\"uote"'))
        self.assertEqual("café", source_text.unquote_c_path('"caf\\303\\251"'))

    def test_an_escape_git_does_not_write_raises(self):
        with self.assertRaises(ValueError):
            source_text.unquote_c_path('"bad\\qescape"')


class CommentLineNumbersTest(unittest.TestCase):
    def test_slash_style_counts_line_comments_and_block_comment_lines(self):
        lines = ["code();", "// one", "/**", " * two", " */", "more();", "/* three */", "x = 1 // trailing"]

        self.assertEqual({2, 3, 4, 5, 7}, source_text.comment_line_numbers(lines, "slash"))

    def test_hash_triple_counts_hash_lines_and_docstring_lines(self):
        lines = ['def f():', '    """Summary.', "", "    More.", '    """', "    # note", "    x = 1  # trailing",
                 '    y = """data', "more data", '"""']

        self.assertEqual({2, 3, 4, 5, 6, 9, 10}, source_text.comment_line_numbers(lines, "hash_triple"))

    def test_hash_triple_counts_a_one_line_docstring_but_not_the_code_line_after_it(self):
        lines = ['"""One line."""', "x = 1"]

        self.assertEqual({1}, source_text.comment_line_numbers(lines, "hash_triple"))

    def test_hash_style_ignores_triple_quotes(self):
        self.assertEqual({2}, source_text.comment_line_numbers(['"""', "# c", '"""'], "hash"))

    def test_unknown_style_raises(self):
        with self.assertRaises(ValueError):
            source_text.comment_line_numbers([], "lisp")


class StringDataLineNumbersTest(unittest.TestCase):
    def test_lines_after_an_assigned_triple_quote_are_data_but_a_docstring_is_not(self):
        lines = ['def f():', '    """Doc.', "    more", '    """', '    y = """', "data", '"""', "z = 1"]

        self.assertEqual({6}, source_text.string_data_regions(lines, "hash_triple")[0])
        self.assertEqual({7: ""}, source_text.string_data_regions(lines, "hash_triple")[1])

    def test_lines_after_an_opening_backtick_through_the_closing_one_are_data(self):
        lines = ["// a `tick", "const s = `", "## x", "`;", "f();"]

        self.assertEqual({3}, source_text.string_data_regions(lines, "slash")[0])
        self.assertEqual({4: ";"}, source_text.string_data_regions(lines, "slash")[1])

    def test_a_triple_quote_on_its_own_line_is_data_after_an_opening_bracket_comma_or_equals(self):
        for opener in ("plan = textwrap.dedent(", "PLANS = [", "x = {", "f(a,", "x ="):
            with self.subTest(opener=opener):
                lines = [opener, '    """## body', "## body", '""",', "]"]

                regions = source_text.string_data_regions(lines, "hash_triple")

                self.assertEqual({3}, regions.numbers)
                self.assertEqual({2: "    "}, regions.openings)

    def test_a_triple_quote_on_its_own_line_after_a_colon_or_at_module_top_is_a_docstring(self):
        for lines in (['def f():', '    """', "body", '    """'], ['"""', "body", '"""']):
            with self.subTest(lines=lines):
                self.assertEqual(set(), source_text.string_data_regions(lines, "hash_triple")[0])

    def test_a_prefixed_docstring_is_not_data(self):
        for prefix in ("r", "u", "b", "R"):
            with self.subTest(prefix=prefix):
                lines = ["def f():", f'    {prefix}"""Match x.', "    body", '    """']

                self.assertEqual(set(), source_text.string_data_regions(lines, "hash_triple")[0])

    def test_an_odd_backtick_inside_a_quoted_string_or_comment_does_not_open_a_template(self):
        for line in ('const fence = "```";', "const fence = '`';", "const x = 1; // a ` tick"):
            with self.subTest(line=line):
                self.assertEqual(set(), source_text.string_data_regions([line, "a", "b"], "slash")[0])

    def test_a_template_closes_at_the_first_unescaped_backtick_of_the_raw_line_even_with_a_slash_pair_before_it(self):
        lines = ["const h = `", "  <p>hi</p>", "  see https://x.com/docs`;", "// Phase 1: leak", "const y = 2;"]

        self.assertEqual(({2}, {3: ";"}, {1: "const h = "}), source_text.string_data_regions(lines, "slash"))

    def test_a_line_that_closes_one_template_and_opens_another_keeps_only_the_code_between_them(self):
        lines = ["const a = `", "x", "`; const b = `## Phase 1", "y", "`;"]

        regions = source_text.string_data_regions(lines, "slash")

        self.assertEqual(({2, 4}, {3: "; const b = ", 5: ";"}, {1: "const a = "}), regions)

    def test_an_escaped_backtick_inside_a_template_does_not_close_it(self):
        lines = ["const h = `", "  a \\` b", "  c`;", "const y = 2;"]

        self.assertEqual(({2}, {3: ";"}, {1: "const h = "}), source_text.string_data_regions(lines, "slash"))

    def test_a_block_comment_body_line_with_an_odd_backtick_does_not_open_a_template(self):
        lines = ["/*", "  uses a ` tick", "*/", "const y = 2;"]

        self.assertEqual((set(), {}, {}), source_text.string_data_regions(lines, "slash"))

    def test_an_apostrophe_inside_a_template_on_one_line_does_not_open_a_template(self):
        lines = ["warn(`can't find ${x}`, 'warn');", "// leftover note", "const y = 2;"]

        self.assertEqual((set(), {}, {}), source_text.string_data_regions(lines, "slash"))

    def test_a_backtick_in_a_trailing_block_comment_does_not_open_a_template(self):
        lines = ["foo(); /* it`s */", "// leftover note", "const y = 2;"]

        self.assertEqual((set(), {}, {}), source_text.string_data_regions(lines, "slash"))

    def test_a_triple_quote_inside_a_single_quoted_literal_does_not_open_a_string(self):
        lines = ["x = '\"\"\"'", "a", "b"]

        self.assertEqual(set(), source_text.string_data_regions(lines, "hash_triple")[0])

    def test_closing_tail_is_the_text_after_the_closing_quote(self):
        lines = ['X = """', "data", '"""  # Phase 2 leftover']

        self.assertEqual({2}, source_text.string_data_regions(lines, "hash_triple")[0])
        self.assertEqual({3: "  # Phase 2 leftover"}, source_text.string_data_regions(lines, "hash_triple")[1])

    def test_an_opening_line_is_listed_with_the_text_before_its_opening_quote(self):
        lines = [
            'PLAN = """## Phase 1', "more", '"""',
            "f(\"a\", '''x", "y", "'''",
            "const t = `a", "`",
            "f(`a`, `x", "`",
        ]

        python_openings = source_text.string_data_regions(lines[:6], "hash_triple").openings

        self.assertEqual({1: "PLAN = ", 4: 'f("a", '}, python_openings)
        self.assertEqual({1: "const t = "}, source_text.string_data_regions(lines[6:8], "slash").openings)
        self.assertEqual({1: "f(`a`, "}, source_text.string_data_regions(lines[8:], "slash").openings)

    def test_a_docstring_and_a_closed_string_are_not_openings(self):
        lines = ["def f():", '    """Doc.', "    more", '    """', 'x = """a"""', "tick = `a`"]

        self.assertEqual({}, source_text.string_data_regions(lines[:5], "hash_triple").openings)
        self.assertEqual({}, source_text.string_data_regions(lines[5:], "slash").openings)

    def test_other_styles_give_no_lines(self):
        self.assertEqual(set(), source_text.string_data_regions(['x = """', "a", '"""'], "hash")[0])


class CommentStyleOfTest(unittest.TestCase):
    def test_an_unknown_suffix_gives_none(self):
        for path in ("x.md", "Makefile"):
            with self.subTest(path=path):
                self.assertIsNone(source_text.comment_style_of(path))


class LiteralTest(unittest.TestCase):
    def test_literals_are_the_numbers_and_unquoted_strings_in_order(self):
        line = "const x2 = pick('a b', 3.5, \"q\") + 7"

        self.assertEqual(["a b", "3.5", "q", "7"], source_text.literals_of(line))

    def test_masking_makes_lines_that_differ_only_in_literals_equal(self):
        mask = source_text.mask_literals

        self.assertEqual(mask("export const A = 24"), mask("export const A = 4"))
        self.assertNotEqual(mask("const A = f(1)"), mask("const A = g(1)"))

    def test_string_text_is_removed_and_code_and_trailing_comment_stay(self):
        line = "plan = \"## Build\" + 'x'  # trailing note"

        self.assertEqual("plan = \"\" + ''  # trailing note", source_text.without_string_text(line))


if __name__ == "__main__":
    unittest.main()
