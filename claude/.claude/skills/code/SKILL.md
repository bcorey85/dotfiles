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

   **`(risk: high)` phases take the `-deep` coder automatically** — no modifier needed, and an untagged phase counts as high (same rule the phase-boundary decision uses at step 2). `+fast` does not override this; a high-risk phase is exactly where the cheap tier is wrong. Measured basis: across four arms implementing one frozen plan, Class-1 data-loss detection tracked **who wrote the phase**, not who reviewed it — the single arm that used `coder-deep` on the high-risk phase scored 4/4, the three that used plain `coder` scored 2/4, 1/4, 0/4, and the best of those three ran the fewest fix rounds. Review depth did not substitute: the 1/4 arm ran 6 fix dispatches to the 4/4 arm's 2. Do NOT raise the review tier on the same reasoning — nothing measured shows it helps here.

2. **Detect multi-phase plans (MANDATORY check)**: If the task input is a path to a plan file (e.g., `*-plan.md` under `docs/plans/`) or pasted plan content, check whether it contains multiple `## Phase N:` sections.

   **Detect and read by section, never by whole file.** `rg -n '^## ' <plan>` answers the multi-phase question AND gives you every section's line number in one call — do not `Read` the plan to count headings. From there, read phase-scoped per `~/.claude/skills/_shared/plan-reading.md`: the shared sections plus the ONE phase you are dispatching, skipping every sibling `## Phase N:` section, via `Read` with `offset`/`limit`. On a 12-phase plan that is ~60% less file, paid on every phase — and this context holds the plan for the whole ticket, so it is the one read that compounds. Pasted plan content is already in context; scoping applies only to paths.

   **Lane provenance (for telemetry, one-time)**: `lane=eng-spec` when the task input came from step 0's resolver (task directory `spec.md`, or a legacy flat plan file); `lane=code` otherwise (direct dispatch, no plan). Carry this value into the `review-loop` dispatch (step 6).

   **If it's a multi-phase plan:**
   - Do NOT dispatch all phases at once.
   - Identify the next un-executed phase by reading the plan's `## Phase Status` section: the first unchecked (`- [ ]`) entry is the phase to dispatch. This is the source of truth across `/clear` boundaries — do NOT scan git log or diff to figure out where you are. If the plan has no `## Phase Status` section (older plan format), fall back to `git status` + per-phase success criteria, but flag this to the user so they can backfill the section.
   - Dispatch the coder for THAT ONE PHASE ONLY. The coder must run the phase's "Automated Verification" gate (typically `npm run validate` or equivalent) before returning. **Re-read the risk tag per phase and apply step 1's tier rule to THIS phase** — `(risk: high)` or untagged → the `-deep` coder variant, `model` omitted. The tier is a property of the phase, not of the invocation, so it can differ from the previous phase's.
   - After the coder completes and you summarize, auto-dispatch `/review` (step 6).
   - **Vacuous-green pre-flight (YOU run this, with `Bash`, in this session)** — before any gate agent, when this phase touched a test file or the coder reported a test command as evidence. **Never dispatch an agent for it** — not `Explore`, not `general-purpose`, not a gate agent (`mechanical-check-gate` denies any `Agent` call whose description names a vacuity/pre-flight task, so the block is the reminder):

     ```bash
     bash ~/.claude/scripts/vacuous-green-preflight.sh both '<the coder's test command>' <changed test files>
     ```

     (Use `cmd` or `files` when only one applies.) It detects three shapes of test that pass without exercising anything: a `-run`/`-k`/`-t` filter selecting zero tests, a test whose body never calls the symbol it is named for (Go/Python test functions; TS/JS `describe()` blocks), and a guard asserting on a literal fragment of the source it guards. Exit 1 → treat every `SUSPECT` as an open finding and route it to `/fix` **before** the phase gate runs; a drift gate reading a vacuous suite is measuring nothing. Exit 0 → read the `what was actually checked` block, because a clean result on an unsupported language is a no-op, not a pass. **Exit 2 (usage error, or `rg` missing) → the check DID NOT RUN.** Say so and fix the invocation; never advance to the phase gate on it. An unhandled exit 2 is the same failure the coverage block exists to prevent, one level up: a check that never ran, reading as a check that passed.

     This runs mechanically rather than as an instruction to a gate agent for one measured reason: the instance it was built for got past the test-intent gate, the drift gate, and a human analyst in the same phase, and was caught by a coder mid-fix. A class that survives three oracles needs a check that cannot forget.

     **And this paragraph, on its own, did not hold.** Measured across one full arm: the orchestrator read it and dispatched a haiku `Explore` agent named "Phase N vacuous-green preflight" anyway — three times, ~32k output tokens, **zero invocations of the script**. Each returned an impression of the test files that read downstream as a clean pre-flight, reproducing the check's own failure mode (did-not-run indistinguishable from passed) one level up in the dispatcher. Hence the hook. A stated rationale is not an instruction.

   - **Phase gate (drift + behavioral, ONE agent)** — after `/review` converges and the pre-flight is clean, before marking the phase done: dispatch `plan-verifier` (pinned; omit `model`) with `scope: phase <N>` and exactly three things — the plan path, the phase number, and the handoff file list. Nothing else. Its whole contract (phase-scoped reading, the two jobs and their ordering, the acceptance-stub survival check, the no-browser rule, the write fence) lives in its agent file; re-stating any of it in the dispatch is spend that buys nothing, and a paraphrase that drifts from the agent file is worse than nothing.

     Acting on what it returns:
     - **Drift gaps** (`partial`/`missing`) → do NOT mark the phase done. Dispatch `/fix` once with the gaps as the issue list, then re-dispatch `plan-verifier` once. Still dirty → stop and hand the remaining gaps to the user.
     - **`N/A — no Success Criteria`** → the gate did not run. That is a plan defect, not a pass: surface it to the user before advancing, and do not print "drift ✓".
     - **`human-only` items** accumulate for the end-of-feature review packet (`/verify`). Never drive them yourself — UI smoke testing is the user's.

   - **Test-intent gate (bug-pinning only)** — only when `git diff --name-only` for this phase hits a test file. Dispatch `test-intent-reviewer` (pinned; omit `model`) with the phase's `Success Criteria` and `Acceptance Stubs` as the intent oracle, scoped to **bug-pinning only**: does each changed assertion pin INTENDED behavior, or codify whatever the implementation happens to do? The oracle is sharpest here — a phase's criteria are specific in a way a whole ticket against a five-phase diff is not — and the cost is asymmetric: a test that pins a bug at phase 2 becomes the bar phases 3..N are built to satisfy. **The cull half (test spam, `COVERAGE-LOST`) does NOT run here** — both are cross-phase properties (a duplicate test across phases 2 and 4 is invisible from inside either; a test deleted in phase 1 and replaced in phase 3 would false-positive), so `/branch-recap` owns them at the Recap closing phase. `weak`/`bug-pinning` verdicts → `/fix`, then re-run the execution gate. Do NOT mark the phase done on an open verdict. Log the firing so yield stays computable (non-blocking; on failure mention and continue): `bash "$HOME/.claude/skills/review/log-review-metrics" repo=<repo> lane=phase-gate test_intent_ran=1 test_intent=<finding count>`.
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
   - Pass the full task description and any relevant context. **When the task is a phase of a multi-phase plan, name the phase explicitly** ("implement Phase 4 of `<plan-path>`") and tell the coder to read it phase-scoped — shared sections plus Phase 4 only, skipping sibling phases (`coder-core`'s workflow step 1 carries the mechanics). A coder handed a bare plan path reads all twelve phases to find its one.
   - Instruct it to follow existing patterns in the codebase
   - Tests follow the test budget in `~/.claude/skills/_shared/test-authoring.md` (coder-core points to it): flip acceptance stubs first; any further tests must trace to a plan criterion or named edge case — never exhaustive per-function coverage
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
         why:                        # from the coder's WHY: lines; omit if none
           - lines: <start>-<end>
             note: <why this block looks the way it does>
     tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
     flagged: <issues the coder explicitly flagged, or "none">
     plan_impact: <verbatim PLAN-IMPACT block + the user's decision, or "none">
     iter: 1
   ```

   The handoff lets the reviewer skip rediscovery — file scope, change intent, and test status are upstream context the reviewer no longer has to reconstruct via `git diff` and full re-reads. Coders already know all of this; pass it forward instead of forcing re-discovery.

   **Then emit the Hunk sidecar** (skip entirely when every coder reported `WHY: none`). Collect the `WHY:` lines from all coder reports and `Write` them to `.git/hunk-agent-context.json` — inside `.git`, never the worktree, because a sidecar in the tree shows up as an untracked file inside the diff it annotates:

   ```json
   {
     "version": 1,
     "summary": "<one line: what this phase did, for the human about to read it>",
     "files": [
       {
         "path": "<relative path>",
         "summary": "<the file's `change` line>",
         "annotations": [
           { "newRange": [<start>, <end>], "summary": "<the WHY note>", "rationale": "<expand only if the note needs it>", "author": "<coder agent type>" }
         ]
       }
     ]
   }
   ```

   `hunk-review` (bound to `prefix h`) picks this up automatically and renders the notes by default; `a` in the TUI toggles them off. Write it fresh each phase — it describes the current unstaged diff, and a stale sidecar annotates code that has since moved. Files with no annotations may be omitted: Hunk renders `annotations[]` only, so a file entry without them contributes nothing.

   This is a one-way channel to the human, not an input to review. Do NOT put review-relevant caveats here and nowhere else — anything the reviewer needs belongs in `flagged`.

6. **Auto-dispatch peer review**: After summarizing the coder output, tell the user: "Auto-dispatching review to check the implementation before committing." Then dispatch the loop directly — `Agent` with `subagent_type: "review-loop"`, `model: "sonnet"` (unpinned), passing `mode: review-first`, `caller: code`, `lane: <lane>` (from step 2), the handoff block from step 5, and any `+fast`/`+deep` modifier plus any specialist flag (`+sec`/`+perf`/`+smell`/`no-specialist`). The loop's Step 6b runs the security/perf/smell specialists automatically on their deterministic triggers; the flags only force or suppress that pass.

   **When step 1's tier rule made this phase's coder `-deep`, also pass `fix_tier: deep`.** That deepens the loop's FIX coder only, leaving every reviewer at its normal tier — a phase written deep and then patched shallow is not a deep phase, and the fix rounds are where the defects this rule exists for actually get resolved. Do NOT pass `+deep` for this purpose; that raises the review tier too, which the measurement does not support.

   Do NOT `Skill`-invoke `/review` here. That re-injects its body into this context once per phase; dispatching the agent keeps the loop's instructions in a subagent context that costs this one nothing. `/review` remains the user-facing entry point for manual review and dispatches the same agent.

   This runs AFTER all coders have completed and the summary is presented. For parallel fullstack dispatches, both coders finish before this step runs — that is the correct sequencing.

   **Route on the returned `status`** — first match wins:
   - **`plan-impact`** → raise the **AskUserQuestion** modal (assumed → found → what changes; `Adopt plan change` / `Keep plan as written` / `Discuss`), record the answer in the plan's `## Plan Deviations` section, then re-dispatch `review-loop` with the decision and BOTH returned counters preserved (`iter` and `spec_iter`). The agent cannot raise a modal; this routing is why.
   - **`critical-blocker`** → STOP. Present `blockers`, do NOT mark the phase done, do NOT advance.
   - **`cap-reached`** → STOP. Report `findings_remaining`. Do NOT mark the phase done. The session is correctly left `dirty`, so `git commit` stays blocked.
   - **`converged`** → render the packet — `### Findings by severity` from `fixed[]`, then `perf[]` under its own heading, then `medium.fix`/`medium.skip` and `low[]`. Present `medium.ask` to the user and wait; never auto-fix an ask item. Then record convergence — `bash ~/.claude/scripts/review-gate-mark clean` (only ever on a `converged` packet) — and proceed to the phase gate.

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
