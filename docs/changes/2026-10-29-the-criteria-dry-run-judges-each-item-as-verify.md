---
type: "Change"
change_type: "fixed"
title: "The criteria dry run judges each item as verify does"
description: "The plan-criteria dry run read only a negated search (`! rg`, `! grep`, `! git grep`) as a ban, while /code's verification also reads a plain rg, grep or git grep line as a ban unless its text says presence, lets ban wording win, and judges a pipe form by its output. A plan item could read GREEN in the dry run and fail at verify. Both now take their verdict from one function in lib/criteria_verdict.py."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-29T07:20:59-05:00"}
seq: 238
kind: "fix"
components: ["script/code-step", "script/criteria-dry-run"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_criteria_dry_run.py::SearchItemVerdictTest::test_a_plain_search_with_ban_wording_that_hits_is_red"
asked: ""
proof: []
unmeasured: "The change makes a planning-time check agree with the verify step; no intake number reads it."
---

## Change

- New `lib/criteria_verdict.py` holds the rule that judges one Automated Verification item after its command ran: `item_verdict(command, line, code, output)` returns outcome (GREEN, RED or BROKEN), the exit-style code, the output with any note, the hit count of a search ban, and the zero-test flag text. `SEARCH_COMMAND`, `BAN_WORDING`, `PRESENCE_WORDING`, `SEARCH_BAN_NOTE`, the no-test constants, `without_negation`, `without_leading_cd_and_env` and `is_search_ban` moved there from `code_step_boundary`, along with the pipe rule and the exit 1/0 mapping that `check_prohibition` held.
- `code_step_boundary.run_verification_commands` calls `item_verdict`. The telemetry call is kept in `code_step_boundary` as `log_prohibition_scan`, run for a search ban. Verify's verdicts, notes and telemetry rows do not change.
- `criteria_dry_run` calls `item_verdict`; its own `is_ban` and `verdict_for` are gone. A plain search with ban wording that hits now reads RED, and a pipe search that prints a count above 0 reads RED, as at verify.

## Evidence

- A plan item such as `grep foo src.txt` with the text "finds no match" read GREEN in the dry run when the file held `foo`, and failed at verify.
- The new dry-run tests fail before the change (the ban-wording hit and the pipe count read GREEN); the unit test for `item_verdict` fails on a missing module.

## Result

- The new tests pass. The dry-run, code-step and path tests pass, and ruff is clean on the changed files.

## Watch

—

## Back-out

Revert the commit. The dry run then reads only a negated search (`! rg`, `! grep`, `! git grep`) as a ban again, and the rule sits in `code_step_boundary`.
