---
type: "Change"
change_type: "fixed"
title: "class closure repairs left_alone objects and retries a shape error once"
description: "A class-closure reply whose left_alone holds objects is repaired to strings with no retry, and any other shape error gets one retry before the loop stops."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T17:09:12-06:00"}
seq: 8
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["class-closure-left-alone-shape-error-aborts-review"]
watches: []
test: "tests/scripts/test_review_loop_closure.py::ClosureCheckRetryTest::test_a_left_alone_object_is_repaired_to_one_string_with_no_retry"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_loop_closure.py` `repaired_closure_problem` turns each `left_alone` object into one string. A reply
that still fails its shape check is asked for once more before the loop stops.

## Evidence

A reviewer returned `left_alone` objects and the whole review aborted on the shape error.

## Result

`ClosureCheckRetryTest` in `test_review_loop_closure.py`.

## Watch

None.

## Back-out

Revert the commit.
