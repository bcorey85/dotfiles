#!/usr/bin/env python3
"""PostToolUse hook on Write|Edit: report when a reviewer agent names a calibration heading that no longer exists.

Runs only when the shared reviewer calibration file, or a reviewer agent that reads it, was just written. Each agent
names the sections it adopts as **Bold Heading** on lines that mention reviewer-calibration.md; each must appear as a
`## Heading` in the calibration file. Reports on stdout and exits 0: a rename is legitimate work, so it never blocks.

CALIB_FILE and CALIB_AGENTS_DIR override the live paths so the check can be exercised against fixtures.
"""
import contextlib
import json
import os
import re
import sys

BOLD = re.compile(r"\*\*([^*]*)\*\*")
REVIEWER_AGENT = re.compile(r".*reviewer.*\.md", re.S)

REPORT_TAIL = ("A reviewer told to adopt a heading that does not exist gets that section only by\n"
               "accident, through \"adopt in full\". Update every agent that names the heading, or\n"
               "restore the heading, before moving on.\n")


def read_text(path):
    try:
        with open(path, "rb") as handle:
            return handle.read().decode("utf-8", "surrogateescape")
    except OSError:
        return None


def is_watched(path, agents_dir):
    if path.endswith("reviewer-calibration.md"):
        return True
    prefix = agents_dir + "/"
    return path.startswith(prefix) and bool(REVIEWER_AGENT.fullmatch(path[len(prefix):]))


def reviewer_agents(agents_dir):
    try:
        names = sorted(os.listdir(agents_dir))
    except OSError:
        return []
    found = []
    for name in names:
        if name.startswith(".") or not REVIEWER_AGENT.fullmatch(name):
            continue
        path = agents_dir + "/" + name
        if os.path.isfile(path):
            found.append((name, path))
    return found


def named_headings(agent_text):
    headings = []
    for line in agent_text.split("\n"):
        if "reviewer-calibration.md" in line:
            headings.extend(BOLD.findall(line))
    return headings


def check(raw):
    home = os.environ.get("HOME", "")
    calibration_path = os.environ.get("CALIB_FILE") or home + "/.claude/skills/_shared/reviewer-calibration.md"
    agents_dir = os.environ.get("CALIB_AGENTS_DIR") or home + "/.claude/agents"

    payload = json.loads(raw)
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict):
        return
    path = tool_input.get("file_path")
    if path is None or path is False:
        return
    path = path.rstrip("\n") if isinstance(path, str) else json.dumps(path)
    if not is_watched(path, agents_dir):
        return
    if not os.path.isfile(calibration_path):
        return

    calibration = read_text(calibration_path)
    calibration_lower = None if calibration is None else calibration.lower()

    missing = ""
    for name, agent_path in reviewer_agents(agents_dir):
        agent_text = read_text(agent_path) or ""
        for heading in named_headings(agent_text):
            if not heading:
                continue
            if calibration_lower is None or ("## " + heading).lower() not in calibration_lower:
                missing += f"  {name} names \"{heading}\" — no such heading in the calibration file\n"
    if not missing:
        return

    report = "⚠️  Reviewer calibration references are out of sync.\n\n" + missing + "\n" + REPORT_TAIL
    sys.stdout.buffer.write(report.encode("utf-8", "surrogateescape"))
    sys.stdout.buffer.flush()


def main():
    with contextlib.suppress(Exception):
        check(sys.stdin.buffer.read())
    sys.exit(0)


if __name__ == "__main__":
    main()
