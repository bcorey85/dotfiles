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


class NoTypescriptTest(ReadabilityRepoTestCase):
    def test_a_typescript_file_with_no_typescript_package_is_skipped(self):
        self.write("src/app.ts", "export const sign = (n: number) => n > 0 ? 1 : n < 0 ? -1 : 0;\n")

        with mock.patch.object(readability_check, "find_typescript", return_value=None):
            records = readability_check.records_by_file([self.repo / "src/app.ts"])

        self.assertEqual({self.repo / "src/app.ts": None}, records)


if __name__ == "__main__":
    unittest.main()
