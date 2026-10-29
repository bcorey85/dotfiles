---
type: "Change"
change_type: "fixed"
title: "code-step start takes a phase named after the plan, and the refactor skill shows a log input that parses"
description: "`code_step.py start <plan> Phase <id>` and `start <plan> <id>` start that phase where they used to stop on 'text after the plan', and the /refactor skill shows a JSON log input that `refactor_flow.py log` accepts, so two first calls that callers got wrong daily now pass."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T21:10:00-05:00"}
seq: 20
kind: "fix"
components: ["script/code-step", "skill/refactor"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_code_step_resume.py::ResumeTest::test_start_with_a_plan_then_phase_and_its_id_starts_that_phase"
asked: ""
proof: []
unmeasured: ""
---

## Change

`code_step.py`: `start` reads `<plan> Phase <id>` and `<plan> <id>` at the end of its words as `<plan> --phase <id>`,
spread or in one quoted argument. The plan word must be a `.md` file and the id must match the plan grammar's phase
id. Any other text after a plan is still refused as before.

`skills/refactor/SKILL.md`: `guards` is described as an object `{"<class>": "<guard>"}`, `flagged` as one line
(`none` when nothing is flagged), and a JSON example of the `log` input follows the field list.

New tests: two in `test_code_step_resume.py` (the spread `Phase 2` form and the quoted bare `2` form start Phase 2),
one in `test_refactor_flow.py` (the skill's JSON example runs through `log --mode branch` with exit 0).

## Evidence

Census of agent-ledger sessions, 2026-10-19 to 2026-10-24 (queue item
`cut-first-try-failures-of-code-step-start-and`): 12 `start <plan> Phase 3` calls stopped on "text after the plan",
and 20 `refactor_flow.py log` calls were refused on input shape (`guards` must be an object, `flagged` must be a
non-empty string). Each caller recovered with one more call.

The three new tests fail on the old code (a stop with "the text after the plan or phase is not task text"; no JSON
example in the skill) and pass on the new code.

Not fixed here: 25 zsh parse errors on unquoted task text (`no matches found`, `unmatched '`). The /code skill still
passes the task text unquoted, and a single quoted argument that holds a plan and a modifier is refused as task text,
so quoting needs its own change.

## Result

`bash tests/run.sh`: 2118 tests, 2 failed. Both are `RealPlansTest` cases on the agent-ledger LED-46 plan's level-5
heading, which fail on master too. `ruff check` passes.

## Watch

None.

## Back-out

Revert the commit.
