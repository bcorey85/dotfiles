---
type: "Change"
change_type: "fixed"
title: "Stage skips added-line tripwires on prose files"
description: "Stage no longer tags a markdown or text file as a suppression or bypass when its prose only names one, so the tag keeps meaning a real suppression in code."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:49:30-06:00"}
seq: 22
kind: "fix"
components: ["skill/stage"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_stage_run.py::StageRunTest::test_prose_naming_a_suppression_raises_no_tripwire_and_code_still_does"
asked: ""
proof: []
unmeasured: ""
---

## Change

`stage.mjs` ran its added-line tripwires (test skip or only, lint suppression, type suppression, hook bypass) on every file type. A plan file whose text named `@ts-ignore` was tagged "type suppression added" and sent to the human queue. The tripwires now skip files ending in `.md`, `.mdx`, `.txt`, `.rst` or `.adoc`. Code files trip as before, comments included.

## Evidence

The queue item reported one plan markdown file tagged "type suppression added" with no code suppression in the diff. A false tag on a prose file teaches the reader to skip the tag.

## Result

The new test fails on the old script (the markdown file carried both suppression tags) and passes on the new one; a `.ts` file with `// @ts-ignore` still trips. 18 of 18 tests in the file pass.

## Watch

None: the intake has no count of stage tripwires by file type.

## Back-out

Delete `PROSE_RE` and the `!isProse` guard in `stage.mjs`, and the new test.
