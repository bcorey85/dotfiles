---
name: migrate-component
description: Migrate a component from the React toolkit to the Vue toolkit — investigates React source for feature parity, pulls Figma tokens, and produces an implementation plan.
allowed-tools: [Task, Read, Glob, Grep, Bash, AskUserQuestion, Skill, mcp__figma__get_design_context, mcp__figma__get_variable_defs, mcp__figma__get_metadata, mcp__figma__get_screenshot]
---

# Migrate Component

Migrate a component from the React reference toolkit to the Vue toolkit. Investigates the React source for feature parity, pulls Figma design context/tokens, and produces a phased implementation plan.

## Usage

```
/migrate-component <component-name> <figma-url> [modifiers]
```

Example: `/migrate-component pagination https://www.figma.com/design/DCoURttbQoysmX5lbVyxwc/Supernova-2.0-DS?node-id=3284-22482&p=f&m=dev`

## Modifiers

- `+screenshot` — Also call `get_screenshot` and include the visual render.

## Instructions

### Phase 0: Parse Arguments

1. **Extract from `$ARGUMENTS`:**
   - **Component name** — the first non-URL, non-modifier token (e.g., `pagination`)
   - **Figma URL** — any `figma.com/design/...` URL
   - **Modifiers** — tokens starting with `+`

2. **Detect source and target repos:**
   - **Target** = current working directory (should be the Vue toolkit)
   - **Source** = read the target project's `CLAUDE.md` and look for a React reference path (e.g., "Reference implementation: ~/dev/..."). If not found, ask the user.
   - Read both projects' `CLAUDE.md` files for stack context.

3. **If component name or Figma URL is missing**, ask the user.

### Phase 1: Investigate React Source (Feature Parity Audit)

4. **Launch an Explore agent** (`subagent_type: Explore`, thoroughness: `"very thorough"`) against the **source** repo to investigate the React component. Instruct it to find and document:

   - **Component file(s):** Main component, sub-components, index/barrel exports
   - **Props interface:** Every prop with its type, default value, and whether it's required — copy the full TypeScript interface verbatim
   - **Variants/sizes:** All visual variants (e.g., severity, size, outlined, text, rounded)
   - **Slots/children:** Named slots or render prop patterns
   - **Internal state:** Any useState/useReducer/useRef hooks and what they control
   - **Event handlers:** All callbacks (onChange, onPageChange, onClick, etc.) with their signatures
   - **Composition:** What MUI (or other library) components does it wrap? What does it add on top?
   - **Styles:** CSS/SCSS/styled-components — extract the actual style rules, breakpoints, and tokens used
   - **Tests:** Summarize what the test file covers (if tests exist)
   - **Accessibility:** ARIA attributes, keyboard navigation, screen reader support
   - **`testId` convention:** How `data-testid` attributes are applied
   - **Exports:** What's exported from the component's index file

   **Explicitly instruct the agent NOT to edit or write any files.**

5. **Present the React Audit** to the user as a structured summary:
   - Component name and file location in source repo
   - Full props interface
   - Variants and visual states
   - Behaviors and interactions
   - Accessibility features
   - Test coverage summary

### Phase 2: Pull Figma Design Context

6. **Parse the Figma URL** — extract `fileKey` and `nodeId` (convert `-` to `:` in nodeId).

7. **If no `node-id` in the URL**: call `get_metadata` to list available frames. Present them and ask which to pull.

8. **Check for cached design tokens** — look for `eng-arch/design-tokens.md` in the target repo. If it exists, read it.

9. **Call `get_design_context`** with the fileKey and nodeId. Include the target project's component conventions (PrimeVue unstyled, SCSS tokens, PT preset) in your prompt to the tool.

10. **Call `get_variable_defs`** with the same fileKey and nodeId.

11. **If `+screenshot` modifier**: also call `get_screenshot`.

12. **Ignore dark mode** — filter out any dark-mode-specific tokens, variants, or color mappings from the Figma output. Only extract light-mode values.

