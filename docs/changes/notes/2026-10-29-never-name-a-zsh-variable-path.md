---
type: "Change"
change_type: "added"
title: "Never name a zsh variable path"
description: "The global CLAUDE.md Safety Rails say zsh ties `path` to `PATH`: never name a shell variable `path`, and name it for what it holds."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T22:38:04-05:00"}
seq: 298
kind: "user-rule"
components: ["rule/global-claude-md"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-29: what rules should we be adding to our claude.md to prevent common issues, then (on five proposed rules, this one among them): add them"
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/CLAUDE.md` (and its opencode link `AGENTS.md`), Safety Rails: in zsh `path` is tied to `PATH`, so never name a shell variable `path`. Assigning it (`path=…` or `for path in …`) replaces the command search path, and later commands fail with "command not found". Name the variable for what it holds.

## Evidence

- An orchestrator session on 2026-10-29 named a Bash-tool variable `path`. zsh replaced `PATH`, and the rest of that call failed.
- The other four rules from the same ask are repo rules and live in that repo's CLAUDE.md.

## Result

- The rule is in the always-loaded file. As a user rule, no test pins it.

## Watch

—

## Back-out

Revert the commit. The global file again says nothing about `path`.
