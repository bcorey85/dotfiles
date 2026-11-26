---
type: "Change"
change_type: "fixed"
title: "Lanes open with no console tab: herdr-dev --headless skips the three shells"
description: "A lane started by herdr-worktree --fork or herdr-lane-resume opens with its claude pane alone: herdr-dev --headless no longer builds the console tab of three idle shells."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T22:39:59-06:00"}
seq: 3
kind: "fix"
components: ["script/herdr-dev"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_herdr_dev.py::HerdrDevTest::test_headless_builds_no_console_tab"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

- `scripts/.local/bin/herdr-dev`: with `--headless`, it builds no console tab: no tab create, no splits, no tuios
  console layout and no mprocs start. The default layout keeps the console tab. `build_tuios_console` takes the
  console pane as an argument.
- `tests/scripts/test_herdr_dev.py`: the test that kept the console tab under `--headless` is replaced by one that
  checks no tab create and no pane split; a new test checks the default layout still builds the console tab.

## Evidence

Every lane workspace opened on 2026-11-25 held four panes: claude plus three idle zsh shells in the console tab. Each
shell holds memory that the next lane needs, and the lanes rule says a lane runs its claude pane alone.

## Result

`test_headless_builds_no_console_tab` fails against the base script (it makes a `tab create`) and passes after. Full
suite: `bash tests/run.sh`, 6674 tests, 0 failed.

## Watch

None: no intake number reads pane layout.

## Back-out

Revert the commit; lanes then open with the console tab again.
