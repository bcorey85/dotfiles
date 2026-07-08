---
name: review
description: Review recent changes using the code-reviewer subagent — the inner-loop reviewer for OUR working diff. Use for "review my changes", "review this diff", "check before I commit". Others' PRs go to /peer-review; this is not the built-in PR-review skill.
allowed-tools:
  [Agent, Bash, Read, Glob, Grep, LSP, AskUserQuestion, SendMessage, Skill]
---

# Code Review

Review recent changes in this codebase using the code-reviewer subagent.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). `+fast` for quick sanity checks on small changes; `+deep` (→ `code-reviewer-deep`) for security-sensitive changes, complex logic, or architectural modifications.

## Instructions

1. **Parse args**:
   - **Modifiers**: If `+deep` is present, dispatch `code-reviewer-deep` instead of `code-reviewer` and omit `model` (its frontmatter pins Opus). If `+fast` is present, pass `model: "haiku"`.
   - **Iteration counter**: Look for `iter=N` in args (default `iter=1`). Tracks how many times the review-fix loop has run. **If `iter >= 3`, STOP immediately** and alert the user: "Review-fix loop has run 3 iterations without converging. Stopping to avoid churn. Outstanding issues: [list]. Decide manually how to proceed." Do NOT auto-dispatch `/fix`.
   - **One-shot mode**: If `iter=oneshot` is present, this is the post-convergence verification pass after a MEDIUM triage `/fix`. Run the review as normal, report results to the user, but **do NOT auto-dispatch anything** — skip step 5's branching entirely. Report findings as a final summary, then stop. (Rationale: MEDIUM triage already happened in the prior turn; re-triaging would loop indefinitely.) **Reviewer for this pass**: if the just-converged loop ran 2 or more iterations, dispatch `code-reviewer-deep` (omit `model`) instead of `code-reviewer` — the task proved itself hard, so the final declare-victory pass gets one decorrelated Opus look (same-model reviewers share the coder's blind spots). Single-iteration loops keep the standard reviewer.
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

   **Second-order supplement (both paths)**: From the handoff `change` lines (or the diff), list every exported symbol whose signature, return type, or name changed. For each, run LSP find-references (fall back to `rg` for untyped code) and collect call sites OUTSIDE the current scope. Append those files to the reviewer's scope tagged "out-of-scope caller — check call-site compatibility only". This is a targeted expansion to catch the coder's most characteristic miss (a forgotten caller in a file it didn't touch); it is NOT an invitation to re-review unchanged code.

3. **Dispatch code-reviewer subagent(s)**:

   **Reviewer continuity (iter ≥ 2)**: when this invocation is a re-review inside the same session's fix loop (handoff has `prior-issues` and `iter ≥ 2`) and the reviewer agent from the previous iteration is still addressable, do NOT spawn a fresh reviewer — continue it via `SendMessage` with the handoff block (prior-issues + changed files). It already holds the context of its earlier review, so it verifies fix-by-fix without re-reading the scope. Spawn fresh only if: no prior reviewer exists in this session, the depth modifier changed (`+fast`/`+deep`), or the parallel-split boundaries changed. **Exception — the `oneshot` pass MUST be a fresh spawn**: a continued reviewer anchors on its own past verdicts, and the declare-victory pass is deliberately decorrelated (per step 1, after 2+ iterations it's `code-reviewer-deep`).

   **If 5 or fewer files in scope**: Dispatch a single code-reviewer subagent.

   **If more than 5 files in scope**: Dispatch parallel code-reviewer subagents along the largest natural boundary in the changed set. Common splits, in priority order:
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

4. **Present the review results** to the user organized by severity

