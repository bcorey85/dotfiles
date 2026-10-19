---
type: "Change"
title: "The hook that forces a nested agent dispatch into the foreground now tests the caller-identity field that the"
description: "The hook that forces a nested agent dispatch into the foreground now tests the caller-identity field that the harness sends."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 16
components: ["script/agent-foreground"]
evidence: ["census"]
watches: []
---

## Change

The hook that forces a nested agent dispatch into the foreground now tests the caller-identity field that the harness sends. It tested a field name that appears in no hook input. So it exited on every call and never acted. A subagent that dispatched another agent got a launch stub and no result, which is the outcome this hook exists to prevent.

## Evidence

census

## Result

Effect unmeasured. No saved run shows the hook act. Live checks at the next intake: whether a nested dispatch returns a result rather than a launch stub, and whether the main session keeps its background agents. The second is the failure to watch for. The evidence that a top-level call carries no caller identity comes from write calls, not from dispatch calls.

## Watch

—

## Back-out

—
