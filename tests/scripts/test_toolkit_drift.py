"""The pre-commit toolkit drift step: a staged edit that loses a metered rule text or a skill fails the commit."""
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = pathlib.Path(os.environ.get("TOOLKIT_DRIFT_SCRIPT", REPO_ROOT / "tests" / "toolkit_drift.py"))
REAL_EVALS = pathlib.Path.home() / "agent-evals"
RULE_LINE = "Never swallow the metered rule."
SKILL_PATH = "claude/.claude/skills/alpha/SKILL.md"
CLAUDE_MD = "claude/.claude/CLAUDE.md"

# The two real semantics the stub keeps: check_rule_texts exits with a message on the first scenario whose rule text
# is missing from its source under toolkit_root, and load_scenarios reads the json beside the module.
STUB_RULE_METER = '''
import json, pathlib, sys
HERE = pathlib.Path(__file__).resolve().parent
def load_scenarios():
    return json.loads((HERE / "rule_meter_scenarios.json").read_text())
def check_rule_texts(scenarios):
    for rule, scenario in scenarios.items():
        root = pathlib.Path(scenario["toolkit_root"]).expanduser()
        source = root / (scenario.get("rule_file") or scenario["rule_source"])
        text = source.read_text() if source.is_file() else ""
        if scenario["rule_text"] not in text:
            sys.exit(f"rule text not found in {source}: {scenario['rule_text']!r}")
'''
# Lists the skills the index holds and compares them with bin/toolkit_skills.txt, as the real test does.
STUB_SKILL_TEST = '''
import os, pathlib, subprocess, sys
HERE = pathlib.Path(__file__).resolve().parent
listed = subprocess.run(["git", "-C", os.path.expanduser("~/dotfiles"), "ls-files", "claude/.claude/skills/*/SKILL.md"],
                        capture_output=True, text=True, check=True).stdout.split()
tracked = {path.split("/")[-2] for path in listed}
known = set((HERE / "toolkit_skills.txt").read_text().split())
if tracked != known:
    sys.exit(f"skill list differs: missing {sorted(known - tracked)} extra {sorted(tracked - known)}")
'''


