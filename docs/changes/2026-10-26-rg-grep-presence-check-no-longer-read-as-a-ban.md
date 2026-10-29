---
type: "Change"
change_type: "fixed"
title: "rg/grep presence check no longer read as a ban"
description: "An rg or grep Automated Verification line stays a ban unless its text says it checks presence; then exit 0 passes."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-26T11:00:34-05:00"}
seq: 58
kind: "fix"
components: ["script/code-step", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_an_rg_presence_check_passes_on_a_hit"
asked: ""
proof: []
unmeasured: ""
---

## Change

run_verification_commands in code_step_boundary.py read every line starting with rg, grep or egrep as a ban, so a presence check that exits 0 on a hit failed. is_search_ban now keeps such a line a ban unless its text (outside the command) has presence wording (Presence, present, exists, contains, defines, defined, finds, found, a hit, matches), where exit 0 passes; ban wording (Prohibition, no match, no output, prints nothing, exit 1, absent, must not, none) or `! rg` wins on the same line; git grep is always a ban. A ban that fails with no presence wording adds a note saying so. plan-format.md states the rule in one sentence.

## Evidence

judgment: a peer session saw three false failures of an rg presence check in one plan. The new presence test fails on the base commit (exit 1 reported for a hit) and passes after; a second test pins that a ban with no wording ("the old name is gone") fails on a hit. The existing rg and grep ban tests still pass.

## Result

Full suite and ruff pass.

## Watch

—

## Back-out

Restore the SEARCH_BAN regex use in run_verification_commands, remove BAN_WORDING, PRESENCE_WORDING and is_search_ban, the plan-format sentence and the test.

