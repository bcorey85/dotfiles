---
name: hillclimb
description: Reads one session and queues the Claude toolkit fixes (skills, agents, rules, hooks, gates, scripts, global CLAUDE.md) that would have made it go better. Fixes to the project repo the session worked in are listed in the report, never queued.
disable-model-invocation: true
allowed-tools: [Bash, Read, Glob, Grep, Skill, mcp__ledger__search, mcp__ledger__session]
---

# Hillclimb — fixes to the environment from one session

Every change to a skill, agent or log is the user's call: queue the candidates you judge worth a fix and log each one you queued or skipped.

Read one session and propose changes to the Claude toolkit that would have made it go better.

The toolkit is `~/dotfiles/claude/.claude/` (skills, agents, rules, hooks, `settings.json`, gates, scripts, the global CLAUDE.md) and `~/agent-evals/`. The queue is for toolkit fixes only. A candidate whose fix lands only in the project repo the session worked in (its code, tests, CI, project CLAUDE.md, project `.claude/skills/`) goes in the report's `Project repo` list. Never run `build_queue.py` for it.

## Input

$ARGUMENTS

- Load the `toolkit-writing` skill first. Its terms (no-op, duplicate, cache, sprawl, weak pointer, sediment, dense rule) judge every steering file you read.
- No argument: the current session.
- A session id, or words that find one: `mcp__ledger__search` for the session, then read it in order with `mcp__ledger__session` (pages of 50 blocks, `from_index` to go on).
- Read every block of the session before you list a candidate.

## Find the moments

List each moment where the session lost time, tokens or correctness:

- many calls to find one file or fact
- a mistake a tool could have caught, found late or by the user
- a reviewer pass that missed a judgment-call mistake
- a hook block, a retry, a failed approach
- a tool call that cost far more than it returned
- a fact the agent could not reach (a log, a service, a machine)
- a no-op: a rule line the session read that changed nothing it did
- a stage, lane or agent pass that ran and changed nothing (a review with no fix, a lane whose change was dropped)
- a step in the wrong owner: the main session doing work a subagent, lane or script could own, or a hop that only relays
- a model or context mismatch: Opus where Sonnet would do, a poll or subagent that re-reads context to do nothing
- a stop for the user, or a stop for a ruling the session could make itself

Each moment carries its block index or turn and a short quote. A cost repeated over many turns is one moment that lists every turn. Drop any candidate you cannot tie to a moment.

## Read the environment

Before you place a fix, read what the toolkit already has:

- Its checks: `settings.json` hooks, `scripts/gates/`, toolkit tests. A check that exists but did not run, or runs and is broken, is the finding.
- The toolkit steering files the session loaded: the global CLAUDE.md, `rules/*.md`, the toolkit skills and agents that ran. Count their lines. In any file over 150 lines, list the lines a check or a reviewer rule could hold, and the no-ops.

## Place each fix

Classify each mistake first. A mechanical one (a fixed pattern, a banned API, a command form, an import shape, a file location) gets a check. Only a judgment call gets prose.

| Moment | Fix |
| --- | --- |
| Slow lookup | A pointer in a toolkit file the agent already reads (global CLAUDE.md, a rule, the toolkit skill that ran) |
| Mechanical mistake (wrong API, path, shape, command form) | A check: gate under `scripts/gates/`, test under `tests/`, lint rule |
| Judgment-call miss | A rule for the reviewer (`rules/*.md`, the reviewer agent), never the implementer or CLAUDE.md |
| A check exists but did not run | Wire it (`settings.json` hook, `tests/run.sh`, CI); never build a second one |
| Expensive tool call | Streamline or replace the tool or script |
| No-op rule line | A deletion candidate, to test with `~/agent-evals/bin/rule_meter.py` before cutting |
| Fact out of reach | Widen access (tee a log to a file, a read-only command) |
| Large steering file | Move its lines into a check or a reviewer rule; keep only navigation pointers |
| Stage or pass that changed nothing | Cut or merge the stage in its skill or agent; bench it as a removal round |
| Step in the wrong owner | Move the step between main session, subagent, lane and script in the skill or `orchestration.md` |
| Model or context mismatch | Change the agent's `model`, what its brief carries, or the loop's interval |
| Stop for the user or a ruling | Let the session rule in the skill that stopped, or make the step a script |

## Before you report

For each toolkit candidate run `python3 ~/agent-evals/bin/build_queue.py prior "<title, no backticks or $>"`. `~/agent-evals` missing: queue nothing and say so in the log.

## Queue

Decide each toolkit candidate yourself. Never ask the user which to queue.

- Queue it when the moment lost work, wrote a wrong record, let a defect through unseen, or happened more than once.
- Queue it when its `same idea` match is closed and the moment came after that fix: name the match in `--not-dup`.
- Skip it when its `same idea` match is still open, or when it happened once and the session recovered with no help.

A component id is kebab-case, such as `script/build-queue`. One command for each candidate you queue:

```bash
python3 ~/agent-evals/bin/build_queue.py new "<title, no backticks or $>" --by <model>/main --kind <chore|method|live-edit> --source <toolkit path the fix touches> --components <ids> --description "<one sentence naming the gain, no backticks or $>" --body - <<'EOF'
## Context
<the moment and what it cost>

## Done when
<the check that fails before and passes after>
EOF
```

On the work machine, write only the toolkit part: no work code, paths, ticket text or tool output.

## Report

A log of every candidate, most costly first, at most 7, in three lists:

- `Queued` and `Skipped`: toolkit candidates. Each line: title, its row in the table above, the moment (index + quote), then the queue file written, or the reason it was skipped and the queue match.
- `Project repo`: fixes that land only in the project repo. Each line: title, the moment (index + quote), the file it would change. These are never queued.

Findings from reading the environment cite the file and line in place of a moment.

Before you report, check the mix. When every candidate is a script or a check, read the session again for the last four moment kinds and add each you find. The report also names at least one cut (a stage, rule, agent or step that did not earn its cost), or says what you searched and that none showed.
