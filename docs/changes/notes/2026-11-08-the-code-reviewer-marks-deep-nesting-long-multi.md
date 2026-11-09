---
type: "Change"
change_type: "changed"
title: "The code reviewer marks deep nesting, long multi-job functions, chained ternaries and packed one-liners as fix"
description: "The code reviewer's list of taste breaks that are a fix, never a nit, now names the coder's readability limits: control flow nested past two levels, a non-test function past 40 lines doing more than one job, a chained ternary, and a one-liner that packs several steps."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-08T18:56:10-06:00"}
seq: 9
kind: "user-rule"
components: ["agent/code-reviewer", "agent/smell-reviewer"]
evidence: ["user rule"]
watches: []
test: ""
asked: "2026-11-08: how do i tune my coder rules so that readability and human maintainability are king / #1 priority bar none ... go hard and solve this"
proof: []
unmeasured: "The intake counts findings by class, not the nit-to-fix share within a class; the coder change's readability-findings watch reads the count."
---

## Change

`agents/code-reviewer.md`, the structure disposition paragraph: the taste breaks that are a `fix` gain four entries that match the coder's readability limits. The smell reviewer reads the same paragraph.

## Evidence

User rule. Work census, `review-findings.jsonl`, code lane, dotfiles and agent-evals excluded: 173 smell, duplication and complexity findings were left as `nit`, which the user then catches by hand or never.

## Result

Pending.

## Watch

None; see `unmeasured`.

## Back-out

Remove the four entries from the paragraph and restore its anchor row.
