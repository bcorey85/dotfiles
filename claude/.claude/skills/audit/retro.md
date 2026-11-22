# Lane: retro — fixes to the environment from one session

Read one session and propose changes to the toolkit or repo that would have made it go better. The output is environment changes only; the session's own code stays as it is.

## Input

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

Each moment carries its block index or turn and a short quote. Drop any candidate you cannot tie to a moment.

## Read the environment

Before you place a fix, read what the repo the session worked in already has:

- Its check commands: test runner, lint and type config, CI workflows, pre-commit hooks, `settings.json` hooks. A check that exists but did not run, or runs and is broken, is the finding.
- No guardrail at all (no pre-commit hook and no CI job that runs its lint, typecheck and tests) is a finding of its own.
- The steering files the session loaded: global and repo CLAUDE.md, `rules/*.md`, the skills that ran. Count their lines. In any file over 150 lines, list the lines a check or a reviewer rule could hold, and the no-ops.

## Place each fix

Classify each mistake first. A mechanical one (a fixed pattern, a banned API, a command form, an import shape, a file location) gets a check. Only a judgment call gets prose.

| Moment | Fix |
| --- | --- |
| Slow lookup | A pointer in a file the agent already reads (repo CLAUDE.md, the skill that ran) |
| Mechanical mistake (wrong API, path, shape, command form) | A check: gate under `scripts/gates/`, test under `tests/`, lint rule |
| Judgment-call miss | A rule for the reviewer (`rules/*.md`, the reviewer agent), never the implementer or CLAUDE.md |
| A check exists but did not run | Wire it (`settings.json` hook, `tests/run.sh`, CI); never build a second one |
| Expensive tool call | Streamline or replace the tool or script |
| No-op rule line | A deletion candidate, to test with `~/agent-evals/bin/rule_meter.py` before cutting |
| Fact out of reach | Widen access (tee a log to a file, a read-only command) |
| No guardrail in the repo | A pre-commit hook or CI job that runs its check command |
| Large steering file | Move its lines into a check or a reviewer rule; keep only navigation pointers |

## Before you report

For each candidate run `python3 ~/agent-evals/bin/build_queue.py prior "<title, no backticks or $>"`. A `same idea` hit: name that item and drop the candidate, or mark it "adds to <item>". `~/agent-evals` missing: say queue checks were not run.

## Report

A numbered list, most costly first, at most 7. Each: title, its row in the table above, the moment (index + quote), the fix and its file, the queue match. Findings from reading the environment cite the file and line in place of a moment. Queue nothing yet. End with one line: reply with the numbers to queue.

## Queue the picks

Queue only the numbers the user picks, then list the queue file written for each. A component id is kebab-case, such as `script/build-queue`. One command each:

```bash
python3 ~/agent-evals/bin/build_queue.py new "<title, no backticks or $>" --by <model>/main --kind <chore|method|live-edit> --source <toolkit path the fix touches> --components <ids> --description "<one sentence naming the gain, no backticks or $>" --body - <<'EOF'
## Context
<the moment and what it cost>

## Done when
<the check that fails before and passes after>
EOF
```

On the work machine, write only the toolkit part: no work code, paths, ticket text or tool output.
