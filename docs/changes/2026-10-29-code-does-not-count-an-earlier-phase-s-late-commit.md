---
type: "Change"
change_type: "fixed"
title: "/code does not count an earlier phase's late commit as the next coder's work"
description: "A commit of the earlier phase made after /code started the next phase no longer reaches the next coder's hand-back check or review scope; a rebase or reset off the phase's start commit stops the run and names both commits."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T22:05:49-05:00"}
seq: 297
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_phase_commit_made_after_the_next_start_is_not_the_next_coders_work"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The coder's committed files now leave out each file that was already dirty when the phase started and that HEAD
  holds unchanged from that start. A commit of the earlier phase made after the next phase started is such a file. A
  file the coder changed and then committed still counts. Both the hand-back's later-phase check and the review scope
  read this list.
- When the coder hands back and HEAD does not descend from the phase's start commit (a rebase or a reset), the run
  stops on the coder's report and names both commits. It no longer guesses which changes are the phase's.
- The peer asked for the base commit to move to the new HEAD when the earlier phase is done. A new phase already
  takes the current HEAD at its start. The bug is a commit landing after that start, while the coder works. Moving the
  base at hand-back would also drop the coder's own commits, so the fix compares content with the start instead.

## Evidence

judgment: on a work repo the main session committed the finished phase after the next phase started. The hand-back
check then blocked the coder about eight times for files it never touched, and the run passed its 30-minute cap.

## Result

The named test fails before (review scope lists the earlier phase's `totals.ts`) and passes after.
`test_a_file_dirty_at_the_start_that_the_coder_changes_and_commits_is_its_work` and
`test_a_coder_hand_back_after_a_reset_off_the_start_commit_stops_and_names_both_commits` cover the other two cases.

## Watch

None.

## Back-out

In `code_step_core.py`, have `coder_changed_files` call `committed_since` again, and remove `committed_since_baseline`.
Remove `head_blob_hashes` and `head_descends_from` from `lib/script_utils.py`, and `head_left_phase_start` from
`code_step_core.py` (it calls `head_descends_from`). Remove `stop_when_head_left_base` and
its call at the top of `review_coder_report` in `code_step.py`, the descent skip in `code_step_hooks.py`'s
`later_phase_edit_denial`, the fresh start commit after a descent stop in `code_step_start.py`, and the tests.
