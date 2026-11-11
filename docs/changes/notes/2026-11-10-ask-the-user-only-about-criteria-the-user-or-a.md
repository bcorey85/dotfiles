---
type: "Change"
change_type: "changed"
title: "Ask the user only about criteria the user or a tracker wrote"
description: "A session rules on cutting or rewording criteria a session wrote (a ticket copied from a session-written queue item) or the plan drafted (a ticket with no criteria heading); only the user's and a tracker's criteria still need the user's sign-off."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T22:23:56-06:00"}
seq: 7
kind: "user-rule"
components: ["rule/global-claude-md", "agent/plan-verifier", "skill/code", "skill/verify-branch", "skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-11-10: on every lane stopping to ask sign-off for session-written criteria: fix it now"
proof: []
unmeasured: ""
---

## Change

- `lib/plan_format.py` `criteria_owner(ticket_path)` names who wrote a ticket's criteria: `session` when a `Source: ~/agent-evals/queue/<slug>.md` line names an existing queue item whose `generated.by` is not a `human:` author, `plan` when the ticket has no `## Acceptance*` or `## Requirements*` heading, `user` otherwise. A queue `Source:` line naming a missing file or a file with no readable `generated.by` fails loudly.
- `plan_check.py owner <plan>` prints the owner as JSON. The drift check accepts a recorded session ruling for a session-owned ticket. verify-prep passes `criteria owner:` to the plan-verifier, and review_fix's plan-impact question routes on the owner.
- `CLAUDE.md` `## Ticket Acceptance Criteria`, plan-verifier's `overridden` rule, `/verify-branch`, `/code`'s plan-impact rule and eng-spec's ticket phase (which writes the `Source:` line for a queue item) follow the owner. The opencode plan-verifier port carries no sign-off rule, so it is unchanged.

## Evidence

- On 2026-11-10 every open lane stopped to ask the user to sign off on cutting or rewording criteria a session had written. The user could not follow the questions, and the auto-mode classifier refused each relayed ruling, so each cost a manual `!` line.
- The queue holds 1013 items; sessions sign `generated.by` under many prefixes (`claude-code/`, `claude-opus-5-5/`, `process:`, `claude/`), and only `human:` prefixes are the user's.

## Result

- As a user rule, no rule-meter fixture shows it: the behavior is a cross-session sign-off route. The script side is pinned by tests in `test_plan_format.py`, `test_plan_check.py`, `test_verify_branch_script.py` and `test_review_fix_script.py`.

## Watch

—

## Back-out

Revert the commit. Every criterion change again needs the user's sign-off.
