---
type: "Change"
change_type: "changed"
title: "Round-one code review splits by lens on every multi-file change"
description: "Round one of the scripted review loop now sends two code reviewers over every file of a multi-file change, one for state and lifecycle and one for inputs, surfaces and contracts, in place of halving the files above 5 files and 300 lines. Known bugs fixed per pass rose from 6.25 to 14.0 of 25, with no fix made worse, for 32% more Opus cache read and 25% more wall-clock."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T12:56:57-06:00"}
seq: 2
kind: "structured"
components: ["script/review-loop-script", "agent/review-loop"]
evidence: ["catch bench", "tests"]
watches: ["review-lens-split-escapes"]
test: "tests/scripts/test_review_loop_script.py"
asked: ""
proof: ["2026-11-04-lens-split-in-round-one-code-review-fixes-2-2x-the"]
impact: {"metric": "quality", "before": 6.25, "after": 14.0, "unit": "of 25 known bugs fixed per pass", "finding": "2026-11-04-lens-split-in-round-one-code-review-fixes-2-2x-the", "better": "higher"}
unmeasured: ""
overlap: "The reviewer-reachable-sweep-escapes watch reads the same escapes metric from 2026-11-02, so its reading and this one cannot be split."
---

## Change

`first_round_plan` in `review_loop_script.py`: when the change has more than one file and the code reviewer owns more
than one, the code-reviewer slot becomes two code-reviewer dispatches over all code-owned files. Each carries a lens
(`LENS_A` state and lifecycle, `LENS_B` inputs, surfaces and contracts), and `review_request` appends it as the last
line of the prompt. `SPLIT_FILES` and `SPLIT_LINES` are gone. A one-file change and every re-review get one plain
reviewer. The review-loop agent's Step 3 (claude and opencode copies) states the same rule.

## Evidence

The proof finding: 12 sealed TLDR frontend phases, 25 keyed bugs, 8 passes per arm, blind Sonnet grading. The arms
differ only in this function and the lens line.

## Result

Known bugs fixed per pass: 6.25 (4–9) live, 14.0 (10–17) lens split; every lens pass beat every live pass. No fix made
worse in either arm. Opus cache read across reviewers and root rose 32% (233.1M → 308.1M), wall-clock per run 388 s
→ 484 s.

## Watch

`review-lens-split-escapes`: review escapes after the change, against the window before it.

Reading 2026-11-11 (work intake, data to 2026-11-10, toolkit repos left out):

- Escapes: no verdict yet. Escapes are counted through 2026-11-03, before the edit.
- Review-loop cache read per run: MOVED down, 7.31M → 2.37M (51 runs). Kept. The scripted loop moved in the same
  window, so the drop is not this edit's alone; the guard was against a rise.
- Fixed bug or correctness findings per code-reviewer run, `/code` reviews: round one 0.30 → 0.81, round two
  0.19 → 0.19.

## Back-out

Restore the size gate in `first_round_plan` (split by file above 5 files and 300 changed lines), drop `LensOwned` and
the lens append in `review_request`, and restore the Step 3 split paragraphs.
