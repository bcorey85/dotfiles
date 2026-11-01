---
type: "Change"
change_type: "removed"
title: "Global CLAUDE.md drops four rules the model follows unprompted or a gate enforces"
description: "Every session loads about 150 fewer words: the domain-naming, code-paragraph and no-blockquote rules go because the model kept them with the text removed, and the coder test-scope sentence goes because the coder Bash hook enforces it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T01:23:32-05:00"}
seq: 420
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["removal round", "gate ranking"]
watches: []
test: ""
asked: "2026-11-01: after the overnight cut-candidate report: fix everything"
proof: []
unmeasured: ""
---

## Change

- `CLAUDE.md` Safety Rails: the no-blockquote paragraph is removed.
- `CLAUDE.md` Quality Checks: "Coders run only the tests for the files they changed." is removed; the full-suite sentence stays.
- `CLAUDE.md` Engineering Judgment: the name-for-the-domain bullet is removed, and the blank-line-between-steps sentence leaves the layout bullet. The lookup-beside-guard, return-early and no-nested-call sentences stay.

## Evidence

Removal rounds under a prompt that pushed against each rule: domain naming 8/8 kept with and without, code paragraphs 8/8 vs 7/8, no blockquote 8/8 vs 8/8 (Opus). The no-nested-call sentence showed a gap (13/16 vs 6/16) and stays. The test-scope text lost to the prompt in both arms (0/8 each); `coder_gate.py bash-hook` denies a coder's whole-suite run, so the gate, not the text, holds it.

## Result

About 150 always-loaded words fewer on every call, both machines. The user signed off on the cut after the report.

## Watch

None: no intake number reads naming, blank lines or blockquotes in output.

## Back-out

Revert the commit.
