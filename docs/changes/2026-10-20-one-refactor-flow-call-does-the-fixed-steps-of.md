---
type: "Change"
title: "One refactor-flow call does the fixed steps of each /refactor mode"
description: "refactor-flow.py has one prep verb per mode, a log verb that writes the escape and finding rows once, and a handoff verb that renders the review hand-off. Each verb ends with a NEXT or STOP line."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-20T23:22:51-05:00"}
seq: 18
components: ["skill/refactor", "script/refactor-flow"]
evidence: ["tests", "judgment"]
watches: ["closing-scripts-cache-read", "closing-scripts-output", "closing-scripts-responses", "closing-scripts-active-time"]
---

## Change

- New script `skills/refactor/scripts/refactor-flow.py`. Every verb prints its report and ends with a `NEXT:` line for what the model still does or a `STOP:` line. Exit 1 is bad input and writes nothing.
  - `branch-prep [--head REF] [--base REF]`: picks the base through `branch-base`, runs the mechanical sweep and prints the finder prompt with the changed-file list. Deleted, renamed and binary files are marked.
  - `audit-prep <dir>` and `simplify-prep <dir|file...> [--slice N]`: print the finder inputs for those modes.
  - `log --mode branch|targeted|audit|simplify --input FILE.json`: writes the escape and finding rows through `log-escape` and `log-review-finding`. It keeps a hash of every row a writer accepted, so a rerun on the same input file skips rows already written.
  - `handoff --input FILE.json`: renders the hand-off block from the input file and prints the review dispatch.
- `skills/refactor/SKILL.md` gets a `## Script` block. The skill dispatches the finder with the printed prompt and the coder as before, then runs `handoff` and dispatches `/review` as printed.
- The prep verbs delete all but the newest 49 of their own temp input files.

## Evidence

Tests: 77 refactor-flow tests pass against the installed paths. They run the verbs on real input shapes: an empty diff, a base with no shared history, a repository with no commits, a writer that refuses a row, and a rerun of `log`.

Judgment: the skill text spelled out the base choice, the sweep, the finder prompt, the log rows and the hand-off block as model steps. All of them are fixed.

## Result

Installed 2026-10-20. The skill kept its live front matter. No work-log reading yet.

## Watch

The four `closing-scripts-*` entries cover `refactor` together with `verify-branch` and `adr`. They read main-session cache read, output, responses and active seconds per turn, expected down.

## Back-out

Restore the previous `skills/refactor/SKILL.md` from the dotfiles history and delete `skills/refactor/scripts/refactor-flow.py`.
