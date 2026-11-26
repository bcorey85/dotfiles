# plan_check owner reads a queue item path named anywhere in a pasted brief

A lane started from a pasted brief copies the brief into `00-ticket.md`. The brief names the queue item as a path in
free text (`Read ~/agent-evals/queue/<slug>.md`), not as a `Source:` line, so `plan_check.py owner` reads owner `user`
and the lane puts plan cuts to the user. Fix it in code, not in the eng-spec prompt (a prompt edit needs rule-meter
runs).

## Scope

- In: `claude/.claude/scripts/lib/plan_format.py` (`criteria_owner` and a reader for queue paths in ticket text),
  `tests/scripts/test_plan_check.py`, one change note in `docs/changes/`.
- Out: `claude/.claude/skills/eng-spec/phases/1-ticket.md` and every other prompt file.

## Phase Status

- [ ] Phase 1: owner reads an existing queue item path named anywhere in the ticket (risk: low)

## Phase 1: owner reads an existing queue item path named anywhere in the ticket

When the ticket is not a queue item and has no queue `Source:` line, `criteria_owner` looks for queue item paths
anywhere in its text: `~/agent-evals/queue/<slug>.md` or the same path spelled with the home folder. It keeps only
paths whose file exists, and takes the owner from those items the way it does for `Source:` lines: `user` when any
named item has a `human:` author, else `session`, with `source` the first path. A path whose file does not exist is
ignored, and a ticket that names no existing queue path keeps today's owner (`plan` or `user`). A named item with no
readable `generated.by` raises, as a `Source:` line's item does.

**File**: `claude/.claude/scripts/lib/plan_format.py`
**Test**: `tests/scripts/test_plan_check.py`

### Success Criteria

- A ticket whose text says `Read ~/agent-evals/queue/<slug>.md.` for a session-written item prints owner `session`
  with that source; the home-folder spelling does too.
- A ticket that names a queue path whose file does not exist, or names no queue path, keeps owner `user`.
- A ticket naming a `human:` item in free text prints owner `user`.
- `bash tests/run.sh` passes.
