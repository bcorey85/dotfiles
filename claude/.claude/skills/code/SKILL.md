---
name: code
description: Dispatch a coder subagent for implementation, then auto-run `/review`. Use for "implement/build/add X" when the task is well-defined or a plan file exists; features needing design decisions go to /eng-spec first.
allowed-tools: [Agent, Bash, Read, Edit, Glob, Grep, AskUserQuestion, Skill]
---

# Code

Dispatch coder subagent(s) to implement code directly without architectural planning.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). `+fast` for trivial tasks (renames, typos, one-liners); `+deep` for complex tasks requiring deeper reasoning.

## Instructions

0. **Resolve task input when no arguments were given**: If `$ARGUMENTS` is empty (after stripping any bare modifiers like `+fast`/`+deep`), run `bash ~/.claude/scripts/resolve-task-dir.sh` (it infers the ticket from the branch name):
   - Exit 0 (eng-spec task directory) → the task input is its `spec.md`. Exit 5 (legacy flat eng-spec plan file) → the printed file is the task input. Either way, tell the user what resolved; step 2's multi-phase detection then applies.
   - Exit 3 (multiple matches) → ask which via AskUserQuestion. Exit 4 (nothing resolvable) → ask the user what to implement. Do not guess a task.

1. **Check for modifiers**: If `+deep` is present, dispatch `coder-deep` instead of `coder` and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

   **Coder tier is the caller's call, not the risk tag's** — a `(risk: high)` phase does NOT auto-select the `-deep` coder. Use `+deep` deliberately on a phase you judge dangerous.

