---
type: "Change"
change_type: "removed"
title: "The global rules drop the never-unstage and full-suite-at-end lines"
description: "The global CLAUDE.md loses two rules the agent already followed without them (never-unstage) or that changed nothing (full suite once, at the end of review), so every session loads about 60 fewer words."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T12:06:58-06:00"}
seq: 17
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["rule meter", "user rule"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: ""
---

## Change

Removed from `claude/.claude/CLAUDE.md`: the Safety Rails paragraph that called the git index the user's and said
never to unstage files, and the Quality Checks line "The full suite runs once, at the end of review."

The review loop's own instructions and the code-reviewer's "never run the full suite" line still carry the suite
timing, and `pull_keep_index.py` keeps staged files staged on a push.

## Evidence

Rule-meter runs, rule on and off.

## Result

- Never-unstage: ALREADY. The agent kept staged files staged in 8 of 8 runs with the rule and 8 of 8 without it.
- Full suite once, at the end: NO-EFFECT. 0 of 8 runs with the rule and 0 of 8 without it showed the behavior the
  rule targets.

## Watch

None. No intake number reads either behavior.

## Back-out

Revert the commit; both lines come back.
