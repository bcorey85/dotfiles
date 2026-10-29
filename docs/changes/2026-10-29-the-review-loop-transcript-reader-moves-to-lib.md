---
type: "Change"
change_type: "changed"
title: "The review-loop transcript reader moves to lib"
description: "LoopTranscript and the checks that read only the transcript move from review_loop_gate.py to lib/loop_transcript.py, so handback.py no longer imports the SubagentStop hook that imports it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T12:14:43-05:00"}
seq: 264
kind: "fix"
components: ["script/handback", "script/review-loop-gate", "script/open-child-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_hook_module_imports.py::HookModuleImportTest::test_no_lib_module_or_handback_imports_a_hook_module"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/loop_transcript.py` holds `LoopTranscript`, the patterns it reads a transcript with, the finding-id patterns,
`last_code_step`, `scan`, `plan_edit_reason`, `touches_plan`, `GATE_REASON` and `PLAN_EDIT_REASON`. `handback.py`,
`review_loop_gate.py` and `open_child_gate.py` import it. `full_suite_in_ci` moves to `handback.py`, since it calls
`full_check.py` and a lib module does not import a review script. `handback.py` re-exports the finding-id patterns.
`handback.py` used to import `review_loop_gate.py` inside three functions, because that hook imports `handback.py`
at its top. That cycle is gone. The gate drops from 755 to 429 lines.

This is the first part of its queue item. The second part, which moves the verification reader and the skill-done
evidence out of `code_step_boundary.py`, waits until the stop-record change lands, because that change edits the
same stop writes.

## Evidence

A move by concern. A new test reads every lib module and `handback.py` and fails when one imports a script that
`settings.json` registers as a hook.

## Result

The new test fails on the tree before the move (`handback.py imports review_loop_gate`) and passes after it. The
hook suites pass with no change in what any hook prints or blocks.

## Watch

None; no behavior change.

## Back-out

Revert `lib/loop_transcript.py`, the import and call edits in `review_loop_gate.py`, `handback.py` and
`open_child_gate.py`, the new test and the `tests/run.sh` list line.
