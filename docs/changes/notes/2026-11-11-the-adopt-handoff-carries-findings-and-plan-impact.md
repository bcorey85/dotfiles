---
type: "Change"
change_type: "fixed"
title: "The adopt handoff carries findings and plan impact whole"
description: "decide --adopt writes each carried finding, the plan impact and the ruling into the adopt handoff whole; before, each was cut at 800 characters, so the next review read findings that stopped mid-sentence."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-11T23:53:09-06:00"}
seq: 14
kind: "fix"
components: ["skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_every_carried_line_and_the_ruling_appear_whole_in_the_adopt_handoff"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/handback.py` `carried_findings` and the plan-impact, carried-note and `Ruling:` lines in `review/review_fix.py`
call `one_line(text, None)`, which keeps the text on one line with no length cut.

## Evidence

judgment: a /review session's adopt handoff cut carried findings mid-sentence at 800 characters. The new test feeds a
finding longer than 800 characters and fails on the old code.

## Result

`bash tests/run.sh` passes on the branch.

## Watch

—

## Back-out

Restore the 800 limit in `carried_findings` and the three `review_fix.py` lines.
