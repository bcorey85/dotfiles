---
type: "Change"
change_type: "added"
title: "refactor simplify: report branch diff growth, add --diff bound"
description: "simplify-prep records the branch diff before the pass and log --mode simplify ends in a STOP naming the files that grew; --diff BASE bounds the complexity-reviewer to the lines the branch added."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T16:16:37-06:00"}
seq: 3
kind: "user-rule"
components: ["skill/refactor", "script/refactor-flow", "agent/complexity-reviewer"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-25: have refactor simplify report whether the branch diff grew and accept a --diff bound"
proof: []
unmeasured: "SKILL.md steps 7a and 7f lines: no rule-meter detector fits them; listed under Questions in agent-evals questions-for-dev.md"
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`simplify-prep` saves the branch diff (work tree plus untracked files against the merge base) as a sidecar beside the log input. `log --mode simplify` measures it again and prints both. When added lines rose it ends in a `STOP:` naming the files that grew; the STOP also carries the step `log` would otherwise print (the `/review` step with a handoff). `simplify-prep --diff BASE` lists each file of the slice that has an added line, with those lines, and bounds the complexity-reviewer to them; it stops when no file of the target has one. The simplify code moved to `simplify_flow.py` and shared helpers to `flow_common.py`. The complexity-reviewer agent (and its opencode port) now takes that added-lines bound: it reads each whole file and sites findings only on the listed lines. A plain `simplify-prep` prints its prompt with a note when no base resolves. The work tree's added ranges have one owner, `lib/change_added_ranges.py`, shared with the review loop's docs-kind check (its wrapper is `review_added_ranges`); its `read_untracked` also owns the untracked-file kind that `flow_common.classify_untracked` reads. `claude/.claude/scripts/CLAUDE.md` names that module as the owner.

## Evidence

Judgment: the user's ask.

## Result

New simplify tests in `test_refactor_flow.py`.

## Watch

None.

## Back-out

Revert the commit.
