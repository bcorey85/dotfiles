---
type: "Change"
change_type: "changed"
title: "The review loop now runs one correctness round and defers what is left to branch exit"
description: "The review loop stops re-reviewing settled code after one correctness round and defers the residue to branch exit; a `blocker` is the only exemption."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-08-07T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
---

## Change

The review loop now runs one correctness round and defers what is left to branch exit.

## Evidence

judgment

## Result

Later iterations re-review settled code; a `blocker` is the only exemption

## Watch

—

## Back-out

—
