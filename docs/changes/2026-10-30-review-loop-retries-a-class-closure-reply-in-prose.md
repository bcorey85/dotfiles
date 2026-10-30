---
type: "Change"
change_type: "fixed"
title: "Review loop retries a class-closure reply in prose, and the staged-claim hook skips staged review data"
description: "A /code phase review no longer stops as a tool fault when the class-closure reply holds prose: it asks once more for the JSON object, and the staged-claim hook that provoked the prose no longer fires on staged rows, records, diffs or findings."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T08:45:24-05:00"}
seq: 338
kind: "fix"
components: ["script/review-loop-script", "script/staged-claim-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_closure.py::ClosureCheckRetryTest::test_a_prose_reply_is_retried_once_and_the_second_reply_is_parsed"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `closure_check` retries once when the class-closure reply holds no `{"receipt", "open"}` object, the way the
  disposition call already does: the retry quotes the first error, cut to 200 characters, asks for the JSON object
  only, and runs under its own role, `class-closure-retry`. A second miss raises as before.
- The retry lives in one helper, `reply_with_one_retry`, which the disposition call now uses too, with no change to
  what it does.
- The staged-claim hook skips a claim whose subject is rows, records, diffs or findings (the word just before the
  claim, in a clause that names no file), unless the sentence also names the index or git. "The fix diffs are staged under fix-diffs." no longer blocks; "All files are staged." still
  does. Every staged claim in a sentence is judged on its own clause, so "Two rows are staged, and all files are
  staged." still blocks.

## Evidence

- One /code phase review stopped as a tool fault: the staged-claim hook read "staged" in the reviewer's closure reply
  as a claim about the git index, the reviewer answered the hook in prose, and the loop raised on the missing JSON
  object, so the review ran again from the start.

## Result

Against the code before this change, the retry test errors (the first prose reply raises at once) and both review-data
cases of the staged-claim test block on an empty index. After it, `test_review_loop_closure.py` and
`test_staged_claim_gate.py` pass (17 tests) and ruff passes.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. A prose class-closure reply then stops the review at once, and the staged-claim hook again blocks
any staged wording when the index is empty.
