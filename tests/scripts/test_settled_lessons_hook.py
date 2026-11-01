"""Checks for settled_lessons_hook.py, the PreToolUse hook that shows a toolkit component's settled results before the
first edit of it in a session.

Set SETTLED_LESSONS_HOOK_SCRIPT to run against another copy, such as a staged one."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("SETTLED_LESSONS_HOOK_SCRIPT")
                      or toolkit_paths.GATES_DIR / "settled_lessons_hook.py")

PAGE = """---
type: Agent
resource: "file://{resource}"
---

<!-- generated -->

# Settled

## Keep

- keep the rule {name}

## Avoid

- avoid the other thing

# Findings

- a finding line that is not a lesson
"""


class SettledLessonsHookTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = pathlib.Path(temp.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.evals = self.root / "evals"
        self.components = self.evals / "components"
        self.toolkit = self.root / "dotfiles" / "claude" / ".claude"

    def add_page(self, component, resource_tail=""):
        resource = f"/x/dotfiles/claude/.claude/{resource_tail}"
        page = self.components / (component + ".md")
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(PAGE.format(resource=resource, name=component))

    def run_hook(self, file_path, session="s1"):
        payload = {"session_id": session, "tool_name": "Edit", "tool_input": {"file_path": str(file_path)}}
        environment = dict(os.environ, HOME=str(self.home), AGENT_EVALS_DIR=str(self.evals))
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(payload), capture_output=True,
                                  text=True, env=environment)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        return finished.stdout

    def context_of(self, output):
        decision = json.loads(output)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertNotIn("permissionDecision", decision)
        return decision["additionalContext"]

    def assert_shows(self, file_path, component):
        context = self.context_of(self.run_hook(file_path))
        first_line = context.splitlines()[0]
        self.assertEqual(first_line, f"Settled results for {component}; do not retest or reverse these without new "
                                     "evidence:")
        self.assertIn(f"keep the rule {component}", context)
        self.assertIn("avoid the other thing", context)
        self.assertNotIn("a finding line", context)

    def test_an_agent_path_shows_that_agents_settled_section(self):
        self.add_page("agent/coder")
        self.assert_shows(self.toolkit / "agents" / "coder.md", "agent/coder")

    def test_a_skill_subfile_and_a_shared_file_map_to_their_pages(self):
        self.add_page("skill/eng-spec")
        self.add_page("shared/closing-phases")
        self.assert_shows(self.toolkit / "skills" / "eng-spec" / "refs" / "a.md", "skill/eng-spec")
        self.assert_shows(self.toolkit / "skills" / "_shared" / "closing-phases.md", "shared/closing-phases")

    def test_a_script_is_found_through_the_resource_of_a_page(self):
        self.add_page("script/aaa-other", "scripts/code/other.py")
        self.add_page("script/aaa-near", "scripts/code/code_wait.py.bak")
        self.add_page("script/aaa-suffix", "scripts/xscripts/code/code_wait.py")
        self.add_page("script/code-wait", "scripts/code/code_wait.py")
        self.assert_shows(self.toolkit / "scripts" / "code" / "code_wait.py", "script/code-wait")

    def test_a_path_through_the_home_claude_symlink_maps_to_the_dotfiles_path(self):
        self.add_page("agent/coder")
        (self.toolkit / "agents").mkdir(parents=True)
        (self.home / ".claude").symlink_to(self.toolkit)
        self.assert_shows(self.home / ".claude" / "agents" / "coder.md", "agent/coder")

    def test_a_missing_page_folder_or_section_is_silent(self):
        self.assertEqual(self.run_hook(self.toolkit / "agents" / "coder.md"), "")
        page = self.components / "agent" / "coder.md"
        page.parent.mkdir(parents=True)
        page.write_text("---\ntype: Agent\n---\n\n# Findings\n\n- x\n")
        self.assertEqual(self.run_hook(self.toolkit / "agents" / "coder.md"), "")

    def test_a_file_outside_the_toolkit_is_silent(self):
        self.add_page("agent/coder")
        self.assertEqual(self.run_hook(self.root / "other" / "agents" / "coder.md"), "")

    def test_a_second_edit_in_the_same_session_is_silent_but_a_new_session_shows_again(self):
        self.add_page("agent/coder")
        edited = self.toolkit / "agents" / "coder.md"
        self.assertNotEqual(self.run_hook(edited), "")
        self.assertEqual(self.run_hook(edited), "")
        self.assertNotEqual(self.run_hook(edited, session="s2"), "")

    def test_a_malformed_payload_exits_0_and_names_the_gate_on_stderr(self):
        environment = dict(os.environ, HOME=str(self.home), AGENT_EVALS_DIR=str(self.evals))
        finished = subprocess.run([sys.executable, str(SCRIPT)], input="not json", capture_output=True, text=True,
                                  env=environment)
        self.assertEqual(finished.returncode, 0, finished.stderr)
        self.assertEqual(finished.stdout, "")
        self.assertTrue(finished.stderr.startswith("settled-lessons-hook: "), finished.stderr)


if __name__ == "__main__":
    unittest.main()
