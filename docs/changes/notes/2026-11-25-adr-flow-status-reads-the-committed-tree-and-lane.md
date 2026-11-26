---
type: "Change"
change_type: "fixed"
title: "adr_flow status reads the committed tree and lane-status prints no commits for a lane that never committed"
description: "adr_flow.py status reports done only from the committed tree, lane-status prints no commits for a lane that never committed, and only Markdown under docs/ is skipped when picking full-check parts."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T20:27:48-06:00"}
seq: 9
kind: "fix"
components: ["script/adr-flow", "skill/close-branch", "script/lane-status", "script/check-discovery", "script/memory-sample"]
evidence: ["tests/scripts/test_adr_flow.py", "tests/scripts/test_lane_status.py", "tests/scripts/test_check_discovery.py"]
watches: []
test: "tests/scripts/test_adr_flow.py::AdrFlowTest::test_status_with_a_task_dir_deleted_but_not_committed_is_not_finished"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`adr_flow.py status` reads the upstream tree (else HEAD) with git ls-tree: the task dir still there, or no ADR in docs/decisions, prints `adr: not finished`; a kept task dir with a committed ADR named for it prints `adr: done`. /close-branch runs the ADR status check before its recap print so the line lands in Open items. `lane-status --git` prints `no commits` for a lane whose branch tip is older than its start. `check_discovery` skips only `.md` doc paths.

## Evidence

Four new adr_flow tests fail on the old script and pass on the new one; the new lane-status and check-discovery tests pass. The full check passed on the final tree (6734 tests, 0 failed).

## Result

A branch whose task-dir deletion is not committed no longer reads as finished, and a never-committed lane no longer reads as merged.

## Watch

—

## Back-out

Revert the commit.
