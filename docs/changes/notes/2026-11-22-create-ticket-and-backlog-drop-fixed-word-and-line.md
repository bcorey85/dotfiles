---
type: "Change"
change_type: "changed"
title: "Create-ticket and backlog drop fixed word and line counts"
description: "Create-ticket and backlog keep their reader-facing size bar (one screen, capture not spec) and drop the fixed counts: 150 words, 1-3 bullets, 30-80 lines."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:50:53-06:00"}
seq: 11
kind: "user-rule"
components: ["skill/create-ticket", "skill/backlog"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "Rule-meter runs pending: until both arms run, this edit stays uncommitted. No intake number reads ticket length."
---

## Change

- `create-ticket`: "Hard cap: the description fits on one screen (~150 words / ~15 lines)." → "The description fits on one
  screen."; "Why = 1–3 bullets max." → "Why = the motivation in a bullet or two."
- `backlog`: "Keep it 30-80 lines" → "Keep it short".

## Evidence

prompt audit against Opus 5.5: fixed counts were tuned for wordier models and squeeze hard cases; the plain bar already
says what the reader needs.

## Result

Pending rule-meter runs.

## Watch

None: see `unmeasured`.

## Back-out

Restore the counts.
