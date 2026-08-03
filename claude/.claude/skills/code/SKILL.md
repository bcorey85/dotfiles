---
name: code
description: Dispatch coder subagent(s) for implementation, then auto-run `/review` — auto-detects scope or accepts be/fe/fs modifier. Use for "implement/build/add X" when the task is well-defined or a plan file exists; features needing design decisions go to /eng-spec first.
allowed-tools: [Agent, Bash, Read, Edit, Glob, Grep, AskUserQuestion, Skill]
---

# Code

Dispatch coder subagent(s) to implement code directly without architectural planning.

## Modifiers

- `be` or `backend` — force backend-only scope
- `fe` or `frontend` — force frontend-only scope
- `fs` or `fullstack` — force fullstack scope
- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). `+fast` for trivial tasks (renames, typos, one-liners); `+deep` for complex tasks requiring deeper reasoning.

## Instructions

0. **Resolve task input when no arguments were given**: If `$ARGUMENTS` is empty (after stripping any bare modifiers like `be`/`fe`/`fs`/`+fast`/`+deep`), run `bash ~/.claude/scripts/resolve-task-dir.sh` (it infers the ticket from the branch name):
   - Exit 0 (eng-spec task directory) → the task input is its `spec.md`. Exit 5 (legacy flat eng-spec plan file) → the printed file is the task input. Either way, tell the user what resolved; step 2's multi-phase detection then applies.
   - Exit 3 (multiple matches) → ask which via AskUserQuestion. Exit 4 (nothing resolvable) → ask the user what to implement. Do not guess a task.

1. **Check for modifiers**: If `+deep` is present, swap each coder for its `-deep` variant and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

   **Coder tier is the caller's call, not the risk tag's** — a `(risk: high)` phase does NOT auto-select the `-deep` coder. Use `+deep` deliberately on a phase you judge dangerous.

