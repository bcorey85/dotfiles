---
type: "Change"
change_type: "fixed"
title: "stage run counts an already-staged deletion as staged"
description: "stage --run no longer aborts when a SAFE deletion was already staged with git rm; it counts it as staged and stages the rest."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T14:11:38-06:00"}
seq: 3
kind: "fix"
components: ["skill/stage"]
evidence: ["tests/scripts/test_stage_run.py"]
watches: []
test: "tests/scripts/test_stage_run.py::test_already_staged_deletion_counts_as_staged_beside_an_unstaged_edit"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`stage.mjs` leaves each SAFE deletion that is already gone from the index out of its `git add` call, still counts it as staged, and skips `git add` when nothing is left.

## Evidence

The new test fails on the old tree with `pathspec 'src/index.ts' did not match any files` and passes on the new one. The full check passed (6658 tests).

## Result

Before, `--run` exited 2 and staged nothing; now it exits 0 and stages or queues the rest.

## Watch

—

## Back-out

Revert the commit.
