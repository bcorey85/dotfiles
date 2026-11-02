---
type: "Change"
change_type: "fixed"
title: "Review packet's class-closure receipt names the members the class repair fixed"
description: "When the class-fix coder changes a file, the packet's class_closure names the members it fixed, so no finding shows as both fixed and open."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T12:09:03-06:00"}
seq: 7
kind: "fix"
components: ["script/review-loop", "agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_class_closure_with_open_members_sends_one_more_coder_and_ends_converged"
asked: ""
proof: []
unmeasured: "One /review run showed it; no intake row reads the class_closure text against fixed[]."
---

## Change

`review_loop_script.py` `class_closure_pass` replaces the closure check's receipt with `review_loop_closure.receipt_after_class_repair(members)` when the `coder-class` pass changed a file. The new receipt names each member the check found open and says the class repair fixed it. With no change the receipt stays as the check wrote it and the members stay in `open_classes`. No second model call.

## Evidence

A /review packet's class-closure line called one test-gap member open (no test). The same packet listed it under fixed, and the `coder-class` call after the closure check had added the test. The caller relayed "one branch still untested" and the orchestrator ordered a redundant /code run.

## Result

The closure test now asserts the receipt drops "still open" and names the fixed member. It fails against the previous script, whose packet kept the receipt "one member still open".

## Watch

None: no intake number reads the closure receipt.

## Back-out

Remove `receipt_after_class_repair` and its branch in `class_closure_pass`, and the three added assertions.
