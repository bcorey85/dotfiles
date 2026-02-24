---
name: cache-design-tokens
description: Pull Figma design tokens and cache them in eng-arch/design-tokens.md for faster future /pull-design runs
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep, mcp__jira__getJiraIssue, mcp__figma__get_design_context, mcp__figma__get_variable_defs, mcp__figma__get_metadata, mcp__figma__get_screenshot]
---

# Cache Design Tokens

Extract the project's design system from Figma and cache it locally. This makes subsequent `/pull-design` runs faster — they diff against the cache instead of re-extracting everything.

## Instructions

### Phase 1: Find the Figma URL

1. **Check `$ARGUMENTS`** for a Figma URL (`figma.com/design/...`).
   - If found, use it directly. Skip to Phase 2.

2. **If no URL in arguments**, check the current Jira ticket:
   - Get branch name: `git branch --show-current`
   - Extract ticket key from branch name
   - Read `JIRA.md` for Cloud ID, fetch ticket via `getJiraIssue`
   - Scan description for `figma.com` URLs
   - If no URL found: ask the user to paste one

### Phase 2: Pull Design Context

3. **Extract `fileKey` and `nodeId`** from the URL (convert `-` to `:` in nodeId).

4. **Determine scope based on modifiers and URL:**

   **Default (single frame):** If a `node-id` is present and `+all` was NOT used:
   - Call `get_design_context` and `get_variable_defs` for that frame.

   **No node-id (no `+all`):** Call `get_metadata` on page root (`0:1`) to list top-level frames. Ask which frame best represents the full design system.

   **`+all` modifier:** Scan ALL top-level frames in the file:
   - Call `get_metadata` on page root (`0:1`) to list all top-level frames.
   - Call `get_design_context` on EACH top-level frame (in parallel if possible).
   - Merge tokens across all frames — deduplicate identical values, keep variants with distinguishing names when values differ (e.g., `bg-tag` vs `bg-modal-tag`).
   - For files with many frames (>5), warn the user about the number of MCP calls before proceeding.

5. **Scan the codebase** for existing components:
   ```
   glob: packages/web/src/components/**/*.vue
   ```

### Phase 3: Extract and Structure Tokens

7. Parse the Figma output and organize into these sections:

**Colors** — Group by semantic usage:
- Text colors (primary, secondary, muted, etc.)
- Background colors (page, card, column, input fields)
- Border colors
- Status/column header colors (with column name mapping)
- Priority badge colors (bg, border, text for each level)
- Interactive colors (button bg, hover states if visible)
- Overlay/backdrop colors

**Typography** — Font family + scale:
- Each level: element name, size, weight, line-height
- Example: `H1 (Board title): 30px / Bold (700) / 36px line-height`

**Spacing** — Recurring values:
- Page padding, column gaps, card gaps
- Card internal padding, section gaps
- Border-radius values (cards, badges, buttons, inputs)

**Shadows** — Box shadow values with semantic names

**Component Inventory** — Every distinct UI component visible:
- Name, whether it exists in code (with file path) or is NEW
- Brief description of what it renders
- Flag components that reference data NOT in the data model

### Phase 4: Check for Existing Cache

8. **Read `eng-arch/design-tokens.md`** if it exists.

9. **If it exists**: diff the old tokens against the new extraction. Present changes to the user:
   - ADDED tokens/components
   - CHANGED values (old -> new)
   - REMOVED items
   - Ask the user to confirm before overwriting.

10. **If it doesn't exist**: proceed directly to writing.

### Phase 5: Write the Cache File

11. **Write to `eng-arch/design-tokens.md`** using this format:

```markdown
# Design Tokens

> Last updated: YYYY-MM-DD
>
> Sources:
>   - [File Name](figma file URL) — frames: frame name (X:Y), other frame (A:B)
>   - [Other File](other URL) — frames: page (1:2)

## Colors

### Text
| Token | Hex | Usage |
|---|---|---|
| text-primary | #101828 | Headings, card titles |
...

### Backgrounds
...

### Borders
...

### Priority Badges
| Level | Background | Border | Text |
|---|---|---|---|
| high | #ffe2e2 | #ffc9c9 | #9f0712 |
...

### Column Headers
| Column | Background | Border |
|---|---|---|
| To Do | #f3f4f6 | #d1d5dc |
...

## Typography

| Element | Size | Weight | Line-height |
|---|---|---|---|
| H1 (Board title) | 30px | Bold (700) | 36px |
...

Font family: Inter

## Spacing

| Token | Value | Usage |
|---|---|---|
| page-padding | 32px | Board container padding |
...

## Shadows

| Name | Value |
|---|---|
| card | 0px 1px 3px rgba(0,0,0,0.1), 0px 1px 2px rgba(0,0,0,0.1) |
...

## Component Inventory

| Component | Status | Code Path | Notes |
|---|---|---|---|
| KanbanBoard | EXISTS | components/board/KanbanBoard.vue | |
...

## Data Model Gaps

Figma elements that reference data NOT in the current data model:
- [list items, or "None" if all elements map to existing fields]
```

12. **Confirm** to the user: show what was written and note the file path. Remind them that `/pull-design` will now diff against this cache on future runs.

## Modifiers

- `+all` — Scan ALL top-level frames in the file instead of just the specified frame. Useful for capturing the full design system in one run. Warns before proceeding if >5 frames.

## When to Re-run

- After significant Figma design changes (new components, color updates)
- When starting a new feature area with different visual patterns
- When adding a new Figma file for a new app section
- If `/pull-design` reports the cache looks stale

## Arguments

$ARGUMENTS
