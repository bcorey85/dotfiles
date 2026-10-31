---
type: "Change"
change_type: "changed"
title: "verify-log writes nothing when a criterion id has no verdict row"
description: "verify-log now exits 2, names the criterion ids with no verdict row and writes no rows. Before, it logged each absent id as a `missing` gap."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T09:51:55-05:00"}
seq: 6
kind: "behavior"
components: ["script/verify-log"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/verify-log`: `ids_without_verdict_row` replaces `add_rows_for_unverdicted_ids`. If any criterion id that verify-prep saved has no verdict row, the command exits 2 with "no verdict row for <ids>: send a verdict for every criterion id, `missing` included. Nothing was written".
- A skipped criterion still cannot pass. The caller sends a row for every id, `missing` included.
- Tests: `tests/scripts/test_verify_branch_script.py`.

## Evidence

- Work incident: the first verify-log call sent rows for 9 of 23 criteria. The script logged the other 12 as `missing` gaps. A full rerun logged PASS, but no logger can supersede the 12 rows, so they stay as open plan-drift findings.

## Result

An incomplete call leaves no rows in the ledger. The skill text at `skills/verify-branch/SKILL.md` still says that an absent id is logged as `missing`, and gets a separate edit after the install.

## Watch

None. The intake counts plan-drift gaps but cannot tell a stale gap from a real one.

## Back-out

Restore `add_rows_for_unverdicted_ids` and its call in `verify-log` from git.
