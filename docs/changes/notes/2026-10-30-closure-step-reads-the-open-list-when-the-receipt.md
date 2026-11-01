---
type: "Change"
change_type: "fixed"
title: "Closure step reads the open list when the receipt holds a raw quote"
description: "The review loop's class-closure step now reads the reply's `\"open\": [..]` list when the whole object does not decode, so a raw double quote in the free-text receipt no longer ends a clean review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T08:02:50-05:00"}
seq: 394
kind: "fix"
components: ["script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ClosureCheckTest::test_a_receipt_with_a_raw_quote_still_reads_its_open_list"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `closure_check` in `review_loop_closure.py` falls back to `closure_from_open_list` when no JSON object decodes. That
  helper decodes the list after the last `"open": [` and keeps the text after the `"receipt":` key, without its wrapping quotes, as the receipt.
- An open list that does not decode still raises, as before.
- The closure prompt now tells the model to escape every double quote inside the receipt.

## Evidence

- A /code review stopped at the closure call with "holds no {"receipt": .., "open": [..]} object". The reply ended
  with `"open": []`, but the receipt held code with a raw `"`, so the decoder failed and a clean review needed a rerun.

## Result

- The named test fails before (ValueError) and passes after. The prompt test fails before and passes after.
  `test_an_open_list_that_does_not_decode_still_raises` pins the raise.

## Watch

—

## Back-out

Revert the commit.
