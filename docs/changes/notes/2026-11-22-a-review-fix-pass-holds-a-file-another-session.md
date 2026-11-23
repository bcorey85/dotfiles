---
type: "Change"
change_type: "fixed"
title: "A review fix pass holds a file another session first dirtied during an earlier phase"
description: "phase_start.py adds a file another session first dirtied during an earlier phase to the kept start record, so the review fix pass holds it like one dirty at the run start."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T21:31:51-06:00"}
seq: 38
kind: "fix"
components: ["script/code-phase-start", "shared/review-loop"]
evidence: ["the code-skill lane proposed it in a fix pass; a later phase could reverse an earlier ruling on a holder file unseen"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest::test_a_holder_first_dirty_at_a_later_phase_start_is_held_and_the_phases_own_file_is_not"
asked: ""
proof: []
unmeasured: "a held file changes no intake count; the held-by header already shows each hold"
---

## Change

A second phase start at the same HEAD used to keep the first record unchanged, so a file another session first dirtied during phase one was never held. `phase_start.py` now adds a file that is dirty, missing from the record and not named in any earlier phase's hand-off to the record, and keeps an `own` list of the files earlier hand-offs named (`handoff_files.entry_paths` reads them). A file with no record, or one an earlier phase handed off, is still not held.

## Evidence

`test_a_holder_first_dirty_at_a_later_phase_start_is_held_and_the_phases_own_file_is_not` failed on the old code (the record held no file) and passes now; the neighbouring test for the first record and the no-record test pass unchanged in meaning.

## Result

test_phase_start.py: 31 tests OK.

## Watch

None: no intake number reads this.

## Back-out

Revert `with_later_dirty_files` in `code/phase_start.py` and its call in `main`.

