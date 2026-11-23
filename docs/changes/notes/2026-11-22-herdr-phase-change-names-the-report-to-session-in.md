---
type: "Change"
change_type: "changed"
title: "herdr-phase-change names the report-to session in the prompt it sends"
description: "Every prompt herdr-phase-change sends now ends with the name of the session that sent it, and nothing is sent when that session cannot be named."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T18:56:02-06:00"}
seq: 29
kind: "fix"
components: ["script/herdr-phase-change"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_herdr_phase_change.py::HerdrPhaseChangeTest::test_no_resolvable_sending_session_sends_nothing_and_says_why"
asked: ""
proof: []
unmeasured: "No count shows how often a cleared worker lacked the name of the session to report to."
---

## Change

`herdr-phase-change` asks `session_pane.py sender` for the name of the session that runs it. It adds ` [report to session <name>]` to the end of every prompt it sends, slash commands included, so a cleared worker's first prompt names the session it reports to. The lane file's brief holds the same text.

When the sender cannot be named, the script exits 1 before it clears the pane, sends nothing, and prints the reason, or says that `session_pane.py` printed no JSON. Errors from `session_pane.py` now reach stderr.

## Evidence

The herdr-phase-change tests run the script against a stub herdr API. Every sent-prompt assertion carries the suffix. One test has a sender that cannot be named and checks exit 1, the reason on stderr and no prompt. Another has a sender lookup that prints nothing.

## Result

The herdr-phase-change tests pass (17), lint passes, and the full check passed in the review loop.

## Watch

A `/code` run that treats the suffix as a run note, until the code skill strips it.

## Back-out

Revert `herdr-phase-change` and its tests to the version that sends the prompt unchanged.
