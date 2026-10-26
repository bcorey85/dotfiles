---
type: "Change"
title: "Review-flow scripts: every function under complexity 10, dead CLI surface cut"
description: "review_fix, handback, review_loop_gate and review_commit_gate hold no function over C901 10 and tests/run.sh fails on one; the hand-back latest verb, kind inference, the --check dry run, the Task tool name and the unused packet keys are gone."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T20:42:06-05:00"}
seq: 18
kind: "fix"
components: ["script/review-fix", "script/handback", "script/review-loop-gate", "script/review-commit-gate", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_internal_error_asks_on_pre_but_stays_silent_on_post"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `tests/run.sh` runs `ruff --select C901` over the four review-flow scripts beside the code-step files, and fails on
  any hit.
- `handback.py`: the hook needs its kind (`dispatch` or `handback`); the `latest` verb and the tool-name guess are gone.
  The packet drops the `perf`, `smell` and `principle` keys; an item keeps `smell`. `validate` splits into header, ask,
  item and status steps, driven by the `ENTRY_TEXT_KEYS` and `STATUS_REQUIRES` tables. A list entry that is
  neither text nor a mapping is still a problem.
- `review_fix.py`: `active_code_step` reads state through `code_step_core.load_state` and the new
  `code_step_core.REVIEW_HANDBACK_STAGES`. Stop statuses and packet commands route through tables. Ask-outcome
  logging splits into skip, read and log steps.
- `review_loop_gate.py`: one `LoopTranscript` pass reads the transcript for both the dispatch check and the stop
  check. One `NOTIFICATION` regex replaces three; an `<agent-message>` also marks its agent as reported. Only the
  `Agent` tool counts. The `--check` dry run and the `script_utils` ImportError fallback are gone.
- `review_commit_gate.py`: `run` splits into event read, state-dir open, pre and post handlers. A state dir it cannot
  create reports one line, `review-commit-gate: cannot create <dir>: <strerror>`.
- The opencode `review-loop.md` still lists `perf:`; opencode runs no hand-back hooks, so it stays as it was.

## Evidence

A complexity review of the four scripts gave a cut list. Every cut was made but `misses.json`, which the list held.
Non-blank code lines: 1905 to 1891. The cuts removed about 118 lines; the splits that bring each function under
C901 10 added about 99; the review fixes added 5, to keep refusing a list entry that is neither text nor a mapping.
The code review replayed the old and new code over real inputs: commit-gate pathspecs over 7,893 real git commands
(0 differences), the loop scan over 116 real review-loop transcripts (116 identical), hand-back load and render over
200 real hand-backs (identical).

## Result

The named test fails on the base script, which printed a different mkdir message. ruff and the C901 check pass.
`test_code_step.py::test_the_first_wait_time_of_a_resumed_coder_is_saved_once` failed once under load. It uses
`wait_env(1, "0.2")`, the same timing cause that `2026-10-25-code-step-wait-tests-set-their-own-cap-so-suite`
fixed; the base predates that fix, and the merge of master brings it in.

## Watch

None. No intake number reads these scripts' internals; their outputs keep their shape.

## Back-out

Revert the commit.
