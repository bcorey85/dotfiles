"""Checks for readability_check.py, which lists the functions a change wrote that break the coder's readability limits.
READABILITY_CHECK_SCRIPT overrides the script path. The TS checks need a typescript package: READABILITY_TYPESCRIPT
names one, else the global one is used, else they skip."""
import importlib.util
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("READABILITY_CHECK_SCRIPT") or toolkit_paths.CODE_DIR / "readability_check.py")
module_spec = importlib.util.spec_from_file_location("readability_check", SCRIPT)
readability_check = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(readability_check)

GIT_IDENTITY = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com", "GIT_COMMITTER_NAME": "t",
                "GIT_COMMITTER_EMAIL": "t@example.com"}
NESTED_PY = ("def handle(a, b, c):\n    if a:\n        if b:\n            if c:\n                return 1\n"
             "    return 0\n")
ELSE_IF_PY = ("def pick(a):\n    if a == 1:\n        return 1\n    elif a == 2:\n        if a:\n            return 2\n"
              "    elif a == 3:\n        return 3\n    return 0\n")
TERNARY_PY = "def sign(n):\n    return 1 if n > 0 else -1 if n < 0 else 0\n"
DEEP_PY = "def total(rows):\n    return print(sum(len(rows)))\n"
FLAT_PY = "def total(rows):\n    count = len(rows)\n    return sum([count])\n"


def long_python_function(name, body_lines):
    return f"def {name}():\n" + "".join(f"    x{index} = {index}\n" for index in range(body_lines))


def typescript_dir():
    named = os.environ.get("READABILITY_TYPESCRIPT")
    if named:
        return pathlib.Path(named)
    root = readability_check.global_node_root()
    candidate = root / "typescript" if root else None
    return candidate if candidate and readability_check.usable_typescript(candidate) else None


class ReadabilityRepoTestCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name)
        self.env = {**os.environ, **GIT_IDENTITY}
        self.git("init", "-q")
        self.git("commit", "-q", "--allow-empty", "-m", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        done = subprocess.run(["git", *args], cwd=self.repo, env=self.env, capture_output=True, text=True, check=True)
        return done.stdout

    def write(self, name, text):
        file = self.repo / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text)

    def commit(self, message="change"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        self.base = self.git("rev-parse", "HEAD").strip()

    def run_check(self, base=None):
        return subprocess.run([sys.executable, str(SCRIPT), "--base", base or self.base], cwd=self.repo, env=self.env,
                              capture_output=True, text=True, check=False)


class PythonLimitTest(ReadabilityRepoTestCase):
    def test_control_flow_three_levels_deep_is_a_hit_on_its_line(self):
        self.write("app.py", NESTED_PY)

        done = self.run_check()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("app.py:4 handle — nesting (3 levels, limit 2)", done.stdout)
        self.assertIn(readability_check.NESTING_FIX, done.stdout)

    def test_an_else_if_stays_at_its_if_level(self):
        self.write("app.py", ELSE_IF_PY)

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_nested_function_counts_its_nesting_from_zero(self):
        self.write("app.py", "def outer(a):\n    if a:\n        def inner(b):\n            if b:\n"
                             "                if b > 1:\n                    return 2\n        return inner\n")

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_chained_ternary_is_a_hit(self):
        self.write("app.py", TERNARY_PY)

        done = self.run_check()

        self.assertEqual(1, done.returncode)
        self.assertIn("app.py:2 sign — chained ternary", done.stdout)

    def test_a_call_result_passed_into_a_call_that_is_an_argument_is_a_hit(self):
        self.write("app.py", DEEP_PY)

        done = self.run_check()

        self.assertEqual(1, done.returncode)
        self.assertIn("app.py:2 total — deep call", done.stdout)

    def test_one_level_of_call_in_call_is_no_hit(self):
        self.write("app.py", FLAT_PY)

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_new_function_over_forty_lines_is_a_hit(self):
        self.write("app.py", long_python_function("build", 45))

        done = self.run_check()

        self.assertEqual(1, done.returncode)
        self.assertIn("app.py:1 build — length (46 lines, limit 40)", done.stdout)

    def test_a_small_edit_to_a_legacy_long_function_is_no_hit(self):
        self.write("app.py", long_python_function("build", 60))
        self.commit()
        text = (self.repo / "app.py").read_text().replace("x3 = 3", "x3 = 33")
        self.write("app.py", text)

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_an_edit_that_takes_a_function_past_the_limit_is_a_hit(self):
        self.write("app.py", long_python_function("build", 38))
        self.commit()
        self.write("app.py", long_python_function("build", 44))

        done = self.run_check()

        self.assertEqual(1, done.returncode)
        self.assertIn("build — length", done.stdout)

    def test_legacy_nesting_the_change_did_not_touch_is_no_hit(self):
        self.write("app.py", NESTED_PY)
        self.commit()
        self.write("app.py", NESTED_PY + "\n\ndef added():\n    return 1\n")

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_tracked_file_edit_is_read_from_the_diff(self):
        self.write("app.py", "def handle(a, b, c):\n    return 0\n")
        self.commit()
        self.write("app.py", NESTED_PY)

        done = self.run_check()

        self.assertEqual(1, done.returncode)
        self.assertIn("app.py:4 handle — nesting", done.stdout)

    def test_test_files_are_left_out(self):
        self.write("tests/test_app.py", NESTED_PY)
        self.write("app_test.py", NESTED_PY)

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_file_that_does_not_parse_is_skipped(self):
        self.write("app.py", "def broken(:\n    if a:\n")

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_base_git_cannot_read_fails_open_with_a_note(self):
        self.write("app.py", NESTED_PY)

        done = self.run_check(base="no-such-rev")

        self.assertEqual((0, ""), (done.returncode, done.stdout))
        self.assertIn("readability_check: skipped", done.stderr)

    def test_the_report_shows_at_most_ten_hit_lines(self):
        functions = "".join(f"def f{index}(n):\n    return 1 if n else 2 if n else 3\n\n" for index in range(13))
        self.write("app.py", functions)

        done = self.run_check()

        hit_lines = [line for line in done.stdout.splitlines() if line.startswith("app.py:")]
        self.assertEqual(1, done.returncode)
        self.assertEqual(readability_check.MAX_HIT_LINES, len(hit_lines))
        self.assertIn("... and 3 more", done.stdout)


class PythonNewLimitTest(ReadabilityRepoTestCase):
    def assert_one_hit(self, text, expected):
        self.write("app.py", text)

        done = self.run_check()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn(expected, done.stdout)

    def assert_no_hit(self, text):
        self.write("app.py", text)

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_ternary_passed_as_a_call_argument_is_a_hit(self):
        self.assert_one_hit("def show(n):\n    print(1 if n else 2)\n",
                            f"app.py:2 show — ternary as a call argument: {readability_check.ARGUMENT_TERNARY_FIX}")

    def test_a_ternary_passed_as_a_keyword_argument_is_a_hit(self):
        self.assert_one_hit("def show(n):\n    print(n, end='' if n else '\\n')\n",
                            "app.py:2 show — ternary as a call argument")

    def test_a_ternary_assigned_first_is_no_hit(self):
        self.assert_no_hit("def show(n):\n    value = 1 if n else 2\n    print(value)\n")

    def test_a_comprehension_with_two_loops_is_a_hit(self):
        self.assert_one_hit("def pairs(rows):\n    return [cell for row in rows for cell in row]\n",
                            f"app.py:2 pairs — comprehension with two loops or a nested comprehension: "
                            f"{readability_check.COMPREHENSION_FIX}")

    def test_a_comprehension_inside_another_is_a_hit(self):
        self.assert_one_hit("def grid(rows):\n    return [[cell for cell in row] for row in rows]\n",
                            "app.py:2 grid — comprehension with two loops")

    def test_a_one_loop_comprehension_is_no_hit(self):
        self.assert_no_hit("def names(rows):\n    return {row.name for row in rows if row}\n")

    def test_a_returned_tuple_of_three_values_is_a_hit(self):
        self.assert_one_hit("def split(text):\n    return text, len(text), text.upper()\n",
                            f"app.py:2 split — tuple return (3 values): {readability_check.WIDE_TUPLE_FIX}")

    def test_a_returned_pair_is_no_hit(self):
        self.assert_no_hit("def split(text):\n    return text, len(text)\n")

    def test_a_function_with_six_parameters_is_a_hit_on_its_def_line(self):
        self.assert_one_hit("def build(a, b, c, d, e, f):\n    return a\n",
                            f"app.py:1 build — parameters (6, limit 5): {readability_check.PARAMETERS_FIX}")

    def test_star_parameters_count_and_self_does_not(self):
        self.assert_one_hit("class Shop:\n    def buy(self, a, b, c, d, *rest, **options):\n        return a\n",
                            "app.py:2 buy — parameters (6, limit 5)")

    def test_a_method_with_five_parameters_besides_self_is_no_hit(self):
        self.assert_no_hit("class Shop:\n    def buy(self, a, b, c, d, e):\n        return a\n")

    def test_a_function_named_test_is_left_out_of_the_parameter_limit(self):
        self.assert_no_hit("def test_build(a, b, c, d, e, f):\n    return a\n")

    def test_a_wide_function_whose_def_line_the_change_did_not_write_is_no_hit(self):
        self.write("app.py", "def build(a, b, c, d, e, f):\n    return a\n")
        self.commit()
        self.write("app.py", "def build(a, b, c, d, e, f):\n    return b\n")

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))


class DiffParsingTest(unittest.TestCase):
    def test_added_lines_come_from_each_hunk_of_each_file(self):
        diff_text = ("diff --git a.py a.py\n--- a.py\n+++ a.py\n@@ -1,0 +2,3 @@\n+x\n+y\n+z\n"
                     "@@ -9 +12 @@\n-old\n+new\n@@ -20,2 +23,0 @@\n-gone\n-gone\n")

        added = readability_check.diff_added_lines(diff_text)

        self.assertEqual({"a.py": {2, 3, 4, 12}}, added)


