---
type: "Change"
title: "A grep or rg ban holds when the search finds nothing"
description: "A plan ban written as a bare rg or grep command exits 1 when it finds nothing, which code-step read as a failed command and stopped the run. Such bans are now judged by match, like a git grep ban."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T23:40:28-05:00"}
seq: 34
kind: "fix"
components: ["script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step.py::CodeStepTest::test_an_rg_ban_with_no_match_holds"
asked: ""
proof: []
unmeasured: "The stop shows only as a halted run at verification; the intake has no count of bans written with rg."
---

## Change

- `code/code_step_boundary.py`: `run_verification_commands` sends a command that starts with rg, grep or egrep to `check_prohibition`, as it already did for `git grep`. No match (exit 1) holds the ban; a match fails it.

- `verification_command` reads a span written `! rg ...` (or grep, egrep, git grep) as the bare search, so the negated form runs, is judged as a ban, and passes `plan check`. Tests: `test_a_negated_rg_ban_runs_and_holds_on_no_match`, `test_a_negated_rg_ban_passes_plan_check`.

## Evidence

judgment: a peer's plan wrote a ban as an rg command; the validator accepted it, and /code stopped at verification because rg exits 1 on no match.

## Result

Installed in the fix/eng-spec-ac-and-scope branch; takes effect when merged.

## Watch

None.

## Back-out

Remove `SEARCH_BAN` and its condition in `run_verification_commands`.
