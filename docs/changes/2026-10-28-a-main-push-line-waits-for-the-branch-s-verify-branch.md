---
type: "Change"
title: "A main push line waits for the branch's verify-branch and non-negotiables results"
description: "The orchestration file's Git section now says the orchestrator hands a push or merge line for main only after the branch reports /verify-branch done and, where the repo's CLAUDE.md names a non-negotiables check, that check passed; a green gate or CI run alone never produces that line."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T19:40:00-05:00"}
seq: 197
kind: "fix"
components: ["rule/orchestration"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_a_main_push_line_waits_for_the_branch_s_verify_branch_and_non_negotiables_results"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `orchestration.md`, Git section: one new bullet. The orchestrator hands a push or merge line for main only after the branch reports `/verify-branch` done and, where the repo's CLAUDE.md names a non-negotiables check, that check passed. It reads both in the branch's final report or asks for them. A green gate or CI run alone never produces that line.
- Closes the queue item main-push-line-handed-before-the-slice-s-branch.

## Evidence

- One orchestrating session gated a slice's merge hash, saw it green on a rerun, and handed the user a main push line. The slice's final report then showed that `/verify-branch`, its last phase and the non-negotiables check had not run. The line was retracted and the merge order changed.

## Result

- The rule text is in the orchestration file that the SessionStart hook loads into every main session. The new guidance test fails without the bullet and passes with it.

## Watch

—

## Back-out

Revert the commit. A green gate alone then reads as enough for a main push line again.
