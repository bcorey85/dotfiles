---
type: "Change"
change_type: "changed"
title: "Three numstat readers share one row parser"
description: "The code step's line counts, verify-prep and the refactor flow read `git diff --numstat -z` rows through one lib parser, and each keeps its own rule for a binary file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T19:43:59-05:00"}
seq: 292
kind: "fix"
components: ["script/code-step", "script/verify-prep", "skill/refactor"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_parse_numstat_skips_a_malformed_row_and_a_rename_row_missing_its_new_path"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `numstat.numstat_rows(text)` yields `(added, deleted, path)` for each `git diff --numstat -z` row. `added` and
  `deleted` are None for a binary file, and a rename yields its new path.
- `numstat.changed_lines_by_path` drops a binary file, `verify-prep` `parse_numstat` counts it as 0, and
  `refactor_flow.binary_paths` collects it. All three are built on `numstat_rows`.
- `verify-prep` and the refactor flow skip a malformed row instead of raising, as the code step already did.

## Evidence

- A review of the shared working-tree scan found three hand-written copies of the same `-z` row walk, each with its
  own rename handling.

## Result

- Tests pin each reader's binary-file rule and a rename row in each.

## Watch

None: no behavior a work log reads changes.

## Back-out

Revert the commit.
