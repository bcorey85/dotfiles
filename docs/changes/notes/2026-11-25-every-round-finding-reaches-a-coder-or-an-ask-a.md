---
type: "Change"
change_type: "changed"
title: "Every round finding reaches a coder or an ask; a used round is refused"
description: "The review loop sends every fix finding of a round to a coder brief or an ask before the next round, and the main session's review call refuses a dispatch whose every report another agent already filled."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T17:36:00-06:00"}
seq: 6
kind: "fix"
components: ["script/review-loop", "script/code-wait"]
evidence: ["tests/scripts/test_review_loop_round_audit.py", "tests/scripts/test_code_wait.py"]
watches: []
test: "tests/scripts/test_review_loop_round_audit.py::RoundAuditTest::test_a_finding_in_no_brief_goes_to_a_coder_pass_and_reads_as_fixed_in_the_prior_issues"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/review_loop_round_audit.py` (a `LoopRun` mixin) records the findings each coder pass is briefed on, and after a round's fix pass `fix_round` checks every fix finding the round's reviewers filed against those briefs and the asks. A finding in neither goes to one coder pass named `coder-missed<round>`, and its prior-issue entry reads fixed, skipped or partial, as the round pass's entries do. A round pass that changed nothing now also reads its findings as skipped ("the coder made no change"), not fixed. `code_wait.py review` records in the round manifest the agent id that filled each report (`filled_by`). `reviewer_dispatch.used_round_problem` makes `code_wait.py review` exit 1 when every pair it is given names a report that a different agent id filled; the call prints the refusal naming the used round and the round to dispatch, then the open round's dispatch lines. The agent that filled a report, run again with the same command, is never refused, on any round, so it prints the next round's lines or `Still working`.

## Evidence

`test_review_loop_round_audit.py` covers briefed, merged-brief, unbriefed, ask, no-change and earlier-round cases, and a loop walk through a two-fix round. `test_code_wait.py` covers the refused stale dispatch.

## Result

Before, a dispatch that named a report another agent had filled was accepted. The loop now also sends any fix finding that no brief or ask holds to a coder before it marks the finding fixed; no real loop path that produces such a finding is known.

## Watch

—

## Back-out

Revert the commit.
