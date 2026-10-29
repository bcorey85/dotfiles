---
type: "Change"
change_type: "fixed"
title: "A ruling corrected mid-run goes to a correction coder before the review"
description: "/code takes a corrected asks-done line while its asks coder runs; a correction coder applies it before the one review, in place of a whole new run."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T18:00:56-05:00"}
seq: 283
kind: "fix"
components: ["skill/code", "script/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_ruling_corrected_while_the_asks_coder_runs_goes_to_a_correction_coder_before_the_review"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step.py correct-ruling` takes the words of `asks-done` while the asks coder runs. It saves the corrected
rulings, rewrites the ruled-asks entry and logs an outcome row for each ask whose ruling changed, and dispatches
nothing. When the asks coder reports, a correction coder gets the old and new ruling of each changed ask (and any
changed `--also` text) and undoes the work for the old one. The asks snapshot stays, so one review covers both
coders. A correction equal to the ruling is dropped. A correction coder that leaves the tree equal to the snapshot,
with no ask still accepted, finishes the phase without review; any differing line gets the review. At any other stage
the verb refuses and the run goes on. The `/code` skill's rule 5 runs a message that starts with `asks-done` through
the verb; every other message keeps the scope refusal. The ask question names how to send a correction.

## Evidence

A wrong ruling sent to a running `/code` was refused as a scope change, so the run built it, and a second run with
its own coder and review undid it.

## Result

The new correction-flow tests fail against the scripts before the change and pass after it. The full suite passes.

## Watch

None; no intake number counts mid-run corrections.

## Back-out

Revert the `correct-ruling` verb and its usage lines, the correction branch in `review_coder_report` and
`unreviewable_outcome`, `correction_coder_prompt`, the ruled-asks replace in `record_ruled_asks`, the rule 2 and 5
edits in `skills/code/SKILL.md`, the ask-question sentence, and the new tests.
