---
type: "Change"
title: "The git rules file and the Obsidian and rule-maintenance sections of the global CLAUDE.md moved into the"
description: "The git rules file and the Obsidian and rule-maintenance sections of the global CLAUDE.md moved into the orchestration file, which only the main session loads."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 3
components: ["rule/global-claude-md", "rule/orchestration"]
evidence: ["census", "judgment"]
watches: []
---

## Change

The git rules file and the Obsidian and rule-maintenance sections of the global CLAUDE.md moved into the orchestration file, which only the main session loads. The text is unchanged, except that "every line here" now names the files it covers. The compaction section stays in CLAUDE.md, because a long subagent run can compact.

## Evidence

census, judgment

### Anchor reasons

Anchor `CLAUDE.md`, section `# Global Claude Code Rules` (evidence: unproven):

Title only, 5 words. Loads in every main session and every subagent.

Anchor `rules/typescript.md`, section `# TypeScript` (evidence: unproven):

24 words. Interface over type, and no `any`. Loads when a `.ts` file is read. Lint can enforce both in repos that configure it.

## Result

Only the main session owns git, notes and rule edits, and no agent file runs a git write. Subagents stop loading about 315 words on every request. At work, subagents ran about 550 times a week with a median of 25 tool uses per run, measured on the 698 runs that record tool uses. That is about 6M to 15M cache-read tokens a week, mostly on the Opus-pinned agents. The main session loads the same text as before.

## Watch

—

## Back-out

restore the file and sections from git.
