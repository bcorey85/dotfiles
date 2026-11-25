---
type: "Change"
change_type: "added"
title: "Lanes open with the claude pane alone, no hunk pane"
description: "`herdr-dev --headless` opens tab 1 with only the claude pane. `herdr-worktree --fork`, `herdr-lane-resume` and the watcher's recovery step open lanes this way, so a lane no longer starts a hunk diff viewer that holds memory for hours. A plain `herdr-dev` or `herdr-worktree` keeps the claude | hunk layout."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T11:52:15-06:00"}
seq: 1
kind: "user-rule"
components: ["script/herdr-dev", "script/herdr-worktree", "script/herdr-lane-resume", "script/herdr-worktree-watch"]
evidence: ["user rule"]
watches: []
test: "tests/scripts/test_herdr_dev.py::HerdrDevTest::test_headless_leaves_out_the_hunk_pane"
asked: "2026-11-24: the user asked for a herdr-dev flag that starts only the claude session, for the child sessions started in worktrees, with the default layout unchanged"
proof: []
unmeasured: "No intake number reads pane layout or viewer memory; the gain is the hunk viewer's memory, which lanes no longer start."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `scripts/.local/bin/herdr-dev`: a `--headless` flag, in any order with `--resume`. With it, tab 1 holds the claude
  pane alone: no split, no `hunk-review-pane`, no tuios resize, and focus stays on the claude pane. The console tab and
  the two printed lines (pane id, typed command) stay as they were.
- `scripts/.local/bin/herdr-worktree`: `--fork` runs `herdr-dev --headless`. A run without `--fork` keeps the hunk pane.
  The header's recovery step 2 names `--headless`.
- `scripts/.local/bin/herdr-lane-resume`: runs `herdr-dev --headless --resume`.
- `scripts/.local/bin/herdr-worktree-watch`: the recovery step 2 it writes names `--headless`.

## Evidence

User rule, 2026-11-24. A hunk diff viewer left open in one lane workspace held 3.3 GB for about 11 hours and kept two
lanes' suites from starting under the 8 GB memory check. Nobody reads the hunk pane in a lane.

## Result

`tests/scripts/test_herdr_dev.py` adds 6 tests: the default layout splits the claude pane and starts
`hunk-review-pane`; `--headless` makes no split and no hunk pane and prints the same two lines; `--headless` keeps the
console tab; `--headless` and `--resume` combine in either order; under tuios, `--headless` makes no tab-1 resize call
(the console tab's resize stays), and the default layout still narrows the claude pane to 40%. The headless tests fail against the base script,
which reads `--headless` as the directory. `tests/scripts/test_herdr_worktree.py` checks that `--fork` passes
`--headless` and that a run without `--fork` does not. The lane-resume and watcher tests expect the new argument.

## Watch

None. The gain is memory on this machine, which no intake reads.

## Back-out

Drop `--headless` from the herdr-worktree, herdr-lane-resume and herdr-worktree-watch calls; herdr-dev's default layout
is unchanged, so the flag can stay.
