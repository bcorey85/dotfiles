---
type: "Change"
title: "An ask with an empty question asks its change"
description: "The review loop no longer builds an ask with an empty question unless it has no change either, and packet validation fills an empty ask question from its finding or its change, so one such entry no longer fails the whole review."
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
- `handback.normalize_ask`: an ask with no question takes its finding, or else its change. An ask with neither still fails validation.
- `agents/review-loop.md` and its opencode port: an ask's question is never empty; an ask with no question takes its finding, or else its change, as its question.

## Evidence

- A /code phase review returned an ask with `question: ''`, a change and `file_line: unlocated`. Validation refused the packet, the loop script turned it into a tool fault, and /code stopped with "found nothing".

## Result

- On the base scripts the new tests in `test_handback.py` and `test_review_loop_script.py` fail. On this change they pass.

## Watch

—

## Back-out

Revert the commit. An ask with an empty question fails the whole packet again.
