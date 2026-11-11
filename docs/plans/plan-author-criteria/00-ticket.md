# Ask the user only about criteria the user or a tracker wrote

Source: user, 2026-11-10

> fix it now

Every lane stopped today to ask the user to sign off on cutting or rewording acceptance criteria that a session wrote.
The user could not follow the questions, and the auto-mode classifier refused every relayed ruling, so each one cost
the user a manual `!` line.

## Acceptance Criteria

- Plan-drafted criteria: when `00-ticket.md` has no `## Acceptance*` or `## Requirements*` heading, the `ACn` lines of `acceptance-criteria.md` are the plan author's restatement. A cut or reword of one passes on a ruling recorded under `## Plan Deviations` with who and when (the orchestrating session counts) while the ticket's own words are still met. A cut that drops something the ticket's own text asks for still needs the user.
- Session-written tickets: when `00-ticket.md` has a `Source: ~/agent-evals/queue/<slug>.md` line and that file exists with frontmatter `generated.by` naming a session, the orchestrating session may cut or reword the ticket's criteria with a recorded ruling (who and when). Both conditions are checked in code; the line alone is never trusted.
- A tracker ticket or the user's own words keeps today's rule: only the user's explicit sign-off changes a criterion.
- The source check is one helper in `plan_format.py`, shared by verify, review_fix and the plan checks.