5. **Decide next steps** based on the review outcome. Severity gating has two tiers:
   - **CRITICAL / HIGH** → auto-fix loop (convergence-bounded, counts toward `iter` limit)
   - **MEDIUM** → main-agent triage as a single follow-up after the loop converges (one-shot, NOT counted toward `iter`)
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

     - **Test-intent audit (conditional, one-shot)**: If the review scope (`handoff.files` or git discovery) contains any **test files**, dispatch ONE `test-intent-reviewer` subagent (omit `model` — its frontmatter pins Opus; call-site `model: "opus"` is hook-blocked). This is the decorrelated check that a `code-reviewer` PASS cannot give: it judges whether the changed assertions pin _intended_ behavior or merely snapshot the now-blessed implementation (a bug-pinning test). Pass it the changed test files + their source-under-test, and any intent context available in args (ticket/plan path, conversation). It self-resolves the intent oracle via `qrspi-resolve-dir.sh`. Run it **once here only** — never per loop iteration, and skip entirely when no test files changed. Route its findings into the same fix/skip/ask buckets as the MEDIUM triage below:
       - **BUG-PINNING (spec-backed)** → treat as a **fix** item (bundle into the one-shot `/fix`). The fix corrects whichever of {test, code} the oracle says is wrong — often the code.
       - **BUG-PINNING / derived-low-confidence**, **UNVERIFIABLE (spec gaps)**, and the **"Derived intent — confirm"** block → **ask** items. Present to the user; do not auto-fix against a weak or absent oracle.
       - If `test-intent-reviewer` returns exit 3 (multiple spec dirs) or asks which directory, relay that to the user.

     Now triage MEDIUMs as a follow-up:
     - **If MEDIUM items exist**: The main agent (caller of this skill) must triage each MEDIUM with explicit judgment. For every MEDIUM, classify it as:
       - **fix** — clear win, safe to auto-apply (e.g. missing null check, obvious dead code, real but non-blocking bug)
       - **skip** — false positive, intentional choice, stylistic noise, or out-of-scope for this change
       - **ask** — ambiguous, requires design decision, or could plausibly be either fix/skip

       Then:
       1. Bundle the **fix** bucket into a **single one-shot** `/fix` dispatch. This dispatch is NOT counted toward the `iter` limit — pass `iter=oneshot` (or omit) so `/fix` knows not to re-enter the convergence loop. After this one-shot fix, run `/review` once more to verify, then stop regardless of remaining MEDIUMs.
       2. List the **skip** bucket inline with a one-line reason each ("intentional — matches existing pattern in X", "false positive — reviewer missed Y", etc.).
       3. Present the **ask** bucket to the user and wait for direction before doing anything with them.

     - **If no MEDIUM items**: "No issues found that warrant auto-fix. Ready for `/commit`." List any LOW items / Notes inline.

   `/fix` already auto-dispatches `/review` when it finishes, so the HIGH/CRITICAL path is an automatic review-fix loop. The convergence loop terminates when:
   - No CRITICAL or HIGH issues remain (clean by the auto-fix gate, regardless of MEDIUM/LOW)
   - A critical blocker surfaces that needs user input
   - 3 iterations pass without converging (stop and alert the user to avoid churn)

   The MEDIUM triage step runs **after** convergence and is a single one-shot — it does NOT re-enter the iter-bounded loop. This keeps the loop's termination condition simple while still surfacing actionable MEDIUMs for fix instead of dropping them on the user.

6. **Log the run** (every invocation, including oneshot — this is the loop's flywheel):

   ```bash
   bash "${CLAUDE_SKILL_DIR}/log-review-metrics" repo="$(basename "$(git rev-parse --show-toplevel)")" iter=<N|oneshot> critical=<n> high=<n> medium=<n> low=<n> fixed=<n> skipped_fp=<n> ask=<n> test_intent=<n> result=<PASS|PASS WITH WARNINGS|NEEDS CHANGES>
   ```

   `fixed`/`skipped_fp`/`ask` are the MEDIUM-triage bucket counts when triage ran, else 0. `test_intent` is the count of bug-pinning/unverifiable findings from the `test-intent-reviewer` (0 when it didn't run). The JSONL at `~/.claude/review-metrics.jsonl` accumulates the convergence distribution and false-positive rate (`skipped_fp` fraction) — the evidence base for tuning the reviewer's calibration and the iter cap. Recurring `skipped_fp` patterns are evidence for refining the reviewer's "Do NOT Flag" list.

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
   absent): date, finding, decision, owner. `/q-verify` reconciles against
   the amended plan; `/q-finalize`'s ADR inherits the record.

## Arguments

$ARGUMENTS
