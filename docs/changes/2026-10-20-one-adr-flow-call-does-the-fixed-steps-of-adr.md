---
type: "Change"
title: "One adr-flow call does the fixed steps of /adr"
description: "adr-flow.py prep resolves the task dir and prints the target path, PR url, sources and template. check validates the draft. finish checks it again and deletes the task dir only when every safety check passes."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-20T23:22:51-05:00"}
seq: 17
components: ["skill/adr", "script/adr-flow"]
evidence: ["tests", "judgment"]
watches: ["closing-scripts-cache-read", "closing-scripts-output", "closing-scripts-responses", "closing-scripts-active-time"]
---

## Change

- New script `skills/adr/scripts/adr-flow.py` with three verbs.
  - `prep [<path-or-ticket>]`: resolves the task dir, prints the target path, the PR url or `(pending)`, the ticket url, the absolute task dir, each source path with its line count, and the template. It never prints a source body. A `keep` word in the argument adds `--keep-task-dir` to the finish command it prints.
  - `check <adr-path>`: required sections filled, no `[placeholder]`, header bullets, section line caps.
  - `finish <adr-path> [--task-dir DIR] [--draft-is-current] [--keep-task-dir]`: runs `check`, then deletes the task dir only when it is one slug under the repo `docs/plans` dir, holds only plan files and has nothing staged. It refuses when the draft is committed and unchanged but not newer than the task dir's last commit, when a task dir file is newer than the draft, or when the task dir has uncommitted entries.
- `skills/adr/SKILL.md` calls `prep` at step 2 and `finish` at step 6, and `check` after the user's edits.
- The script imports `script_utils.py`, installed in the same step.

## Evidence

Tests: 120 adr-flow tests pass against the installed paths. They cover a plan file moved into the task dir after the draft, a draft committed before the task dir, ignored files, staged entries and both override flags.

Judgment: the skill text listed the task-dir lookup, the PR lookup, the template read, the section checks and the delete as separate model steps. All of them are fixed.

## Result

Installed 2026-10-20. Known gap: the guard against a plan file moved into the task dir after the draft relies on a rename updating `st_ctime`. Run `test_refuses_a_plan_file_moved_into_the_task_dir_after_the_draft` on the work machine (macOS) before trusting it there. No work-log reading yet.

## Watch

The four `closing-scripts-*` entries cover `adr` together with `verify-branch` and `refactor`. They read main-session cache read, output, responses and active seconds per turn, expected down.

## Back-out

Restore the previous `skills/adr/SKILL.md` from the dotfiles history and delete `skills/adr/scripts/adr-flow.py`.
