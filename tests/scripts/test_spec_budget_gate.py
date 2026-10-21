"""Checks for spec-budget-gate.py, the PreToolUse hook that denies edits growing the eng-spec planning tree past its
word budget."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPTS_DIR = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or pathlib.Path.home() / ".claude" / "scripts")
SCRIPT = SCRIPTS_DIR / "spec-budget-gate.py"


def words(count):
    return " ".join("w" for _ in range(count)) + "\n"


class SpecBudgetGateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = pathlib.Path(self.tmp.name) / "claude"
        self.base.mkdir()

    def put(self, relative, content):
        path = self.base / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return str(path)

    def run_hook(self, payload, env=None):
        environment = {"PATH": os.environ["PATH"], "HOME": self.tmp.name, "TMPDIR": self.tmp.name}
        environment.update(env or {})
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                              env=environment)

    def write(self, path, content, env=None):
        return self.run_hook({"tool_name": "Write", "tool_input": {"file_path": path, "content": content}}, env)

    def edit(self, path, old, new, env=None):
        return self.run_hook({"tool_name": "Edit", "tool_input": {"file_path": path, "old_string": old,
                                                                  "new_string": new}}, env)

    def assert_allowed(self, finished):
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def denial(self, finished):
        self.assertEqual(finished.returncode, 0)
        self.assertTrue(finished.stdout.endswith("\n"))
        decision = json.loads(finished.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        return decision["permissionDecisionReason"]

    def test_invalid_input_and_unguarded_paths_pass(self):
        for stdin in ("not json", "", json.dumps({"tool_input": {}})):
            self.assert_allowed(self.run_hook(stdin))
        self.assert_allowed(self.write(str(self.base / "skills/other/SKILL.md"), words(20000)))
        self.assert_allowed(self.write(str(self.base / "agents/coder.md"), words(20000)))

    def test_templates_are_exempt(self):
        self.assert_allowed(self.write(str(self.base / "skills/eng-spec/templates/t.md"), words(20000)))

    def test_path_without_skills_or_agents_directory_passes(self):
        self.assert_allowed(self.write("/tmp/x/spec-questions.md".replace("/tmp/x", "/nonexistent"), words(20000)))

    def test_other_tools_pass(self):
        path = self.put("skills/eng-spec/SKILL.md", words(10))
        payload = {"tool_name": "NotebookEdit", "tool_input": {"file_path": path, "new_source": words(20000)}}
        self.assert_allowed(self.run_hook(payload))
        self.assert_allowed(self.run_hook({"tool_input": {"file_path": path, "content": words(20000)}}))

    def test_resident_ceiling_denies_growing_spine(self):
        path = self.put("skills/eng-spec/SKILL.md", words(800))
        self.put("skills/eng-spec/phases/a.md", words(600))
        reason = self.denial(self.write(path, words(901)))
        self.assertEqual(reason,
                         "spec-budget-gate: this edit puts eng-spec's resident load at ~1501 words (ceiling 1500) — "
                         "SKILL.md (901) plus its largest phase file (600). That is what is actually in context "
                         "during a run and what has to survive compaction. Cut words from the spine or from that "
                         "phase file in the same change, or move a rule into the agent that is the only one who "
                         "applies it. Splitting a phase file only helps if it is a real phase boundary. Ask the "
                         "user to raise RESIDENT_CEILING; never raise it yourself.")

    def test_resident_ceiling_at_limit_passes(self):
        path = self.put("skills/eng-spec/SKILL.md", words(800))
        self.put("skills/eng-spec/phases/a.md", words(600))
        self.assert_allowed(self.write(path, words(900)))

    def test_shrinking_edit_passes_even_when_over_resident_ceiling(self):
        path = self.put("skills/eng-spec/SKILL.md", words(1000))
        self.put("skills/eng-spec/phases/a.md", words(900))
        self.assert_allowed(self.write(path, words(990)))
        self.assert_allowed(self.edit(path, "w w w", "w"))

    def test_largest_phase_file_counts_and_edited_phase_is_prospective(self):
        self.put("skills/eng-spec/SKILL.md", words(900))
        small = self.put("skills/eng-spec/phases/small.md", words(100))
        self.put("skills/eng-spec/phases/big.md", words(500))
        self.assert_allowed(self.write(small, words(550)))
        reason = self.denial(self.write(small, words(700)))
        self.assertIn("~1600 words", reason)
        self.assertIn("largest phase file (700)", reason)

    def test_new_phase_file_counts_and_nested_phase_files_are_found(self):
        self.put("skills/eng-spec/SKILL.md", words(900))
        self.put("skills/eng-spec/phases/deep/nested.md", words(650))
        reason = self.denial(self.write(str(self.base / "skills/eng-spec/phases/new.md"), words(10)))
        self.assertIn("~1550 words", reason)

    def test_edit_counts_added_minus_deleted_words(self):
        path = self.put("skills/eng-spec/SKILL.md", words(1000))
        self.put("skills/eng-spec/phases/a.md", words(499))
        self.assert_allowed(self.edit(path, "w w w w", "w w w w w"))
        reason = self.denial(self.edit(path, "w", "w w w w w"))
        self.assertIn("SKILL.md (1004)", reason)

    def test_multiedit_sums_every_edit(self):
        path = self.put("skills/eng-spec/SKILL.md", words(1000))
        self.put("skills/eng-spec/phases/a.md", words(496))
        edits = [{"old_string": "w", "new_string": "w w w"}, {"old_string": "w", "new_string": "w w w"}]
        self.assert_allowed(self.run_hook({"tool_name": "MultiEdit", "tool_input": {"file_path": path, "edits": edits}}))
        edits.append({"old_string": "", "new_string": "w w"})
        reason = self.denial(self.run_hook({"tool_name": "MultiEdit",
                                            "tool_input": {"file_path": path, "edits": edits}}))
        self.assertIn("SKILL.md (1006)", reason)

    def test_total_ceiling_denies_growth(self):
        path = self.put("skills/eng-spec/SKILL.md", words(100))
        self.put("skills/_shared/plan-format.md", words(8000))
        self.put("agents/spec-research.md", words(550))
        self.assert_allowed(self.write(path, words(150)))
        reason = self.denial(self.write(path, words(151)))
        self.assertEqual(reason,
                         "spec-budget-gate: this edit grows the planning tree to ~8701 words (ceiling 8700, "
                         "currently 8650). The planning system grows only by displacement — delete words elsewhere "
                         "in the guarded set (eng-spec, spec-* agents, its _shared files) in the same change, or "
                         "ask the user to raise TOTAL_CEILING in spec-budget-gate.py. Never raise it yourself.")

    def test_total_covers_every_guarded_agent_and_shared_file(self):
        names = ["agents/spec-questions.md", "agents/spec-leak-check.md", "agents/spec-research.md",
                 "agents/spec-criteria.md", "agents/goal-blind-researcher.md",
                 "skills/_shared/design-decision-format.md", "skills/_shared/plan-format.md",
                 "skills/_shared/closing-phases.md"]
        for name in names:
            self.put(name, words(1000))
        path = self.put("skills/eng-spec/SKILL.md", words(100))
        reason = self.denial(self.write(str(self.base / "agents/spec-questions.md"), words(1601)))
        self.assertIn("~8701 words", reason)
        self.assertIn("currently 8100", reason)
        self.assert_allowed(self.write(path, words(100)))

    def test_templates_and_unrelated_files_do_not_count_toward_total(self):
        path = self.put("skills/eng-spec/SKILL.md", words(100))
        self.put("skills/eng-spec/templates/t.md", words(9000))
        self.put("agents/coder.md", words(9000))
        self.put("skills/other/SKILL.md", words(9000))
        self.assert_allowed(self.write(path, words(200)))

    def test_total_shrink_passes_when_over_ceiling(self):
        path = self.put("skills/eng-spec/SKILL.md", words(100))
        self.put("skills/_shared/plan-format.md", words(9000))
        self.assert_allowed(self.write(path, words(50)))

    def test_agent_base_is_derived_from_agents_directory(self):
        self.put("skills/_shared/plan-format.md", words(8650))
        path = str(self.base / "agents/spec-criteria.md")
        self.assert_allowed(self.write(path, words(50)))
        self.denial(self.write(path, words(51)))

    def test_skip_variable_disables_gate(self):
        path = self.put("skills/eng-spec/SKILL.md", words(800))
        self.put("skills/eng-spec/phases/a.md", words(600))
        self.assert_allowed(self.write(path, words(2000), env={"CLAUDE_SKIP_HOOKS": "1"}))

    def test_new_file_has_zero_old_words(self):
        self.put("skills/eng-spec/phases/a.md", words(1400))
        path = str(self.base / "skills/eng-spec/SKILL.md")
        self.assert_allowed(self.write(path, words(100)))
        self.denial(self.write(path, words(101)))

    def test_missing_edit_fields_count_as_empty(self):
        path = self.put("skills/eng-spec/SKILL.md", words(10))
        self.assert_allowed(self.run_hook({"tool_name": "Edit", "tool_input": {"file_path": path}}))


if __name__ == "__main__":
    unittest.main()
