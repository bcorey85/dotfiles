---
type: "Change"
change_type: "changed"
title: "The worktree rule names tuios beside herdr"
description: "The worktree line in orchestration.md now sends a session inside tuios to `herdr-worktree --fork`, the same as inside herdr. tuios sets `HERDR_ENV` too."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-24T05:06:55-05:00"}
seq: 5
kind: "behavior"
components: ["skill/herdr"]
evidence: ["judgment"]
watches: []
test: ""
unmeasured: "No work-log field records which route opened a worktree."
---

## Change

- `orchestration.md`, `### Git`, the worktree location line: "Inside herdr" now reads "Inside herdr or tuios". The test stays `HERDR_ENV` set. The edit came in with the tuios port merge, with no change file. This file records it after the fact.

## Evidence

Judgment: the tuios port sets `HERDR_ENV`, so the rule already fired inside tuios. The new words name the case the test already covers.

## Result

The rule text matches when it fires. Behavior does not change.

## Watch

None. See `unmeasured`.

## Back-out

Remove "or tuios" from the worktree location line in `orchestration.md`.
