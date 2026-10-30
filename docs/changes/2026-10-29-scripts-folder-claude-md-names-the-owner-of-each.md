---
type: "Change"
change_type: "added"
title: "Scripts folder CLAUDE.md names the owner of each shared fact"
description: "A CLAUDE.md under claude/.claude/scripts/ tells a coder to search first, import the one owner of each shared fact, pass JSON between steps and report every hook exception."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T00:00:00-05:00"}
seq: 297
kind: "user-rule"
components: ["rule/scripts-claude-md"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-29: these are LLM agents that dont have foresight to look before they hammer. we need to guide them"
proof: []
unmeasured: "No intake number reads whether a script adds a second copy of a fact; the duplicate-code check covers only repeated names and clones."
---

## Change

New `claude/.claude/scripts/CLAUDE.md`, loaded whenever an agent works under `scripts/`. It tells the agent to `rg` for an existing owner before adding a parser, rule, status, store or classifier, and lists the one owner of each shared fact: review clean status, the reviewed tree and commit credit, tree fingerprint, the hand-back store, the full-check result and scope, the test-file rule, command classification, and shell parsing for gates. It also bans rendering JSON as text for another script to parse, bans swallowed hook exceptions, and requires one atomic state write per command.

`docs/toolkit-script-rules.md` imports it with `@~/dotfiles/claude/.claude/scripts/CLAUDE.md` on its first line after the title, because sessions started outside `scripts/` do not load a nested CLAUDE.md but do load that file.

## Evidence

The user's rule, from the architects' read of the scripts: several facts have more than one owner today (review clean status, the reviewed tree, test-file names, command classification, tree identity), and some steps re-parse another step's text.

## Result

Not measured. About 40 lines are now paid on every run under `scripts/`. The file points at the owner to collapse into; it does not remove the existing copies.

## Watch

None.

## Back-out

Delete `claude/.claude/scripts/CLAUDE.md` and the import line in `docs/toolkit-script-rules.md`.
