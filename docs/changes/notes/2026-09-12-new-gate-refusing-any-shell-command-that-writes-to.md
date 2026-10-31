---
type: "Change"
change_type: "added"
title: "New gate refusing any shell command that writes to a tracked file by redirection or appending"
description: "New gate refusing any shell command that writes to a tracked file by redirection or appending, and refusing in-place editing outright, on tracked and untracked paths alike."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-12T00:00:00-05:00"}
seq: 6
kind: "behavior"
components: ["script/shell-write-gate"]
evidence: ["judgment"]
watches: []
---

## Change

New gate refusing any shell command that writes to a tracked file by redirection or appending, and refusing in-place editing outright, on tracked and untracked paths alike.

## Evidence

judgment

## Result

Creating or rewriting a tracked file from the shell bypasses the entire write-time hook pipeline — the prose check, the vocabulary check, the citation check — so a rule enforced on every edit made through the editing tools was enforced on none of the edits that went around them. Untracked and scratch paths keep working, because the point is the pipeline, not the shell. In-place editors are unconditional: the flag itself is the bypass, and which file it happens to target is not what makes it one.

## Watch

—

## Back-out

—
