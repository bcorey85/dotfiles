---
type: "Change"
change_type: "fixed"
title: "Permission-question gate lets an answer to the user's question stand"
description: "A reply to a user's question now ends the turn even when it closes on an offer, so the user reads the answer instead of watching the session start unasked work."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T09:30:31-06:00"}
seq: 9
kind: "fix"
components: ["script/staged-claim-gate"]
evidence: ["user report"]
watches: []
test: "tests/scripts/test_staged_claim_gate.py::PermissionQuestionTest::test_an_answer_to_the_users_question_passes_even_when_it_ends_on_an_offer"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The Stop hook's permission-question check passes when the user's newest typed prompt asks a question: a `?` in the
  user's own words, or a question word at the start, and no `can you` / `please` request opening. Pasted blocks,
  reminders, tool results and notices are not the user's words (`lib/user_prompts.py`).
- The block reason now says to send the message again without the closing question, and to start the offered step only
  when the user's request already covers it. It used to say "take the step yourself".
- The transcript is read only when the message ends on an offer. An unreadable transcript judges the message alone, as
  before.

## Evidence

User report, 2026-11-07: a reply that answers their question is replaced when it ends on an offer, and the session
starts work they did not ask for. Tests: `test_an_answer_to_the_users_question_passes_even_when_it_ends_on_an_offer`
and `test_the_reason_says_to_drop_the_question_not_to_start_the_step` fail before and pass after;
`test_an_offer_after_a_handed_over_task_is_still_sent_back` and
`test_a_question_inside_a_paste_or_a_later_tool_result_is_not_the_users_question` keep the old block.

## Result

Hook median on a matching Stop with a 2001-row transcript: 33.4 ms (30.7 ms on a message with no offer), against
7.9 ms for a bare Python start.

## Watch

None: no intake number counts replies replaced by this gate.

## Back-out

Revert the commit; the gate returns to blocking every closing offer with the old reason.
