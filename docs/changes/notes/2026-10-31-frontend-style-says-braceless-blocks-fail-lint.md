---
type: "Change"
change_type: "fixed"
title: "frontend-style says braceless blocks fail lint only where eslint enables curly"
description: "Architects stop citing braceless blocks as a hard CI break in repos where lint allows them: the rule keeps braces as the style and sends the reader to the repo's eslint config before calling one a lint error."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T20:16:40-05:00"}
seq: 408
kind: "fix"
components: ["rule/frontend-style"]
evidence: ["planner correction"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_frontend_style_calls_a_braceless_block_a_lint_error_only_where_eslint_enables_curly"
asked: ""
proof: []
unmeasured: ""
---

## Change

The braces line in `rules/frontend-style.md` keeps "always use curly braces" as the style. It drops the CRITICAL tag and the claim that a braceless block always fails lint and breaks CI. It now says a braceless block fails lint only where the repo's eslint config enables `curly`, and tells the reader to read that config before calling one a lint error or a CI break.

## Evidence

In a repo whose eslint config does not enable `curly`, an architect cited the rule as a hard CI constraint. The planner had to correct it during spec finalization.

## Result

The new test reads the braces line of the rule. It fails on the old line, which says "will break CI" and names no `curly` condition, and passes on the new one. It pins the wording only: no script acts on the rule, so whether architects stop citing the false constraint shows only in later plans.

## Watch

None: no intake number counts a false lint constraint in a plan.

## Back-out

Revert the commit.
