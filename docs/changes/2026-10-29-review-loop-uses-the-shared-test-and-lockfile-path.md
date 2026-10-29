---
type: "Change"
title: "Review loop uses the shared test and lockfile path rules"
description: "The scripted review loop routes tests to the test reviewer and sizes a change by the same test and lockfile rules as the other scripts, so __tests__/, test_*.py, *_test.* and nested tests/ files and every lockfile are recognised. Generated, dist/, snapshot and .min.js files also no longer count toward the size bar."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T09:35:48-05:00"}
seq: 248
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_added_lines_of_tests_and_any_lockfile_stay_out_of_the_size_bar"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_loop_script.py` drops its own `is_test` and the `package-lock.json` suffix check. Reviewer routing (first
round and round two) calls `source_paths.is_test_path`, and `counts_toward_size` calls
`source_paths.is_counted_source` (plus its own `.md` doc rule). The lockfile list and the test-path rules live in
`lib/source_paths.py` only. Generated, `dist/`, snapshot and `.min.js` files, which that module does not count as
source, also no longer count toward the size bar.

## Evidence

Fail-first: the two new tests in `tests/scripts/test_review_loop_script.py` failed on the old code. A
`__tests__/`, `test_*.py`, `*_test.go` or nested `tests/` file went to the code reviewer (no `test-reviewer`
dispatch), and added lines in those files or in `yarn.lock`, `poetry.lock` or `pnpm-lock.yaml` tripped the size bar
and added a smell reviewer.

## Result

Both new tests pass; the whole review-loop-script and source-paths test files pass (124 tests).

## Watch

—

## Back-out

Revert the commit.
