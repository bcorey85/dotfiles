"""Checks for tests/lint.sh, the one lint entry point: a file named on its command line gets the same complexity gate
that the full suite applies."""
import pathlib
import re
import shutil
import subprocess
import tempfile
import unittest

from toolkit_paths import TREE_CLAUDE_DIR

REPO_ROOT = TREE_CLAUDE_DIR.parents[1]
LINT_SH = REPO_ROOT / "tests" / "lint.sh"
RUFF_TOML = REPO_ROOT / "ruff.toml"
GATED_PATH = "claude/.claude/scripts/code/plan_check.py"
SUFFIXLESS_PATHS = ("claude/.claude/scripts/review/verify-log", "claude/.claude/scripts/review/verify-prep")
UNGATED_PATH = "claude/.claude/scripts/tools/some_tool.py"
# Eleven branches: complexity 12, past the limit of 10 in ruff.toml, and clean under every other rule.
COMPLEX_FUNCTION = "def classify(value):\n" + "".join(
    f"    if value == {number}:\n        return {number}\n" for number in range(11)) + "    return -1\n"


def last_line(output):
    return [line for line in output.splitlines() if line.strip()][-1]


@unittest.skipUnless(shutil.which("ruff"), "ruff is not installed")
class LintScriptTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tree = pathlib.Path(tmp.name)
        (self.tree / "tests").mkdir()
        shutil.copy(LINT_SH, self.tree / "tests" / "lint.sh")
        shutil.copy(RUFF_TOML, self.tree / "ruff.toml")

    def lint(self, *given_files, cwd=None, merged_output=False):
        stderr_target = subprocess.STDOUT if merged_output else subprocess.PIPE
        return subprocess.run(["bash", str(self.tree / "tests" / "lint.sh"), *given_files],
                              cwd=cwd or self.tree, stdout=subprocess.PIPE, stderr=stderr_target, text=True,
                              timeout=60)

    def write_complex_function(self, relative_path):
        script = self.tree / relative_path
        script.parent.mkdir(parents=True, exist_ok=True)
        script.write_text(COMPLEX_FUNCTION)

    def test_a_gated_file_past_the_complexity_limit_fails_the_lint_of_that_file(self):
        self.write_complex_function(GATED_PATH)

        finished = self.lint(GATED_PATH)

        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("C901", finished.stdout)

    def test_the_same_function_in_a_file_outside_the_gated_lists_passes(self):
        self.write_complex_function(UNGATED_PATH)

        finished = self.lint(UNGATED_PATH)

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)

    def test_a_file_that_is_not_python_is_skipped(self):
        (self.tree / "notes.pyi").write_text("def broken(:\n")

        finished = self.lint("notes.pyi")

        self.assertEqual(finished.returncode, 0, finished.stdout + finished.stderr)

    def test_a_relative_argument_resolves_against_the_callers_folder(self):
        self.write_complex_function(GATED_PATH)

        finished = self.lint("plan_check.py", cwd=(self.tree / GATED_PATH).parent)

        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("C901", finished.stdout)

    def test_an_absolute_argument_is_gated(self):
        self.write_complex_function(GATED_PATH)

        finished = self.lint(str(self.tree / GATED_PATH))

        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("C901", finished.stdout)

    def test_the_ruff_rules_apply_to_a_file_outside_the_gated_lists(self):
        script = self.tree / UNGATED_PATH
        script.parent.mkdir(parents=True)
        script.write_text("import os\n")

        finished = self.lint(UNGATED_PATH)

        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("F401", finished.stdout)

    def test_a_script_without_a_py_suffix_that_the_full_lint_checks_is_linted(self):
        for suffixless_path in SUFFIXLESS_PATHS:
            with self.subTest(suffixless_path=suffixless_path):
                script = self.tree / suffixless_path
                script.parent.mkdir(parents=True, exist_ok=True)
                script.write_text("import os\n")

                finished = self.lint(suffixless_path)

                self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
                self.assertIn("F401", finished.stdout)

    def prepare_full_lint_tree(self):
        for gated_path in re.findall(r"claude/\.claude/scripts/\S+?\.py", LINT_SH.read_text()):
            gated_file = self.tree / gated_path
            gated_file.parent.mkdir(parents=True, exist_ok=True)
            gated_file.write_text("")
        (self.tree / "claude" / ".claude" / "skills").mkdir(parents=True)
        (self.tree / "scripts" / ".local" / "lib").mkdir(parents=True)
        (self.tree / "tests" / "scripts").mkdir()
        (self.tree / "tests" / "duplicate_code.py").write_text("")

    def test_no_argument_runs_the_whole_lint_with_the_complexity_gate(self):
        self.prepare_full_lint_tree()
        self.write_complex_function(GATED_PATH)

        finished = self.lint()

        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("C901", finished.stdout)

    def test_no_argument_runs_the_whole_lint_with_the_ruff_rules(self):
        self.prepare_full_lint_tree()
        (self.tree / "tests" / "scripts" / "unused_import.py").write_text("import os\n")

        finished = self.lint()

        self.assertEqual(finished.returncode, 1, finished.stdout + finished.stderr)
        self.assertIn("F401", finished.stdout)

    def assert_last_line_names_one_ruff_error(self, finished):
        output = finished.stdout
        self.assertEqual(finished.returncode, 1, output)
        self.assertEqual(last_line(output), "lint failed: ruff rules (1 error)", output)

    def test_a_failing_given_files_run_ends_with_a_line_naming_the_failed_step(self):
        script = self.tree / UNGATED_PATH
        script.parent.mkdir(parents=True)
        script.write_text("import os\n")

        finished = self.lint(UNGATED_PATH, merged_output=True)

        self.assert_last_line_names_one_ruff_error(finished)

    def test_a_ruff_run_that_fails_without_an_error_count_says_so_on_the_last_line(self):
        script = self.tree / UNGATED_PATH
        script.parent.mkdir(parents=True)
        script.write_text("x = 1\n")
        (self.tree / "ruff.toml").write_text("this is [not valid toml\n")

        finished = self.lint(UNGATED_PATH, merged_output=True)

        self.assertEqual(finished.returncode, 1, finished.stdout)
        self.assertEqual(last_line(finished.stdout), "lint failed: ruff rules (failed, no error count)",
                         finished.stdout)

    def test_a_complexity_report_that_cannot_run_claims_no_count(self):
        self.prepare_full_lint_tree()
        (self.tree / "ruff.toml").write_text("this is [not valid toml\n")

        finished = self.lint(merged_output=True)

        self.assertIn("complexity report could not run (ruff exit 2): not a failure", finished.stdout)
        self.assertNotIn("over the limit", finished.stdout)

    def test_a_failing_full_run_ends_with_a_line_naming_the_failed_step(self):
        self.prepare_full_lint_tree()
        (self.tree / "tests" / "scripts" / "unused_import.py").write_text("import os\n")
        self.write_complex_function(UNGATED_PATH)

        finished = self.lint(merged_output=True)

        self.assert_last_line_names_one_ruff_error(finished)
        # The only summary line is the ruff rules step's own; the complexity report adds none.
        summary_lines = re.findall(r"^Found \d+ errors?", finished.stdout, re.MULTILINE)
        self.assertEqual(len(summary_lines), 1, finished.stdout)
        self.assertIn("complexity report only (1 function over the limit): not a failure", finished.stdout)

    def test_a_failing_run_names_every_failed_step_with_its_error_count(self):
        self.prepare_full_lint_tree()
        self.write_complex_function(GATED_PATH)
        (self.tree / "tests" / "scripts" / "unused_import.py").write_text("import os\nimport sys\n")

        finished = self.lint(merged_output=True)

        self.assertEqual(last_line(finished.stdout),
                         "lint failed: ruff rules (2 errors), complexity gate (1 error)", finished.stdout)


if __name__ == "__main__":
    unittest.main()
