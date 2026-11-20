---
type: "Change"
change_type: "fixed"
title: "An ask the user accepted that is already in the tree is logged as accepted"
description: "asks-done takes a new outcome word, applied, for an accepted ask whose change is already in the tree. It logs as accepted and writes no finding, so the ruling log no longer shows such an ask as rejected."
generated: {"by": "process:main-session", "at": "2026-11-19T01:28:53-06:00"}
seq: 4
kind: "fix"
components: ["script/review-asks", "script/review-fix-asks", "script/review-fix"]
evidence: ["tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_an_applied_ask_logs_as_accepted_and_prints_no_fix_run"]
watches: []
test: "tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_an_applied_ask_logs_as_accepted_and_prints_no_fix_run"
asked: ""
proof: []
unmeasured: ""
---

## Change

`APPLIED` joins the outcome words in `lib/ask_outcome_words.py` and `ASK_OUTCOMES`. `log_ask_outcome` logs it as `accepted`. `finding_ask_indexes` leaves it out of the findings file, so when every outcome is applied or rejected no fix run prints. The usage and error help list it. `phase_asks.py rule` still takes only accepted and rejected.

## Evidence

tests/scripts/test_review_fix_ask_ruler.py::AskRulerTest::test_an_applied_ask_logs_as_accepted_and_prints_no_fix_run

## Result

A session with an accepted ask already in the tree answers `applied` and the ask is logged accepted, with no fix run.

## Watch

—

## Back-out

Remove `APPLIED`, `APPLIED_MEANS`, the mapping in `log_ask_outcome` and the `APPLIED` exclusion in `finding_ask_indexes`.