@unittest.skipIf(typescript_dir() is None, "no typescript package: set READABILITY_TYPESCRIPT")
class TypescriptLimitTest(ReadabilityRepoTestCase):
    def setUp(self):
        super().setUp()
        (self.repo / "node_modules").mkdir()
        (self.repo / "node_modules" / "typescript").symlink_to(typescript_dir())
        self.write(".gitignore", "node_modules\n")
        self.commit("ignore")

    def test_each_limit_is_a_hit_in_typescript(self):
        body = "".join(f"  const x{index} = {index};\n" for index in range(42))
        self.write("src/app.ts", (
            "export function handle(a: number, b: number, c: number) {\n  if (a) {\n    if (b) {\n      if (c) {\n"
            "        return 1;\n      }\n    }\n  }\n  return 0;\n}\n"
            "export const sign = (n: number) => n > 0 ? 1 : n < 0 ? -1 : 0;\n"
            "export function total(rows: string[]) {\n  return String(Math.abs(Number(rows.length)));\n}\n"
            f"export function build() {{\n{body}}}\n"))

        done = self.run_check()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("src/app.ts:4 handle — nesting (3 levels, limit 2)", done.stdout)
        self.assertIn("src/app.ts:11 sign — chained ternary", done.stdout)
        self.assertIn("src/app.ts:13 total — deep call", done.stdout)
        self.assertIn("src/app.ts:15 build — length (44 lines, limit 40)", done.stdout)

    def test_an_else_if_stays_at_its_if_level_in_typescript(self):
        self.write("src/app.ts", "export function pick(a: number) {\n  if (a === 1) {\n    return 1;\n"
                                 "  } else if (a === 2) {\n    if (a) {\n      return 2;\n    }\n  }\n  return 0;\n}\n")

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_typescript_test_file_and_a_file_that_does_not_parse_are_skipped(self):
        self.write("src/app.test.ts", "export const sign = (n: number) => n > 0 ? 1 : n < 0 ? -1 : 0;\n")
        self.write("src/broken.ts", "export function (\n")

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_each_new_limit_is_a_hit_in_typescript(self):
        self.write("src/app.ts", (
            "export function show(n: number) {\n  console.log(n ? 1 : 2);\n}\n"
            "export function split(text: string) {\n  return [text, text.length, text.toUpperCase()];\n}\n"
            "export function build(a: number, b: number, c: number, d: number, e: number, f: number) {\n"
            "  return a;\n}\n"))

        done = self.run_check()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("src/app.ts:2 show — ternary as a call argument", done.stdout)
        self.assertIn("src/app.ts:5 split — tuple return (3 values)", done.stdout)
        self.assertIn("src/app.ts:7 build — parameters (6, limit 5)", done.stdout)

    def test_typescript_near_misses_of_the_new_limits_are_no_hit(self):
        self.write("src/app.ts", (
            "export function show(n: number) {\n  const value = n ? 1 : 2;\n  console.log(value);\n}\n"
            "export function list(text: string): string[] {\n  return [text, text, text];\n}\n"
            "export function build(this: Window, { a, b, c, d, e, f }: Options, g: number) {\n  return a;\n}\n"
            "interface Options { a: number; b: number; c: number; d: number; e: number; f: number }\n"))

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))

    def test_a_vue_script_block_hit_reports_the_vue_file_line(self):
        self.write("src/Card.vue", (
            "<template>\n  <div>{{ a ? b ? 1 : 2 : 3 }}</div>\n</template>\n\n"
            "<script>\nexport default {\n  methods: {\n    sign(n) {\n      return n > 0 ? 1 : n < 0 ? -1 : 0;\n"
            "    },\n  },\n};\n</script>\n"))

        done = self.run_check()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("src/Card.vue:9 sign — chained ternary", done.stdout)
        self.assertNotIn("Card.vue:2", done.stdout)

    def test_a_vue_script_setup_lang_ts_block_is_read_as_typescript(self):
        self.write("src/Card.vue", (
            "<script setup lang=\"ts\">\nconst props = defineProps<{ n: number }>();\n"
            "function show(n: number): void {\n  console.log(n ? 1 : 2);\n}\n</script>\n\n"
            "<template>\n  <div>{{ props.n }}</div>\n</template>\n"))

        done = self.run_check()

        self.assertEqual(1, done.returncode, done.stderr)
        self.assertIn("src/Card.vue:4 show — ternary as a call argument", done.stdout)

    def test_a_vue_file_with_no_script_block_is_skipped(self):
        self.write("src/Card.vue", "<template>\n  <div>{{ a ? b ? 1 : 2 : 3 }}</div>\n</template>\n")

        done = self.run_check()

        self.assertEqual((0, ""), (done.returncode, done.stdout))


class NoTypescriptTest(ReadabilityRepoTestCase):
    def test_a_typescript_file_with_no_typescript_package_is_skipped(self):
        self.write("src/app.ts", "export const sign = (n: number) => n > 0 ? 1 : n < 0 ? -1 : 0;\n")

        with mock.patch.object(readability_check, "find_typescript", return_value=None):
            records = readability_check.records_by_file([self.repo / "src/app.ts"])

        self.assertEqual({self.repo / "src/app.ts": None}, records)


if __name__ == "__main__":
    unittest.main()
