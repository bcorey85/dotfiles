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


class LiteralTest(unittest.TestCase):
    def test_literals_are_the_numbers_and_unquoted_strings_in_order(self):
        line = "const x2 = pick('a b', 3.5, \"q\") + 7"

        self.assertEqual(["a b", "3.5", "q", "7"], source_text.literals_of(line))

    def test_masking_makes_lines_that_differ_only_in_literals_equal(self):
        mask = source_text.mask_literals

        self.assertEqual(mask("export const A = 24"), mask("export const A = 4"))
        self.assertNotEqual(mask("const A = f(1)"), mask("const A = g(1)"))


if __name__ == "__main__":
    unittest.main()
