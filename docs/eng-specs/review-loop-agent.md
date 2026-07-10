# Review-Loop Agent: Eliminate Orchestrator Re-Injection

> Jira: none
> Context sources: conversation (measurements taken 2026-07-09), live harness spike
> Date: 2026-07-09

## Summary

Every `Skill` invocation re-injects that skill's full `SKILL.md` body into the persistent orchestrator context as a tool result. `skills/code/SKILL.md:99` instructs the orchestrator to `Skill`-invoke `/review`, and the multi-phase loop at `:101` re-enters that step once per phase — so `review/SKILL.md` (17,007 bytes) lands in context N times for an N-phase plan. Subagent bodies, by contrast, land in fresh throwaway contexts and cost the orchestrator nothing: `agents/code-reviewer.md` is the largest file in the toolkit at 19,318 bytes and is effectively free.

This spec extracts the review-fix convergence loop into a `review-loop` **agent**, and reduces `/code`, `/review`, and `/fix` to thin callers. One loop implementation, three callers. Per-phase orchestrator cost for a review drops from ~4.2k tokens to the size of a returned verdict.

## Decisions

### Decision 1: The loop lives in an agent; `/review` becomes a wrapper

- **Choice**: Extract the review-fix loop into `agents/review-loop.md`, granted the `Agent` tool so it can dispatch `code-reviewer` and fix coders itself. `/code` dispatches it per phase; `/review` shrinks to a thin wrapper that dispatches the same agent.
- **Reasoning** (owner: User): Words in agent bodies are free; words in orchestrator skills are paid on every invocation. A loop agent moves 16.8 KB from the paid side to the free side. Keeping `/review` as a second implementation would recreate the duplication the toolkit currently does not have anywhere. (Confirmed by the user after the pattern was stated explicitly.)
- **Alternatives rejected**:
  - *Inline-once* (`_shared/review-loop.md` read at phase 1, followed from context on phases 2..N): smallest diff and touches no enforcement config, but nothing mechanically enforces that phase 4 still follows instructions read at phase 1. Pure adherence, no mechanism.
  - *Loop agent for `/code` only*: preserves live fix-loop narration for typed `/review`, at the cost of two implementations of one loop that will drift.
- **Trade-off accepted**: When the user types `/review`, the fix loop runs inside a subagent, so they see a returned summary rather than a live narration of each iteration. Observability is traded for context.

### Decision 2: Plan-impact is handled by abort-and-return

