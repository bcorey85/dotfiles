#!/usr/bin/env python3
"""PostToolUse (Skill) and UserPromptSubmit hook: skill-usage telemetry.

Appends {ts, skill, via, repo} to SKILL_USAGE_FILE (default
~/.claude/skill-usage.jsonl). PostToolUse logs tool_input.skill with via "model". UserPromptSubmit logs a
leading /name in the prompt with via "user". Emits no hook output. Exits 0, except 5 on a payload that is
not valid JSON or not an object, as the bash original did through jq.
"""
import json
import os
import re
import sys
import time

import hook_input
from hook_input import (JqError, bash_basename, current_directory, index, parse_documents, present, raw_text,
                        report_open_failure)

try:
    from telemetry_enabled import telemetry_enabled
except ImportError:
    def telemetry_enabled():
        return False

PROMPT_SKILL = re.compile(r"/([A-Za-z0-9:_-]+)")


def field(documents, extract, newlines):
    """What `jq -r <extract> <<<"$input"` leaves in a shell variable (here-string adds one newline)."""
    pieces = []
    for document in documents:
        try:
            pieces.append(raw_text(extract(document)))
        except JqError as error:
            sys.stderr.write("jq: error (at <stdin>:%d): %s\n" % (newlines + 1, error))
            sys.exit(5)
    return "\n".join(pieces).rstrip("\n")


def main():
    text = hook_input.read_stdin_text().rstrip("\n")
    newlines = text.count("\n")
    try:
        documents = parse_documents(text)
    except ValueError:
        sys.stderr.write("jq: error (at <stdin>:%d): parse error\n" % (newlines + 1))
        return 5

    event = field(documents, lambda d: present(index(d, "hook_event_name")), newlines)
    skill = ""
    via = ""
    if event == "PostToolUse":
        skill = field(documents, lambda d: present(index(index(d, "tool_input"), "skill")), newlines)
        via = "model"
    elif event == "UserPromptSubmit":
        prompt = field(documents, lambda d: present(index(d, "prompt")), newlines)
        found = PROMPT_SKILL.match(prompt)
        if found:
            skill = found.group(1)
            via = "user"

    if skill == "":
        return 0

    if not telemetry_enabled():
        return 0

    project_dir = os.environ.get("CLAUDE_PROJECT_DIR", "")
    repo = bash_basename(project_dir if project_dir else current_directory())
    out = os.environ.get("SKILL_USAGE_FILE") or os.path.join(os.environ.get("HOME", ""), ".claude",
                                                             "skill-usage.jsonl")
    try:
        handle = open(out, "a", encoding="utf-8", errors="replace")
    except OSError as error:
        report_open_failure(error, out)
        return 0
    with handle:
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "skill": skill, "via": via, "repo": repo}
        encoded = json.dumps(row, separators=(",", ":"), ensure_ascii=False)
        handle.write(encoded.replace("\x7f", "\\u007f") + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