class ToolkitDriftTests(unittest.TestCase):
    def setUp(self):
        folders = [tempfile.TemporaryDirectory() for _ in range(3)]
        for folder in folders:
            self.addCleanup(folder.cleanup)
        self.repo, self.evals, self.home = (pathlib.Path(folder.name) for folder in folders)
        (self.home / "dotfiles").mkdir()
        self.git("init", "-q")
        self.write(CLAUDE_MD, f"intro\n{RULE_LINE}\nend\n")
        self.write(SKILL_PATH, "skill\n")
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "base")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True)

    def write(self, relative_path, text):
        target = self.repo / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def install_stubs(self, scenarios_json):
        bin_dir = self.evals / "bin"
        bin_dir.mkdir()
        (bin_dir / "rule_meter.py").write_text(STUB_RULE_METER, encoding="utf-8")
        (bin_dir / "rule_meter_scenarios.json").write_text(scenarios_json, encoding="utf-8")
        (bin_dir / "test_skill_names.py").write_text(STUB_SKILL_TEST, encoding="utf-8")
        (bin_dir / "toolkit_skills.txt").write_text("alpha\n", encoding="utf-8")

    def commit(self):
        self.git("add", ".")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "more")

    def run_step(self, evals=None, extra_env=None):
        env = {**os.environ, "AGENT_EVALS_DIR": str(evals or self.evals), "HOME": str(self.home), **(extra_env or {})}
        return subprocess.run([sys.executable, str(SCRIPT)], cwd=self.repo, env=env, capture_output=True, text=True)

    def scenario_json(self, extra=None):
        scenario = {"rule_text": RULE_LINE}
        return json.dumps({
            "R1": scenario,
            "RETIRED": {**scenario, "retired": True},
            "ELSEWHERE": {**scenario, "toolkit_root": "~/dev/evals/x"},
            "LIVE_HOME": {**scenario, "toolkit_root": "~/.claude"},
            "LIVE_CHECKOUT": {**scenario, "toolkit_root": "~/dotfiles/claude/.claude"},
            **(extra or {}),
        })

    def test_a_staged_deletion_of_a_metered_rule_line_fails_and_names_it(self):
        self.install_stubs(self.scenario_json())
        self.write(CLAUDE_MD, "intro\nend\n")
        self.git("add", CLAUDE_MD)
        result = self.run_step()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("scenario R1", result.stderr)
        self.assertIn("scenario LIVE_HOME", result.stderr)
        self.assertIn("scenario LIVE_CHECKOUT", result.stderr)
        self.assertIn(CLAUDE_MD, result.stderr)
        self.assertIn(RULE_LINE, result.stderr)
        self.assertNotIn("RETIRED", result.stderr)
        self.assertNotIn("ELSEWHERE", result.stderr)

    def test_the_check_reads_the_staged_copy_not_the_work_tree(self):
        self.install_stubs(self.scenario_json())
        self.write(CLAUDE_MD, "intro\nend\n")
        self.git("add", CLAUDE_MD)
        self.write(CLAUDE_MD, f"intro\n{RULE_LINE}\nend\n")
        result = self.run_step()
        self.assertEqual(result.returncode, 1, result.stderr)

    def test_a_rule_line_only_in_the_staged_copy_passes(self):
        self.install_stubs(self.scenario_json())
        self.write(CLAUDE_MD, f"intro\nnew line\n{RULE_LINE}\nend\n")
        self.git("add", CLAUDE_MD)
        self.write(CLAUDE_MD, "intro\nend\n")
        result = self.run_step()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_rule_file_scenario_reads_that_file_and_an_agent_edit_triggers_it(self):
        agent_path = "claude/.claude/agents/x.md"
        agent_rule = {"AGENT_RULE": {"rule_text": "Agent rule.", "rule_file": "agents/x.md"}}
        self.install_stubs(self.scenario_json(agent_rule))
        self.write(agent_path, "intro\nAgent rule.\n")
        self.commit()
        self.write(agent_path, "intro\n")
        self.git("add", agent_path)
        result = self.run_step()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("scenario AGENT_RULE", result.stderr)

    def test_a_claude_md_edit_does_not_pick_a_rule_file_scenario(self):
        agent_rule = {"AGENT_RULE": {"rule_text": "Agent rule.", "rule_file": "agents/x.md"}}
        self.install_stubs(self.scenario_json(agent_rule))
        self.write("claude/.claude/agents/x.md", "intro\n")
        self.commit()
        self.write(CLAUDE_MD, f"intro\nnew line\n{RULE_LINE}\nend\n")
        self.git("add", CLAUDE_MD)
        result = self.run_step()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_nested_claude_md_edit_triggers_its_scenario(self):
        nested_path = "claude/.claude/scripts/CLAUDE.md"
        nested_rule = {"NESTED": {"rule_text": "Nested rule.", "rule_source": "scripts/CLAUDE.md"}}
        self.install_stubs(self.scenario_json(nested_rule))
        self.write(nested_path, "Nested rule.\n")
        self.commit()
        self.write(nested_path, "gone\n")
        self.git("add", nested_path)
        result = self.run_step()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("scenario NESTED", result.stderr)

    def test_a_rule_meter_that_cannot_be_imported_fails_closed(self):
        self.install_stubs(self.scenario_json())
        (self.evals / "bin" / "rule_meter.py").write_text("def broken(:\n", encoding="utf-8")
        self.write(CLAUDE_MD, "gone\n")
        self.git("add", CLAUDE_MD)
        result = self.run_step()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SyntaxError", result.stderr)

    def test_an_unrelated_staged_toolkit_change_passes(self):
        self.install_stubs(self.scenario_json())
        self.write(CLAUDE_MD, f"intro\nnew line\n{RULE_LINE}\nend\n")
        self.git("add", CLAUDE_MD)
        result = self.run_step()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_a_staged_change_outside_the_watched_paths_passes_without_a_check(self):
        self.install_stubs(self.scenario_json())
        self.write("other.txt", "x\n")
        self.git("add", "other.txt")
        result = self.run_step()
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_a_missing_agent_evals_dir_skips_with_a_note(self):
        self.write(CLAUDE_MD, "gone\n")
        self.git("add", CLAUDE_MD)
        result = self.run_step(evals=self.evals / "absent")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("were not checked", result.stderr)

    def test_a_staged_skill_deletion_fails_the_skill_list(self):
        self.install_stubs(self.scenario_json())
        self.git("rm", "-q", SKILL_PATH)
        # The stub reads the skills the index holds through ~/dotfiles, which GIT_DIR points at the repo under test.
        result = self.run_step()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("skill list", result.stderr)
        self.assertIn("missing ['alpha']", result.stderr)

    def test_a_staged_skill_edit_with_the_list_unchanged_passes(self):
        self.install_stubs(self.scenario_json())
        self.write(SKILL_PATH, "skill edited\n")
        self.git("add", SKILL_PATH)
        result = self.run_step()
        self.assertEqual((result.returncode, result.stderr), (0, ""))

    def test_the_skill_list_is_read_from_a_non_default_index(self):
        self.install_stubs(self.scenario_json())
        index_copy = self.home / "index-copy"
        shutil.copy(self.repo / ".git" / "index", index_copy)
        copy_env = {**os.environ, "GIT_INDEX_FILE": str(index_copy)}
        subprocess.run(["git", "rm", "-q", "--cached", SKILL_PATH], cwd=self.repo, env=copy_env, check=True)
        result = self.run_step(extra_env={"GIT_INDEX_FILE": str(index_copy)})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("missing ['alpha']", result.stderr)

    def test_the_rule_text_is_read_from_a_non_default_index(self):
        self.install_stubs(self.scenario_json())
        index_copy = self.home / "index-copy"
        shutil.copy(self.repo / ".git" / "index", index_copy)
        self.write(CLAUDE_MD, "intro\nend\n")
        copy_env = {**os.environ, "GIT_INDEX_FILE": str(index_copy)}
        subprocess.run(["git", "add", CLAUDE_MD], cwd=self.repo, env=copy_env, check=True)
        self.write(CLAUDE_MD, f"intro\n{RULE_LINE}\nend\n")
        result = self.run_step(extra_env={"GIT_INDEX_FILE": str(index_copy)})
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("scenario R1", result.stderr)

    @unittest.skipUnless((REAL_EVALS / "bin" / "rule_meter.py").is_file(), "no ~/agent-evals")
    def test_the_real_agent_evals_loads_and_passes_an_agent_edit_no_scenario_reads(self):
        self.write("claude/.claude/agents/unmetered-agent-for-test.md", "agent\n")
        self.git("add", "claude/.claude/agents/unmetered-agent-for-test.md")
        env = {**os.environ, "AGENT_EVALS_DIR": str(REAL_EVALS)}
        result = subprocess.run([sys.executable, str(SCRIPT)], cwd=self.repo, env=env, capture_output=True, text=True)
        self.assertEqual((result.returncode, result.stderr), (0, ""))


if __name__ == "__main__":
    unittest.main()
