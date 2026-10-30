"""Checks for the full-check receipt: the store and its validity rules (lib/full_check_receipt), the rows that
review/full_check.py writes, and the readers that ask the receipt instead of reading command text."""
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import receipt_repo
import toolkit_paths

sys.path.insert(0, str(toolkit_paths.REVIEW_DIR))
sys.path.insert(0, str(toolkit_paths.LIB_DIR))
import check_scope
import full_check
import full_check_receipt
import reviewed_tree
import script_utils
import verify_common

SCRIPT = pathlib.Path(os.environ.get("FULL_CHECK_SCRIPT") or toolkit_paths.REVIEW_DIR / "full_check.py")
PASSING_SUITE = "echo '3 passed in 0.1s'"


class ReceiptTestCase(unittest.TestCase):
    def setUp(self):
        self.repo = receipt_repo.make_repo(self)
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.log = os.path.join(scratch.name, "review-gate.log")

    def edit(self, text="x = 2\n"):
        pathlib.Path(self.repo, "app.py").write_text(text)

    def rows(self):
        return script_utils.read_jsonl(full_check_receipt.receipts_path(self.repo))

    def rows_of(self, kind):
        return [row for row in self.rows() if row["kind"] == kind]

    def finish_satisfied_run(self, command):
        """Write the rows of a run of `command` through full_check.write_step_rows that ended passed and satisfied."""
        run_id = full_check_receipt.write_started_row(self.repo, command, command)
        full_check.write_step_rows(self.repo, run_id, command)
        tree = full_check_receipt.current_tree(self.repo)
        full_check_receipt.write_finished_row(self.repo, run_id, full_check.PASSED, 0, False, False, True, tree, "")


