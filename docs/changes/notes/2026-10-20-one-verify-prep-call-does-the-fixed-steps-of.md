---
type: "Change"
change_type: "added"
title: "One verify-prep call does the fixed steps of verify-branch"
description: "verify-prep resolves the task dir, reads the criteria, measures the diff, checks for a branch-wide review since the last change and prints the exact dispatches; verify-log writes the run and gap rows. The Verify pass in /code only invokes /verify-branch, which owns the branch-wide review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T18:56:02-05:00"}
seq: 9
kind: "behavior"
components: ["skill/verify-branch", "script/code-step"]
evidence: ["census", "judgment"]
watches: ["verify-branch-one-call", "verify-branch-one-call-escapes"]
---

## Change

- New scripts `scripts/verify-prep`, `scripts/verify-log` and `scripts/verify_common.py`.
- `skills/verify-branch/SKILL.md`: Step 0 runs `verify-prep` and follows its printed steps. Step 1 sends one `code-reviewer` over the branch diff unless prep reports a branch-wide review since the last change, routes its findings through `/review`, logs the review with `verify-log review`, and reruns prep. Step 2 sends `plan-verifier` with the payload prep prints. Step 3 pipes the verdict rows to `verify-log`, which writes the run row and one drift row per gap.
- `scripts/code-step.py`: the Verify pass invokes `/verify-branch` and no longer sends its own `code-reviewer`. The skill runs the review on every path, direct or from `/code`.
- `skills/_shared/closing-phases.md`: the Verify pass text says that `/verify-branch` runs both checks.

Review coverage is the same: a branch-wide review runs at branch end unless one already ran on the same diff.

## Evidence

Work main sessions on Opus: `/verify-branch` 205 turns, 1,737 responses, a mean of 8.5 per turn. An audit of the skill text counted the fixed steps (task-dir lookup, criteria read, diff measure, log rows) at about 4 responses per call, about 820 over the window.

Tests: 24 pass against the drafts. `verify-prep` ran on 27 of 27 real task dirs on this machine.

## Result

Installed 2026-10-20. The `verify-branch` front matter kept its live description. No work-log reading yet.

## Watch

- `verify-branch-one-call`: main-session responses per turn for `/verify-branch`, expected down.
- `verify-branch-one-call-escapes`: review escapes per review run, expected flat.

Reading, 2026-10-27 intake: `verify-branch-one-call` BETTER, closed. Main-session responses per `/verify-branch` turn went from a 9.85 median (range 7.35–13.50) to 6.42, over 33 turns. The escapes watch has no data yet.

## Back-out

Restore the previous `SKILL.md`, `closing-phases.md` and `code-step.py` from the dotfiles history and delete the three scripts.