- **Choice**: When the reviewer emits a `PLAN-IMPACT:` block, the loop agent stops immediately, dispatches no coder, and returns `status: plan-impact` with the verbatim block and the current `iter`. The orchestrator raises the `AskUserQuestion` modal, then re-dispatches the loop agent with the user's decision and the preserved `iter`.
- **Reasoning** (owner: User): `AskUserQuestion` cannot reach the user from inside a subagent — a hard harness invariant. Today `/review` raises the modal *before* `/fix` dispatches, so the user decides before any coder acts. Abort-and-return is the only option that preserves that ordering.
- **Alternatives rejected**:
  - *Fix-then-surface* (loop runs to convergence, plan-impact surfaced at the end): inverts the ordering. Coders will have rewritten code against an unapproved plan change, so "Keep plan as written" degrades into reverting shipped edits.
  - *Pre-scan in the orchestrator* (orchestrator runs iteration 1's reviewer itself): raises the modal earliest, but splits the loop across two homes — the orchestrator retains the dispatch and split-threshold rules, so `review/SKILL.md` shrinks far less.
- **Trade-off accepted**: One extra `review-loop` dispatch on the plan-impact path. That path is rare, and the dispatch is cheap relative to a wrong fix.
- **Hard ordering requirement (gate-critical)**: the `iter >= 3` cap check MUST fire *before* dispatching what would be the final nested `code-reviewer`, mirroring `review/SKILL.md:19-20`'s current step-1 ordering. See the `cap-reached` contract below — violating this ordering silently unblocks `git commit` on unresolved findings.

### Decision 3: `/fix` becomes a wrapper over the same agent

- **Choice**: `review-loop` takes a `mode` parameter. `mode=review-first` (callers: `/code`, `/review`) reviews, then fixes to convergence. `mode=fix-first` (callers: `/fix`, and transitively `/cc` and `/verify`) dispatches coders against supplied findings, then reviews to convergence.
- **Reasoning** (owner: User): The loop agent must dispatch fix coders regardless, which is exactly what `/fix` does today. Giving the agent a mode parameter means one loop implementation exists anywhere in the system; `/cc` and `/verify` keep calling `/fix` and notice no change.
- **Alternatives rejected**:
  - *Loop agent owns fix; `/fix` keeps its own copy*: two implementations of one loop, guaranteed drift.
  - *Loop agent `Skill`-invokes `/fix` internally*: elegant, and `/fix`'s body would land free in the subagent context — but it depends on a subagent being able to invoke the `Skill` tool, which is **unverified**. Rejected rather than gamble the design on it.
- **Trade-off accepted**: `review-loop.md` grows a mode branch, making it the single most complex agent in the toolkit. That complexity is paid in a free context.

### Decision 4: `review-loop` logs its own invocations

- **Choice**: `review-loop` appends one line to `~/.claude/skill-usage.jsonl` per run, matching `log-skill-use.sh`'s existing `{ts, skill, via, repo}` schema, with `skill: "review-loop"`, `via: "agent"`, plus a new `caller: code|review|fix` field. `/skill-audit`'s exempt-list note is updated in the same phase.
- **Reasoning** (owner: User): `log-skill-use.sh` is a `PostToolUse` hook on the **`Skill`** tool (`settings.json:209-216`). Replacing `/code`'s `Skill`-invoke with an `Agent` dispatch makes it blind to the model-path review and fix runs — 26 + 14 events in the trailing 7 days. Without this, `/skill-audit` reads `review` and `fix` as untriggered and recommends retiring the two most-used skills in the toolkit. Logging from the agent also yields a strictly better signal than today: `caller` distinguishes user-typed reviews from chained ones, which the current `via: model|user` split cannot.
- **Alternatives rejected**:
  - *Accept the gap and document it* (add `review`/`fix` to `/skill-audit`'s exempt list, as `coder-core` is today): zero cost, but permanently destroys the invocation count that justified this entire refactor.
  - *Keep the `Skill`-invoke purely for logging* (`/code` → `Skill(review)` → `Agent(review-loop)`): telemetry untouched, but re-introduces a per-phase Skill injection (~2 KB × N) and recovers only most of the saving.
  - *Call `log-skill-use.sh` from the agent*: *not possible.* Verified — the script reads hook JSON from stdin and has no CLI argument handling (`scripts/log-skill-use.sh:14-30`). The agent must append the line directly.
- **Trade-off accepted**: `skill-usage.jsonl` gains a second writer. `log-skill-use.sh` remains the schema owner; if its fields change, `review-loop` must be updated in lockstep or `/skill-audit` will silently mis-parse. Recorded as a contract below.

## External Contracts

- **Claude Code harness — nested `PostToolUse` propagation.** Verified empirically in this session (2026-07-09): a `code-reviewer` dispatched from inside a `general-purpose` subagent caused `PostToolUse(Agent)` to fire and write `clean` to the **parent session's** state file (`~/.claude/state/review-gate/81dac750-…`), alongside files for the child sessions. **Invariant relied upon**: `review-commit-gate.sh`'s clean signal is a `code-reviewer|code-reviewer-deep|test-intent-reviewer` `subagent_type` dispatch *anywhere in the agent tree*, not only at the top level. **Breakage**: if a future harness release stops propagating nested `PostToolUse` under the parent `session_id`, `/code` will mark the session `dirty` (its coder dispatches are top-level) and the `clean` signal will never arrive — every `git commit` after a `/code` run blocks until the user manually creates the `.skip` override. This is the single assumption the whole design rests on; it is fail-closed, not fail-open.

- **`scripts/review-commit-gate.sh` — no modification required.** Because of the above, the gate keeps working untouched. `review-loop` must NOT be added to its `case` statement: adding it as a clean signal would mark the session clean on dispatch, *before* any reviewer has actually run.

- **`review-commit-gate.sh` — the `cap-reached` ordering invariant (gate-critical).** Today, `review/SKILL.md:19-20` checks `iter >= 3` at the *start* of an invocation and stops without dispatching, so on the non-convergence path the last Agent dispatch in the chain is a **fix coder** → session left `dirty` → `git commit` correctly blocked with findings outstanding. **Invariant**: `review-loop` MUST perform the cap check before dispatching what would be the final nested `code-reviewer`. **Breakage**: if the loop instead reviews, discovers non-convergence, and only then returns `status: cap-reached`, its last nested dispatch is a `code-reviewer`, which (per the propagation contract above) writes `clean` to the parent session — leaving `git commit` **unblocked while HIGH/CRITICAL findings remain unresolved**. This inverts the gate using the very mechanism this design depends on. The same reasoning applies to the `plan-impact` abort path: it returns *after* a reviewer ran and *before* any coder ran, so `clean` is correct there — unreviewed coder work does not exist at that moment.

- **`scripts/log-skill-use.sh` → `~/.claude/skill-usage.jsonl` → `/skill-audit`.** The hook is `PostToolUse` on the **`Skill`** tool (`settings.json:209-216`); it has no CLI interface (stdin JSON only, `log-skill-use.sh:14-30`). **Invariant**: `/skill-audit` reads `{ts, skill, via, repo}`, one JSON object per line, and filters entries against the skills directory. **Breakage**: Phase 3 removes the only `Skill`-invoke of `review` on the model path (and Decision 3 removes it for `fix`), so both vanish from telemetry and `/skill-audit` recommends retiring them. Mitigated by Decision 4 — `review-loop` appends its own line. `log-skill-use.sh` remains the schema owner; the two writers must stay in lockstep. `/skill-audit`'s exempt-list note (which currently says `fix` and `review` "DO log via the model path") becomes false and is corrected in Phase 1.

- **`AskUserQuestion` cannot originate in a subagent.** Invariant. Breakage: a plan-impact finding raised inside `review-loop` would be silently swallowed. Decision 2 exists solely to honor this.

- **`~/.claude/review-metrics.jsonl` and `~/.claude/second-draft.jsonl`** — consumed by `/review-stats` to compute convergence, false-positive rate, and first-draft smell distribution. **Invariant**: one JSON object per line, field names unchanged. Writes are plain `bash` (`skills/review/log-review-metrics`) against the same filesystem, so they behave identically from inside the loop agent. **Breakage**: `/review-stats` miscomputes or crashes.

- **`scripts/agent-model-guard.sh`** — enforces "pinned agent → omit `model`; unpinned → `sonnet` for implementation/analysis". `review-loop` will be **unpinned**, so every call site passes `model: "sonnet"`. **Breakage**: a pinned `review-loop` with `model` passed at the call site is hook-blocked.

- **`skills/review/SKILL.md` "Handoff Block" schema** — `/code:84` and `/fix` both produce it and reference `review/SKILL.md` as its definition. Moving the loop means the schema's home must move too (to the agent, or to `_shared/`), or those cross-references dangle.

**Nothing in this spec performs a destructive or irreversible operation**, and no decision leaves credentials, secrets, or user data alive past a removal intent. The `.skip` override file is the only state consumed-on-use, and it is untouched.

## Plan Deviations

| Date | Finding | Decision | Owner |
| --- | --- | --- | --- |
| 2026-07-09 | Phase 2 review (governance): `review-loop` holds `Write`+`Edit` for the perf vault log, and used them to edit source files — including its own definition — instead of dispatching a fix coder. `review-commit-gate.sh` marks the session `dirty` only on a `coder*` dispatch, so code changed while the gate read `clean`. The agent can silently disarm the gate it exists to feed. | **Fence the write scope — advisory only.** `Write`/`Edit` permitted only under `~/vault/` (the perf log); every source edit must go through an `Agent` coder dispatch, restoring dirty-marking. Implemented as prose in the agent's What-NOT-to-do section, which is **not enforcement**. Mechanizing it requires a `write-edit-safety-gate` rule (enforcement config → `/deep-plan` lane) and depends on an unverified hook payload field: no hook currently reads a calling-agent identity. Deferred to `docs/backlog/review-loop-write-fence.md`. | User |
| 2026-07-09 | Phase 1 review (HIGH): the return packet carries `medium`, `low`, and `perf`, but no field carries the *descriptions* of the CRITICAL/HIGH findings the loop finds and auto-fixes — only counts reach `review-metrics.jsonl`. The wrapper renders "Findings by severity" from a field that does not exist. Pre-refactor, `/review` presented the full reviewer report by severity (`git show HEAD:.../review/SKILL.md:64`). As written, the loop would silently repair real bugs and never name them. | **Adopt plan change.** Add `fixed: [{severity, finding, file_line}]` to the return packet, populated from the CRITICAL/HIGH each fix coder resolves; the wrapper renders it under "Findings by severity". | User |
| 2026-07-09 | Phase 1 review (MEDIUM): `skill-audit/SKILL.md:20`'s corrected note claims both `review` and `fix` are agent-dispatched. True for `review` after Phase 1; false for `fix`, whose Phase 1 diff was only a pointer retarget. | **Land Phase 2 in the same change** so the note is true when it ships. | User |
| 2026-07-09 | The spec's return contract accounted for 1 of 4 points where the review loop must reach the user. `review/SKILL.md:84-90` (critical blockers needing user judgment), `:105-113` (MEDIUM triage `ask` bucket), and `:100-102` (test-intent `ask` items) would have been silently swallowed by a loop agent that could only return `converged \| plan-impact \| cap-reached`. The contract also omitted the execution gate (`:92`), the perf-findings vault log (`:66-75`), and the post-convergence `no-review` `/fix` dispatch (`:111`). | **Adopt plan change.** The loop agent owns everything through convergence *and* the post-convergence steps, returning one structured packet; the thin wrapper renders it and raises the modals. Return contract expanded with a `critical-blocker` status plus `blockers`, `medium`, `test_intent`, and `perf` fields. | User |

## Approach

- **Agent** (`agents/review-loop.md`, new): owns the `iter` counter and 3-iteration convergence cap, reviewer continuity via `SendMessage` on `iter ≥ 2`, the parallel-split threshold (>5 files AND ~300+ changed lines), the second-order LSP call-site sweep, the handoff-block schema, metrics logging, self-logging to `skill-usage.jsonl` (Decision 4), and coder dispatch for fixes. `tools:` must include `Agent`, `Bash`, `Read`, `Glob`, `Grep`, `LSP`, `SendMessage`. Unpinned model.
- **Loop ordering (gate-critical, from Decision 2)**: each iteration is `check cap → (if capped: return cap-reached WITHOUT dispatching a reviewer) → dispatch reviewer → scan for PLAN-IMPACT → (if found: return plan-impact WITHOUT dispatching a coder) → dispatch fix coder → iter++`. The two early returns are what keep `review-commit-gate` honest.
- **Return contract** (the only thing the orchestrator pays for). Amended per Plan Deviations 2026-07-09 — carries all four user-interaction points:
  ```
  status: converged | plan-impact | cap-reached | critical-blocker
  iter: <n>
  fixed: [{severity, finding, file_line}]  # CRITICAL/HIGH the loop resolved — rendered by the wrapper
  blockers: [<one line each>]              # status=critical-blocker; needs user judgment, no /fix
  findings_remaining: [<one line each>]    # status=cap-reached
  plan_impact: <verbatim PLAN-IMPACT block>  # status=plan-impact
  medium: {fix: [], skip: [{item, reason}], ask: []}   # classified by the agent; wrapper presents `ask`
  test_intent: {ran: <bool>, fix: [], ask: []}         # `ask` never auto-fixed
  perf: [{finding, principle, file_line}]              # wrapper renders under its own heading
  files_touched: [<path>]
  low: [<one line each>]                               # report-only, never auto-handled
  load_bearing_clean: <one line, or omitted>           # high-blast-radius file that came back clean
  ```
  The agent CLASSIFIES `medium` into fix/skip/ask and performs the `fix` bucket itself (one `no-review` coder dispatch); the wrapper only PRESENTS `skip` inline and raises `ask`. Perf findings are appended to the vault log by the agent (iteration 1 / manual only) and additionally returned so the wrapper can surface them under `### Perf findings`.
- **`/review`**: parse args → dispatch `review-loop` with `mode=review-first` → if `status=plan-impact`, raise the modal and re-dispatch → present the verdict.
- **`/fix`**: same, with `mode=fix-first` and the supplied findings.
- **`/code`**: replace the `Skill`-invoke at `:99` with an `Agent` dispatch of `review-loop`; keep the coder-report PLAN-IMPACT gate at `:67` exactly as it is (that one is about the *coder's* report, not the reviewer's, and already runs in the main session).

## Dependencies

- No external packages. No new scripts. `skills/review/log-review-metrics` is reused as-is.

## Implementation Plan

## Phase Status

<!-- Updated by /code after each phase completes + review passes. Source of truth for "which phase is next" across /clear boundaries. Do not delete. -->

- [ ] Phase 1: `review-loop` agent + `/review` wrapper (risk: high)
- [ ] Phase 2: `fix-first` mode + `/fix` wrapper (risk: high)
- [ ] Phase 3: `/code` per-phase dispatch + plan-impact abort-and-return (risk: high)
- [ ] Phase 4: Refactor pass — /refactor cleanup sweep (risk: low)
- [ ] Phase 5: Verify pass — branch-wide deep review + /verify (plan↔diff + smoke list) (risk: high)
- [ ] Phase 6: Orient pass — /orient situate the change (risk: low)
- [ ] Phase 7: Finalize — /adr durable decision record (risk: low)

## Current State Analysis

`skills/code/SKILL.md:99` — "invoke the `/review` skill via the Skill tool with `skill: \"review\"`". `:101` re-enters step 2 per phase. `skills/review/SKILL.md:16-157` is a 142-line Instructions block whose six numbered steps carry the loop's responsibilities: the `iter` cap, reviewer continuity, the split threshold, the LSP call-site sweep, the handoff schema, metrics logging, and `/fix` dispatch. `agents/code-reviewer.md` (19,318 B) already lives in a free context and needs no change. Measured 2026-07-09, post-edit: `review/SKILL.md` 17,007 B; `code/SKILL.md` 13,779 B; `fix/SKILL.md` 7,046 B. A 3-phase plan costs ~79 KB (~19,700 tokens) of orchestrator instruction text, ~34 KB of it the same review body pasted twice more.

## Desired End State

`review/SKILL.md` under 3,500 bytes; `fix/SKILL.md` under 3,500 bytes; zero `Skill`-invocations of `review` from `code/SKILL.md`; `agents/review-loop.md` exists with `Agent` in its tools; `review-commit-gate.sh` byte-identical to its pre-change state; `git commit` still succeeds after a `/code` run; `/review-stats` still parses both JSONL files.

## What We're NOT Doing

- Rewording any skill for brevity (measured: only 4 shared lines across code/review/fix/refactor/coder-core — there is no prose duplication to remove).
- Touching `/peer-review`.
- Changing what `code-reviewer` flags, or its calibration.
- Modifying `review-commit-gate.sh` or `agent-model-guard.sh`.
- Shrinking `agents/code-reviewer.md` — it is correctly large, in a free context.

## Implementation Approach

Build the agent first and prove it against the *simplest* caller (`/review`, typed by hand) before wiring the two automated callers. Each phase leaves the toolkit in a working state: after Phase 1 `/code` still uses its old `Skill`-invoke path, so nothing is broken mid-flight.

## Phase 1: `review-loop` agent + `/review` wrapper

### Overview

Create the agent, move the loop into it, reduce `/review` to a dispatcher. `/code` is untouched and keeps working via its existing `Skill`-invoke.

### Changes Required:

#### 1. New loop agent

**File**: `claude/.claude/agents/review-loop.md`
**Changes**: New. Frontmatter: `name: review-loop`, terse description (`"Runs the review→fix convergence loop. Dispatched by /review, /fix, /code."`), no `model:` key (unpinned), `tools: Agent, Bash, Read, Glob, Grep, LSP, SendMessage`. Body: verbatim relocation of `review/SKILL.md:16-157`, plus the `mode` branch stub (`review-first` only in this phase) and the return contract above. Implement the loop ordering from the Approach section exactly — **cap check before the would-be final reviewer dispatch**, plan-impact abort before any coder dispatch. Add the Decision 2 abort-and-return rule.

#### 1b. Self-logged telemetry (Decision 4)

**File**: `claude/.claude/agents/review-loop.md`
**Changes**: As its first action, append one line to `~/.claude/skill-usage.jsonl` matching `log-skill-use.sh`'s schema — `{"ts":"<ISO8601Z>","skill":"review-loop","via":"agent","repo":"<basename of git toplevel>","caller":"<code|review|fix>"}`. Direct `jq`/`printf` append; the script has no CLI interface.

#### 1c. Correct `/skill-audit`'s exempt-list note

**File**: `claude/.claude/skills/skill-audit/SKILL.md`
**Changes**: The note claiming `fix` and `review` "DO log via the model path" becomes false once Phase 3 lands. Replace with: the loop is dispatched as the `review-loop` agent and self-logs with `via: "agent"`; count those lines, and read `caller` to separate chained runs from user-typed ones.

#### 2. `/review` becomes a wrapper

**File**: `claude/.claude/skills/review/SKILL.md`
**Changes**: Reduce to: frontmatter, Modifiers, a ~20-line Instructions block that parses args, dispatches `review-loop` (`model: "sonnet"`, `mode=review-first`), handles `status: plan-impact` by raising `AskUserQuestion` and re-dispatching, and presents the verdict. Keep the "Plan-impact findings (unskippable routing)" section — it now describes what the *orchestrator* does with a returned block. Move the "Handoff Block" schema to `_shared/handoff-block.md` and reference it from both the agent and `/code:84`.

### Success Criteria

#### Automated Verification:

- [ ] **Size-verified**: `test $(wc -c < ~/.claude/skills/review/SKILL.md) -lt 3500`
- [ ] **Agent-exists-verified**: `test -f ~/.claude/agents/review-loop.md && grep -qE '^tools:.*Agent' ~/.claude/agents/review-loop.md`
- [ ] **Unpinned-verified**: `! grep -qE '^model:' ~/.claude/agents/review-loop.md`
- [ ] **Gate-untouched-verified**: `git diff --quiet -- claude/.claude/scripts/review-commit-gate.sh claude/.claude/scripts/agent-model-guard.sh`
- [ ] **No-dangling-refs-verified**: `! grep -rn 'review/SKILL.md.*Handoff Block' ~/.claude/skills/`
- [ ] **Cap-ordering-verified**: the agent body states the cap check precedes the reviewer dispatch — `grep -qiE 'cap check.*before.*(reviewer|dispatch)' ~/.claude/agents/review-loop.md`
- [ ] **Telemetry-verified**: `grep -q 'skill-usage.jsonl' ~/.claude/agents/review-loop.md`
- [ ] **Exempt-note-verified**: `! grep -q 'DO log via the model path' ~/.claude/skills/skill-audit/SKILL.md`

#### Manual Verification:

- [ ] **Manual-verified**: type `/review` on a small working diff; confirm findings are returned and the session's gate file flips to `clean` — `cat ~/.claude/state/review-gate/$SESSION`
- [ ] **Manual-verified**: force a plan-impacting finding; confirm the `AskUserQuestion` modal appears **before** any coder subagent is dispatched (human-only: requires watching the dispatch order)
- [ ] **Manual-verified**: drive the loop to `iter=3` without converging; confirm the gate file reads `dirty` and `git commit` is **blocked** — this is the gate-critical `cap-reached` path (human-only: requires staging a non-converging diff)
- [ ] **Manual-verified**: after one `/review`, `tail -1 ~/.claude/skill-usage.jsonl` shows `"skill":"review-loop","via":"agent","caller":"review"` and `jq -e .` parses it

## Phase 2: `fix-first` mode + `/fix` wrapper

### Overview

Add the `fix-first` branch to the agent and reduce `/fix`. `/cc` and `/verify` call `/fix` and must observe no behavior change.

### Changes Required:

#### 1. Agent gains `fix-first`

**File**: `claude/.claude/agents/review-loop.md`
**Changes**: Add the `mode=fix-first` branch — dispatch coders against supplied findings first, then enter the review loop at `iter=1`.

#### 2. `/fix` becomes a wrapper

**File**: `claude/.claude/skills/fix/SKILL.md`
**Changes**: Reduce to arg parsing + `review-loop` dispatch with `mode=fix-first`, plus the same plan-impact re-dispatch handling as `/review`.

### Success Criteria

#### Automated Verification:

- [ ] **Size-verified**: `test $(wc -c < ~/.claude/skills/fix/SKILL.md) -lt 3500`
- [ ] **Mode-verified**: `grep -q 'fix-first' ~/.claude/agents/review-loop.md`
- [ ] **Callers-intact-verified**: `git diff --quiet -- claude/.claude/skills/cc/SKILL.md claude/.claude/skills/verify/SKILL.md`

#### Manual Verification:

- [ ] **Manual-verified**: run `/cc` against a `claude-comments.md` with one comment; confirm it routes through `/fix` → `review-loop` and converges
- [ ] **Manual-verified**: run `/verify` on a plan with a known gap; confirm its `/fix` offer still works

## Phase 3: `/code` per-phase dispatch

### Overview

Replace `/code`'s `Skill`-invoke of `/review` with an `Agent` dispatch of `review-loop`. This is the phase that actually realizes the token saving.

### Changes Required:

#### 1. `/code` step 6

**File**: `claude/.claude/skills/code/SKILL.md`
**Changes**: At `:99`, replace the `Skill` invocation with `Agent(subagent_type: "review-loop", model: "sonnet", mode: "review-first", …handoff)`. Handle `status: plan-impact` (raise modal, re-dispatch) and `status: cap-reached` (STOP, do not advance the phase). Leave the coder-report PLAN-IMPACT gate at `:67` untouched. Update `:84`'s handoff-schema reference to `_shared/handoff-block.md`.

### Success Criteria

#### Automated Verification:

- [ ] **No-skill-invoke-verified**: `! grep -q 'skill: "review"' ~/.claude/skills/code/SKILL.md`
- [ ] **Dispatch-verified**: `grep -q 'review-loop' ~/.claude/skills/code/SKILL.md`
- [ ] **Gate-still-untouched-verified**: `git diff --quiet -- claude/.claude/scripts/review-commit-gate.sh`

#### Manual Verification:

- [ ] **Manual-verified**: run `/code` against a real 2-phase plan; confirm phase 2's review adds only a verdict (not a 16.8 KB body) to the orchestrator transcript (human-only: requires reading the transcript)
- [ ] **Manual-verified**: after that `/code` run, `git commit` is NOT blocked by `review-commit-gate` — the nested reviewer wrote `clean`
- [ ] **Manual-verified**: `/review-stats` still parses `review-metrics.jsonl` and `second-draft.jsonl` and reports convergence

## Phase 4: Refactor pass — /refactor cleanup sweep (risk: low)

`/refactor` over the code this plan shipped: DRY out duplication between the three wrappers, delete dead scaffolding, tighten names. Cleanup only, no behavior change.

### Success Criteria
- [ ] **Automated**: all Phase 1–3 automated checks still pass.

## Phase 5: Verify pass — branch-wide deep review + /verify (risk: high)

Dispatch ONE `code-reviewer-deep` (omit `model`) over `git diff <base>...HEAD` — the per-loop reviews were phase-scoped; this is the only fresh-eyes look at cross-phase interactions. Then `/verify` to reconcile the shipped diff against this spec and emit the human smoke-test checklist.

### Success Criteria
- [ ] **Automated**: deep review returns no Critical or High findings.
- [ ] **Manual**: reconciliation reports no missing work; smoke-test checklist delivered.

## Phase 6: Orient pass — /orient situate the change (risk: low)

`/orient` to rebuild the map: how `review-loop` connects to the unchanged `code-reviewer`, the coders, and the two hooks.

### Success Criteria
- [ ] **Manual**: orientation summary produced; any surprise coupling surfaced as a follow-up.

## Phase 7: Finalize — /adr durable decision record (risk: low)

`/adr` sourcing the "why" from this spec + the branch diff. The nested-`PostToolUse` finding is the load-bearing fact to record.

### Success Criteria
- [ ] **Manual**: ADR written, pre-merge, shipping in the same PR.
