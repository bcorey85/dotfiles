---
name: component-refactor
description: Refactor a React or Vue component for readability — extract subcomponents, utils, hooks, and flatten logic. Optimizes for human-scannable code.
allowed-tools: [Read, Write, Edit, Grep, Glob, Bash, Agent]
user-invocable: true
---

# Component Refactor

Refactor a component to maximize human readability and maintainability. The goal: a developer should be able to open the file and understand the full picture in under 30 seconds.

**Core principle:** A component should either _implement logic_ or _compose other components_ — never both. If it's doing both, it needs decomposition.

## Arguments

$ARGUMENTS — path to a component file, or a component name to locate.

## Modifiers

- `+dry` — Analysis only. Print the refactoring plan but make no changes.
- `+utils` — Focus only on extracting pure JS/TS to `.utils.ts`.
- `+structure` — Focus only on subcomponent/hook extraction (skip utils).

## Instructions

### Phase 0: Locate and Read

1. Resolve the target component file. If a name is given without a path, search for it in the project's component directories.
2. Read the full component file and any co-located files (`.utils.ts`, `.types.ts`, child components).
3. Detect framework: `.tsx`/`.jsx` → React, `.vue` → Vue.

### Phase 1: Analyze

Score the component on these dimensions (note findings, don't change anything yet):

**A. Overall size & scrollability**
- Can the component be read without scrolling on a laptop screen (~50 lines of logic)?
- If scrolling is needed, it's too large — decomposition is warranted.

**B. Implements-vs-composes violation**
- Does the component both implement complex logic AND compose multiple child sections?
- A healthy component does one or the other. Flag if it does both.

**C. Return statement density (React only)**
- Count lines of JSX in the final `return` statement
- Flag inline ternaries, logical expressions (`&&`), and nested conditionals
- Flag any non-trivial expression inside JSX attributes (more than a simple variable reference)
- Flag `renderFoo()` methods — these are an anti-pattern (they share parent scope implicitly, obscuring dependencies). Extract to actual components or named JSX variables instead.

**D. Logic in the render path**
- Inline computations in JSX/template (`{items.filter(...).map(...)}`)
- Complex boolean expressions not assigned to a named variable
- Inline event handlers longer than one simple call (e.g., `onClick={() => { setState(...); track(...); }}`)

**E. Pure function candidates**
- Formatting functions (dates, currency, strings)
- Validation logic
- Data transformations (mapping, filtering, sorting)
- Conditional class builders beyond a simple `clsx` call
- Anything that takes args and returns a value with no dependency on component state or React/Vue reactivity

**F. Subcomponent candidates (React only)**
- Repeated JSX blocks (2+ occurrences of structurally similar markup)
- Self-contained render sections with their own conditional logic (e.g., a header area, an empty state, a list item)
- Any JSX block >15 lines that can be described with a single noun

**G. Custom hook / composable candidates**
- A group of related `useState` + `useEffect` (React) or `ref` + `watch`/`computed` (Vue) that form a cohesive concern
- State + handlers that could be described as a single behavior (e.g., "pagination", "file upload progress", "form validation")

**H. Breakout-to-file candidates**
- A subcomponent that manages its own state (any `useState`/`useReducer`)
- A subcomponent that needs its own props interface (>3 props)
- A subcomponent >40 lines of JSX
- A subcomponent reusable by sibling components
- If any of these apply → extract to its own file in the same directory, not just a variable

**I. Structural clarity**
- Nested conditionals that could be flattened with early returns or guard clauses
- Deeply nested ternaries in JSX (>1 level)
- Missing named constants for non-obvious values

**J. Conditional rendering hygiene (React only)**
- `condition ? <X /> : null` → should be `condition && <X />`
- `array && <List />` → should be `array.length > 0 && <List />` (avoids rendering "0")
- Nested ternaries (>1 level deep) → extract to named variable or early return

### Phase 2: Plan

Present the refactoring plan to the user as a checklist, grouped by category:

```
## Refactoring Plan: CbFoo

### Utils extraction → CbFoo.utils.ts
- [ ] `formatFileSize(bytes)` — lines 45-52, pure formatting
- [ ] `getStatusColor(status)` — lines 78-85, pure mapping

### Derived state (hoist above return)
- [ ] `isUploadComplete` — inline ternary at line 102
- [ ] `visibleItems` — filter+map chain at line 115

### Subcomponent variables (React only)
- [ ] `headerContent` — lines 130-155, static header with conditional badge
- [ ] `emptyState` — lines 160-180, self-contained empty view

### Breakout to file
- [ ] `CbFooListItem` → new file — has own state (selected, hovered), 60 lines JSX, own props

### Custom hook / composable extraction
- [ ] `useFileUpload` — useState x3 + useEffect at lines 20-55, cohesive upload concern

### Early returns / guard clauses
- [ ] Flatten nested if/else at line 90 → early return for error state

### Event handler extraction
- [ ] `handleFileSelect` — inline onChange at line 200, 8 lines

### Conditional rendering cleanup (React only)
- [ ] Line 105: `status ? <Badge /> : null` → `status && <Badge />`
- [ ] Line 120: nested ternary → extract to `statusIndicator` variable
```

If `+dry` modifier is set, stop here.

### Phase 3: Execute

Apply changes in this order (each step should leave the component in a working state):

1. **Extract utils** → Create or update `ComponentName.utils.ts`. Export named functions. Add imports to the component. Write unit tests in `ComponentName.utils.test.ts` for each extracted function.

2. **Extract custom hooks/composables** → For React: create `use{Name}.ts` in the same directory. For Vue: first try an inline composable within `<script setup>` — a `function use{Name}()` that groups related state+logic and returns its interface. Only promote to a separate file when reusable across components. Move related state + effects as a unit.

3. **Breakout subcomponents** → Create new component files in the same directory. Follow project scaffold conventions. Keep the parent's import clean.

4. **Hoist derived state** → Move complex expressions to named `const` declarations above the return. Use descriptive names that read as boolean questions (`isDisabled`, `hasResults`, `shouldShowBanner`) or noun phrases (`visibleItems`, `activeFilters`).

5. **Extract event handlers** → Move inline handlers to named `function` declarations above the return. Name them `handle{Event}` (React) or `on{Event}` (Vue).

6. **Hoist subcomponent variables (React only)** → For JSX blocks that don't warrant their own file, extract to `const fooContent = (...)` variables above the return. Name them as noun phrases describing what they render. **Never use `renderFoo()` methods** — they share parent scope implicitly, making dependencies invisible.

7. **Flatten control flow** → Replace nested conditionals with early returns. Replace nested ternaries with named variables or extracted subcomponents. Clean up conditional rendering idioms (see Phase 1 section J).

8. **Clean up the return statement** → The final return should read like an outline of the component — mostly composed of named variables and subcomponents with minimal inline logic.

### Phase 4: Verify

1. Run type-check on the affected package
2. Run existing tests for the component
3. Run new util tests
4. Verify no lint errors on changed files

## Framework-Specific Rules

### React

- **Subcomponent variables** are the primary readability tool. The final `return` should read like a table of contents.
- Name subcomponent variables as noun phrases: `headerContent`, `actionButtons`, `emptyState`, `fileList`.
- Subcomponent variables go directly above the `return` statement, after all hooks and handlers.
- Order in component body: types/interfaces → hooks → derived state → handlers → subcomponent variables → return.
- **Never write `renderFoo()` helper methods.** They implicitly close over parent state/props, hiding dependencies. Use named JSX variables (`const fooContent = (...)`) or extract to a real component with explicit props.
- Co-locate state with the component that uses it. If a subcomponent's state is unrelated to the parent's purpose, that's a breakout-to-file signal.

### Vue (`<script setup>`)

- **Do NOT hoist template sections to variables.** Vue's `v-if`/`v-for`/`v-show` directives are already declarative and readable in templates.
- **DO extract** complex computed logic, watchers, and helper functions to utils or composables.
- **DO extract** child components to separate files when they have their own state or are >40 lines of template.
- **Try inline composables first.** Before creating a `use{Name}.ts` file, group related logic into a `function use{Name}()` inside `<script setup>` that returns its public interface. Promote to a file only when reused across components.
- Template should use simple variable references — if a template expression is complex, move it to a `computed()`.
- Order in `<script setup>`: imports → props/emits → composables → refs/reactive → computed → watchers → handlers → lifecycle hooks.

## Naming Conventions

| Artifact | Pattern | Example |
|---|---|---|
| Utils file | `ComponentName.utils.ts` | `CbFileUploadItem.utils.ts` |
| Utils test | `ComponentName.utils.test.ts` | `CbFileUploadItem.utils.test.ts` |
| Custom hook | `use{Concern}.ts` | `useFileUpload.ts` |
| Breakout component | `ComponentName{Part}/` | `CbFooListItem/` |
| Subcomponent variable | `{noun}Content` / `{noun}Section` | `headerContent`, `emptyState` |
| Derived state | `is{Adj}` / `has{Noun}` / `should{Verb}` / `{noun}s` | `isDisabled`, `visibleItems` |
| Event handler (React) | `handle{Event}` | `handleFileSelect` |
| Event handler (Vue) | `on{Event}` | `onFileSelect` |

## What NOT to Do

- Don't rename existing props or public API — this is an internal refactor only
- Don't change behavior — refactoring must be transparent to consumers
- Don't extract trivial one-liners to utils just for the sake of it
- Don't create a utils file for a single tiny function — inline it as a named const
- Don't hoist JSX that's already clean (a single `<Component prop={value} />` doesn't need extraction)
- Don't add comments explaining what extracted variables are — the name should be self-documenting
- Don't extract React subcomponents that use parent closures heavily (>3 values from parent scope) — they'll need too many props, defeating the purpose
- Don't use `renderFoo()` methods — extract to named variables or real components with explicit props
- Don't prematurely extract Vue composables to files — try inline first, promote to file when reused
