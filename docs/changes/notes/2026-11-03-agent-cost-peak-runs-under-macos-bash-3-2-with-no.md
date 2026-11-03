---
type: "Change"
change_type: "fixed"
title: "agent-cost PEAK runs under macOS bash 3.2 with no cutoff"
description: "agent-cost's PEAK mode no longer dies with \"find_args[@]: unbound variable\" under macOS bash 3.2 when no --days or --since is given."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-03T09:05:52-06:00"}
seq: 5
kind: "fix"
components: ["script/agent-cost"]
evidence: ["macOS suite run"]
watches: []
test: "tests/scripts/test_agent_cost.py::AgentCostTest::test_peak_output_matches_master"
asked: ""
proof: []
unmeasured: ""
---

## Change

`scripts/.local/bin/agent-cost` expands the empty `find_args` array as `${find_args[@]+"${find_args[@]}"}`, which bash 3.2 under `set -u` accepts.

## Evidence

On macOS `/bin/bash` 3.2.57 a bare `agent-cost` printed `find_args[@]: unbound variable` and `agent-cost: no dispatches in range`.

## Result

Before: PEAK with no cutoff found no dispatches on macOS. After: it reports them and matches the fixture output.

## Watch

None: the test above pins it on a macOS run of `bash tests/run.sh`.

## Back-out

Revert the commit.

