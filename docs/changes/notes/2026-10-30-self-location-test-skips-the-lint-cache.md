---
type: "Change"
change_type: "fixed"
title: "Self-location test skips the lint cache"
description: "The self-location test skips `.ruff_cache`, so a lint run in the scripts folder no longer fails the full check on files no diff holds."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T15:54:44-05:00"}
seq: 388
kind: "fix"
components: []
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_self_location.py::ScannedFilesTest::test_a_lint_cache_file_is_not_scanned_and_a_script_is"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `scanned_files` in `tests/scripts/test_toolkit_self_location.py` skips `.ruff_cache` as well as `__pycache__`.

## Evidence

A lint run leaves `.ruff_cache` under `claude/.claude/scripts/`. The test read its files as toolkit code and failed the
full check, which stopped a review at `critical-blocker` on files outside its diff.

## Result

The targeted test passes. A lint cache file is not scanned, and a script beside it is.

## Watch

None: a test-only change has no work-log number to read.

## Back-out

Revert the commit.
