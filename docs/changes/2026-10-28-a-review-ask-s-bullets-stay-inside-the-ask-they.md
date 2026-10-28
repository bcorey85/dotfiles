---
type: "Change"
title: "A review ask's bullets stay inside the ask they follow"
description: "A multi-line ask (a mapping lead, then plain-text bullets at the same indent) parsed as one ask per bullet, so asks-done wanted an outcome for each; the bullets now join the lead ask's question, and the /code asks-done refusal names how many outcomes it expects."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:54:45-05:00"}
seq: 193
kind: "fix"
components: ["script/handback", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::ParseTest::test_bullets_after_a_mapping_ask_stay_inside_that_ask"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `handback.fold_bullets_into_asks`: in the `ask` list, a plain-text entry that follows a mapping ask adds to that ask's
  question, or to its finding when it has no question. Plain-text asks with no mapping before them stay separate asks.
- `code_step.py asks-done` with the wrong count adds "N ask(s) wait: give N outcome(s), in order." to its refusal.

## Evidence

- A queued report: one ask with a lead line and five bullets became six asks, five of them unlocated. asks-done refused
  one outcome, and the forked run stopped without advancing.

## Result

- The new parse test reads one ask holding every bullet; test_code_step_cap_reached.py's
  `test_asks_done_with_the_wrong_number_of_outcomes_names_how_many_it_expects` reads the count. Both failed before.

## Watch

—

## Back-out

Revert the commit.
