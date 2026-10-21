---
type: "Change"
title: "Prescribe toolkit logging calls as plain commands by path"
description: "The review-scope, log-review-finding and log-escape calls in the review loop and eight skills are now one plain command by the script path, with no `bash \"$HOME/...\"`, variable, array or `$(...)`, because a worktree-isolated session refuses those forms."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-20T19:14:31-05:00"}
seq: 11
components: ["agent/review-loop", "skill/review", "skill/fix", "skill/cc", "skill/escape", "skill/refactor", "skill/commit", "skill/pr-comments", "skill/verify-branch", "skill/test-audit", "skill/eng-spec"]
evidence: ["transcript read", "docs"]
watches: []
---

## Change

- `agents/review-loop.md` Step 0: `~/.claude/skills/review/review-scope caller=<caller>`, plus one sentence that names the refused forms.
- `skills/_shared/finding-log.md`: the `L=` variable and the `C=( ... )` array are gone. Each run row and finding row is one plain call that repeats lane, scope, phase and iter.
- `skills/review/SKILL.md` and `skills/fix/SKILL.md` ask-outcome rows: plain path, no `repo=` and no `branch=`.
- Seven log-escape callers (fix, cc, escape, refactor, commit, pr-comments, verify-branch): `~/.claude/scripts/log-escape stage_found=...`, no `repo=`.
- log-review-metrics in the review-loop metrics step, test-audit and calibrate, and log-spec-run in eng-spec 6b-review: plain path and no `repo=`. calibrate passes `out=~/.claude/review-calibration.jsonl`.
- log-review-metrics and log-spec-run set `repo` from repo-name, as log-review-finding and log-escape do, and keep a caller value only when repo-name fails. log-review-metrics expands a leading `~` in `out=`.
- Five other calls lose the `bash` prefix and run the executable by path: review-gate-mark in review and fix, resolve-task-dir in verify-branch and test-intent-reviewer, spec-criteria-lint in eng-spec finalize. The review-commit-gate hook matches `review-gate-mark clean` anywhere in the command, so the mark still registers.
- `agents/test-reviewer.md` branch scope: `<default>` is the first word that `~/.claude/scripts/branch-base` prints. On its `STOP:` line, the reviewer asks the user for the base.
- `skills/audit/skills.md` names the `log-skill-use.py` hooks in place of the old `.sh` name.

## Evidence

The Claude Code worktree docs ("How Claude Code enforces isolation", Command shape check) say that a worktree-isolated session refuses a command whose text it cannot verify, and that the check cannot be turned off. One bench transcript read paired every logging call with its result. Every form with `$HOME`, a variable, `$(...)`, an array or several statements was refused. The same agent ran the literal-path form seconds later and it passed. Later, in an EnterWorktree session, the guard refused five log-review-metrics calls from review-loop and fix subagents: "this command runs bash in a plain command; what it reads or is handed as shell text cannot be shown not to run git." The five rows were lost. log-review-finding and log-escape already overwrite `repo` and `branch` with the worktree-aware name, so the dropped `repo=` and `branch=` arguments carried nothing.

## Result

A probe in a worktree-isolated subagent ran review-scope four ways. The guard refused `bash "$HOME/..."`. It ran `~/.claude/skills/review/review-scope`, the same call split with a backslash line continuation, and the literal home path.

Installed 2026-10-20 with the logger scripts. The `review-fix.py` mark strings lost their `bash ` prefix on 2026-10-21, with the sign-off install bundle.

## Watch

None. The work logs do not record refusals by the built-in guard.

## Back-out

Restore the previous call lines and the two scripts from git in `~/dotfiles`.
