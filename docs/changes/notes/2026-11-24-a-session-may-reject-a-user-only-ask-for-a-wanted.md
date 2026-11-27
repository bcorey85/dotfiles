---
type: "Change"
change_type: "fixed"
title: "A session may reject a user-only ask for a wanted change to an approval-only file"
description: "The review fork's resume rule lets a `--by session` asks-done call answer `rejected` on a user-only ask whose change ends with an `(edit to <path>)` note and names no criteria; every other outcome on a user-only ask stays `held`."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-24T12:56:13-06:00"}
seq: 2
kind: "fix"
components: ["shared/review-loop", "script/review-fix"]
evidence: ["tests/scripts/test_review_fix_ask_ruler.py", "tests/scripts/test_phase_asks.py"]
watches: []
test: "tests/scripts/test_review_fix_ask_ruler.py::test_a_session_correction_of_a_wanted_change_to_accepted_or_modified_is_refused"
asked: ""
proof: []
unmeasured: "No rule-meter fixture shows a session rejecting a user-only wanted-change ask: the scenarios that name user-only asks (the relay-line ones) grade the `--by user --relayed-by` flags, not a `rejected` outcome, so the rule's wording has no on/off arm. The behavior is pinned by the script tests; the fork text only tells the session the script now accepts it. The orchestrator puts this to the user before merge."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`review-fork-run.md` tells the fork that a `[user only]` ask whose change ends with an `(edit to <path>)` note and names no criteria may be answered `rejected` in a `--by session` call. The loop has already put the file back, so a reject leaves the approval-only file as the base has it. Any other outcome stays `held`. The refusal text names the user as the one who accepts a wanted-change ask, and the glossary entry for a user-only ask says the same.

## Evidence

`test_review_fix_ask_ruler.py` and `test_phase_asks.py` pin the session reject on a wanted-change ask, and the refusal of a session accept, modify, or any ruling on a revert or criteria ask.

## Result

Before, a session had to hold every user-only ask for the user, including a wanted-change ask the user would only reject; now it rejects that one itself.

## Watch

—

## Back-out

Revert the `review-fork-run.md` sentence, `session_may_reject` and its callers in `review_asks.py` and `phase_asks.py`, and the glossary wording.
