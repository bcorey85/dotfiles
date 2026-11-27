---
type: "Change"
change_type: "fixed"
title: "A missing binary under bash running as sh reads ENV naming the tool"
description: "An npm script whose binary is missing prints `sh: line 1: tsc: command not found` at exit 127; the criteria verdict now reads it ENV with the install fix naming tsc, not BROKEN."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:52:39-06:00"}
seq: 4
kind: "fix"
components: ["script/criteria-dry-run", "shared/check-output"]
evidence: ["tests/scripts/test_criteria_verdict.py", "tests/scripts/test_check_output.py"]
watches: []
test: "tests/scripts/test_criteria_verdict.py::ItemVerdictTest.test_an_npm_script_whose_binary_is_missing_under_sh_reads_env_naming_the_tool"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`check_output.NOT_FOUND_BRANCHES`: the `/bin/sh: line N:` branch also takes a bare `sh: line N:`, so `missing_tool` names the program.

## Evidence

Bench dry runs printed `BROKEN rc=127 npm run typecheck` with only npm's `> pkg@1.0.0 typecheck` banner in the flag. On a machine where `/bin/sh` is bash, npm's script shell prints `sh: line 1: tsc: command not found`, which no branch matched. The test fails on the old tree (BROKEN) and passes after (ENV, tool `tsc`).

## Result

A missing node_modules binary reads as an environment gap with its fix.

## Watch

—

## Back-out

Restore `^/bin/sh: line` in that branch and remove the new tests.
