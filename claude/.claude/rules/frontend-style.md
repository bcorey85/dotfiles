---
paths:
  - "**/*.vue"
  - "**/*.ts"
  - "**/*.js"
---

# Frontend Style

- CRITICAL: Always use curly braces `{}` on control flow blocks (`if`, `else`, `for`, `while`, `do`), even single-line. Braceless blocks are a lint error and will break CI.
- `function` for declarations, arrow functions for callbacks.
- `const` over `let`; never `var`.
- Template literals over string concatenation.
- Strict equality (`===`/`!==`) only.
- Early returns over nested conditionals.
- Named exports only — no default exports.
- Sort imports: external → internal → relative.
- No semicolons unless project rules say otherwise.
- Colocate tests, types, styles with their module (e.g., `Button/Button.vue`, `Button/Button.test.ts`, `Button/Button.types.ts`).
- `index.ts` re-exports at leaf folders only — no large barrel files.
