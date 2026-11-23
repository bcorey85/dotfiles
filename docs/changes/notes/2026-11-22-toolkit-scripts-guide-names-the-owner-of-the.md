---
type: "Change"
change_type: "added"
title: "Toolkit scripts guide names the owner of the review scope guard"
description: "The owners list in the toolkit scripts guide now points to the module that owns which files a review fix pass must leave alone, so a later edit reuses it in place of writing a second guard."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T23:35:39-06:00"}
seq: 44
kind: "user-rule"
components: ["rule/scripts-claude-md", "script/review-loop"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-22: the user set that a session writes an owner line in the toolkit scripts guide on its own, with a change file"
proof: []
unmeasured: "An owner line is a pointer to a module, and the rule that governs it exempts it from a meter run. No intake number reads it."
---

## Change

`claude/.claude/scripts/CLAUDE.md`, the review loop parts line under Owners: one clause added. Files outside the
review's scope that a fix pass changed and the loop puts back are owned by `review/review_loop_scope_guard.py`.

## Evidence

- judgment: the module landed the same day with no owner line, and the branch's review asked for one.

## Result

One clause added. The rule-anchor check and the change builder pass.

## Watch

None: see `unmeasured`.

## Back-out

Delete the clause.
