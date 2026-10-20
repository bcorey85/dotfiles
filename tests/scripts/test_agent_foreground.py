"""Checks for agent-foreground.py, the PreToolUse hook that forces run_in_background:false on nested Agent calls.

Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import subprocess
import sys
import unittest

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or pathlib.Path.home() / ".claude" / "scripts") / "agent-foreground.py"


def payload(tool_input=None, tool_name="Agent", **extra):
    document = {"hook_event_name": "PreToolUse", "tool_name": tool_name,
                "tool_input": {"description": "d", "prompt": "p", "run_in_background": True}
                if tool_input is None else tool_input}
    document.update(extra)
    return json.dumps(document)


PARITY_CASES = [
    {"name": "top level agent", "stdin": payload()},
    {"name": "nested agent_type", "stdin": payload(agent_type="coder")},
    {"name": "nested agent_id", "stdin": payload(agent_id="abc")},
    {"name": "nested both", "stdin": payload(agent_type="coder", agent_id="abc")},
    {"name": "nested non-agent tool", "stdin": payload(tool_name="Bash", agent_type="coder")},
    {"name": "skip hooks", "stdin": payload(agent_type="coder"), "env": {"CLAUDE_SKIP_HOOKS": "1"}},
    {"name": "empty skip hooks still runs", "stdin": payload(agent_type="coder"), "env": {"CLAUDE_SKIP_HOOKS": ""}},
    {"name": "already foreground", "stdin": payload({"run_in_background": False, "prompt": "p"}, agent_id="a")},
    {"name": "no run_in_background key", "stdin": payload({"prompt": "p", "model": "haiku"}, agent_id="a")},
    {"name": "key order kept", "stdin": payload({"z": 1, "run_in_background": True, "a": 2}, agent_id="a")},
    {"name": "tool_input null", "stdin": '{"tool_name":"Agent","tool_input":null,"agent_id":"a"}'},
    {"name": "tool_input missing", "stdin": '{"tool_name":"Agent","agent_id":"a"}'},
    {"name": "tool_input string", "stdin": '{"tool_name":"Agent","tool_input":"x","agent_id":"a"}'},
    {"name": "tool_input array", "stdin": '{"tool_name":"Agent","tool_input":[1],"agent_id":"a"}'},
    {"name": "empty agent_id blocks fallback", "stdin": payload(agent_id="", agent_type="coder")},
    {"name": "null agent_id falls back", "stdin": payload(agent_id=None, agent_type="coder")},
    {"name": "false agent_id falls back", "stdin": payload(agent_id=False, agent_type="coder")},
    {"name": "empty both", "stdin": payload(agent_id="", agent_type="")},
    {"name": "numeric agent_id", "stdin": payload(agent_id=0)},
    {"name": "object agent_id", "stdin": payload(agent_id={"a": 1})},
    {"name": "unicode and escapes", "stdin": payload({"prompt": "café \"q\" \\ \x7f \x01 \U0001f600 \n\t"}, agent_id="a")},
    {"name": "nested values", "stdin": payload({"a": {"b": [1, 2.5, None, True, "x"]}, "n": 10}, agent_id="a")},
    {"name": "empty stdin", "stdin": ""},
    {"name": "invalid json", "stdin": "not json"},
    {"name": "array payload", "stdin": "[1]"},
    {"name": "null payload", "stdin": "null"},
    {"name": "number tool name", "stdin": '{"tool_name":5,"agent_id":"a"}'},
]
TYPICAL = {"name": "typical", "stdin": payload({"description": "x", "prompt": "y" * 400, "subagent_type": "coder"},
                                                 agent_type="review-loop", agent_id="abc123")}


def run_hook(stdin, env=None):
    environment = {key: value for key, value in os.environ.items() if key != "CLAUDE_SKIP_HOOKS"}
    environment.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True, env=environment)


class AgentForegroundTest(unittest.TestCase):
    def assert_silent(self, stdin, env=None):
        finished = run_hook(stdin, env)
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))

    def test_top_level_call_is_untouched(self):
        self.assert_silent(payload())

    def test_skip_hooks_exits_without_output(self):
        self.assert_silent(payload(agent_type="coder"), {"CLAUDE_SKIP_HOOKS": "1"})

    def test_non_agent_tool_is_untouched(self):
        self.assert_silent(payload(tool_name="Bash", agent_type="coder"))

    def test_nested_call_is_forced_to_foreground(self):
        for extra in ({"agent_type": "coder"}, {"agent_id": "abc"}, {"agent_type": "coder", "agent_id": "abc"}):
            finished = run_hook(payload(**extra))
            self.assertEqual(finished.returncode, 0)
            self.assertEqual(finished.stderr, "")
            self.assertEqual(json.loads(finished.stdout), {"hookSpecificOutput": {
                "hookEventName": "PreToolUse", "permissionDecision": "allow",
                "updatedInput": {"description": "d", "prompt": "p", "run_in_background": False}}})

    def test_output_is_compact_json_on_one_line(self):
        finished = run_hook(payload({"b": 1, "a": 2}, agent_id="x"))
        self.assertEqual(finished.stdout,
                         '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow",'
                         '"updatedInput":{"b":1,"a":2,"run_in_background":false}}}\n')

    def test_existing_key_keeps_its_position(self):
        finished = run_hook(payload({"z": 1, "run_in_background": True, "a": 2}, agent_id="x"))
        self.assertIn('"updatedInput":{"z":1,"run_in_background":false,"a":2}', finished.stdout)

    def test_missing_or_null_tool_input_becomes_only_the_flag(self):
        for stdin in ('{"tool_name":"Agent","tool_input":null,"agent_id":"a"}', '{"tool_name":"Agent","agent_id":"a"}'):
            self.assertIn('"updatedInput":{"run_in_background":false}', run_hook(stdin).stdout)

    def test_non_object_tool_input_fails_open(self):
        for value in ('"x"', "[1]", "5"):
            self.assert_silent('{"tool_name":"Agent","tool_input":%s,"agent_id":"a"}' % value)

    def test_empty_agent_id_hides_agent_type(self):
        self.assert_silent(payload(agent_id="", agent_type="coder"))

    def test_null_or_false_agent_id_falls_back_to_agent_type(self):
        for value in (None, False):
            self.assertIn("allow", run_hook(payload(agent_id=value, agent_type="coder")).stdout)

    def test_empty_ids_pass_untouched(self):
        self.assert_silent(payload(agent_id="", agent_type=""))

    def test_zero_agent_id_counts_as_nested(self):
        self.assertIn("allow", run_hook(payload(agent_id=0)).stdout)

    def test_unicode_kept_and_del_escaped_like_jq(self):
        finished = run_hook(payload({"prompt": "café \x7f \x01"}, agent_id="a"))
        self.assertIn("café \\u007f \\u0001", finished.stdout)

    def test_bad_input_fails_open(self):
        for stdin in ("", "not json", "[1]", "null", '{"tool_name":5,"agent_id":"a"}'):
            self.assert_silent(stdin)


if __name__ == "__main__":
    unittest.main()
