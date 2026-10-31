"""Tests for plan_verification.py: which Automated Verification items of a plan can run."""
import importlib.util
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

import toolkit_paths

sys.path.insert(0, str(toolkit_paths.LIB_DIR))
module_spec = importlib.util.spec_from_file_location("plan_verification",
                                                     toolkit_paths.CODE_DIR / "plan_verification.py")
plan_verification = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(plan_verification)


class VerificationItemTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.repo = pathlib.Path(folder.name)

    def test_an_item_with_a_program_on_path_runs_and_names_its_command(self):
        line = "- [ ] `ls -l` lists the folder"

        self.assertEqual(plan_verification.verification_command(line, self.repo), "ls -l")
        self.assertIsNone(plan_verification.verification_item_problem(line, self.repo))

    def test_an_item_with_no_backticked_command_has_a_problem(self):
        problem = plan_verification.verification_item_problem("- [ ] it works", self.repo)

        self.assertIn("no backticked command", problem)

    def test_an_item_that_hands_a_shell_its_code_is_not_a_command(self):
        line = "- [ ] `bash -c 'ls'` lists"

        self.assertIsNone(plan_verification.verification_command(line, self.repo))
        self.assertEqual(plan_verification.verification_item_problem(line, self.repo),
                         plan_verification.SHELL_CODE_PROBLEM)

    def test_an_item_whose_span_starts_with_no_program_names_the_first_words(self):
        problem = plan_verification.verification_item_problem("- [ ] `nosuchprogram_xyz --flag` runs", self.repo)

        self.assertIn("no backticked span starts with a program", problem)
        self.assertIn("`nosuchprogram_xyz`", problem)

    def test_a_command_that_never_returns_is_not_a_check(self):
        self.assertIsNone(plan_verification.verification_command("- [ ] `tail -f log.txt` follows", self.repo))

    def test_a_repo_file_is_a_command_only_when_it_is_executable(self):
        check_file = self.repo / "scripts/check-orders"
        check_file.parent.mkdir()
        check_file.write_text("#!/bin/sh\n")
        check_file.chmod(0o644)
        item = "- [ ] **Check**: the orders pass - `scripts/check-orders --all`"

        not_executable = plan_verification.verification_command(item, self.repo)
        check_file.chmod(0o755)
        executable = plan_verification.verification_command(item, self.repo)

        self.assertEqual((None, "scripts/check-orders --all"), (not_executable, executable))

    def test_a_relative_path_with_a_slash_is_never_looked_up_on_path(self):
        with mock.patch.object(plan_verification.shutil, "which", return_value="/anywhere/tool"):
            self.assertFalse(plan_verification.starts_like_a_program_here("../tool --x", self.repo))
            self.assertFalse(plan_verification.starts_like_a_program_here("sub/tool --x", self.repo))
            self.assertTrue(plan_verification.starts_like_a_program_here("tool --x", self.repo))
            self.assertTrue(plan_verification.starts_like_a_program_here("/opt/bin/tool --x", self.repo))

    def test_the_last_program_span_after_the_em_dash_wins_over_prose_spans_before_it(self):
        item = "- [ ] **Check**: `ls -la` lists them — run `wc -l` then `stat -c %s`"

        self.assertEqual("stat -c %s", plan_verification.verification_command(item, self.repo))

    def test_a_shell_that_runs_a_script_file_is_still_a_verification_command(self):
        for command in ("sh scripts/check.sh", "bash -e scripts/check.sh --fast", "bash -o pipefail scripts/check.sh",
                        "bash -euo pipefail scripts/check.sh", "sh scripts/check.sh -c fast"):
            with self.subTest(command=command):
                item = f"- [ ] **Check**: `{command}`"

                self.assertEqual(command, plan_verification.verification_command(item, self.repo))

    def test_a_negated_rg_or_git_grep_ban_is_a_command_without_its_negation(self):
        cases = {
            "! rg -n console.log backend/src/orders.ts": "rg -n console.log backend/src/orders.ts",
            "cd backend && ! rg -n x src/orders.ts": "cd backend && rg -n x src/orders.ts",
            "! git grep -n console.log -- backend/src/orders.ts": "git grep -n console.log -- backend/src/orders.ts",
        }
        for span, expected in cases.items():
            with self.subTest(span=span):
                item = f"- [ ] **Prohibition**: no console.log - `{span}`"

                self.assertEqual(expected, plan_verification.verification_command(item, self.repo))
                self.assertIsNone(plan_verification.verification_item_problem(item, self.repo))


if __name__ == "__main__":
    unittest.main()
