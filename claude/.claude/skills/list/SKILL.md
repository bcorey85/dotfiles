---
name: list
description: List the changes proposed in this conversation as one numbered list, best first, so the user can pick them by number. Use after an audit, review, research pass or plan that proposed edits. Triggers on "ol of proposed changes", "list the proposed changes", "numbered list of changes", "what are you proposing", "/list".
---

# List — the proposed changes as a numbered list

The user picks by number. Output is a list to choose from, not a report.

## Sources

Only changes already proposed in this conversation: audit findings, review findings, diff hunks, plan steps. A file written in this session (a report, a diff) counts. Do no new scan, search or subagent: a change not yet proposed is not on the list.

## Order

1. Changes that fix something broken now: a wrong path, an unset variable, a missing file.
2. Changes that remove a conflict between two files.
3. Changes that remove stale or extra text.
4. Flag-only items last, after a `Flags (no change proposed)` line.

Inside each tier, higher confidence first.

## Format

```
1. `<path:line>` — <the change, imperative, before → after when short>. Gate: <direct | meter | user>.
```

- One line each. No sub-bullets, no evidence, no rationale.
- Number continuously, flags included, so every item has one number.
- `Gate` is what it takes to ship: `direct` (a path or typo fix, edit plus change file), `meter` (a new or reworded rule, needs rule-meter runs first), `user` (the user decides).
- Merge changes that must ship together into one item and name every location in it.
- Name the file that holds the full text (report, diff) once, under the list.

## Closing line

End with one line: `Reply with numbers to apply (e.g. "1-3, 7").` Nothing after it.
