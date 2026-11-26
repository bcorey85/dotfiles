---
type: "Change"
change_type: "fixed"
title: "a plan folder for a repo with no docs/plans lives in the git dir"
description: "resolve-task-dir.sh gains a git-dir plan root, <git dir>/claude-plans/, with a --home verb that names it when the repo has no docs/plans, and verify-prep finds a plan there and names a ticket path there in place of the tmpfs scratchpad."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T04:41:29-06:00"}
seq: 7
kind: "fix"
components: ["script/resolve-task-dir", "script/verify-prep"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_verify_branch_script.py::PrepTest::test_a_git_dir_plan_folder_resolves_on_a_ticketless_branch_with_no_arguments"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`claude/.claude/scripts/tools/resolve-task-dir.sh`: a repo with no `docs/plans` keeps plan folders in `<git dir>/claude-plans/`, where `<git dir>` is the current worktree's own git dir. `--home <slug>` prints `docs/plans/<slug>` when that folder exists, else the git-dir path. The ticket lookup also searches the git-dir root. With no ticket and no argument, the root's single folder resolves (exit 3 for several). Paths under the git-dir root print absolute. `claude/.claude/scripts/review/verify-prep`: exit 4 names `<git dir>/claude-plans/<KEY>/00-ticket.md` in place of `<scratchpad>/<KEY>-ticket.md`.

## Evidence

Second sighting (queue item `a-lane-plan-and-its-criteria-in-the-tmpfs`): a reboot cleared a lane's tmpfs scratchpad and took its plan, decision log and acceptance criteria, and verify-prep then exited 4. The scratchpad was the only place verify-prep's exit-4 message and the lane knew for a repo that must not gain files. The git dir survives a reboot and is outside the tracked tree.

## Result

The two new verify-prep tests (a git-dir plan folder by ticket branch and by ticketless branch, no arguments) fail against the old resolver (2 failures) and pass against the new one. New `tests/scripts/test_resolve_task_dir.py` covers `--home`, linked worktrees, bad slugs and unchanged docs/plans lookup. Review loop converged in 3 rounds; full suite 7576 tests, 0 failed.

## Watch

None.

## Back-out

Revert the commit; plan folders already in `<git dir>/claude-plans/` then need a path argument.
