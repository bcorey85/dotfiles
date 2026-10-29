---
type: "Change"
change_type: "changed"
title: "Review a whole branch with review base=ref"
description: "`/review base=<ref>` passes a `base: <ref>` input to the review loop, which hands it to review-scope, so one review covers every change since that ref, commits included."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T20:27:57-05:00"}
seq: 14
kind: "behavior"
components: ["agent/review-loop", "skill/review"]
evidence: ["judgment"]
watches: []
---

## Change

- `agents/review-loop.md` Inputs: a new `base: <ref>` input. Absent means `HEAD`, the working-tree changes.
- `agents/review-loop.md` Step 0: the review-scope call takes `[base=<ref>]`, and one sentence says to add it only when the dispatch gave one.
- `skills/review/SKILL.md` step 1: pass `base: <ref>` when `$ARGUMENTS` holds `base=<ref>`.
- `skills/review/SKILL.md` ask-outcome row: `scope=branch-exit` when the review had a base, else `scope=standalone`.

## Evidence

Before the edit, the loop measured its scope only against `HEAD`. A branch whose work was already committed had no whole-branch review path, apart from a hand-built diff. The installed review-scope script already reads `base=<ref>` and takes every count against it, so no script change was needed. The `branch-exit` scope label keeps the finding rows of a whole-branch review apart from the rows of a working-tree review.

## Result

Not run since the edit.

## Watch

None. No work-log row had a whole-branch review before this edit, so there is no before reading.

## Back-out

Delete the `base: <ref>` input line, the `[base=<ref>]` argument and its sentence in Step 0, and the `base:` line in the review skill. Set the ask-outcome row back to `scope=standalone`.
