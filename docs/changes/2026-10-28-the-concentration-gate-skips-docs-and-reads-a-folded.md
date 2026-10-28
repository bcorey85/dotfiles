---
type: "Change"
title: "The concentration gate skips docs and reads a folded gate item"
description: "The refactor phase's concentration gate no longer counts files under a docs/ folder, and skill-done writes the simplify record under a Manual Verification item that names the gate instead of asking for the exact criterion line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T10:00:00-05:00"}
seq: 145
kind: "fix"
components: ["script/code-step", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_the_gate_leaves_plan_and_doc_folders_out_of_the_counts"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The concentration gate leaves out every file under a `docs/` folder when it counts added lines per module, so a
  slice's own plan folder no longer triggers `/refactor simplify`.
- When a refactor phase's Success Criteria hold no open gate item, `skill-done pass --simplify` looks for an open
  Manual Verification item of the phase that names the concentration gate. It writes the simplify Done lines under
  that item and leaves its box open. Only a phase with neither stops for the exact criterion line.
- `closing-phases.md` names the docs exclusion.

## Evidence

- A deletion-only branch triggered simplify on its own `docs/plans/<ticket>/` folder, about 700 added lines of
  planning docs. The complexity-reviewer found nothing.
- `skill-done pass --simplify` then refused, because the spec folded the gate into a Manual-verified line. In
  `~/dev`, 9 of 41 plan lines that name the gate sit in a Manual Verification section.
- The new tests fail on the old scripts.

## Result

- No simplify run on plan docs, and no hand edit of the plan to close a refactor phase.

## Watch

—

## Back-out

Revert the commit.
