"""Checks for full_check.py, the review loop's full check under a time limit.

Set FULL_CHECK_SCRIPT to run against another copy, such as a staged one."""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("FULL_CHECK_SCRIPT") or toolkit_paths.REVIEW_DIR / "full_check.py")
sys.path.insert(0, str(SCRIPT.parent))
import full_check  # noqa: E402

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import linked_installs  # noqa: E402

# A command that prints a test runner's own summary line.
PASSING_SUITE = "echo '3 passed in 0.1s'"


class FullCheckTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name)
        self.log = self.repo / "review-gate.log"

    def check(self, command, claude_md=None, timeout=None, env=None):
        if claude_md is not None:
            (self.repo / "CLAUDE.md").write_text(claude_md)
        argv = [sys.executable, "-B", str(SCRIPT), str(self.repo), "--log", str(self.log)]
        if timeout is not None:
            argv += ["--timeout", str(timeout)]
        return subprocess.run([*argv, "--", command], capture_output=True, text=True, timeout=60, env=env)

    def pyenv_root_with_a_python3_shim(self):
        pyenv_root = self.repo / "pyenv-root"
        shim = pyenv_root / "shims" / "python3"
        shim.parent.mkdir(parents=True)
        shim.write_text("#!/bin/sh\necho pinned python3\n")
        shim.chmod(0o755)
        return pyenv_root

    def test_a_repo_with_a_python_version_file_runs_python3_through_the_pyenv_shims(self):
        (self.repo / ".python-version").write_text("3.12.4\n")
        pyenv_root = self.pyenv_root_with_a_python3_shim()

        completed = self.check("python3", env={**os.environ, "PYENV_ROOT": str(pyenv_root)})

        self.assertEqual(completed.stdout.splitlines()[0], "full check: unverified (exit 0, no runner summary)",
                         completed.stdout)
        self.assertEqual(self.log.read_text(), "pinned python3\n")

    def test_a_repo_with_no_python_version_file_keeps_the_path_as_it_is(self):
        pyenv_root = self.pyenv_root_with_a_python3_shim()

        self.check("command -v python3", env={**os.environ, "PYENV_ROOT": str(pyenv_root)})

        self.assertNotIn(str(pyenv_root), self.log.read_text())

    def missing_module_check(self, module):
        return self.check(f"echo \"ModuleNotFoundError: No module named '{module}'\"; exit 1")

    def test_a_missing_declared_module_is_an_environment_gap_not_a_failure(self):
        (self.repo / "requirements-dev.txt").write_text("# dev tools\n-r requirements.txt\nruff==0.6.9\n")

        completed = self.missing_module_check("ruff")

        self.assertEqual(completed.returncode, 0, completed.stdout)
        self.assertEqual(completed.stdout.splitlines()[0],
                         "full check: not run (environment gap: No module named 'ruff')")

    def test_a_missing_declared_module_is_reported_ahead_of_a_setup_fault_marker(self):
        (self.repo / "requirements-dev.txt").write_text("ruff==0.6.9\n")

        completed = self.check("echo \"ModuleNotFoundError: No module named 'ruff'\"; "
                               "echo ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND; exit 1")

        self.assertEqual(completed.stdout.splitlines()[0],
                         "full check: not run (environment gap: No module named 'ruff')")

    def test_a_missing_undeclared_module_is_a_failure(self):
        (self.repo / "requirements.txt").write_text("flask>=3\n")

        completed = self.missing_module_check("requests")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 1)")

    def test_each_dependency_file_shape_declares_its_modules_by_normalized_name(self):
        dependency_files = {
            "pyproject.toml": ('[project]\ndependencies = ["Typing_Extensions>=4"]\n'
                               '[project.optional-dependencies]\ndev = ["pytest-cov"]\n'
                               '[dependency-groups]\nlint = ["mypy", {include-group = "test"}]\n'
                               '[tool.poetry.group.docs.dependencies]\nsphinx = "^7"\n'),
            "setup.cfg": "[options]\ninstall_requires =\n    attrs>=23\n[options.extras_require]\nyaml = PyYAML\n",
            "Pipfile": '[packages]\nrich = "*"\n[dev-packages]\nblack = "*"\n',
        }
        for name, text in dependency_files.items():
            (self.repo / name).write_text(text)

        for module in ("typing_extensions", "pytest_cov", "mypy", "sphinx.ext", "attrs", "yaml", "rich", "black"):
            with self.subTest(module=module):
                completed = self.missing_module_check(module)

                expected = "full check: not run" if module != "yaml" else "full check: failed"
                self.assertTrue(completed.stdout.startswith(expected), completed.stdout)

    def test_a_missing_module_of_the_repo_itself_is_a_failure(self):
        (self.repo / "orders").mkdir()

        completed = self.missing_module_check("orders.totals")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 1)")

    def test_a_passing_check_prints_passed_and_the_runner_summary(self):
        completed = self.check(PASSING_SUITE)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines(), ["full check: passed", "summary: 3 passed in 0.1s"])
        self.assertEqual(self.log.read_text(), "3 passed in 0.1s\n")

    def test_an_exit_zero_with_no_runner_summary_is_unverified_not_passed(self):
        completed = self.check("echo 496 tests registered")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines(),
                         ["full check: unverified (exit 0, no runner summary)", "summary: not found"])
        self.assertTrue(full_check.is_unverified("unverified (exit 0, no runner summary)"))
        self.assertFalse(full_check.is_unverified("passed"))

    def test_a_chained_command_prints_each_summary_joined_with_a_bar(self):
        completed = self.check("echo '3 passed in 0.1s'; echo '  8 passing (2ms)'")

        self.assertEqual(completed.stdout.splitlines()[1], "summary: 3 passed in 0.1s | 8 passing (2ms)")

    def test_a_log_name_with_an_unfilled_placeholder_is_a_usage_error(self):
        for name in ("review-gate-....log", "review-gate-<branch>.log", "review-gate->x.log"):
            with self.subTest(name=name):
                self.log = self.repo / name

                completed = self.check(PASSING_SUITE)

                self.assertEqual(completed.returncode, 2)
                self.assertFalse(self.log.exists())

    def test_a_failing_check_prints_its_exit_code_and_the_log_tail(self):
        completed = self.check("echo the rounding test failed; exit 3")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines(), ["full check: failed (exit 3)", "the rounding test failed"])

    def test_a_failing_lint_step_shows_its_error_lines_not_the_passing_test_tail(self):
        stand_in = ("printf 'C901 `command_asks_done` is too complex (12 > 10)\\n  --> app.py:12:5\\n'; "
                    "for n in $(seq 1 60); do echo \"test_$n OK\"; done; echo '60 tests, 0 failed'; "
                    "echo 'FAILED: lint'; exit 1")

        completed = self.check(stand_in)

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines(), ["full check: failed (exit 1)",
                                                         "C901 `command_asks_done` is too complex (12 > 10)",
                                                         "  --> app.py:12:5", "FAILED: lint"])

    def test_a_failing_test_step_shows_its_fail_lines(self):
        completed = self.check("echo 'FAIL: test_rounding (test_money.MoneyTest)'; echo 'Ran 9 tests'; exit 1")

        self.assertIn("FAIL: test_rounding (test_money.MoneyTest)", completed.stdout.splitlines())

    def test_a_step_on_a_missing_path_is_a_check_command_error_not_a_failure(self):
        for command in ("git init -q && git diff --exit-code missing/schema.json", "cd missing-dir && true",
                        "python3 missing/manage.py test",
                        "echo 'ERROR: file or directory not found: missing/test_x.py'; exit 4"):
            with self.subTest(command=command):
                completed = self.check(command)

                self.assertEqual(completed.returncode, 0, completed.stdout)
                first_line = completed.stdout.splitlines()[0]
                self.assertTrue(first_line.startswith("full check: not run (check-command error: "), first_line)
                self.assertIn("missing", first_line)

    def test_a_step_on_a_path_the_diff_removed_is_a_failure(self):
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "schema.json").write_text("{}\n")
        for argv in (["init", "-q"], ["add", "pkg"], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q",
                                                      "-m", "base"], ["rm", "-q", "-r", "pkg"]):
            subprocess.run(["git", *argv], cwd=self.repo, check=True)

        for command in ("git diff --exit-code pkg/schema.json", "cd pkg && true"):
            with self.subTest(command=command):
                completed = self.check(command)

                self.assertEqual(completed.returncode, 1, completed.stdout)
                self.assertTrue(completed.stdout.startswith("full check: failed"), completed.stdout)

    def test_a_check_with_no_package_manifest_is_a_setup_fault(self):
        completed = self.check("echo ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND; exit 1")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: setup fault (exit 1)")

    def test_a_missing_module_from_outside_the_repo_is_a_failure_not_a_setup_fault(self):
        completed = self.check("echo \"ModuleNotFoundError: No module named 'requests'\"; exit 2")

        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 2)")

    def test_a_failing_test_name_the_tail_cut_off_is_printed_above_the_tail(self):
        failing_test = "FAILED tests/test_totals.py::test_rounding"
        completed = self.check(f"echo '{failing_test}'; seq 1 100; exit 1")

        self.assertEqual(completed.stdout.splitlines()[:3],
                         ["full check: failed (exit 1)", "Failing tests:", failing_test])

    def test_a_check_past_its_limit_is_not_run_and_leaves_no_process_behind(self):
        pid_file = self.repo / "sleeper.pid"

        completed = self.check(f"sleep 30 & echo $! > {pid_file}; wait", timeout=1)

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: not run (timeout)")
        sleeper = int(pid_file.read_text())
        time.sleep(0.2)
        with self.assertRaises(ProcessLookupError):
            os.kill(sleeper, 0)

    def test_the_full_suite_in_ci_line_skips_the_check(self):
        marker = self.repo / "ran"

        completed = self.check(f"touch {marker}", claude_md="# Repo\n\n- Full suite: CI\n")

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: not run (CI)")
        self.assertFalse(marker.exists())

    def test_the_check_runs_when_claude_md_has_no_full_suite_line(self):
        completed = self.check(PASSING_SUITE, claude_md="Quality check: `make test`\n")

        self.assertEqual(completed.stdout.splitlines()[0], "full check: passed")

    def test_a_misspelled_full_suite_line_still_runs_the_check(self):
        for line in ("Full suite: ci", "Full-suite: CI", "Full suite CI", "Full suite: CI runs it"):
            with self.subTest(line=line):
                completed = self.check(PASSING_SUITE, claude_md=line + "\n")

                self.assertEqual(completed.stdout.splitlines()[0], "full check: passed")

    def test_a_package_manager_version_mismatch_is_a_setup_fault(self):
        completed = self.check("echo 'ERR_PNPM_BAD_PM_VERSION  This project is configured to use v9'; exit 1")

        self.assertEqual(completed.stdout.splitlines()[0], "full check: setup fault (exit 1)")


class FullCheckSideEffectsTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.repo = pathlib.Path(scratch.name) / "repo"
        self.repo.mkdir()
        self.log = pathlib.Path(scratch.name) / "review-gate.log"
        for args in (("init", "-q", "-b", "main"), ("config", "user.email", "t@example.com"),
                     ("config", "user.name", "T")):
            subprocess.run(["git", *args], cwd=self.repo, check=True)
        (self.repo / "generated.ts").write_text("generated v1\n")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "files"], cwd=self.repo, check=True)

    def check(self, command, timeout=60):
        argv = [sys.executable, "-B", str(SCRIPT), str(self.repo), "--log", str(self.log), "--timeout", str(timeout)]
        return subprocess.run([*argv, "--", command], capture_output=True, text=True, timeout=60)

    def test_a_tracked_file_the_check_rewrote_and_a_file_it_created_are_named_and_left_in_place(self):
        command = f"echo generated v2 > generated.ts; mkdir dist; echo built > dist/out.js; {PASSING_SUITE}"

        completed = self.check(command)

        self.assertEqual(completed.stdout.splitlines(), [
            "full check: passed", "summary: 3 passed in 0.1s",
            "changed by the check: generated.ts", "created by the check: dist/out.js"])
        self.assertEqual("generated v2\n", (self.repo / "generated.ts").read_text())
        self.assertTrue((self.repo / "dist" / "out.js").is_file())

    def test_a_file_that_held_edits_before_the_check_and_was_rewritten_is_named_on_its_own_line(self):
        (self.repo / "generated.ts").write_text("edited by the coder\n")

        completed = self.check(f"echo rewritten > generated.ts; {PASSING_SUITE}")

        self.assertEqual(completed.stdout.splitlines(), [
            "full check: passed", "summary: 3 passed in 0.1s", "rewrote edited files: generated.ts"])

    def test_exit_zero_with_a_summary_that_reports_failures_is_a_failure(self):
        completed = self.check("echo '=== 3 failed, 1 passed in 0.1s ==='; true")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 0, summary reports failures)")
        self.assertTrue(full_check.is_failure("failed (exit 0, summary reports failures)"))

    def test_a_failing_summary_after_the_fifth_is_still_a_failure(self):
        command = ("for n in 1 2 3 4 5 6; do echo \"test result: ok. $n passed; 0 failed\"; done; "
                   "echo '=== 2 failed, 1 passed in 0.1s ==='")

        completed = self.check(command)

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 0, summary reports failures)")

    def test_exit_zero_with_a_unittest_failed_line_is_a_failure(self):
        completed = self.check("printf 'Ran 3 tests in 0.1s\\n\\nFAILED (failures=1)\\n'")

        self.assertEqual(completed.returncode, 1)
        self.assertEqual(completed.stdout.splitlines()[0], "full check: failed (exit 0, summary reports failures)")

    def test_exit_zero_with_a_failure_count_in_a_runners_summary_is_a_failure(self):
        cases = {
            "mocha": "printf '  3 passing (9ms)\\n  2 failing\\n'",
            "bun": "printf ' 3 pass\\n 2 fail\\n'",
            "node test": "printf '# tests 5\\n# pass 3\\n# fail 2\\n'",
            "playwright": "printf '  2 failed\\n  3 passed (5.2s)\\n'",
            "go": "printf 'ok  \\texample.com/a\\t0.1s\\nFAIL\\texample.com/b\\t0.2s\\n'",
            "dotfiles suite": "echo '9 tests in 2 files, wall-clock 1.0s, sum of per-file seconds 1.5s, 1 failed'",
        }
        for runner, command in cases.items():
            with self.subTest(runner):
                completed = self.check(command)

                self.assertEqual(completed.returncode, 1, completed.stdout)
                self.assertEqual(completed.stdout.splitlines()[0],
                                 "full check: failed (exit 0, summary reports failures)")

    def test_exit_zero_summaries_with_no_failures_stay_passed(self):
        cases = {
            "all passed": "echo '=== 4 passed in 0.1s ==='",
            "cargo zero failed": "echo 'test result: ok. 5 passed; 0 failed; 0 ignored'",
            "mocha": "printf '  3 passing (9ms)\\n'",
            "bun": "printf ' 3 pass\\n 0 fail\\n'",
            "node test": "printf '# tests 3\\n# pass 3\\n# fail 0\\n'",
            "playwright": "printf '  3 passed (5.2s)\\n'",
            "go": "printf 'ok  \\texample.com/a\\t0.1s\\n'",
            "dotfiles suite": "echo '9 tests in 2 files, wall-clock 1.0s, sum of per-file seconds 1.5s, 0 failed'",
        }
        for name, command in cases.items():
            with self.subTest(name):
                completed = self.check(command)

                self.assertEqual(completed.returncode, 0, completed.stdout)
                self.assertEqual(completed.stdout.splitlines()[0], "full check: passed")

    def test_a_check_that_times_out_still_names_what_it_rewrote_and_leaves_it(self):
        completed = self.check("echo generated v2 > generated.ts; sleep 30", timeout=1)

        self.assertEqual(completed.stdout.splitlines(),
                         ["full check: not run (timeout)", "changed by the check: generated.ts"])
        self.assertEqual("generated v2\n", (self.repo / "generated.ts").read_text())

    def test_a_repo_that_leaves_its_log_inside_the_work_tree_does_not_report_the_log_as_created(self):
        self.log = self.repo / "review-gate.log"

        completed = self.check(PASSING_SUITE)

        self.assertEqual(completed.stdout.splitlines(), ["full check: passed", "summary: 3 passed in 0.1s"])


