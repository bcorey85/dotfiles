---
type: "Change"
change_type: "changed"
title: "The coder, the deep coder, and the test writer now have an explicit tool list: Bash, Read, Edit, Write, LSP"
description: "The coder, the deep coder, and the test writer hold an explicit tool list (`Bash, Read, Edit, Write, LSP`) in place of every tool but Agent."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-18T00:00:00-05:00"}
seq: 8
kind: "behavior"
components: ["agent/test-writer"]
evidence: ["census", "live check"]
watches: []
---

## Change

The coder, the deep coder, and the test writer hold an explicit tool list (`Bash, Read, Edit, Write, LSP`) in place of every tool but Agent. The web tools, the MCP tools, the skill tool, and the tool search go with the old grant, so web and docs research stays with the main session. The three file tools stay because the write hooks match only Write and Edit calls.

## Evidence

census, live check

## Result

On harness 2.1.272 the coder starts at 16K tokens and runs at 17K, against 23K and 29K for an every-tool agent, of which about 8K is the Agent tool and its agent listing. The list itself removes about 4K per turn: the skill tool, the tool search, the skill listing, and the deferred tool names. The start context is read again on every turn, so that is about a tenth of a writing agent's tokens and at least 5% of a ticket's tokens, nearly all of it cache reads, with no token type rising. A first estimate of a fifth to a quarter of a ticket rested on sessions of an older harness, which loaded every tool definition at the start (near 58K), and the live check overturned it. The writing agents called only these five tools, plus the tool search that loaded LSP. A move of reads, writes, and edits to the shell was sized at about 3-4% of context growth and rejected. Open: in the live check no subagent held LSP, with the list or with every tool, so confirm LSP on the next coder dispatch in a typed repo.

## Watch

—

## Back-out

—