2. **Detect multi-phase plans (MANDATORY check)**: If the task input is a path to a plan file (e.g., `*-plan.md` under `docs/plans/`) or pasted plan content, check whether it contains multiple `## Phase N:` sections.

   **Detect and read by section, never by whole file.** `rg -n '^## ' <plan>` answers the multi-phase question AND gives you every section's line number in one call — do not `Read` the plan to count headings. From there, read phase-scoped per `~/.claude/skills/_shared/plan-reading.md`. Pasted plan content is already in context; scoping applies only to paths.

   **Lane provenance (for telemetry, one-time)**: `lane=eng-spec` when the task input came from step 0's resolver (task directory `spec.md`, or a legacy flat plan file); `lane=code` otherwise (direct dispatch, no plan). Carry this value into the `review-loop` dispatch (step 6).

   **If it's a multi-phase plan:**
   - Do NOT dispatch all phases at once.
   - Identify the next un-executed phase by reading the plan's `## Phase Status` section: the first unchecked (`- [ ]`) entry is the phase to dispatch. This is the source of truth across `/clear` boundaries — do NOT scan git log or diff to figure out where you are. If the plan has no `## Phase Status` section (older plan format), fall back to `git status` + per-phase success criteria, but flag this to the user so they can backfill the section.
   - Dispatch the coder for THAT ONE PHASE ONLY. The coder must run the phase's "Automated Verification" gate (typically `npm run validate` or equivalent) before returning. **Re-read the phase's Phase Status line before dispatching** — its `(risk: …)` tag drives the phase-boundary decision (step 2) and its `(reviewers: …)` list is passed through to the review loop (step 6). Both are properties of the phase, not of the invocation, so they can differ from the previous phase's.
   - After the coder completes, dispatch the `test-writer` (step 4b); after it returns and you summarize, auto-dispatch `/review` (step 6).
   - **Vacuous-green pre-flight (YOU run this, with `Bash`, in this session)** — before any gate agent, when this phase touched a test file or the test-writer reported a test command as evidence. **Never dispatch an agent for it** — not `Explore`, not `general-purpose`, not a gate agent (`mechanical-check-gate` denies any `Agent` call whose description names a vacuity/pre-flight task, so the block is the reminder):

     ```bash
     bash ~/.claude/scripts/vacuous-green-preflight.sh both '<the test-writer's tests-run command>' <changed test files>
     ```

     (Use `cmd` or `files` when only one applies.) It detects three shapes of test that pass without exercising anything: a `-run`/`-k`/`-t` filter selecting zero tests, a test whose body never calls the symbol it is named for (Go/Python test functions; TS/JS `describe()` blocks), and a guard asserting on a literal fragment of the source it guards. Exit 1 → treat every `SUSPECT` as an open finding and route it to `/fix` **before** the test-intent gate runs; an intent gate reading a vacuous suite is measuring nothing. Exit 0 → read the `what was actually checked` block, because a clean result on an unsupported language is a no-op, not a pass. **Exit 2 (usage error, or `rg` missing) → the check DID NOT RUN.** Say so and fix the invocation; never advance to the phase gate on it.

   - **No per-phase `plan-verifier`.** Plan↔diff reconciliation runs ONCE, at branch end, from `/verify`. Here, YOU check before marking the phase done: the phase's `#### Automated Verification` commands actually ran and passed (coder evidence), and its `#### Manual Verification` items go on the deferred list for `/verify`. A phase with no Success Criteria is a plan defect, not a pass — say so before advancing.

   - **Test-intent gate (bug-pinning only)** — only when `git diff --name-only` for this phase hits a test file. Dispatch `test-intent-reviewer` (pinned; omit `model`) with the phase's `Success Criteria` and `Acceptance Stubs` as the intent oracle, scoped to **bug-pinning only**: does each changed assertion pin INTENDED behavior, or codify whatever the implementation happens to do? **The cull half (test spam, `COVERAGE-LOST`) does NOT run here** — both are cross-phase properties, so `/branch-recap` owns them at the Recap closing phase. `weak`/`bug-pinning` verdicts → re-dispatch `test-writer` with the verdict (assertions are its scope, and it stays implementation-blind while rewriting them); route to `/fix` only when the finding implicates src. Then re-run the execution gate. Do NOT mark the phase done on an open verdict. Log the firing so yield stays computable (non-blocking; on failure mention and continue): `bash "$HOME/.claude/skills/review/log-review-metrics" repo=<repo> lane=phase-gate test_intent_ran=1 test_intent=<finding count>`.
   - After peer review passes AND the phase's Automated Verification is green, mark the phase done in the plan: `Edit` the `## Phase Status` section to flip `- [ ] Phase N: ...` → `- [x] Phase N: ...`. This single Edit is the durable record of progress — it survives `/clear` and lets in-session re-entry detect the next phase.
   - **Phase-boundary decision** — the phase is done; now decide stop vs. auto-advance, checking these in order (first match wins), then print the matching Phase-Complete Block:
     1. **Last phase** → STOP; print the completion footer (block C).
     2. **Phase 1**, any risk tier → STOP for **calibration** (block B). 3. **A gate needed an exception, a `/fix` loop hit its cap, or the coder flagged an ambiguity**, any tier → STOP (block B).
     3. **`(risk: high)`** — and an untagged phase counts as high → STOP for phase-level sign-off (block B).
     4. Otherwise — genuinely **`(risk: low)`** with all machine gates green → **AUTO-ADVANCE in-session** (block A): print the one-line advance notice, then re-enter step 2 for the next phase. Do NOT `/clear` and do NOT wait — the user can interrupt at any boundary.
   - If the plan has only one phase or no phase headers, treat it as a single dispatch (skip the phase loop).

3. **Determine scope**:
   - If a scope modifier (`be`, `fe`, `fs`) was provided, use that
   - Otherwise, analyze the task description — read referenced files, check relevant directories — and determine if this is frontend, backend, both, or neither (non-web repo: CLI tool, library, scripts, infra, config)

