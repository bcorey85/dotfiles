---
type: "Change"
change_type: "added"
title: "herdr-lane-resume --close closes a merged lane that has no lane file entry"
description: "herdr-lane-resume --close takes a lane name or a worktree path and closes a merged lane with no lane file entry, refusing an unmerged, detached, main-checkout, ambiguous or working lane."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T10:29:02-06:00"}
seq: 4
kind: "fix"
components: ["script/herdr-lane-resume"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_lane_resume.py::EntrylessCloseTest::test_entryless_close_by_name_closes_the_merged_workspace_and_prunes"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`--close <name|path>`: an argument with a `/` is a worktree path, anything else a lane name. A lane with an entry closes as
before. With none, the script finds the open herdr workspace on a linked worktree of that name or path, checks the branch is
merged into `origin/<default>`, refuses a working claude agent, closes the workspaces and runs `herdr-worktree-prune --apply`
in the main checkout. It refuses, changing nothing but the origin/<default> ref, for the main checkout, a detached HEAD, the default branch, an unmerged
branch, no open workspace on the worktree, several linked worktrees of that name, and a name under tuios.
The main checkout comes from the shared `scripts/.local/lib/main-checkout.bash` (first `git worktree list` entry, refusing a bare or non-work-tree one); `herdr-worktree` uses it too.

## Evidence

Judgment: the tests run a real bare origin, a real linked worktree and real git merges against stub herdr commands.

## Result

A finished lane whose lane file entry is gone closes with one command instead of by hand.

## Watch

None: a refused close prints its reason and changes nothing but the origin/<default> ref.

## Back-out

Revert the commit: `--close` takes a lane name with an entry only.