class ReceiptValidityTest(ReceiptTestCase):
    def test_a_work_tree_with_no_run_has_no_receipt(self):
        self.assertEqual(full_check_receipt.receipt_problem(self.repo), "no full check has run in this work tree")
        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_finished_satisfied_whole_run_on_this_tree_is_valid(self):
        run_id = receipt_repo.plant_receipt(self.repo)

        receipt = full_check_receipt.valid_receipt(self.repo)

        self.assertEqual(receipt["run_id"], run_id)
        self.assertIsNone(full_check_receipt.receipt_problem(self.repo))

    def test_a_started_run_with_no_finished_row_is_not_valid(self):
        receipt_repo.plant_receipt(self.repo, finish=False)

        self.assertIn("never finished", full_check_receipt.receipt_problem(self.repo))

    def test_a_killed_later_run_voids_an_older_valid_receipt(self):
        receipt_repo.plant_receipt(self.repo)
        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

        receipt_repo.plant_receipt(self.repo, finish=False)

        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_run_that_verified_nothing_is_not_valid_and_says_its_result(self):
        for result_line in ("failed (exit 0, summary reports failures)", "setup fault (exit 127)"):
            with self.subTest(result_line=result_line):
                receipt_repo.plant_receipt(self.repo, result=result_line, satisfied=False)

                problem = full_check_receipt.receipt_problem(self.repo)

                self.assertIn("did not verify the tree", problem)
                self.assertIn(result_line, problem)

    def test_a_commit_after_a_clean_tree_run_voids_the_receipt(self):
        git = ["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "add", "app.py"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "one"], check=True)
        receipt_repo.plant_receipt(self.repo)
        self.assertIsNone(full_check_receipt.receipt_problem(self.repo))

        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "two"], check=True)

        self.assertEqual(full_check_receipt.receipt_problem(self.repo),
                         "HEAD moved after the latest full check run")
        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_relative_log_is_stored_as_an_absolute_path(self):
        run_id = full_check_receipt.write_started_row(self.repo, "npm test", "npm test")
        tree = full_check_receipt.current_tree(self.repo)

        full_check_receipt.write_finished_row(self.repo, run_id, "passed", 0, False, False, True, tree, "rel.log")

        [finished] = self.rows_of("finished")
        self.assertEqual(finished["log"], str(pathlib.Path("rel.log").resolve()))

    def test_a_run_with_a_scoped_or_excluding_test_step_is_not_valid_and_names_the_step(self):
        cases = {
            "pytest tests/test_a.py && npm run build": "pytest tests/test_a.py",
            "pytest --ignore=tests/test_slow.py && npm run build": "pytest --ignore=tests/test_slow.py",
            "pytest -k 'not slow' && npm run build": "pytest -k 'not slow'",
            "pytest --deselect tests/test_a.py::test_x && npm run build": "pytest --deselect tests/test_a.py::test_x",
            "npm run build && pytest tests/test_a.py": "pytest tests/test_a.py",
            "npm run lint; pytest tests/a.py": "npm run lint; pytest tests/a.py",
            "npm run lint || pytest -k x": "npm run lint || pytest -k x",
            "pytest -kfoo": "pytest -kfoo",
            "uv run pytest -kfoo": "uv run pytest -kfoo",
            "npm test -- --testNamePattern=foo": "npm test -- --testNamePattern=foo",
            "pytest --lf": "pytest --lf",
            "python -m unittest tests.test_a": "python -m unittest tests.test_a",
            "python3 -m unittest tests.test_a && npm run build": "python3 -m unittest tests.test_a",
        }
        for command, named_step in cases.items():
            with self.subTest(command=command):
                self.finish_satisfied_run(command)

                problem = full_check_receipt.receipt_problem(self.repo)

                self.assertEqual(problem, f"the latest full check run was scoped: `{named_step}`")
                self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_run_of_the_repos_test_root_folder_is_valid_and_a_subfolder_voids_it(self):
        pathlib.Path(self.repo, "tests", "unit").mkdir(parents=True)
        for command in ("pytest tests/", "pytest tests", "npm run build && pytest tests/"):
            with self.subTest(command=command):
                self.finish_satisfied_run(command)

                self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

        self.finish_satisfied_run("pytest tests/unit")

        self.assertEqual(full_check_receipt.receipt_problem(self.repo),
                         "the latest full check run was scoped: `pytest tests/unit`")
        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_test_step_after_a_cd_piece_is_judged_in_the_directory_it_moved_to(self):
        pathlib.Path(self.repo, "backend", "tests").mkdir(parents=True)
        cases = {
            "cd backend; pytest tests": "whole",
            "cd backend || pytest tests/test_a.py": "targeted",
        }
        for step, expected in cases.items():
            with self.subTest(step=step):
                self.assertEqual(expected, check_scope.step_check_scope(step, pathlib.Path(self.repo)))

    def test_a_declared_whole_check_of_any_stack_is_a_valid_receipt(self):
        pathlib.Path(self.repo, "Cargo.toml").write_text("[package]\nname = 'x'\n")
        pathlib.Path(self.repo, "go.mod").write_text("module x\n")
        pathlib.Path(self.repo, "Makefile").write_text("test:\n\tpytest\n")
        pathlib.Path(self.repo, "sub").mkdir()
        pathlib.Path(self.repo, "sub", "Makefile").write_text("test:\n\tpytest\n")
        for command in ("cargo test", "cargo nextest run", "go test ./...", "cd sub && make test", "npm test",
                        "pytest -q", "make test", "ruff check src; pytest",
                        "ruff check src && pytest -q", "mypy app.py && pytest"):
            with self.subTest(command=command):
                self.finish_satisfied_run(command)

                self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_test_step_whose_scope_cannot_be_read_is_a_valid_receipt(self):
        pathlib.Path(self.repo, "Makefile").write_text("test:\n\tpytest $(TESTS)\n")
        for command in ("make test PY=python3", "make test TESTS=tests/a.py", "CI=1 make test",
                        "make -C nowhere test"):
            with self.subTest(command=command):
                self.finish_satisfied_run(command)

                self.assertEqual(self.rows_of("step")[-1]["scope"], "unresolved")
                self.assertIsNone(full_check_receipt.receipt_problem(self.repo))
                self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_make_target_under_a_cd_is_judged_in_the_directory_it_runs_in(self):
        pathlib.Path(self.repo, "Makefile").write_text("test:\n\tpytest\n")
        pathlib.Path(self.repo, "sub").mkdir()
        pathlib.Path(self.repo, "sub", "Makefile").write_text("test:\n\tpytest tests/a.py\n")

        self.finish_satisfied_run("cd sub && make test")

        self.assertEqual(full_check_receipt.receipt_problem(self.repo),
                         "the latest full check run was scoped: `make test`")

    def test_a_run_of_the_real_check_with_a_fake_pytest_records_a_whole_test_step_and_a_valid_receipt(self):
        fake_pytest = pathlib.Path(self.repo, "bin", "pytest")
        fake_pytest.parent.mkdir()
        fake_pytest.write_text("#!/bin/sh\necho '3 passed in 0.1s'\n")
        fake_pytest.chmod(0o755)
        env = {**os.environ, "PATH": f"{fake_pytest.parent}{os.pathsep}{os.environ['PATH']}"}

        full_check.run(pathlib.Path(self.repo), "pytest", self.log, 60, env=env)

        [step] = self.rows_of("step")
        self.assertIs(step["runs_tests"], True)
        self.assertEqual(step["scope"], "whole")
        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_tree_that_cannot_be_fingerprinted_leaves_no_valid_receipt(self):
        for error in (reviewed_tree.TreeFingerprintError, OSError):
            fingerprint = mock.patch.object(full_check_receipt.reviewed_tree, "work_tree_fingerprint",
                                            side_effect=error)
            with self.subTest(error=error.__name__), fingerprint:
                receipt_repo.plant_receipt(self.repo)

                self.assertEqual(full_check_receipt.receipt_problem(self.repo),
                                 "the latest full check run recorded no tree fingerprint")
                self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_tree_that_cannot_be_fingerprinted_at_read_time_reads_as_a_changed_tree(self):
        receipt_repo.plant_receipt(self.repo)

        with mock.patch.object(full_check_receipt.reviewed_tree, "work_tree_fingerprint", side_effect=OSError):
            self.assertEqual(full_check_receipt.receipt_problem(self.repo),
                             "the work tree changed after the latest full check run")

    def test_a_run_that_started_after_another_started_leaves_the_earlier_one_unfinished_for_the_gate(self):
        first = full_check_receipt.write_started_row(self.repo, "npm test", "npm test")
        full_check_receipt.write_started_row(self.repo, "npm test", "npm test")
        full_check_receipt.write_step_row(self.repo, first, 0, "npm test", True, "whole")
        tree = full_check_receipt.current_tree(self.repo)
        full_check_receipt.write_finished_row(self.repo, first, "passed", 0, False, False, True, tree, self.log)

        self.assertIn("never finished", full_check_receipt.receipt_problem(self.repo))
        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_an_edit_after_the_run_voids_the_receipt_and_undoing_it_restores_it(self):
        receipt_repo.plant_receipt(self.repo)

        self.edit()
        self.assertEqual(full_check_receipt.receipt_problem(self.repo),
                         "the work tree changed after the latest full check run")

        self.edit("x = 1\n")
        self.assertIsNone(full_check_receipt.receipt_problem(self.repo))

    def test_a_new_untracked_file_after_the_run_voids_the_receipt(self):
        receipt_repo.plant_receipt(self.repo)

        pathlib.Path(self.repo, "new.py").write_text("y = 1\n")

        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_each_work_tree_keeps_its_own_receipts(self):
        git = ["git", "-C", self.repo, "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run([*git, "add", "app.py"], check=True)
        subprocess.run([*git, "commit", "-q", "-m", "one"], check=True)
        linked = tempfile.TemporaryDirectory()
        self.addCleanup(linked.cleanup)
        other = os.path.join(linked.name, "other")
        subprocess.run([*git, "worktree", "add", "-q", "--detach", other], check=True)

        receipt_repo.plant_receipt(self.repo)

        self.assertIsNone(full_check_receipt.receipt_problem(self.repo))
        self.assertEqual(full_check_receipt.receipt_problem(other), "no full check has run in this work tree")

    def test_a_directory_outside_git_keeps_no_receipts_and_writes_none(self):
        outside = tempfile.TemporaryDirectory()
        self.addCleanup(outside.cleanup)

        self.assertIsNone(full_check_receipt.receipts_path(outside.name))
        full_check_receipt.append(outside.name, {"kind": "started", "run_id": "r1"})
        self.assertEqual(os.listdir(outside.name), [])
        self.assertEqual(full_check_receipt.receipt_problem(outside.name), "no full check has run in this work tree")


class FullCheckRunRowsTest(ReceiptTestCase):
    def declare(self, command, extra=""):
        pathlib.Path(self.repo, "CLAUDE.md").write_text(f"{extra}Quality check: `{command}`\n")

    def run_declared(self, **options):
        return full_check.run(pathlib.Path(self.repo), full_check.configured_check_command(self.repo), self.log, 60,
                              **options)

    def test_a_passing_declared_check_writes_started_step_and_finished_rows_and_a_valid_receipt(self):
        self.declare(PASSING_SUITE)

        result, _tail, _details = self.run_declared()

        self.assertEqual(result, full_check.PASSED)
        self.assertEqual([row["kind"] for row in self.rows()], ["started", "step", "finished"])
        started, step, finished = self.rows()
        self.assertEqual((started["configured"], started["command"]), (PASSING_SUITE, PASSING_SUITE))
        self.assertEqual((step["step"], step["runs_tests"]), (PASSING_SUITE, False))
        self.assertEqual((finished["result"], finished["satisfied"], finished["exit"]), (full_check.PASSED, True, 0))
        self.assertEqual(len({row["run_id"] for row in self.rows()}), 1)
        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_multi_step_check_writes_one_step_row_per_step_and_no_test_counts_on_the_finished_row(self):
        self.declare("echo '2 passed in 0.1s' && echo '5 passed, 1 skipped in 0.2s'")

        self.run_declared()

        steps = self.rows_of("step")
        self.assertEqual([(row["index"], row["step"]) for row in steps],
                         [(0, "echo '2 passed in 0.1s'"), (1, "echo '5 passed, 1 skipped in 0.2s'")])
        [finished] = self.rows_of("finished")
        self.assertFalse({"passed", "failed", "skipped", "counts"} & finished.keys())

    def test_the_steps_of_a_check_share_one_shell(self):
        self.declare(f"export CHECK_FLAG=on && test $CHECK_FLAG = on && {PASSING_SUITE}")

        result, _tail, _details = self.run_declared()

        self.assertEqual(result, full_check.PASSED)
        self.assertEqual(len(self.rows_of("step")), 3)

    def test_a_check_that_fails_at_a_step_records_the_overall_exit_and_leaves_no_valid_receipt(self):
        self.declare("echo '2 passed in 0.1s' && exit 3 && echo '9 passed'")

        result, _tail, _details = self.run_declared()

        self.assertEqual(result, "failed (exit 3)")
        self.assertEqual(len(self.rows_of("step")), 3)
        [finished] = self.rows_of("finished")
        self.assertEqual((finished["exit"], finished["satisfied"]), (3, False))
        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_the_receipt_tree_is_the_tree_line_the_run_prints(self):
        self.declare(PASSING_SUITE)

        completed = subprocess.run([sys.executable, "-B", str(SCRIPT), self.repo, "--log", self.log],
                                   capture_output=True, text=True, timeout=60)

        printed = [line for line in completed.stdout.splitlines() if line.startswith("tree: ")]
        [finished] = self.rows_of("finished")
        self.assertEqual(printed, [f"tree: {finished['tree']}"])

    def test_a_log_inside_the_work_tree_does_not_void_the_receipt(self):
        self.declare(PASSING_SUITE)
        in_tree_log = os.path.join(self.repo, "check.log")

        full_check.run(pathlib.Path(self.repo), PASSING_SUITE, in_tree_log, 60)

        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_unparseable_test_count_output_leaves_the_verdict_to_the_exit_code_and_wholeness(self):
        cases = {
            "true": True,
            "echo 496 tests registered": True,
            "echo '3 passed, 1 failed in 0.1s'": False,
            "echo 'garbled output' && exit 2": False,
            "echo '3 passed in 0.1s' && exit 1": False,
        }
        for command, expects_receipt in cases.items():
            with self.subTest(command=command):
                self.declare(command)

                self.run_declared()

                self.assertIs(self.rows_of("finished")[-1]["satisfied"], expects_receipt)
                self.assertIs(full_check_receipt.valid_receipt(self.repo) is not None, expects_receipt)

    def test_a_scoped_run_that_exits_zero_never_gets_full_suite_credit(self):
        fake_pytest = pathlib.Path(self.repo, "bin", "pytest")
        fake_pytest.parent.mkdir()
        fake_pytest.write_text("#!/bin/sh\necho '3 passed in 0.1s'\n")
        fake_pytest.chmod(0o755)
        env = {**os.environ, "PATH": f"{fake_pytest.parent}{os.pathsep}{os.environ['PATH']}"}
        self.declare("pytest tests/test_a.py")

        full_check.run(pathlib.Path(self.repo), "pytest tests/test_a.py", self.log, 60, env=env)

        [step] = self.rows_of("step")
        self.assertEqual(step["scope"], "targeted")
        self.assertEqual(self.rows_of("finished")[0]["exit"], 0)
        self.assertEqual(full_check_receipt.receipt_problem(self.repo),
                         "the latest full check run was scoped: `pytest tests/test_a.py`")
        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_check_past_its_limit_leaves_a_timed_out_row_and_no_valid_receipt(self):
        self.declare("sleep 5")

        result, _tail, _details = full_check.run(pathlib.Path(self.repo), "sleep 5", self.log, 1)

        self.assertEqual(result, full_check.NOT_RUN_TIMEOUT)
        [finished] = self.rows_of("finished")
        self.assertIs(finished["timed_out"], True)
        self.assertIs(finished["satisfied"], False)
        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_an_edit_after_the_run_voids_the_receipt_the_run_wrote(self):
        self.declare(PASSING_SUITE)
        self.run_declared()
        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

        self.edit()

        self.assertIsNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_check_that_rewrites_files_still_leaves_a_receipt_valid_for_the_tree_it_left(self):
        self.declare(f"{PASSING_SUITE} && echo y = 5 > app.py")

        self.run_declared()

        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_run_that_writes_no_receipt_leaves_the_rows_alone(self):
        self.declare(PASSING_SUITE)

        self.run_declared(receipt=False)

        self.assertFalse(full_check_receipt.receipts_path(self.repo).exists())

    def test_the_check_of_a_repo_with_no_quality_check_line_runs_nothing_and_is_satisfied(self):
        pathlib.Path(self.repo, "CLAUDE.md").write_text("Run make ci before you push.\n")

        completed = subprocess.run([sys.executable, "-B", str(SCRIPT), self.repo, "--log", self.log],
                                   capture_output=True, text=True, timeout=60)

        self.assertTrue(completed.stdout.startswith("full check: not run (no check found"), completed.stdout)
        self.assertIn("command: none", completed.stdout.splitlines())
        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_handed_command_is_ignored_and_the_declared_check_runs(self):
        self.declare(PASSING_SUITE)
        marker = pathlib.Path(self.repo, "ran")

        completed = subprocess.run([sys.executable, "-B", str(SCRIPT), self.repo, "--log", self.log, "--",
                                    f"touch {marker}; {PASSING_SUITE}"], capture_output=True, text=True, timeout=60)

        self.assertFalse(marker.exists())
        self.assertIn("the handed command is not run", completed.stderr)
        self.assertEqual(self.rows_of("started")[0]["command"], PASSING_SUITE)


class CiMarkerTest(ReceiptTestCase):
    def result_for(self, claude_md):
        pathlib.Path(self.repo, "CLAUDE.md").write_text(claude_md)
        result, _tail, _details = full_check.run(pathlib.Path(self.repo), "true", self.log, 60)
        return result

    def test_the_full_suite_in_ci_marker_is_read_in_each_markdown_form_and_case(self):
        check = "Quality check: `true`\n"
        forms = ("Full suite: CI", "- Full suite: CI", "* Full suite: CI", "## Full suite: CI", "**Full suite: CI**",
                 "**Full suite:** CI", "**Full suite**: CI", "`Full suite`: CI", "`Full suite: CI`", "full suite: ci",
                 "FULL SUITE: CI", "### **Full suite: CI**")
        for form in forms:
            with self.subTest(form=form):
                self.assertEqual(self.result_for(f"# Repo\n\n{form}\n\n{check}"), full_check.CHECK_ONLY_PASSED)
                self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_text_that_only_mentions_the_marker_does_not_declare_it(self):
        check = "Quality check: `true`\n"
        lines = ("The full suite: CI is slow", "Full-suite: CI", "Full suite: CI runs nightly", "Full suite: local")
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(self.result_for(f"{line}\n{check}"), full_check.UNVERIFIED)

    def test_a_ci_repo_with_no_quality_check_line_is_not_run_and_the_marker_variants_all_count(self):
        for form in ("- Full suite: CI", "## Full suite: CI", "**Full suite: CI**", "`full suite: ci`"):
            with self.subTest(form=form):
                pathlib.Path(self.repo, "CLAUDE.md").write_text(f"{form}\n")

                completed = subprocess.run([sys.executable, "-B", str(SCRIPT), self.repo, "--log", self.log],
                                           capture_output=True, text=True, timeout=60)

                self.assertEqual(completed.stdout.splitlines()[0], f"full check: {full_check.NOT_RUN_CI}")
                self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))


