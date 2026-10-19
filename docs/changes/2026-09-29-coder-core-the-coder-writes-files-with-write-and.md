---
type: "Change"
title: "coder-core: the coder writes files with Write and Edit, and uses Bash only to run commands"
description: "coder-core: the coder writes files with Write and Edit, and uses Bash only to run commands."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-29T00:00:00-05:00"}
seq: 2
components: ["skill/coder-core"]
evidence: ["model round"]
watches: []
---

## Change

coder-core: the coder writes files with Write and Edit, and uses Bash only to run commands

## Evidence

model round

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `## You are the terminal implementer (HARD RULE)` (evidence: removal round, judgment, census, model round):

Edit files yourself, stop if the task is too large, screenshots to /tmp. Write files with Write and Edit, never through Bash: a coder that wrote every file through heredocs in one Bash call hit false-positive hook blocks and stopped with no code written. The no-dispatch sentence was later cut: without it the coder attempted no dispatch or review call. Kept in the contract-only text that matched the full core. Not itself varied. The screenshot line moved here from the dropped style block by judgment. The agent definition grants no dispatch tool, so a census of every saved implementer dispatch found no attempt to sub-dispatch in any of them; the tool list pins this, not the text.

## Result

Under a Sonnet 5.5 coder, 5 of 48 runs wrote every file through heredocs in one Bash call. Hooks blocked the call on false positives, and the coder stopped with no code written. Opus did this in 0 of 48 runs. Untested under the rule. About 20 tokens per coder request.

## Watch

—

## Back-out

—
