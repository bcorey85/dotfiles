---
type: "Change"
change_type: "changed"
title: "The `/refactor` skill's prompt is now 1,407 words, down from 1,578, with rule rationales cut"
description: "The `/refactor` skill's prompt is now 1,407 words, down from 1,578, after seventeen sentences and clauses that explained why a rule exists were cut: the fresh-eyes and own-checklist notes, tests-are-the-contract, when to pick each modifier, the lean-context reasons in branch audit and simplify."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["skill/refactor"]
evidence: ["removal round"]
watches: []
---

## Change

The `/refactor` skill's prompt is now 1,407 words, down from 1,578, after seventeen sentences and clauses that explained why a rule exists were cut: the fresh-eyes and own-checklist notes, tests-are-the-contract, when to pick each modifier, the lean-context reasons in branch audit and simplify, the sweep's cost note and pattern labels, the audit lane's trigger and detector-judge note, and the work-list and subtraction framings. Two clauses stay: "old debt is not an escape" in the escape-log step and "Fires on pre-existing code too. Non-blocking." in the finder-log step.

## Evidence

removal round

### Anchor reasons

Anchor `skills/refactor/SKILL.md`, section `# Refactor` (evidence: removal round):

The find/fix/gate line and the two finders with their questions and bounds. Gone: "fresh eyes, out of this context" and "never compiles its own checklist".

Anchor `skills/refactor/SKILL.md`, section `## CRITICAL: Never modify a test to make a refactor pass` (evidence: removal round):

The never-touch-a-test rule, the stop-and-alert route, and the verbatim-move exception. Gone: "tests are the contract". Every coder dispatch passed the rule without it.

Anchor `skills/refactor/SKILL.md`, section `## Modifiers` (evidence: removal round):

The modifier pointer, the finder variants, and "Never `+fast` in simplify". Gone: when to use each modifier and the whole-module reason. The haiku pass-through in simplify was the same with and without the reason.

Anchor `skills/refactor/SKILL.md`, section `## Instructions` (evidence: removal round, census):

The mode router, the four mode pipelines, the coder dispatch, escape and finder logging, the test audit, and the `/review` handoff. Gone: the lean-context reasons, the sweep's cost note, the audit lane's trigger note. Kept: "old debt is not an escape" in the escape-log step and "Fires on pre-existing code too. Non-blocking." in the finder-log step. Without them, branch runs stopped to ask approval for an escape guard and never logged or reached `/review`. The handoff starts the round counter at zero. Census on work-machine logs: the earlier start value of one left the loop one full review round where its text gives two, and this skill reached the loop in at most 44 of 700 loop starts. The start value was not itself varied, and the effect is unmeasured.

Anchor `skills/refactor/SKILL.md`, section `## Code to refactor` (evidence: removal round):

The argument placeholder. Byte-identical in all arms. Not itself varied.

## Result

A Go CLI in seven shapes: a seeded simplify module, a clean twin, a feature branch with seeded smells and litter under a generic final-pass argument and under no argument, a seeded audit target, bare `simplify`, and `+fast simplify`; stand-in finder, coder, test, and loop agents returned canned reports; three Sonnet runs per wording per shape. The fully cut text matched the full text on every simplify, audit, and routing check, but on the branch runs it stopped twice in six to ask approval for an escape guard, and logged no escape, no finder row, and never reached `/review` in three of three final-pass runs (full: two of three each). With the two clauses restored, six branch runs made no guard stop, reached `/review` in five of six (full: three of six), and logged escapes, finder rows, and `/review` in two of three final-pass runs. Wrapper fresh-plus-output: cut text 0.99x full over 42 runs. Live gaps, report-only, in every wording: the finder log is never written in simplify or audit mode; simplify dispatches omit the unreachability proof and cost clause; `+fast simplify` passes haiku in two of three runs; the test audit is skipped as "mechanical" in two of three final-pass runs; the wrapper asks to confirm the coder dispatch in about a third of branch runs; two runs edited CLAUDE.md for a guard without approval.

## Watch

—

## Back-out

—
