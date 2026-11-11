# Ask the user only about criteria the user or a tracker wrote

Two kinds of criteria stop needing the user's sign-off: the plan author's restatement of a ticket with no criteria
heading, and the criteria of a ticket copied from a session-written queue item. One helper in `plan_format.py` names
who owns a ticket's criteria; the plan checks, verify-prep and review_fix read it, and the prompts route on it.

## Scope

- In: `claude/.claude/scripts/lib/plan_format.py`, `claude/.claude/scripts/code/plan_check.py`,
  `claude/.claude/scripts/review/verify-prep`, `claude/.claude/scripts/review/verify_common.py`,
  `claude/.claude/scripts/review/review_fix.py`, `claude/.claude/CLAUDE.md` (`## Ticket Acceptance Criteria`),
  `claude/.claude/agents/plan-verifier.md`, `claude/.claude/skills/verify-branch/SKILL.md`,
  `claude/.claude/skills/code/SKILL.md`, `claude/.claude/skills/eng-spec/phases/1-ticket.md`, the opencode ports of
  the changed agents, and their tests in `tests/scripts/`.
- Out: `review_loop_script.py` (over 1000 lines; the packet gains no field), `verify-log` (its `signoff` field already
  takes any recorded who-and-when text), `settings.json`, any `~/agent-evals/` file.

## Phase Status

- [x] Phase 1: criteria owner helper and the scripts that read it (risk: low)
- [x] Phase 2: prompts route on the owner (risk: low)

## Phase 1: criteria owner helper and the scripts that read it

1. `plan_format.py`: constants `CRITERIA_OWNER_USER = "user"`, `CRITERIA_OWNER_PLAN = "plan"`,
   `CRITERIA_OWNER_SESSION = "session"` and `CRITERIA_OWNER_RULES` (owner → the one-line rule for who may cut or
   reword a criterion). `criteria_owner(ticket_path)` returns `{"owner", "ticket", "source", "rule"}`:
   - The ticket's first `Source:` line (markdown marks `*`, `_` and backticks stripped) whose value starts with
     `~/agent-evals/queue/` must read `~/agent-evals/queue/<slug>.md`, optionally followed by text after a space.
     The file must exist (`~` is the home folder) and its frontmatter must hold `generated:` with a JSON object whose
     `by` is a non-empty string. Any break raises PlanFormatError `ticket:line: ...` naming the queue file and the
     expected form. `by` starting with `human:` is the user's; any other author is a session → `session`.
   - Else `ticket_criteria` raising NoCriteriaHeadingError → `plan`. Any other PlanFormatError propagates.
   - Else `user`. A `Source:` line naming anything outside the queue folder (a product spec, `user, <date>`) never
     changes the owner.
   `plan_criteria_owner(plan_path)`: the owner of the one `*00-ticket.md` beside the plan; none beside it gives `user`
   with `ticket: None`. `spec_ac_failures` finds its ticket through the same lookup.
2. `ac_drift_failures` takes the owner. For `session`, a criteria-file or `## Plan Deviations` line that names the
   criterion counts when it holds a sign-off or a ruling (`ruled`, `ruling`); its failure message asks for the
   session's recorded ruling. `user` keeps the sign-off rule and message as they are.
3. `plan_check.py owner <plan>`: prints `plan_criteria_owner` as JSON, exit 0; a PlanFormatError prints the message
   and exits 1. Update the module docstring and USAGE.
4. `verify_common.py`: `branch_criteria_owner(ticket_path)`, a `raising_verify_error` wrapper. `verify-prep`
   `read_criteria` stores it as `counts["criteriaOwner"]`; `print_plan` adds
   `criteria owner: <owner> — <rule>` to the plan-verifier prompt, after the ticket lines.
5. `review_fix.py`: `plan_impact_question_lines` first tells the session to run `plan_check.py owner <plan>` when the
   run has a plan: owner `session` → rule yourself with `decide ... --by session`; owner `plan` → rule yourself only
   when the ticket's own words stay met, else ask; owner `user` or no plan → ask the user as today.
   `DECIDE_BY_NOTE`: a session ruling changes an acceptance criterion only when `plan_check.py owner` names `session`
   or `plan`.

#### Automated Verification

New tests, each failing on the current tree: in `test_plan_format.py`, a queue-sourced ticket with `generated.by`
`claude-code/x` is `session`, `human:x` is `user`, a missing queue file and a frontmatter with no `generated:` raise,
`Source: product-specs/a.md` with a criteria heading is `user`, no criteria heading is `plan`, and a session-owned
reworded criterion with a ruling line passes drift while the same line on a user-owned ticket fails; in
`test_plan_check.py`, `plan_check.py owner` prints the JSON; in `test_verify_branch_script.py`, verify-prep's prompt
names the owner; in `test_review_fix_script.py`, the plan-impact question names `plan_check.py owner`.

- [x] **Tests**: the changed test files pass - `python3 tests/parallel_tests.py test_plan_format.py test_plan_check.py test_verify_branch_script.py test_review_fix_script.py`
- [x] **Agent-run**: `bash tests/lint.sh` on the changed .py files passes

## Phase 2: prompts route on the owner

Prompt edits only. Each names the two cases and keeps today's rule for the user's and a tracker's criteria.

1. `claude/.claude/CLAUDE.md` `## Ticket Acceptance Criteria`: the sign-off rule covers criteria the user or a
   tracker wrote. `python3 ~/.claude/scripts/code/plan_check.py owner <plan>` names the owner. Owner `session` (a
   ticket copied from a session-written queue item) or `plan` (the plan author's restatement of a ticket with no
   criteria heading): the orchestrating session rules and records who and when under `## Plan Deviations`; for `plan`,
   a cut that drops what the ticket's own text asks for still goes to the user.
2. `agents/plan-verifier.md`: the `overridden` rule passes on the user's sign-off, or, when the dispatch's
   `criteria owner:` is `session` or `plan`, on a recorded session ruling (who and when); for `plan`, only while the
   ticket's own words are met. The table row and the closing `missing` line say "sign-off or ruling".
3. `skills/verify-branch/SKILL.md` line 76: the exception follows the prep's `criteria owner:` line.
4. `skills/code/SKILL.md` plan-impact rule (line 34) and Block B: at the phase end run `plan_check.py owner <plan>`;
   owner `session` or `plan` → the run's orchestrating session rules, a coder logs it under `## Plan Deviations` with
   who and the date, and the run goes on; owner `user` → `Plan changes awaiting sign-off` and STOP as today. The
   queue-item-without-ticket sentence stays.
5. `skills/eng-spec/phases/1-ticket.md` step 3: when the ticket is a file under `~/agent-evals/queue/`, the first
   line under the title of `00-ticket.md` is `Source: ~/agent-evals/queue/<slug>.md`.
6. Opencode ports of `plan-verifier.md`: same edit, or state the skip.

#### Automated Verification

- [x] **Agent-run**: `rule-anchors.sh check` passes after each edited prompt file's row is updated
- [x] **Suite**: the full suite passes - `bash tests/run.sh`

## Plan Deviations
