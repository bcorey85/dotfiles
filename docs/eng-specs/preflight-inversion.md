# Preflight inversion — move the gates into the phase loop, keep a branch recap

Status: proposed
Date: 2026-07-14
Scope: `claude/.claude/skills/{code,preflight,stage,_shared}` + CLAUDE.md routing

## Problem

`/preflight` was designed as the branch-exit ladder: every pre-commit gate either
fires or is reported skipped-with-reason, so nothing is silently missed. That was
correct when review, staging, and orientation all happened once, at the end.

They don't any more. Staging moved per-phase (`/stage` is a deterministic script and
runs fine at any boundary), and phase-boundary sign-off is where the real review
attention now lands. So preflight has drifted into a ladder whose rungs either
duplicate work already done or triage a surface the user already read.

Concretely, rung by rung:

| Rung | Today | Verdict |
| --- | --- | --- |
| 0 — preconditions | Refuses an unreviewed diff | Redundant; `review-commit-gate` blocks the commit anyway |
| 1 — `/stage` | Triages the whole branch | Moved per-phase; only closing-phase residue is left at exit |
| 1.5 — test-intent | One branch-wide audit | Split (see D2) |
| 2 — `/verify` | Fires when a spec exists | **Always a duplicate** — a spec means an `/eng-spec` plan, which mandates the Verify closing phase. There is no lane where this rung fires and the closing phase didn't |
| 2.5 — orient | No-spec branches only | Keep — the only orient that lane gets |
| 3 — read-surface triage | Model-classifies changed files | Redundant with `/stage`'s deterministic queue |
| 4 — receipt | Branch rollup | Keep — becomes the whole point |

The gates aren't wrong, they're in the wrong place. Every one of them has a sharper
oracle and a cheaper fix at the phase boundary than at branch exit.

## Decisions

### D1 — `/code`'s phase walkthrough is `/stage`-driven, not model-ranked

Block B/C of `/code` gained a "What changed / Read first" walkthrough (uncommitted, in
`claude/.claude/skills/code/SKILL.md`). As written, the orchestrator ranks blast radius
by judgment. **That is superseded by this spec**: block B invokes `/stage` instead.

- `/stage` stages the SAFE tier and returns ESCALATE / READ / SKIM in blast-radius order.
- That queue *is* the "Read first" section. Deterministic beats model-judged, and the
  staging lands exactly where the user signs off.
- The `stage.mjs` classifier stays the single source of truth for tiers — block B renders
  them, never re-ranks or promotes them.

### D2 — test-intent splits into two jobs by scope

`test-intent-reviewer` already has two (pin-intent, cull-spam). They have opposite scope
needs, so they run in different places.

**Per-phase — bug-pinning only.** The oracle is sharpest here: the phase's Success Criteria
and Acceptance Stubs, not a whole ticket against a five-phase diff. And the cost is
asymmetric — a test that pins a bug at phase 2 means phases 3–5 get built on top of the
wrong pinned behavior. This is the same argument `/code` already makes for keeping the
drift gate phase-scoped ("catches plan drift while it is still phase-sized").

**At exit — cull + coverage-net.** Test spam and `COVERAGE-LOST` are inherently cross-phase:
phase 2 and phase 4 each adding a test for the same thing is invisible phase-locally, and a
test deleted in phase 1 that phase 3 legitimately replaced would be a false positive if
judged per-phase.

Same agent, two scoped dispatches. Not two agents.

### D3 — cut preflight steps 2 and 3

- **Step 2 dies, `/verify` does not.** What dies is preflight's *duplicate invocation*.
  Branch-wide `/verify` stays a closing phase: the phase drift gate is phase-scoped and
  cannot do cross-phase completeness, and nothing else produces the human smoke-test
  checklist.
- **Step 3 dies into `/stage`'s queue.** The user has already consumed that queue per-phase.

### D4 — preflight inverts: gate-runner → branch synthesis

Superseded in part by D5/D6 below — the synthesis is right, but its home and name change.

By the time you reach branch exit, everything has been gated. Preflight's remaining job is
to reassemble the branch into one thing you can hold in your head before opening the PR.

```
## Branch recap — <repo> @ <branch>

What this branch does        — one paragraph, from the spec
Change map across phases     — rolled up from each phase's walkthrough
Cross-phase test audit       — cull + COVERAGE-LOST (D2)
Smoke-test checklist         — from the /verify closing phase
Open items                   — medium.ask, low[], escapes
Still unstaged               — closing-phase residue, /stage-ordered
Orient                       — ran (no-spec lane) | spec closing phase owns it

Next: read → smoke → stage → /commit. After the PR: /adr.
```

### D5 — every branch has a spec, so two more rungs are dead code

Resolves Q1 (below) and goes further. If no branch is ever specless:

- **Step 2.5 (orient on no-spec branches) never fires.** The Orient closing phase always
  owns it. D3 originally kept this rung — that was wrong.
