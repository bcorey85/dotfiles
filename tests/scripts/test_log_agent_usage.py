"""Checks for log_agent_usage.py, the per-dispatch Agent token telemetry hook.

Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

import toolkit_paths

os.environ.pop("CLAUDE_TOOLKIT_TELEMETRY", None)  # the switch file alone decides in these tests

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or toolkit_paths.TELEMETRY_DIR) / "log_agent_usage.py"
TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
KEYS = ["ts", "repo", "agent", "model", "desc", "tokens", "toolUses", "durationMs", "reportChars", "noResult",
        "respKeys"]


def post(tool_input=None, tool_response="absent", event="PostToolUse"):
    document = {"hook_event_name": event, "tool_name": "Agent",
                "tool_input": {"subagent_type": "coder", "model": "sonnet", "description": "Fix it"}
                if tool_input is None else tool_input}
    if tool_response != "absent":
        document["tool_response"] = tool_response
    return json.dumps(document)


def sync_response(**extra):
    response = {"status": "completed", "content": [{"type": "text", "text": "All done, 3 files changed."}],
                "totalTokens": 1234, "totalToolUseCount": 7, "totalDurationMs": 4567}
    response.update(extra)
    return response


PARITY_CASES = [
    {"name": "sync response", "stdin": post(tool_response=sync_response())},
    {"name": "no response", "stdin": post()},
    {"name": "null response", "stdin": post(tool_response=None)},
    {"name": "string response", "stdin": post(tool_response="plain text")},
    {"name": "number response", "stdin": post(tool_response=5)},
    {"name": "bool response", "stdin": post(tool_response=True)},
    {"name": "array response", "stdin": post(tool_response=[{"a": 1}, 2, 3])},
    {"name": "empty array response", "stdin": post(tool_response=[])},
    {"name": "empty object response", "stdin": post(tool_response={})},
    {
        "name": "async response",
        "stdin": post(tool_response={"status": "async_launched", "outputFile": "/x", "agentId": "a1"}),
    },
    {"name": "string content", "stdin": post(tool_response={"content": "found nothing to report"})},
    {"name": "no result phrases", "stdin": post(tool_response={"content": "I Could Not Find it; NO MATCHES"})},
    {"name": "couldn't phrase", "stdin": post(tool_response={"content": "Couldn\u2019t find x and couldn't find y"})},
    {"name": "does not exist phrase", "stdin": post(tool_response={"content": "the file does not exist"})},
    {"name": "plain content", "stdin": post(tool_response={"content": "ok\nmultiline\nreport"})},
    {"name": "empty string content", "stdin": post(tool_response={"content": ""})},
    {"name": "content is object", "stdin": post(tool_response={"content": {"text": "x"}})},
    {"name": "content is number", "stdin": post(tool_response={"content": 5})},
    {
        "name": "content array mixed",
        "stdin": post(
            tool_response={
                "content": [
                    {"text": "a"},
                    "b",
                    None,
                    {"x": 1},
                    {"text": None},
                    {"text": False},
                    {"text": 5},
                    {"text": True},
                    [1],
                ]
            }
        ),
    },
    {"name": "content array object text", "stdin": post(tool_response={"content": [{"text": {"a": 1}}]})},
    {"name": "content array list text", "stdin": post(tool_response={"content": [{"text": [1]}]})},
    {"name": "content empty array", "stdin": post(tool_response={"content": []})},
    {"name": "content unicode length", "stdin": post(tool_response={"content": "caf\u00e9 \U0001f600 \u65e5\u672c"})},
    {"name": "usage total_tokens", "stdin": post(tool_response={"usage": {"total_tokens": 99, "output_tokens": 5}})},
    {"name": "usage output_tokens only", "stdin": post(tool_response={"usage": {"output_tokens": 5}})},
    {"name": "top total_tokens", "stdin": post(tool_response={"total_tokens": 42})},
    {"name": "zero totalTokens is kept", "stdin": post(tool_response={"totalTokens": 0, "total_tokens": 9})},
    {"name": "false totalTokens falls through", "stdin": post(tool_response={"totalTokens": False, "total_tokens": 9})},
    {
        "name": "null totalTokens falls through",
        "stdin": post(tool_response={"totalTokens": None, "usage": {"total_tokens": 8}}),
    },
    {"name": "usage string errors", "stdin": post(tool_response={"usage": "x"})},
    {"name": "usage string but totalTokens set", "stdin": post(tool_response={"totalTokens": 3, "usage": "x"})},
    {"name": "usage array errors", "stdin": post(tool_response={"usage": [1]})},
    {"name": "usage null", "stdin": post(tool_response={"usage": None})},
    {"name": "tool_uses and duration_ms", "stdin": post(tool_response={"tool_uses": 3, "duration_ms": 12})},
    {
        "name": "float and string tokens",
        "stdin": post(tool_response={"totalTokens": 12.5, "tool_uses": "3", "duration_ms": 1.0}),
    },
    {"name": "big number", "stdin": post(tool_response={"totalTokens": 12345678901234567890})},
    {"name": "no tool_input fields", "stdin": post({})},
    {"name": "tool_input null", "stdin": '{"hook_event_name":"PostToolUse","tool_input":null}'},
    {"name": "tool_input missing", "stdin": '{"hook_event_name":"PostToolUse"}'},
    {"name": "tool_input string errors", "stdin": '{"hook_event_name":"PostToolUse","tool_input":"x"}'},
    {"name": "empty model and agent", "stdin": post({"model": "", "subagent_type": ""})},
    {"name": "false model", "stdin": post({"model": False, "subagent_type": False})},
    {"name": "numeric agent", "stdin": post({"subagent_type": 5, "model": ["a"]})},
    {"name": "long description", "stdin": post({"description": "x" * 200})},
    {"name": "description unicode cut", "stdin": post({"description": "\u00e9" * 100 + "\U0001f600" * 10})},
    {"name": "description 80 exactly", "stdin": post({"description": "y" * 80})},
    {"name": "description number errors", "stdin": post({"description": 5})},
    {"name": "description true errors", "stdin": post({"description": True})},
    {"name": "description array slices", "stdin": post({"description": list(range(100))})},
    {"name": "description object errors", "stdin": post({"description": {"a": 1}})},
    {"name": "description null", "stdin": post({"description": None})},
    {"name": "description escapes", "stdin": post({"description": 'q"\\\x7f\x01\n'})},
    {"name": "response keys sorted", "stdin": post(tool_response={"z": 1, "a": 2, "\u00e9": 3, "B": 4})},
    {"name": "pre tool use ignored", "stdin": post(event="PreToolUse")},
    {"name": "missing event ignored", "stdin": '{"tool_input":{}}'},
    {"name": "project dir sets repo", "stdin": post(tool_response=sync_response()), "project": True},
    {"name": "output file override", "stdin": post(), "env": {"AGENT_USAGE_FILE": "{ROOT}/custom.jsonl"}},
    {"name": "output dir missing", "stdin": post(), "env": {"AGENT_USAGE_FILE": "{ROOT}/nope/x.jsonl"}},
    {"name": "appends to existing", "stdin": post(), "files": {"home/.claude/agent-usage.jsonl": '{"old":1}\n'}},
    {"name": "empty stdin", "stdin": ""},
    {"name": "invalid json", "stdin": "not json"},
    {"name": "array payload", "stdin": "[1]"},
    {"name": "null payload", "stdin": "null"},
    {"name": "skip hooks not honored", "stdin": post(), "env": {"CLAUDE_SKIP_HOOKS": "1"}},
]
TYPICAL = {"name": "typical", "stdin": post({"subagent_type": "coder", "model": "sonnet",
                                              "description": "Implement the change", "prompt": "p" * 500},
                                             sync_response())}


def run_hook(stdin, env=None, project=None):
    with tempfile.TemporaryDirectory() as scratch:
        home = pathlib.Path(scratch) / "home"
        (home / ".claude").mkdir(parents=True)
        working = pathlib.Path(scratch) / "work" / "myrepo"
        working.mkdir(parents=True)
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CLAUDE_PROJECT_DIR", "AGENT_USAGE_FILE")}
        environment.update(HOME=str(home), TMPDIR=scratch, PWD=str(working), CLAUDE_TOOLKIT_TELEMETRY="1")
        if project:
            environment["CLAUDE_PROJECT_DIR"] = project
        environment.update({key: value.replace("{ROOT}", scratch) for key, value in (env or {}).items()})
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                                  env=environment, cwd=str(working))
        log = home / ".claude" / "agent-usage.jsonl"
        text = log.read_text() if log.exists() else None
        rows = [json.loads(line) for line in text.splitlines()] if text else ([] if text == "" else None)
        return finished, rows, text


class LogAgentUsageTest(unittest.TestCase):
    def one_row(self, stdin, **kwargs):
        finished, rows, _ = run_hook(stdin, **kwargs)
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))
        self.assertEqual(len(rows), 1)
        return rows[0]

    def test_sync_response_row_has_exact_keys_order_and_values(self):
        finished, rows, text = run_hook(post(tool_response=sync_response()))
        self.assertEqual(finished.returncode, 0)
        row = rows[0]
        self.assertEqual(list(row), KEYS)
        self.assertRegex(row["ts"], TIMESTAMP)
        self.assertEqual({key: row[key] for key in KEYS[1:]}, {
            "repo": "myrepo", "agent": "coder", "model": "sonnet", "desc": "Fix it", "tokens": 1234, "toolUses": 7,
            "durationMs": 4567, "reportChars": 26, "noResult": False,
            "respKeys": ["content", "status", "totalDurationMs", "totalTokens", "totalToolUseCount"]})
        self.assertTrue(text.endswith("}\n"))
        self.assertNotIn(": ", text)

    def test_defaults_when_tool_input_is_empty(self):
        row = self.one_row(post({}))
        self.assertEqual((row["agent"], row["model"], row["desc"]), ("general-purpose", "inherit", ""))
        self.assertEqual((row["tokens"], row["toolUses"], row["durationMs"]), (None, None, None))
        self.assertEqual((row["reportChars"], row["noResult"], row["respKeys"]), (None, None, "null"))

    def test_missing_and_null_tool_input_use_defaults(self):
        for stdin in ('{"hook_event_name":"PostToolUse","tool_input":null}', '{"hook_event_name":"PostToolUse"}'):
            self.assertEqual(self.one_row(stdin)["agent"], "general-purpose")

    def test_respkeys_for_each_response_shape(self):
        shapes = {"x": "string", "5": "number", "true": "boolean", "null": "null", "[7,8,9]": [0, 1, 2], "[]": [],
                  "{}": [], '{"b":1,"a":2}': ["a", "b"]}
        for text, expected in shapes.items():
            stdin = '{"hook_event_name":"PostToolUse","tool_input":{},"tool_response":%s}' % (
                json.dumps(text) if text == "x" else text)
            self.assertEqual(self.one_row(stdin)["respKeys"], expected, text)

    def test_async_response_has_null_report_fields(self):
        row = self.one_row(post(tool_response={"status": "async_launched", "outputFile": "/x"}))
        self.assertEqual((row["tokens"], row["reportChars"], row["noResult"]), (None, None, None))
        self.assertEqual(row["respKeys"], ["outputFile", "status"])

    def test_no_result_phrases_are_found_case_insensitively(self):
        for phrase in (
            "No Results here",
            "NOT FOUND",
            "no matches",
            "could not find it",
            "couldn't find it",
            "couldn\u2019t find it",
            "Nothing found",
            "nothing to report",
            "no relevant files",
            "no such file",
            "unable to find x",
            "found no hits",
            "no occurrences",
            "does not exist",
            "does not appear",
        ):
            row = self.one_row(post(tool_response={"content": phrase}))
            self.assertTrue(row["noResult"], phrase)
        for phrase in ("all good", "found it", "nothing", "No\nresults"):
            self.assertFalse(self.one_row(post(tool_response={"content": phrase}))["noResult"], phrase)

    def test_non_ascii_uppercase_is_not_folded(self):
        self.assertFalse(self.one_row(post(tool_response={"content": "NOT FOUND".replace("O", "\u00d6")}))["noResult"])

    def test_report_chars_counts_code_points(self):
        row = self.one_row(post(tool_response={"content": "caf\u00e9 \U0001f600 \u65e5\u672c"}))
        self.assertEqual(row["reportChars"], 9)

    def test_content_array_joins_text_with_spaces(self):
        row = self.one_row(post(tool_response={"content": [{"text": "a"}, "b", None, {"x": 1}, {"text": None},
                                                             {"text": False}, {"text": 5}, {"text": True}]}))
        self.assertEqual(row["reportChars"], len("a      5 true") + 1 - 1)

    def test_content_array_with_structured_text_writes_no_row(self):
        for text in ({"a": 1}, [1]):
            finished, _rows, text_out = run_hook(post(tool_response={"content": [{"text": text}]}))
            self.assertEqual(finished.returncode, 0)
            self.assertEqual(text_out, "")

    def test_content_of_other_types_is_null(self):
        for content in ({"text": "x"}, 5, None, True):
            self.assertIsNone(self.one_row(post(tool_response={"content": content}))["reportChars"])

    def test_empty_content_is_zero_chars(self):
        row = self.one_row(post(tool_response={"content": ""}))
        self.assertEqual((row["reportChars"], row["noResult"]), (0, False))

    def test_token_fallback_chain(self):
        cases = [
            ({"totalTokens": 1, "usage": {"total_tokens": 2}, "total_tokens": 3}, 1),
            ({"usage": {"total_tokens": 2}, "total_tokens": 3}, 2),
            ({"total_tokens": 3, "usage": {"output_tokens": 4}}, 3),
            ({"usage": {"output_tokens": 4}}, 4),
            ({"usage": {}}, None),
            ({"totalTokens": 0, "total_tokens": 9}, 0),
            ({"totalTokens": False, "total_tokens": 9}, 9),
            ({"totalTokens": None, "usage": None}, None),
        ]
        for response, expected in cases:
            self.assertEqual(self.one_row(post(tool_response=response))["tokens"], expected, response)

    def test_tool_use_and_duration_fallbacks(self):
        row = self.one_row(post(tool_response={"tool_uses": 3, "duration_ms": 12}))
        self.assertEqual((row["toolUses"], row["durationMs"]), (3, 12))
        row = self.one_row(post(tool_response={"totalToolUseCount": 1, "tool_uses": 3, "totalDurationMs": 5,
                                               "duration_ms": 12}))
        self.assertEqual((row["toolUses"], row["durationMs"]), (1, 5))

    def test_non_object_usage_without_earlier_tokens_writes_no_row(self):
        for usage in ("x", [1], 5):
            finished, _rows, text = run_hook(post(tool_response={"usage": usage}))
            self.assertEqual((finished.returncode, text), (0, ""))
        self.assertEqual(self.one_row(post(tool_response={"totalTokens": 3, "usage": "x"}))["tokens"], 3)

    def test_description_is_cut_to_80_code_points(self):
        self.assertEqual(self.one_row(post({"description": "x" * 200}))["desc"], "x" * 80)
        self.assertEqual(self.one_row(post({"description": "\u00e9" * 79 + "\U0001f600" * 5}))["desc"],
                         "\u00e9" * 79 + "\U0001f600")

    def test_non_string_description(self):
        self.assertEqual(self.one_row(post({"description": None}))["desc"], "")
        self.assertEqual(self.one_row(post({"description": False}))["desc"], "")
        self.assertEqual(self.one_row(post({"description": list(range(100))}))["desc"], list(range(80)))
        for value in (5, True, {"a": 1}):
            _finished, _rows, text = run_hook(post({"description": value}))
            self.assertEqual(text, "", value)

    def test_agent_and_model_keep_their_json_types(self):
        row = self.one_row(post({"subagent_type": 5, "model": ["a"]}))
        self.assertEqual((row["agent"], row["model"]), (5, ["a"]))
        row = self.one_row(post({"subagent_type": "", "model": False}))
        self.assertEqual((row["agent"], row["model"]), ("", "inherit"))

    def test_other_events_write_nothing(self):
        for stdin in (post(event="PreToolUse"), '{"tool_input":{}}', '{"hook_event_name":5}'):
            finished, _rows, text = run_hook(stdin)
            self.assertEqual((finished.returncode, text), (0, None))

    def test_project_dir_names_the_repo(self):
        self.assertEqual(self.one_row(post(), project="/a/b/proj/")["repo"], "proj")
        self.assertEqual(self.one_row(post(), project="")["repo"], "myrepo")

    def test_output_file_override_and_unwritable_location(self):
        with tempfile.TemporaryDirectory() as scratch:
            target = pathlib.Path(scratch) / "custom.jsonl"
            (pathlib.Path(scratch) / ".claude").mkdir()
            environment = dict(os.environ, HOME=scratch, AGENT_USAGE_FILE=str(target), CLAUDE_TOOLKIT_TELEMETRY="1")
            subprocess.run([sys.executable, str(SCRIPT)], input=post(), text=True, env=environment)
            subprocess.run([sys.executable, str(SCRIPT)], input=post(), text=True, env=environment)
            self.assertEqual(len(target.read_text().splitlines()), 2)
            environment["AGENT_USAGE_FILE"] = str(pathlib.Path(scratch) / "nope" / "x.jsonl")
            finished = subprocess.run([sys.executable, str(SCRIPT)], input=post(), text=True, env=environment,
                                      capture_output=True)
            self.assertEqual(finished.returncode, 0)
            self.assertEqual(
                finished.stderr,
                "log-agent-usage: cannot open {}: No such file or directory\n".format(environment["AGENT_USAGE_FILE"]),
            )

    def test_bad_payloads_exit_five_without_a_row(self):
        for stdin in ("not json", "[1]", '"s"', "5"):
            finished, _rows, text = run_hook(stdin)
            self.assertEqual(finished.returncode, 5, stdin)
            self.assertIsNone(text)

    def test_empty_and_null_payloads_are_quiet(self):
        for stdin in ("", "null"):
            finished, _rows, text = run_hook(stdin)
            self.assertEqual((finished.returncode, text), (0, None))

    def test_string_tool_input_leaves_an_empty_log_like_the_bash_redirect(self):
        finished, _rows, text = run_hook('{"hook_event_name":"PostToolUse","tool_input":"x"}')
        self.assertEqual((finished.returncode, text), (0, ""))

    def test_skip_hooks_is_not_honored(self):
        _finished, rows, _text = run_hook(post(), env={"CLAUDE_SKIP_HOOKS": "1"})
        self.assertEqual(len(rows), 1)

    def test_del_and_control_characters_are_escaped_like_jq(self):
        _, _, text = run_hook(post({"description": "a\x7fb\x01c"}))
        self.assertIn('"desc":"a\\u007fb\\u0001c"', text)


if __name__ == "__main__":
    unittest.main()
