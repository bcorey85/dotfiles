---
name: audit-code
description: Audit code for security, bugs, DRY/maintainability, and accessibility — auto-triages findings and presents only actionable issues
allowed-tools: [Task, Bash, Read, Write, Glob, Grep]
---

# Code Audit

Audit a codebase for security vulnerabilities, real bugs, DRY/maintainability issues, and accessibility violations. **Read-only** — presents findings for the user to decide what to fix. Writes a findings ledger so re-runs are deterministic and converge.

## Philosophy

Report only issues that a senior staff engineer at a top-tier company would flag in a PR review. The goal is world-class engineering standards, not theoretical perfection. If an issue wouldn't survive triage, don't report it.

## Modifiers

- `+fast` — Use Haiku model for auditor subagents. Quick surface-level scan.
- `+deep` — Use Opus model for auditor subagents. Thorough, line-by-line analysis.
- `+fresh` — Ignore previous findings ledger and start a clean audit.

## Arguments

`$ARGUMENTS` may contain:

- A **file path**, **directory**, or **glob pattern** to scope the audit (e.g., `src/components/`, `packages/vue/src/composables/*.ts`)
- A **focus keyword** to narrow the audit categories (e.g., `security`, `dry`, `a11y`)
- If empty, audit the entire project source (use project structure from CLAUDE.md to identify source directories)

## Instructions

### Phase 0: Load Previous Findings

Look for an existing findings ledger at `.claude/audit-findings.json` in the project root.

If found (and `+fresh` was NOT passed):

- Read it. It contains an array of previous findings with `file`, `line`, `category`, `severity`, `description`, `status` (open/fixed/wontfix), and `hash` (a fingerprint of file+line+description).
- Pass the full list of **open** findings to each subagent so they can skip already-known issues.
- After the audit, merge new findings into the existing ledger (dedup by hash).

If not found (or `+fresh` was passed):

- Start with an empty findings list.

### Phase 1: Parse & Discover

1. **Parse arguments**: Extract scope and focus from `$ARGUMENTS`. Strip modifiers (`+fast`, `+deep`, `+fresh`).

2. **Determine model**: If `+deep`, pass `model: "opus"` to all Task calls. If `+fast`, pass `model: "haiku"`. Default: no model override (Sonnet).

3. **Discover scope**: If no path/pattern was given, identify the project's source directories (check CLAUDE.md, look for `src/`, `packages/`, `app/`, `lib/`, etc.). Exclude `node_modules`, `dist`, `build`, `.git`, vendor dirs, and generated files.

4. **Classify files by tier**:
   - **Production code** (library source, components, utilities, services) — full audit depth
   - **Supporting code** (tests, scripts, playground/demo apps, dev tooling, config) — light scan only

5. **Collect file list**: Use Glob to gather all source files in scope. **Sort the file list alphabetically.** This is critical for determinism. Tag each file with its tier.

### Phase 2: Deterministic File Assignment

Split the sorted file list into batches using this **deterministic algorithm**:

1. Sort all files alphabetically by full path.
2. Determine batch count: `min(4, ceil(file_count / 25))` — i.e., 1 batch per 25 files, max 4.
3. Assign files round-robin by index: file 0 → batch 0, file 1 → batch 1, ..., file N → batch (N % batch_count).

This ensures identical scope always produces identical batches. Do NOT group by "domain" or "directory" — use strict round-robin on the sorted list.

### Phase 3: Dispatch Auditor Subagents

Launch one subagent per batch via the Task tool. Each subagent receives:

- Its exact list of files (full paths), with each file tagged as **production** or **supporting**
- The list of **known open findings** (from the ledger) for its files — with instructions to **skip these** and only report NEW issues
- The audit prompt below
- If the user provided a focus keyword, tell subagents to prioritize that category but still note anything critical in other categories.

**Auditor prompt** (pass to each subagent):

