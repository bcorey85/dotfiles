---
type: "Change"
change_type: "changed"
title: "A plan-impact ruling names who made it, and only the user's ruling changes the criteria"
description: "decide adopt|keep needs --by user|session. Only --by user signs with the git user name and lets the plan-edit coder rewrite the acceptance criteria. A session or pre-set ruling edits the plan only, and code-step.py restores the criteria if the coder changes them."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T00:00:14-05:00"}
seq: 1
kind: "behavior"
components: ["script/code-step", "script/review-fix", "skill/code", "skill/review", "skill/fix"]
evidence: ["judgment", "tests"]
watches: []
---

## Change

- `scripts/code-step.py`: `decide adopt|keep` needs `--by user|session` before `--ruling`. Without it the call stops with the usage line and changes no state.
  - `--by user` signs the ruling with the git user name. The plan-edit coder may rewrite the acceptance criteria and sign them off.
  - `--by session` signs as "the session, not the user". The pre-set decision signs as "the pre-set decision". The plan-edit coder edits the plan only. The script saves the criteria text before that coder runs. It restores the text after the plan edit, or at the next `tick` or `start` on the same branch if the plan edit did not finish, and says so. On another branch, that `tick` or `start` drops the saved text and says so.
  - A restore keeps the text it replaced in a new file under the git dir (`code-step-replaced-criteria`) and names that file. A criteria file that did not exist at the save is moved there the same way.
  - The step after the plan edit waits for the plan-edit coder's report before it restores the criteria. On a branch other than the one where the plan edit started, or with the plan file missing, it stops, changes nothing and tells the user what to do.
  - While the plan-edit coder is still out, `tick`, `start` and `start --take-over` stop, change nothing and name the step after the plan edit as the command to run first.
  - The RESOLVED block, the deviation entry and the dispatch text name who ruled.
- `scripts/review-fix.py`: `decide` takes the same `--by`, so a `/review` or `/fix` ruling names who made it. `discuss` prints the exact `decide` commands for each outcome.
- `skills/review/SKILL.md`, `skills/fix/SKILL.md`: after a discussion, run the `decide` command that the script printed. The old wording named `decide adopt` and `decide keep` with no `--by`, which the new script refuses.
- `skills/code/SKILL.md`: a task text that starts with `after-plan-edit` goes to `code-step.py` as is.
- `skills/_shared/handoff-block.md`: a RESOLVED block names who ruled: the user, the session or the pre-set decision.

## Evidence

Judgment: only the user's explicit sign-off overrides an acceptance criterion. Before this change, a pre-set decision or the session's own call was recorded in "the user's words", and the plan-edit coder could rewrite the criteria on it.

Tests: the bundle tests cover a missing, bad and valueless `--by`, both rulings, the pre-set path, and the restore of criteria that a coder edited on a session ruling.

## Result

Installed 2026-10-21 with the sign-off install bundle. Before that, from 23:15 on 2026-10-20, a first draft of the `code-step.py` part was live by mistake: the coder's patch script wrote it past the script write gate. The bundle tests pass: 233 for `code-step.py`, 13 for the fixes and the full termination walk.

Two known gaps stay. A plan edit that spans the install loses its saved criteria text. A run state with no branch skips the branch check.

## Watch

None. A wrong sign-off shows in the criteria file and its deviation entry, not in a work-log number.

## Back-out

Reinstall the previous `code-step.py` and `review-fix.py` from the dotfiles history, and restore the previous `handoff-block.md`.
