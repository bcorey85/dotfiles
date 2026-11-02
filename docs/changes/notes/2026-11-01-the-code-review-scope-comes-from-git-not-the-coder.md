---
type: "Change"
change_type: "fixed"
title: "The code review scope comes from git, not the coder's list"
description: "The /code handoff now takes its changed files from git, so reviewers stop spending findings on files and claims the coder got wrong."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T19:12:00-06:00"}
seq: 454
kind: "fix"
components: ["skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_review_start.py::CodeReviewStartTest::test_the_handoff_files_come_from_git_and_only_the_coders_why_lines_are_kept"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_review_start.py` replaces the handoff's `files` block with what git shows changed since the phase base, tracked and untracked. Only the coder's `why` lines are kept, under the matching path. A base that is not a commit stops the run. The /code skill and the handoff schema now say the script owns the list.

## Evidence

Reviewers on two bench tickets found handoffs that left out 3 and 4 changed files, carried stale line numbers, or claimed an export that did not exist. The rule that the handoff is the exact scope entered on 2026-05-30 with no stated reason.

## Result

Both new tests fail on the old code and pass on the new. The full suite passes: 3013 tests, 0 failed.

## Watch

None. The /fix and /refactor handoffs still write the list by hand, queued.

## Back-out

Revert the branch merge.
