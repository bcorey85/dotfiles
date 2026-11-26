---
type: "Change"
change_type: "fixed"
title: "the full check skips only Markdown under docs and adr_flow status refuses on a failing git log"
description: "The discovered full check skips only Markdown under docs/ through the notes_paths owner, and adr_flow status refuses when git log fails instead of reading never committed."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T21:13:44-06:00"}
seq: 10
kind: "fix"
components: ["script/check-discovery", "script/adr-flow"]
evidence: ["tests/scripts/test_check_discovery.py", "tests/scripts/test_adr_flow.py"]
watches: []
test: "tests/scripts/test_check_discovery.py::ChangedPathPartsTest::test_a_markdown_file_outside_docs_widens_the_check_to_every_part"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`check_discovery.parts_to_run` calls `notes_paths.is_notes_path(path, ())` in place of a suffix-only copy. `adr_flow.path_was_committed` raises RefusedError on a failing `git log`.

## Evidence

Both new tests fail on the old code and pass on the new. The full check passed on the final tree (6736 tests, 0 failed).

## Result

A root README.md beside frontend files no longer drops the Python part; a git failure no longer reads as a never-committed plan.

## Watch

—

## Back-out

Revert the commit.
