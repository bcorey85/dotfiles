---
type: "Change"
change_type: "added"
title: "Scripts folder CLAUDE.md names the owner of commit placement, ask outcome words and the file lock"
description: "Three owner lines tell a coder under scripts/ to import the commit-folder lookup, the ask outcome words and the file lock, in place of writing a second copy."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-14T23:26:55-06:00"}
seq: 3
kind: "user-rule"
components: ["rule/scripts-claude-md"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-14: go (to the three owner lines shown in the reply before it)"
proof: []
unmeasured: "No rule-tester run: no fixture shows a coder adding a second copy of one of these three helpers. No intake number reads it either."
---

## Change

Three lines under `## Owners` in `claude/.claude/scripts/CLAUDE.md`:

- which folder a git commit lands in: `lib/shell_command.py` (`git_commit_dirs`, `git_c_directory`);
- the ask outcome words and the ruling command the commit gate prints: `lib/ask_outcome_words.py`;
- a lock held across processes: `lib/file_lock.py`.

## Evidence

Judgment. The three helpers shipped with the phase-asks ruling gate and had no owner line, so the next coder under `scripts/` had no pointer to them.

## Result

Not measured. Three more lines are paid on every run under `scripts/`.

## Watch

None.

## Back-out

Delete the three lines.
