---
type: "Change"
change_type: "fixed"
title: "A review ask's bullets stay inside the ask they follow"
description: "In a multi-line ask (a mapping lead, then plain-text bullets at the same indent) the bullets now join the lead ask's question, and the /code asks-done refusal names how many outcomes it expects. Before, each bullet parsed as its own ask, so asks-done wanted an outcome for each."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T13:54:45-05:00"}
seq: 204
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
  question, or to its finding when it has no question. A mapping entry with no file_line and no finding adds its fields
  to that ask; only question and change are joined with a newline, any other field keeps the lead's value. A bullet
  that carries a `| path:line` field starts a new ask; a location at the start of a fact bullet
  does not. Plain-text asks with no mapping before them stay separate asks.
- `code_step.py asks-done` with the wrong count adds "N ask(s) wait: give N outcome(s), in order." to its refusal.

## Evidence

- A queued report: one ask with a lead line and five bullets became six asks, five of them unlocated. asks-done refused
  one outcome, and the forked run stopped without advancing.

## Result

- The new parse test reads one ask holding every bullet; test_code_step_cap_reached.py's
  `test_asks_done_with_the_wrong_number_of_outcomes_names_how_many_it_expects` reads the count. Both failed before.
  Four more parse tests in test_handback.py pin the edges: a mid-sentence or leading location stays in the ask, a
  `| path:line` bullet is its own ask, and a key-only mapping joins the lead ask.

## Watch

—

## Back-out

Revert the commit.