- **`resolve-task-dir` exit 4 is unreachable**, so step 2's skip path is dead too.
- **Q1 dissolves.** The branch-wide deep review always fires, because the Verify closing
  phase always runs.

What survives of preflight is exactly three things: the cross-phase test audit (D2's exit
half), staging the closing-phase residue, and the recap.

### D6 — it becomes the fourth closing phase, renamed `/branch-recap`

Three things, and it must run *after* the Refactor sweep (which produces its own diff the
recap has to cover). That is a closing phase, not a skill you remember to run.

**Finalize becomes Recap.** This also resolves a pre-existing three-way contradiction:

| File | Says |
| --- | --- |
| `_shared/closing-phases.md:39` | Finalize runs `/adr` **pre-merge, so it ships in the same PR** |
| `CLAUDE.md:37` | "`/adr` **stays post-PR**" |
| `skills/preflight/SKILL.md:166` | "**Never run `/adr` pre-PR**" |

Finalize is defined to run `/adr` in a place two other files forbid. So `/adr` leaves the
closing phases entirely and lives post-PR, where the majority already agreed it belongs.

```
- [ ] Phase N:   Refactor pass — /refactor cleanup sweep (risk: low)
- [ ] Phase N+1: Verify pass   — branch-wide deep review + /verify (risk: high)
- [ ] Phase N+2: Orient pass   — /orient situate the change (risk: low)
- [ ] Phase N+3: Recap         — /branch-recap branch synthesis (risk: low)

Post-PR (not a phase): /adr
```

**Name: `/branch-recap`, not `/recap`.** `daily-recap` and `weekly-recap` are already skills
in the same namespace and mean something entirely different (vault journal rollups). `/recap`
next to those two reads as a third journal tool.

No explicit "mandatory" tag is needed: `closing-phases.md` already opens with the closing
phases being "not negotiable and never omitted," so slotting Recap in inherits that.

## Changes by file

1. `skills/code/SKILL.md` — block B/C walkthrough invokes `/stage`, renders its queue as
   "Read first" (revises the uncommitted edit). Add the per-phase bug-pinning test-intent
   dispatch to the phase gate, gated on `git diff --name-only` hitting a test file.
2. `skills/preflight/` → `skills/branch-recap/` — delete steps 0, 2, 2.5, 3. Demote step 1
   to closing-phase residue only. Rescope step 1.5 to cull + coverage-net. Rewrite step 4 as
   the recap. Drop the "ladder" framing from the description and opening paragraph.
3. `skills/_shared/closing-phases.md` + `plan-format.md` — Finalize → Recap (`/branch-recap`);
   `/adr` drops out of the closing phases.
4. `CLAUDE.md:37` — rewrite the branch-exit line for the new shape.
5. `agents/test-intent-reviewer.md` — description says "Dispatched by /preflight at branch
   exit"; it is now two scoped dispatches (phase gate + `/branch-recap`).
6. `agents/review-loop.md:183,233` — prose says test-intent is "a branch-exit step dispatched
   by /preflight". The *rule* stays correct (the loop still never dispatches it — `/code`'s
   phase gate does, outside the loop), but the attribution is stale.
7. `scripts/resolve-task-dir.sh:3` — header comment lists `/preflight` as a consumer.
8. `docs/backlog/stage-import-checklist.md` — describes the old ladder throughout; stale.

## Open questions

_None. Q1 and Q2 resolved — see D5 (every branch has a spec) and the direct-edit lane
accepted as ungated by design._

## Risks

- Moving gates into the phase loop makes them *fire more often* (once per phase, not once
  per branch). Per-phase test-intent only dispatches when test files changed, but on a
  test-heavy plan this is N dispatches where there was 1. Watch the flywheel.
- Preflight's stated purpose is "a stage silently not-run is the failure mode this skill
  deletes." Inverting it means that guarantee now rests on `/code`'s phase gate. If a user
  works outside `/code` (Q2), the guarantee is gone rather than degraded.

## Propagation sweep (mandatory — repo CLAUDE.md)

Before claiming done on any edit under `claude/.claude/`:

1. `grep -r` every changed section/tag name across the repo; update consumers —
   `review-loop.md` routing, the telemetry log call, `audit/review.md`.
2. Patch the ported copies in `opencode/.config/opencode/agents/`, or state the skip.
3. Check inheriting variants (`-deep` agents inherit by reference; coders preload
   `coder-core`).
4. `preflight-receipts.jsonl` schema changes with step removal — the `printf` in step 4
   emits `stage_triage`/`verify` fields that will no longer exist. Either keep them as
   `n/a — moved per-phase` or version the line.

## Suggested order

D1 first (it's a correction to uncommitted work and unblocks nothing else), then D2's
per-phase half, then D3+D4 together — preflight can't shed steps 2/3 until the phase loop
demonstrably covers them.
