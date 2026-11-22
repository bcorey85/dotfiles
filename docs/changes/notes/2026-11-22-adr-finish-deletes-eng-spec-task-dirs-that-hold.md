---
type: "Change"
change_type: "fixed"
title: "adr finish deletes eng-spec task dirs that hold architect plans and plan-review reports"
description: "adr_flow.py finish now counts the architect plans (NN-backend-plan.md, NN-frontend-plan.md) and the plan-review reports (review-round<n>-shard-<x>.md) as plan files, so a finished eng-spec task dir deletes without a manual step."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T09:26:26-06:00"}
seq: 1
kind: "fix"
components: ["script/adr-flow", "skill/adr"]
evidence: ["queue item adr-finish-refuses-to-delete-eng-spec-task-dirs: finish refused a task dir holding 04-backend-plan.md, 05-frontend-plan.md and review-round1-shard-a.md/-b.md, all written by eng-spec"]
watches: []
test: "tests/scripts/test_adr_flow.py::AdrFlowTest::test_finish_deletes_dir_with_eng_spec_shard_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

`PLAN_FILE_PATTERN` in `adr_flow.py` also matches `<digits>-backend-plan.md`, `<digits>-frontend-plan.md` and `review-round<digits>-shard-<letters>.md`. Every other name still refuses.

## Evidence

eng-spec phase 6b writes `review-round<n>-shard-<x>.md` into the task dir, and the architect plans were seen in a real task dir. `test_finish_deletes_dir_with_eng_spec_shard_files` fails without the change. `test_refuses_hand_written_names_that_only_look_like_plan_files` adds near-miss names (`backend-plan.md`, `06-api-plan.md`, `review-round-shard-a.md`, `review-round1-shard-.md`) that still refuse.

## Result

The adr_flow tests and the full suite pass.

## Watch

A task dir that holds a hand-written file under one of the new names, which finish would now delete.

## Back-out

Drop the last alternation line from `PLAN_FILE_PATTERN`.
