---
type: "Change"
change_type: "fixed"
title: "Class closure leaves members that read the value for another purpose and names them in the receipt"
description: "The review loop's class-closure check now says what each member reads the value for before it calls the member open, lists members with another purpose under a new left_alone reply field, and ends every class_closure receipt with \"; left alone, read for another purpose:\" and those members."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-10T18:49:00-06:00"}
seq: 9
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["review-class-closure-sweeps-readers-without"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_repaired_class_receipt_names_the_members_left_alone"
asked: ""
proof: []
unmeasured: "No meter run; the user ruled ship on 2026-11-10 in session agent-evals-5e."
---

## Change

- `review/review_loop_closure.py`: `CLOSURE_RULES` adds a purpose check, the reply gains a `left_alone` list, and the recovery parser for a reply that will not decode keeps that list.
- `review/review_loop_script.py`: `class_closure_pass` appends `left_alone_clause` to every receipt it writes.
- `lib/script_utils.py`: new `nonblank_strings`, the list filter the closure reply uses.

## Evidence

The closure check listed readers of a value as open when they read it for another purpose, and the repair coder then edited them.

## Result

Tests cover the closed, held, repaired and still-open receipts, a reply without `left_alone`, and a raw-quote reply that keeps it.

## Watch

None: the change is pinned by tests.

## Back-out

Revert the commit.
