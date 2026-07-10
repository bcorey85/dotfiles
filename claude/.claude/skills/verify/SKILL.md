---
name: verify
description: Reconcile the shipped changes against the deep-plan ticket + plan to confirm everything was actually built, BEFORE /pr. A completeness gate, not a code review — checks "did we build what the plan called for", not code quality. Runs after /code (+/review) and before /pr.
allowed-tools: [Bash, Read, Glob, Grep, Agent, AskUserQuestion, Skill]
---

# Verify deep-plan Completeness

Independently reconcile what shipped on this branch against the ticket's requirements and the plan's per-phase success criteria. Report unbuilt or partial items before the PR opens.

## Why

`/review` (chained after `/code`) checks code **quality** — bugs, anti-patterns, security. Nothing in the flow checks **completeness**: did the diff actually satisfy every plan phase + ticket requirement? Those are different audits. The plan's `## Phase Status` checkboxes are self-reported by `/code`; verify does NOT trust them — it verifies against the real diff. Finding a gap here is cheap; finding it after `/pr` (or in `/finalize`, which seals the work) is not.

## When it runs

After `/code` (and its auto `/review`) report done, **before `/pr`**. Not a behavioral check — terminal-drivable behavioral verification runs per-phase via `/code`'s agent verifier (evidence recorded in the plan). verify is static reconciliation of plan ↔ diff, and on a clean result it assembles the **review packet**, whose centerpiece is the **human smoke-test checklist** — UI/browser-level verification is deliberately the user's job; agents never drive a browser.

## Resolve the task directory

Same resolver as `/finalize` (do NOT reimplement):

```bash
bash ~/.claude/scripts/resolve-task-dir.sh "$ARGUMENTS"
```

Exit 0 → use it, then glob `DIR/*.md` for the ticket (`-00-ticket.md`) and plan (`-05-plan.md`) files. Exit 3 → ask which match. Exit 4 → **eng-spec lane fallback**: take the branch's ticket key and glob `docs/eng-specs/<TICKET>*.md` — that doc is both ticket (requirements/ACs section) and plan. If neither lane yields a plan, ask for a path.

No plan found anywhere → stop: _"/verify needs a plan (deep-plan task dir or docs/eng-specs). Run /deep-plan or /eng-spec first, or verify manually."_

## Inputs

| File                  | Read for                                                                    |
| --------------------- | --------------------------------------------------------------------------- |
| `IQ-XXX-00-ticket.md` | Acceptance criteria / requirements                                          |
| `IQ-XXX-05-plan.md`   | `Phase Status`, each phase's `Success Criteria`, and `What We're NOT Doing` |

This is the one deep-plan step that DOES read the plan in full (contrast `/finalize`, which forbids it).

## Process

1. Resolve the directory; locate ticket + plan.
2. Determine the change set: everything on this branch (committed + uncommitted) vs its base branch. Default `BASE=$(git merge-base HEAD origin/master 2>/dev/null || git merge-base HEAD origin/main)`, then `git diff --stat "$BASE"...HEAD` plus working-tree changes; adjust the base if the branch was cut from a sprint branch.
3. **Dispatch a read-only reconciliation agent** — `Agent` with `subagent_type: "general-purpose"`, `model: "sonnet"`. Pass it: the ticket path, the plan path, and the diff scope. Instruct it to, for every ticket requirement and every plan `Success Criteria` item:
   - decide `done` / `partial` / `missing` by inspecting the actual diff and source (file:line evidence), NOT the Phase Status checkboxes;
   - if the plan has an `Acceptance Stubs` section, run its count command FIRST — a nonzero remainder is hard evidence of `missing` items (name the unflipped stubs); also verify every stub sentence still exists, as a todo or as a real test bearing that name — a reworded or deleted stub is tampering, reported as `missing`; this beats opinion-based reconciliation for those criteria;
   - run each **Automated Verification** command from the plan and record pass/fail;
   - list **Manual Verification** items as `needs-manual` (it can't run them — they feed the smoke-test checklist);
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
  bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=verify gate_missed=drift-gate class=plan-drift severity=<high|medium> lane=deep-plan desc="<one line>" file=<path>
  ```

  Then offer to dispatch `/fix` (or `/code` for net-new work) to close them. Re-run verify after.

- **Clean**: build the **review packet** — the single artifact for the human bulk review:
  1. Auto-invoke `/orient` via the Skill tool (`skill: "orient"`, no args — it self-scopes to the branch diff).
  2. Assemble one output, in this order: (a) the completeness table above; (b) orient's map (where it sits / wiring / reused-vs-new / structural risks); (c) **smoke-test checklist** — every acceptance criterion restated as a user-observable check, every `human-only` item from the plan's Manual Verification sections, and anything `needs-manual` from the reconciliation, each with concrete steps to exercise it; (d) **diff hotspots** — the 3–5 files where orient's structural risks and the completeness evidence point, listed as "read these first, skim the rest"; (e) a one-line pointer to the agent-verified evidence in the plan for spot-checking.
  3. Point forward: run the smoke-test checklist, then `/pr`. After the PR, `/finalize` (deep-plan lane).

## What NOT to do

- **Don't review code quality** — bugs/anti-patterns/security are `/review`'s job. Stay on "is it built".
- **Don't drive a browser or run the app** — UI/behavioral smoke testing belongs to the user via the smoke-test checklist; your executable scope is the plan's Automated Verification commands only.
- **Don't edit code or tests** — verify is read-only; it reports and routes.
- **Don't trust `Phase Status` checkboxes** — verify against the diff.
- **Don't flag `What We're NOT Doing` items** — those are deliberate scope cuts, not omissions.

## Arguments

$ARGUMENTS
