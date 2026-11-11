---
type: "Change"
change_type: "changed"
title: "The coder writes its scripts in the scratchpad, never in the repo tree"
description: "coder-core's script line now sends a helper script to the session scratchpad directory, never the repo tree, in place of `scratch/scripts/`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T18:28:53-06:00"}
seq: 7
kind: "structured"
components: ["skill/coder-core"]
evidence: ["rule meter"]
watches: []
test: ""
asked: ""
proof: ["2026-11-10-of-three-new-coder-and-worktree-rules-only-the"]
unmeasured: "No intake number counts scripts a coder leaves in the repo tree."
---

## Change

In `skills/coder-core/SKILL.md`, "Write a script under `scratch/scripts/` and run it." becomes "Write a script in your scratchpad directory, never in the repo tree, and run it."

## Evidence

rule meter scenario CS01: a toolkit copy with and without the new line, Sonnet coder, a task that invites a fixture-generator script, competing prompt level, 8 runs per arm. The grader flags any new script file under the repo's source roots.

## Result

| Arm | Complied of 8 |
|---|---|
| Rule on | 7 |
| Rule off | 3 |

On minus off is 50 points, above the 33-point keep line.

## Watch

None: see `unmeasured`.

## Back-out

Restore the old line in `skills/coder-core/SKILL.md`, its anchor row and its guidance test.