4. **Dispatch the appropriate coder(s)**:

   **Frontend only** → Launch a single `frontend-coder` subagent
   **Backend only** → Launch a single `backend-coder` subagent
   **Both** → Launch both in parallel using a single message with multiple Agent tool calls
   **Neither** (non-web repo) → Launch a single `coder` subagent — the frontend/backend split only applies to web-fullstack codebases

   For each coder:
   - Pass the full task description and any relevant context. **When the task is a phase of a multi-phase plan, name the phase explicitly** ("implement Phase 4 of `<plan-path>`") and tell the coder to read it phase-scoped (`coder-core`'s workflow step 1 carries the mechanics).
   - Instruct it to follow existing patterns in the codebase
   - Coders write NO tests (coder-core's "Tests Are Not Yours") — stub flips and all test authorship happen in step 4b's `test-writer` dispatch
   - Flag any ambiguities or issues
   - If the task turns out to be architectural, have it report back and recommend `/eng-spec` instead

4b. **Dispatch the test-writer** (after every coder dispatch that implemented plan behavior): a single `test-writer` subagent (pinned; omit `model`). Skip ONLY when the task/phase has no Success Criteria behavior and no Acceptance Stubs (pure config or mechanical phases) — note the skip in the phase summary.

Pass the plan path + phase number (it reads phase-scoped) and the stub file list when the plan names one. **Pass NOTHING from the coder** — the agent is implementation-blind by contract: no diff, no coder summary, no source file contents in its prompt. Its assertions must come from the plan alone; feeding it the implementation reintroduces the bug-pinning failure the split exists to remove.

Route on its report:

- `FAILING-TEST` lines → candidate implementation bugs, the split working as designed. Dispatch `/fix` scoped to make the named behaviors pass WITHOUT touching the failing tests' assertions, then re-run the test-writer's `tests-run` command yourself with Bash. Cap: 2 fix rounds; still red → STOP and surface to the user.
- `UNDERSPECIFIED` lines → surface in the phase summary; a success criterion left untested by one blocks marking the phase done (plan gap — treat like a missing Success Criteria section, step 2).

5. **After coder(s) and the test-writer complete**, summarize for the user AND build a handoff block for downstream review.

   **PLAN-IMPACT gate (before anything else in this step)**: scan the coder report for a `PLAN-IMPACT:` block (coder-core requires `PLAN-IMPACT: yes` as the report's last line when one exists). If present, present it via **AskUserQuestion** — assumed → found → what changes, options `Adopt plan change` / `Keep plan as written` / `Discuss` — BEFORE summarizing or auto-dispatching `/review`. Record the answer in the plan's `## Plan Deviations` section (create if absent) so `/verify` reconciles against the amended plan.

   User summary:
   - What was implemented
   - Any issues flagged
   - Any follow-up items

   Handoff block (passed as args to `/review` in step 6). Schema is defined in `~/.claude/skills/_shared/handoff-block.md`. Required fields:

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

6. **Auto-dispatch peer review**: After summarizing the coder output, tell the user: "Auto-dispatching review to check the implementation before committing." Then dispatch the loop directly — `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"` (unpinned), passing `mode: review-first`, `caller: code`, `lane: <lane>` (from step 2), the handoff block from step 5, and any `+fast`/`+deep` modifier plus any specialist flag (`+sec`/`+perf`/`+smell`/`no-specialist`).

   **Pass `reviewers: <domains>` verbatim from this phase's Phase Status line** (`plan-format.md`), when it has one. This is the PRIMARY dispatch signal for `security-reviewer` — its diff trigger is deliberately narrow. The loop's Step 6b unions plan-declared ∪ force flag (`+sec`/`+perf`/`+smell`) ∪ diff trigger; `no-specialist` suppresses the pass.

   Do NOT `Skill`-invoke `/review` here — that re-injects its body into this context once per phase. `/review` remains the user-facing entry point for manual review and dispatches the same agent.

   This runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

   **Route on the returned `status`** — first match wins:
   - **`plan-impact`** → raise the **AskUserQuestion** modal (assumed → found → what changes; `Adopt plan change` / `Keep plan as written` / `Discuss`), record the answer in the plan's `## Plan Deviations` section, then re-dispatch `review-loop` with the decision and BOTH returned counters preserved (`iter` and `spec_iter`). The agent cannot raise a modal; this routing is why.
   - **`critical-blocker`** → STOP. Present `blockers`, do NOT mark the phase done, do NOT advance.
   - **`cap-reached`** → STOP. Report `findings_remaining`. Do NOT mark the phase done. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`converged`** → render the packet — `### Findings by severity` from `fixed[]`, then `perf[]` under its own heading, then `medium.fix`/`medium.skip` and `low[]`. Present `medium.ask` to the user and wait; never auto-fix an ask item. Then record convergence — `bash ~/.claude/scripts/review-gate-mark clean` (only ever on a `converged` packet) — and proceed to the phase gates.

7. **Multi-phase plans only — apply the phase-boundary decision**: If step 2 detected a multi-phase plan, after `review-loop` returns `converged` and the phase gates are clean, run the **Phase-boundary decision** (step 2) to choose stop vs. auto-advance. Any other status (`plan-impact`, `critical-blocker`, `cap-reached`) is a STOP — never advance a phase on an unconverged loop. On a STOP, print the matching phase-complete block with all placeholders resolved and wait; when the user confirms (in-session by default — `/clear` only if context genuinely got heavy), re-enter step 2 for the next phase, using the `## Phase Status` section (fallback: `git status` + success criteria) to detect what's already done. On an AUTO-ADVANCE, print the one-line advance notice and re-enter step 2 immediately for the next phase in the same context.

## Phase-Complete Block

After each phase + review + phase gates, the **Phase-boundary decision** (step 2) selects one of three blocks. Print the matching block verbatim with `<N>`, `<N+1>`, `<plan-path>`, and lists filled in.

**A — Auto-advance** (decision rule 5: genuinely `(risk: low)`, all machine gates green, not Phase 1, not the last phase, no exception/cap/ambiguity). No sign-off is requested; do not stop:

```
Phase <N> complete — machine gates green (review ✓, execution ✓, automated-verification ✓). Risk: low. Manual verification: <n> agent-verified, <m> human-only deferred to the /verify packet.
→ Auto-advancing to Phase <N+1> in-session (no /clear; interrupt anytime).
```

Then re-enter step 2 for Phase <N+1> in the same context — do not wait for the user.

**B — Stop for sign-off** (decision rules 2–4: `(risk: high)` or untagged; OR Phase 1 calibration regardless of tier; OR any tier where a gate needed an exception, a fix loop hit its cap, or the coder flagged an ambiguity):

```
Phase <N> complete. Risk: <high | low — Phase 1 calibration | low — exception>. Phase-level sign-off requested.

What changed:
- <path> — <one-line change intent>

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
  2. Stage what you've read, then confirm to continue to Phase <N+1> — in-session (no /clear needed; /clear only if context got heavy).

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
- **No risk tag (older plan format) → treat as high** (block B).

### The walkthrough (blocks B and C)

This is what the user reads to sign off on the phase and decide what to stage.
**Skill-invoke `/stage` to build it** — do not rank files yourself.

`/stage` runs the deterministic classifier: it stages the SAFE tier (mechanical,
invariant-verified) and returns everything else as an ESCALATE / READ / SKIM queue
in blast-radius order. That queue **is** the "Read first" section — render it, never
re-rank it, never promote a tier.

- **What changed** — one line per changed file: the path and what the phase did to
  it, in the coder's terms (from the handoff; absent one, `git diff --stat` and mark
  it `derived from diff`). Not a hunk summary.
- **Read first** — `/stage`'s queue, verbatim, in its order. SAFE-tier files are
  already staged and do not appear.

Two fences:

- **Never feed this ordering into a reviewer dispatch.** It renders only after
  `review-loop` returns `converged`, and only to the user.
- **This is not `/orient`.** It maps the phase's own diff so the user can read and
  stage it. It does not open the unchanged neighbours, and it does not replace the
  branch-wide Orient closing phase.

For complex features requiring design decisions, use `/eng-spec` instead.

## Task

$ARGUMENTS
