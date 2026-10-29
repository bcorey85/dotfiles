---
type: "Change"
change_type: "fixed"
title: "code_step start lets the same session replace its stopped run and prints a restart form it accepts"
description: "A run that stopped on the coder's report no longer blocks the same session's next `start`, and the open-run refusal prints a `--restart` command the script accepts."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:50:59-05:00"}
seq: 77
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_start_input.py::StartInputTest::test_a_run_stopped_on_the_coder_report_is_replaced_by_the_same_session_without_restart"
asked: ""
proof: []
unmeasured: "Open-run refusals are not logged; no intake number reads them."
---

## Change

`start` replaces a run stopped on the coder's report when the session that starts again is the run's pinned session.
Another session is still refused. For plain task text the refusal now prints `start --restart --task '<text>'`, where
it printed a positional form the script refused as task text over open phases.

## Evidence

A run stopped for design questions; the same orchestrator answered them and invoked /code again, and the start waited on
the user for its own earlier run. A second report showed the printed restart hint refused when run.

## Result

The same session starts over without a user round trip; the printed restart command runs.

## Watch

None.

## Back-out

Revert the commit.
