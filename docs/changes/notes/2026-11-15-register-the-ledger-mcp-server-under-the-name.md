---
type: "Change"
change_type: "fixed"
title: "Register the ledger MCP server under the name sessions call"
description: "scripts/mcp_ledger registers ledger mcp as the user-scope server ledger (the name behind mcp__ledger__*), counts a bare or full-path command as registered, and removes an old agent-memory entry for the same command."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T13:54:30-06:00"}
seq: 6
kind: "fix"
components: ["script/mcp-ledger"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_mcp_ledger.py::RegisterTests::test_hand_registered_bare_command_is_not_added_again"
asked: ""
proof: []
unmeasured: "No intake number reads a one-time registration on a new machine."
---

## Change

A new machine gets the ledger tools under the name sessions call (`mcp__ledger__facts`) from one line,
`./scripts/mcp_ledger`, now listed in the README after the individual installers. The script registers `ledger mcp` as
the user-scope server `ledger` and counts a hand-made entry (bare command `ledger`) as already registered, as well as
one with the resolved path. A user-scope `agent-memory` entry that runs `ledger mcp` is removed after `ledger` is
registered, since it exposes the same tools twice; an `agent-memory` entry that runs anything else is left alone and
the script says so in one line. With no `ledger` installed it exits 0 and prints nothing.

`install/claude-plugins` does not call it. That installer runs before the ledger is necessarily installed and hides
every failure with `|| true`, so the step would skip silently on a machine that gets the ledger later. The explicit line
is the one place the result shows.

## Evidence

judgment: the script registered the name `agent-memory`, which no session calls, and nothing in the repo ran or
documented it. The working entry on this machine was added by hand as `ledger`.

## Result

`tests/scripts/test_mcp_ledger.py` holds 20 tests with a fake `claude` and `ledger` on PATH. Against the unmodified
script 16 of the 20 fail; the four that pass on both are the missing-ledger, missing-claude, unknown-error and
second-run cases. All 20 pass on the new script.

## Watch

None: a one-time setup step.

## Back-out

Revert the commit.
