---
type: "Change"
change_type: "added"
title: "The code reviewer cuts new docs and test modules no plan step asks for"
description: "The code reviewer marks a new doc file or test module that no plan step, criterion or finding asks for as a fix to delete it, and a doc that repeats a sibling doc or the code; close-branch carries the Diff split line and treats an OVERSIZED part as a finding."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T17:04:07-06:00"}
seq: 4
kind: "structured"
components: ["agent/code-reviewer", "skill/close-branch"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-25-the-code-reviewer-s-unasked-files-rule-moves-the"]
unmeasured: "No intake metric counts the unasked docs or test modules a review cuts."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`agents/code-reviewer.md` Step 3 gains item 7, Unasked files: when the prompt names a plan or acceptance criteria, a new doc file or test module that no plan step, criterion or prior finding asks for is a `fix` to delete it, and a new doc that repeats a sibling doc or the code is a `fix` to delete it that names what it repeats. The opencode port carries the same rule under Do Flag. `skills/close-branch/SKILL.md` Step 1 keeps the `Diff split:` line for the recap and makes each `OVERSIZED:` part a Step 3 finding.

## Evidence

Rule-meter scenario UF01 (`~/agent-evals/bin/rule_meter_scenarios.json`): a late-fee plan asks for one function and one test module; the commit also adds an unasked test matrix module and a doc that restates the code step by step. Neutral level, Opus, 8 runs per arm: on 8 of 8 cut the doc, off 2 of 8 (Wilson 95% [0.68, 1.00] vs [0.07, 0.59]).

## Result

The rule moves the cut of an unasked doc from 2 of 8 to 8 of 8 at the neutral level. The supportive and competing levels were not run. The close pass's `OVERSIZED:` line gives the same check at branch end.

## Watch

—

## Back-out

Revert the commit.
