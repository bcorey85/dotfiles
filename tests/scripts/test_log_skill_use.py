"""Checks for log-skill-use.py, the skill-usage telemetry hook.

Set HOOK_SCRIPTS_DIR to run against another directory of scripts."""
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

os.environ.pop("CLAUDE_TOOLKIT_TELEMETRY", None)  # the switch file alone decides in these tests

SCRIPT = pathlib.Path(os.environ.get("HOOK_SCRIPTS_DIR") or pathlib.Path.home() / ".claude" / "scripts") / "log-skill-use.py"
TIMESTAMP = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")


def post(skill, **extra):
    document = {"hook_event_name": "PostToolUse", "tool_name": "Skill", "tool_input": {"skill": skill}}
    document.update(extra)
    return json.dumps(document)


def prompt(text, event="UserPromptSubmit"):
    return json.dumps({"hook_event_name": event, "prompt": text})


PARITY_CASES = [
    {"name": "model skill", "stdin": post("review")},
    {"name": "model skill with args", "stdin": json.dumps({"hook_event_name": "PostToolUse",
                                                             "tool_input": {"skill": "fix", "args": "x"}})},
    {"name": "plugin skill", "stdin": post("anthropic-skills:deep-research")},
    {"name": "empty skill", "stdin": post("")},
    {"name": "missing skill", "stdin": json.dumps({"hook_event_name": "PostToolUse", "tool_input": {}})},
    {"name": "tool_input null", "stdin": json.dumps({"hook_event_name": "PostToolUse", "tool_input": None})},
    {"name": "tool_input string", "stdin": json.dumps({"hook_event_name": "PostToolUse", "tool_input": "x"})},
    {"name": "numeric skill", "stdin": post(5)},
    {"name": "object skill", "stdin": post({"a": 1})},
    {"name": "false skill", "stdin": post(False)},
    {"name": "skill trailing newline", "stdin": post("fix\n")},
    {"name": "user slash command", "stdin": prompt("/review the diff")},
    {"name": "user slash with colon", "stdin": prompt("/plugin:thing arg")},
    {"name": "user builtin", "stdin": prompt("/clear")},
    {"name": "user slash alone", "stdin": prompt("/")},
    {"name": "user slash then newline", "stdin": prompt("/fix\nmore")},
    {"name": "user prompt without slash", "stdin": prompt("hello /fix")},
    {"name": "user prompt leading space", "stdin": prompt(" /fix")},
    {"name": "user prompt path", "stdin": prompt("/home/brandon/x is a path")},
    {"name": "user prompt unicode name", "stdin": prompt("/caf\u00e9")},
    {"name": "user prompt empty", "stdin": prompt("")},
    {"name": "user prompt missing", "stdin": json.dumps({"hook_event_name": "UserPromptSubmit"})},
    {"name": "user prompt numeric", "stdin": json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": 5})},
    {"name": "user prompt array", "stdin": json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": ["/x"]})},
    {"name": "other event", "stdin": prompt("/fix", event="Stop")},
    {"name": "missing event", "stdin": json.dumps({"prompt": "/fix"})},
    {"name": "event is number", "stdin": json.dumps({"hook_event_name": 5})},
    {"name": "project dir sets repo", "stdin": post("review"), "project": True},
    {"name": "output file override", "stdin": post("review"), "env": {"SKILL_USAGE_FILE": "{ROOT}/custom.jsonl"}},
    {"name": "output dir missing", "stdin": post("review"), "env": {"SKILL_USAGE_FILE": "{ROOT}/nope/x.jsonl"}},
    {"name": "appends to existing", "stdin": post("review"), "files": {"home/.claude/skill-usage.jsonl": '{"old":1}\n'}},
    {"name": "empty stdin", "stdin": ""},
    {"name": "invalid json", "stdin": "not json"},
    {"name": "array payload", "stdin": "[1]"},
    {"name": "null payload", "stdin": "null"},
    {"name": "skip hooks not honored", "stdin": post("review"), "env": {"CLAUDE_SKIP_HOOKS": "1"}},
]
TYPICAL = {"name": "typical", "stdin": post("review")}


def run_hook(stdin, env=None, project=None, cwd=None):
    with tempfile.TemporaryDirectory() as scratch:
        home = pathlib.Path(scratch) / "home"
        (home / ".claude").mkdir(parents=True)
        (home / ".claude" / "toolkit-telemetry").touch()
        working = pathlib.Path(scratch) / "work" / "myrepo"
        working.mkdir(parents=True)
        environment = {key: value for key, value in os.environ.items()
                       if key not in ("CLAUDE_PROJECT_DIR", "SKILL_USAGE_FILE")}
        environment.update(HOME=str(home), TMPDIR=scratch, PWD=str(cwd or working))
        if project:
            environment["CLAUDE_PROJECT_DIR"] = project
        environment.update({key: value.replace("{ROOT}", scratch) for key, value in (env or {}).items()})
        finished = subprocess.run([sys.executable, str(SCRIPT)], input=stdin, capture_output=True, text=True,
                                  env=environment, cwd=str(cwd or working))
        log = home / ".claude" / "skill-usage.jsonl"
        rows = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else None
        return finished, rows, log.read_text() if log.exists() else None


class LogSkillUseTest(unittest.TestCase):
    def test_model_skill_row_has_exact_keys_and_order(self):
        finished, rows, text = run_hook(post("review"))
        self.assertEqual((finished.returncode, finished.stdout, finished.stderr), (0, "", ""))
        self.assertEqual(len(rows), 1)
        self.assertEqual(list(rows[0]), ["ts", "skill", "via", "repo"])
        self.assertRegex(rows[0]["ts"], TIMESTAMP)
        self.assertEqual((rows[0]["skill"], rows[0]["via"], rows[0]["repo"]), ("review", "model", "myrepo"))
        self.assertRegex(text, r'^\{"ts":"[^"]+","skill":"review","via":"model","repo":"myrepo"\}\n$')

    def test_user_slash_command_row(self):
        _, rows, _ = run_hook(prompt("/fix the bug"))
        self.assertEqual((rows[0]["skill"], rows[0]["via"]), ("fix", "user"))

    def test_slash_name_allows_colon_underscore_hyphen_and_stops_at_other_characters(self):
        for text, expected in (("/plugin:my_skill-2 x", "plugin:my_skill-2"), ("/fix\nmore", "fix"), ("/a.b", "a")):
            _, rows, _ = run_hook(prompt(text))
            self.assertEqual(rows[0]["skill"], expected)

    def test_prompts_without_a_leading_slash_are_not_logged(self):
        for text in ("hello /fix", " /fix", "", "/", "/ fix", "/\u00e9"):
            self.assertIsNone(run_hook(prompt(text))[1])

    def test_non_string_prompt_is_not_logged(self):
        self.assertIsNone(run_hook(json.dumps({"hook_event_name": "UserPromptSubmit", "prompt": 5}))[1])
        self.assertIsNone(run_hook(json.dumps({"hook_event_name": "UserPromptSubmit"}))[1])

    def test_other_events_are_ignored(self):
        self.assertIsNone(run_hook(prompt("/fix", event="Stop"))[1])
        self.assertIsNone(run_hook(json.dumps({"prompt": "/fix"}))[1])

    def test_empty_or_missing_skill_is_not_logged(self):
        for stdin in (post(""), post(None), post(False), json.dumps({"hook_event_name": "PostToolUse"})):
            self.assertIsNone(run_hook(stdin)[1])

    def test_non_string_skill_is_logged_as_text(self):
        self.assertEqual(run_hook(post(5))[1][0]["skill"], "5")

    def test_trailing_newline_of_skill_is_stripped(self):
        self.assertEqual(run_hook(post("fix\n"))[1][0]["skill"], "fix")

    def test_project_dir_names_the_repo(self):
        _, rows, _ = run_hook(post("x"), project="/somewhere/else/proj-name/")
        self.assertEqual(rows[0]["repo"], "proj-name")

    def test_repo_falls_back_to_the_working_directory(self):
        _, rows, _ = run_hook(post("x"), project="")
        self.assertEqual(rows[0]["repo"], "myrepo")

    def test_root_project_dir_is_a_slash(self):
        _, rows, _ = run_hook(post("x"), project="/")
        self.assertEqual(rows[0]["repo"], "/")

    def test_output_file_override_and_missing_directory(self):
        with tempfile.TemporaryDirectory() as scratch:
            target = pathlib.Path(scratch) / "custom.jsonl"
            (pathlib.Path(scratch) / ".claude").mkdir()
            (pathlib.Path(scratch) / ".claude" / "toolkit-telemetry").touch()
            environment = dict(os.environ, HOME=scratch, SKILL_USAGE_FILE=str(target))
            subprocess.run([sys.executable, str(SCRIPT)], input=post("a"), text=True, env=environment)
            subprocess.run([sys.executable, str(SCRIPT)], input=post("b"), text=True, env=environment)
            self.assertEqual([json.loads(line)["skill"] for line in target.read_text().splitlines()], ["a", "b"])
            environment["SKILL_USAGE_FILE"] = str(pathlib.Path(scratch) / "nope" / "x.jsonl")
            finished = subprocess.run([sys.executable, str(SCRIPT)], input=post("a"), text=True, env=environment,
                                      capture_output=True)
            self.assertEqual(finished.returncode, 0)
            self.assertEqual(finished.stderr, "log-skill-use: cannot open %s: No such file or directory\n"
                             % environment["SKILL_USAGE_FILE"])

    def test_bad_payloads_exit_five_without_a_row(self):
        for stdin in ("not json", "[1]", '"s"', "5"):
            finished, rows, _ = run_hook(stdin)
            self.assertEqual(finished.returncode, 5)
            self.assertIsNone(rows)

    def test_empty_and_null_payloads_are_quiet(self):
        for stdin in ("", "null", "  \n"):
            finished, rows, _ = run_hook(stdin)
            self.assertEqual(finished.returncode, 0)
            self.assertIsNone(rows)

    def test_string_tool_input_exits_five_only_on_post_tool_use(self):
        finished, rows, _ = run_hook(json.dumps({"hook_event_name": "PostToolUse", "tool_input": "x"}))
        self.assertEqual(finished.returncode, 5)
        finished, rows, _ = run_hook(json.dumps({"hook_event_name": "Stop", "tool_input": "x"}))
        self.assertEqual(finished.returncode, 0)

    def test_skip_hooks_is_not_honored(self):
        _, rows, _ = run_hook(post("review"), env={"CLAUDE_SKIP_HOOKS": "1"})
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
