---
type: "Change"
change_type: "fixed"
title: "Test that every mcp tool name in the toolkit names a registered server"
description: "A test fails when a skill, agent, command or settings file names an mcp__<server>__ tool for a server the toolkit does not register, so a stale server name is caught before a lane breaks."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T15:48:43-06:00"}
seq: 34
kind: "fix"
components: ["script/mcp-ledger", "skill/audit"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_mcp_server_names.py::McpServerNames::test_every_named_server_is_known"
asked: ""
proof: []
unmeasured: "No intake number reads a tool-name typo; the test is the guard."
---

## Change

A retro lane called `mcp__agent-memory__*` tools; the server is registered as `ledger`. `tests/scripts/test_mcp_server_names.py` scans claude/.claude for `mcp__<server>__` names and fails on any server outside the known set: `ledger` is read from `server_name` in scripts/mcp_ledger, and the Jira, Atlassian and context7 servers (registered outside this repo) are listed once in the test. No stale name remained in this tree, so no skill text changed.

## Evidence

judgment: the old name reached a lane because no check tied tool names to the registered server.

## Result

With a skill file containing `mcp__agent-memory__facts` as the scanned folder, the test fails naming agent-memory; on this tree it passes. `test_old_agent_memory_name_is_flagged` pins the scanner on that text.

## Watch

None.

## Back-out

Delete the test file.