2. **Detect multi-phase plans (MANDATORY check)**: If the task input is a path to a plan file (e.g., `*-plan.md` under `docs/plans/`) or pasted plan content, check whether it contains multiple `## Phase N:` sections.

   **Detect and read by section, never by whole file.** `rg -n '^## ' <plan>` answers the multi-phase question AND gives you every section's line number in one call — do not `Read` the plan to count headings. From there, read phase-scoped per `~/.claude/skills/_shared/plan-reading.md`. Pasted plan content is already in context; scoping applies only to paths.

   **Lane provenance (for telemetry, one-time)**: `lane=eng-spec` when the task input came from step 0's resolver (task directory `spec.md`, or a legacy flat plan file); `lane=code` otherwise (direct dispatch, no plan). Carry this value into the `review-loop` dispatch (step 6).

   **If it's a multi-phase plan:**
   - Do NOT dispatch all phases at once.
   - Identify the next un-executed phase by reading the plan's `## Phase Status` section: the first unchecked (`- [ ]`) entry is the phase to dispatch. This is the source of truth across `/clear` boundaries — do NOT scan git log or diff to figure out where you are. If the plan has no `## Phase Status` section (older plan format), fall back to `git status` + per-phase success criteria, but flag this to the user so they can backfill the section.
   - **Acceptance-criteria check (YOU do this, by reading, before the phase's coder — every phase):** confirm `docs/plans/<slug>/acceptance-criteria.md` exists beside the plan and is non-empty.

     Missing, when the ticket plainly has behavioral criteria → **STOP and do not dispatch**; report it as a plan defect and hand it to the user. Never write the criteria yourself at this point and never dispatch an agent to do it. They are `/eng-spec` Phase 7.5's output, written with the user.

     Missing on a task with no behavioral criteria (pure config, mechanical refactor) → proceed.

     The criteria are prose and stay in the planning directory. Do not seed `tests/` with stub files from them, and never pass criterion ids into a dispatch prompt — that is how they leak into committed code (`_shared/code-vocabulary.md`). The closing Verify phase is what proves each one ended up with a test.

     When the check fails — missing file, empty file, or criteria that plainly do not cover the ticket — score it before you do anything else:

     ```bash
     bash ~/.claude/scripts/log-scan repo=<basename> scan=acceptance-stub \
       stage=code-phase exit=0 candidates=1 confirmed=1 note="<what was missing>"
     ```

     `exit=` says only whether the scan RAN (`0` printed rows, `1` clean, `2` did not run) — a found defect is `exit=0` with counts.

   - Dispatch the coder for THAT ONE PHASE ONLY. The coder must run the phase's "Automated Verification" gate (typically `npm run validate` or equivalent) before returning. **Re-read the phase's Phase Status line before dispatching** — its `(risk: …)` tag drives the phase-boundary decision (step 2) and its `(reviewers: …)` list is passed through to the review loop (step 5).
   - After the coder completes, dispatch the `test-writer` (step 3b); after it returns and you summarize, auto-dispatch `/review` (step 5).
   - **No per-phase `plan-verifier`.** Plan↔diff reconciliation runs ONCE, at branch end, from `/verify`. Here, YOU check before marking the phase done: the phase's `#### Automated Verification` commands actually ran and passed (coder evidence), and its `#### Manual Verification` items go on the deferred list for `/verify`. A phase with no Success Criteria is a plan defect, not a pass — say so before advancing.

     **Run any prohibition criterion yourself and log the run.** A criterion of the form "`git grep <pattern>` returns zero hits" is a scan, not coder evidence — run it with Bash and score it, because a prohibition nobody re-ran is indistinguishable from one that never held:

     ```bash
     bash ~/.claude/scripts/log-scan repo=<basename> scan=prohibition \
       stage=code-phase exit=<0|1> candidates=<hits> confirmed=<real hits> \
       branch=<branch> note="<the command, and what the ban protects>"
     ```

     Grep exits 1 on a clean tree, so a passing run is `exit=1 candidates=0`.

   - **No per-phase test-intent audit.** The enforced coder/test-writer split already severs bug-pinning's cause, so the audit does not run here. The cull/coverage/weak half runs at the `/test-audit` closing phase, and `/verify` reconciles plan↔diff at branch end; a `weak`/`bug-pinning` finding surfacing from ANY other gate still routes to `test-writer` re-dispatch (implementation-blind), `/fix` only when it implicates src.
   - After the review loop returns `converged` or `deferred` AND the phase's Automated Verification is green, mark the phase done in the plan: `Edit` the `## Phase Status` section to flip `- [ ] Phase N: ...` → `- [x] Phase N: ...`. This single Edit is the durable record of progress — it survives `/clear` and lets in-session re-entry detect the next phase.
   - **Phase-boundary decision** — the phase is done; now decide stop vs. auto-advance, checking these in order (first match wins), then print the matching Phase-Complete Block:
     1. **Last phase** → STOP; print the completion footer (block C).
     2. **Phase 1**, any risk tier → STOP for **calibration** (block B) — first contact between plan and repo.
     3. **A gate needed an exception, a `/fix` loop hit its cap, or the coder flagged an ambiguity**, any tier → STOP (block B).
     4. **`(risk: high)`** — and an untagged phase counts as high → STOP for phase-level sign-off (block B).
     5. Otherwise — genuinely **`(risk: low)`** with all machine gates green → **AUTO-ADVANCE in-session** (block A): print the one-line advance notice, then re-enter step 2 for the next phase. Do NOT `/clear` and do NOT wait — the user can interrupt at any boundary.
   - If the plan has only one phase or no phase headers, treat it as a single dispatch (skip the phase loop) — but still run the acceptance-criteria check above before dispatching. A one-phase plan owes its criteria the same way a nine-phase one does.

3. **Dispatch the coder**:

   Launch a single `coder` subagent, whatever the work touches — client, server, both, or neither. There is no scope variant to pick, so do not spend a step detecting one. One owner per phase, and therefore one owner for both ends of any wire it crosses.

   Dispatch two coders in parallel ONLY when the work holds two genuinely independent deliverables that share no contract, type, or file — and then split by DELIVERABLE, never by client/server layer.

   For each coder:
   - **When the task is a phase of a multi-phase plan, name the phase explicitly** ("implement Phase 4 of `<plan-path>`") and tell the coder to read it phase-scoped (`coder-core`'s workflow step 1 carries the mechanics).
   - Coders write NO tests (coder-core's "Tests Are Not Yours") — stub flips and all test authorship happen in step 3b's `test-writer` dispatch
   - If the task turns out to be architectural, have it report back and recommend `/eng-spec` instead

3b. **Dispatch the test-writer** (after every coder dispatch that implemented plan behavior): a single `test-writer` subagent (pinned; omit `model`). Skip ONLY when the task/phase has no Success Criteria behavior and no acceptance criteria (pure config or mechanical phases) — note the skip in the phase summary.

Pass the plan path + phase number (it reads phase-scoped) and the stub file list when the plan names one. **Pass NOTHING from the coder** — the agent is implementation-blind by contract: no diff, no coder summary, no source file contents in its prompt. Its assertions must come from the plan alone.

Route on its report:

- `FAILING-TEST` lines → candidate implementation bugs, the split working as designed. Dispatch `/fix` scoped to make the named behaviors pass WITHOUT touching the failing tests' assertions, then re-run the test-writer's `tests-run` command yourself with Bash. Cap: 2 fix rounds; still red → STOP and surface to the user.

  **First decide which side is wrong.** A `FAILING-TEST` whose scenario cannot run as planned (unreachable fixture, contradicting criterion, disagreeing sections) is a SPEC defect: route to **AskUserQuestion** as the PLAN-IMPACT gate does, record in `## Plan Deviations`, then re-dispatch the `test-writer` — never the coder.

- `UNDERSPECIFIED` lines → surface in the phase summary; a success criterion left untested by one blocks marking the phase done (plan gap — treat like a missing Success Criteria section, step 2).

**Log every spec defect resolved above as an escape, at the moment it resolves** — one row per defect, before advancing (the Deviations entry records the decision; this row makes it countable):

```bash
bash ~/.claude/scripts/log-escape repo=<basename> stage_found=phase-gate \
  gate_missed=eng-spec class=plan-drift severity=<high|medium|low> \
  lane=eng-spec guard=<...> desc="<what the plan asserted, and why it could not hold>" \
  file=<plan path>
```

`gate_missed=eng-spec`, never `coder` — the implementer did not miss this.

4. **After the coder and the test-writer complete**, summarize for the user AND build a handoff block for downstream review.

   **PLAN-IMPACT gate (before anything else in this step)**: scan the coder report for a `PLAN-IMPACT:` block (coder-core requires `PLAN-IMPACT: yes` as the report's last line when one exists). If present, present it via **AskUserQuestion** — assumed → found → what changes, options `Adopt plan change` / `Keep plan as written` / `Discuss` — BEFORE summarizing or auto-dispatching `/review`. Record the answer in the plan's `## Plan Deviations` section (create if absent) so `/verify` reconciles against the amended plan.

   User summary:
   - What was implemented
   - Any issues flagged
   - Any follow-up items

   Handoff block (passed as args to `/review` in step 5). Schema is defined in `~/.claude/skills/_shared/handoff-block.md`. Required fields:

   ```
   handoff:
     files:
       - path: <relative path>
         change: <one line: what changed and why>
         why:                        # from the coder's WHY: lines; omit if none
           - lines: <start>-<end>
             note: <why this block looks the way it does>
     tests-run: <from the test-writer's report: exact command + exit code; or "none">
     flagged: <issues the coder or test-writer explicitly flagged, incl. UNDERSPECIFIED and resolved FAILING-TEST outcomes, or "none">
     plan_impact: <verbatim PLAN-IMPACT block + the user's decision, or "none">
     iter: 1
   ```

   **Then surface the `WHY:` lines to the human** (skip entirely when every coder reported `WHY: none`). They go in the phase summary, grouped by file as `path:start-end — <note>`.

   This is a one-way channel to the human, not an input to review. Do NOT put review-relevant caveats here and nowhere else — anything the reviewer needs belongs in `flagged`.

5. **Auto-dispatch review**: After summarizing the coder output, tell the user: "Auto-dispatching review to check the implementation before committing." Then dispatch the loop directly — `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"` (unpinned), passing `mode: review-first`, `caller: code`, `lane: <lane>` (from step 2), the handoff block from step 4, and any `+fast`/`+deep` modifier plus any specialist flag (`+sec`/`+perf`/`+smell`/`no-specialist`).

   **Pass `reviewers: <domains>` verbatim from this phase's Phase Status line** (`plan-format.md`), when it has one. The loop's Step 6b unions plan-declared ∪ force flag (`+sec`/`+perf`/`+smell`) ∪ diff trigger; `no-specialist` suppresses the pass.

   Do NOT `Skill`-invoke `/review` here — that re-injects its body into this context once per phase; it stays the user-facing entry for manual review.

   **Route on the returned `status`** — first match wins:
   - **`plan-impact`** → raise the modal exactly as step 4's PLAN-IMPACT gate (record in `## Plan Deviations`), then re-dispatch `review-loop` with the decision and BOTH counters preserved (`iter` and `spec_iter`).
   - **`critical-blocker`** → STOP. Present `blockers`, do NOT mark the phase done, do NOT advance.
   - **`cap-reached`** → STOP. Report `findings_remaining`. Do NOT mark the phase done. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`deferred`** → one-round budget spent, residue logged for branch exit. A NORMAL completion: render as `converged`, plus `findings_remaining` under `### Deferred to branch exit`. Record convergence and proceed. Do NOT re-dispatch to chase them.
   - **`converged`** → render the packet (`### Fixed` from `fixed[]`, blockers first and marked; `perf[]` under its own heading; `skipped_fp[]`, `nit[]`). Present `ask[]` and wait — never auto-fix. After the user answers, log one row per ask (PLAN-IMPACT asks excluded — the Deviations entry is their record); telemetry never blocks:

     ```bash
     bash "$HOME/.claude/skills/review/log-review-finding" kind=finding \
       repo="$(basename "$(git rev-parse --show-toplevel)")" branch="$(git branch --show-current)" \
       lane=<lane> scope=phase phase=<N> iter=<handoff iter> \
       gate=<entry gate> disposition=ask class=<entry class> file=<path> line=<n> \
       actioned=ask ask_outcome=<accepted|rejected|modified> desc="ask resolved: <one line>"
     ```

     Rows carrying `ask_outcome` are resolutions, not new findings — excluded from yield counts (see `/audit review`). Then `bash ~/.claude/scripts/review-gate-mark clean` and proceed to the phase gates.

6. **Multi-phase plans only — apply the phase-boundary decision**: If step 2 detected a multi-phase plan, after `review-loop` returns `converged` (or `deferred`, which advances the same way) and the phase gates are clean, run the **Phase-boundary decision** (step 2) to choose stop vs. auto-advance. Any other status (`plan-impact`, `critical-blocker`, `cap-reached`) is a STOP — never advance a phase on an unconverged loop. On a STOP, print the matching phase-complete block with all placeholders resolved and wait; when the user confirms (in-session by default — `/clear` only if context genuinely got heavy), re-enter step 2 for the next phase, using the `## Phase Status` section (fallback: `git status` + success criteria) to detect what's already done. On an AUTO-ADVANCE, print the one-line advance notice and re-enter step 2 immediately for the next phase in the same context.

## Phase-Complete Block

After each phase + review + phase gates, the **Phase-boundary decision** (step 2) selects one of three blocks.

**Deliver every block through the `brief` skill's shape** (`~/.claude/skills/brief/SKILL.md`): verdict + blockers + one decision owed up front; queue, gate evidence, and verification lists held back until asked. The blocks below define what must EXIST at the boundary; `brief` decides what prints unasked.

**A — Auto-advance** (decision rule 5). No sign-off is requested; do not stop:

```
Phase <N> complete — machine gates green (review ✓, execution ✓, automated-verification ✓). Risk: low. Manual verification: <n> agent-verified, <m> human-only deferred to the /verify packet.
→ Auto-advancing to Phase <N+1> in-session (no /clear; interrupt anytime).
```

Then re-enter step 2 for Phase <N+1> in the same context — do not wait for the user.

**B — Stop for sign-off** (decision rules 2–4):

```
Phase <N> complete. Risk: <high | low — Phase 1 calibration | low — exception>. Phase-level sign-off requested.

Behavior delta (what the system now does):
- <1–3 lines: system now does X instead of Y. Narrative — no paths, no line numbers.>

Read first (/stage queue, blast-radius order):
  ESCALATE:
  - <path> — <classifier reason>
  READ / SKIM:
  - <path>
Staged mechanically (<n>) — invariant-verified, skip.

Agent-verified (evidence in the plan):
- <item — one-line evidence summary>

Human-only verification remaining:
- <item 1>
- <...>

Next:
  1. Read the queue; spot-check the evidence lines; run the human-only items.
  2. Before advancing, state in one line what this phase makes the system do. Can't → you have not read enough; go back to the queue.
  3. Stage what you've read, then confirm to continue to Phase <N+1> — in-session (no /clear needed; /clear only if context got heavy).

Or give feedback now for revisions to Phase <N>.
```

**C — Last phase** (decision rule 1): print block B's walkthrough and verification lists, then replace its "Next" block with:

```
All phases complete. Next: /verify (completeness + review packet; includes the remaining human-only checks), then you open the PR.
```

Resolution rules:

- `<N>` is the just-finished phase number; `<N+1>` the next.
- `<plan-path>` is the absolute or repo-relative path the orchestrator was invoked with.
- Verification items come from the just-finished phase's `#### Manual Verification:` section in the plan, split by the verifier agent's `agent-verified` / `human-only` tags. If that section is empty in block B, omit both lists and replace step 1 with: "Read the /stage queue."
- No risk tag (older plan format) → treat as high, per the phase-boundary decision list above. Stated there, not here.

### The walkthrough (blocks B and C)

**Skill-invoke `/stage` to build the sign-off walkthrough** — do not rank files yourself.

`/stage` runs the deterministic classifier: it stages the SAFE tier (mechanical,
invariant-verified) and returns everything else as an ESCALATE / READ / SKIM queue
in blast-radius order. That queue **is** the "Read first" section — render it, never
re-rank it, never promote a tier.

- **Behavior delta** — from the coder's handoff (absent one, derive from the diff and mark `derived from diff`).
- **Read first** — `/stage`'s queue, verbatim, in its order. When the user steps the queue ("next"), `nvim-jump` each entry per `~/.claude/skills/_shared/nvim-jump.md`.
- **Active recall** — render the "Next" block's recall prompt, never answer it for the user.

Two fences:

- **Never feed this ordering into a reviewer dispatch.** It renders only after
  `review-loop` returns `converged`, and only to the user.
- **This is not situating.** It maps the phase's own diff so the user can read and
  stage it. It does not open the unchanged neighbours — situating the change in
  the code that did not change is `/orient`, run on demand.

For complex features requiring design decisions, use `/eng-spec` instead.

## Task

$ARGUMENTS
