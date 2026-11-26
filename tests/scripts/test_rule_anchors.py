"""Fails when a prompt block and its row in docs/rule-anchors.md drift apart: a block with no row, a row whose block
changed or went, or a row whose file is gone."""
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

import toolkit_paths

RULE_ANCHORS = os.environ.get("RULE_ANCHORS_SCRIPT") or str(toolkit_paths.TOOLS_DIR / "rule-anchors.sh")
DRIFT_HELP = ("Run `rule-anchors.sh list <file>` for each file named above and update its row in "
              "docs/rule-anchors.md: replace the hash, then fix the evidence and the reason.")


def awk_reads_heading_intervals():
    """False on an awk whose regex has no {n,m} interval: the script's block finder then sees no heading."""
    probe = subprocess.run(["awk", 'BEGIN { exit !("## x" ~ /^#{1,6} /) }'], capture_output=True)
    return probe.returncode == 0


@unittest.skipUnless(awk_reads_heading_intervals(), "this awk has no regex interval support")
class RuleAnchorsTest(unittest.TestCase):
    def test_every_prompt_block_has_a_current_row(self):
        result = subprocess.run(["bash", RULE_ANCHORS, "check"], capture_output=True, text=True)
        faults = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, f"{faults}\n{DRIFT_HELP}")
        self.assertEqual(faults, "", f"{faults}\n{DRIFT_HELP}")

    def test_check_reads_the_checkout_it_runs_in_not_the_one_the_script_lives_in(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            installed_script = temp_path / "elsewhere" / "claude" / ".claude" / "scripts" / "tools" / "rule-anchors.sh"
            installed_script.parent.mkdir(parents=True)
            shutil.copy(RULE_ANCHORS, installed_script)

            checkout = temp_path / "checkout"
            checkout_script = checkout / "claude" / ".claude" / "scripts" / "tools" / "rule-anchors.sh"
            checkout_script.parent.mkdir(parents=True)
            shutil.copy(RULE_ANCHORS, checkout_script)
            (checkout / "claude" / ".claude" / "rules.md").write_text("# Rule\n\nbody text\n")
            (checkout / "docs").mkdir()
            (checkout / "docs" / "rule-anchors.md").write_text(
                "| hash | file | section | reason |\n| 00000000 | rules.md | # Rule | stale row |\n")
            subprocess.run(["git", "init", "-q", str(checkout)], check=True)

            env = {key: value for key, value in os.environ.items() if key != "RULE_ANCHORS"}
            result = subprocess.run(["bash", str(installed_script), "check"], cwd=checkout, env=env,
                                    capture_output=True, text=True)

        output = result.stdout + result.stderr
        self.assertIn("STALE  rules.md  00000000", output, output)
        self.assertEqual(result.returncode, 1, output)

    def check_from_unrelated_cwd(self, make_git_repo):
        """Runs `check` from a cwd with no dotfiles checkout; returns the combined output and exit code."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = pathlib.Path(temp_dir)
            installed = temp_path / "installed"
            installed_script = installed / "claude" / ".claude" / "scripts" / "tools" / "rule-anchors.sh"
            installed_script.parent.mkdir(parents=True)
            shutil.copy(RULE_ANCHORS, installed_script)
            (installed / "claude" / ".claude" / "rules.md").write_text("# Rule\n\nbody text\n")
            (installed / "docs").mkdir()
            (installed / "docs" / "rule-anchors.md").write_text(
                "| hash | file | section | reason |\n| 00000000 | rules.md | # Rule | stale row |\n")

            unrelated = temp_path / "unrelated"
            unrelated.mkdir()
            if make_git_repo:
                subprocess.run(["git", "init", "-q", str(unrelated)], check=True)

            env = {key: value for key, value in os.environ.items() if key != "RULE_ANCHORS"}
            result = subprocess.run(["bash", str(installed_script), "check"], cwd=unrelated, env=env,
                                    capture_output=True, text=True)
        return result.stdout + result.stderr, result.returncode

    def test_check_falls_back_to_the_script_checkout_in_a_git_repo_without_the_script(self):
        output, returncode = self.check_from_unrelated_cwd(make_git_repo=True)
        self.assertIn("STALE  rules.md  00000000", output, output)
        self.assertEqual(returncode, 1, output)

    def test_check_falls_back_to_the_script_checkout_outside_any_git_repo(self):
        output, returncode = self.check_from_unrelated_cwd(make_git_repo=False)
        self.assertIn("STALE  rules.md  00000000", output, output)
        self.assertEqual(returncode, 1, output)


if __name__ == "__main__":
    unittest.main()
