---
type: "Change"
title: "The gate scripts drop duplicate checks and hand-built deny output"
description: "A refactor with no behavior change: the review-commit gate's second folder-change check folds into its first, the /code hooks share one fork-block helper, and the hand-back gate uses the shared deny printer and table-driven report text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T07:10:49-05:00"}
seq: 175
kind: "user-rule"
components: ["script/review-commit-gate", "script/code-step", "script/coder-gate"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-28: lets fan out some workers - see if there are some ways to refactor / simplify code and review scripts"
proof: []
unmeasured: ""
---

## Change

- `review_commit_gate.py`: the folder-change test reads `eval` and `source` in its one regex; the second check
  (`names_unknown_target`, `UNKNOWN_TARGET`, `UNKNOWN_COMMAND_WORDS`) is gone, since every case it caught the first
  check already caught.
- `code_step_hooks.py`: the fork's early hand-back deny and its stop block share one helper and one resume sentence.
- `coder_gate.py`: both deny sites print through `script_utils.pre_tool_use_deny`; the hand-back stamp and the clear
  text come from tables instead of near-copy blocks.

## Evidence

- A read-only survey of the gate scripts, each duplicate checked by hand against the code.

## Result

- Net 19 lines removed across the three scripts (90 added, 109 deleted); no test changed.
- Full suite after the merge with the simplify integration branch: 3679 tests in 95 files, 0 failed; ruff and the
  duplicate check clean. The review loop converged with no behavior change found.

## Watch

—

## Back-out

Revert the commit.
