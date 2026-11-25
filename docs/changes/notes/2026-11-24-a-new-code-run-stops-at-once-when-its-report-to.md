---
type: "Change"
change_type: "changed"
title: "A new /code run stops at once when its report-to session is not live"
description: "phase_start --new-run reads the lane file and stops with the live session names when the lane's report-to session is not live."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T20:46:33-06:00"}
seq: 7
kind: "fix"
components: ["script/phase-start"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_phase_start.py::PhaseStartTest::test_a_new_run_whose_report_to_session_is_not_live_stops_and_lists_the_live_names"
asked: ""
proof: []
unmeasured: "No intake number counts report-to names that were missing at hand-back."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`phase_start.py --new-run` looks up the lane file of the worktree it runs in. When the lane's `reports_to` session is not a live name in the session registry, it exits non-zero before writing anything and lists the live names, so a fork whose brief names a missing report-to session stops in its first minute and not at hand-back. No lane file, an empty `reports_to` or an unreadable lane file passes (the last with a stderr note). Only `--new-run` checks.

## Evidence

Three tests: a missing name stops, lists both names and leaves no start record; a live name goes on; no lane file or an empty `reports_to` goes on. The first failed before the change (exit 0).

## Result

The phase_start tests pass (47), lint passes.

## Watch

None.

## Back-out

Revert `phase_start.py` and its tests.

