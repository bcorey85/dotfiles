---
name: peer-review
description: Peer-review recent changes using the code-reviewer subagent
allowed-tools: [Task, Bash, Read, Glob, Grep, Skill]
---

# Code Review

Review recent changes in this codebase using the code-reviewer subagent.

## Modifiers

- `+fast` — Use Haiku model for code-reviewer subagent(s). Use for quick sanity checks on small changes.
- `+deep` — Use Opus model for code-reviewer subagent(s). Use for security-sensitive changes, complex logic, or architectural modifications.

## Instructions

1. **Parse args**:
   - **Modifiers**: If `+deep` is present, pass `model: "opus"` to all Task tool calls below. If `+fast` is present, pass `model: "haiku"`.
   - **Iteration counter**: Look for `iter=N` in args (default `iter=1`). Tracks how many times the review-fix loop has run. **If `iter >= 3`, STOP immediately** and alert the user: "Review-fix loop has run 3 iterations without converging. Stopping to avoid churn. Outstanding issues: [list]. Decide manually how to proceed." Do NOT auto-dispatch `/fix-feedback`.
   - **Handoff block**: Look for a `handoff:` block in args (produced by `/code` or `/fix-feedback`). If present, use it as the review scope per the "Handoff Block" section below.

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

3. **Dispatch code-reviewer subagent(s)**:

   **If 5 or fewer files in scope**: Dispatch a single code-reviewer subagent.

   **If more than 5 files in scope**: Dispatch parallel code-reviewer subagents along the largest natural boundary in the changed set. Common splits, in priority order:
   - Frontend vs backend (most web codebases)
   - Source vs tests
   - Two unrelated subsystems / packages in a monorepo
   - Rules/config vs runtime code

   Pick the split that minimizes overlap between reviewers. Launch both in a single message with multiple Task tool calls.

   When invoking each reviewer subagent, pass:
   - The exact file list it owns (from handoff or git discovery — never let the subagent rediscover scope)
   - If `handoff.prior-issues` exists, the subset relevant to its files
   - If `handoff.flagged` exists, the subset relevant to its files
   - The standard review checklist below

   Each reviewer should check for:
   - Bugs or logic errors
   - Security issues
   - Performance problems
   - Code style violations
   - Missing error handling
   - Anti-patterns
   - Architectural violations

   If a file path is provided via $ARGUMENTS (and no handoff block), focus the review on that file only.

4. **Present the review results** to the user organized by severity

5. **Decide next steps** based on the review outcome. Severity gating is **strict** — only CRITICAL and HIGH trigger the auto-fix loop. MEDIUM and LOW are report-only.
   - **If all clear (no CRITICAL or HIGH issues)**: "No issues found that warrant auto-fix. Ready for `/commit`." If there are MEDIUM items or Notes, list them inline so the user can decide manually whether to address.

   - **If HIGH issues found but NO critical blockers**: Auto-dispatch `/fix-feedback` for the HIGH (and CRITICAL, if any non-blocking) issues only. Tell the user: "Auto-dispatching `/fix-feedback` to resolve N high-priority issues (iteration M of 3). M MEDIUM and L LOW items reported but skipped from auto-fix." Invoke the Skill tool (`skill: "fix-feedback"`, args including `iter=M` — current count, unchanged; `/fix-feedback` increments before re-invoking peer-review). **Do not pass MEDIUM or LOW items to `/fix-feedback`** — they are reported to the user, not fed into the loop.

   - **If critical blockers that need user judgment**: STOP and alert the user. Critical blockers are:
     - Security vulnerabilities that require design decisions
     - Architectural issues that need `/eng-spec`
     - Ambiguous fixes where multiple valid approaches exist and the wrong choice could break things
     - Issues that require changing the public API contract

     Present these to the user and wait for direction. Do NOT auto-dispatch `/fix-feedback` in this case.

   - **If only MEDIUM and/or LOW items**: Report them and stop. Tell the user: "Review found N medium-priority items and L notes. None warrant auto-fix — review and address manually if you want them fixed." Do NOT auto-dispatch `/fix-feedback`.

   `/fix-feedback` already auto-dispatches `/peer-review` when it finishes, so this creates an automatic review-fix loop. The loop terminates when:
   - No CRITICAL or HIGH issues remain (clean by the gate, even if MEDIUM/LOW items exist)
   - A critical blocker surfaces that needs user input
   - 3 iterations pass without converging (stop and alert the user to avoid churn)

   This severity gate is the primary defense against noise-driven loop iterations. If reviewer noise creeps into MEDIUM/LOW, it costs you a single report — not another full iteration.

## Handoff Block

When invoked from `/code` or `/fix-feedback`, args may contain a handoff block. Canonical schema:

```
handoff:
  files:
    - path: <relative path>
      change: <one line: what changed and why>
  tests-run: <command(s) and pass/fail status, or "none">
  flagged: <issues the upstream coder explicitly flagged, or "none">
  prior-issues:           # only present on fix-feedback → peer-review
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

When absent (manual `/peer-review` invocation), fall back to git discovery in step 2.

## Arguments

$ARGUMENTS
