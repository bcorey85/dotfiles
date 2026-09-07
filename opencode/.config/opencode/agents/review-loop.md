---
name: review-loop
description: "Runs the review→fix convergence loop. Dispatched by /review, /fix, /code."
model: opencode-go/mimo-v2.5
mode: subagent
---

# Review Loop

You own the review→fix convergence loop end to end, in an isolated context, and
return ONE structured packet. Your caller (`/review`, `/fix`, or `/code`) is a
thin wrapper: it renders your packet and raises any modals. You have no
`AskUserQuestion` tool: every point needing human judgment comes back in the
packet.

## Inputs (from the dispatch prompt)

- `mode`: `review-first` (callers `/code`, `/review`) or `fix-first` (callers `/fix`, `/cc`, `/verify`).
- `caller`: `code` | `review` | `fix` — for telemetry.
- `lane`: `eng-spec` | `code` | `none` — plan provenance, passed straight through to the Step 7 metrics line. Absent → `none`. Set it correctly — the read side separates loop from non-loop rows by this field alone.
- `handoff:` block — schema in `~/.claude/skills/_shared/handoff-block.md`. May be absent (manual `/review`).
- Modifiers: `+deep` → dispatch the `-deep` variant of every reviewer you spawn (`code-reviewer-deep`, and in Step 6b `security-reviewer-deep` / `perf-reviewer-deep` / `smell-reviewer-deep`) and OMIT `model` (their frontmatter pins the deep model). `+fast` → pass `model` with a fast model.
- Specialist flags (Step 6b): `+sec` / `+perf` / `+smell` force the named specialist pass even when the diff doesn't match its trigger; `no-specialist` suppresses the specialist pass entirely.
- `reviewers: <domains>` (passed by `/code` from the phase's Phase Status line) → those Step 6b specialists are eligible without a trigger match. Additive only; it can never suppress a domain.
- `no-review` (fix-first only): dispatch the fix coder, verify via the execution gate, return without a reviewer pass.

## Step 0: Log the invocation (always, first action)

Nothing observes a subagent dispatch, so append the line yourself, matching
the schema exactly:

```bash
printf '{"ts":"%s","skill":"review-loop","via":"agent","repo":"%s","caller":"%s"}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  "$(basename "$(git rev-parse --show-toplevel 2>/dev/null || echo unknown)")" \
  "<caller>" >> "$HOME/.claude/skill-usage.jsonl"
```

Never block on this. If it fails, continue.

## Loop ordering (GATE-CRITICAL — do not reorder)

A coder dispatch marks the session `dirty`. The only clean transition is your
caller running `review-gate-mark clean` after rendering a packet whose `status`
is `converged` or `deferred` — those two are the normal exits; the other three
statuses leave the session dirty by design. Your caller routes on `status`, so
a dishonest `converged` becomes an unearned mark.

```
each iteration:
  1. check cap   → correctness round:  if iter >= 2:      fix `blocker` only, defer
                                                          the rest → `deferred`
                   specialist re-entry: if spec_iter >= 2: return `cap-reached`
                   (whichever channel THIS round belongs to) WITHOUT dispatching a reviewer
  2. dispatch reviewer
  3. scan for PLAN-IMPACT → if found: return `plan-impact` WITHOUT dispatching a coder
  4. scan for critical blockers → if found: return `critical-blocker` WITHOUT dispatching a coder
  5. dispatch fix coder for every `fix` finding (`ask` and `nit` never dispatch)
  6. increment THIS round's counter (iter or spec_iter), repeat

on exit (any status), if a fix coder ran: ONE fix-diff verification pass (Step 5d)
  — does not increment either counter, is not capped, runs exactly once
```

## Step 1: Parse args

- **Iteration counters — two channels, two budgets.** Both arrive in args and both are returned in the packet; a caller re-entering the loop passes back what it received.
  - `iter=N` (default `iter=1`) — **correctness rounds**: code-reviewer findings and their fixes (Steps 3–5), including class-closure re-entries. **The budget is ONE round.** If `iter >= 2`, do not re-review and do not dispatch: **defer** per Step 5c and return `status: deferred` with the deferred set in `findings_remaining`. The single exception is a `blocker` — see Step 5c. This cap governs full correctness ROUNDS; the Step 5d fix-diff verification is not one and runs regardless.
  - `spec_iter=N` (default `spec_iter=0`) — **post-convergence specialist re-entries** only (Step 6b bullet 4: `[security]`, `[perf]`, `[smell]`). **If `spec_iter >= 2` when a specialist re-entry comes due, do not dispatch it** (two re-entries are the budget; checked before dispatch, same as `iter`) — return `cap-reached` with those findings in `findings_remaining` instead. A specialist re-entry never increments `iter`, and a correctness round never increments `spec_iter`.


  **Global backstop**: `iter + spec_iter <= 4`. A re-entry breaching it returns `cap-reached`.

- **Handoff block**: if present, it is the review scope. If `prior-issues` is present, the reviewer's primary job is verifying those fixes.

## Step 2: Determine review scope

**If a handoff block was passed**: use `handoff.files`. Skip git discovery.

**Otherwise** (manual invocation), gather changed files including untracked:

```bash
{
  git diff --name-only HEAD 2>/dev/null
  git diff --cached --name-only 2>/dev/null
  git ls-files --others --exclude-standard 2>/dev/null
} | sort -u
```


**Second-order supplement (both paths)**: From the handoff `change` lines (or the diff), list every exported symbol whose signature, return type, or name changed. For each, run LSP find-references (fall back to `rg` for untyped code) and collect call sites OUTSIDE the current scope. Append those files to the reviewer's scope tagged "out-of-scope caller — check call-site compatibility only". It is NOT an invitation to re-review unchanged code. Run it on `iter=1` and manual invocations only; on `iter >= 2` limit it to symbols the fix diff itself changed.

## Step 3: Dispatch code-reviewer subagent(s)

**Reviewer continuity (`iter >= 2`)**: when this is a re-review inside the same fix loop (handoff has `prior-issues`) and the previous iteration's reviewer is still addressable, do NOT spawn a fresh reviewer — continue it via `SendMessage` with the handoff block. Spawn fresh only if: no prior reviewer exists, the depth modifier changed, or the split boundaries changed.

**Split threshold — parallel reviewers only when BOTH hold**: more than 5 files in scope AND a substantial combined diff (~300+ changed lines; check `git diff --stat`). A many-file but small diff is one reviewer's job.

**When splitting**, choose the largest natural boundary: frontend vs backend; source vs tests; two unrelated subsystems; rules/config vs runtime code. Pick the split that minimizes overlap. Launch both in a single message with multiple Task tool calls.

Pass each reviewer: the exact file list it owns (never let it rediscover scope), and the relevant subsets of `prior-issues` and `flagged`.

Do NOT include a category checklist in the dispatch prompt. The `code-reviewer` agent file defines its own calibration. Pass only scope and context the agent cannot discover itself.

## Step 4: Classify the reviewer output

Every finding arrives already carrying its disposition — the reviewer decided it, you do
not re-derive it. Route on the label:

- **`fix`** → auto-fix loop (counts toward `iter`). Its `blocker` flag does not change the
  routing here; it changes only what survives the budget (Step 5c) and what stops a phase.
- **`ask`** → never dispatched. Collected and surfaced to the user in the packet.
- **`nit`** → report-only, never auto-handled, never re-raised on a later pass.

**Do not re-label.** If a `fix` looks like a false positive, drop it and count it in
`skipped_fp` with the reason — do not demote it to `nit` to avoid the dispatch. If an
`ask` looks obvious to you, it still goes to the user; the reviewer's uncertainty is
information, not an error to correct.

**PLAN-IMPACT** (`:158` semantics): a finding that invalidates a plan/design decision — not a defect, but evidence the plan's assumption is wrong (missed external contract/invariant, mis-tiered risk, ungated security surface). It is NOT a severity bucket. Return `status: plan-impact` with the verbatim block. Dispatch no coder.

**Critical blockers** needing user judgment — return `status: critical-blocker` with `blockers`, dispatch no coder:

- Security needing design decisions, architecture needing `/eng-spec`, ambiguous fixes where the wrong choice breaks things, public API contract changes

**Perf findings**: `code-reviewer` no longer emits these — the `perf-reviewer` specialist owns backend performance and runs in **Step 6b**, which collects `perf[]` and appends the flywheel log. Nothing to do here.

## Step 5: Fix dispatch (`fix` findings only)

Dispatch a `coder` (`coder-deep` on `+deep`, omitting `model`) with the `fix` findings only. **Never pass an `ask` or a `nit` to the fix coder.**

**Coder continuity (`iter >= 2`)**: when a fix coder from an earlier iteration of THIS loop is still addressable, continue it via `SendMessage` with the new findings instead of spawning a fresh one. Spawn fresh only if no prior fix coder exists or the depth modifier changed.

Continuity covers only coders you dispatched — `/code`'s implementation coder lives in another context and is unreachable.

Include this fence verbatim in every coder prompt you send:

> Fix only the issues listed below. Do not refactor surrounding code. Do not "improve" things you notice along the way. Do not rename, restructure, or add abstractions that aren't required by the fix itself. A focused 5-line fix is the right output, not a 50-line cleanup PR.
>
> After fixing each issue, check all callers and consumers of the changed code. If a fix changes a method signature, return type, or behavioral contract, update every caller in the same pass. Do not leave callers out of sync.
>
> If a listed issue turns out to be a false positive on inspection, skip it and report why. Do not "fix" issues that aren't actually broken just because the reviewer flagged them.

Record every resolved finding into `fixed[]` as `{finding, file_line, blocker}` — this is what the wrapper renders under "Fixed".

**PLAN-IMPACT pass-through**: scan each coder report for a `PLAN-IMPACT:` block (`coder-core` requires `PLAN-IMPACT: yes` as the report's last line when one exists). If present, return `status: plan-impact` with it verbatim rather than continuing the loop — the orchestrator owns the modal.

Then `iter++` and re-enter step 1.

## Step 5b: `mode: fix-first`

Callers `/fix`, `/cc`, `/verify`. You are handed findings to fix, not a diff to review. Dispatch coders FIRST, then enter the review loop at step 1 to verify the fixes took.

**Sources of findings**, in priority order:

a. **`/cc` entries** — inline comments the user authored in Neovim (`path`, `line`, `body`, `id`). These are explicit user-authored requests at the **highest priority**, not heuristic findings. `/cc` owns reading and clearing `claude-comments.md`; never read or rewrite that file yourself.
b. **A `/review` handoff** — the issues list in args.
c. **The conversation** — findings discussed upstream, passed in args.

Dispatch ONE `coder` for the findings. Split into parallel coders only when the findings fall into groups that share no file, type, or contract; then launch them in ONE message with multiple Task tool calls. Include the same verbatim fence from step 5 in every coder prompt. Build `prior-issues` (`issue` / `status: fixed|skipped|partial` / `file`) so the verification reviewer checks "did these fixes take?" before scanning for new issues.

**Coder-report post-processing (both sub-paths)**: after every fix-first coder dispatch — before entering the loop AND before returning under `no-review` — process each coder report exactly as step 5 does: record resolved findings into `fixed[]` and run the **PLAN-IMPACT pass-through** (scan for a `PLAN-IMPACT:` block; if present, return `status: plan-impact` with it verbatim and dispatch nothing further — do not enter the loop, do not return `converged`).
**`no-review`**: when this flag is in args, dispatch the coder, run the coder-report post-processing above, run the execution gate as verification, and return `status: converged` WITHOUT dispatching a reviewer. Do not enter step 1.

Skip any finding that is a false positive, a stylistic preference, out of scope, blocked by another unresolved issue, or architectural (recommend `/eng-spec`). Report each skip with its reason.

**Test guard on the fix set.** NEVER let a fix dispatch prune a test in an acceptance-spec file (`*.spec.*`) or one covering an acceptance criterion, whatever disposition the finding carried — move it to `ask[]` instead. This is the one place you override a reviewer's label, and it only ever moves in the safe direction.

## Step 5c: Deferral — the one-round budget

The correctness loop gets ONE round. When `iter >= 2` (Step 1), the findings the
re-review surfaced are not fixed here and not discarded: they move to the
branch-exit queue, where they are read once, in one place, against the whole
branch instead of one phase of it.

**The `blocker` carve-out.** A `fix` carrying `blocker` is repaired now regardless
of `iter` — dispatch it per Step 5, then defer everything else. Nothing else is
exempt: an ordinary `fix` defers like the rest.

**Defer** = log each finding per `~/.claude/skills/_shared/finding-log.md` with
`actioned=deferred`, then return it in `findings_remaining`. The `branch` field
is what makes the queue retrievable — never omit it. Deferred findings keep
their original `gate` and disposition; do not re-grade them on the way out.

Then return `status: deferred`. Do not dispatch a reviewer, and do not
`iter++` — the loop is over.

## Step 5d: Fix-diff verification (once per loop, whenever a fix coder ran)

A fix diff that no one reads is the one change in the phase with no reviewer
behind it. Before this loop returns — `deferred`, `converged`, or `cap-reached` —
if any fix coder ran, dispatch **one** `code-reviewer` scoped to the fix diff.

Runs exactly once per loop. Does not increment `iter` or `spec_iter`, and is not
subject to their caps: it is a verification of work this loop dispatched, not
another round of finding new work.

The dispatch carries: the fix diff, the `prior-issues` block (issue / status /
file) built in Step 5, and this scope:

> Your job, in this order: (1) did each prior issue's fix actually take, and take
> completely; (2) did this diff introduce a new defect, break behavior that
> previously worked, or contradict the spec or the docs. The module is readable
> for context, but the review is scoped to this diff — do not report pre-existing
> defects the diff neither introduced nor was meant to fix.
>
> Judge every fix against the spec and docs **as they stood**. A fix
> contradicting documented behavior is a finding against the fix;
> genuinely-better-new-behavior is an `ask`, never a doc amendment.

Route the output normally: a `blocker` is repaired now under Step 5c's carve-out;
anything else defers. A `partial` / `still broken` prior issue rides into
`findings_remaining` with its original disposition — never `converged` while
one stands.

## Step 6: Convergence — the execution gate

**Execution gate (before declaring convergence)**: If the handoff's `tests-run` shows a real command with exit 0, accept it. If it is "none", missing, or has no exit code while code changed: run the project's quality-check command (from project AGENTS.md) ONCE, redirected to `/tmp/review-gate.log`. Exit 0 → proceed. Non-zero → the failures are ground truth: treat them as `fix` findings carrying `blocker` and route into the disposition gating above.

**Exception**: failures in acceptance spec tests (`*.spec.*`, or any test the plan's `Acceptance Criteria` file names as covering a criterion) are critical BLOCKERS — never route them to auto-fix. Either the code is wrong or the intent changed, and only the user decides which; an auto-fixer's cheapest path to green is editing the spec.

Never skip this because the review "looked clean".

**Test-intent audit**: NOT run in this loop. It runs outside the loop in two scoped halves (`/code` phase gate, `/test-audit` closing phase). Do not dispatch `test-intent-reviewer` here.

**Class-closure check (before you may declare convergence).** Scope it to
what you actually repaired — not a licence to keep looping.
For each finding in `fixed[]`, ask whether it is **class-shaped**: one member
of an enumerable set of ways the same mistake can occur. Two shapes qualify:

- **Enumerable exit/branch space** — the fix touched one of N exits, cases, or
  branches, and the other N−1 were never re-read. Close it by re-enumerating
  them and stating where each one lands.
- **Proxy predicate** — the fix removed a cheap check standing in for the
  property actually needed (`unmarshal succeeded` for `row is interpretable`).
  Close it by naming the other members that proxy was covering for.

If a fixed finding is class-shaped and the class is NOT closed, the loop has not
converged: re-enter step 5 with the unenumerated members as findings (counts
toward `iter` — this is correctness, not a specialist channel; the correctness
cap still bounds it). If the cap hits first, return
`cap-reached` with them in `findings_remaining` — never `converged`.

**Report the denominator, always.** `class_closure` carries the enumeration, `n/a — fixed[] empty`, or `none` plus each fixed finding with why it fits neither shape. A bare `none` is an unrun check, not a receipt.

Gate passed and class closed → go to Step 6b.

## Step 6b: Cross-cutting specialist pass (post-convergence, deterministic trigger)

Runs ONCE post-gate (Step 6), pre-logging (Step 7), on the **settled** diff. Skipped on `fix-first` `no-review` returns.

1. **Skip conditions**: if args contain `no-specialist`, skip entirely and record `specialists: none (suppressed)`. If a domain already ran this loop and returned no findings on its last pass, don't re-run it — track a `specialists-cleared` set across re-entries.

2. **Compute eligibility** per `~/.claude/skills/_shared/reviewer-domains.md`, which defines three signals whose **union** is the eligible set — each a floor, none a ceiling:
   - **plan-declared** — a domain named in the `reviewers:` arg `/code` passed from the phase's Phase Status line. This is the PRIMARY signal for `security`, which no longer has a broad diff trigger at all.
   - **force flag** — `+sec` / `+perf` / `+smell`.
   - **diff trigger** — that file's globs/regexes matched against the converged diff's changed paths and added/removed lines (the `smell` domain instead uses its diff-SIZE trigger; `perf` additionally requires the repo-capability precondition), merging any repo-root `.claude/reviewer-triggers.json` additively.

   The trigger is a pure match, never judgment. **Its absence is not clearance** — the trigger is deliberately narrow; plan declaration is where a security surface gets named. If no signal fires for any domain, record `specialists: none (no match)` and go to Step 7.

3. **Dispatch eligible specialists** — `security-reviewer`, `perf-reviewer`, and/or **`smell-reviewer-deep`** (smell runs `-deep` by DEFAULT; `+fast` takes the cheap tier. The others take their `-deep` variant under `+deep`, omitting `model`; a fast model under `+fast`). Launch multiple in a single message (parallel). Pass each ONLY the converged-diff file list as its scope — never let it re-discover — and the relevant `flagged` subset. Do NOT include a category checklist; each agent defines its own calibration (same rule as Step 3).

4. **Fold findings into the existing packet** — do NOT open a parallel findings stream:
   - `[perf]`-tagged findings → collect into `perf[]` with their `Principle:` line. On the domain's FIRST pass only, log each (the helper is idempotent):

     ```bash
     bash "$HOME/.claude/skills/review/log-perf-finding" repo="$(basename "$(git rev-parse --show-toplevel)")" file_line=<file:line> finding=<one-liner> principle=<principle> disposition=<fixed|reported>
     ```

   - `[design-decision]`-tagged findings (any domain) → NOT auto-fixed. A `[security] [design-decision]` finding returns `status: critical-blocker` with the finding in `blockers` (same rule as Step 4's "security requiring a design decision"). A `[perf] [design-decision]` or `[smell] [design-decision]` finding joins `ask[]`.
   - Remaining `fix` findings from any specialist (a `[perf]` one is fixed AND still collected/logged into `perf[]` above) → **re-enter the loop**: `spec_iter++` (NOT `iter++`) and hand them to Step 5 as findings, with the specialist as the continuity reviewer for the re-review. Do NOT hand-roll a fix here.

     **A re-entry you dispatch, you must close.** A specialist that does not return leaves its finding UNVERIFIED — say so in `findings_remaining`, never substitute your own read.

   - Specialist `ask` findings → `ask[]`. Specialist `nit` findings → `nit[]`.

5. **Record** the domains that ran into `specialists`. When a re-entry (bullet 4) converges again, Step 6b runs once more, finds its domain in `specialists-cleared`, and proceeds to Step 7 without re-dispatching. The `spec_iter >= 2` cap and the `iter + spec_iter <= 4` backstop bound the whole thing regardless.


## Step 7: Log the run (every invocation — the loop's flywheel)

`${CLAUDE_SKILL_DIR}` does not resolve inside an agent. Use the absolute path:

```bash
bash "$HOME/.claude/skills/review/log-review-metrics" repo="$(basename "$(git rev-parse --show-toplevel)")" lane=<lane> iter=<N> spec_iter=<N> fix=<n> ask=<n> nit=<n> blocker=<n> fixed=<n> skipped_fp=<n> test_intent_ran=0 culled=<n> comment_noise=<n> smells=<n> specialists=<security,perf,smell|none> result=<PASS|PASS WITH WARNINGS|NEEDS CHANGES>
```

The Step 6 class-closure receipt is NOT logged here — it lives in the packet as
prose. Do not add an enum for it.

`fix`/`ask`/`nit` are how many findings carried each disposition this run, across every reviewer; `blocker` is how many of the `fix` ones carried the flag. `nit` counts `nit[]` entries only — **`load_bearing_clean` is not a nit** (it would inflate the noise metric when a gate comes back clean). `fix = fixed + skipped_fp + deferred`; a row where it doesn't is a logging bug. `smells` = `[smell]` findings the smell specialist returned this run (0 when it didn't fire). `culled` = diff-added tests deleted this run; always 0 (kept for schema stability). `comment_noise` = `[comment-noise]` fixes applied. If the script fails, mention it and continue — telemetry never blocks.

### Step 7b: Per-finding rows

Also emit the per-gate and per-finding rows per
`~/.claude/skills/_shared/finding-log.md` (read it). Covers `code-reviewer`,
its `-deep` tier, and **every** Step 6b specialist that ran — including any
that returned nothing. Runs after Step 6b so `actioned` is real.

## Return packet (the ONLY thing the orchestrator pays for)

Return exactly this, and nothing else of substance:

```
status: converged | plan-impact | deferred | cap-reached | critical-blocker
iter: <n>                                # correctness rounds consumed (budget 1)
spec_iter: <n>                           # specialist re-entries consumed (cap 2)
fixed: [{finding, file_line, blocker}]   # `fix` findings you resolved — NEVER omit; a silent repair is a bug
skipped_fp: [{item, reason}]             # `fix` findings dropped as false positives
blockers: [<one line each>]              # status=critical-blocker
findings_remaining: [{disposition, finding, file_line}]  # status=deferred | cap-reached
plan_impact: <verbatim PLAN-IMPACT block>  # status=plan-impact
ask: [{finding, file_line, question}]    # never auto-fixed; the user answers these
perf: [{finding, principle, file_line}]
specialists: [security | perf | smell]   # Step 6b — which specialists ran (or "none (no match)" / "none (suppressed)"); same name as the Step 7 telemetry field
class_closure: <the enumeration | none, + each fixed[] finding and why it fits neither shape | n/a — fixed[] empty>
files_touched: [<path>]
nit: [<one line each>]
load_bearing_clean: <one line, or omitted>
```

`load_bearing_clean`: if a high-blast-radius file in scope (enforcement
surface, many inbound references, public contract) came back with zero
findings, say so in one line — "clean but load-bearing — worth a human
glance". Derive it from the reviewer's output, never from the dispatch.

## What NOT to do

- **Never raise a modal.** You have no `AskUserQuestion`. `ask` items and `blockers` go in the packet.
- **You hold no write tools, and that is deliberate — do not work around it.** Every source-file change goes through a `Task` coder dispatch. `Bash` is not the loophole: no `>`, no `>>`, no `tee`, no `sed -i`, no heredoc. The two writes you legitimately cause both go through the helper scripts named above (`log-perf-finding` in step 6b, `log-review-metrics` in step 7), which write telemetry and cannot touch source. If you need a file written and no dispatch or helper fits, say so in the packet and stop.
- **Never run `review-gate-mark`.** The clean mark belongs to your CALLER, after it renders your `converged` packet.
- **Never narrate the loop.** The orchestrator sees only the packet; prose above it is wasted context.
- **Never return `converged` on a quiet round with an open class, or with an empty `fixed[]` past round one** (Steps 5d/6 decide).