class BaseComparisonTest(unittest.TestCase):
    """The check run on HEAD without the diff, and the comparison of its failing lines with the diff's."""

    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name)
        self.repo = self.scratch / "shop-api"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "T")
        (self.repo / "app.py").write_text("limit = 1\n")
        self.git("add", "app.py")
        self.git("commit", "-q", "-m", "files")
        self.base_log = self.scratch / "full-check-base.log"

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, capture_output=True, text=True, check=True).stdout

    def base_lines(self, command):
        return full_check.base_run(str(self.repo), command, self.base_log, 60)

    def test_a_check_that_fails_on_head_returns_its_failing_lines_and_leaves_the_work_tree_alone(self):
        (self.repo / "app.py").write_text("limit = 2\n")

        base = self.base_lines("echo 'FAIL: test_old (5.2 s)'; exit 1")

        self.assertEqual((base.result, base.failing_lines), ("failed (exit 1)", {"FAIL: test_old"}))
        self.assertEqual((self.repo / "app.py").read_text(), "limit = 2\n")
        self.assertEqual(self.git("status", "--porcelain"), " M app.py\n")
        self.assertEqual(self.git("worktree", "list", "--porcelain").count("worktree "), 1)

    def test_the_base_tree_is_registered_in_live_trees_while_the_check_runs_and_dropped_after(self):
        trees = set()
        seen = []

        def check_run(base_repo, *args, **kwargs):
            seen.append((set(trees), pathlib.Path(base_repo).is_dir()))
            return "passed", set(), {}

        with mock.patch.object(full_check, "run", side_effect=check_run):
            full_check.base_run(str(self.repo), "exit 1", self.base_log, 60, live_trees=trees)

        self.assertEqual(len(seen), 1)
        registered, tree_existed = seen[0]
        self.assertEqual(len(registered), 1)
        (root, tree), = registered
        self.assertEqual(pathlib.Path(root).resolve(), self.repo.resolve())
        self.assertTrue(tree_existed)
        self.assertTrue(str(tree).endswith("base"))
        self.assertEqual(trees, set())

    def test_a_check_that_fails_only_with_the_diff_has_no_base_failure(self):
        (self.repo / "app.py").write_text("limit = 2\n")
        check = "grep -q 'limit = 1' app.py || { echo 'FAIL: test_new'; exit 1; }"

        self.assertIsNone(self.base_lines(check))

    def test_a_base_run_that_hits_a_setup_fault_has_no_base_failure(self):
        self.assertIsNone(self.base_lines("echo 'ERR_PNPM_NO_IMPORTER_MANIFEST_FOUND'; exit 1"))

    def test_the_base_run_sees_the_untracked_dependency_folders_of_the_repo(self):
        (self.repo / "node_modules").mkdir()
        (self.repo / "node_modules" / "dep.txt").write_text("dep\n")
        (self.repo / ".venv").mkdir()
        check = "test -f node_modules/dep.txt && test -d .venv && echo 'FAIL: deps linked'; exit 1"

        self.assertEqual(self.base_lines(check).failing_lines, {"FAIL: deps linked"})
        self.assertTrue((self.repo / "node_modules" / "dep.txt").is_file())

    def test_the_worktree_is_removed_when_the_base_run_raises(self):
        with mock.patch.object(full_check, "run", side_effect=RuntimeError("boom")), \
                self.assertRaises(RuntimeError):
            self.base_lines("exit 1")

        self.assertEqual(self.git("worktree", "list", "--porcelain").count("worktree "), 1)

    def add_base_child(self, name, age_seconds):
        """A leftover base worktree under the base folder, last modified `age_seconds` ago."""
        base_parent = self.repo / ".git" / full_check.BASE_TREE_FOLDER
        child = base_parent / name
        child.mkdir(parents=True)
        self.git("worktree", "add", "-q", "--detach", str(child / "base"), "HEAD")
        modified = time.time() - age_seconds
        os.utime(child, (modified, modified))
        return child

    def test_a_base_run_removes_a_leftover_tree_older_than_twice_the_timeout_and_keeps_a_fresh_one(self):
        old_child = self.add_base_child("old", 200)
        fresh_child = self.add_base_child("fresh", 10)

        self.base_lines("echo 'FAIL: test_old'; exit 1")

        self.assertFalse(old_child.exists())
        self.assertTrue(fresh_child.exists())
        worktrees = self.git("worktree", "list", "--porcelain")
        self.assertNotIn(str(old_child), worktrees)
        self.assertIn(str(fresh_child), worktrees)

    def test_a_base_run_keeps_the_record_of_a_user_worktree_whose_folder_is_missing(self):
        user_tree = self.scratch / "user-tree"
        self.git("worktree", "add", "-q", "--detach", str(user_tree), "HEAD")
        shutil.rmtree(user_tree)
        self.add_base_child("old", 200)

        self.base_lines("echo 'FAIL: test_old'; exit 1")

        self.assertIn(str(user_tree), self.git("worktree", "list", "--porcelain"))

    def base_of(self, text, result="failed (exit 1)"):
        self.base_log.write_text(text)
        return full_check.BaseRun(result, *full_check.log_comparison(text.splitlines()))

    def test_head_failing_lines_are_pre_existing_only_when_every_one_fails_on_base(self):
        head_log = self.scratch / "full-check.log"
        old = "FAIL: test_a\nFAIL: test_b\nFAIL: test_c\n"
        cases = {
            "same lines, durations differ":
                ("FAIL: test_a (12ms)\nFAIL: test_b (5.2 s)\n", old, "failed (exit 1)", True),
            "one new failing line on top of an old one":
                ("FAIL: test_a\nFAIL: test_new\n", old, "failed (exit 1)", False),
            "no failing lines on head": ("1 test crashed\n", old, "failed (exit 1)", False),
            "base failure with no lines": ("FAIL: test_a\n", "nothing useful\n", "failed (exit 1)", False),
            "another exit code": ("FAIL: test_a\n", old, "failed (exit 2)", False),
            "a trailing ms timing differs": ("FAIL  a.test.ts > t1 15ms\n", "FAIL  a.test.ts > t1 12ms\n",
                                             "failed (exit 1)", False),
            "a pytest clock suffix on a run over a minute differs":
                ("FAIL: test_a\n1 failed in 65.12s (0:01:05)\n", old + "1 failed in 61.5s (0:01:01)\n",
                 "failed (exit 1)", True),
            "an assertion message with different numbers":
                ("FAILED t.py::test_a - assert expected 5000ms, got 2000ms\n",
                 "FAILED t.py::test_a - assert expected 5000ms, got 3000ms\n", "failed (exit 1)", False),
            "a detail line under a failing test with different millisecond values in its message":
                ("FAIL: test_a\n    AssertionError: expected 5000ms, got 2000ms\n",
                 "FAIL: test_a\n    AssertionError: expected 5000ms, got 3000ms\n", "failed (exit 1)", False),
            "a detail line under a failing test with different passed counts":
                ("FAIL: test_a\n    AssertionError: expected 3 passed\n",
                 "FAIL: test_a\n    AssertionError: expected 5 passed\n", "failed (exit 1)", False),
            "a pytest reason with different warning counts":
                ("FAILED t.py::test_a - expected 3 warnings, got 0\n",
                 "FAILED t.py::test_a - expected 5 warnings, got 0\n", "failed (exit 1)", False),
            "the same test fails with a different assertion":
                ("FAIL: test_a\n    assert 1 == 2\n\nFAIL: test_b\n",
                 "FAIL: test_a\n    assert 1 == 3\n\nFAIL: test_b\n", "failed (exit 1)", False),
            "a jest file fails on a new detail line":
                ("FAIL src/a.test.ts\n  old failure\n  new failure\n", "FAIL src/a.test.ts\n  old failure\n",
                 "failed (exit 1)", False),
            "a jest file gains a second failing test after a blank line":
                ("FAIL src/a.test.js\n  ● suite > old\n\n    Expected: 3\n\n  ● suite > new\n\n    Expected: 5\n",
                 "FAIL src/a.test.js\n  ● suite > old\n\n    Expected: 3\n", "failed (exit 1)", False),
            "a jest run time differs between base and head":
                ("FAIL src/a.test.js\n  ● suite > old\n\n    Expected: 3\n\nTime:        1.5 s\n",
                 "FAIL src/a.test.js\n  ● suite > old\n\n    Expected: 3\n\nTime:        1.2 s\n",
                 "failed (exit 1)", True),
            "a vitest duration and start time differ between base and head":
                ("FAIL  src/a.test.ts > suite > case\nDuration  1.23s (transform 10ms)\nStart at  10:00:05\n",
                 "FAIL  src/a.test.ts > suite > case\nDuration  1.56s (transform 12ms)\nStart at  10:00:00\n",
                 "failed (exit 1)", True),
            "a jest file passes on head beside the failing file it had on base":
                ("FAIL src/a.test.js\n  ● suite > old\n    Expected: 3\n\nPASS a.test.js\nPASS new.test.js\n",
                 "FAIL src/a.test.js\n  ● suite > old\n    Expected: 3\n\nPASS a.test.js\n", "failed (exit 1)", True),
            "a vitest summary whose total in parentheses changes":
                ("FAIL: test_a\nTests  1 failed | 11 passed (13)\n", "FAIL: test_a\nTests  1 failed | 10 passed (12)\n",
                 "failed (exit 1)", True),
            "an xfail test added to a suite that already fails":
                ("FAIL: test_a\n1 failed, 10 passed, 1 xfailed\n", "FAIL: test_a\n1 failed, 10 passed\n",
                 "failed (exit 1)", True),
            "an identical failing block":
                ("FAIL: test_a\n    assert 1 == 2 (5ms)\n\nFAIL: test_b\n",
                 "FAIL: test_a\n    assert 1 == 2 (9ms)\n\nFAIL: test_b\n", "failed (exit 1)", True),
            "a new passing test changes only the passed count":
                ("FAIL: test_a\n1 failed, 11 passed in 1.5s\n", old + "1 failed, 10 passed in 1.2s\n",
                 "failed (exit 1)", True),
            "a new skipped test beside a changed passed count":
                ("FAIL: test_a\n1 failed, 11 passed, 2 skipped\n", old + "1 failed, 10 passed\n",
                 "failed (exit 1)", True),
            "a new compiler error beside an old failure":
                ("FAIL: test_a\nsrc/a.ts(3,1): error TS2322 type mismatch\n", old, "failed (exit 1)", False),
            "a changed total that counts a failure":
                ("FAIL: test_a\n2 failed, 8 passed\n", old + "1 failed, 9 passed\n", "failed (exit 1)", False),
            "a lint error at a new location":
                ("E501 x\n  --> new.py:9:1\nFAILED: lint\n", "E501 x\n  --> old.py:3:1\nFAILED: lint\n",
                 "failed (exit 1)", False),
            "an identical lint error":
                ("E501 x\n  --> old.py:3:1\nFAILED: lint\n", "E501 x\n  --> old.py:3:1\nFAILED: lint\n",
                 "failed (exit 1)", True),
            "a failed-steps summary with a new non-error line":
                ("FAILED: lint duplicate-check\nduplicate code: src/b.py\n", "FAILED: lint duplicate-check\n",
                 "failed (exit 1)", False),
            "identical logs that hold only a failed-steps summary":
                ("FAILED: lint duplicate-check\n", "FAILED: lint duplicate-check\n", "failed (exit 1)", True),
            "a changed timing is not a new line":
                ("FAIL: test_a\nran 10 tests in 1.5s\n", old + "ran 10 tests in 2.5s\n", "failed (exit 1)", True),
        }
        for name, (head_text, base_text, head_result, expected) in cases.items():
            with self.subTest(name):
                base = self.base_of(base_text)
                head_log.write_text(head_text)

                self.assertEqual(full_check.is_pre_existing(head_log, head_result, base), expected)

        head_log.write_text("FAIL: test_a\n")
        self.assertFalse(full_check.is_pre_existing(head_log, "failed (exit 1)", None))

    def test_a_repo_with_an_editable_install_in_its_venv_is_an_editable_install(self):
        site = self.repo / ".venv" / "lib" / "python3.12" / "site-packages"
        site.mkdir(parents=True)
        (site / "__editable__.shop-0.1.pth").write_text("/somewhere\n")

        self.assertIsNone(self.base_lines("echo 'FAIL: test_old'; exit 1"))
        self.assertFalse(self.base_log.exists())

    def test_a_dist_info_without_the_editable_mark_and_a_pth_with_no_path_get_a_base_run(self):
        site = self.repo / ".venv" / "lib" / "python3.12" / "site-packages"
        dist_info = site / "shop-0.1.dist-info"
        dist_info.mkdir(parents=True)
        (dist_info / "direct_url.json").write_text('{"url": "file:///x", "dir_info": {}}')
        (site / "distutils-precedence.pth").write_text("import os\n")

        base = full_check.base_run(str(self.repo), "echo 'FAIL: test_old'; exit 1", self.base_log, 60)

        self.assertFalse(linked_installs.holds_editable_install(self.repo))
        self.assertIsInstance(base, full_check.BaseRun)

    def test_a_virtualenv_outside_the_repo_skips_the_base_run_only_when_it_links_into_the_repo(self):
        site = self.scratch / "elsewhere-env" / "lib" / "python3.12" / "site-packages"
        site.mkdir(parents=True)
        env = {**os.environ, "VIRTUAL_ENV": str(self.scratch / "elsewhere-env")}
        links = {
            "a .pth line": ("shop.pth", f"{self.repo}\n", True),
            "an egg-link": ("shop.egg-link", f"{self.repo}\n.\n", True),
            "an editable finder module": ("__editable___shop_finder.py", f"MAPPING = {{'shop': '{self.repo}/shop'}}\n",
                                          True),
            "a .pth line to another project": ("other.pth", f"{self.scratch}/other-project\n", False),
            "a sibling folder named like the repo": ("sibling.pth", f"{self.repo}-copy\n", False),
            "an egg-link to another project": ("other.egg-link", f"{self.scratch}/other-project\n.\n", False),
            "an editable finder module for another project": (
                "__editable___other_finder.py", f"MAPPING = {{'other': '{self.scratch}/other-project/other'}}\n",
                False),
        }
        for name, (file_name, text, expected) in links.items():
            with self.subTest(name):
                for stale in site.iterdir():
                    stale.unlink()
                (site / file_name).write_text(text)

                base = full_check.base_run(str(self.repo), "echo 'FAIL: test_old'; exit 1", self.base_log, 60, env=env)

                self.assertEqual(base is None, expected)
                self.assertEqual(self.base_log.exists(), not expected)
                self.base_log.unlink(missing_ok=True)

    def test_a_check_command_or_env_value_naming_the_repo_path_gets_no_base_run(self):
        cases = {
            "the command": (f"cd {self.repo} && echo 'FAIL: test_old'; exit 1", None),
            "a gate-env value": ("echo 'FAIL: test_old'; exit 1", {"APP_DIR": f"{self.repo}/src"}),
        }
        for name, (command, gate_env) in cases.items():
            with self.subTest(name):
                base = full_check.base_run(str(self.repo), command, self.base_log, 60,
                                           env={**os.environ, **(gate_env or {})}, gate_env=gate_env)

                self.assertIsNone(base)
                self.assertFalse(self.base_log.exists())

    def test_an_inherited_pwd_in_the_repo_does_not_block_the_base_run(self):
        env = {**os.environ, "PWD": str(self.repo)}

        base = full_check.base_run(str(self.repo), "echo 'FAIL: test_old'; exit 1", self.base_log, 60, env=env)

        self.assertIsInstance(base, full_check.BaseRun)

    def test_the_base_tree_is_made_under_the_repos_git_common_dir_and_removed_afterwards(self):
        seen = []

        def check_run(base_repo, *args, **kwargs):
            seen.append(pathlib.Path(base_repo))
            return "passed", set(), {}

        with mock.patch.object(full_check, "run", side_effect=check_run):
            full_check.base_run(str(self.repo), "exit 1", self.base_log, 60)

        base_folder = (self.repo / ".git" / full_check.BASE_TREE_FOLDER).resolve()
        self.assertIn(base_folder, seen[0].resolve().parents)
        self.assertFalse(seen[0].exists())

    def test_an_inherited_import_path_inside_the_repo_blocks_the_base_run(self):
        (self.repo / "src").mkdir()
        outside = self.scratch / "elsewhere"
        cases = {"PYTHONPATH in the repo": ("PYTHONPATH", f"{outside}{os.pathsep}{self.repo}/src", True),
                 "NODE_PATH in the repo": ("NODE_PATH", f"{self.repo}/node_modules", True),
                 "a relative entry in the repo": ("PYTHONPATH", "src", True),
                 "PYTHONPATH outside the repo": ("PYTHONPATH", str(outside), False),
                 "a sibling named like the repo": ("PYTHONPATH", f"{self.repo}-v2/src", False)}
        for name, (variable, value, blocked) in cases.items():
            with self.subTest(name):
                base = full_check.base_run(str(self.repo), "echo 'FAIL: test_old'; exit 1", self.base_log, 60,
                                           env={**os.environ, variable: value})

                self.assertEqual(base is None, blocked)

    def test_a_sibling_path_named_like_the_repo_does_not_block_the_base_run(self):
        command = f"echo 'FAIL: test_old'; exit 1 # {self.repo}-v2/run"

        base = full_check.base_run(str(self.repo), command, self.base_log, 60,
                                   gate_env={"APP_DIR": f"{self.repo}-v2"})

        self.assertIsInstance(base, full_check.BaseRun)

    def test_a_repo_in_a_subfolder_runs_its_check_in_the_same_subfolder_of_the_base_tree(self):
        (self.repo / "pkg").mkdir()
        (self.repo / "pkg" / "app.py").write_text("limit = 1\n")
        self.git("add", "pkg/app.py")
        self.git("commit", "-q", "-m", "pkg")

        base = full_check.base_run(str(self.repo / "pkg"), "test -f app.py && echo 'FAIL: in pkg'; exit 1",
                                   self.base_log, 60)

        self.assertEqual(base.failing_lines, {"FAIL: in pkg"})

    def test_an_untracked_subfolder_with_its_own_dependencies_gets_no_base_run(self):
        (self.repo / "newpkg" / "node_modules").mkdir(parents=True)

        base = full_check.base_run(str(self.repo / "newpkg"), "echo 'FAIL: test_old'; exit 1", self.base_log, 60)

        self.assertIsNone(base)
        self.assertFalse(self.base_log.exists())

    def test_a_django_traceback_in_the_base_run_matches_the_head_run_once_the_temp_paths_are_mapped_back(self):
        traceback = ("FAIL: test_old (shop.tests.OldTest)\n"
                     "Traceback (most recent call last):\n"
                     '  File "{root}/shop/tests.py", line 9, in test_old\n'
                     "    self.assertEqual(1, 2)\n"
                     "AssertionError: 1 != 2\n")
        command = ('printf "FAIL: test_old (shop.tests.OldTest)\\nTraceback (most recent call last):\\n'
                   '  File \\"$PWD/shop/tests.py\\", line 9, in test_old\\n    self.assertEqual(1, 2)\\n'
                   'AssertionError: 1 != 2\\n"; exit 1')
        head_log = self.scratch / "full-check.log"
        head_log.write_text(traceback.format(root=self.repo.resolve()))

        base = full_check.base_run(str(self.repo), command, self.base_log, 60)

        self.assertIn(f'File "{self.repo.resolve()}/shop/tests.py", line 9, in test_old',
                      self.base_log.read_text())
        self.assertTrue(full_check.is_pre_existing(head_log, "failed (exit 1)", base))


class LinkedInstallsTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name)
        self.repo = self.scratch / "repo"
        self.repo.mkdir()

    def test_a_dist_info_with_a_direct_url_marked_editable_is_an_editable_install(self):
        dist_info = self.repo / "venv" / "lib" / "python3.12" / "site-packages" / "shop-0.1.dist-info"
        dist_info.mkdir(parents=True)
        (dist_info / "direct_url.json").write_text('{"url": "file:///x", "dir_info": {"editable": true}}')

        self.assertTrue(linked_installs.holds_editable_install(self.repo))

    def test_a_node_modules_symlink_into_the_repo_is_an_editable_install_but_one_into_itself_is_not(self):
        (self.repo / "packages" / "shared").mkdir(parents=True)
        modules = self.repo / "node_modules"
        modules.mkdir()
        (modules / "real").mkdir()
        (modules / "alias").symlink_to(modules / "real", target_is_directory=True)
        self.assertFalse(linked_installs.holds_editable_install(self.repo))

        (modules / "shared").symlink_to(self.repo / "packages" / "shared", target_is_directory=True)

        self.assertTrue(linked_installs.holds_editable_install(self.repo))

    def test_a_scoped_node_modules_symlink_into_the_repo_is_an_editable_install(self):
        (self.repo / "packages" / "shared").mkdir(parents=True)
        scope = self.repo / "node_modules" / "@org"
        scope.mkdir(parents=True)
        (scope / "shared").symlink_to(self.repo / "packages" / "shared", target_is_directory=True)

        self.assertTrue(linked_installs.holds_editable_install(self.repo))

    def test_a_virtualenv_dist_info_marked_editable_is_an_editable_install_only_when_its_url_is_in_the_repo(self):
        dist_info = self.scratch / "elsewhere-env" / "lib" / "python3.12" / "site-packages" / "shop-0.1.dist-info"
        dist_info.mkdir(parents=True)
        env = {"VIRTUAL_ENV": str(self.scratch / "elsewhere-env")}
        urls = {f"file://{self.repo}": True, f"file://{self.scratch}/other-project": False}
        for url, expected in urls.items():
            with self.subTest(url):
                (dist_info / "direct_url.json").write_text(f'{{"url": "{url}", "dir_info": {{"editable": true}}}}')

                self.assertEqual(linked_installs.holds_editable_install(self.repo, env), expected)

    def test_a_conda_environment_that_links_into_the_repo_is_an_editable_install(self):
        site = self.scratch / "conda" / "lib" / "python3.12" / "site-packages"
        site.mkdir(parents=True)
        (site / "shop.egg-link").write_text(f"{self.repo}\n.\n")

        env = {"CONDA_PREFIX": str(self.scratch / "conda")}

        self.assertTrue(linked_installs.holds_editable_install(self.repo, env))


if __name__ == "__main__":
    unittest.main()
