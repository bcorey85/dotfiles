---
type: "Change"
change_type: "fixed"
title: "The comment-bloat gate reads only comment lines in JSON files"
description: "The comment-bloat gate no longer reads JSON values as comments. It blocked writes of JSON fixtures and test files that held long string values."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T08:03:31-05:00"}
seq: 7
kind: "fix"
components: ["script/comment-bloat-gate"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `scripts/comment-bloat-gate.py`: in a `.json` file, the gate scans only lines that look like comments. Before, it read JSON string values as comment text.

## Evidence

Work incident: work sessions reported false blocks on JSON writes, and the sessions got the advice to ignore them. A worker in this repo hit the same false block on a new test file.

## Result

Staged 2026-10-21 in the script fix batch. The gate tests pass. Installed 2026-10-21.

## Watch

None. This gate does not write to the hook block log that the watch metrics read.

## Back-out

Restore the previous `comment-bloat-gate.py` from the dotfiles history.
