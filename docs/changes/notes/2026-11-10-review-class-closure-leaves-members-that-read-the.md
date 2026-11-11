---
type: "Change"
change_type: "fixed"
title: "Class closure leaves members that read the value for another purpose and names them in the hand-back"
description: "The review loop's class-closure check now says what each member reads the value for before it calls the member open, lists members with another purpose under a new left_alone reply field, and carries those members in a left_alone packet field that the hand-back renders, even when the receipt is missing."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-10T18:49:00-06:00"}
seq: 9
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["review-class-closure-sweeps-readers-without"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_repaired_class_packet_carries_the_members_left_alone"
asked: ""
proof: []
unmeasured: "No meter run; the user ruled ship on 2026-11-10 in session agent-evals-5e."
---

## Change

- `review/review_loop_closure.py`: `CLOSURE_RULES` adds a purpose check, the reply gains a `left_alone` list, and the recovery parser for a reply that will not decode keeps that list.
- `review/review_loop_closure.py`: new `ClosureState` holds the receipt, the open classes and the left-alone list.
- `review/review_loop_script.py`: `class_closure_pass` stores the list in `ClosureState.left_alone`, which the outcome builder writes to the `left_alone` packet field, so a missing receipt keeps it. `LoopRun` holds one `closure` field in place of the receipt and open-classes fields.
- `review/review_loop_packet.py`: the packet message writes `left_alone`, and the empty outcome carries it.
- `review/handback.py`: `left_alone` is a packet key, a list key and a string-list key, and the hand-back renders it.
- `lib/script_utils.py`: new `nonblank_strings`, the list filter the closure reply uses.

## Evidence

The closure check listed readers of a value as open when they read it for another purpose, and the repair coder then edited them.

## Result

Tests cover the closed, held, repaired and still-open packets, a reply without `left_alone`, and a raw-quote reply that keeps it.

## Watch

None: the change is pinned by tests.

## Back-out

Revert the commit.
