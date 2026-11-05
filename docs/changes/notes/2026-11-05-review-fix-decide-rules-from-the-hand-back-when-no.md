---
type: "Change"
change_type: "fixed"
title: "review_fix decide rules from the hand-back when no packet ran"
description: "With no review_fix state file, decide reads the held plan impacts from the session's hand-back: keep records the ruling and clears the commit gate, adopt logs the deviation and stops for the caller's own loop."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-05T17:00:08-06:00"}
seq: 11
kind: "fix"
components: ["skill/review", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_decide_keep_with_no_state_rules_on_the_held_impact_in_the_hand_back"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review_fix.py decide` falls back to `handback.unruled_plan_impacts(handback_store.latest_for_repo(...))` when no fix state file exists, the read the commit gate makes. `decide keep` writes the deviation and records the ruling (`ACTION: done`). `decide adopt` writes the deviation and stops with `/code resume`, since no launch state exists to re-dispatch from. No hand-back keeps the "no packet was processed" error; an unreadable state file keeps its own error. `ruling_logged_line` replaces three copies of the "Recorded in" line. The commit gate's deny text in `review_commit_gate.py` names the no-state path.

## Evidence

judgment: in a /code run the fork reads the packet through `code_wait.py`, so `packet` never runs. After a plan-impact hold the commit gate named `decide`, and `decide` failed until the caller ran `packet` by hand. The new tests fail on f22db22c and pass after.

## Result

Full check 3206 tests, 0 failed.

## Watch

—

## Back-out

Revert the no-state branch and `ruling_logged_line` in `review_fix.py`, the gate text in `review_commit_gate.py`, and the tests.
