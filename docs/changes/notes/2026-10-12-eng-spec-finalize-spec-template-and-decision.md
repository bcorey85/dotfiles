---
type: "Change"
change_type: "changed"
title: "eng-spec finalize, spec template and decision format: the spec states each fact once"
description: "eng-spec finalize, spec template and decision format: the spec states each fact once."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-12T00:00:00-05:00"}
seq: 7
kind: "behavior"
components: ["skill/eng-spec"]
evidence: ["census", "judgment", "paired bench"]
watches: ["spec-states-each-fact-once"]
---

## Change

eng-spec finalize, spec template and decision format: the spec states each fact once. `## Decisions` holds one line per ledger decision (the choice, and the trade-off only where it changes code), not a verbatim copy of the four-field blocks. An edge case lives in the phase that handles it, and gate-only facts stay in their sibling file

## Evidence

census, judgment, paired bench

## Result

One work plan, read in full: about 45 to 50% of the spec repeated another section or file, and the decisions copy alone was about 370 byte-identical lines. Every coder dispatch reads all text above Phase 0, and a sharded plan review reads it three times. Gain: tokens on each coder and review read, and fewer places for two copies to disagree.

## Watch

plan defects per finished plan in the work logs, 14.4 now (130 since 2026-09-05 over 9 plans), and spec line counts.

## Back-out

restore the verbatim-copy bullet and the old template comment. Bench check, five build phases of one plan, index against the verbatim copy: both followed all 27 decisions with 0 violations, and reviewers asked to undo a decision 0 times. Cost 3% lower and coder cache read per dispatch 4% lower, inside run-to-run noise. Kept
