#!/usr/bin/env python3
"""PostToolUse hook on Write|Edit: warn on stderr when an edited CLAUDE.md exceeds 150 lines. Always exits 0."""
import errno
import json
import os
import re
import sys

import hook_input
from hook_input import emit_stderr, report_open_failure

LINE_LIMIT = 150
CLAUDE_MD = re.compile(r"CLAUDE\.md$", re.I | re.M)


def line_count(file_path):
    """Count of newline bytes, like `wc -l`; 0 when the file cannot be opened.

    A missing or unreadable file is reported on one plain stderr line."""
    try:
        with open(file_path, "rb") as handle:
            return handle.read().count(b"\n")
    except OSError as error:
        if error.errno in (errno.ENOENT, errno.EACCES):
            report_open_failure(error, file_path)
        return 0


def check(raw):
    payload = json.loads(raw)
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    if not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path")
    if file_path is None or file_path is False:
        return
    file_path = file_path.rstrip("\n") if isinstance(file_path, str) else json.dumps(file_path)
    if not file_path or not CLAUDE_MD.search(file_path):
        return
    lines = line_count(file_path)
    if lines > LINE_LIMIT:
        emit_stderr("CLAUDE.md is %d lines (target: <150). Consider moving reference data to skills or MEMORY.md.\n"
                    % lines)


def main():
    try:
        check(sys.stdin.buffer.read())
    except Exception:
        pass
    sys.exit(0)


if __name__ == "__main__":
    main()
