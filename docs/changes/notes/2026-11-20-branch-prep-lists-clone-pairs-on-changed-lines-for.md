---
type: "Change"
change_type: "fixed"
title: "Branch-prep lists clone pairs on changed lines for the smell-reviewer"
description: "refactor_flow branch-prep runs jscpd at 40 tokens over the repo and prints the pairs that have a site on a line the branch changed in the smell-reviewer prompt, so a helper copied from a sibling folder reaches the reviewer."
generated: {"by": "process:coder", "at": "2026-11-20T13:56:52-06:00"}
seq: 1
kind: "fix"
components: ["skill/refactor", "script/refactor-flow", "script/clone-pairs"]
evidence: ["branch-refactor-misses-small-duplication-in", "branch-work-duplicates-helpers-that-sibling-tool"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_branch_prep_lists_a_clone_pair_that_touches_a_changed_line"
asked: ""
proof: []
unmeasured: ""
---

## Change

`branch-prep` runs jscpd over the repo root at `--min-tokens 40` and keeps each pair with a site on a line the branch added (diff lines plus every line of an untracked file). The pairs go in the smell-reviewer prompt, capped at 40, with a one-line summary in the scope header. With `--head` it skips detection and says so. The jscpd code moved to `clone_pairs.py`, shared with `audit-prep`, which reads jscpd's JSON report (`duplicates[]` with `format` and `firstFile`/`secondFile` of `name`, `start`, `end`) through one reader; a missing or misshapen report is a `jscpd output did not parse` note. Branch-prep drops the prose formats `markdown`, `text` and `txt` before the cap.

## Evidence

Queue items `branch-refactor-misses-small-duplication-in` and `branch-work-duplicates-helpers-that-sibling-tool`.

## Result

Eleven branch-prep clone tests in `test_refactor_flow.py` and report-reader tests in `test_clone_pairs.py`.

## Watch

None.

## Back-out

Revert the commit.
