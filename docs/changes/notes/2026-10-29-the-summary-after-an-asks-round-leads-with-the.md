---
type: "Change"
change_type: "changed"
title: "The summary after an asks round leads with the current asks coder"
description: "After a round of review asks, the /code review summary leads with the current asks coder's report, shows earlier asks rounds as one line each, and drops the why notes the asks coder replaced."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T13:46:31-05:00"}
seq: 269
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_the_summary_after_two_asks_rounds_leads_with_the_current_asks_coder"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_review.emit_review_dispatch`: after an asks round, the summary in say.md starts with
  `Ask-fix coder (current report):`. The newest asks round is shown in full, each earlier round is one
  `Earlier ask-fix round N:` line, and the phase coder's behavior is one `Phase coder's behavior (earlier):` line. A
  run with no asks round prints `Implemented:` as before.
- `code_step.record_coder_report` keeps the asks rounds as one list per round in `state["askRounds"]`, and the
  summary's notes in `state["summaryWhy"]`. Those notes are the asks coder's for the files it changed, and the earlier
  notes for every other file. `state["why"]`, which the reviewer prompt reads, is unchanged.
- `migrate_old_state` turns an old flat `askFixBehavior` into one earlier round.
- A stopped coder's stage is kept as `coderStage` in the stop record, from both the stop on its report and the wait
  cap; a coder capped again after a resume keeps it. `put_resumed_coder_back` restores it, so a resumed asks coder goes back to the asks-coder stage, not the phase
  coder stage, and its summary reads as an asks round.

## Evidence

- A stop after an asks round handed back the phase coder's report as current. It named a basis the asks coder had
  renamed, and a member the asks coder had since answered.

## Result

- The named test fails before (the summary led with the phase coder's behavior and kept the replaced note) and passes
  after. Further tests pin the kept note on a file the asks coder did not touch and an old flat state.

## Watch

—

## Back-out

Revert the commit.
