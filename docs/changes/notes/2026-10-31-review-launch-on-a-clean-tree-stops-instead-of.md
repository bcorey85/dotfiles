---
type: "Change"
change_type: "fixed"
title: "review launch on a clean tree stops instead of passing an empty review"
description: "/review's scripted launch stops on a working tree with no changes and names the base= route, so a commit or merge is never passed as reviewed when no reviewer read any code."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T19:19:39-05:00"}
seq: 406
kind: "fix"
components: ["script/review-fix", "skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_launch_on_a_clean_tree_stops_naming_the_empty_scope_and_the_base_route"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_fix.py launch` reads the working tree's status before it records a dispatch. With no dirty or untracked
  file it stops with `ACTION: stop-usage`, exit 2, a line that says the review scope is empty, and the route for
  committed work: dispatch review-loop with `base=<ref>`. Nothing is launched or recorded.
- `launch --help` prints its usage and exits 0.
- `/review` step 1: on `ACTION: stop-usage` from launch, skip step 2, show the user the lines, never report a clean
  review.

## Evidence

judgment: after a commit, launch on the clean tree ran the loop, which found no diff and handed back
`Fixed 0` and "Ready for /commit". A session reviewing a merge it just committed got a clean result no reviewer
produced.

## Result

The named test fails before (launch runs the loop and exits 0) and passes after, with a `--help` test and one
that a clean `--repo` stops even when the cwd's repo is dirty. The launch tests that expect a run now edit a file
first. `test_review_fix_script`: 151 tests, 0 failed; ruff clean.

## Watch

None. The stop prints its reason in the session.

## Back-out

Revert the status check and the help argument in `launch_arguments` and `command_launch`, the step 1 sentence in the
review skill, and the two tests.
