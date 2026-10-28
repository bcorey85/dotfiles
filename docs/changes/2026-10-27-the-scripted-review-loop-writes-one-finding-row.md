---
type: "Change"
title: "The scripted review loop writes one finding row per finding, with the reviewer's class and the coder's outcome"
description: "The scripted review loop's finding rows now carry the class the reviewer tagged, a 1-based iter, the actioned value the coder's report shows, and one stable id per finding, so the watches that read review-findings.jsonl read the loop again instead of its logger."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T19:39:19-05:00"}
seq: 120
kind: "fix"
components: ["script/review-loop-script"]
evidence: ["census"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_finding_the_second_round_files_again_is_one_row"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The reviewer prompt asks for a bracket class tag on each Fix, Ask and Nit item. The finding row takes that tag, or
  `other` when there is none. The keyword guess that fell back to `bug` is gone.
- Run and finding rows carry the 1-based round number, like every other writer.
- A fix finding starts as `actioned: none`. After the coder returns, the row reads `fixed`, or `skipped_fp` when the
  coder's report skips it. It stays `none` when no coder ran, or when the coder stopped on a plan change.
- Each finding gets an id hashed from the session, lane, scope, reviewer, file and the finding's title (its text without
  the file:line and tags), plus a `#n` ordinal among same-title findings in that file. The line is left out. A finding
  the same reviewer files again in a later round, in the same file with the same disposition and the same or near
  title, updates its first row and stays off the new run row, even when the coder's edit moved its line. A different
  finding in that file files a new row. A rerun of the review writes the same id, so the ledger keeps one row for it.
  The run row's `n_findings` counts the rows it files.
- The metrics row counts each finding once: fix, ask, nit, blocker and smells tally only new findings, and smells
  uses the reviewer's class tag. `fixed` and `skipped_fp` count the final `actioned` values, plus the fixes the full
  check and the class closure make.
- A plan-change ask that opens with its file:line, as the tag rule asks, still stops the loop.
- The "Overall Assessment" line after the Nit section is no longer filed as a nit.

## Evidence

- `review-findings.jsonl`, rows from the loop's first work day: 534 finding rows, more than the run rows declared. The
  export carries no finding id, so which writer added the extra rows is not confirmed; each rerun of the loop minted new
  ids, and a finding refiled in round two was filed again. Run rows carried a 0-based iter. Bug and correctness findings
  per run jumped from the guessed class. The scripted loop defers no fix by design.
- Each part has a test in `tests/scripts/test_review_loop_script.py` that failed before and passes after:
  - class: `test_a_finding_row_takes_the_class_its_reviewer_tagged_and_other_when_untagged`
  - iter: `test_run_and_finding_rows_count_rounds_from_one`
  - actioned: `test_a_skip_in_round_one_and_a_fix_in_round_two_are_each_logged_with_their_outcome`, and the plan-change coder test now checks
    `actioned: none`
  - one row per finding: `test_a_finding_the_second_round_files_again_is_one_row` and
    `test_a_rerun_of_the_review_logs_the_same_finding_under_the_same_id`

## Result

- The finding rows count each finding once, and they carry the reviewer's class and what the coder did with each fix.

## Watch

No new watch. This change lowers `review_findings_per_review_run`, the metric these four open watches read. They read
`review-findings.jsonl` and could not be read from 2026-10-27 to the install day. Their after windows are not restarted
here; the user restarts them at the install day, and `edit-watches.json` is unchanged:

- coder-guard-make-review-findings
- stale-prose-handback-docs-findings
- stale-prose-handback-severe-findings
- test-sibling-whole-suite

## Back-out

Revert the commit.
