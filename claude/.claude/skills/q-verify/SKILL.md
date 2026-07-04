---
name: q-verify
description: Reconcile the shipped changes against the QRSPI ticket + plan to confirm everything was actually built, BEFORE /pr. A completeness gate, not a code review — checks "did we build what the plan called for", not code quality. Runs after /code (+/review) and before /pr.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Verify QRSPI Completeness

Independently reconcile what shipped on this branch against the ticket's requirements and the plan's per-phase success criteria. Report unbuilt or partial items before the PR opens.

## Why

`/review` (chained after `/code`) checks code **quality** — bugs, anti-patterns, security. Nothing in the flow checks **completeness**: did the diff actually satisfy every plan phase + ticket requirement? Those are different audits. The plan's `## Phase Status` checkboxes are self-reported by `/code`; q-verify does NOT trust them — it verifies against the real diff. Finding a gap here is cheap; finding it after `/pr` (or in `/q-finalize`, which seals the work) is not.

## When it runs

After `/code` (and its auto `/review`) report done, **before `/pr`**. Not a behavioral check — for "does the app actually do the thing", that's `/verify`. q-verify is static reconciliation of plan ↔ diff.

## Resolve the task directory

Same resolver as `/q-finalize` (do NOT reimplement):

```bash
bash ~/.claude/scripts/qrspi-resolve-dir.sh "$ARGUMENTS"
```

Exit 0 → use it. Exit 3 → ask which match. Exit 4 → ask for a path. Then glob `DIR/*.md` for the ticket (`-00-ticket.md`) and plan (`-05-plan.md`) files.

Missing `-05-plan.md` → stop: _"/q-verify needs a QRSPI plan. Run /q-orchestrator first, or verify manually."_

## Inputs

| File                  | Read for                                                                    |
| --------------------- | --------------------------------------------------------------------------- |
| `IQ-XXX-00-ticket.md` | Acceptance criteria / requirements                                          |
| `IQ-XXX-05-plan.md`   | `Phase Status`, each phase's `Success Criteria`, and `What We're NOT Doing` |

This is the one QRSPI step that DOES read the plan in full (contrast `/q-finalize`, which forbids it).

## Process

1. Resolve the directory; locate ticket + plan.
2. Determine the change set: everything on this branch (committed + uncommitted) vs its base branch. Default `git diff --stat $(git merge-base HEAD origin/master)...HEAD` plus working-tree changes; adjust the base if the branch was cut from a sprint branch.
3. **Dispatch a read-only reconciliation agent** — `Agent` with `subagent_type: "general-purpose"`, `model: "sonnet"`. Pass it: the ticket path, the plan path, and the diff scope. Instruct it to, for every ticket requirement and every plan `Success Criteria` item:
   - decide `done` / `partial` / `missing` by inspecting the actual diff and source (file:line evidence), NOT the Phase Status checkboxes;
   - if the plan has an `Acceptance Stubs` section, run its count command FIRST — a nonzero remainder is hard evidence of `missing` items (name the unflipped stubs); also verify every stub sentence still exists, as a todo or as a real test bearing that name — a reworded or deleted stub is tampering, reported as `missing`; this beats opinion-based reconciliation for those criteria;
   - run each **Automated Verification** command from the plan and record pass/fail;
   - list **Manual Verification** items as `needs-manual` (it can't run them — flag for `/verify`);
   - skip anything under `What We're NOT Doing` (intentional scope cuts are not gaps);
   - return the structured checklist below and change nothing.
4. Present the checklist. Route per the result.

## Reconciliation output

```
## Completeness: IQ-XXX

| Source item | Status | Evidence |
| ----------- | ------ | -------- |
| [ticket req / plan criterion] | done / partial / missing / needs-manual | path:line or cmd result |

Automated checks: <cmd> ✓ / ✗ …
Manual (for /verify): …
Out of scope (skipped): …
```

## Routing

- **Gaps found (`partial`/`missing`/failing check)**: list them, and log each as an escape past the phase-level drift gates (ground truth for the loop's trustworthiness — see `/review-stats`):

  ```bash
  bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=q-verify gate_missed=drift-gate class=plan-drift severity=<high|medium> desc="<one line>" file=<path>
  ```

  Then offer to dispatch `/fix` (or `/code` for net-new work) to close them. Re-run q-verify after.

- **Clean**: say so, then auto-invoke `/orient` via the Skill tool (`skill: "orient"`, no args — it self-scopes to the branch diff). Its map plus the completeness table above form the human review packet: read those first, then the diff hotspots they point at. Then point forward: `/verify` for any `needs-manual` items, otherwise `/pr`. After the PR, `/q-finalize`.

## What NOT to do

- **Don't review code quality** — bugs/anti-patterns/security are `/review`'s job. Stay on "is it built".
- **Don't run the app** — behavioral confirmation is `/verify`.
- **Don't edit code or tests** — q-verify is read-only; it reports and routes.
- **Don't trust `Phase Status` checkboxes** — verify against the diff.
- **Don't flag `What We're NOT Doing` items** — those are deliberate scope cuts, not omissions.

## Arguments

$ARGUMENTS
