---
name: pull-design
description: Pull Figma design context for the current feature — extracts measurements, tokens, and component mapping before implementation
allowed-tools: [Bash, Read, Glob, Grep, mcp__jira__getJiraIssue, mcp__figma__get_design_context, mcp__figma__get_variable_defs, mcp__figma__get_metadata, mcp__figma__get_screenshot]
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

### Phase 3: Pull Design Context

5. **Call `get_design_context`** with the fileKey and nodeId. In your prompt to the tool, include project-specific conventions:
   - Read CLAUDE.md to determine the project's frontend framework, styling approach, and component patterns
   - Tell the tool to describe structure and measurements, NOT to generate production code
   - Reference the project's design token system (CSS variables, theme file, etc.) if one exists
   - Before calling the tool, scan the codebase for the existing component directory (glob for the frontend components folder). Include a list of existing component names in your annotation so the tool can reference them when describing the design.

6. **Call `get_variable_defs`** with the same fileKey and nodeId to extract design tokens.

7. **If the `get_design_context` response is truncated or very large**: call `get_metadata` to get sub-node IDs, then call `get_design_context` on each section separately. Present results grouped by section.

### Phase 4: Check for Eng Plan

8. **Look for an eng plan** in the conversation thread or on disk (`eng-plan/*.md` matching the ticket). If found, use it as context for the gap analysis in Phase 5.

### Phase 5: Present the Design Brief

Format the output as a **Design Brief** with these sections:

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

## Modifiers

- `+screenshot` — Also call `get_screenshot` and include the visual render in the output. Useful for documenting what a component looks like.

## Tips

- **Select one frame at a time.** Full pages produce truncated or noisy output. If the design has multiple sections, run `/pull-design` once per section or let the skill chunk automatically.
- **Run after `/eng-plan`.** The eng plan establishes component architecture. This skill fills in visual details — measurements, tokens, and gaps.
- **Figma shows the WHAT, not the HOW.** Don't let Figma output override architectural decisions from the eng plan.

## Arguments

$ARGUMENTS
