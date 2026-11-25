---
type: "Change"
change_type: "fixed"
title: "Cap stop line names the orchestrating session"
description: "When a /code phase review stays cap-reached in a lane another session started, code_wait now prints a STOP line that names that session as the one that rules on the cap, in place of the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T02:48:51-06:00"}
seq: 1
kind: "fix"
components: ["script/code-wait"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_wait.py::WaitReviewTest::test_a_cap_reached_packet_in_a_lane_names_the_orchestrating_session_as_the_ruler"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`claude/.claude/scripts/code/code_wait.py` `phase_stop_line` gains a cap-reached route. When the phase packet's
effective status (`capped_review.effective_status`) stays `cap-reached` and the lane entry holding the repo
(`lane_entries.entry_containing`) has a non-empty `reports_to`, it prints a STOP line that names that session as the
cap's ruler: write findings_remaining to the run's stop.md, send them to that session with SendMessage, record its
reply under `## Plan Deviations` as ruled by session with the date of its reply, then `/code resume`. code_wait exits
1. With no lane entry, an empty `reports_to`, or a refused lane file (a stderr note naming code_wait), the output is
unchanged and the skill's user-facing cap route applies. `tests/scripts/test_code_wait.py` covers the five cases.

## Evidence

Judgment: a lane session hit the cap and read the cap text as asking the user, though its brief named an orchestrating
session that rules on caps.

## Result

The targeted tests pass; the review loop's full check passed 6456/0.

## Watch

None: the test pins the behavior.

## Back-out

Revert the commit; code_wait then prints no cap stop line and the skill's cap-reached route names the user again.
