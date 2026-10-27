---
type: "Change"
title: "eng-spec plan repairs ask architects for section text, not file edits"
description: "When a design gap or a plan-review finding goes back to an architect, eng-spec now asks for the full text of each changed section and writes it into the plan files itself, because architects hold no Edit or Write tool."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T20:57:17-05:00"}
seq: 69
kind: "user-rule"
components: ["skill/eng-spec"]
evidence: ["peer report"]
watches: []
test: ""
asked: "2026-10-26: go (approving the proposed fix for plan-review repairs that go to an architect with no Edit or Write tool)"
proof: []
unmeasured: ""
---

## Change

The finalize phase's design-gap bullet now says architects cannot edit files: get each changed section's full text and write it in yourself. The plan-review phase sends BLOCKER and GAP findings to the architect for revised section text that the main session writes in, in place of "never hand-patched", which read as "have the architect edit the files". To stay under the eng-spec resident-word ceiling, the finalize phase drops one rationale clause from the fullstack weave bullet.

## Evidence

peer report: one plan-review repair asked backend-architect to revise spec.md and acceptance-criteria.md in place. All four of its Edit calls failed. It returned 48 old/new pairs that the main session applied in about 50 Edit calls. The architect run took about 397 s and 120k tokens and changed no file.

## Result

The spec-budget gate passes the edit.

## Watch

—

## Back-out

Restore the old design-gap bullet and the old step 20 sentence, and restore the weave bullet's rationale clause.
