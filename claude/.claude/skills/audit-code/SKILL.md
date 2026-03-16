---
name: audit-code
description: Audit code for DRY violations, code smells, security issues, accessibility, bugs, and design pattern opportunities — presents findings for user decision
allowed-tools: [Task, Bash, Read, Write, Glob, Grep]
---

# Code Audit

Deep audit of a codebase (or a specified scope) for quality, security, and design issues. **Read-only** — presents findings for the user to decide what to fix. Writes a findings ledger so re-runs are deterministic and converge.

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

4. **Collect file list**: Use Glob to gather all source files in scope. **Sort the file list alphabetically.** This is critical for determinism.

### Phase 2: Deterministic File Assignment

Split the sorted file list into batches using this **deterministic algorithm**:

1. Sort all files alphabetically by full path.
2. Determine batch count: `min(4, ceil(file_count / 25))` — i.e., 1 batch per 25 files, max 4.
3. Assign files round-robin by index: file 0 → batch 0, file 1 → batch 1, ..., file N → batch (N % batch_count).

This ensures identical scope always produces identical batches. Do NOT group by "domain" or "directory" — use strict round-robin on the sorted list.

### Phase 3: Dispatch Auditor Subagents

Launch one subagent per batch via the Task tool. Each subagent receives:

- Its exact list of files (full paths)
- The list of **known open findings** (from the ledger) for its files — with instructions to **skip these** and only report NEW issues
- The audit prompt below
- If the user provided a focus keyword, tell subagents to prioritize that category but still note anything critical in other categories.

**Auditor prompt** (pass to each subagent):

> You are a senior code auditor. Read every file in your assigned batch thoroughly. For each issue found, report the exact file path, line number(s), the category, the severity, a brief description, and a concrete suggestion.
>
> **IMPORTANT**: You have been given a list of KNOWN findings. Do NOT re-report these. Only report issues that are genuinely NEW and not already captured. If you find zero new issues in a file, say so explicitly.
>
> Audit for ALL of the following categories:
>
> **DRY Violations & Duplication**
>
> - Copy-pasted logic across files (even with minor variations)
> - Repeated constants, magic strings, or config values
> - Similar functions that could share an abstraction
> - Duplicated type definitions or interfaces
>
> **Code Smells**
>
> - God functions/components (doing too much)
> - Deep nesting (>3 levels of conditionals/callbacks)
> - Long parameter lists (>4 params without an options object)
> - Dead code, unused imports, commented-out blocks
> - Overly complex conditionals that need simplification
> - Inconsistent naming or conventions across files
> - Primitive obsession (using strings/numbers where a type/enum fits)
> - Feature envy (a function that uses another module's data more than its own)
>
> **Security Issues**
>
> - XSS vectors (unsanitized user input in templates/HTML)
> - Injection risks (SQL, command, path traversal)
> - Hardcoded secrets, API keys, or credentials
> - Missing input validation at system boundaries
> - Insecure defaults (permissive CORS, disabled auth checks)
> - Sensitive data in logs or error messages
> - Prototype pollution or unsafe object manipulation
>
> **Accessibility (a11y)**
>
> - Missing ARIA attributes on interactive elements
> - Non-semantic HTML (div/span where button/nav/main fits)
> - Missing alt text on images
> - Missing label associations on form inputs
> - Keyboard navigation gaps (click handlers without key handlers)
> - Color contrast or focus indicator concerns
> - Missing skip-navigation or landmark roles
>
> **Bugs & Logic Errors**
>
> - Null/undefined access without guards
> - Off-by-one errors, boundary conditions
> - Race conditions or timing issues
> - Unhandled promise rejections or missing error handling
> - Incorrect boolean logic or operator precedence
> - Type coercion traps (== vs ===, falsy 0/"" checks)
> - Missing return statements or wrong return types
>
> **Design Pattern Opportunities**
>
> - Logic that would benefit from Strategy, Observer, Factory, Adapter, etc.
> - State management that's tangled or could use a well-known pattern
> - Components that should be composed differently (slots, render props, provide/inject)
> - Missing separation of concerns (business logic in UI, data fetching in components)
> - Opportunities for dependency inversion or interface extraction
>
> **Performance**
>
> - Unnecessary re-renders or missing memoization
> - N+1 queries or unbounded loops over large datasets
> - Missing debounce/throttle on frequent events
> - Large synchronous operations that should be async
> - Bundle size concerns (large imports that could be tree-shaken or lazy-loaded)
>
> Categorize every finding by severity:
>
> - **CRITICAL** — Security vulnerability, data loss risk, or crash-level bug
> - **HIGH** — Likely bug, significant architectural issue, or a11y blocker
> - **MEDIUM** — Code smell, DRY violation, or design improvement
> - **LOW** — Minor suggestion, style nit, or optimization opportunity
>
> Format each finding as a JSON object on its own line:
>
> ```
> {"file": "path/to/file.ts", "line": 42, "category": "Code Smells", "severity": "MEDIUM", "description": "...", "suggestion": "..."}
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

Present the audit report to the user:

```
## Code Audit Report

**Scope**: [files/directories audited]
**Files Analyzed**: [count]
**Previous Known Findings**: [count from ledger, if any]
**New Findings This Run**: [count]
**Total Open Findings**: [count]

### CRITICAL
[file:line — category — description — suggestion]

### HIGH
[file:line — category — description — suggestion]

### MEDIUM
[file:line — category — description — suggestion]

### LOW
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
