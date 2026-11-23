---
type: "Change"
change_type: "fixed"
title: "A ticket whose Source line spells the queue path with the home folder reads as session-owned"
description: "A lane ticket whose Source line names a session-written queue item with the home folder spelled out (/home/<user>/agent-evals/queue/...) now reads as session-owned criteria, as the ~ spelling already did, so the lane takes the orchestrating session's ruling."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T17:04:57-06:00"}
seq: 35
kind: "fix"
components: ["script/plan-check", "skill/verify-branch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_check.py::PlanCheckCliTest.test_owner_prints_session_when_the_source_line_spells_the_queue_path_with_the_home_folder"
asked: ""
proof: []
unmeasured: "No intake number reads it; the queue item that reported it is the evidence."
---

## Change

`plan_format.queue_source_line` also accepts a `Source:` value that starts with the home folder's agent-evals queue path and turns it into the `~/agent-evals/queue/` form, so `queue_item_author` and `author_owner` read it as they read the `~` spelling. Before, such a line was ignored and the ticket read as `user`. The eng-spec phase-1 text writes `Source: ~/agent-evals/queue/<slug>.md` only when the ticket is a queue file; a lane that pastes a brief gets no Source line from the skill (not edited here).

## Evidence

A forked lane built from a session-written queue item read its criteria owner as user and asked the user to sign off a ruling the orchestrating session had made. A ticket with the `~` Source line already gave `session`; the same line with the home path gave `user` silently.

## Result

The new test fails on the old plan_format (`'user' != 'session'`) and passes now. Guard tests keep a human-written queue item (either spelling) and a ticket with no queue Source at `user`. Full suite passes.

## Watch

None.

## Back-out

Revert the commit: `home_queue_prefix` and the spelling branch go.
