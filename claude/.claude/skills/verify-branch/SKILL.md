---
name: verify-branch
description: Reconcile the shipped changes against the eng-spec ticket + plan to confirm everything was actually built, BEFORE the PR opens. A completeness gate, not a code review — checks "did we build what the plan called for", not code quality. Runs after /code (+/review); the user opens the PR.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Verify Branch

Two checks, in order, on every path to branch end: a branch-wide correctness review, then a completeness reconciliation (did we build what the ticket and plan called for). Direct calls and `/code`'s Verify pass run the same thing.

`/code`'s `## Phase Status` checkboxes are self-reported. This skill checks the real diff.

## Step 0: prep

```bash
~/.claude/scripts/review/verify-prep $ARGUMENTS
```

It resolves the task dir, reads the criteria, measures the diff, checks whether a branch-wide review ran since the last change, and prints the dispatches. Do the steps it prints, in order. Do not re-derive any of it.

| Exit | Meaning                                                                                            | Do                                                                                                                                                                                 |
| ---- | -------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 0    | ready                                                                                              | follow the printed steps                                                                                                                                                           |
| 2    | loud failure (no criteria found, missing file, no base, empty diff, detached HEAD, unknown option) | report the message to the user; never treat it as a pass                                                                                                                           |
| 3    | several task dirs                                                                                  | ask which; rerun with the answer                                                                                                                                                   |
| 4    | no plan                                                                                            | ticket-only: fetch the ticket per `~/.claude/skills/_shared/jira-ticket.md`, write its raw fields to `<scratchpad>/<KEY>-ticket.md`, rerun `verify-prep --ticket-file <that path>` |

For a sprint-branch cut pass `--base <ref>`. The ticket's ACs are always in scope, plan or no plan. Never check them yourself in place of the gate.

## Step 1: branch-wide review (only when prep says it has not run)

1. Dispatch `code-reviewer` with the exact prompt prep prints.
2. Route its findings with `/review` and fix them.
3. After the fixes, log the review with every finding the reviewer reported, one entry each (`[]` when none): `~/.claude/scripts/review/verify-log review --result <PASS|PASS WITH WARNINGS|NEEDS CHANGES> --rows <file|->`. Each entry is `{"desc": "<one line>", "file": "<path>", "line": 0, "class": "<bug|smell|...>", "actioned": "<fixed|skipped_fp|deferred|ask|none>"}`. `actioned` is required, and a `fix` finding (the default disposition) cannot have `actioned` `none`. `class` and `disposition` are optional.
4. Rerun `verify-prep`. It must now report the review as ran. Do not continue until it does.

The log row records the content of the tree, apart from the task dir. Any later change to the diff or to an untracked file (an edit, a deletion, a rename, a new file) makes the review stale: prep says so and asks for the review again. `verify-log` exits 2 with "rerun verify-prep" when the tree changed since prep or no logged review covers it, and logs nothing. Only a review logged by `verify-log review` counts.

## Step 2: plan-verifier

Dispatch `plan-verifier` (pinned; omit `model`) with the exact payload prep prints. It is the only run site. Nothing else goes in the prompt.

`N/A — no criteria in scope` is not a pass. The plan gave the gate nothing to check; surface it to the user. Log it with `verify-log --rows - --result NA` and `[]` as the rows.

## Step 3: log

Convert the verifier's verdict table to a JSON list and pipe it in:

```bash
~/.claude/scripts/review/verify-log --rows - <<'JSON'
[{"item": "<criterion>", "verdict": "done|partial|missing|failed-check|needs-manual|overridden",
  "file": "<path>", "line": 0, "evidence": "<one line>", "signoff": "<who and when; overridden only>"}]
JSON
```

One row per verdicted item, verbatim, plus one `failed-check` row for each ✗ automated check in the verifier's Job 2 table (`item` is the command, `evidence` its failure). Add a `missing` row for each id the verifier marks ⚠️ MISSING; name the id at the start of `item` (`AC3: ...`). Send a row for every id in the criteria file: if one has no row, the script exits 2, names it and writes nothing. `line` is a number or a range such as `12-20`. The script writes the run row and a `plan-drift` finding row per gap, and prints the result. A `partial`, a `missing`, a `failed-check`, and an `overridden` row without a sign-off are gaps. An N/A verdict exits 3: tell the user, do not report completeness. Empty rows without `--result NA` exit 2.

## Routing

- **Gaps**: list them. Pick the guard rung per `~/.claude/skills/_shared/escape-ratchet.md` (batching rule across the list), add `"guard": "<rung>"` and `"severity": "<high|medium|low>"` to those rows, then rerun the same command with `--escapes-only` to log the drift-gate escapes. An escape already logged is not logged twice, and `--escapes-only` prints only the escapes it logged. Offer `/fix` (or `/code` for net-new work). Re-run `/verify-branch` after.
- **Clean**: the **branch-final smell gate** first. Run a bare `/refactor` now and let it converge, unless you can show one ran since the last code change. Then build the **review packet** from the checklist skeleton `verify-log` printed:
  1. (a) the completeness table; (b) the smoke-test checklist: fill the `steps:` of every line with concrete steps; (c) the diff hotspots it listed ("read these first, skim the rest"); (d) a pointer to agent-verified evidence. Do NOT situate here (`/orient`, on demand).
  2. Before presenting, `nvim-jump` the evidence per `~/.claude/skills/_shared/nvim-jump.md`: each completeness-table `file:line` in table order with `--note "<criterion>: <what the line proves>"`, then each covering test's `file:line` with `--note "<AC id>: <what it asserts>"`.
  3. Point forward: run the smoke-test checklist, then open the PR yourself. Agents never open PRs. After the PR exists, `/adr`.

## What NOT to do

- Don't review quality yourself; the code-reviewer dispatch in Step 1 does.
- Don't drive a browser or run the app. Smoke testing is the user's via the checklist.
- Don't edit code or tests in this skill. Fixes go through `/review`, `/fix` or `/code`.
- Don't trust `Phase Status` checkboxes.
- Don't flag plan items in `What We're NOT Doing`. A ticket AC there is the exception: only the user's explicit sign-off cuts one.
- Don't skip Step 1 because the phases were reviewed. Only prep's "ran" report skips it.

## Arguments

$ARGUMENTS
