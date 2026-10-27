---
type: "Change"
title: "The turn-end formatter skips plan files"
description: "format_changed.py no longer runs prettier or oxfmt on files under docs/plans/, so a plan's next Edit and its review shards still match the text on disk."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T11:55:46-05:00"}
seq: 53
kind: "fix"
components: ["script/format-changed"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_format_changed.py::FormatChangedTest::test_plan_files_are_never_formatted"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The Stop hook that formats each file a turn changed skips every path under `docs/plans/`.

## Evidence

- A peer's eng-spec run: a plan file grew 7 lines on disk after Write (list items gained blank lines), the next Edit
  missed its anchor, and the review shards went stale until rebuilt. The only hook that rewrites markdown is this Stop
  hook, which runs prettier or oxfmt on every changed `.md` at turn end.
- The new test fails on the base commit and passes after.

## Result

- Full suite and ruff pass on the worktree.

## Watch

—

## Back-out

Revert the commit.
