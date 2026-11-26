---
type: "Change"
change_type: "added"
title: "adr runs after the PR and adr_flow status reports a branch not finished"
description: "adr_flow.py status reports a branch whose PR exists and whose task dir remains as not finished, and the branch-end skills run /adr as a numbered step after the PR."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:23:48-06:00"}
seq: 7
kind: "fix"
components: ["skill/adr", "skill/verify-branch", "skill/close-branch", "skill/branch-recap"]
evidence: ["tests/scripts/test_adr_flow.py", "tests/scripts/test_guidance_rules.py"]
watches: []
test: "tests/scripts/test_adr_flow.py::AdrFlowTest::test_status_with_a_pr_and_a_task_dir_left_is_not_finished"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `adr_flow.py status [<plan folder>]` prints `adr: not finished`, `adr: done`, `adr: no PR yet` or `adr: cannot tell: <reason>`. /verify-branch and /close-branch make /adr then `status` a numbered step once the PR exists; README, closing-phases and branch-recap say the same order; the opencode adr command follows.

## Evidence

The status test fails on the old tree (no `status` verb) and passes on the new one. The full check passed on the final tree (6728 tests, 0 failed).

## Result

Rule-meter arms pending.

## Watch

—

## Back-out

Revert the commit.
