---
type: "Change"
change_type: "fixed"
title: "announced step passes a progress line after a background launch in the same turn"
description: "A subjectless progress line passes the announced-step stop check when the current turn launched background work; a crash in one stop check keeps the other checks' reasons."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T05:24:46-06:00"}
seq: 2
kind: "fix"
components: ["script/announced-step", "script/staged-claim-gate", "script/wait-loop-gate", "script/inline-interpreter-hint", "script/user-prompts", "script/tool-call-flags"]
evidence: ["incident"]
watches: []
test: "tests/scripts/test_announced_step.py::AnnouncedStepTest::test_incident_progress_line_after_a_background_launch_passes"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

The announcement pattern splits into first-person forms and subjectless progress forms. A progress-only sentence passes when the transcript's current turn holds a background Bash call (`run_in_background`) or an Agent call not set to the foreground. The `I am …` form widened from four verbs (`going to|about to|starting|working`) to the full `I'm` list, so "I am checking…", "I am on it" and "I am writing…" now block. Each stop check in the staged-claim gate runs under its own guard, so a crash in one prints a line on stderr and the other reasons still go out. wait_loop_gate.py and inline_interpreter_hint.py now read the background flag through `tool_call_flags.runs_in_background`, so both read a string `"true"` `run_in_background` as a background run: wait_loop_gate now denies such a call from a background agent, and inline_interpreter_hint no longer denies it.

## Evidence

A turn that launched a background agent ended on "a new agent is working on it" and was sent back although work was running.

## Result

That sentence passes after a background launch in the same turn. First-person steps, a launch in an earlier turn and a turn with no transcript still block. Of 44 past blocks, 43 still block; the one that passes is the incident sentence.

## Watch

A progress line that passes while no background work runs.

## Back-out

Restore the single announcement pattern and the unguarded stop checks.
