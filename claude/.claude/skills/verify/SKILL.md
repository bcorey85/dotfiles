---
name: verify
description: Reconcile the shipped changes against the eng-spec ticket + plan to confirm everything was actually built, BEFORE the PR opens. A completeness gate, not a code review — checks "did we build what the plan called for", not code quality. Runs after /code (+/review); the user opens the PR.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Verify Completeness

Independently reconcile what shipped on this branch against the ticket's requirements and the plan's per-phase success criteria. Report unbuilt or partial items before the PR opens.

## Why

Nothing in the flow checks **completeness** (did the diff satisfy every phase + ticket requirement?). `/code`'s `## Phase Status` checkboxes are self-reported — verify checks the real diff instead.

## When it runs

After `/code`+`/review` report done, **before the PR opens**. Static plan↔diff reconciliation only (behavioral verification already ran per-phase); on clean, assembles the **review packet** centered on the **human smoke-test checklist**.

## Resolve the task directory

Shared resolver (do NOT reimplement):

```bash
bash ~/.claude/scripts/resolve-task-dir.sh "$ARGUMENTS"
```

Exit 0 → an `/eng-spec` task directory: the ticket is `DIR/00-ticket.md`, the plan is `DIR/spec.md`. Exit 5 → a legacy flat eng-spec file: it is both ticket (requirements/ACs section) and plan. Exit 3 → ask which match. Exit 4 → ask for a path.

No plan found anywhere → stop: _"/verify needs a plan (an eng-spec task dir under docs/plans). Run /eng-spec first, or verify manually."_

## Inputs

| File | Read for |
| --- | --- |
| `00-ticket.md` | Acceptance criteria / requirements |
| `spec.md` | `Phase Status`, each phase's `Success Criteria`, and `What We're NOT Doing` |

This is the one step that DOES read the plan in full (contrast `/adr`, which forbids it).

## Process

1. Resolve the directory; locate ticket + plan.
2. Determine the change set: everything on this branch (committed + uncommitted) vs its base branch. Default base is merge-base against origin master or main, then triple-dot diff plus working-tree changes; adjust the base for sprint-branch cuts.
3. **Dispatch `plan-verifier`** (pinned; omit `model`) with `scope: branch`, ticket path, plan path, diff scope — nothing else. Its ONLY run site.

   **`N/A — no criteria in scope`** is not a pass. It means the plan gave the gate nothing to check; surface that to the user rather than reporting completeness.

4. **Log the gate BEFORE presenting.** Per `~/.claude/skills/_shared/finding-log.md` (read it): `gate=plan-verifier lane=verify scope=branch-exit`. One `kind=run` row every invocation (clean rows give the denominator) + one `kind=finding` row per `partial`/`missing` (`class=plan-drift`). Non-blocking — write the row while the reconciliation is in front of you.

5. Present the checklist. Route per the result.

## Reconciliation output

Present what it returns. Downstream you consume: verdict table, AC result, `needs-manual` items (→ smoke-test checklist), denominator.

## Routing

- **Gaps found (`partial`/`missing`/failing check)**: list them, log each as a drift-gate escape:

  ```bash
  bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=verify gate_missed=drift-gate class=plan-drift severity=<high|medium> lane=eng-spec guard=<...> desc="<one line>" file=<path>
  ```

  `guard` comes from the ratchet — run it per `~/.claude/skills/_shared/escape-ratchet.md`, using its batching rule across the gap list.

  Then offer to dispatch `/fix` (or `/code` for net-new work) to close them. Re-run verify after.

- **Clean**: first the **branch-final smell gate** — a bare `/refactor` must have run since the last code change; if not, run it now and let it converge. verify stays read-only and withholds the packet without it. Then build the **review packet**:
  1. Assemble in order: (a) completeness table; (b) **smoke-test checklist** — every AC restated as a user-observable check + every `human-only` Manual Verification item + `needs-manual` reconciliation items, each with concrete steps; (c) **diff hotspots** — the 3–5 heaviest files ("read these first, skim the rest"); (d) pointer to agent-verified evidence for spot-checking. Do NOT situate here — that's `/orient`, on demand.
  2. Point forward: run the smoke-test checklist, then open the PR yourself — agents never open PRs. After the PR exists, `/adr`.

## What NOT to do

- **Don't review quality** — that's `/review`; stay on "is it built".
- **Don't drive a browser or run the app** — smoke testing is the user's via the checklist; your scope is Automated Verification commands only.
- **Don't edit code or tests** — read-only; report and route.
- **Don't trust `Phase Status` checkboxes** — verify the diff.
- **Don't flag `What We're NOT Doing`** — deliberate cuts, not omissions.

## Arguments

$ARGUMENTS
