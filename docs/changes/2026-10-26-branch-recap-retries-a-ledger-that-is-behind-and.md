---
type: "Change"
title: "branch recap retries a ledger that is behind and never records it as empty"
description: "branch-recap's deferred-findings read retries ledger exit 75 for up to 60 seconds, then records the queue as not read (cache busy or behind), never as none."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:56:21-05:00"}
seq: 87
kind: "fix"
components: ["skill/branch-recap"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_guidance_rules.py::GuidanceRulesTest::test_branch_recap_retries_a_ledger_behind_and_never_records_an_unread_queue_as_none"
asked: ""
proof: []
unmeasured: ""
---

## Change

- Step 2 runs `ledger yield --deferred` in a counted loop: on exit 75 it sleeps 5 seconds and tries again, 12 times
  at most. Still 75 → it prints `deferred: not read (cache busy or behind)`. Any other non-zero exit prints
  `deferred: not read (ledger exit <code>)`.
- The rule and the recap's Deferred findings section name the unread outcomes beside `none` and `not tracked`.

## Evidence

- A recap hit exit 75 twice a few seconds apart and had to invent its own "not read" line. The skill named only
  rows or "ledger not installed", so an unread queue could be recorded as empty, which turns deferral into deletion.
- The test pins the loop and the mentions; it fails on the base tree.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
