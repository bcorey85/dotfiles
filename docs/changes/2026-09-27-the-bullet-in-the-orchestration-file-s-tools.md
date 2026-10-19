---
type: "Change"
title: "The bullet in the orchestration file's Tools section that told the main session to search past sessions"
description: "The bullet in the orchestration file's Tools section that told the main session to search past sessions before asking the user to recall past work was deleted."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 6
components: ["rule/orchestration"]
evidence: ["removal round"]
watches: []
---

## Change

The bullet in the orchestration file's Tools section that told the main session to search past sessions before asking the user to recall past work was deleted. The Tools, Tool Use Efficiency, Git and Stacked PRs sections stay.

## Evidence

removal round

### Anchor reasons

Anchor `orchestration.md`, section `### Tools` (evidence: removal round):

97 words, moved from CLAUDE.md. Commands: Write for new files, Read and Edit for file I/O, LSP before grep in typed code, `--help` before a guessed flag. The shell-write gate enforces the redirection and in-place halves. The coder did the same work without it. Tested in the main session with the tool-efficiency and git blocks: without them it broke a rule in 4 of 6 tasks, one of them a new file made by shell redirect. The memory-search bullet was removed because the memory server's own instructions say the same and the model searched without it. Main session only.

Anchor `orchestration.md`, section `### Stacked PRs (`gh stack`, github/gh-stack)` (evidence: removal round):

137 words, moved from the git rules file. When to restack, the ban on the force-pushing `gh stack` commands, and how to adopt a chain. Without it, the main session skipped the stack tool and tried raw merge, push or PR-merge commands itself in 3 of 4 stack tasks, and 0 of 4 with it. Costs about 280 tokens a request. The git discipline gate cannot see the force in those commands, so the text is the only guard. Main session only.

## Result

The memory server's own instructions tell the model to search before asking. With or without the bullet, the main session searched past sessions on a "same error as last time" request, and it also searched unprompted on two other tasks without it. The other sections were tested for removal in the main session and held. Without the tools, tool-efficiency and git sections, it broke a rule in 4 of 6 tasks: a lowercase ticket branch, no worktree rename or push, a new file made by shell redirect, and a second full test-suite run. Those runs also used more tokens, 51.8K against 39.4K median cache read per run, so the 670 tokens those sections add per request paid for themselves there. Without the stacked-PR section, it skipped the stack tool and tried raw merge, push or PR-merge commands itself in 3 of 4 tasks, and in 0 of 4 with it. One run per task. The bullet removal saves about 30 tokens per main-session request.

## Watch

—

## Back-out

restore the bullet from git.
