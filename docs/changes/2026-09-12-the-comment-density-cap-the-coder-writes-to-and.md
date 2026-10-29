---
type: "Change"
change_type: "changed"
title: "The comment-density cap the coder writes to and the reviewer flags against was raised from a tenth of a"
description: "The comment-density cap the coder writes to and the reviewer flags against was raised from a tenth of a file's lines to a fifth, in the reviewer and in the write-time gate alike."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 14
kind: "behavior"
components: ["agent/code-reviewer", "script/comment-bloat-gate"]
evidence: ["judgment"]
watches: []
---

## Change

The comment-density cap the coder writes to and the reviewer flags against was raised from a tenth of a file's lines to a fifth, in the reviewer and in the write-time gate alike.

## Evidence

judgment

## Result

The tighter cap was firing on files where every remaining comment was a genuine why — an invariant, a unit, a gotcha — and the only ways under it were to delete real information or pad the file with code, both of which the rule itself forbids. A cap meetable only by breaking its own escape clause is not measuring what it claims to. The looser value still catches narration, which is the target.

## Watch

—

## Back-out

—
