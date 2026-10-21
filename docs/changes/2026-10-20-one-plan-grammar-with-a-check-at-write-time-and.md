---
type: "Change"
title: "One plan grammar with a check at write time, and closing phases after coding phases"
description: "code-step reads every plan through one parse function that stops on any line it cannot read, checks a plan when it is written, and runs the closing phases only after every coding phase, so a phase added during a run cannot run after the Verify pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T18:56:02-05:00"}
seq: 8
components: ["script/code-step", "skill/eng-spec"]
evidence: ["census", "judgment"]
watches: []
---

## Change

`scripts/code-step.py`:

- `parse_plan` is the one reader of a plan's Phase Status list and phase sections. A phase id is letters and digits joined by `.` or `-`, and it holds at least one digit (`10.5`, `8.6b`, `P4`, `6A`). Section headings at levels 2 to 4 match.
- A plan that the grammar cannot read stops the run with the file, the line and the expected form. The failure kinds are an unparsed status line, a duplicate id, a coding phase with no section, and a section with no status line. A closing phase needs no section.
- New verbs: `plan check <file>` and `plan parse --json <file>`. `plan-hook` runs `plan check` after each Write or Edit of a plan file, so a bad plan fails when it is written.
- Closing phases (Refactor pass, Test audit, Verify pass, Recap) match by their place in the status list, not by title. They run only after every coding phase is done. When a coding phase is added or reopened after a closing phase ran, the closing phases are unchecked and run again. Lines added to a phase during a run go to an addendum coder.
- The plan census in the intake prints one line and exits 0 when the installed code-step has no `parse_plan`.

Settings entry (PostToolUse): `{"matcher":"Write|Edit","hooks":[{"type":"command","command":"python3 ~/.claude/scripts/code-step.py plan-hook"}]}`.

## Evidence

The earlier closing-phase match read `Phase 10.5` as Phase 10, because it was tested on plans the author wrote. Real plans use ids such as `8.6b`, `P4` and `6A`, and the main session adds phases during a run.

Census on this machine: 307 plans parse with 0 failures. `plan check` passed 18 of 22 files under `~/dev/*/docs/plans`. The 4 failures are review-shard files that copy a status list, not plans. Three real specs had a closing phase with a status line and no section, which the first grammar refused; closing phases no longer need a section.

Tests: 99 pass against the draft, with a walk over every state and verb (288,788 paths, 0 repeats, 0 paths that never end). An end-to-end test edits the plan during a run and checks that the review runs once and the phase finishes.

## Result

Installed 2026-10-20 with the `plan-hook` settings entry. The intake's plan census counts the id and heading shapes at work.

## Watch

None in the edit watches. Read the plan census in the intake: any unparsed shape at work is a grammar gap to fix before trust.

## Back-out

Reinstall the previous `code-step.py` from the dotfiles history and remove the `plan-hook` settings entry.
