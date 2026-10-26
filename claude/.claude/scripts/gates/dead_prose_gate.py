#!/usr/bin/env python3
"""PostToolUse hook on Write|Edit: warn when a rewritten agent, skill or command body ships banned rationale or a
hardcoded path.

The rationale check covers .claude/{agents,skills}/*.md; the portability check also covers .claude/commands/*.md.
A warning, never a block: always exits 0, warnings go to stderr.
"""
import contextlib
import json
import os
import re
import sys

sys.path[:0] = [os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib")]
import hook_input
from hook_input import emit_stderr

SURFACE = re.compile(r"\.claude/(agents|skills|commands)/.*\.md$", re.M)
RATIONALE_SURFACE = re.compile(r"\.claude/(agents|skills)/.*\.md$", re.M)

RATIONALE = [re.compile(pattern, re.I) for pattern in (
    r"(you|this|it) exists?( only)? because",
    r"the reason (you|this|it) exists?",
    r"(chosen|not a) measured (one|budget|default)",
    r"chosen (budget|default)s?, not",
    r"(this |it )?was retired|retired because",
    r"measured basis|as measured|we measured",
    r"[^0-9]20[0-9]{2}-[0-9]{2}-[0-9]{2}",
)]
PORTABILITY = re.compile(r"/Users/|/home/[a-z]|\bdotfiles\b")


def numbered_hits(lines, matches):
    return [f"  {number}:{line}\n" for number, line in enumerate(lines, 1) if matches(line)]


def check(raw):
    payload = json.loads(raw)
    tool_input = hook_input.tool_input_of(payload)
    if tool_input is None:
        return
    file_path = hook_input.edited_file_path(tool_input)
    if not file_path or not SURFACE.search(file_path) or not os.path.isfile(file_path):
        return

    file_text = hook_input.read_file_text(file_path) or ""
    lines = file_text.split("\n")
    name = os.path.basename(file_path)

    if RATIONALE_SURFACE.search(file_path):
        rationale = numbered_hits(lines, lambda line: any(p.search(line) for p in RATIONALE))
        if rationale:
            emit_stderr("dead-prose-gate: possible banned rationale in {} — the rule ships every dispatch; keep the "
                        "RULE, cut the defense:\n{}".format(name, "".join(rationale)))

    portability = numbered_hits(lines, PORTABILITY.search)
    if portability:
        emit_stderr("dead-prose-gate: hardcoded path or repo name in {} — agents, skills and commands must be "
                    "portable across WSL/Ubuntu/macOS/Arch:\n{}".format(name, "".join(portability)))


def main():
    with contextlib.suppress(Exception):
        check(sys.stdin.buffer.read())
    sys.exit(0)


if __name__ == "__main__":
    main()