### Phase 3: Cross-Reference & Gap Analysis

13. **Check the target repo** for existing patterns:
    - Read `lib/primevue/preset.ts` for existing PT patterns
    - Glob `lib/components/` for existing components (to match conventions)
    - Read `lib/assets/scss/components/` for SCSS patterns
    - Check `docs/component-mapping.md` if it exists
    - Check `docs/migration_plan.md` if it exists

14. **Map React features to Vue equivalents:**

    | React Pattern | Vue Equivalent |
    |---|---|
    | Props interface | `defineProps<T>()` with same prop names |
    | `children` / render props | Vue `<slot>` / named slots |
    | `useState` | `ref()` / `reactive()` |
    | `useEffect` | `watch()` / `onMounted()` |
    | `useCallback`/`useMemo` | `computed()` |
    | `forwardRef` | `defineExpose()` |
    | MUI component | PrimeVue equivalent (unstyled + PT) |
    | MUI `sx` prop / styled() | SCSS component file + PT classes |
    | `className` prop | `:class` binding in PT or template |
    | `data-testid` | Same convention via PT `data-testid` or template attribute |

15. **Identify gaps:**
    - React props with no clear PrimeVue equivalent
    - Behaviors that need custom implementation (not covered by PrimeVue)
    - Figma tokens that don't exist in the current SCSS variables
    - Figma visual states not covered by the React component

### Phase 4: Present Migration Plan

16. **Present the plan** to the user with these sections:

---

**Component:** `<ComponentName>`
**Source:** `<path in React toolkit>`
**Target:** `lib/components/<ComponentName>/`
**PrimeVue Base:** `<PrimeVue component name>` (or "Custom — no PrimeVue equivalent")

**Props Interface (Vue)**
```typescript
// Mapped from React, adapted for Vue conventions
interface <ComponentName>Props {
  // ... full interface
}
```

**Variants & Visual States**
- List all variants from React + any additional states from Figma
- Note which are handled by PrimeVue PT vs custom SCSS

**Figma Token Mapping**
| Figma Token | SCSS Token | Status |
|---|---|---|
| `color/...` | `colors.$...` | Exists / NEW |
| `space/...` | `space.space(N)` | Exists / NEW |

**Files to Create/Modify**

| File | Action | Description |
|---|---|---|
| `lib/components/<Name>/<Name>.vue` | Create | Main component |
| `lib/assets/scss/components/_<name>.scss` | Create | Component styles |
| `lib/primevue/preset.ts` | Modify | Add PT entry for PrimeVue component |
| `lib/components/index.ts` | Modify | Export new component |
| `src/pages/<Name>Page.vue` | Create | Demo page with all variants |
| `src/router.ts` | Modify | Add demo route |
| `src/pages/HomePage.vue` | Modify | Add link to demo |
| `docs/component-mapping.md` | Modify | Document migration |

**Implementation Sequence**
1. Numbered steps with dependencies noted

**Feature Parity Checklist**
- [ ] Each React feature mapped to Vue implementation
- [ ] Each Figma visual state accounted for

**Open Questions** (if any)
- Decisions that need user input before implementation

---

### Phase 5: Approval → Implement → Review

17. **HARD STOP — Wait for explicit user approval of the plan before proceeding.**

    Present the plan and ask: "Ready to implement, or want to adjust?"
    - **Adjust** → Take feedback and revise the plan, then ask again.
    - **Approved** → Proceed to step 18.

    Do NOT ask about saving to disk. The plan lives in the conversation only.

18. **Auto-dispatch `/code fe`** — invoke the Skill tool (`skill: "code", args: "fe"`) with the full migration plan as context. The coder has everything it needs: React audit, Figma tokens, Vue props interface, file list, and implementation sequence.

19. **After coder completes**, auto-dispatch `/peer-review` — invoke the Skill tool (`skill: "peer-review"`). This is mandatory; never skip it.

## Arguments

$ARGUMENTS
