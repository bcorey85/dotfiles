---
type: "Change"
change_type: "fixed"
title: "The criteria verdict reads an unset variable or refused connection with no runner summary as ENV"
description: "A failed check whose output holds an unset-variable line or a refused connection, and no runner summary, now reads ENV with an environment-failure flag in the criteria dry run and /code verification, not RED."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:52:39-06:00"}
seq: 3
kind: "fix"
components: ["script/criteria-dry-run", "shared/check-output", "shared/criteria-verdict"]
evidence: ["tests/scripts/test_criteria_verdict.py", "tests/scripts/test_check_output.py"]
watches: []
test: "tests/scripts/test_criteria_verdict.py::ItemVerdictTest.test_an_unset_variable_or_refused_connection_with_no_runner_summary_reads_env"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/check_output.py` adds `ENVIRONMENT_GAP_LINE` and `environment_gap_line(code, output)`: the first line, anchored at its start, that shows an unset variable (`X is not set`, prisma's `Environment variable not found: X`) or a refused connection (psycopg's `connection to server at ... failed: Connection refused`, `ECONNREFUSED`, prisma's `Can't reach database server`), for a failed run with no runner summary. `criteria_verdict.item_verdict` reads that as ENV with `environment failure: <line>` when `cannot_start_line` finds nothing. A run with a runner summary ran tests and stays RED.

## Evidence

Bench runs of a vitest repo with no test DB printed every vitest check RED at rc 1: the setup env guard threw `DATABASE_URL is not set` before any test ran. prisma validate printed `Environment variable not found: DATABASE_URL`. Transcripts hold the Django refused-connection form. Each is a fixture; the test fails on the old tree (RED) and passes after (ENV).

## Result

A planner reading the dry run tells a missing test DB from a missing feature.

## Watch

—

## Back-out

Remove `environment_gap_line` and its pattern from `check_output.py`, its call in `criteria_verdict.item_verdict`, and the new tests.
