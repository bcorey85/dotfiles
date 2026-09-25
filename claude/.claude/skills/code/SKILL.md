---
name: code
description: Dispatch a coder subagent for implementation, then auto-run `/review`. Use for "implement/build/add X" when the task is well-defined or a plan file exists; features needing design decisions go to /eng-spec first.
allowed-tools: [Agent, Bash, Read, Edit, Glob, Grep, AskUserQuestion, Skill]
---

# Code

Dispatch coder subagent(s) to implement code directly without architectural planning.

## Modifiers

`+fast` / `+deep` per `~/.claude/skills/_shared/modifiers.md` (read it when either is present).

## Instructions

0. **No arguments** (after stripping modifiers): run `bash ~/.claude/scripts/resolve-task-dir.sh`. Exit 0 → the task directory's `spec.md` is the task input; exit 5 → the printed plan file. Say what resolved. Exit 3 → ask which via AskUserQuestion. Exit 4 → ask the user what to implement.

1. **Modifiers**: `+deep` → dispatch `coder` and omit `model` (it pins Opus). `+fast` → pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Plan file or pasted plan**: `rg -n '^## ' <plan>` lists every section; the plan is multi-phase when more than one `## Phase N:` section exists. Read it phase-scoped per `~/.claude/skills/_shared/plan-reading.md`. `lane=eng-spec` when step 0 resolved the task input, `lane=code` otherwise; carry it into the review-loop dispatch.

   Multi-phase plan:

   - The next phase is the first unchecked `- [ ]` entry under `## Phase Status`. Without that section, fall back to `git status` plus per-phase success criteria and tell the user to backfill it.
   - Before every phase's coder, confirm `docs/plans/<slug>/acceptance-criteria.md` exists beside the plan and is non-empty. Missing on a task with behavioral criteria → STOP, do not dispatch, report a plan defect to the user; never write the criteria and never dispatch an agent to. Missing on pure config or mechanical work → proceed. Never pass criterion ids into a dispatch prompt. Log a failed check first:

     ```bash
     bash ~/.claude/scripts/log-scan repo=<basename> scan=acceptance-stub \
       stage=code-phase exit=0 candidates=1 confirmed=1 note="<what was missing>"
     ```

   - Dispatch the coder for that one phase only, with the phase's Automated Verification gate in its instructions. Re-read the phase's Phase Status line first: `(risk: …)` drives the boundary decision and `(reviewers: …)` passes to the review loop.
   - After the coder returns, dispatch the test-writer (3b); after it returns and you summarize, dispatch the review loop (5).
   - Before marking the phase done, check that the phase's `#### Automated Verification` commands passed: the review loop's execution gate is the full suite; run any other listed command once, after the loop returns; its `#### Manual Verification` items go on the deferred list for `/verify`. A phase with no Success Criteria is a plan defect; say so before advancing. A prohibition criterion (`git grep <pattern>` returns zero hits) is yours to run with Bash and log:

     ```bash
     bash ~/.claude/scripts/log-scan repo=<basename> scan=prohibition \
       stage=code-phase exit=<0|1> candidates=<hits> confirmed=<real hits> \
       branch=<branch> note="<the command, and what the ban protects>"
     ```

   - After the review loop returns `converged` or `deferred` and Automated Verification is green, `Edit` the phase's `## Phase Status` line from `- [ ] Phase N: ...` to `- [x] Phase N: ...`.
   - **Phase-boundary decision**, first match wins, then print the matching Phase-Complete Block:
     1. Last phase → STOP, block C.
     2. Phase 1, any risk tier → STOP, block B.
     3. A gate needed an exception, a `/fix` loop hit its cap, or the coder flagged an ambiguity → STOP, block B.
     4. `(risk: high)`, or no risk tag → STOP, block B.
     5. `(risk: low)` with all machine gates green → AUTO-ADVANCE, block A, then re-enter step 2 for the next phase in-session.
   - One phase or no phase headers → a single dispatch, still after the acceptance-criteria check.

3. **Dispatch the coder**: one `coder` subagent for the whole phase, whatever layers it touches. Two coders in parallel only for two deliverables that share no contract, type, or file, split by deliverable. Name the phase ("implement Phase N of `<plan-path>`") and tell the coder to read it phase-scoped. Coders write no tests. If the task turns out architectural, have the coder report back and recommend `/eng-spec`.

3b. **Dispatch the test-writer** after every coder dispatch that implemented plan behavior: one `test-writer` subagent, omit `model`. Skip only when the phase has no Success Criteria behavior and no acceptance criteria (pure config or mechanical), and note the skip in the phase summary. Pass the plan path, the phase number, and the stub file list when the plan names one. Pass nothing from the coder: no diff, no summary, no source contents.

Route on its report:

- `FAILING-TEST` lines → dispatch `/fix` scoped to make the named behaviors pass without touching the failing tests' assertions, then re-run the test-writer's `tests-run` command with Bash. Cap 2 fix rounds; still red → STOP and surface to the user. A `FAILING-TEST` whose scenario cannot run as planned is a spec defect: AskUserQuestion as in step 4, record it under `## Plan Deviations`, re-dispatch the `test-writer`.
- `UNDERSPECIFIED` lines → surface in the phase summary; a success criterion left untested blocks marking the phase done.
- Log each spec defect resolved above, one row each, before advancing:

  ```bash
  bash ~/.claude/scripts/log-escape repo=<basename> stage_found=phase-gate \
    gate_missed=eng-spec class=plan-drift severity=<high|medium|low> \
    lane=eng-spec guard=<...> desc="<what the plan asserted, and why it could not hold>" \
    file=<plan path>
  ```

