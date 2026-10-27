#!/usr/bin/env python3
"""PreToolUse hook on Write|Edit|MultiEdit|NotebookEdit: log one JSONL row per edit that touches a test file.

LOG-ONLY: never emits a permission decision, always exits 0, prints nothing. Row appended to
~/.claude/test-edit-telemetry.jsonl: {ts, tool, agent, file, cwd, snippet}. agent is agent_type or "main"; snippet is
the first 200 characters of new_string or content. CLAUDE_SKIP_HOOKS skips logging. A write failure is ignored.
"""
import contextlib
import json
import os
import re
import sys
import time

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + "/lib"]
import hook_input
import script_utils
from hook_input import current_directory, raw_text, report_open_failure, truthy

TEST_SUFFIXES = ("_test.go", ".test.ts", ".test.tsx", ".test.js", ".test.jsx", ".spec.ts", ".spec.tsx", ".spec.js",
                 ".spec.jsx", "_spec.rb", "_test.py", "/conftest.py")
TEST_PREFIXED_PYTHON = re.compile(r".*/test_.*\.py", re.S)
TEST_DIRECTORIES = ("/tests/", "/testdata/", "/fixtures/", "/__tests__/", "/__mocks__/")
SNIPPET_LENGTH = 200


def is_test_file(file_path):
    if file_path.endswith(TEST_SUFFIXES) or TEST_PREFIXED_PYTHON.fullmatch(file_path):
        return True
    return any(directory in file_path for directory in TEST_DIRECTORIES)


def row_json(row):
    text = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
    return text.replace("\x7f", "\\u007f")


def check(raw):
    if os.environ.get("CLAUDE_SKIP_HOOKS") or not raw.strip():
        return
    payload = json.loads(raw)
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path")
    file_path = raw_text(file_path).rstrip("\n") if truthy(file_path) else ""
    if not file_path or not is_test_file(file_path):
        return

    tool = payload.get("tool_name")
    tool = raw_text(tool).rstrip("\n") if truthy(tool) else ""
    agent = payload.get("agent_type")
    agent = raw_text(agent).rstrip("\n") if truthy(agent) else "main"

    snippet = tool_input.get("new_string")
    if not truthy(snippet):
        snippet = tool_input.get("content")
    if not truthy(snippet):
        snippet = ""

    if not script_utils.telemetry_switch_on():
        return

    log_path = os.environ.get("HOME", "") + "/.claude/test-edit-telemetry.jsonl"
    try:
        log = open(log_path, "ab")
    except OSError as error:
        report_open_failure(error, log_path)
        return
    with log:
        if not isinstance(snippet, str):
            return
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "tool": tool, "agent": agent,
               "file": file_path, "cwd": current_directory(), "snippet": snippet[:SNIPPET_LENGTH]}
        log.write((row_json(row) + "\n").encode("utf-8", "replace"))


def main():
    with contextlib.suppress(Exception):
        check(hook_input.read_stdin_text())
    sys.exit(0)


if __name__ == "__main__":
    main()
