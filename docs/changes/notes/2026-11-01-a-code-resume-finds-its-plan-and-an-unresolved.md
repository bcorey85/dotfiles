---
type: "Change"
change_type: "fixed"
title: "A code resume finds its plan and an unresolved task writes no stop file"
description: "A /code stop's resume line now carries the plan path, so a resume from another cwd finds its run, and a run that resolved no task leaves every stop file alone."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T22:58:22-06:00"}
seq: 456
kind: "fix"
components: ["skill/code", "script/code-relay"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::test_a_code_resume_finds_its_plan_and_an_unresolved_task_writes_no_stop_file"
asked: ""
proof: []
unmeasured: ""
---

## Change

A /code stop ends with `To go on: /code resume <plan path> <your feedback>`, with the plan's absolute path; a run with no plan file keeps the short line. On resume that path sets the repo root, so the run folder is the plan's repo, not the cwd. The skill description and the relay rule tell the main session to run the stop's `To go on:` line. Step 0's two unresolved exits end with a final reply and write no stop file.

## Evidence

A /code run on a sibling repo's plan stopped, and its resume from another cwd failed in `resolve-task-dir.sh` and overwrote that cwd repo's `stop.md`. The skill text still sent that path through a STOP that writes the file.

## Result

The stop line and the resume rule are skill text, pinned by a guidance test. `code_relay.py` run from the cwd of a different repo still finds no new stop and falls back to the Skill result, which is the right text.

## Watch

None. No intake number counts a clobbered stop file.

## Back-out

Revert the commit.
