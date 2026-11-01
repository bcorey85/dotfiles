---
type: "Change"
change_type: "fixed"
title: "an ask with an empty change marker asks its question"
description: "An ask that ends on an empty change: marker uses its question as its change, as an ask with no marker does, in place of failing the packet as a critical blocker."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:56:52-06:00"}
seq: 431
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_an_ask_with_an_empty_change_asks_its_question_as_the_change"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `review_loop_packet.ask_entry`: when the text after the last `change:` marker is empty, the change is the text
  before it.
- The test that pinned the critical-blocker stop on an empty change now pins the new entry.

## Evidence

judgment: a bug hunt on master 22c42b39 found that one reviewer ask ending in "change:" with nothing after it made
the packet fail to parse ("ask entry has no change"), so the whole loop ended critical-blocker and every fix it
made went unreported as a clean hand-back.

## Result

The named test fails before (exit 1, critical-blocker) and passes after (exit 0, the ask's question and change are
both its question). `test_review_loop_script` and `test_change_size_bar`: 207 tests, 0 failed; ruff clean.

## Watch

None. A bad ask entry still fails the packet check loudly.

## Back-out

Revert the fallback in `ask_entry` and restore the critical-blocker test.
