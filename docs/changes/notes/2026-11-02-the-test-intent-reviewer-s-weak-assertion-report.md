---
type: "Change"
change_type: "fixed"
title: "The test-intent reviewer's weak-assertion report no longer asks for a shape from a list it never gives"
description: "Each weak-assertion finding names the wrong value its assertion accepts, in place of a shape from a list the agent no longer carries."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T16:27:38-06:00"}
seq: 10
kind: "fix"
components: ["agent/test-intent-reviewer"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_test_intent_reviewer_names_no_shape_list_it_never_gives"
asked: ""
proof: []
unmeasured: ""
---

## Change

The WEAK report line asked for "its shape (one of the six, or `absent`)", and Step 5 called the first pass "the shape pass". The six shapes were cut from Step 5 earlier, so the reviewer had no list to pick from. Each WEAK finding now names the assertion (or `absent`) and the wrong value it accepts, and the absence pass no longer refers to a shape pass.

## Evidence

A /code test-audit phase on 2026-11-01 found the dangling reference. The test fails on the old text, which holds "one of the six".

## Result

No list reference is left in the agent. The weak-assertion definition and the absence pass with its count are unchanged.

## Watch

None: wording fix with no intake number.

## Back-out

Revert the two lines in agents/test-intent-reviewer.md and the test.
