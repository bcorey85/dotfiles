---
type: "Change"
change_type: "fixed"
title: "A review fix pass keeps an owner-line edit to the scripts CLAUDE.md under a standing ruling"
description: "A review fix pass keeps an owner-line edit to the scripts CLAUDE.md when a standing ruling covers owner lines."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T22:21:14-06:00"}
seq: 38
kind: "fix"
components: ["script/review-loop-ruled", "script/standing-rulings", "script/owner-lines"]
evidence: ["queue item"]
watches: []
test: "tests/scripts/test_owner_lines.py::OwnerLinesOnlyTest.test_every_other_edit_is_false; tests/scripts/test_review_loop_ruled.py::OwnerLineEditTest.test_only_an_owner_line_edit_stands_under_the_ruling; tests/scripts/test_plan_format.py::CriteriaOwnerTest.test_a_pasted_brief_lane_ticket_with_one_source_line_per_item_is_session_owned"
asked: ""
proof: []
unmeasured: "No intake number reads it; the queue item that reported it is the evidence."
---

## Change

`lib/owner_lines.py` reads the owner-line format of the scripts CLAUDE.md and says whether an edit only adds or updates owner bullets. `lib/standing_rulings.py` accepts `covers: owner-lines` beside `covers: rewords`, read by `owner_line_ruling`. The review loop (`review/review_loop_ruled.py`) keeps a ruled owner-line edit instead of reverting it.

The ruling line has this exact form:

`Standing ruling by <who> at <YYYY-MM-DD>: <paraphrase, no quote marks> covers: owner-lines`

It goes in the lane's `03-decisions.md`, or in the plan's `## Plan Deviations`. It must be in place before the fix pass starts: a ruling the pass itself adds does not count. Under it, only adds and updates inside `## Owners` stand; any other edit, a mixed edit or a removed bullet reverts as before. Close pass: owner-line updates must map each old bullet to its own new bullet in order; the standing-ruling wording lets the session rule rewords only for criteria it owns.

The queue item's second item closes on evidence: a replay of a pasted-brief lane ticket reads owner `session`, and a pin test in `CriteriaOwnerTest` holds that shape. No failing replay exists, so there is no code change for it.

The glossary gains three edits: the approval-only file entry names the owner-line exception and `review/review_loop_ruled.py`, the standing ruling entry covers owner-line edits, and a new owner line entry names `lib/owner_lines.py`.

Merge dependency: this branch merges after `fix/toolkit-rules-nov22`, which owns the neighboring edits to the scripts CLAUDE.md.

## Evidence

Queue item: review-fix-pass-lets-an-owner-line-edit-in-the.

## Result

The owner-line and review-loop tests fail without the change. The `CriteriaOwnerTest` pin passes before and after, as regression cover for the pasted-brief ticket shape.

## Watch

None.

## Back-out

Revert the commit and remove any `covers: owner-lines` line from plans, which would then raise `PlanFormatError`.
