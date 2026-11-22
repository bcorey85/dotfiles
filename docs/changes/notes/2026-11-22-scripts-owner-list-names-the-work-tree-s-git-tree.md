---
type: "Change"
change_type: "changed"
title: "Scripts owner list names the work tree's git tree object writer"
description: "The tree identity owner line now names the helper that returns the work tree's git tree object id and says it is not a fingerprint, so a coder under scripts/ imports it and does not take it for a second tree hash."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T12:55:20-06:00"}
seq: 20
kind: "user-rule"
components: ["rule/scripts-claude-md"]
evidence: ["user request", "judgment"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "No rule-meter run: no fixture shows a coder writing a second tree id helper or removing this one. No intake number reads it either."
---

## Change

One sentence added to the tree identity line under `## Owners` in `claude/.claude/scripts/CLAUDE.md`: the git tree
object id of the work tree comes from `lib/worktree_snapshot.py` `work_tree_tree`, and it is not a fingerprint.

## Evidence

User request, on a judgment: the line said "never hash a tree another way" and named only the fingerprint, while
`work_tree_tree` is a second, allowed read of the work tree that the close-branch fix diff uses. A reader of the
line had no way to tell the helper from a forbidden copy.

## Result

Not measured. One more sentence is paid on every run under `scripts/`.

## Watch

None.

## Back-out

Delete the sentence.

