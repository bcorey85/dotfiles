---
type: "Change"
change_type: "fixed"
title: "An ask outcome keeps the finding id of the ask row the loop logged"
description: "The review-loop stop hook pairs each ask row the loop logged with the finding id the log helper printed; review_fix.py and code_step.py fill each packet ask from those rows, or log the ask row themselves, so every ask outcome supersedes its ask row instead of landing under a new id."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T20:52:28-05:00"}
seq: 71
kind: "fix"
components: ["script/review-loop-gate", "script/handback", "script/review-fix", "script/code-step", "agent/review-loop", "shared/finding-log", "skill/review", "skill/fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_an_ask_the_loop_logged_without_writing_its_id_gets_its_outcome_under_the_logged_id"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The review-loop stop hook reads the loop's `log-review-finding kind=finding ... actioned=ask` calls, pairs the Nth
  call in a command with the Nth `finding_id=` the helper printed, and saves `{file, line, finding_id}` as `ask_rows` on
  the stop row. When the counts differ it pairs nothing. A call through a shell variable (`L=...log-review-finding;
  $L kind=finding`) counts as a call. The stop row also records whether the gate blocked the stop; a blocked stop row
  is never read.
- /code waits up to 15s for the loop's settled stop row after the hand-back, since the SubagentStop hook writes it
  after the hand-back event. Its saved ask ids are scoped to one hand-back.
- `handback.supply_ask_finding_ids` keeps a valid id already on an ask, else takes the id of the logged row at the same
  file and line (each row serves one ask), else logs the ask row itself and keeps the printed id.
- `review_fix.py packet` and `code_step.py` (after review) call it before the asks are presented and save the ids in
  their state, so a repeat logs no ask row twice.
- review-loop no longer carries `finding_id` in its ask entries; it logs each ask row at the same file and line as the
  ask's `file_line`.

## Evidence

- Three /review runs in one session: each `asks-done` logged every outcome under a new id. The loop had left the id out
  of the packet's asks, or written a placeholder, even when its log calls had printed the ids. Every ask row stayed open.
- The new tests fail on the base commit and pass after.

## Result

- Full suite and ruff pass on the worktree.

## Watch

—

## Back-out

Revert the commit.
