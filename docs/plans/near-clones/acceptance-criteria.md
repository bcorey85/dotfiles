# Acceptance criteria

- **AC1** — branch-prep lists a renamed copy (same body, different names) of an existing function as a candidate pair, on Python and TypeScript fixtures. (Phase 1)
- **AC2** — branch-prep lists a one-token variant (`<` against `<=`) of an existing function as a near-match pair, on Python and TypeScript fixtures. (Phase 1)
- **AC3** — For a domain-named function with a generic body (a `getNodeFromPlan` that only finds an item in a list by key), branch-prep lists the generic helper among its nearest other functions, on Python and TypeScript fixtures. (Phase 1; ruling in Plan Deviations)
- **AC4** — Each of AC1–AC3 has a test in `tests/scripts/` that fails without the change and passes with it. (Phase 1)
- **AC5** — The pass makes no model call and branch-prep runs under 10 s on the dotfiles repo. (Phase 1)
- **AC6** — The refactor SKILL.md step 3a and both smell-reviewer.md copies describe the new candidate kinds. (Phase 1)
- **AC7** — `bash tests/run.sh` passes. (all)
