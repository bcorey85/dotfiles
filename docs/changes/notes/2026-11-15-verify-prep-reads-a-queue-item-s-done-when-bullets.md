---
type: "Change"
change_type: "fixed"
title: "verify-prep reads a queue item's Done when bullets as the ticket criteria"
description: "A queue item now works as the ticket of a branch check: its `## Done when` bullets are the criteria, and the owner line names a session for an item a session wrote. No hand copy of the criteria is needed."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-15T10:53:17-06:00"}
seq: 3
kind: "fix"
components: ["script/verify-prep", "script/plan-format", "script/script-utils", "script/verify-log", "script/verify-common", "skill/verify-branch", "agent/plan-verifier", "rule/global-claude-md"]
evidence: ["verify-prep-refuses-a-queue-item-as-the-ticket"]
watches: []
test: "tests/scripts/test_verify_prep_queue_ticket.py::QueueTicketTest::test_a_queue_item_exits_0_with_its_done_when_bullets_and_a_session_owner"
asked: ""
proof: []
unmeasured: "Three prompt lines (verify-branch SKILL.md line 59, plan-verifier.md line 38, global CLAUDE.md line 30) were reworded to match the script. No rule-tester run was made: the wording names a heading and a ticket form the script already reads, and asks for no new behavior."
---

## Change

`lib/plan_format.py` owns the list of criteria headings. `Done when` joins `Acceptance` and `Requirements` there, in
any case, so every reader takes it.

`criteria_owner` now checks first whether the ticket file is itself a queue item (frontmatter `type` of
`QueueItem`). Its owner comes from the item's own `generated.by`: `human:` gives `user`, any other author gives
`session`. A script author (`process:`) gives `session`, because a script is not the user. A queue item with a
missing or broken `generated` key stops with the file, the line and the expected form: it never prints `user` for
criteria a session wrote. The frontmatter reader itself folds CRLF line ends, so a CRLF queue item and a CRLF queue
file behind a `Source:` line are both read.

`## Done when` in a file that is not a queue item now gives criteria too, and this changes its owner. A ticket with
only `## Done when` and no queue `Source:` line used to stop with no criteria heading. Its owner was `plan`, and the
plan drift check (`spec_ac_failures`, `ac_drift_failures`) returned nothing for it. Now its owner is `user`, the
drift check runs on it, and prose mixed with bullets in it fails the plan check. No `00-ticket.md` under
`~/dev/*/docs/plans` has a `Done when` heading, so no existing plan on this machine changes. When a file holds both
`## Acceptance Criteria` and `## Done when`, the old pick rule holds: the shallowest heading with items wins, then the first in the file. A
heading that starts with `Done when` but has more text (`## Done when (narrowed by ruling)`) stops loudly, like a
misspelled `Acceptance` heading.

A `Done when` section that holds prose and no list item is read as one criterion per paragraph: 448 real queue
items write it that way. A `Done when` section that mixes prose with list items stops with the file and line, so a
ruling written beside the bullets is never dropped or turned into a criterion. A fenced block, a sub-heading or
a `>` blockquote line in a prose section stops too. Prose under `Acceptance` or `Requirements` still stops, as before.

The error messages that list the headings now name all three. Docstrings in `review/verify_common.py` and
`review/verify-log` were reworded to match.

## Evidence

One sighting, 2026-11-15: a lane ran the branch check on a branch whose only ticket was a queue item. Prep exited 2.
The session copied the bullets by hand under `## Acceptance Criteria`, and prep then named the owner `user` for an
item a session wrote.

## Result

30 new tests in `tests/scripts/test_verify_prep_queue_ticket.py`, 3 in `CriteriaOwnerTest` in
`tests/scripts/test_plan_format.py` and 5 in `tests/scripts/test_script_utils.py`. A real run on the queue item that asked for this change printed 3 ticket criteria
and owner `session`, exit 0.

A sweep of every real queue item through the reader and the owner: parsed 1,030 of 1,096 (582 with the bullet
reading alone). The 66 left are bad inputs that stop with a reason: 61 with no criteria heading, 4 that mix prose and
bullets, 1 empty section.

`skills/verify-branch/SKILL.md` line 59 and `agents/plan-verifier.md` line 38 said "no Acceptance or Requirements
heading". Both now say "no Acceptance, Requirements or Done when heading", to match the scripts. The plan-verifier
row in `docs/rule-anchors.md` carries the new hash.

The `CLAUDE.md` `session` owner definition now reads "a session-written queue item, or a ticket copied from one".
A review coder made that edit without a go-ahead. The user read the before and after text and ruled "keep" on
2026-11-15; session agent-evals-7d relayed the ruling.
Its `## Ticket Acceptance Criteria` anchor row carries the new hash and links this note.

## Watch

None. No intake number reads a refused queue ticket.

## Back-out

Revert the commit. A queue item as the ticket then exits 2 again.
