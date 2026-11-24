---
type: "Change"
change_type: "fixed"
title: "Review loop lints the files each fix pass changed before the next review round"
description: "The review loop now runs the repo lint on the files a fix pass changed and sends any failure to its lint repair in the same pass, so a long line or other lint failure a fix wrote no longer waits a round for a reviewer to find it."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-23T01:01:11-06:00"}
seq: 1
kind: "fix"
components: ["script/review-loop"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_review_loop_script.py::FixRoundWiringTest::test_a_review_round_fix_pass_lints_the_files_it_changed_before_the_next_round"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review/full_check_gate.py`: `FullCheckSteps.repair_lint_problems` holds the lint repair. The exit check's
`lint_pass` and the new `lint_fixed_files` both call it. `review/review_loop_script.py`: `fix_round` and `fix_first`
call `lint_fixed_files` after the fix pass, on the files that pass changed. A failure goes to the lint repair coder
before the next review round. A clean pass starts no repair. A repair after a fix pass that changes nothing
records no skipped finding; the exit check's lint repair and the full-check repair record theirs as before. A
failure the repair leaves is caught by the exit check of a converged run; a run that stops lints nothing more.

The repair's diff is read with the other late repairs, once, at the end of a converged run
(`review/review_loop_final_read.py`), the lint repair after a fix pass mid-loop included.

## Evidence

- census: on one toolkit branch, six of the 19 findings open when its review stopped were lint failures on lines a
  fix pass had written one round earlier. The loop ran lint only at its exit.

## Result

The named test fails without the `lint_fixed_files` call in `fix_round` and passes with it.
`test_full_check_gate.py::LintRepairTest` covers a 130-character line in a Python file. The full suite passes.

## Watch

None. No intake number reads lint findings by the round that wrote the line.

## Back-out

Delete the two `lint_fixed_files` calls. The loop lints at its exit only, as before.
