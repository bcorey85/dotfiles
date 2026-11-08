---
type: "Change"
change_type: "fixed"
title: "The close-pass recap lists criteria changes from the sign-off lines"
description: "The /close-branch recap gains a Criteria changes section built from an rg of the decisions ledger and the spec for sign-off lines, so the recap and the hand-back can no longer say no criterion was narrowed while a sign-off narrowing one sits in the ledger."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-07T22:05:18-06:00"}
seq: 12
kind: "fix"
components: ["skill/close-branch"]
evidence: ["defect report", "tests"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_close_pass_recap_lists_criteria_changes_from_the_sign_off_lines"
asked: ""
proof: []
unmeasured: ""
---

## Change

`/close-branch` Step 6 runs `rg -n -i 'sign-?off' <plan folder>/03-decisions.md <spec>` beside its other recap
commands. The recap template gains `### Criteria changes`, built from that output only: each sign-off line with the
criterion, the change, who signed and when. A sign-off another session wrote is listed as not the user's, with the
criterion standing. `none` needs an empty rg. Any report on whether a criterion was cut or narrowed repeats the
section.

## Evidence

A peer session reported a close pass whose recap and hand-back both said no AC was cut or narrowed while
`03-decisions.md` held a signed AC narrowing. The recap template had no section that read the ledger, so the claim
came from nothing. The new guidance test fails before the edit and passes after it.

## Result

Guidance tests pass.

## Watch

None: the defect is a false sentence in a recap, which no intake row records.

## Back-out

Remove the rg line, the Criteria changes row and its paragraph from `skills/close-branch/SKILL.md`, and the test.
