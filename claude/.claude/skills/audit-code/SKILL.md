---
name: audit-code
description: Audit code for security, bugs, DRY/maintainability, and accessibility — auto-triages findings and presents only actionable issues
allowed-tools: [Agent, Bash, Read, Write, Glob, Grep]
---

# Code Audit

Audit a codebase for security vulnerabilities, real bugs, DRY/maintainability issues, and accessibility violations. **Read-only** — presents findings for the user to decide what to fix. Writes a findings ledger so re-runs are deterministic and converge.

## Philosophy

Report only issues that a senior staff engineer at a top-tier company would flag in a PR review. The goal is world-class engineering standards, not theoretical perfection. If an issue wouldn't survive triage, don't report it.

## Modifiers

- `+fast` — Use Haiku model for auditor subagents. Quick surface-level scan.
- `+deep` — Thorough mode: still Sonnet (call-site `model: "opus"` is blocked by the agent-model-guard hook), but with smaller batches (1 per 15 files) and a line-by-line instruction added to the auditor prompt.
- `+fresh` — Ignore previous findings ledger and start a clean audit.
- Default (no modifier) — Use Sonnet model for auditor subagents. Always explicitly pass `model: "sonnet"` — never inherit the parent session's model.

## Arguments

`$ARGUMENTS` may contain:

- A **file path**, **directory**, or **glob pattern** to scope the audit (e.g., `src/components/`, `packages/vue/src/composables/*.ts`)
- A **focus keyword** to narrow the audit categories (e.g., `security`, `dry`, `a11y`)
- If empty, audit the entire project source (use project structure from CLAUDE.md to identify source directories)

## Instructions

### Phase 0: Load Previous Findings

Look for an existing findings ledger at `.claude/audit-findings.json` in the project root.

If found (and `+fresh` was NOT passed):

- Read it. It contains an array of previous findings with `file`, `line`, `category`, `severity`, `description`, `status` (open/fixed/wontfix), and `hash` (a fingerprint of file+line+description).
- Pass the full list of **open** findings to each subagent so they can skip already-known issues.
- After the audit, merge new findings into the existing ledger (dedup by hash).

If not found (or `+fresh` was passed):

- Start with an empty findings list.

### Phase 1: Parse & Discover

1. **Parse arguments**: Extract scope and focus from `$ARGUMENTS`. Strip modifiers (`+fast`, `+deep`, `+fresh`).

2. **Determine model**: If `+fast`, pass `model: "haiku"`. Otherwise pass `model: "sonnet"` to all Agent calls — never inherit the parent model, never pass `model: "opus"` (hook-blocked). If `+deep`, keep Sonnet but use 1 batch per 15 files in Phase 2 and append to the auditor prompt: "Audit line by line; trace every code path in production files."

3. **Discover scope**: If no path/pattern was given, identify the project's source directories (check CLAUDE.md, look for `src/`, `packages/`, `app/`, `lib/`, etc.). Exclude `node_modules`, `dist`, `build`, `.git`, vendor dirs, and generated files.

4. **Classify files by tier**:
   - **Production code** (library source, components, utilities, services) — full audit depth
   - **Supporting code** (tests, scripts, playground/demo apps, dev tooling, config) — light scan only

5. **Collect file list**: Use Glob to gather all source files in scope. **Sort the file list alphabetically.** This is critical for determinism. Tag each file with its tier.

### Phase 2: Deterministic File Assignment

Do NOT batch by hand. Save the discovered file list (one path per line) to `/tmp/audit-files.txt` with the Write tool, then run the bundled script:

```bash
bash "${CLAUDE_SKILL_DIR}/batch-files" < /tmp/audit-files.txt                  # default: 1 batch per 25 files, max 4
bash "${CLAUDE_SKILL_DIR}/batch-files" --per-batch 15 < /tmp/audit-files.txt   # +deep
```

It sorts and assigns round-robin (file i → batch i % count), so identical scope always produces identical batches. Output is `# batch N of M (K files)` headers followed by the paths. Do NOT group by "domain" or "directory" — use the script's batches as-is. Tag each file with its tier (from Phase 1) when passing the batch to its auditor.

### Phase 3: Dispatch Auditor Subagents

Launch one subagent per batch via the Agent tool. Each subagent receives:

- Its exact list of files (full paths), with each file tagged as **production** or **supporting**
- The list of **known open findings** (from the ledger) for its files — with instructions to **skip these** and only report NEW issues
- The audit prompt below
- If the user provided a focus keyword, tell subagents to prioritize that category but still note anything critical in other categories.

**Auditor prompt**: instruct each subagent to FIRST Read `~/.claude/skills/audit-code/auditor-prompt.md` and follow it as its audit instructions (categories, tiers, self-filter rule, severity levels, JSON output format). Keep the dispatch prompt itself to the per-batch specifics listed above — file list with tiers, known findings to skip, and the focus keyword. If `+deep`, also append: "Audit line by line; trace every code path in production files."

### Phases 4–5: Merge & Write Ledger (via script)

1. Extract the JSON finding lines from all subagent results and save them (one object per line) to `/tmp/audit-new-findings.jsonl` with the Write tool.
2. Run the bundled merge script:

   ```bash
   bash "${CLAUDE_SKILL_DIR}/ledger-merge" .claude/audit-findings.json /tmp/audit-new-findings.jsonl --scope "<scope>" --files-analyzed <N>
   ```

   It computes the dedup hash (`file:line:first-60-chars-of-description`, lowercased/trimmed), drops findings already in the ledger, appends genuinely new ones with `status: "open"` and today's `foundDate`, marks open findings whose file no longer exists as `stale`, updates `lastAuditDate`/`scope`/`filesAnalyzed`, and prints a summary line (incoming / new-this-run / open / fixed / wontfix / stale). Use those counts in the report. It creates the ledger if missing — do NOT build or edit the ledger JSON by hand.

3. The script cannot detect findings whose cited line content changed significantly — if you noticed any while reading subagent results, mark those `stale` with a targeted Edit.

### Phase 6: Present Report

Present the audit report to the user. Only show MEDIUM and above — no LOW findings.

```
## Code Audit Report

**Scope**: [files/directories audited]
**Files Analyzed**: [count] ([count] production, [count] supporting)
**Previous Known Findings**: [count from ledger, if any]
**New Findings This Run**: [count]
**Total Open Findings**: [count]

### CRITICAL
[file:line — category — description — suggestion]

### HIGH
[file:line — category — description — suggestion]

### MEDIUM
[file:line — category — description — suggestion]

### Top Recommendations
1. [highest-impact improvement]
2. [second highest]
3. [third highest]
```

If there were **zero new findings**, say:

```
## Audit Complete — No New Findings

All [N] previously identified findings are tracked in `.claude/audit-findings.json`.
[X] open, [Y] fixed, [Z] wontfix, [W] stale.

The codebase is clean relative to the audit criteria. No further audit runs needed.
```

### Phase 7: Next Steps

Ask the user which findings they'd like to address. Suggest appropriate next commands:

- `/refactor` for DRY/pattern/smell issues
- `/fix` if they want to batch-fix specific items
- Manual fixes for security issues that need design decisions
- Re-run `/audit-code` after fixes to verify — the ledger will skip known issues and only surface anything truly new.

## Arguments

$ARGUMENTS
