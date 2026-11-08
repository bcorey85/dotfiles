---
name: close-branch
description: The one closing phase. Scripts first, then four report-only reviewers in parallel on the whole branch diff, one coder that fixes every finding, a report-only gate on the fix diff alone, then the recap sheet. Use for "close the branch", "/close-branch", and the plan's Close pass. Hands back a read queue; the staging of semantic files, the commit and the PR stay the user's.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Close branch

One pass over the finished branch: every reviewer reads the same tree at once, one coder fixes everything they found, and a gate reads only what that coder changed. Reviewers never edit. You never edit code or tests yourself.

## Step 1: scripts first

Run these from the repo root, in one response:

```bash
~/.claude/scripts/review/verify-prep $ARGUMENTS
python3 ~/.claude/skills/refactor/scripts/refactor_flow.py branch-prep
```

verify-prep's exit codes are those in `~/.claude/skills/verify-branch/SKILL.md` Step 0; follow that table. Note the merge-base it prints as `<base>`, and pass `--base <base>` to `branch-prep` when the two bases differ. Then run, in one response:

```bash
python3 ~/.claude/scripts/code/concentration.py <base>
python3 ~/.claude/scripts/review/full_check.py "$(git rev-parse --show-toplevel)" --log <scratchpad>/close-full-check.log --base <base>
```

`concentration.py` counts commits only, so commit the last feature phase first. Keep both concentration counts for the recap; no module is simplified here. When the full check prints `not run (no check found`, run once instead the one command that runs every lint, type check and test, as the repo's README or Makefile names it (such as `make check`), output to the same log. A failing check is a finding for Step 3, with its failing lines. Step 4 reruns whichever check ran here.

## Step 2: four reviewers in parallel

Send all four `Agent` calls in ONE message. Omit `model` on each. Each reports and does not edit.

1. `code-reviewer` — the review prompt verify-prep printed, verbatim, with its uncommitted and untracked notes.
2. `smell-reviewer` — the finder prompt `branch-prep` printed, verbatim. Every finding carries `file:line`, and duplication names the sibling's `file:line`. A cast or `?? default` papering a fixable wide type is a finding.
3. `test-intent-reviewer` — `scope: cull`, the branch diff (`git diff <base>` plus the untracked files verify-prep listed), the spec path, and the `acceptance-criteria.md` path beside the plan.
4. `plan-verifier` — the payload verify-prep printed, exactly. Nothing else in the prompt.

While they run, read the diff yourself for a surprise none of them is placed to see (a behavior change, a dropped case, a cross-file break) and note each as a finding.

## Step 3: one fix coder

Merge the four reports and your own findings into one list, deduplicated by file and line. Each item keeps its file, line, source reviewer and proposed change. It holds:

- every code-reviewer and smell-reviewer finding, nits included;
- every test-intent cull and WEAK finding. A `REQUIRES-MUTATION` cull is not acted on: list it under open items in the recap, marked `not run`;
- every criterion the plan-verifier marked partial, missing, or MISSING, and every failed automated check, each as "write or fix the covering test" or "build the missing behavior";
- every failing full-check line from Step 1.

An `ask` whose change cuts or changes a ticket AC goes to the user, not to the coder: log it with disposition `ask` and actioned `ask`.

Before the dispatch, run `git add -A` so the index holds the reviewed tree. Then dispatch `coder` ONCE with the whole list. The coder runs the tests for the files it changed. With an empty list, skip to Step 5.

## Step 4: the fix-diff gate

The fix diff is `git diff` (working tree against the index) plus any file `git status --porcelain` shows as `??`. Run in one response:

- the check from Step 1 again;
- ONE `code-reviewer` (omit `model`) with this prompt: "Report-only gate. Review ONLY the fix diff: `git diff` (working tree against the index) and these new files: <list>. The fixes answered these findings: <the Step 3 list, one line each>. For each finding, say whether the diff fixes it. Report every new defect the diff introduces, with file, line and severity (critical, high, medium, low). For each criterion in this list, name the test that now covers it, or say MISSING: <the criteria from Step 3>."

The gate FAILS on a red full check, a critical or high finding, a criterion still MISSING, or a Step 3 finding the diff left unfixed without showing it wrong. Medium and low findings do not fail it: they go under open items in the recap.

On a fail, run `git add -A`, dispatch `coder` ONCE with only the failing items, and run Step 4 once more on the new fix diff. A second fail → STOP: report the failing items to the user.

## Step 5: log

1. Rerun `verify-prep`. Log every finding from Steps 2 to 4 with `~/.claude/scripts/review/verify-log review --result <PASS|PASS WITH WARNINGS|NEEDS CHANGES> --rows <file>`, in the row shape `~/.claude/skills/verify-branch/SKILL.md` Step 1 gives (`actioned` `fixed`, `skipped_fp`, or `ask`). Rerun `verify-prep`; it must report the review as ran.
2. Log the plan-verifier's verdicts with `verify-log --rows <file>`, as `~/.claude/skills/verify-branch/SKILL.md` Step 3 says, with each criterion the gate showed covered moved to `done` and its covering test as the evidence. On gaps, follow that file's Routing for gaps; on asks open, its Routing for asks.

## Step 6: recap

Run, in one response, from the repo root:

```bash
node ~/.claude/skills/stage/scripts/stage.mjs --run
git diff --stat <base>
rg -n -i 'sign-?off' <the plan's folder>/03-decisions.md <the spec path>
```

Run the deferred queue read in its own Bash call with a `timeout` of `600000` (about 204 s when the ledger answers busy at once, longer when a ledger call hangs):

```bash
~/.claude/scripts/tools/ledger_deferred.py
```

Print one recap, assembled from what you already hold. Never dispatch an agent for it and never re-read code for it:

```
## Branch recap — <repo> @ <branch>

<one paragraph: what this branch does, from the spec>

### Change map                    (from git diff --stat)
### Close pass                    (findings by reviewer: fixed / shown wrong / ask; gate result and rounds)
### Criteria changes              (each sign-off line rg printed: the criterion, what changed, who signed, when)
### Concentration                 (largest module and branch counts)
### Deferred findings             (ledger_deferred.py's line as printed, or each row triaged fixed / stale / carried)
### Smoke-test checklist          (verify-log's checklist skeleton, every human-only item with concrete steps)
### Open items                    (asks, gate medium and low findings, REQUIRES-MUTATION culls not run)
### Still unstaged                (from stage.mjs, blast-radius order)

Next: read the residue → run the smoke checklist → /adr → stage → /commit → open the PR.
```

Build Criteria changes from the `rg` output only. A sign-off that another session wrote, not the user, is listed as `not the user's sign-off: the criterion stands`. Write `none` only when `rg` printed no line. Any report that says whether a criterion was cut or narrowed, the hand-back included, repeats this section.

## What NOT to do

- Never edit code or tests yourself; the Step 3 and Step 4 coders do.
- Never dispatch a reviewer after Step 4's second gate.
- Never `git commit` or open a PR.
- Never trust `Phase Status` checkboxes.

## Arguments

$ARGUMENTS
