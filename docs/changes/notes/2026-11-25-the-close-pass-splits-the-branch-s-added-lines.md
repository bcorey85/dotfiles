---
type: "Change"
change_type: "added"
title: "The close pass splits the branch's added lines into docs, tests and code"
description: "The concentration gate also prints the branch's added lines split into docs, tests and code, and flags a docs or tests part over 40% of a branch of 300 or more lines."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T17:01:20-06:00"}
seq: 3
kind: "fix"
components: ["script/concentration", "skill/close-branch"]
evidence: ["tests/scripts/test_concentration.py", "tests/scripts/test_script_utils.py"]
watches: []
test: "tests/scripts/test_concentration.py::test_oversized_parts_are_named_docs_first"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`concentration.py <base>` prints a second line after the gate line: `Diff split: docs <n> (<p>%), tests <n> (<p>%), code <n> (<p>%) of <total> added lines.` A test file counts as tests, then a Markdown file or a file under a docs folder counts as docs, and every other file as code; lockfiles, generated files and binary files count nowhere. On a branch of 300 or more added lines, a docs or tests part over 40% ends the line with `OVERSIZED:`, which names the part and says to check each new file of that part against a plan step, criterion or finding and cut the rest. `script_utils.rounded_percent` rounds the shares.

## Evidence

The new tests in `test_concentration.py` fail on the old script, which printed no split line. The full check passed, 6673 tests.

## Result

Before, the close pass counted only source lines, so a branch whose diff was mostly unasked docs and tests passed with no flag.

## Watch

—

## Back-out

Revert the commit.

