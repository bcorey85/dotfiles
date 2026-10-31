---
type: "Change"
change_type: "fixed"
title: "Hand-back no longer waits on a nested agent that ended on an API error"
description: "A review loop no longer waits on a nested reviewer that died on a usage limit, so it is not stuck behind a report that will never come; a clean packet whose latest dispatch of one reviewer kind died is denied."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-30T20:33:02-05:00"}
seq: 389
kind: "fix"
components: ["script/handback", "script/script-utils", "script/review-loop-gate", "script/open-child-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::OneCheckedHandBackTest::test_a_plan_impact_hand_back_passes_when_the_background_reviewer_ended_on_an_api_error_and_never_reported"
asked: ""
proof: []
unmeasured: ""
---

## Change

The open-dispatch count (`LoopTranscript.open_launches` and the resume check) skips a background agent whose own transcript, kept beside the loop's as `agent-<id>.jsonl`, ends on an API error record. Such an agent can die with no task notification, so the hand-back hook, the stop gate, the open-child gate and the metrics gate (`review_loop_gate.py`, via `open_kinds`) no longer wait on it. `script_utils.ends_on_api_error` reads the last record of any transcript. A launch whose agent is still running (last record is not an API error) keeps blocking, pinned by `test_a_hand_back_is_denied_while_the_background_reviewer_is_still_running`. A clean packet is denied when the latest dispatch of any reviewer kind died (`LoopTranscript.dead_reviewers`): the rule is per kind, so one dead kind denies even when another kind reported last, and a `-deep` dispatch supersedes the base dispatch of its kind. The deny is with `DEAD_REVIEWER_REASON` in `handback_hook.py`: the loop holds no finished review from its latest run, so it dispatches the reviewer again. Each dead dispatch denies once. A repeat hand-back on the same dead dispatch passes and is stored with `no_reviewer` set, so a loop whose every reviewer dies on a limit still hands back, as not reviewed: `false_clean_reason` refuses the clean credit, and `/review` and `/fix` route it to `stop-no-reviewer`, which stops after two in a row.

Known gaps. A hand-back between an API error and a retry reads a live agent as dead; that window is accepted. A foreground reviewer that dies is not seen, because only a background launch is read for death; this predates the change. A last record over 64 KB reads as alive; real ones are about 1.8 KB.

## Evidence

The new hand-back test fails with the check disabled and passes with it. 36 subagent transcripts under `~/.claude/projects` hold an `isApiErrorMessage: true` record, 16 of them as the last record, among them nested `a3869aec8fab7eb1e`; the other 20 went on after the error. 13 of those 16 dead agents have a task notification in a parent transcript; 3 have none. The tests use a redacted copy of a real last record (`tests/scripts/fixtures/subagent_api_error_last_record.json`). Resume tests pin both sides: a resumed agent that ended on an API error does not block, one that wrote a later record does.

## Result

Targeted tests pass: `test_handback.OneCheckedHandBackTest` and `test_script_utils.EndsOnApiErrorTest`.

## Watch

None.

## Back-out

Revert the `agent_died` calls in `loop_transcript.py`, remove `dead_reviewers` there, and remove its `DEAD_REVIEWER_REASON` deny and `reviewer_dead` flag in `handback_hook.py`.
