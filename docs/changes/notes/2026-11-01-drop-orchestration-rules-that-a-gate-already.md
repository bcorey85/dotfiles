---
type: "Change"
change_type: "removed"
title: "Drop orchestration rules that a gate already states"
description: "The SessionStart orchestration text loses two rules that a gate enforces and states in its own deny message, cutting it from 2,318 to 2,120 tokens."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T04:33:42-06:00"}
seq: 437
kind: "structured"
components: ["rule/orchestration"]
evidence: ["census"]
watches: []
test: ""
asked: ""
proof: ["2026-11-01-main-session-prefix-breakdown-what-each-always"]
unmeasured: "A measured prefix drop with no behavior change: both removed rules stay enforced by a gate whose deny message states the same instruction, so no intake number moves; the token cut is read directly by the headless prefix run."
---

## Change

Removed from `orchestration.md`, which every main session loads at start:

- The second sentence of the shell-file-creation bullet: "shell-write-gate denies redirection or `tee` onto a
  git-tracked file, and in-place editing (`sed -i`, `perl -pi`, `awk -i inplace`) of ANY file, tracked or not."
  `scripts/gates/shell_write_gate.py` enforces it and says so in its deny message. The first sentence (use Write for a
  new file) stays.
- The "Worktree branches: NEVER leave the auto-generated `worktree-` prefix" bullet.
  `scripts/gates/git_discipline_gate.py` denies commit and push on a `worktree-` branch with the same rename
  instruction, and `herdr-worktree` pushes the branch itself. The worktree-location bullet still forbids
  `.claude/worktrees/`. The bullet's push-before-work step is dropped on purpose for the non-herdr path
  (`git worktree add`): the user keeps throwaway branches off the remote (user, 2026-11-01).

Every other rule in the file is stated nowhere the main session loads.

## Evidence

A census of every rule in the file against agents, skills, CLAUDE.md files and gate messages found only these two
stated elsewhere. Headless prefix run, each version as an empty project's CLAUDE.md minus the empty project.

## Result

The orchestration text drops 2,318 → 2,120 tokens (−198, 8.5%; median of 8 runs per arm), on every main session start. The dotfiles suite
passes (2,936 tests, 0 failed).

## Watch

None: no behavior changes, so no intake number reads it.

## Back-out

Restore the two passages from git history of `claude/.claude/orchestration.md`.
