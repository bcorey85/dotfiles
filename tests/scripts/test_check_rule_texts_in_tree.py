"""Checks for check_rule_texts_in_tree.py, which compares each live scenario's rule_text with its agent or skill file.

Set CHECK_RULE_TEXTS_SCRIPT to run against another copy of the script."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("CHECK_RULE_TEXTS_SCRIPT")
                      or toolkit_paths.REPO_ROOT / "tests" / "scripts" / "check_rule_texts_in_tree.py")
RULE = "Never guess a path."


def make_repo(folder):
    folder.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(folder)], check=True)
    skills = folder / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text(f"# Demo\n\n{RULE}\n")
    return folder


def run_check(scenarios, root):
    with tempfile.TemporaryDirectory() as scratch:
        scenarios_file = pathlib.Path(scratch) / "scenarios.json"
        scenarios_file.write_text(scenarios if isinstance(scenarios, str) else json.dumps(scenarios))
        return subprocess.run([sys.executable, str(SCRIPT), str(scenarios_file), str(root)],
                              capture_output=True, text=True, check=False)


class CheckRuleTextsInTreeTest(unittest.TestCase):
    def setUp(self):
        scratch = tempfile.TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.scratch = pathlib.Path(scratch.name)
        self.repo = make_repo(self.scratch / "repo")

    def test_a_scenario_whose_rule_text_is_in_its_file_exits_0(self):
        run = run_check({"A": {"rule_source": "skills/demo/SKILL.md", "rule_text": RULE}}, self.repo)

        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout, "")

    def test_every_mismatch_prints_before_the_run_exits_1(self):
        scenarios = {
            "A": {"rule_source": "skills/demo/SKILL.md", "rule_text": "Not in the file."},
            "B": {"rule_source": "skills/demo/SKILL.md", "rule_text": RULE},
            "C": {"rule_source": "skills/missing/SKILL.md", "rule_text": RULE},
        }

        run = run_check(scenarios, self.repo)

        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertIn("FAIL A: rule_text not verbatim in skills/demo/SKILL.md", run.stdout)
        self.assertIn("FAIL C: skills/missing/SKILL.md is missing from", run.stdout)
        self.assertNotIn("FAIL B", run.stdout)

    def test_a_missing_rule_text_exits_2_after_the_mismatches_before_it_printed(self):
        scenarios = {
            "A": {"rule_source": "skills/demo/SKILL.md", "rule_text": "Not in the file."},
            "B": {"rule_source": "skills/demo/SKILL.md", "rule_text": ""},
        }

        run = run_check(scenarios, self.repo)

        self.assertEqual(run.returncode, 2)
        self.assertIn("FAIL A", run.stdout)
        self.assertIn("scenario B", run.stderr)

    def test_a_root_outside_any_git_repository_exits_2(self):
        bare_folder = self.scratch / "bare"
        bare_folder.mkdir()

        run = run_check({}, bare_folder)

        self.assertEqual(run.returncode, 2)
        self.assertIn("is not inside a git repository", run.stderr)

    def test_unreadable_json_exits_2(self):
        run = run_check("{not json", self.repo)

        self.assertEqual(run.returncode, 2)
        self.assertIn("cannot read", run.stderr)

    def test_a_scenario_with_a_toolkit_root_in_another_repository_is_skipped(self):
        frozen_copy = make_repo(self.scratch / "frozen")
        scenarios = {
            "A": {"rule_source": "skills/demo/SKILL.md", "rule_text": "Not in the file.",
                  "toolkit_root": str(frozen_copy)},
            "B": {"rule_source": "skills/demo/SKILL.md", "rule_text": "Not in the file.",
                  "toolkit_root": str(self.repo)},
        }

        run = run_check(scenarios, self.repo)

        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertNotIn("FAIL A", run.stdout)
        self.assertIn("FAIL B", run.stdout)

    def test_retired_scenarios_and_sources_outside_agents_and_skills_are_skipped(self):
        scenarios = {
            "A": {"rule_source": "skills/demo/SKILL.md", "rule_text": "Not in the file.", "retired": True},
            "B": {"rule_source": "docs/notes.md", "rule_text": "Not in the file."},
        }

        run = run_check(scenarios, self.repo)

        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_a_wrong_argument_count_exits_2_with_usage(self):
        run = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=False)

        self.assertEqual(run.returncode, 2)
        self.assertIn("usage:", run.stderr)

    def test_json_that_is_not_an_object_of_objects_exits_2(self):
        for text in ("[1]", '{"A": 1}'):
            with self.subTest(text=text):
                run = run_check(text, self.repo)

                self.assertEqual(run.returncode, 2)
                self.assertIn("must be a JSON object of scenario objects", run.stderr)


if __name__ == "__main__":
    unittest.main()
