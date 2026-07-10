---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools:
  [Agent, Bash, Read, Write, Edit, Glob, Grep, LSP, AskUserQuestion, SendMessage, Skill]
---

# Code Review

Review recent changes in this codebase using the code-reviewer subagent.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). `+fast` for quick sanity checks on small changes; `+deep` (→ `code-reviewer-deep`) for security-sensitive changes, complex logic, or architectural modifications.

## Instructions

1. **Parse args**:
   - **Modifiers**: If `+deep` is present, dispatch `code-reviewer-deep` instead of `code-reviewer` and omit `model` (its frontmatter pins Opus). If `+fast` is present, pass `model: "haiku"`.
   - **Iteration counter**: Look for `iter=N` in args (default `iter=1`). Tracks how many times the review-fix loop has run. **If `iter >= 3`, STOP immediately** and alert the user: "Review-fix loop has run 3 iterations without converging. Stopping to avoid churn. Outstanding issues: [list]. Decide manually how to proceed." Do NOT auto-dispatch `/fix`.
   - **Handoff block**: Look for a `handoff:` block in args (produced by `/code` or `/fix`). If present, use it as the review scope per the "Handoff Block" section below.

2. **Determine review scope**:

   **If a handoff block was passed**: use `handoff.files` as the review scope. Skip git discovery. If `handoff.prior-issues` is present, the reviewer's primary job is verifying those fixes — pass them to the reviewer subagent explicitly.

   **Otherwise** (manual invocation, no handoff), gather changed files including untracked:

   ```bash
   {
     git diff --name-only HEAD 2>/dev/null
     git diff --cached --name-only 2>/dev/null
     git ls-files --others --exclude-standard 2>/dev/null
   } | sort -u
   ```

   This captures unstaged, staged, AND new untracked files. `git diff --name-only HEAD` alone misses untracked files — the most common case right after a coder dispatch.

   **Second-order supplement (both paths)**: From the handoff `change` lines (or the diff), list every exported symbol whose signature, return type, or name changed. For each, run LSP find-references (fall back to `rg` for untyped code) and collect call sites OUTSIDE the current scope. Append those files to the reviewer's scope tagged "out-of-scope caller — check call-site compatibility only". This is a targeted expansion to catch the coder's most characteristic miss (a forgotten caller in a file it didn't touch); it is NOT an invitation to re-review unchanged code. Run it on `iter=1` and manual invocations only; on re-review iterations (`iter ≥ 2`) limit it to symbols the fix diff itself changed — the base scope was already expanded once and hasn't moved.

3. **Dispatch code-reviewer subagent(s)**:

   **Reviewer continuity (iter ≥ 2)**: when this invocation is a re-review inside the same session's fix loop (handoff has `prior-issues` and `iter ≥ 2`) and the reviewer agent from the previous iteration is still addressable, do NOT spawn a fresh reviewer — continue it via `SendMessage` with the handoff block (prior-issues + changed files). It already holds the context of its earlier review, so it verifies fix-by-fix without re-reading the scope. Spawn fresh only if: no prior reviewer exists in this session, the depth modifier changed (`+fast`/`+deep`), or the parallel-split boundaries changed.

   **Split threshold — parallel reviewers only when BOTH hold**: more than 5 files in scope AND a substantial combined diff (~300+ changed lines; check `git diff --stat` over the scope). A many-file but small diff (rename ripple, config touches) is one reviewer's job — a second spawn doubles cost without adding coverage. Otherwise dispatch a single code-reviewer subagent.

   **When splitting**, choose the largest natural boundary in the changed set. Common splits, in priority order:
   - Frontend vs backend (most web codebases)
   - Source vs tests
   - Two unrelated subsystems / packages in a monorepo
   - Rules/config vs runtime code

   Pick the split that minimizes overlap between reviewers. Launch both in a single message with multiple Agent tool calls.

   When invoking each reviewer subagent, pass:
   - The exact file list it owns (from handoff or git discovery — never let the subagent rediscover scope)
   - If `handoff.prior-issues` exists, the subset relevant to its files
   - If `handoff.flagged` exists, the subset relevant to its files

   Do NOT include a category checklist (e.g. "check for style violations, missing error handling, anti-patterns") in the dispatch prompt. The code-reviewer agent file defines its own calibration — what to flag and what to suppress — and a flat category list in the task prompt reads as a quota, re-opening the noise channels that calibration closes. Pass only scope and context the agent cannot discover itself.

   If a file path is provided via $ARGUMENTS (and no handoff block), focus the review on that file only.

4. **Present the review results** to the user organized by severity. One addition severity ordering can't express: if a high-blast-radius file in scope (enforcement surface, many inbound references, public contract) came back with zero findings, note it in one line — "clean but load-bearing — worth a human glance". Never pre-rank files in the dispatch itself (step 3's no-checklist rule); this note is derived from the reviewer's output, after the fact.

   **Perf learning surface**: `[perf]`-tagged findings never scroll past silently, regardless of severity bucket or whether they're about to be auto-fixed. Two obligations:

   1. **In-session**: list them in the summary under their own `### Perf findings` heading, each with its `Principle:` line — the user is deliberately building backend-performance intuition from these.
   2. **Vault log**: append each to `~/vault/91. Areas/Backend Performance/Backend Perf - Findings Log.md` via Read + Edit (Write the file with a `# Backend Perf - Findings Log` heading if it doesn't exist yet). One entry per finding:

      ```
      - **<today's date>** `<repo>` `<file:line>` — <finding one-liner> → <fix applied or "reported">. *Principle: <principle>*
      ```

      Append only on iteration 1 and manual invocations — re-review iterations (`iter ≥ 2`) re-see the same findings; don't double-log them.

5. **Decide next steps** based on the review outcome. Severity gating has two tiers:
   - **CRITICAL / HIGH** → auto-fix loop (convergence-bounded, counts toward `iter` limit)
   - **MEDIUM** → main-agent triage after convergence; fix bucket gets ONE `no-review` `/fix` dispatch (coder only — no reviewer respawn)
   - **LOW** → report-only, never auto-handled

   - **If HIGH issues found but NO critical blockers**: Auto-dispatch `/fix` for the HIGH (and CRITICAL, if any non-blocking) issues only. Tell the user: "Auto-dispatching `/fix` to resolve N high-priority issues (iteration M of 3). M MEDIUM items will be triaged after the loop converges. L LOW items reported only." Invoke the Skill tool (`skill: "fix"`, args including `iter=M` — current count, unchanged; `/fix` increments before re-invoking review). **Do not pass MEDIUM or LOW items to `/fix`** — MEDIUMs are deferred to post-loop triage, LOWs are reported only.

   - **If critical blockers that need user judgment**: STOP and alert the user. Critical blockers are:
     - Security vulnerabilities that require design decisions
     - Architectural issues that need `/eng-spec`
     - Ambiguous fixes where multiple valid approaches exist and the wrong choice could break things
     - Issues that require changing the public API contract

     Present these to the user and wait for direction. Do NOT auto-dispatch `/fix` in this case.

   - **Execution gate (before declaring convergence)**: A reviewer PASS is an opinion; a passing check run is evidence. Before treating the loop as converged, verify the evidence link: if the handoff's `tests-run` shows a real command with exit 0, accept it. If it is "none", missing, or has no exit code while code changed: run the project's quality-check command (from project CLAUDE.md, e.g. `npm run validate`) ONCE, redirected to `/tmp/review-gate.log`. Exit 0 → proceed. Non-zero → the failures are ground truth: treat them as CRITICAL findings and route into the severity gating above. Exception: failures in acceptance spec tests (the plan's `Acceptance Stubs` file(s), or the project's acceptance-spec convention, e.g. `*.spec.*`) are critical BLOCKERS for user judgment — never route them to auto-`/fix`. Either the code is wrong or the intent changed, and only the user decides which; an auto-fixer's cheapest path to green is editing the spec. Never skip this because the review "looked clean" — model approval without executed evidence is the loop's weakest exit, and this gate is what makes convergence mean something.

   - **If all clear on the auto-fix gate (no CRITICAL or HIGH issues remain)**: The convergence loop is done.

     - **Test-intent audit (conditional, one-shot)**: Opus-priced, so it fires only when BOTH gates pass — mere test-file churn gives it nothing to judge:
       1. **Assertion gate (deterministic)**: `git diff -U0 HEAD -- <changed test files> | grep -cE '^\+.*\b(expect|assert|should)\b'` — zero added assertion lines → skip. Moves, helper/fixture edits, and rename ripple add no assertion lines; an added import mentioning `expect` can false-positive, which costs at most one unnecessary audit.
       2. **Oracle gate**: run `bash ~/.claude/scripts/resolve-task-dir.sh` here first (one cheap call). Exit 0 → proceed (deep-plan ticket + plan are the oracle). Exit 5 → proceed — the printed eng-spec file's acceptance criteria are the oracle; pass its path to the reviewer. Exit 4 (no spec anywhere — weak oracle only) → skip unless `+deep` was passed; note "test-intent audit skipped: no spec oracle". Exit 3 → relay the directory question to the user.

       When both pass, dispatch ONE `test-intent-reviewer` subagent (omit `model` — its frontmatter pins Opus; call-site `model: "opus"` is hook-blocked). This is the decorrelated check that a `code-reviewer` PASS cannot give: it judges whether the changed assertions pin _intended_ behavior or merely snapshot the now-blessed implementation (a bug-pinning test). Pass it the changed test files + their source-under-test, and any intent context available in args (ticket/plan path, conversation). Run it **once here only** — never per loop iteration. Route its findings into the same fix/skip/ask buckets as the MEDIUM triage below:
       - **BUG-PINNING (spec-backed)** → a **fix** item: bundle into the fix-bucket dispatch tagged `[test-intent]`. The fix corrects whichever of {test, code} the oracle says is wrong — often the code.
       - **BUG-PINNING / derived-low-confidence**, **UNVERIFIABLE (spec gaps)**, and the **"Derived intent — confirm"** block → **ask** items. Present to the user; do not auto-fix against a weak or absent oracle.

     Now triage MEDIUMs as a follow-up:
     - **If MEDIUM items exist**: The main agent (caller of this skill) must triage each MEDIUM with explicit judgment. For every MEDIUM, classify it as:
       - **fix** — clear win, safe to auto-apply (e.g. missing null check, obvious dead code, real but non-blocking bug). A `[test-fluff]` finding on a diff-introduced test defaults to **fix** (prune it, or tighten it to assert real behavior) — this is the auto-prune that keeps test spam out of the diff. **Guard**: NEVER auto-prune a test in an acceptance-spec file (`*.spec.*`) or the plan's Acceptance Stubs — route those to **ask** instead. Same reasoning as the execution gate above: an auto-fixer's cheapest path to a smaller diff is deleting a test, and only the user decides whether lost coverage is acceptable.
       - **skip** — false positive, intentional choice, stylistic noise, or out-of-scope for this change
       - **ask** — ambiguous, requires design decision, or could plausibly be either fix/skip

       Then:
       1. Dispatch `/fix` ONCE with the **fix** bucket, args including `no-review` — `/fix` skips its auto-review in this mode; verification is the execution gate (the coder runs the project's quality checks and reports the exit code). No reviewer respawn: MEDIUM is by definition shippable-without-fixing, so a model re-review of these fixes buys nothing the gate doesn't. Not counted toward `iter`. Tell the user: "Dispatching /fix (no re-review) for <n> triaged MEDIUMs."
       2. List the **skip** bucket inline with a one-line reason each ("intentional — matches existing pattern in X", "false positive — reviewer missed Y", etc.).
       3. Present the **ask** bucket to the user and wait for direction before doing anything with them.

     - **If no MEDIUM items**: "No issues found that warrant auto-fix. Ready for `/commit`." List any LOW items / Notes inline.

   `/fix` already auto-dispatches `/review` when it finishes, so the HIGH/CRITICAL path is an automatic review-fix loop. The convergence loop terminates when:
   - No CRITICAL or HIGH issues remain (clean by the auto-fix gate, regardless of MEDIUM/LOW)
   - A critical blocker surfaces that needs user input
   - 3 iterations pass without converging (stop and alert the user to avoid churn)

   The MEDIUM triage step runs **after** convergence and never re-enters the loop — one coder dispatch, gate-verified, no reviewer.

6. **Log the run** (every invocation — this is the loop's flywheel):

   ```bash
   bash "${CLAUDE_SKILL_DIR}/log-review-metrics" repo="$(basename "$(git rev-parse --show-toplevel)")" iter=<N> critical=<n> high=<n> medium=<n> low=<n> fixed=<n> skipped_fp=<n> ask=<n> test_intent_ran=<0|1> test_intent=<n> result=<PASS|PASS WITH WARNINGS|NEEDS CHANGES>
   ```

   `fixed`/`skipped_fp`/`ask` are the MEDIUM-triage bucket counts when triage ran, else 0. `test_intent_ran` records whether the audit fired; paired with `test_intent` (finding count) it lets `/review-stats` compute yield-per-firing — the signal that catches a stage that fires and finds nothing. The JSONL at `~/.claude/review-metrics.jsonl` accumulates the convergence distribution and false-positive rate (`skipped_fp` fraction) — the evidence base for tuning the reviewer's calibration and the iter cap. Recurring `skipped_fp` patterns are evidence for refining the reviewer's "Do NOT Flag" list.

When invoked from `/code` or `/fix`, args may contain a handoff block. Canonical schema:

```
handoff:
  files:
    - path: <relative path>
      change: <one line: what changed and why>
  tests-run: <exact command + exit code, e.g. "npm run validate → exit 0"; or "none">
  flagged: <issues the upstream coder explicitly flagged, or "none">
  plan_impact: <verbatim PLAN-IMPACT block + the user's decision, or "none">
  prior-issues:           # only present on fix → review
    - issue: <one line>
      status: fixed | skipped | partial
      file: <path>
  iter: <integer>
```

When present:

- Use `files` as exact review scope. Do not run `git diff`.
- If `prior-issues` is present, the reviewer's primary job is verifying those fixes — pass them to the reviewer subagent so it can confirm fix-by-fix before scanning for new issues.
- Use `iter` for the iteration counter check (step 1).
- Treat the schema as a versioned interface — if a producer skill needs additional fields, add them here first and update both producers and consumers in the same change.

When absent (manual `/review` invocation), fall back to git discovery in step 2.

## Plan-impact findings (unskippable routing)

A reviewer finding that **invalidates a plan/design decision** — not a code
defect to fix, but evidence the plan's assumption is wrong (missed external
contract/invariant, mis-tiered risk, security surface the plan doesn't gate) —
is a `PLAN-IMPACT`, not a severity bucket. When the reviewer report contains
one (or a coder handoff carried `plan_impact`):

1. Do NOT fold it into the findings summary or triage it as a MEDIUM.
2. Present it via **AskUserQuestion** before any further auto-dispatch
   (`/fix`, next iteration, commit): state assumed → found → what changes,
   with options `Adopt plan change` / `Keep plan as written` / `Discuss`.
   (The AskUserQuestion hook makes this a desktop notification + tmux badge;
   the modal blocks until answered — that is the point.)
3. Record the answer in the plan's `## Plan Deviations` section (create it if
   absent): date, finding, decision, owner. `/verify` reconciles against
   the amended plan; `/finalize`'s ADR inherits the record.

## Arguments

$ARGUMENTS
