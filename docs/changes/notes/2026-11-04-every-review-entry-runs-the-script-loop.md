---
type: "Change"
change_type: "fixed"
title: "Every review entry runs the script loop"
description: "/review and /fix sent a run to the review-loop agent whenever the call carried a handoff block, a base, a file path, a model modifier, an iter count or findings, and to the script loop otherwise, so the main session dispatched reviewers on some runs and an agent drove the loop on others. Every /review and /fix entry now runs `review_fix.py launch`, which takes each of those as a flag, and the review-loop agent is deleted."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T14:27:31-06:00"}
seq: 4
kind: "fix"
components: ["script/review-fix", "script/review-loop-script", "script/reviewer-dispatch", "skill/review", "skill/fix", "agent/review-loop"]
evidence: ["user report", "tests"]
watches: []
test: "tests/scripts/test_review_fix_script.py::test_launch_with_fix_writes_the_findings_and_hands_packet_the_fix_skill"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_fix.py launch` moves to `review_launch.py` and takes `--fix <findings file>`, `--no-review`, `--base`,
`--file`, `--handoff`, `--fast` / `--deep`, `--iter` and `--lane`. A findings file holds `- ` items at column 0 with
indented continuation lines; any other line stops the launch with file:line. The launch writes each flag as a prompt
header line (`findings:`, `no-review:`, `base:`, `files:`, `reviewer-model:`, `iter:`) and the packet arguments to
`launch.json`, which `reviewer_dispatch.packet_command` reads for the finish line. The loop script runs fix-first (the
fix coder applies the caller's findings before any reviewer), plans no reviewer under `no-review`, scopes the review to
a base or a file list, names the reviewer model on each dispatch line, and carries in the rounds an earlier run used.
Its scope planning moves to `review_loop_plan.py` and its prompt-file format to `review_loop_prompt_file.py`. Step 1 of
`/review` and `/fix` always launches the script. `agents/review-loop.md` is deleted in the claude and opencode trees,
with its rule-anchor rows.

## Evidence

The user saw the main session dispatch reviewers on some runs and the review-loop agent drive the loop on others. The
new tests cover each launch flag, the findings grammar, the launch.json packet arguments, the model on a dispatch
line, and the fix-first, no-review, base, file and iter paths of the loop script.

## Result

One route for every /review and /fix run. `bash tests/run.sh` passes.

## Watch

None.

## Back-out

Revert the commit: it restores `agents/review-loop.md` in both trees, the two-route Step 1 of `/review` and `/fix`, and
the launch with no flags.
