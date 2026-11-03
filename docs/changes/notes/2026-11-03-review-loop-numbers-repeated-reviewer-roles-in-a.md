---
type: "Change"
change_type: "fixed"
title: "review loop numbers repeated reviewer roles in a round"
description: "When a large diff split one reviewer agent over two dispatches in a round, both shared a role and so one report file, and the scripted loop waited out its 1800 s timeout. The round writer now numbers repeated roles (`-2`, `-3`) before any file is written, so each dispatch gets its own prompt and report file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T09:45:24-06:00"}
seq: 3
kind: "fix"
components: ["script/reviewer-dispatch"]
evidence: ["bench hang", "tests"]
watches: []
test: "tests/scripts/test_reviewer_dispatch.py::test_two_requests_for_one_role_get_their_own_files_and_both_reports_return"
asked: ""
proof: []
unmeasured: ""
---

## Change

`reviewer_dispatch.write_round` keeps a set of the roles taken in the round and suffixes a repeat `-2`, `-3`, and so
on, before it writes the prompt file, the report file path and the manifest. `request_round` keys its waits by that
unique role, so it returns once each report file holds text. Shipped on the branch in commit `5ead9d30`.

## Evidence

The one-round bench (onepass12) hung on a phase whose large diff sent two code-reviewers in one round: both wrote
`review1-code-reviewer.report.md`, the wait counted one report for two requests and timed out. Before the fix the
same two-request round gives 1 distinct report file and `request_round` raises after its timeout; after it, 2 files
and both reports return.

## Result

`test_reviewer_dispatch.py` 8 tests pass; the new test fails against the pre-fix module (1 report file, timeout).

## Watch

None: the test pins the behaviour.

## Back-out

Revert the numbering loop in `write_round`; split rounds then hang again.
