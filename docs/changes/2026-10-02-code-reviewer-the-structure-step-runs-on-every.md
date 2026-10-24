---
type: "Change"
title: "code-reviewer: the structure step runs on every review pass, not only when the structure domain is eligible"
description: "code-reviewer: the structure step runs on every review pass, not only when the structure domain is eligible."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-02T00:00:00-05:00"}
seq: 9
components: ["agent/code-reviewer"]
evidence: ["census", "seeded round"]
watches: ["structure-pass-in-code-reviewer"]
---

## Change

code-reviewer: the structure step runs on every review pass, not only when the structure domain is eligible

## Evidence

census, seeded round

## Result

At work, 72 of 160 structure escapes had no structure pass before them. On five seeded large diffs, the code reviewer's own structure step caught 39 of 45 planted structure defects. Check after the edit: structure escapes per loop in the work logs

## Watch

Read 2026-10-24 on work logs through 2026-10-22: smell, duplication and complexity escapes per code-reviewer run 0.12 after, against a median of 0.12 (range 0.04 to 0.19) before. No change. Kept: the Opus structure reviewer stopped running on every loop with no rise in structure escapes. Watch closed.

## Back-out

—
