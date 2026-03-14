---
name: changeset
description: Create or update a changeset file from recent changes. Use when the user says "changeset", "add changeset", "version bump", or wants to document changes for the next release in a Changesets monorepo.
allowed-tools: [Bash, Read, Write, Grep, Glob]
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

3. **Read the diff** — Read the actual diff content to understand what changed. Focus on public API changes: new/changed exports, props, types, component behavior, tokens, and bug fixes.

4. **Determine bump level** (unless overridden by modifier):
   - `major` — Removed/renamed exports, breaking prop or behavior changes, import path restructuring
   - `minor` — New components, composables, exports, public API additions (non-breaking)
   - `patch` — Bug fixes, style tweaks, internal refactors, docs edits, dev dep bumps
   - When uncertain and consumer impact exists, default to `patch`

5. **Draft the changeset body** following these formatting rules:
   - No markdown tables (they break in npm/changelog renderers)
   - No `#`/`##`/`###` headings (changesets auto-generates those) — use **bold text** to group related changes
   - List every prop change per component explicitly — don't summarize breaking changes
   - Non-breaking additions (icons, tokens, misc fixes) can be summarized in 1-2 lines
   - Keep it concise but complete — a consumer reading the changelog should understand what changed and whether it affects them
   - When updating an existing changeset, merge new changes into the existing body — reorganize and deduplicate as needed

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
