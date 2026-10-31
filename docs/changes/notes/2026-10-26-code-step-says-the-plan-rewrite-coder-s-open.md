---
type: "Change"
change_type: "changed"
title: "code_step says the plan-rewrite coder's open choices to the user"
description: "The plan-rewrite coder may not ask the user; it ends its report with one `OPEN CHOICE:` line per choice the ruling leaves open, and `after-plan-edit` says each one to the user."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T23:05:53-05:00"}
seq: 83
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_hand_back.py::HandBackTest::test_the_plan_edit_coders_open_choice_reaches_the_hand_back_and_the_prompt_says_where_it_goes"
asked: ""
proof: []
unmeasured: "Plan-rewrite reports are not logged; no intake number reads them."
---

## Change

`plan_edit_prompt` tells the coder to end with `OPEN CHOICE: <one line>` lines instead of asking; `command_after_plan_edit`
reads them through `plan_edit_open_choices` and puts them in say.md before the review dispatch.

## Evidence

After `decide adopt`, the plan-rewrite coder ended with a choice for the user (one more plan step for a later phase?);
the run went straight to review and the hand-back said only that the plan states the ruling.

## Result

A choice the rewrite leaves open reaches the user.

## Watch

None.

## Back-out

Revert the commit.
