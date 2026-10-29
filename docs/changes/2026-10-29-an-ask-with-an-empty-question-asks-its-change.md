---
type: "Change"
title: "An ask with an empty question asks its change"
description: "The review loop no longer builds an ask with an empty question unless it has no change either. Packet validation fills an empty ask question from its finding or its change, and drops an ask with none of them under a Dropped asks warning, so one bad ask no longer fails the whole review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T21:00:00-05:00"}
seq: 242
kind: "fix"
components: ["script/review-loop-script", "script/handback", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::ParseTest::test_an_ask_with_an_empty_question_asks_its_change"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_packet.ask_entry`: an ask text that opens with its `change:` marker takes the change as its question.
- `handback.normalize_ask`: an ask with no question takes its finding, or else its change.
- `handback.drop_unaskable_asks`: an ask with no question, finding or change is dropped from the packet. The other asks and fields stand. `handback.print_dropped_asks` prints the warnings once, right after the load and before any route, in `review_fix.py packet`, `code_step_review.load_review_packet` and `handback.py check`.
- `agents/review-loop.md` and its opencode port: an ask's question is never empty; an ask with no question takes its finding, or else its change, as its question.

## Evidence

- A /code phase review returned an ask with `question: ''`, a change and `file_line: unlocated`. Validation refused the packet, the loop script turned it into a tool fault, and /code stopped with "found nothing".

## Result

- On the base scripts the new tests in `test_handback.py`, `test_review_fix_script.py` and `test_code_step_review_script.py` fail. On this change they pass.

## Watch

—

## Back-out

Revert the commit. An ask with an empty question fails the whole packet again.
