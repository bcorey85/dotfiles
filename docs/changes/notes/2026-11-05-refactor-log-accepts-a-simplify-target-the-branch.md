---
type: "Change"
change_type: "fixed"
title: "refactor log accepts a simplify target the branch deleted"
description: "refactor_flow.py log accepts an audit or simplify target that is gone from the index but tracked at HEAD, prints it as deleted, and counts its HEAD lines in diff_loc."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T17:21:47-06:00"}
seq: 13
kind: "fix"
components: ["skill/refactor"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_log_simplify_accepts_a_target_the_branch_deleted_and_refuses_one_never_tracked"
asked: ""
proof: []
unmeasured: ""
---

## Change

`check_targets_match` accepts a target that matches no file in the index when it matches a file at `HEAD`, and prints one line naming it as deleted. A target in neither still raises. `diff_loc_for` counts deleted target files from `HEAD`, so the finder row no longer logs 0 lines for them.

## Evidence

judgment: a simplify fix deleted a slice file and staged the deletion; `log` exited 1 ("matches no tracked file"), the caller dropped the path, and the logged target no longer matched the slice that ran. The new test fails on f22db22c and passes after.

## Result

Full check 3213 tests, 0 failed.

## Watch

—

## Back-out

Revert the HEAD fallback in `check_targets_match` and `diff_loc_for`, and the test.
