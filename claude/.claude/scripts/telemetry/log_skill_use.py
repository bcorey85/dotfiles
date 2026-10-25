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

sys.path[:0] = [os.path.dirname(os.path.dirname(os.path.realpath(__file__))) + "/lib"]
import hook_input
import script_utils
from hook_input import (
    bash_basename,
    current_directory,
    index,
    parse_documents,
    present,
    report_open_failure,
)

PROMPT_SKILL = re.compile(r"/([A-Za-z0-9:_-]+)")


def main():
    text = hook_input.read_stdin_text().rstrip("\n")
    # A here-string adds one newline, so jq counts one more input line than the text holds.
    error_line = text.count("\n") + 1
    try:
        documents = parse_documents(text)
    except ValueError:
        sys.stderr.write(f"jq: error (at <stdin>:{error_line}): parse error\n")
        return 5

    event = hook_input.jq_output(documents, lambda d: present(index(d, "hook_event_name")), error_line)
    skill = ""
    via = ""
    if event == "PostToolUse":
        skill = hook_input.jq_output(documents, lambda d: present(index(index(d, "tool_input"), "skill")),
                                     error_line)
        via = "model"
    elif event == "UserPromptSubmit":
        prompt = hook_input.jq_output(documents, lambda d: present(index(d, "prompt")), error_line)
        found = PROMPT_SKILL.match(prompt)
        if found:
            skill = found.group(1)
            via = "user"

    if skill == "":
        return 0

    if not script_utils.telemetry_switch_on():
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
