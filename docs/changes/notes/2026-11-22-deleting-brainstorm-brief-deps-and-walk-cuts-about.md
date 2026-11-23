---
type: "Change"
change_type: "removed"
title: "Deleting brainstorm, brief, deps and walk cuts about 215 description words from every session"
description: "The brainstorm, brief and deps skills are deleted and walk folds into orient, so the skill list every session loads is four entries and about 215 description words shorter."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T23:05:59-06:00"}
seq: 41
kind: "user-rule"
components: ["skill/brainstorm", "skill/brief", "skill/deps", "skill/walk", "skill/orient", "agent/coder", "skill/code"]
evidence: ["census"]
watches: []
test: ""
asked: "2026-11-22: deletion and simplification is a priority equal to additions; cut what does not earn its cost"
proof: []
unmeasured: "No intake metric counts calls to one skill, so no edit watch exists; the work skill-usage census is the evidence and a later census of orient calls reads the fold."
---

## Change

Deleted the brainstorm, brief, deps and walk skill folders. Orient gains a `## Walk` section (`/orient walk [focus]`,
`here`, `replay`) holding the walk steps, and its description now names the walk triggers. Callers fixed: the coder
agent's description drops /deps; the code skill drops its line pointing at the brief shape; settings.json drops the
brainstorm and brief overrides; `_shared/nvim-jump.md` names `/orient walk`.

## Evidence

Work skill-usage census (toolkit rows filtered), all time / last 30 days: brainstorm 2/0, brief 1/0, deps 2/0, walk 4/1.

## Result

About 215 description words leave the always-loaded skill list. Unmeasured beyond the census.

## Watch

None: no intake metric counts one skill's calls.

## Back-out

Restore the four folders and the edited lines from git history.

