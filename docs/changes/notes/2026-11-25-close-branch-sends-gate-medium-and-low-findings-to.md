---
type: "Change"
change_type: "fixed"
title: "close-branch sends gate medium and low findings to the coder"
description: "The close-branch fix-diff gate sends its medium and low findings to a coder round, never to open items, so Step 4 and Step 5's verify-log rows agree."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T17:01:26-06:00"}
seq: 3
kind: "fix"
components: ["skill/close-branch"]
evidence: ["judgment", "tests/scripts/test_guidance_rules.py"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_the_close_pass_gate_sends_medium_and_low_findings_to_a_coder_not_open_items"
asked: ""
proof: []
unmeasured: "Rule meter CB01 (detector gate_minor_to_coder, 1 run per cell): on 3/3, off 3/3 across supportive, neutral and competing, so ALREADY. The off arm keeps the fail bullet, which also names the medium and low findings. The line ships because the old text sent these findings to open items, which verify-log cannot log without an ask that blocks the plan log."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

close-branch Step 4: a medium or low finding from the fix-diff gate never goes to open items. On a gate pass with such findings, one `coder` dispatch takes them, then Step 5. On a gate fail, they go to the coder with the failing items. The recap's Open items line no longer lists gate medium and low findings.

## Evidence

Step 5 logs every Step 2 to 4 finding with `actioned` `fixed`, `skipped_fp` or `ask`. A finding left under open items had no value to log it with, and an `ask` blocks the next plan log with ASKS OPEN.

## Result

Rule meter CB01: on 3/3, off 3/3 (ALREADY). Step 4 and Step 5 now name the same place for a gate medium or low finding: a coder round, logged `fixed` or `skipped_fp`.

## Watch

—

## Back-out

Revert the Step 4 hunk and the recap's Open items line in `claude/.claude/skills/close-branch/SKILL.md`.
