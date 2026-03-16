---
name: changeset
description: Create or update a changeset file from recent changes. Use when the user says "changeset", "add changeset", "version bump", or wants to document changes for the next release in a Changesets monorepo.
allowed-tools: [Bash, Read, Write, Edit, Grep, Glob]
---

# Changeset

Create or update a `.changeset/*.md` file summarizing changes for the next release. The convention is **one changeset per PR** — if one already exists for this branch, update it rather than creating a new file.

## Modifiers

- `+minor` / `+patch` / `+major` — Force a specific bump level (skip auto-detection).
- `+core` / `+vue` — Scope to a single package instead of detecting from changed files.
- `+new` — Force creation of a new changeset file even if one already exists.

## Instructions

1. **Check for existing changeset** — Look in `.changeset/` for any `.md` files besides `README.md`. If one exists, read it — this is the changeset for the current PR and should be updated in place.

2. **Detect changed packages** — Run `git diff --cached --stat` (staged) and `git diff --stat` (unstaged). If nothing is staged or changed, diff against the base branch (`git diff <base-branch>...HEAD --stat`). Determine which packages (`@big6media/core`, `@big6media/vue`) are affected.

3. **Read the diff** — Read the actual diff content to understand what changed. Focus exclusively on **consumer-facing changes**: new/changed exports, props, types, component behavior, tokens, bug fixes, security, and accessibility. Omit the following — they are internal implementation details and do not belong in a changeset:
   - DRY refactors (extracted helpers, shared utilities, deduplication)
   - Type safety improvements (removed `any`, extracted interfaces) unless they change a public type
   - Test coverage additions or fixes
   - Internal-only computed/watcher/variable extractions
   - Performance micro-optimizations with no observable behavior change

4. **Determine bump level** (unless overridden by modifier):
   - `major` — Removed/renamed exports, breaking prop or behavior changes, import path restructuring
   - `minor` — New components, composables, exports, public API additions (non-breaking)
   - `patch` — Bug fixes, style tweaks, internal refactors, docs edits, dev dep bumps
   - When uncertain and consumer impact exists, default to `patch`

5. **Draft the changeset body** following these formatting rules:
   - No markdown tables (they break in npm/changelog renderers)
   - No `#`/`##`/`###` headings (changesets auto-generates those) — use **bold text** to group related changes
   - List every prop change per component explicitly — don't summarize breaking changes
   - Non-breaking additions and internal improvements can be summarized in 1-2 lines per item; don't enumerate every sub-detail
   - Keep it concise but complete — a consumer reading the changelog should understand what changed and whether it affects them
   - When updating an existing changeset, merge new changes into the existing body — reorganize and deduplicate as needed
   - Merge related sub-sections (e.g. two rounds of bug fixes or accessibility audits → one **Bug fixes** section)

   **Canonical section order** (use only sections that apply):
   - **Breaking:** — renamed/removed exports, prop renames, behavior changes requiring consumer action
   - **Token changes** — renamed/removed design tokens or z-index scale restructuring
   - **New components** — new public components
   - **New props** — new props/events on existing components
   - **New composables** — new exported composables
   - **New exports** — new types or utilities exported from package barrels
   - **API changes** — changed function signatures, renamed options
   - **Security** — sanitization, blocked protocols, XSS prevention
   - **Bug fixes** — observable behavior fixes
   - **Accessibility** — a11y improvements
   - **Improvements** — consumer-visible behavioral/UX improvements (not internal refactors)
   - **Standardization** — renamed variant values, type alias cleanup
   - **SCSS tokens & mixins** — new/changed public SCSS tokens and mixins
   - **Shared configs** — new ESLint/Prettier/tsconfig exports for consumer apps
   - **Developer tooling** — CLI tools, test utilities, scaffold scripts

6. **Write the file**:
   - **Updating**: overwrite the existing changeset file, preserving its filename. Adjust the frontmatter package list and bump levels if the scope changed.
   - **Creating** (no existing changeset, or `+new`): generate a slug (lowercase, kebab-case, descriptive), check `.changeset/` for collisions, and write to `.changeset/<slug>.md`.

   Format:
   ```
   ---
   '@big6media/vue': patch
   '@big6media/core': patch
   ---

   Changeset body here.
   ```

   Only include packages that actually changed. Use single quotes around package names in the frontmatter.

7. **Show the user** the final file content and path.

## Arguments

$ARGUMENTS
