---
type: "Change"
change_type: "changed"
title: "The coder logs or returns every caught error, also when the task asks for a fallback"
description: "The coder's swallowed-error line now says to bind the error in every catch block and use it, and names a catch that only returns a fallback as a swallowed error."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-10T13:33:59-06:00"}
seq: 3
kind: "structured"
components: ["skill/coder-core"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-10-rewording-the-swallowed-error-rule-to-bind-and-use"]
unmeasured: "No intake number reads this behavior: work escape descriptions are hashed, so no class count maps to the rule. The new wording has no run without the rule in its own batch; the count without it comes from the earlier batch on the same task. No run put a catch in a Vue component's script block."
overlap: "Replaces the line shipped the same day in 2026-11-10-the-coder-validates-handler-input-keeps-caught; that change has no watch."
---

## Change

In the readability list of `skills/coder-core/SKILL.md`, the line "Never write a catch block that drops the error:
rethrow it, return it as a typed failure, or log it with the input that caused it." becomes "Bind the error in every
catch block and use it: log it with the input that caused it, rethrow it, or return it as a typed failure; a catch
that only returns a fallback is a swallowed error."

## Evidence

rule meter: each wording in the coder skill file of a toolkit copy, Sonnet coder, plain task prompt, 8 runs per
cell, graded by a script that reads every catch block in the final code. The task on each stack asks for a fallback
value when a load fails.

## Result

Runs that complied out of 8:

| Wording | React | Vue | TypeScript backend | Django |
|---|---|---|---|---|
| No rule | 0 | 0 | 0 | 0 |
| Old line | 2 | 5 | 8 | 8 |
| New line | 8 | 8 | 8 | 8 |

Every miss of the old line returned the fallback from a catch with no error bound.

## Watch

None: see `unmeasured`.

## Back-out

Restore the old line in `skills/coder-core/SKILL.md` and its anchor row.
