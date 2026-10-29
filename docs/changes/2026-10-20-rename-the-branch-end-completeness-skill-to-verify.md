---
type: "Change"
change_type: "changed"
title: "Rename the branch-end completeness skill to verify-branch"
description: "Claude Code 2.1.304 ships its own skill named verify, and adds the line 'Always run /verify right before the commit command' to the Bash tool instructions when any skill has that name. With the user's skill also named verify, the line sent agents to the branch-end completeness check before each commit. The user's skill is now verify-branch, so the name verify means only Claude Code's skill."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T11:16:05-05:00"}
seq: 3
kind: "behavior"
components: ["skill/verify", "skill/verify-branch", "script/code-step", "agent/review-loop", "agent/plan-verifier", "skill/branch-recap", "skill/escape"]
evidence: ["judgment"]
watches: []
---

## Change

`skills/verify/` moved to `skills/verify-branch/`, with `name: verify-branch`. Every command reference to the skill changed to `/verify-branch`: `README.md`, `agents/review-loop.md`, `agents/plan-verifier.md`, `skills/branch-recap/SKILL.md`, `skills/escape/SKILL.md`, `skills/audit/review.md`, and `skills/_shared/` `escape-ratchet.md`, `plan-format.md` and `closing-phases.md`.

`scripts/code-step.py` maps the closing phase title `Verify pass` to `/verify-branch` in place of `/verify`, in 5 places. The title regex does not change, so plans already written still match. `scripts/resolve-task-dir.sh` changes in a comment only.

These do not change, so the time series continue:

- The log labels `lane=verify` and `stage_found=verify`, and `q-verify` in `scripts/log-escape`.
- The `code-step.py verify` verb.

`skill-usage.jsonl` rows take the skill name from the Skill tool input, so new rows say `verify-branch`. `bin/compaction-cost.py`, `bin/gp_dispatch_census.py` and `bin/work-live-census.py` in agent-evals count both names.

## Evidence

judgment

The Claude Code 2.1.304 binary builds the commit line from the loaded skill list. It adds the line if a skill named `verify` exists, and Claude Code always loads its own `verify` skill. That skill drives the changed flow end to end before a commit, and writes a project verify skill into a repo that has none. The user's `verify` is a branch-end completeness check that reconciles the diff against the plan. With one name for both, the line pointed agents at the wrong check.

The rename does not remove the line. It makes the line point at the skill it was written for.

## Result

| Test | Result |
|---|---|
| `test_code_step`, `test_code_step_termination`, against the patched script | 67 pass |
| Full dotfiles suite, before the script install | 448 ran, 2 fail, 2 expected failures |

The 2 failures are `test_closing_phase_titles_must_be_the_closing_phase` and `test_verify_pass_dispatches_the_branch_wide_reviewer_first`. They check the installed script for the new name, and pass after the install.

## Watch

None. The dotfiles suite fails if `code-step.py` and the tests disagree on the skill name.

## Back-out

Move `skills/verify-branch/` back to `skills/verify/`, set `name: verify`, and revert the text edits. Restore `scripts/code-step.py` and `scripts/resolve-task-dir.sh` from the commit before this change.
