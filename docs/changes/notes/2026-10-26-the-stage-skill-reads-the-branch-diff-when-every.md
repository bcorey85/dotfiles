---
type: "Change"
change_type: "fixed"
title: "The stage skill reads the branch diff when every phase is committed"
description: "stage.mjs --run on a clean tree classifies the branch diff against its merge-base with the default branch, in report-only mode, instead of finding nothing."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:36:12-05:00"}
seq: 93
kind: "fix"
components: ["skill/stage"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_stage_run.py::StageRunTest::test_committed_branch_changes_are_read_against_the_base_without_staging"
asked: ""
proof: []
unmeasured: ""
---

## Change

- When the working tree has no changes against HEAD, `stage.mjs --run` resolves the base with the existing
  `tools/branch-base` script, diffs against the merge-base, and reports tiers and the jump queue for those files.
- That mode never stages: committed changes have nothing to stage. The report names the base and says report-only.
- That mode logs no `lane=stage` metrics row, so a branch read never counts as a stage run that staged nothing.
- A dirty tree, or a branch with no base or an empty branch diff, behaves as before.

## Evidence

- The stage skill found nothing on every /code run that commits its phases, the point where the reading queue is most
  needed.
- The new test fails on the base commit's `stage.mjs` and passes after.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
