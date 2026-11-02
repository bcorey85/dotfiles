---
type: "Change"
change_type: "added"
title: "Personal workflow never forces a company repo to change"
description: "A global rule keeps every personal setting out of company repos, so the toolkit works on any repo as it stands."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T18:50:45-06:00"}
seq: 453
kind: "user-rule"
components: []
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-01: \"add a rule - personal workflow can never force company repo to change under any circumstances\""
proof: []
unmeasured: "A rule about what the toolkit may ask of a repo; no intake number reads it."
---

## Change

The agent-evals CLAUDE.md now says the toolkit works on a repo as it stands, and that personal per-repo settings go in `~/.claude/CLAUDE.local.md`, which the global file imports and dotfiles ignores, so it stays on each machine. The rule first went in the global CLAUDE.md and moved the same day at the user's word, because it governs how this repo builds the toolkit.

## Evidence

User rule, given after a proposal to add a Quality check line to a repo's CLAUDE.md so the full check would run.

## Result

Not measured.

## Watch

None.

## Back-out

Delete the paragraph from the agent-evals CLAUDE.md.
