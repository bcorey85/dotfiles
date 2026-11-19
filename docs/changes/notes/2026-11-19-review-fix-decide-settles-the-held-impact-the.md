---
type: "Change"
change_type: "fixed"
title: "review-fix decide settles the held impact the commit gate blocks on"
description: "`review_fix.py decide` falls back to the latest hand-back's held plan impacts when the repo's packet state is finished, so it settles the same impact the commit gate blocks on."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T02:32:03-06:00"}
seq: 1
kind: "fix"
components: ["script/review-fix", "script/review-commit-gate", "script/handback"]
evidence: ["commit-gate-and-review-fix-decide-disagree-on-held"]
watches: []
test: "tests/scripts/test_review_fix_script.py::ReviewFixScriptTest::test_decide_settles_the_held_impact_the_gate_blocks_on_past_a_stale_finished_state"
asked: ""
proof: []
unmeasured: ""
---

## Change

`command_decide` reads the packet state only when it waits on a plan impact that is the one the latest hand-back holds,
or when the hand-back holds none. Otherwise it reads the held impacts of the latest hand-back for the repo, the same
rows the commit gate reads, and settles those. The `--by session` command lines print `--plan <the plan path>` as
required, the `--by user` lines say "when the handoff names one", and the usage line, the question line and the gate
denial say "required with --by session, else when the handoff names one".

## Evidence

The review-fix state is per repo and never deleted. A finished state from an earlier run made `decide` answer "no
plan-impact is waiting" while the gate still blocked on a held impact.

## Result

New tests in `tests/scripts/test_review_fix_script.py` and `tests/scripts/test_handback.py`.

## Watch

None.

## Back-out

Revert the commit.
