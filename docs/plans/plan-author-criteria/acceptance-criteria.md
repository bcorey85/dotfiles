# Acceptance Criteria — plan-author-criteria

> Written before implementation.

- **AC1** — `plan_format.criteria_owner(ticket_path)` returns `session` for a ticket whose `Source:` line names an existing `~/agent-evals/queue/<slug>.md` whose frontmatter `generated.by` is not a `human:` author, `plan` for a ticket with no `## Acceptance*` or `## Requirements*` heading, and `user` otherwise; a `Source:` line naming a missing queue file, or a queue file with no readable `generated.by`, raises PlanFormatError naming the file.
- **AC2** — `plan_check.py owner <plan>` prints the owner of the ticket beside the plan as JSON (`owner`, `ticket`, `source`, `rule`); no ticket beside the plan gives `user`.
- **AC3** — `plan check` on a spec whose session-written ticket's criterion is reworded passes when a `## Plan Deviations` line records a ruling naming that criterion; a user-owned ticket still needs a sign-off line, and its failure message is unchanged.
- **AC4** — verify-prep's plan-verifier prompt carries a `criteria owner:` line with the owner and its rule.
- **AC5** — review_fix's plan-impact question tells the session to run `plan_check.py owner` and rule itself with `--by session` when the owner is `session` or `plan` (for `plan`, only while the ticket's own words stay met), and to ask the user otherwise.
- **AC6** — The `## Ticket Acceptance Criteria` rule in `claude/.claude/CLAUDE.md`, the plan-verifier `overridden` rule, `/verify-branch`, `/code`'s plan-impact rule and Block B, and eng-spec's ticket phase (which writes the `Source:` line for a queue item) state the two cases; the opencode ports match.
- **AC7** — `bash tests/run.sh` passes.
- **AC8** — Plan-drafted criteria: when `00-ticket.md` has no `## Acceptance*` or `## Requirements*` heading, the `ACn` lines of `acceptance-criteria.md` are the plan author's restatement. A cut or reword of one passes on a ruling recorded under `## Plan Deviations` with who and when (the orchestrating session counts) while the ticket's own words are still met. A cut that drops something the ticket's own text asks for still needs the user.
- **AC9** — Session-written tickets: when `00-ticket.md` has a `Source: ~/agent-evals/queue/<slug>.md` line and that file exists with frontmatter `generated.by` naming a session, the orchestrating session may cut or reword the ticket's criteria with a recorded ruling (who and when). Both conditions are checked in code; the line alone is never trusted.
- **AC10** — A tracker ticket or the user's own words keeps today's rule: only the user's explicit sign-off changes a criterion.
- **AC11** — The source check is one helper in `plan_format.py`, shared by verify, review_fix and the plan checks.