4. **After the coder and the test-writer complete**: if the coder report carries a `PLAN-IMPACT:` block, raise it via AskUserQuestion (assumed → found → what changes; options `Adopt plan change` / `Keep plan as written` / `Discuss`) before anything else, and record the answer under the plan's `## Plan Deviations` (create if absent). Then summarize for the user: what was implemented, issues flagged, follow-up items, and the coder's `WHY:` lines grouped by file as `path:start-end — <note>` (omit when every coder reported `WHY: none`).

5. **Dispatch review**: first build the handoff block per `~/.claude/skills/_shared/handoff-block.md`: `files` (path, one-line change, `why` from the coder's WHY lines), `tests-run` from the test-writer's report, `flagged` (incl. UNDERSPECIFIED and resolved FAILING-TEST outcomes, or `none`), `plan_impact` (the block plus the user's decision, or `none`), `iter: 0`. Never dispatch without it. Then tell the user "Auto-dispatching review to check the implementation before committing." Then `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"`, passing `mode: review-first`, `caller: code`, `lane: <lane>`, `plan: <path>` and `phase: <N>` for the phase under review (omit `phase` when the plan file holds one phase or none, omit both when the plan was pasted), `reviewers: <domains>` verbatim from the phase's Phase Status line when it has one (omit when the tag reads `none`), the handoff block, and any `+fast`/`+deep` modifier plus any specialist flag (`+sec`/`+perf`/`+smell`/`no-specialist`).

   Route on the returned `status`, first match wins:

   - `plan-impact` → the step-4 modal, record under `## Plan Deviations`, re-dispatch `review-loop` with the decision and both counters (`iter`, `spec_iter`) preserved.
   - `critical-blocker` → STOP. Present `blockers`; do not mark the phase done.
   - `cap-reached` → STOP. Report `findings_remaining`; do not mark the phase done. The session is correctly left `dirty`, so `git commit` stays blocked.
   - `deferred` → render as `converged`, plus `findings_remaining` under `### Deferred to branch exit`; proceed.
   - `converged` → run `bash ~/.claude/scripts/review-gate-mark clean` first. Then render the packet (`### Fixed` from `fixed[]`, blockers first and marked; `perf[]` under its own heading; `skipped_fp[]`, `nit[]`). Present `ask[]` and wait; when `ask[]` is empty, proceed to the phase gates at once. After the user answers, log one row per ask (PLAN-IMPACT asks excluded):

     ```bash
     bash "$HOME/.claude/skills/review/log-review-finding" kind=finding \
       repo="$(basename "$(git rev-parse --show-toplevel)")" branch="$(git branch --show-current)" \
       lane=<lane> scope=phase phase=<N> iter=<returned iter> \
       gate=<entry gate> disposition=ask class=<entry class> file=<path> line=<n> \
       actioned=ask ask_outcome=<accepted|rejected|modified> desc="ask resolved: <one line>"
     ```

     Then proceed to the phase gates.

6. **Multi-phase plans**: after `converged` or `deferred`, run the phase-boundary decision (step 2). Any other status is a STOP. On a STOP, print the block with every placeholder resolved and wait; when the user confirms, re-enter step 2 for the next phase using `## Phase Status`. On an AUTO-ADVANCE, print block A and re-enter step 2 at once for the next phase in the same context.

## Phase-Complete Block

Deliver every block through the `brief` skill's shape (`~/.claude/skills/brief/SKILL.md`).

**A — Auto-advance** (decision rule 5):

```
Phase <N> complete — machine gates green (review ✓, execution ✓, automated-verification ✓). Risk: low. Manual verification: <n> agent-verified, <m> human-only deferred to the /verify packet.
→ Auto-advancing to Phase <N+1> in-session (no /clear; interrupt anytime).
```

**B — Stop for sign-off** (decision rules 2–4):

```
Phase <N> complete. Risk: <high | low — Phase 1 calibration | low — exception>. Phase-level sign-off requested.

Behavior delta (observable change + its proof, max 3 — no internals, no paths):
- <before → after, user-visible>. See it: <test name / command / UI flow>.

Read first (/stage queue, blast-radius order):
  ESCALATE:
  - <path> — <classifier reason>
  READ / SKIM:
  - <path>
Staged mechanically (<n>) — invariant-verified, skip.

Agent-verified (evidence in the plan):
- <item — one-line evidence summary>

Human-only verification remaining:
- <item>

Next:
  1. Read the queue; spot-check the evidence lines; run the human-only items.
  2. Stage what you've read, then run /clear and /code to start Phase <N+1> fresh. To keep this context, confirm here.

Or give feedback now for revisions to Phase <N>.
```

**C — Last phase** (decision rule 1): block B's walkthrough and verification lists, with the "Next" block replaced by:

```
All phases complete. Next: /verify (completeness + review packet; includes the remaining human-only checks), then you open the PR.
```

Verification items come from the just-finished phase's `#### Manual Verification:` section, split by the `agent-verified` / `human-only` tags. When that section is empty, omit both lists and replace step 1 with "Read the /stage queue."

Skill-invoke `/stage` to build the "Read first" queue and render it verbatim, in its order. The behavior delta comes from the coder's handoff (absent one, derive it from the diff and mark `derived from diff`). When the user steps the queue, `nvim-jump` each entry per `~/.claude/skills/_shared/nvim-jump.md`.

## Task

$ARGUMENTS
