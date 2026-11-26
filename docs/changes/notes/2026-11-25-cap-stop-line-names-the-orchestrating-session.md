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
cap's ruler: write findings_remaining and a `Ruling: session <name>` line (`cap_ruler_line`) to the run's stop.md,
end the run, then `/code resume`. The ruler line tells the lane session to send the findings to that session with
SendMessage, take its reply as the stop's feedback, and when the run has a plan file, a coder records it in the
plan's decision log (`03-decisions.md`, or `## Plan Deviations` when the plan has none) as ruled by session
`<reports_to>` with the date of its reply. code_wait exits 1. With no lane entry, an empty `reports_to`, or a
refused lane file (a stderr note naming code_wait), the output is unchanged and the skill's user-facing cap route
applies.

On that route the `cap reached after N fix round(s)` summary line and the finding-asks notice (the `phase-asks-open`
row and the `phase_asks.py rule` line) still print, before the STOP line, which stays last. The STOP line tells the
fork to write the printed finding asks to stop.md with `findings_remaining`. `phase_stop_line` returns the step
line with the loaded packet, set only on the cap STOP, and `print_ended_loop_and_held` prints the summary and asks
from that packet, so the decision and the packet read happen once. When the asks cannot be opened, their
failure step prints last in place of the STOP line and the exit code is 1.

The step line (STOP or restart) now always prints last, on its own line, after the `Tool fault:` and held-released
lines: `print_ended_loop` returns it and `print_ended_loop_and_held` prints it. The restart step used to end the
no-output and LOOP_GONE line.

`tests/scripts/test_code_wait.py` covers six cap cases (named ruler, no lane entry, empty `reports_to`, invalid packet,
a clean packet that reads as deferred, refused lane file), the step-line order tests, which include the cap stop
line staying last when the scope file lists a held-released path, and
`test_the_cap_summary_and_the_asks_notice_print_before_the_cap_stop_line_in_a_lane`,
`test_a_cap_reached_packet_with_no_review_out_prints_the_restart_step_and_no_cap_summary` and
`test_asks_that_cannot_be_opened_keep_their_rerun_step_as_the_last_line_in_a_lane`.

## Evidence

Judgment: a lane session hit the cap and read the cap text as asking the user, though its brief named an orchestrating
session that rules on caps.

## Result

The targeted tests pass.

## Watch

None: the test pins the behavior.

## Back-out

Revert the commit; code_wait then prints no cap stop line and the skill's cap-reached route names the user again.