> You are a senior staff engineer conducting a code audit. Read every file in your assigned batch thoroughly. Your standard is world-class engineering — report only issues that would warrant a comment in a PR review at a top-tier company.
>
> **IMPORTANT**: You have been given a list of KNOWN findings. Do NOT re-report these. Only report issues that are genuinely NEW and not already captured. If you find zero new issues in a file, say so explicitly.
>
> ## File Tiers
>
> Each file is tagged as **production** or **supporting**:
>
> - **Production files** (library source, components, utilities, services): Audit with full depth across all categories below.
> - **Supporting files** (tests, scripts, playground/demo apps, dev tooling): Light scan only. Flag: security issues, real bugs, significant DRY violations, and tests that give false confidence (testing the wrong thing, assertions that always pass). Skip style nits, minor DRY, pattern suggestions, and cosmetic a11y issues in supporting code.
>
> ## Audit Categories
>
> Audit in this priority order:
>
> ### 1. Security Issues (highest priority)
>
> - XSS vectors (unsanitized user input in templates/HTML, v-html with untrusted data)
> - Injection risks (SQL, command, path traversal)
> - Hardcoded secrets, API keys, or credentials
> - Missing input validation at system boundaries
> - Insecure defaults (permissive CORS, disabled auth checks)
> - Sensitive data in logs or error messages
> - Prototype pollution or unsafe object manipulation
>
> ### 2. Bugs & Logic Errors
>
> **Only flag bugs that could be triggered through normal user interaction or standard API usage.** Skip bugs that require 2+ unlikely preconditions, only affect impossible states, or are purely theoretical in the current codebase.
>
> - Null/undefined access on realistic code paths
> - Race conditions in user-facing flows
> - Incorrect boolean logic or operator precedence
> - Unhandled promise rejections in error paths users can trigger
> - Type coercion traps that affect real behavior (not theoretical)
> - Missing return statements or wrong return types
> - State management bugs (stale refs, missing reactivity, lost updates)
>
> ### 3. DRY & Code Health
>
> Focus on issues that hurt **long-term human readability and maintainability**:
>
> - Copy-pasted logic across files (3+ duplications, or 2 with divergence risk)
> - Repeated constants or magic strings that will drift out of sync
> - God functions/components (>200 lines doing multiple unrelated things)
> - Dead code that confuses readers (unused exports, unreachable branches)
> - Deeply nested logic (>3 levels) that could be flattened
> - Missing separation of concerns that makes code hard to test or modify
>
> Skip: minor naming nits, single-use abstractions, "this could be a Map", vendored files, convention-only violations caught by linters.
>
> ### 4. Accessibility (a11y)
>
> Focus on issues that block real users of assistive technology:
>
> - Missing ARIA attributes on **interactive** elements (buttons, inputs, dialogs)
> - Non-semantic HTML for interactive controls (div with onClick instead of button)
> - Missing label associations on form inputs
> - Keyboard navigation gaps on interactive components (click handlers without key handlers)
> - Missing alt text on informational images
>
> Skip: decorative SVG missing aria-hidden in demo/playground code, color contrast concerns in non-production pages, landmark roles on internal tooling pages.
>
> ### 5. Architecture & Patterns (production code only)
>
> Only flag when the current approach will cause **real pain within 6 months** — not theoretical improvements:
>
> - Business logic tightly coupled to UI that prevents testing or reuse
> - State management that will break as the feature grows
> - Missing error boundaries that will cause cascading failures
> - Fragile coupling to library internals that will break on upgrade
>
> Skip: "this could use Strategy pattern", "consider dependency inversion", or any suggestion that adds abstraction without solving a concrete near-term problem.
>
> ### 6. Performance (production code only)
>
> Only flag issues with **measurable user impact**:
>
> - N+1 queries or unbounded loops over user-scale datasets
> - Bundle size regressions (importing entire libraries for one function)
> - Missing cleanup (event listeners, subscriptions, timers that leak)
>
> Skip: missing memoization on cheap computations, theoretical re-render concerns, micro-optimizations.
>
> ## Self-Filter Rule
>
> Before reporting any finding, ask: **"Would a senior staff engineer at a top company leave this comment on a PR, or would they let it go?"** If the answer is "let it go," do not report it. Fewer high-quality findings are better than many noisy ones.
>
> ## Severity Levels
>
> - **CRITICAL** — Security vulnerability, data loss risk, or crash-level bug reachable through normal usage
> - **HIGH** — Likely bug in a user-facing flow, significant a11y blocker, or security concern that needs design discussion
> - **MEDIUM** — DRY violation that will cause drift, maintainability issue that hurts the next developer, or pattern that needs refactoring
>
> Do NOT use LOW severity. If a finding isn't worth MEDIUM, don't report it.
>
> ## Output Format
>
> Format each finding as a JSON object on its own line:
>
> ```
> {"file": "path/to/file.ts", "line": 42, "category": "Security Issues", "severity": "CRITICAL", "description": "...", "suggestion": "..."}
> ```
>
> At the end, after all JSON findings, list your top 3 highest-impact recommendations as plain text.

### Phase 4: Merge & Deduplicate

1. Parse all subagent results. Extract JSON finding objects.
2. For each finding, compute a `hash` by combining: `file + ":" + line + ":" + first 60 chars of description` (lowercased, trimmed). This is the dedup key.
3. Compare against existing ledger entries by hash. Drop any finding whose hash already exists in the ledger.
4. Add genuinely new findings to the ledger with `"status": "open"`.
5. For ledger entries whose file no longer exists or whose line content has changed significantly, mark them `"status": "stale"`.

### Phase 5: Write Findings Ledger

Write the updated ledger to `.claude/audit-findings.json` in this format:

```json
{
  "lastAuditDate": "2026-03-14",
  "scope": "packages/vue/src/",
  "filesAnalyzed": 85,
  "findings": [
    {
      "hash": "...",
      "file": "src/composables/useDialog.ts",
      "line": 42,
      "category": "Bugs & Logic Errors",
      "severity": "HIGH",
      "description": "...",
      "suggestion": "...",
      "status": "open",
      "foundDate": "2026-03-14"
    }
  ]
}
```

### Phase 6: Present Report

Present the audit report to the user. Only show MEDIUM and above — no LOW findings.

```
## Code Audit Report

**Scope**: [files/directories audited]
**Files Analyzed**: [count] ([count] production, [count] supporting)
**Previous Known Findings**: [count from ledger, if any]
**New Findings This Run**: [count]
**Total Open Findings**: [count]

### CRITICAL
[file:line — category — description — suggestion]

### HIGH
[file:line — category — description — suggestion]

### MEDIUM
[file:line — category — description — suggestion]

### Top Recommendations
1. [highest-impact improvement]
2. [second highest]
3. [third highest]
```

If there were **zero new findings**, say:

```
## Audit Complete — No New Findings

All [N] previously identified findings are tracked in `.claude/audit-findings.json`.
[X] open, [Y] fixed, [Z] wontfix, [W] stale.

The codebase is clean relative to the audit criteria. No further audit runs needed.
```

### Phase 7: Next Steps

Ask the user which findings they'd like to address. Suggest appropriate next commands:

- `/fix` for bug fixes
- `/refactor` for DRY/pattern/smell issues
- `/fix-feedback` if they want to batch-fix specific items
- Manual fixes for security issues that need design decisions
- Re-run `/audit-code` after fixes to verify — the ledger will skip known issues and only surface anything truly new.

## Arguments

$ARGUMENTS
