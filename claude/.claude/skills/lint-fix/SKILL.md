---
name: lint-fix
description: Run ESLint, Prettier, and type checking to auto-fix all issues in the project
allowed-tools: [Bash, Read, Glob]
user-invocable: true
---

# Lint Fix

Run ESLint, Prettier, and type checking. Execute the full pipeline in one pass — do NOT pause for approval.

## Modifiers

- `+no-types` — Skip the type-checking step.

## Instructions

1. **Detect environment**: Check `package.json` in the working directory (or nearest parent). Detect:
   - **Package manager**: `bun.lock` → bun, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, otherwise npm.
   - **Available tools**: Check dependencies/devDependencies for eslint, prettier, vue-tsc, typescript.
   - **Scripts**: Note any `lint`, `lint:fix`, `format`, `prettier`, `typecheck`, `type-check`, or `tsc` scripts in `package.json`.

2. **Run ESLint fix**: Use the `lint:fix` or `lint` script if one exists (append `--fix` if the script doesn't already include it); otherwise run `npx eslint . --fix`. Scope to argument paths if provided.

3. **Run Prettier fix**: Use the `format` or `prettier` script if one exists; otherwise run `npx prettier --write .`. Scope to argument paths if provided.

4. **Run type checking** (skip if `+no-types`): Pick the right checker:
   - If `vue-tsc` is in dependencies → run the `typecheck` / `type-check` script, or `npx vue-tsc --noEmit`.
   - Else if `typescript` is in dependencies → run the `typecheck` / `type-check` / `tsc` script, or `npx tsc --noEmit`.
   - Else skip and note that no type checker was found.

5. **Report results**: Summarize what was fixed. List any unfixable ESLint errors, Prettier failures, or type errors clearly so the user can address them manually.

## Arguments

$ARGUMENTS
