"""Checks for agent_model_guard.py, the PreToolUse hook that blocks Agent calls with Opus or no model pin.

Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.GATES_DIR) / "agent_model_guard.py"

OPUS_STDERR = (
    "[agent-model-guard] BLOCKED: Agent call sets model containing 'opus' at the call site.\n"
    "Call-site Opus is forbidden. The only legitimate way to run a subagent on Opus\n"
    "is a 'model: opus' line in the agent file's own frontmatter.\n"
    "Use 'haiku' (read-only/lookup) or 'sonnet' (fan-out implementation) at the call site.\n")


def agent_payload(model=None, subagent="coder", tool_name="Agent", **extra):
    tool_input = {"description": "x", "prompt": "y"}
    if subagent is not None:
        tool_input["subagent_type"] = subagent
    if model is not None:
        tool_input["model"] = model
    payload = {"hook_event_name": "PreToolUse", "tool_name": tool_name, "tool_input": tool_input}
    payload.update(extra)
    return json.dumps(payload)


# Each case: name, stdin, env, files written under HOME or the project dir.
PARITY_CASES = [
    {"name": "non-agent tool", "stdin": agent_payload(tool_name="Bash")},
    {"name": "explicit sonnet", "stdin": agent_payload("sonnet")},
    {"name": "explicit haiku", "stdin": agent_payload("haiku")},
    {"name": "opus lower", "stdin": agent_payload("opus")},
    {"name": "opus mixed case", "stdin": agent_payload("Claude-OPUS-4")},
    {"name": "inherit", "stdin": agent_payload("inherit")},
    {"name": "inherit upper", "stdin": agent_payload("INHERIT")},
    {"name": "opus beats inherit", "stdin": agent_payload("opus-inherit")},
    {"name": "invalid subagent", "stdin": agent_payload("sonnet", subagent="bad name!")},
    {"name": "invalid subagent path", "stdin": agent_payload(None, subagent="../x")},
    {"name": "invalid subagent newline", "stdin": agent_payload(None, subagent="ok\nnot")},
    {"name": "invalid subagent unicode", "stdin": agent_payload("sonnet", subagent="café\x7f")},
    {"name": "skip hooks", "stdin": agent_payload("opus"), "env": {"CLAUDE_SKIP_HOOKS": "1"}},
    {"name": "no model no file", "stdin": agent_payload(None, subagent="ghost")},
    {"name": "empty model no file", "stdin": agent_payload("", subagent="ghost")},
    {"name": "no subagent no model", "stdin": agent_payload(None, subagent=None)},
    {
        "name": "home frontmatter pin",
        "stdin": agent_payload(None, subagent="pinned"),
        "files": {"home/.claude/agents/pinned.md": "---\nname: pinned\nmodel: sonnet\n---\nbody\n"},
    },
    {
        "name": "home no frontmatter pin",
        "stdin": agent_payload(None, subagent="loose"),
        "files": {"home/.claude/agents/loose.md": "---\nname: loose\n---\nbody\n"},
    },
    {
        "name": "indented model line is not a pin",
        "stdin": agent_payload(None, subagent="indented"),
        "files": {"home/.claude/agents/indented.md": "---\n  model: sonnet\n---\n"},
    },
    {
        "name": "project pin",
        "stdin": agent_payload(None, subagent="projpin"),
        "project": True,
        "files": {"project/.claude/agents/projpin.md": "model: opus\n"},
    },
    {
        "name": "project file without pin does not fall back to home",
        "stdin": agent_payload(None, subagent="both"),
        "project": True,
        "files": {"project/.claude/agents/both.md": "no pin\n", "home/.claude/agents/both.md": "model: sonnet\n"},
    },
    {
        "name": "project dir without file falls back to home",
        "stdin": agent_payload(None, subagent="fallback"),
        "project": True,
        "files": {"home/.claude/agents/fallback.md": "model: haiku\n"},
    },
    {"name": "numeric model", "stdin": agent_payload(5)},
    {"name": "false model is empty", "stdin": agent_payload(False, subagent="ghost")},
    {
        "name": "null model is empty",
        "stdin": agent_payload(None, subagent="ghost").replace('"y"}', '"y", "model": null}'),
    },
    {"name": "empty stdin", "stdin": ""},
    {"name": "whitespace stdin", "stdin": "  \n"},
    {"name": "null document", "stdin": "null"},
    {"name": "tool_input null", "stdin": '{"tool_name":"Agent","tool_input":null}'},
    {"name": "tool_input missing", "stdin": '{"tool_name":"Agent"}'},
    {"name": "tool_input string", "stdin": '{"tool_name":"Agent","tool_input":"x"}'},
    {"name": "non-agent with string tool_input", "stdin": '{"tool_name":"Bash","tool_input":"x"}'},
    {"name": "array payload", "stdin": "[1]"},
    {"name": "string payload", "stdin": '"s"'},
    {"name": "number tool name", "stdin": '{"tool_name":7}'},
    {"name": "unicode subagent in deny", "stdin": agent_payload(None, subagent="ü")},
]


def run_hook(stdin, env=None, project=False, files=None):
    with tempfile.TemporaryDirectory() as scratch:
        home = pathlib.Path(scratch) / "home"
        project_dir = pathlib.Path(scratch) / "project"
        for relative, content in (files or {}).items():
            target = pathlib.Path(scratch) / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content)
        home.mkdir(exist_ok=True)
        project_dir.mkdir(exist_ok=True)
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CLAUDE_SKIP_HOOKS", "CLAUDE_PROJECT_DIR")}
        environment.update(HOME=str(home), TMPDIR=scratch)
        if project:
            environment["CLAUDE_PROJECT_DIR"] = str(project_dir)
        environment.update(env or {})
        return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                              env=environment)


def decision_of(finished):
    return json.loads(finished.stdout)["hookSpecificOutput"]


class AgentModelGuardTest(unittest.TestCase):
    def assert_passes(self, **kwargs):
        finished = run_hook(**kwargs)
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stdout, "")
        self.assertEqual(finished.stderr, "")

    def test_skip_hooks_passes_everything(self):
        self.assert_passes(stdin=agent_payload("opus"), env={"CLAUDE_SKIP_HOOKS": "1"})

    def test_non_agent_tool_passes(self):
        self.assert_passes(stdin=agent_payload("opus", tool_name="Bash"))

    def test_empty_stdin_passes(self):
        self.assert_passes(stdin="")

    def test_explicit_model_passes(self):
        self.assert_passes(stdin=agent_payload("sonnet"))
        self.assert_passes(stdin=agent_payload("haiku", subagent="ghost"))

    def test_opus_denied_with_stderr(self):
        finished = run_hook(stdin=agent_payload("Opus"))
        self.assertEqual(finished.returncode, 0)
        self.assertEqual(finished.stderr, OPUS_STDERR)
        decision = decision_of(finished)
        self.assertEqual(decision["hookEventName"], "PreToolUse")
        self.assertEqual(decision["permissionDecision"], "deny")
        self.assertIn("Call-site Opus is forbidden", decision["permissionDecisionReason"])
        self.assertTrue(finished.stdout.endswith("}\n"))
        self.assertIn('"permissionDecision":"deny"', finished.stdout)

    def test_opus_checked_before_inherit(self):
        finished = run_hook(stdin=agent_payload("inherit-opus"))
        self.assertIn("containing 'opus'", finished.stderr)

    def test_inherit_denied(self):
        finished = run_hook(stdin=agent_payload("Inherit"))
        self.assertIn("containing 'inherit'", finished.stderr)
        self.assertIn("resolves to the orchestrator model", decision_of(finished)["permissionDecisionReason"])
        self.assertEqual(decision_of(finished)["permissionDecision"], "deny")

    def test_invalid_subagent_denied_without_stderr(self):
        finished = run_hook(stdin=agent_payload("sonnet", subagent="a b"))
        self.assertEqual(finished.stderr, "")
        self.assertEqual(decision_of(finished)["permissionDecisionReason"],
                         "Agent call to subagent_type='a b' is invalid. subagent_type must contain only "
                         "alphanumeric characters, hyphens, and underscores.")

    def test_subagent_with_inner_newline_is_invalid(self):
        finished = run_hook(stdin=agent_payload("sonnet", subagent="ok\nx"))
        self.assertEqual(decision_of(finished)["permissionDecision"], "deny")

    def test_subagent_trailing_newline_is_stripped_like_the_shell(self):
        self.assert_passes(stdin=agent_payload("sonnet", subagent="ok\n"))

    def test_missing_pin_denied(self):
        finished = run_hook(stdin=agent_payload(None, subagent="ghost"))
        self.assertEqual(finished.returncode, 0)
        self.assertIn("subagent_type='ghost' has no model pin.", finished.stderr)
        self.assertTrue(finished.stderr.endswith('      model: "sonnet" - fan-out implementation or analysis\n'))
        self.assertIn(
            "has no model pin. No 'model:' frontmatter found", decision_of(finished)["permissionDecisionReason"]
        )

    def test_empty_model_string_counts_as_missing(self):
        finished = run_hook(stdin=agent_payload("", subagent="ghost"))
        self.assertEqual(decision_of(finished)["permissionDecision"], "deny")

    def test_home_frontmatter_pin_passes(self):
        self.assert_passes(stdin=agent_payload(None, subagent="pinned"),
                           files={"home/.claude/agents/pinned.md": "---\nmodel: opus\n---\n"})

    def test_frontmatter_without_model_denied(self):
        finished = run_hook(stdin=agent_payload(None, subagent="loose"),
                            files={"home/.claude/agents/loose.md": "---\nname: loose\n---\n"})
        self.assertEqual(decision_of(finished)["permissionDecision"], "deny")

    def test_indented_model_line_is_not_a_pin(self):
        finished = run_hook(stdin=agent_payload(None, subagent="x"),
                            files={"home/.claude/agents/x.md": "  model: sonnet\n"})
        self.assertEqual(decision_of(finished)["permissionDecision"], "deny")

    def test_project_pin_passes(self):
        self.assert_passes(stdin=agent_payload(None, subagent="p"), project=True,
                           files={"project/.claude/agents/p.md": "model: sonnet\n"})

    def test_project_file_without_pin_does_not_fall_back_to_home(self):
        finished = run_hook(stdin=agent_payload(None, subagent="p"), project=True,
                            files={"project/.claude/agents/p.md": "x\n", "home/.claude/agents/p.md": "model: sonnet\n"})
        self.assertEqual(decision_of(finished)["permissionDecision"], "deny")

    def test_project_dir_without_file_falls_back_to_home(self):
        self.assert_passes(stdin=agent_payload(None, subagent="p"), project=True,
                           files={"home/.claude/agents/p.md": "model: haiku\n"})

    def test_missing_subagent_type_denied(self):
        finished = run_hook(stdin=agent_payload(None, subagent=None))
        self.assertIn("subagent_type=''", finished.stderr)

    def test_deny_output_escapes_like_jq(self):
        finished = run_hook(stdin=agent_payload(None, subagent="ü"))
        self.assertIn("subagent_type='ü' is invalid", finished.stdout)
        finished = run_hook(stdin=agent_payload("sonnet", subagent="a\x7f"))
        self.assertIn("\\u007f", finished.stdout)

    def test_invalid_json_exits_five(self):
        finished = run_hook(stdin="not json")
        self.assertEqual(finished.returncode, 5)
        self.assertEqual(finished.stdout, "")

    def test_non_object_payload_exits_five_with_jq_message(self):
        finished = run_hook(stdin="[1]")
        self.assertEqual(finished.returncode, 5)
        self.assertEqual(finished.stderr, 'jq: error (at <stdin>:0): Cannot index array with string ("tool_name")\n')

    def test_string_tool_input_exits_five_for_agent_only(self):
        self.assertEqual(run_hook(stdin='{"tool_name":"Agent","tool_input":"x"}').returncode, 5)
        self.assertEqual(run_hook(stdin='{"tool_name":"Bash","tool_input":"x"}').returncode, 0)

    def test_null_document_passes(self):
        self.assert_passes(stdin="null")


if __name__ == "__main__":
    unittest.main()
