---
type: "Change"
title: "code-step names its state folder once per verb, and the walk's hand-back stub carries a transcript"
description: "state_dir asked git for the code-step state folder about 14 times per verb; it now asks once per resolved folder, which cuts the termination walk's CPU time by about a sixth. The walk's review-loop hand-back stub now names an empty loop transcript, so the hand-back gates run instead of printing a KeyError."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T08:22:31-05:00"}
seq: 179
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::StateDirTest::test_one_verb_asks_git_for_the_state_folder_once"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `code_step_core.state_dir` keeps the folder git names for each resolved cwd, so one verb runs
  `git rev-parse --git-path code-step` once, not about 14 times.
- The termination walk's review-loop hand-back stub names an empty loop transcript. The hand-back hook's three
  gates read it and pass, as they do for a loop that started no background work and changed no code.

## Evidence

- test_code_step_termination.py ran past the 1200s per-file cap in the full suite.
- The main walk did not grow: 5001 nodes with the same per-node cost before and after the master merge (759s against
  758s wall, 457s against 459s CPU, three walks run at once). The merge added the 1501-node script-loop walk
  (133s wall, 122s CPU), and a loaded machine stretched the file past the cap.
- A profile showed 14 of about 20 git calls per node were `rev-parse --git-path code-step` from `state_dir`.
- With the fix, under the same three-way load: main walk 668s wall, 376s CPU; script-loop walk 112s wall, 103s CPU.
- The `KeyError: 'transcript_path'` came from the stub event, which had no transcript path. A real hook event
  carries one, so handback.py needs no change.

## Result

- The termination file costs about 17% less CPU, and every code-step verb spawns about 13 fewer git processes.

## Watch

—

## Back-out

Revert the commit.
