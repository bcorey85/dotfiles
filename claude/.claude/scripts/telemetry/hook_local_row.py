#!/usr/bin/env python3
"""Keep a skill-use or test-edit hook event in its jsonl file. ledger-hook runs this when no ledger is found and the
telemetry switch is on.

usage: hook_local_row.py <skill-use|test-edit>   (the hook event is read from stdin)

skill-use appends {ts, skill, via, repo} to SKILL_USAGE_FILE (default ~/.claude/skill-usage.jsonl): via is "model" for
a Skill tool call and "user" for a prompt that starts with /name. test-edit appends {ts, tool, agent, file, cwd,
snippet} to ~/.claude/test-edit-telemetry.jsonl for an edit to a test file; CLAUDE_SKIP_HOOKS skips it. Fails open: a
bad event or a failed write prints one stderr line and exits 0.
"""
import json
import os
import pathlib
import re
import sys
import time

sys.path[:0] = [str(pathlib.Path(__file__).resolve().parent.parent / "lib")]
import script_utils
import source_paths

PROMPT_SKILL = re.compile(r"/([A-Za-z0-9:_-]+)")
SNIPPET_LENGTH = 200


def timestamp():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def skill_use_row(event):
    """The row for a Skill tool call or a /name prompt, or None for any other event."""
    if event.get("hook_event_name") == "PostToolUse":
        skill, via = (event.get("tool_input") or {}).get("skill"), "model"
    else:
        found = PROMPT_SKILL.match(event.get("prompt") or "")
        skill, via = found and found.group(1), "user"
    if not skill:
        return None
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return {"ts": timestamp(), "skill": skill, "via": via, "repo": script_utils.repo_name(project_dir)}


def test_edit_row(event):
    """The row for an edit to a test file, or None for any other edit."""
    tool_input = event.get("tool_input") or {}
    file_path = tool_input.get("file_path")
    if os.environ.get("CLAUDE_SKIP_HOOKS") or not file_path or not source_paths.is_test_path(file_path):
        return None
    snippet = tool_input.get("new_string") or tool_input.get("content") or ""
    return {"ts": timestamp(), "tool": event.get("tool_name", ""), "agent": event.get("agent_type") or "main",
            "file": file_path, "cwd": os.getcwd(), "snippet": snippet[:SNIPPET_LENGTH]}


def log_path(hook_name):
    home = pathlib.Path(os.environ["HOME"])
    if hook_name == "test-edit":
        return home / ".claude" / "test-edit-telemetry.jsonl"
    return pathlib.Path(os.environ.get("SKILL_USAGE_FILE") or home / ".claude" / "skill-usage.jsonl")


def keep_row(hook_name, event_text):
    event = json.loads(event_text)
    row = test_edit_row(event) if hook_name == "test-edit" else skill_use_row(event)
    if row is None:
        return
    target = log_path(hook_name)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as log:
        log.write(json.dumps(row, separators=(",", ":"), ensure_ascii=False) + "\n")


def main():
    hook_name = sys.argv[1]
    try:
        keep_row(hook_name, sys.stdin.read())
    except (OSError, KeyError, ValueError, AttributeError, TypeError) as error:
        print(f"hook_local_row: {hook_name} row dropped: {error}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
