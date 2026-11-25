---
type: "Change"
change_type: "added"
title: "refactor simplify: report branch diff growth, add --diff bound"
description: "simplify-prep records the branch diff before the pass and log --mode simplify ends in a STOP naming the files that grew; --diff BASE bounds the complexity-reviewer to the lines the branch added."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T16:16:37-06:00"}
seq: 3
kind: "user-rule"
components: ["skill/refactor", "script/refactor-flow"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-25: have refactor simplify report whether the branch diff grew and accept a --diff bound"
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`simplify-prep` saves the branch diff (work tree plus untracked files against the merge base) as a sidecar beside the log input. `log --mode simplify` measures it again and prints both. When added lines rose it ends in a `STOP:` naming the files that grew; with a handoff, the STOP also carries the `/review` step. `simplify-prep --diff BASE` lists each file of the target that has an added line, with those lines, and bounds the complexity-reviewer to them; it stops when no file of the target has one. The simplify code moved to `simplify_flow.py` and shared helpers to `flow_common.py`.

## Evidence

Judgment: the user's ask.

## Result

New simplify tests in `test_refactor_flow.py`.

## Watch

None.

## Back-out

Revert the commit.
