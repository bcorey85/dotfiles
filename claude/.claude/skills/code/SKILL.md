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

2. **Detect multi-phase plans (MANDATORY check)**: If the task input is a path to a plan file (e.g., `*-plan.md` under `docs/eng-specs/`) or pasted plan content, read it and check whether it contains multiple `## Phase N:` sections.

   **Lane provenance (for telemetry, one-time)**: `lane=eng-spec` when the task input came from step 0's resolver (task directory `spec.md`, or a legacy flat plan file); `lane=code` otherwise (direct dispatch, no plan). Carry this value into the `review-loop` dispatch (step 6).

   **If it's a multi-phase plan:**
   - Do NOT dispatch all phases at once.
   - Identify the next un-executed phase by reading the plan's `## Phase Status` section: the first unchecked (`- [ ]`) entry is the phase to dispatch. This is the source of truth across `/clear` boundaries — do NOT scan git log or diff to figure out where you are. If the plan has no `## Phase Status` section (older plan format), fall back to `git status` + per-phase success criteria, but flag this to the user so they can backfill the section.
   - Dispatch the coder for THAT ONE PHASE ONLY. The coder must run the phase's "Automated Verification" gate (typically `npm run validate` or equivalent) before returning.
   - After the coder completes and you summarize, auto-dispatch `/review` (step 6).
   - **Phase gate (drift + behavioral, ONE agent)** — after `/review` converges, before marking the phase done: dispatch ONE `general-purpose` agent (`model: "sonnet"`) with ONLY the plan path, the phase number, and the handoff file list. It does two jobs in sequence, in one context (they consume the same plan + diff — never spawn them separately):
     1. **Drift reconciliation (read-only)**: verdict each of the phase's `Success Criteria` items `done` / `partial` / `missing` against the actual diff (file:line evidence). If the plan has an `Acceptance Stubs` section, verify stub-sentence survival: every stub sentence must still exist — as a todo or as a real test bearing that name; a reworded or deleted stub is tampering, reported as `missing`. This is the phase-scoped version of `/verify` — it catches plan drift while it is still phase-sized. Any `partial`/`missing` → report and STOP; skip job 2 (don't behavioral-test a drifted phase).
     2. **Behavioral verification (terminal-only)** — only if job 1 is clean and the phase has `Manual Verification` items: execute every item it can drive from the terminal — curl the endpoint, run the CLI, execute the scenario command. **NO browser driving of any kind** (no Playwright, no browser MCP): anything UI-level is tagged `human-only` — UI smoke testing is the user's job, fed by the smoke-test checklist `/verify` emits at branch end. It records results by editing the plan in place: `- [x] agent-verified: <item> — <evidence: command + observed result>`, or `- [ ] human-only: <item> — <why it can't be driven>`. It never checks an item without captured evidence — observed output, not asserted success.

     **Write scope (hard fence)**: its ONLY permitted edits are the Manual Verification checkbox lines above. It changes NO code and never touches Success Criteria, Acceptance Stubs, or Phase Status — a gap-finder that can rewrite its own bar isn't a gate. Gaps from job 1: do NOT mark the phase done; dispatch `/fix` once with the gaps as the issue list, then re-run job 1 once (job 2 after, if newly clean). Still dirty → stop and hand the remaining gaps to the user. Human-only remainders accumulate for the end-of-feature review packet (`/verify`).

   - **Test-intent gate (bug-pinning only)** — only when `git diff --name-only` for this phase hits a test file. Dispatch `test-intent-reviewer` (pinned; omit `model`) with the phase's `Success Criteria` and `Acceptance Stubs` as the intent oracle, scoped to **bug-pinning only**: does each changed assertion pin INTENDED behavior, or codify whatever the implementation happens to do? The oracle is sharpest here — a phase's criteria are specific in a way a whole ticket against a five-phase diff is not — and the cost is asymmetric: a test that pins a bug at phase 2 becomes the bar phases 3..N are built to satisfy. **The cull half (test spam, `COVERAGE-LOST`) does NOT run here** — both are cross-phase properties (a duplicate test across phases 2 and 4 is invisible from inside either; a test deleted in phase 1 and replaced in phase 3 would false-positive), so `/branch-recap` owns them at the Recap closing phase. `weak`/`bug-pinning` verdicts → `/fix`, then re-run the execution gate. Do NOT mark the phase done on an open verdict.
   - After peer review passes AND the drift gate is clean, mark the phase done in the plan: `Edit` the `## Phase Status` section to flip `- [ ] Phase N: ...` → `- [x] Phase N: ...`. This single Edit is the durable record of progress — it survives `/clear` and lets in-session re-entry detect the next phase.
   - **Phase-boundary decision** — the phase is done; now decide stop vs. auto-advance, checking these in order (first match wins), then print the matching Phase-Complete Block:
     1. **Last phase** → STOP; print the completion footer (block C).
     2. **Phase 1**, any risk tier → STOP for **calibration** (block B). Cheapest place to catch the coder — and the plan's risk tagging — drifting from intent before phases 2..N build on it.
     3. **A gate needed an exception, a `/fix` loop hit its cap, or the coder flagged an ambiguity**, any tier → STOP (block B).
     4. **`(risk: high)`** — and an untagged phase counts as high → STOP for phase-level sign-off (block B).
     5. Otherwise — genuinely **`(risk: low)`** with all machine gates green → **AUTO-ADVANCE in-session** (block A): print the one-line advance notice, then re-enter step 2 for the next phase. Do NOT `/clear` and do NOT wait — subagent isolation keeps the main-loop context lean, so the coder's heavy context never lands here; the user can interrupt at any boundary.
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
   - Pass the full task description and any relevant context
   - Instruct it to follow existing patterns in the codebase
   - Tests follow coder-core's test budget: flip acceptance stubs first; any further tests must trace to a plan criterion or named edge case — never exhaustive per-function coverage
   - Flag any ambiguities or issues
   - If the task turns out to be architectural, have it report back and recommend `/eng-spec` instead

