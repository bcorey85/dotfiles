---
type: "Change"
change_type: "fixed"
title: "A search ban behind a leading cd now passes when the search finds nothing"
description: "A verification line whose rg or grep command starts with cd <dir> && now counts as a search ban like a bare one, so exit 1 with no match passes."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T16:53:05-05:00"}
seq: 61
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_a_cd_then_rg_line_that_prints_nothing_passes_verify"
asked: ""
proof: []
unmeasured: "A cd-prefixed search ban is not logged as its own number."
---

## Change

`code_step_boundary` ignores a leading `cd <dir> &&` (and env assignments) when it judges whether a command is an rg or grep search, and `NEGATED_SEARCH` accepts `cd <dir> && ! rg`. The command still runs as written. `without_negation` is used by `verification_command` and the criteria dry run; `is_search_ban` reads negation from the backticked spans.

## Evidence

judgment: a session report. `cd backend && rg ... ` prints nothing failed verify on exit 1 when the code was right. Tests: the one above, a hit that fails, and `cd x && ! rg` as a ban.

## Result

Scoped and full suite results in the hand-over.

## Watch

—

## Back-out

Revert `LEADING_CD`, `without_negation` and `without_leading_cd_and_env`.

