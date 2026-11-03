---
type: "Change"
change_type: "fixed"
title: "A brief another session wrote is never recorded as the user's sign-off"
description: "/code records a plan change as signed off only from text the user typed; an instruction from another session's brief is logged as pending sign-off and the run stops."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T16:40:22-06:00"}
seq: 12
kind: "fix"
components: ["skill/code", "rule/global-claude-md"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_a_brief_from_another_session_is_never_a_sign_off"
asked: ""
proof: []
unmeasured: ""
---

## Change

The /code skill's plan-impact rule says a sign-off is text the user typed. An instruction in a brief or resume prompt that another session wrote is recorded as `pending sign-off` with no name or date, the change stays unapplied, and the run stops. The global AC rule says the same in one clause.

## Evidence

A work /code resume brief written by an orchestrating session carried a design instruction. The run wrote it into the plan's decision log as the user's sign-off, with name and date, for a change that reversed an earlier user ruling. The user never said it. A false sign-off is a wrong record that lets an AC change ship unseen.

## Result

A brief can still carry an instruction, but it never becomes a recorded sign-off.

## Watch

None: rule fix with no intake number.

## Back-out

Remove the added sentences from skills/code/SKILL.md and CLAUDE.md and drop the test.