5. **After coder(s) complete**, summarize for the user AND build a handoff block for downstream review.

   **PLAN-IMPACT gate (before anything else in this step)**: scan the coder report for a `PLAN-IMPACT:` block (coder-core requires `PLAN-IMPACT: yes` as the report's last line when one exists). If present, present it via **AskUserQuestion** — assumed → found → what changes, options `Adopt plan change` / `Keep plan as written` / `Discuss` — BEFORE summarizing or auto-dispatching `/review`. A plan-impact finding folded into a prose summary is a protocol violation: the modal (and its attention-hook notification) is what makes the finding unskippable. Record the answer in the plan's `## Plan Deviations` section (create if absent) so `/verify` reconciles against the amended plan.

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
     tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
     flagged: <issues the coder explicitly flagged, or "none">
     plan_impact: <verbatim PLAN-IMPACT block + the user's decision, or "none">
     iter: 1
   ```

   The handoff lets the reviewer skip rediscovery — file scope, change intent, and test status are upstream context the reviewer no longer has to reconstruct via `git diff` and full re-reads. Coders already know all of this; pass it forward instead of forcing re-discovery.

6. **Auto-dispatch peer review**: After summarizing the coder output, tell the user: "Auto-dispatching review to check the implementation before committing." Then dispatch the loop directly — `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"` (unpinned), passing `mode: review-first`, `caller: code`, `lane: <lane>` (from step 2), the handoff block from step 5, and any `+fast`/`+deep` modifier plus any specialist flag (`+sec`/`+perf`/`+smell`/`no-specialist`). The loop's Step 6b runs the security/perf/smell specialists automatically on their deterministic triggers; the flags only force or suppress that pass.

   Do NOT `Skill`-invoke `/review` here. That re-injects its body into this context once per phase; dispatching the agent keeps the loop's instructions in a subagent context that costs this one nothing. `/review` remains the user-facing entry point for manual review and dispatches the same agent.

   This runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

   **Route on the returned `status`** — first match wins:
   - **`plan-impact`** → raise the **AskUserQuestion** modal (assumed → found → what changes; `Adopt plan change` / `Keep plan as written` / `Discuss`), record the answer in the plan's `## Plan Deviations` section, then re-dispatch `review-loop` with the decision and the returned `iter` preserved. The agent cannot raise a modal; this routing is why.
   - **`critical-blocker`** → STOP. Present `blockers`, do NOT mark the phase done, do NOT advance.
   - **`cap-reached`** → STOP. Report `findings_remaining`. Do NOT mark the phase done. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`converged`** → render the packet — `### Findings by severity` from `fixed[]`, then `perf[]` under its own heading, then `medium.fix`/`medium.skip` and `low[]`. Present `medium.ask` and `test_intent.ask` to the user and wait; never auto-fix either. Then proceed to the phase gate.

7. **Multi-phase plans only — apply the phase-boundary decision**: If step 2 detected a multi-phase plan, after `review-loop` returns `converged` and the drift gate passes, run the **Phase-boundary decision** (step 2) to choose stop vs. auto-advance. Any other status (`plan-impact`, `critical-blocker`, `cap-reached`) is a STOP — never advance a phase on an unconverged loop. On a STOP, print the matching phase-complete block with all placeholders resolved and wait; when the user confirms (in-session by default — `/clear` only if context genuinely got heavy), re-enter step 2 for the next phase, using the `## Phase Status` section (fallback: `git status` + success criteria) to detect what's already done. On an AUTO-ADVANCE, print the one-line advance notice and re-enter step 2 immediately for the next phase in the same context.

## Phase-Complete Block

After each phase + review + drift gate, the **Phase-boundary decision** (step 2) selects one of three blocks. Print the matching block verbatim with `<N>`, `<N+1>`, `<plan-path>`, and lists filled in.

**A — Auto-advance** (decision rule 5: genuinely `(risk: low)`, all machine gates green, not Phase 1, not the last phase, no exception/cap/ambiguity). No sign-off is requested; do not stop:

```
Phase <N> complete — machine gates green (review ✓, execution ✓, drift ✓, behavioral ✓). Risk: low. Manual verification: <n> agent-verified, <m> human-only deferred to the /verify packet.
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
re-rank it, never promote a tier. A model verdict that licenses the user to skip
reading semantic changes is the exact trade `/stage` was written to refuse; ranking
by judgment here would smuggle it back in.

- **What changed** — one line per changed file: the path and what the phase did to
  it, in the coder's terms (from the handoff; absent one, `git diff --stat` and mark
  it `derived from diff`). Not a hunk summary.
- **Read first** — `/stage`'s queue, verbatim, in its order. SAFE-tier files are
  already staged and do not appear.

Two fences:

- **Never feed this ordering into a reviewer dispatch.** It renders only after
  `review-loop` returns `converged`, and only to the user. Pre-labelling files
  "low priority" for a reviewer anchors it into skimming exactly where quiet bugs
  survive — the same rule `/orient`'s attention map carries.
- **This is not `/orient`.** It maps the phase's own diff so the user can read and
  stage it. It does not open the unchanged neighbours, and it does not replace the
  branch-wide Orient closing phase, which is the only pass that builds the system
  model across phases.

For complex features requiring design decisions, use `/eng-spec` instead.

## Task

$ARGUMENTS
