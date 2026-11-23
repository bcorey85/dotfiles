# Lane brief: review-owner-nov22

Source: ~/agent-evals/queue/review-fix-pass-lets-an-owner-line-edit-in-the.md
Source: ~/agent-evals/queue/a-lane-forked-with-a-pasted-brief-writes-no-queue.md

## Brief (verbatim)

# Lane: review-owner-nov22 (branch fix/review-owner-nov22)

Read `/tmp/claude-1000/-home-brandon-agent-evals/a0b58526-6a4a-4e0a-af5b-8d0985572fda/scratchpad/lane-common.md` first. It holds the lane rules; this file holds the work. The orchestrating session is agent-evals-c3 (its ListAgents name).

## Items (queued on origin/bench-base of ~/agent-evals; read each with `git -C ~/agent-evals show origin/bench-base:queue/<slug>.md`)

1. `review-fix-pass-lets-an-owner-line-edit-in-the`: `claude/.claude/scripts/review/review_loop_ruled.py` keeps a /code review fix-pass edit to `claude/.claude/scripts/CLAUDE.md` whose only changed lines are owner lines (a pointer to the module that owns a fact) when the run's decision log records a session ruling for it, and still reverts every other CLAUDE.md edit. Test under `tests/scripts/` that fails before and passes after, for both the kept owner line and a reverted non-owner edit. Change file kind `fix`.
2. `a-lane-forked-with-a-pasted-brief-writes-no-queue`: eng-spec phase 1 (`claude/.claude/skills/eng-spec/phases/1-ticket.md`) writes a `Source: ~/agent-evals/queue/<slug>.md` line only when the ticket is a queue file, so a lane forked with a pasted brief that restates a queue item reads criteria owner `user`. Make phase 1 write Source when the brief names a queue item path. The skill-edit route needs rule-meter arms; a script route (if `plan_check.py owner` or a phase-1 helper can read the brief's queue path itself) does not. Pick the route that needs no new prose rule where one exists, and say which in 03-decisions.md. Done when a replay of a pasted-brief lane prints owner `session`.

## Rulings already made (agent-evals-c3, 2026-11-22; record each in the plan's 03-decisions.md)

- Owners lines: none in any CLAUDE.md. A module owner goes in its module docstring.
- Scripts live under `claude/.claude/scripts/`, tests under `tests/scripts/` with paths from `tests/scripts/toolkit_paths.py`. You edit them on this branch in this worktree; the write-edit gate blocks the live `~/.claude/scripts`, never the worktree.
- Do not touch `claude/.claude/skills/code/**`, `claude/.claude/scripts/code/**` (code-skill lane owns them), `claude/.claude/CLAUDE.md` or `orchestration.md` (toolkit-rules lane).
- Every new or reworded prose rule gets rule-meter on and off arms before commit. New scenarios go in `~/agent-evals/bin/rule_meter_scenarios.json`; detector bodies in `bin/rule_meter_checks/` with tests; one registration-only line in `bin/rule_meter.py` is allowed. Run `git -C ~/agent-evals status --short bin/` right before each edit there and stop (message me) if a rule_meter file is dirty. Set each new scenario's `toolkit_root` to `/home/brandon/dotfiles/claude/.claude` before your final commit. Budget: 24 runs per item.
- Dotfiles history on GitHub was rewritten on 2026-11-22; your branch starts from the new master, so a plain push works. Never use --force or --force-with-lease.
- When a /code phase ends, commit it (plan files included) and go straight on to the next phase with /clear then /code. Do not wait between phases.

## Order

Triage, claim, /eng-spec one plan, /code, /verify-branch, suite under `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh` with `run_in_background`, then commit and push the branch and send the final report to agent-evals-c3.

## Queue item 1 (verbatim): review-fix-pass-lets-an-owner-line-edit-in-the

---
type: "QueueItem"
title: "Review fix pass lets an owner-line edit in the scripts CLAUDE.md stand when the orchestrating session ruled it"
description: "A /code fix pass that adds or updates a pointer line in the scripts CLAUDE.md keeps it instead of reverting it and asking the user, who has said not to be asked about that file."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T21:00:13-06:00"}
kind: "chore"
status: "running"
rank: 1910
blocked_by: []
source: "claude/.claude/scripts/review/review_loop_ruled.py"
components: ["script/review-loop-ruled", "shared/review-loop"]
not_dup: "The 2026-11-19 change made the loop revert approval-only edits and report them; this item adds the one exemption the global CLAUDE.md now grants, an owner line in scripts/CLAUDE.md under a session ruling."
---

## Context

The toolkit-rules lane (2026-11-22) added a sentence to the global CLAUDE.md go-ahead line: an owner line in `claude/.claude/scripts/CLAUDE.md` is covered by the orchestrating session's ruling. Its Phase 4 close pass found that `review_loop_ruled.py` still reverts every CLAUDE.md edit a /code review fix pass makes and files a user-only ask, so the sentence reaches direct lane edits only. The lane narrowed its criterion to direct edits and recorded the gap. The user, 2026-11-22: "i need you to stop askingme about modifying scripts/claude.md".

## Done when

- `review_loop_ruled.py` keeps an edit to `claude/.claude/scripts/CLAUDE.md` whose only changed lines are owner lines (a pointer to the module that owns a fact) when the run's decision log records a session ruling for it, and still reverts every other CLAUDE.md edit.
- A test under `tests/scripts/` fails before the change and passes after it, for both the kept owner line and the reverted non-owner edit.
- Change file in `~/dotfiles/docs/changes/` with kind fix naming that test.

## Queue item 2 (verbatim): a-lane-forked-with-a-pasted-brief-writes-no-queue

---
type: "QueueItem"
title: "A lane forked with a pasted brief writes no queue Source line, so its criteria read as the user's"
description: "Lanes stop asking the user to sign off criteria the session wrote, when the lane started from a pasted brief."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-22T17:24:45-06:00"}
kind: "method"
status: "running"
rank: 1903
blocked_by: []
source: "claude/.claude/skills/eng-spec/phases/1-ticket.md"
components: ["skill/eng-spec", "skill/herdr"]
---

## Context
2026-11-22: plan_check owner now reads both spellings of a queue Source line. eng-spec phase 1 writes Source only when the ticket is a queue file, so a lane forked with a pasted brief that restates a queue item still reads owner user.

## Done when
- The fork brief names the queue item path so phase 1 takes the file branch, or phase 1 writes Source for a brief that names one; a skill edit runs rule-meter arms.
- A replay of a pasted-brief lane prints owner session.

## Comments

none
