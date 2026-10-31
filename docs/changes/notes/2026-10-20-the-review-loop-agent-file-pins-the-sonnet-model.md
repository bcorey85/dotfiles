---
type: "Change"
change_type: "changed"
title: "The review-loop agent file pins the sonnet model"
description: "`agents/review-loop.md` frontmatter now holds `model: sonnet`, so a dispatch that names no model runs the loop on Sonnet and does not take the model of the session that dispatched it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T20:27:57-05:00"}
seq: 13
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
---

## Change

`agents/review-loop.md` frontmatter: one added line, `model: sonnet`. The preamble anchor no longer says "no model line, since the callers pass sonnet".

## Evidence

The three callers already pass the model on each dispatch: `skills/review/SKILL.md` step 1 and `skills/fix/SKILL.md` step 1 pass `model: "sonnet"`, and `scripts/code-step.py` builds its review dispatch with `model="sonnet"`. An agent file with no model line runs on the model of the session that dispatches it. So a new caller, or a caller that drops the parameter, runs the loop on Opus from the main session. The pin makes Sonnet the default in one place. The Agent tool's `model` parameter takes precedence over the frontmatter, so `+fast` still runs the reviewers on Haiku.

## Result

No change for the three current callers, because each one already sends `sonnet`. Not run since the edit.

## Watch

None. The callers send the same model as before, so no work-log number is expected to move.

## Back-out

Delete the `model: sonnet` line from the frontmatter of `agents/review-loop.md`.
