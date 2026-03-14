---
name: audit-code
description: Audit code for DRY violations, code smells, security issues, accessibility, bugs, and design pattern opportunities — presents findings for user decision
allowed-tools: [Task, Bash, Read, Glob, Grep]
---

# Code Audit

Deep audit of a codebase (or a specified scope) for quality, security, and design issues. **Read-only** — presents findings for the user to decide what to fix.

## Modifiers

- `+fast` — Use Haiku model for auditor subagents. Quick surface-level scan.
- `+deep` — Use Opus model for auditor subagents. Thorough, line-by-line analysis.

## Arguments

`$ARGUMENTS` may contain:
- A **file path**, **directory**, or **glob pattern** to scope the audit (e.g., `src/components/`, `packages/vue/src/composables/*.ts`)
- A **focus keyword** to narrow the audit categories (e.g., `security`, `dry`, `a11y`)
- If empty, audit the entire project source (use project structure from CLAUDE.md to identify source directories)

## Instructions

1. **Parse arguments**: Extract scope and focus from `$ARGUMENTS`. Strip modifiers (`+fast`, `+deep`).

2. **Determine model**: If `+deep`, pass `model: "opus"` to all Task calls. If `+fast`, pass `model: "haiku"`. Default: no model override (Sonnet).

3. **Discover scope**: If no path/pattern was given, identify the project's source directories (check CLAUDE.md, look for `src/`, `packages/`, `app/`, `lib/`, etc.). Exclude `node_modules`, `dist`, `build`, `.git`, vendor dirs, and generated files.

4. **Collect file list**: Use Glob to gather all source files in scope. Group them by domain or directory for parallel dispatch.

5. **Dispatch auditor subagents** via the Task tool:

   Split files into **2–4 batches** (by directory or domain) and launch parallel subagents. Each subagent gets its batch of files and the audit prompt below.

   If the user provided a focus keyword, tell subagents to prioritize that category but still note anything critical in other categories.

   **Auditor prompt** (pass to each subagent):

   > You are a senior code auditor. Read every file in your assigned batch thoroughly. For each issue found, report the exact file path, line number(s), a brief description, and a concrete suggestion.
   >
   > Audit for ALL of the following categories:
   >
   > **DRY Violations & Duplication**
   > - Copy-pasted logic across files (even with minor variations)
   > - Repeated constants, magic strings, or config values
   > - Similar functions that could share an abstraction
   > - Duplicated type definitions or interfaces
   >
   > **Code Smells**
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
   > - XSS vectors (unsanitized user input in templates/HTML)
   > - Injection risks (SQL, command, path traversal)
   > - Hardcoded secrets, API keys, or credentials
   > - Missing input validation at system boundaries
   > - Insecure defaults (permissive CORS, disabled auth checks)
   > - Sensitive data in logs or error messages
   > - Prototype pollution or unsafe object manipulation
   >
   > **Accessibility (a11y)**
   > - Missing ARIA attributes on interactive elements
   > - Non-semantic HTML (div/span where button/nav/main fits)
   > - Missing alt text on images
   > - Missing label associations on form inputs
   > - Keyboard navigation gaps (click handlers without key handlers)
   > - Color contrast or focus indicator concerns
   > - Missing skip-navigation or landmark roles
   >
   > **Bugs & Logic Errors**
   > - Null/undefined access without guards
   > - Off-by-one errors, boundary conditions
   > - Race conditions or timing issues
   > - Unhandled promise rejections or missing error handling
   > - Incorrect boolean logic or operator precedence
   > - Type coercion traps (== vs ===, falsy 0/"" checks)
   > - Missing return statements or wrong return types
   >
   > **Design Pattern Opportunities**
   > - Logic that would benefit from Strategy, Observer, Factory, Adapter, etc.
   > - State management that's tangled or could use a well-known pattern
   > - Components that should be composed differently (slots, render props, provide/inject)
   > - Missing separation of concerns (business logic in UI, data fetching in components)
   > - Opportunities for dependency inversion or interface extraction
   >
   > **Performance**
   > - Unnecessary re-renders or missing memoization
   > - N+1 queries or unbounded loops over large datasets
   > - Missing debounce/throttle on frequent events
   > - Large synchronous operations that should be async
   > - Bundle size concerns (large imports that could be tree-shaken or lazy-loaded)
   >
   > Categorize every finding by severity:
   > - **CRITICAL** — Security vulnerability, data loss risk, or crash-level bug
   > - **HIGH** — Likely bug, significant architectural issue, or a11y blocker
   > - **MEDIUM** — Code smell, DRY violation, or design improvement
   > - **LOW** — Minor suggestion, style nit, or optimization opportunity
   >
   > At the end, list your top 3 highest-impact recommendations.

6. **Collect and deduplicate results**: Merge findings from all subagents. Remove duplicates (same file + line + issue). Sort by severity (CRITICAL first).

7. **Present the audit report** to the user in this format:

   ```
   ## Code Audit Report

   **Scope**: [files/directories audited]
   **Files Analyzed**: [count]
   **Total Findings**: [count by severity]

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

8. **Ask the user** which findings they'd like to address. Suggest appropriate next commands:
   - `/fix` for bug fixes
   - `/refactor` for DRY/pattern/smell issues
   - `/fix-feedback` if they want to batch-fix specific items
   - Manual fixes for security issues that need design decisions

## Arguments

$ARGUMENTS
