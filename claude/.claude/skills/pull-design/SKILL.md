---
name: pull-design
description: Pull Figma design context for the current feature — extracts measurements, tokens, and component mapping before implementation
allowed-tools:
  [
    Bash,
    Read,
    Edit,
    Glob,
    Grep,
    mcp__jira__getJiraIssue,
    mcp__figma__get_design_context,
    mcp__figma__get_variable_defs,
    mcp__figma__get_metadata,
    mcp__figma__get_screenshot,
  ]
---

# Pull Design Context

Pull Figma design context for the current feature. Run before `/eng-spec`, so the architect has design context.

## Instructions

If the Figma MCP tools aren't available in this session, say so and stop — don't describe designs from memory.

### Phase 1: Find the Figma URL

1. **Check `$ARGUMENTS`** for a Figma URL (`figma.com/design/...` or `figma.com/file/...`).
   - If found, use it directly. Skip to Phase 2.

2. **If no URL in arguments**, check the current Jira ticket:
   - Resolve + fetch per `jira-ticket.md` (read it) — **optional-ticket caller**: no key/MCP → skip to asking the user for the URL.
   - Scan the description for `figma.com` URLs (`getJiraIssue` may exclude comments — don't silently miss those; ask the user instead).
   - One URL → use it (say where found); several → list and ask; none → ask the user to paste it

### Phase 2: Parse the URL

3. **Extract `fileKey` and `nodeId`** from the URL:
   - `figma.com/design/:fileKey/:fileName?node-id=:nodeId` — convert `-` to `:` in nodeId
   - `figma.com/design/:fileKey/branch/:branchKey/:fileName` — use branchKey as fileKey

4. **If no `node-id` in the URL**: call `get_metadata` to list available top-level frames. Present them and ask which to pull.

### Phase 3: Check for Cached Design Tokens

5. **Read `docs/architecture/design-tokens.md` if present** (cached design system). Cache exists → Phase 6 is a NEW/CHANGED-only diff, never re-extraction. No cache → full extraction.

### Phase 4: Pull Design Context

6. **Call `get_design_context`** with fileKey + nodeId. In the tool prompt: project conventions from CLAUDE.md (framework, styling, patterns); describe structure + measurements, NOT production code; reference the project's token system if any; include existing component names (glob the components folder first) so the tool can reference them.

7. **Call `get_variable_defs`** with the same fileKey and nodeId to extract design tokens.

8. **Truncated/huge response** → `get_metadata` for sub-node IDs, `get_design_context` per section, results grouped by section.

### Phase 5: Check for Eng Plan

9. **Look for an eng plan** in the conversation thread or on disk (`docs/plans/*.md` matching the ticket). If found, use it as context for the gap analysis in Phase 6.

### Phase 6: Present the Design Brief

**Cache exists → lightweight diff brief.** Frame-specific measurements (only NEW/CHANGED vs cache), New Elements ("NEW — not in cached tokens"), Token Conflicts, then the shared sections below.

**No cache → full brief:**

**Measurements**

- Frame dimensions, column widths, gap values, padding, border radius — exact values

**Design Tokens**

- Colors (map Figma variables to project tokens; flag unmatched), Typography (family, sizes, weights, line heights), Spacing (padding, gap, margin)

**Component Inventory**

- Figma components in this frame; per component, matching code component exists or NEW

**Shared sections (both modes)**

**Data-model gaps**

- Figma elements referencing data outside the current data model (from cache or freshly detected)

**Visual Decisions**

- Interactive states (hover, active, disabled, focus); UI states (empty, loading, error) if separate frames
- Details NOT covered by ticket AC — "Figma shows [X], ticket is silent — implementing as shown unless you say otherwise"

**Gaps & Conflicts** (only if eng plan exists)

- Figma/plan discrepancies; precedence ticket-AC-for-behavior, Figma-for-visuals; plan omissions (with rationale if noted)

**Next Step**
"Design context loaded. Ready for `/code` with these measurements as reference."

### Phase 7: Auto-Update Cache (only if cache existed in Phase 3)

10. **Append NEW tokens to the cache** (`docs/architecture/design-tokens.md`): new entries into each relevant sub-table (Colors, Typography, Spacing, Shadows, Border Radius, Component Inventory) + the `Frames:` header line. Append-only — never modify existing entries. CONFLICTS (same role, different value) get a distinguishing name (`bg-tag` vs `bg-modal-tag`).

11. **Briefly note** what was added: "Updated cache with N new tokens from [frame name]."

---

## Modifiers

- `+screenshot` — Also call `get_screenshot` and include the visual render in the output. Useful for documenting what a component looks like.

## Tips

- **One frame at a time** — chunk multi-section designs.
- **Figma shows the WHAT, not the HOW.** Don't let Figma output override architectural decisions from the eng plan.

## Arguments

$ARGUMENTS
