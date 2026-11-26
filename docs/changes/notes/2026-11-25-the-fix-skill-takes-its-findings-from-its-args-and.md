---
type: "Change"
change_type: "fixed"
title: "the fix skill takes its findings from its args and stops without them"
description: "The fix skill, a fork that never sees the conversation, takes its findings from its args and stops at once with one line when it has none."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:23:48-06:00"}
seq: 6
kind: "fix"
components: ["skill/fix"]
evidence: ["tests/scripts/test_guidance_rules.py"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_no_fork_skill_description_names_the_conversation_as_an_input_source"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The fix description drops the conversation as a source and tells the caller to pass the findings in the args. Step 1 ends a run with no findings, no handoff and no `resume` at once with one line, and starts no loop.

## Evidence

The new guidance tests fail on the old skill text and pass on the new one. The full check passed on the final tree (6728 tests, 0 failed).

## Result

Rule-meter arms pending.

## Watch

—

## Back-out

Revert the commit.
