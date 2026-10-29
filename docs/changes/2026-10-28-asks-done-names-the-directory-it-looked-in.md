---
type: "Change"
change_type: "fixed"
title: "asks-done names the directory it looked in"
description: "When asks-done finds no packet, the refusal names the review-fix state directory it looked in and the directory it ran from, so a call from another repo is told to run there."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-28T00:23:28-05:00"}
seq: 166
kind: "fix"
components: ["script/review-fix"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_asks_done_from_another_repo_names_the_directory_it_looked_in"
asked: ""
proof: []
unmeasured: "The refusal leaves no row in the intake logs, so no intake number reads it."
---

## Change

- `asks-done` reads its state from the repo of the current directory. Its refusal now names that state directory and
  the directory it ran from, and says to run the call in the repo that processed the packet.

## Evidence

- Read of the state lookup: the state path comes from git in the current directory, so a call from another repo
  found no packet, and the refusal said only that none was processed.
- The test runs `asks-done` from a second git repo. It fails before the change (no directory in the message) and
  passes after. This is the smaller fix: the call does not search other repos.

## Result

- The refusal tells the user where it looked, so the wrong-directory cause is visible at once.

## Watch

No watch: the refusal is not counted in any intake log.

## Back-out

Revert the message in `load_fix_state`.
