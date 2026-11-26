---
type: "Change"
change_type: "fixed"
title: "plan_check owner reads a queue item path named anywhere in a pasted brief"
description: "A ticket copied from a pasted brief names its queue item as a path in free text, not a Source line. plan_check owner now reads an existing queue path anywhere in the ticket, so a session-written item gives owner session."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-25T16:00:00-06:00"}
seq: 4
kind: "fix"
components: ["script/plan-format"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_check.py::PlanCheckCliTest::test_owner_prints_session_for_a_queue_path_named_in_free_text_in_either_spelling"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

A lane started from a pasted brief names the queue item as `Read ~/agent-evals/queue/<slug>.md`, so the owner read
`user` and plan cuts went to the user. `criteria_owner` now takes every existing queue path named in the text (either
spelling) beside the `Source:` lines and reads the owner as it does for them: a named `human:` item makes it `user`,
and an all-session ticket keeps the first `Source:` line as `source`. A path whose file is missing is ignored.

## Evidence

Judgment from the failing tests written first.

## Result

The new tests print `session` for both spellings, `user` for a human-written item and for a missing file, and fail on
an item with no `generated.by`.

## Watch

None: tests pin it.

## Back-out

`git revert` the commit.
