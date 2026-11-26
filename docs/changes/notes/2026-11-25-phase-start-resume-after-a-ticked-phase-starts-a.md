---
type: "Change"
change_type: "fixed"
title: "phase_start resume after a ticked phase starts a new record at HEAD"
description: "`phase_start.py --resume` after a commit that ticked a phase in a plan's Phase Status prints HEAD as the base and writes a new start record, so the next phase no longer reviews against the previous phase's start."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T15:53:32-06:00"}
seq: 3
kind: "fix"
components: ["script/phase-start", "skill/code"]
evidence: ["tests/scripts/test_phase_start.py"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest.test_resume_after_a_commit_that_ticked_a_phase_starts_a_new_record_at_head"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`phase_start.resume_base` reads the `## Phase Status` of each `.md` file changed between the kept record's head and HEAD, at both commits, through `plan_format.phase_status_entries`. A phase done at HEAD and not done at the kept head is a tick: a stderr line names the file and phase, and the resume writes a new record at HEAD and prints HEAD.

## Evidence

`test_phase_start.py` pins a tick (new HEAD base), no tick and a markdown edit that ticks nothing (kept base), a commit that adds an already-ticked plan, and a Phase 2 tick with Phase 1 already done.

## Result

Before, a `/code resume` for Phase N+1 after Phase N was committed printed Phase N's start head as the base; now it prints the Phase N commit.

## Watch

—

## Back-out

Revert `done_phase_numbers`, `ticked_since` and the tick branch of `resume_base` in `phase_start.py`, and the docstring sentence.