class ExpectedRedRowsTest(ReceiptTestCase):
    PLAN = ("## Phase Status\n\n- [ ] Phase 1: Totals (risk: low)\n- [ ] Phase 2: Audit (risk: low)\n\n"
            "## Phase 1: Totals\n\nExpected red: `exit 1` until Phase 2\n\n## Phase 2: Audit\n")

    def test_an_expected_red_run_records_the_configured_command_the_steps_run_and_the_step_left_out(self):
        configured = f"{PASSING_SUITE} && exit 1"
        pathlib.Path(self.repo, "CLAUDE.md").write_text(f"Quality check: `{configured}`\n")
        pathlib.Path(self.repo, "plan.md").write_text(self.PLAN)

        completed = subprocess.run([sys.executable, "-B", str(SCRIPT), self.repo, "--log", self.log, "--plan",
                                    "plan.md", "--phase", "1"], capture_output=True, text=True, timeout=60)

        self.assertEqual(completed.returncode, 0, completed.stdout)
        [started] = self.rows_of("started")
        self.assertEqual(started["configured"], configured)
        self.assertEqual(started["command"], PASSING_SUITE)
        self.assertEqual(started["left_out"], [{"command": "exit 1", "until": "2"}])
        self.assertEqual([row["step"] for row in self.rows_of("step")], [PASSING_SUITE])
        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))

    def test_a_whole_check_that_is_expected_red_is_not_run_and_its_receipt_is_satisfied(self):
        configured = f"{PASSING_SUITE} && exit 1"
        pathlib.Path(self.repo, "CLAUDE.md").write_text(f"Quality check: `{configured}`\n")
        pathlib.Path(self.repo, "plan.md").write_text(self.PLAN.replace("`exit 1`", f"`{configured}`"))

        subprocess.run([sys.executable, "-B", str(SCRIPT), self.repo, "--log", self.log, "--plan", "plan.md",
                        "--phase", "1"], capture_output=True, text=True, timeout=60, check=True)

        [finished] = self.rows_of("finished")
        self.assertEqual(finished["result"], "not run (expected red until Phase 2)")
        self.assertEqual(self.rows_of("step"), [])
        self.assertIsNotNone(full_check_receipt.valid_receipt(self.repo))


class ReaderTest(ReceiptTestCase):
    def test_verify_prep_state_names_the_reason_when_no_receipt_is_valid_and_is_valid_after_a_run(self):
        absent = verify_common.full_check_state(self.repo)
        self.assertEqual(absent, {"valid": False, "reason": "no full check has run in this work tree"})

        receipt_repo.plant_receipt(self.repo)

        self.assertEqual(verify_common.full_check_state(self.repo),
                         {"valid": True, "reason": "latest full check: passed"})

        self.edit()

        self.assertEqual(verify_common.full_check_state(self.repo),
                         {"valid": False, "reason": "the work tree changed after the latest full check run"})


if __name__ == "__main__":
    unittest.main()
