---
type: "Change"
change_type: "added"
title: "The test reviewer opens the fixture of every test that asserts an order"
description: "The test reviewer now opens the fixture of every test that asserts an order and reports a fixture already in the expected order as a fix. On Sonnet it used to miss that gap in half its reviews of a real-size phase."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-11T00:37:30-06:00"}
seq: 1
kind: "structured"
components: ["agent/test-reviewer"]
evidence: ["rule meter", "seeded round"]
watches: []
test: ""
asked: ""
proof: ["2026-11-11-the-test-reviewer-opens-the-fixture-of-every-order"]
unmeasured: "No intake number reads it: the work logs do not tag a test-reviewer finding as a fixture finding. Measured on a TypeScript billing app, a small TypeScript case and a small Django case; the Django case shows no gain because the reviewer already reports it there. No run on any other stack or on a frontend test."
overlap: "Two open watches from 2026-11-01 read test-reviewer findings per run and test-reviewer cache-read tokens per dispatch. This edit adds about one finding per affected review and raised cache read by about 16k Sonnet tokens per review on the bench, so a rise in either reading after 2026-11-11 is credited jointly, not to the Sonnet switch alone."
---

## Change

`agents/test-reviewer.md` gains one paragraph after the step that reads assertions against the spec: "**Step 3c:
Fixtures.** Open the fixture of every test that asserts an order. When its rows already sit in the expected order, the
test passes on code that sorts nothing: report it as a `fix` and name the row to move. Write no bullet for a fixture
that can fail its test."

## Evidence

rule meter: both arms ran with the paragraph in the reviewer's file of a toolkit copy, on the Sonnet reviewer with a
plain review prompt, graded by a script and then read by hand.

seeded round: the same two arms reviewed one phase of a billing app with five seeded test gaps, reports pooled and
graded without the arm key.

## Result

Runs that reported the already-ordered fixture as a fix, 8 runs per arm, Sonnet:

| Stack and case | With the paragraph | Without |
|---|---|---|
| TypeScript billing app, payments phase, fixture created oldest first | 8/8 | 4/8 |
| TypeScript, small date-order test over a sorted array | 8/8 | 1/8 |
| Django, small date-order test over rows created in date order | 8/8 | 8/8 |

The four other seeded gaps in the billing-app phase: 32/32 with the paragraph, 30/32 without. On sound order tests no
run in either arm raised a fixture finding (0/16 each). On sound filter tests the paragraph added one true, low-value
finding in 5/16 runs against 0/16.

Sonnet tokens per review of the billing-app phase, median, without → with: fresh 11 → 12, cache write 30,542 →
47,723, cache read 95,597 → 111,722, output 2,464 → 3,390. No Opus tokens. `bash tests/run.sh` passes.

## Watch

None: see `unmeasured` and `overlap`.

## Back-out

Delete the Step 3c paragraph from `agents/test-reviewer.md` and restore the anchor row for the review process.
