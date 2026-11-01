---
type: "Change"
change_type: "changed"
title: "Frontend rules load on tsx and jsx files"
description: "React components now get the frontend style, TypeScript and testing rules: their path globs cover .tsx and .jsx beside .ts and .js."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T20:25:48-05:00"}
seq: 409
kind: "user-rule"
components: ["rule/frontend-style", "rule/typescript", "rule/testing"]
evidence: ["judgment"]
watches: []
test: ""
asked: "2026-10-31: on the frontend-style rule's path globs: we need to load that on tsx and jsx too"
proof: []
unmeasured: ""
---

## Change

- `rules/frontend-style.md`: paths gain `**/*.tsx` and `**/*.jsx`.
- `rules/typescript.md`: paths gain `**/*.tsx`, the TypeScript side of the same files.
- `rules/testing.md`: paths gain `**/*.test.tsx`, `**/*.test.jsx`, `**/*.spec.tsx` and `**/*.spec.jsx`, matching its `.ts` and `.js` test globs.

`rules/vue.md` stays on `**/*.vue` only.

## Evidence

The user asked for the frontend style rule to load on tsx and jsx files. The TypeScript and testing rules carried the same `.ts` and `.js` globs and missed the same files, so they get the matching globs.

## Result

No test pins rule path globs, so none was added. The globs are checked by reading the frontmatter.

## Watch

None: no intake number counts which rule loaded on a file.

## Back-out

Revert the commit.
