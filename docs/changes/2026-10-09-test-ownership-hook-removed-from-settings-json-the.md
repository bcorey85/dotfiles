---
type: "Change"
change_type: "removed"
title: "Test-ownership hook removed from `settings.json`; the global hook list again omits coder test writes and"
description: "Test-ownership hook removed from `settings.json`; the global hook list again omits coder test writes and again tells the agent to redo a blocked shell write with Write or Edit."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-09T00:00:00-05:00"}
seq: 4
kind: "behavior"
components: ["rule/settings-json", "rule/global-claude-md"]
evidence: ["judgment"]
watches: []
---

## Change

Test-ownership hook removed from `settings.json`; the global hook list again omits coder test writes and again tells the agent to redo a blocked shell write with Write or Edit

## Evidence

judgment

## Result

The hook bound no agent type, so it ran on every write and blocked none. The coder rules tell the coder to write its own tests, so a hook list that named coder test writes as blocked contradicted them. A later commit undid the earlier list text by accident, and this restores the text the earlier row backs. The script file stays on disk.

## Watch

—

## Back-out

re-add the hook entry from git
