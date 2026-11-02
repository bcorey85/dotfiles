---
type: "Change"
change_type: "added"
title: "Every review escape records why review missed it"
description: "log-escape now requires miss_reason, a plain-text label from a fixed list, so the work logs can show that we miss a class of defect for a named reason. Model callers pick the label from escape-ratchet.md; scripts pass unknown."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T20:41:11-06:00"}
seq: 453
kind: "user-rule"
components: ["script/log-escape", "shared/escape-ratchet", "skill/escape", "skill/cc", "skill/commit", "skill/pr-comments", "skill/eng-spec", "skill/audit", "skill/refactor", "script/verify-log", "script/review-fix"]
evidence: ["census", "judgment"]
watches: []
test: ""
asked: "2026-11-01: \"stuff like we always miss x because y so z must pass or its a regression\""
proof: []
unmeasured: ""
---

## Change

`log-escape` refuses a row whose `miss_reason` is missing or outside the list: out-of-scope, needs-other-file, needs-runtime, plan-gap, seen-dismissed, rule-absent, overlooked, unknown. `escape-ratchet.md` defines each label, first fit wins. `/escape`, `/cc`, `/commit` and `/pr-comments` pick a label, eng-spec plan review passes plan-gap, and `verify-log`, `review_fix.py` and `refactor_flow.py` pass unknown. `/audit review` counts by class and miss reason.

## Evidence

The label list was checked against the 37 escape rows in `~/dev/evals/review-golden-v4-sealed/keys/*.json`. Most need a read outside the diff or are copies in plain view. The second shape fits no candidate label, so `overlooked` joined the list. The rows hold no record of a dismissal and none shows a runtime defect, so seen-dismissed and needs-runtime stand on judgment. The work log holds 634 escape rows, 354 with gate_missed review, and none says why.

## Result

`tests/scripts/test_log_escape.py` covers each label stored as plain text, a missing label refused, and a label outside the list refused.

`ledger write` refuses a field the registry does not name, with exit 2. The ledger never blocks the workflow: `log-escape` drops `miss_reason` on that refusal, sends the row again, prints one stderr note and exits 0. With no ledger the row lands in the local file with its label. `log-escape-check` passes on either build. The label is stored once `registry/review_escape.toml` gains it (LED-85); rows logged before then have none.

## Watch

None. The reading is the intake's escape-miss-reasons table.

## Back-out

Revert the commit.
