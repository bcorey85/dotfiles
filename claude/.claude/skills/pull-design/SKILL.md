---
name: pull-design
description: Pull Figma design context for the current feature — extracts measurements, tokens, and component mapping before implementation
allowed-tools: [Bash, Read, Edit, Glob, Grep, mcp__jira__getJiraIssue, mcp__figma__get_design_context, mcp__figma__get_variable_defs, mcp__figma__get_metadata, mcp__figma__get_screenshot]
---

# Pull Design Context

Pull Figma design context for the current feature. Run after `/eng-plan`, before `/code`.

## Instructions

### Phase 1: Find the Figma URL

1. **Check `$ARGUMENTS`** for a Figma URL (`figma.com/design/...` or `figma.com/file/...`).
   - If found, use it directly. Skip to Phase 2.

2. **If no URL in arguments**, check the current Jira ticket:
   - Get branch name: `git branch --show-current`
   - Extract ticket key (e.g., `TAS-13` from `TAS-13-board-rendering`)
   - Read `JIRA.md` for Cloud ID, fetch ticket via `getJiraIssue`
   - Scan the ticket description for `figma.com` URLs. Note: `getJiraIssue` may not include comments by default. If no URL found in the description, proceed to asking the user rather than silently missing URLs in comments.
   - If one URL found: use it, tell the user where you found it
   - If multiple URLs found: list them and ask which frame to pull
   - If no URL found: ask the user to paste the Figma frame URL

### Phase 2: Parse the URL

3. **Extract `fileKey` and `nodeId`** from the URL:
   - `figma.com/design/:fileKey/:fileName?node-id=:nodeId` — convert `-` to `:` in nodeId
   - `figma.com/design/:fileKey/branch/:branchKey/:fileName` — use branchKey as fileKey

4. **If no `node-id` in the URL**: call `get_metadata` to list available top-level frames. Present them and ask which to pull.

### Phase 3: Check for Cached Design Tokens

5. **Check for `eng-arch/design-tokens.md`**. If it exists, read it — this is the cached design system from a previous `/cache-design-tokens` run. This changes how Phase 6 works:
   - **Cache exists**: You already have the full design system (colors, typography, spacing, component inventory). Do NOT re-extract or re-document these. Phase 6 becomes a lightweight diff — only report what's NEW or CHANGED in this frame vs the cache.
   - **No cache**: Full extraction mode (original behavior). Suggest running `/cache-design-tokens` after this pull to speed up future runs.

### Phase 4: Pull Design Context

6. **Call `get_design_context`** with the fileKey and nodeId. In your prompt to the tool, include project-specific conventions:
   - Read CLAUDE.md to determine the project's frontend framework, styling approach, and component patterns
   - Tell the tool to describe structure and measurements, NOT to generate production code
   - Reference the project's design token system (CSS variables, theme file, etc.) if one exists
   - Before calling the tool, scan the codebase for the existing component directory (glob for the frontend components folder). Include a list of existing component names in your annotation so the tool can reference them when describing the design.

7. **Call `get_variable_defs`** with the same fileKey and nodeId to extract design tokens.

8. **If the `get_design_context` response is truncated or very large**: call `get_metadata` to get sub-node IDs, then call `get_design_context` on each section separately. Present results grouped by section.

### Phase 5: Check for Eng Plan

9. **Look for an eng plan** in the conversation thread or on disk (`eng-plan/*.md` matching the ticket). If found, use it as context for the gap analysis in Phase 6.

### Phase 6: Present the Design Brief

**If cached tokens exist** — present a lightweight brief:

**Frame-Specific Measurements**
- Dimensions, layout, and spacing unique to THIS frame (e.g., modal width/height, field grid layout)
- Only include values that differ from or aren't covered by the cached tokens

**New Elements** (not in cache)
- NEW components, colors, or patterns that appear in this frame but aren't in `design-tokens.md`
- Flag these clearly: "NEW — not in cached tokens"

**Token Conflicts** (if any)
- Values in this frame that DIFFER from the cached tokens (e.g., a color used differently)

**Visual Decisions**
- Interactive states shown in Figma (hover, active, disabled, focus)
- UI states (empty, loading, error) if present as separate frames
- Any visual detail NOT covered by the Jira ticket AC — flag these: "Figma shows [X], ticket is silent — implementing as shown unless you say otherwise"

**Data Model Gaps**
- Figma elements that reference data NOT in the current data model (from cache or freshly detected)

**Gaps & Conflicts** (only if eng plan exists)
- Discrepancies between Figma and the eng plan
- Recommend precedence: ticket AC > Figma for behavior; Figma > ticket for visual measurements
- Figma elements the eng plan intentionally omits (with rationale if noted in the plan)

**Next Step**
"Design context loaded. Ready for `/code` with these measurements as reference."

### Phase 7: Auto-Update Cache (only if cache existed in Phase 3)

10. **If the diff found NEW tokens, colors, typography, spacing, shadows, or components**: automatically append them to `eng-arch/design-tokens.md` using the Edit tool.
    - Add new colors to the appropriate Colors sub-table (Text, Backgrounds, Borders, etc.)
    - Add new typography entries to the Typography table
    - Add new spacing tokens to the Spacing table
    - Add new shadows to the Shadows table
    - Add new border-radius values to the Border Radius table
    - Add new components to the Component Inventory table
    - Update the `Frames:` line in the header to include the new frame name and node-id
    - Do NOT remove or modify existing entries — only append new ones
    - If a token CONFLICTS (same semantic role, different value), add the new variant with a distinguishing name (e.g., `bg-tag` for cards vs `bg-modal-tag` for modal)

11. **Briefly note** what was added: "Updated cache with N new tokens from [frame name]."

---

**If NO cached tokens** — present the full brief:

**Measurements**
- Frame dimensions, column widths, gap values, padding, border radius
- Exact values from the design

**Design Tokens**
- Colors: map Figma variable names to the project's existing token system. Flag any colors in the design that don't have a matching project token.
- Typography: font family, sizes, weights, line heights
- Spacing: padding, gap, margin values

**Component Inventory**
- List Figma components visible in this frame
- For each, note whether a matching code component already exists (check the codebase) or is NEW
- Flag Figma elements that reference data the current data model doesn't have (e.g., "Figma shows assignee avatar — not in our data model")

**Visual Decisions**
- Interactive states shown in Figma (hover, active, disabled, focus)
- UI states (empty, loading, error) if present as separate frames
- Any visual detail NOT covered by the Jira ticket AC — flag these: "Figma shows [X], ticket is silent — implementing as shown unless you say otherwise"

**Gaps & Conflicts** (only if eng plan exists)
- Discrepancies between Figma and the eng plan
- Recommend precedence: ticket AC > Figma for behavior; Figma > ticket for visual measurements
- Figma elements the eng plan intentionally omits (with rationale if noted in the plan)

**Next Step**
"Design context loaded. Ready for `/code` with these measurements as reference."
Suggest: "Run `/cache-design-tokens` to cache the design system for faster future pulls."

## Modifiers

- `+screenshot` — Also call `get_screenshot` and include the visual render in the output. Useful for documenting what a component looks like.

## Tips

- **Select one frame at a time.** Full pages produce truncated or noisy output. If the design has multiple sections, run `/pull-design` once per section or let the skill chunk automatically.
- **Run after `/eng-plan`.** The eng plan establishes component architecture. This skill fills in visual details — measurements, tokens, and gaps.
- **Figma shows the WHAT, not the HOW.** Don't let Figma output override architectural decisions from the eng plan.

## Arguments

$ARGUMENTS
