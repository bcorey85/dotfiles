---
type: "Change"
change_type: "fixed"
title: "The full suite passes under a relative PYTHONPATH such as tests/scripts"
description: "The test helper makes relative PYTHONPATH and NODE_PATH entries absolute, so nested fixture repos stop reading them as paths inside themselves."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T20:40:55-06:00"}
seq: 37
kind: "fix"
components: ["script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_paths.py::ToolkitPathsTest::test_a_relative_pythonpath_entry_becomes_absolute_so_no_nested_repo_claims_it"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; no intake number reads it."
---

## Change

tests/scripts/toolkit_paths.py (imported by every test) makes each relative PYTHONPATH and NODE_PATH entry absolute on import. The script side is unchanged: a relative entry in a real run is inside the repo, so skipping the base run there is correct.

## Evidence

Judgment: the full suite with PYTHONPATH=tests/scripts exported failed test_full_check (BaseComparisonTest, base_run returned None) and test_review_loop_script, because the ambient relative entry resolved inside each nested fixture repo.

## Result

The new test pins the rewrite. The full suite with PYTHONPATH=tests/scripts exported now passes: 5671 tests, 0 failed; before, test_full_check and test_review_loop_script failed under it. Lint passes.

## Watch

None.

## Back-out

Revert the commit.
