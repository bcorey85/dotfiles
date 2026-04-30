---
name: audit-docs
description: Audit a docs tree for stale data, broken code pointers, duplication, and drift between docs and code. Use when the user says "/audit-docs", "audit the docs", "check for stale docs", "find duplicate info in docs", or asks for a doc-tree health pass. Read-only — produces a report, does not edit.
---

# Audit-docs

Sweep a docs tree, find rot, report it. Read-only — the user fixes the findings (or invokes `/write-doc` to rewrite).

## Arguments

`<scope>` — optional. Defaults to the current repo's `docs/`. Accepts:

- A directory path (`<repo>/docs/eng-arch/`) — audit just that folder.
- A repo name when run from a multi-repo workspace — audit that repo's `docs/`.
- `all` — audit every `docs/` directory under the workspace root (siblings of the cwd).

## Phase 1 — Inventory

1. Resolve scope to a concrete list of directories.
2. Glob `**/*.md` under each. Record file path, line count, and last-modified date for each.
3. If the inventory is over ~50 files, ask the user whether to narrow before running checks (the report gets noisy fast).

## Phase 2 — Run checks in parallel

Five independent checks. Run as parallel Bash/Grep calls.

### Check 1 — Broken `file:line` pointers

Every doc in `docs/eng-arch/` and `docs/coordination/` (or equivalent behavioral docs) tends to anchor on `path/to/file.ts:NN` or `path/to/file.ts` references. For each:

1. Extract all matches of `\`[^`]+\.[a-z]+:\d+\``and bare`[a-z][a-z0-9_/-]+\.(ts|js|py|md|sql|yaml|yml|tsx)` strings.
2. For each, check the file exists. If a line number is given, check the file has that many lines.
3. **Report**: file does not exist OR line out of range OR file exists but is much smaller than the cited line (within ±10 lines is fine — drift, not broken).

### Check 2 — Stale temporal phrases

Pattern-match for time-relative claims that age silently:

- `\b(today|currently|right now|at the moment|as of (today|now))\b`
- `\b(this (week|month|quarter|year))\b`
- `\b(last|next) (week|month|quarter)\b`
- `\b(recently|lately|just (added|shipped|landed))\b`
- Hardcoded dates: `\d{4}-\d{2}-\d{2}` — flag any older than **30 days** from `currentDate`.

**Report**: file:line, the matched phrase, the age (if a date is nearby in the same paragraph). One pass per file.

### Check 3 — Duplicate facts

Heuristic detection. Two docs likely duplicate if both contain:

- The same proper noun (CamelCase identifier, dotted path, file name) **and**
- The same number (`\d{2,}`) within 5 lines of it.

Process:

1. For each pair of docs, find shared proper nouns.
2. For each shared noun, check if both files have the same nearby number.
3. **Report**: pairs of `file:line` ranges that look duplicated, with the shared anchor. Do not auto-merge.

### Check 4 — Drift between doc claims and code

For doc files in behavioral genres (`eng-arch/`, `architecture/`, `behavior/`):

1. Pull cited code pointers (Check 1's matches that resolved).
2. Scan the cited file ±10 lines for symbols mentioned in the doc paragraph.
3. **Report**: doc says `MAX_TOOL_ROUNDS = 3` but the cited line now reads `MAX_TOOL_ROUNDS = 5`. This is a heuristic — false positives are expected. Tag findings as **likely** vs **certain**.

### Check 5 — Orphan and overlap

- **Orphans**: docs not referenced by any other doc and not in a top-level README/index. Report as candidates for deletion or promotion.
- **Overlap**: two docs whose top-level headings (`##` only) overlap by ≥3 entries. Report as candidates for merging.

## Phase 3 — Report

Single markdown report. Sections in this order, each present only if it has findings:

```
# Doc audit — <scope> — <date>

## Broken pointers (<n>)

| Doc | Pointer | Problem |
| --- | ------- | ------- |
| `docs/eng-arch/x.md:42` | `worker/src/foo.ts:108` | line out of range (file has 90 lines) |

## Stale temporal phrases (<n>)

| Doc | Line | Phrase | Age |
| --- | ---- | ------ | --- |

## Likely duplicates (<n>)

| Doc A | Doc B | Shared anchor | Recommendation |
| ----- | ----- | ------------- | -------------- |

## Likely drift between doc and code (<n>)

| Doc | Cited code | Doc claim | Code now says |
| --- | ---------- | --------- | ------------- |

## Orphan docs (<n>)

| Doc | Last modified | Candidate action |
| --- | ------------- | ---------------- |

## Heading overlap (<n>)

| Doc A | Doc B | Overlapping sections |
| ----- | ----- | -------------------- |

## Suggested next moves

1-3 concrete actions, ranked. e.g. "Run /write-doc to merge X and Y", "Open these three pointers and fix the line numbers", "Delete this orphan".
```

## Guidelines

- **Read-only.** Never edit a doc during audit. The user picks what to fix.
- **One report per run.** Don't propose fixes inline; consolidate at the end.
- **Heuristics are heuristics.** Tag uncertain findings as "likely". A false-positive-heavy report still beats no audit, but flag the noise honestly.
- **Don't audit code-comment files** (`CHANGELOG.md`, `LICENSE`, auto-generated API docs). Stick to `docs/`.
- **Cap the report at ~80 lines of findings.** If more, summarize the rest as "+N similar". Long audit reports go unread.
- **Date everything.** Include the audit date in the report header. Findings without dates are useless six weeks later.
