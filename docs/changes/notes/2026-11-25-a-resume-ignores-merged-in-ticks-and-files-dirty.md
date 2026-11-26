---
type: "Change"
change_type: "fixed"
title: "A resume ignores merged-in ticks and files dirty before the run"
description: "phase_start.py --resume counts only the branch's own commits as a phase tick and names a Phase Status line that does not parse; the phase-end change-file check leaves out files that were dirty before the run and are unchanged."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:35:11-06:00"}
seq: 7
kind: "fix"
components: ["script/code-step"]
evidence: ["tests/scripts/test_phase_start.py", "tests/scripts/test_phase_change_file.py"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest.test_resume_after_a_merge_that_brings_in_a_ticked_plan_keeps_the_recorded_head"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`phase_start.py --resume` compares the phase ticks at HEAD against the kept head with the merged-in branches folded in (`merge_free_base`), so a merge of master that brings in another plan's ticked phase no longer resets the kept record. When a changed file's Phase Status has a line that does not parse, the resume names the file, the line and the expected form on stderr and keeps the record. Only files whose diff gains or loses a `- [x]` line are read. `phase_change_file.py` reads the start record and drops each path recorded as dirty before the run whose bytes still match the recorded hash; a start record that does not parse exits 2; with no record it behaves as before.

## Evidence

`test_phase_start.py` pins a resume after a merge that adds a ticked plan keeping the recorded head, and a resume after a commit with an unparsed status line keeping it and naming `file:line`. `test_phase_change_file.py` pins a pre-run dirty toolkit file passing when unchanged, failing when edited since, and a bad start record exiting 2.

## Result

Before, a merge reset the record and dropped its dirty and own entries, a partial parse reset it silently, and a toolkit file that was dirty before the run failed the phase-end check. Now each keeps the run's record or passes.

## Watch

—

## Back-out

Revert the `ticked_since` and `phase_change_file.py` changes; the resume then compares against the kept head directly and the change-file check reads every dirty file.
