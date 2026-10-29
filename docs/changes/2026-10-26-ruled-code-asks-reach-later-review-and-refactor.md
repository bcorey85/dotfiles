---
type: "Change"
change_type: "fixed"
title: "Ruled /code asks reach later review and refactor passes"
description: "asks-done and pre-set ask outcomes are saved in the code-step state directory, and later review hand-offs and the closing refactor prompt list them so a matching finding is dropped instead of raised again."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T00:15:29-05:00"}
seq: 2
kind: "fix"
components: ["script/code-step", "agent/review-loop", "skill/refactor"]
evidence: ["judgment", "tests"]
watches: []
test: "tests/scripts/test_code_step_open_phase.py::AskOutcomesReachLaterPasses::test_a_ruled_ask_is_in_the_review_handoff_of_a_later_phase"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `record_ruled_asks` writes each ask outcome to `ruled-asks.json` in the code-step state directory; a new planless task clears it.
- `handoff_block` adds a `ruled-asks:` list and `emit_closing_skill` adds an "Asks already ruled" list, both for the same plan only.
- `review-loop.md` and `refactor/SKILL.md` each get one line: drop a finding that matches a ruled ask and never undo its outcome.

## Evidence

Judgment: a later /refactor pass reversed an ask that asks-done had ruled, because outcomes lived only in the review log and a fresh fork never saw them. Tests: `test_code_step_open_phase.py` (6 for this defect) failed on the unfixed script and pass now.

## Result

Not installed yet.

## Watch

None. A fix: tests prove it.

## Back-out

Revert the three edited files plus `code_step_core.py`, and delete the test file. A leftover `ruled-asks.json` is ignored.
