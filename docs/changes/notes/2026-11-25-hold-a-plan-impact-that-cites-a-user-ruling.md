---
type: "Change"
change_type: "fixed"
title: "Hold a plan impact that cites a user ruling"
description: "A plan impact with no criterion change that quotes or points at a sign-off line the user ruled in the decision log is held for a ruling instead of adopted as code-wins."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T16:23:36-06:00"}
seq: 5
kind: "fix"
components: ["script/review-loop-ruled", "script/signoff-lines"]
evidence: ["tests/scripts/test_review_loop_ruled.py"]
watches: []
test: "tests/scripts/test_review_loop_ruled.py::UserRulingImpactTest::test_an_impact_quoting_a_user_ruled_line_is_held_and_prints_no_deviation"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

route_plan_items records an impact as not adopted and holds it for a ruling when it names the decision log (or the plan's Plan Deviations) and quotes, or points by line number at, a line of a user-ruled sign-off entry. A coder's PLAN-IMPACT is held the same way. A quote of any line of a user-ruled entry (a line of three or more words, or the whole entry), or a pointer at any of its line numbers, matches; the ruler need not sit on that line. The `The ruling:` text that `ruling_deviation` writes after a blank line belongs to the entry above it, quoted with or without its label. signoff_lines.py gains `cites_user_ruling`, `unit_is_user_ruled` and `signoff_entry_ranges`.

An entry is user-ruled through the owner, `is_session_ruled`: it holds a marker line (`ruled`, `ruling`, `sign-off`, `signed off`, or a `... by` form, now also `relayed by`) that no session rules. It fails closed: a marker line that names no ruler reads as the user's. An entry with no marker line is no user ruling; unlike `records_user_signoff`, no other entry of the file stands in for it.

`SESSION_RULER` now also reads as a session: an `agent-evals-*` name, `lane session` or `orchestrating session` anywhere on the line, `by` the or this (named) lane or session, `session` as a listed owner (`(session, <date>)`, `(session <id>)`, `, session,`, `session (lane ...)`), and `Lane call`.

`USER_SIGNOFF` wins over a session ruler on the same line. It now also reads `ruled by: user`, `the user ruled|approved|signed`, and a `relayed by` on a line that names the user. `user sign-off` and `sign-off:` followed by a session name no longer count.

## Evidence

`UserRulingImpactTest` fails before the change: the impact was adopted and printed a Plan Deviations line that reversed the ruling. Impacts that cite no log, quote no line, or quote a session-ruled line are still adopted by rule. `UserRuledLineTest` reads one-line logs through `records_user_signoff`; its session-name, `Lane call`, `ruled by: user` and `relayed by` cases fail before the `SESSION_RULER` and `USER_SIGNOFF` change.

Sweep over every real log (67 files: decision logs and plans with a `## Plan Deviations` section, in this repo's `docs/plans` and `~/dev/*/docs/plans`): 545 sign-off units, parsed 545 of 545. 168 read as user-ruled, against 32 under the line reader this branch had before. 137 units flip from session to user: entries with a ruling marker and no session named on any marker line (`Phase 2 ruling: ...`, `**Choice**: six rulings ...`), which the fail-closed owner reads as the user's. A person's name that signed off or ruled stays the user's beside a session name (`Brandon Corey signed off, directly to agent-evals-5e`, `queue-fixes/plan.md:77`). 1 flips from user to session: `queue-fixes/plan.md:91`, a disagreement block under the 21:33 entry `Ruled by the queue-fixes lane session, not the user`; the old reader took the quoted `User sign-off: Brandon Corey` inside the block as a ruler.

## Result

A reviewer or coder impact that quotes, or points by line number at, a line of a sign-off entry the user ruled is held, never recorded as overridden by the code. An impact that cites a session-ruled entry is still adopted by rule (AC14).

## Watch

None.

## Back-out

Revert the commit.
