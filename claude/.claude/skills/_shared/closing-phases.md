# Mandatory Closing Phase (single source of truth)

Every `/eng-spec` plan ends with ONE closing phase after the last feature phase — **not negotiable, never omitted**. A real `## Phase Status` entry; `/code` invokes the named skill instead of a coder. Numbered continuing from the last feature phase.

## The phase

**Close pass** (risk: high) — `/close-branch`: scripts first, then four report-only reviewers in parallel on the whole branch diff (correctness, structure, test intent, plan and acceptance-criteria reconciliation), ONE `coder` that fixes every finding and writes every owed test, then a report-only gate on the fix diff alone, then the recap sheet. **Root-cause rule:** a cast/`?? default` papering a fixable wide type or loose structure is a finding; fix the source.

Success Criteria: quality checks green; every reviewer finding fixed, shown wrong, or (an ask that changes a ticket AC) put to the user; the fix-diff gate passed; every acceptance criterion mapped to a test or explicitly retired; concentration counts stated; recap and smoke-test checklist delivered.

A scope box diffs two recorded commit ids, never a branch name (`main...HEAD` is empty once the branch merges), and fails on an empty diff: `test -n "$(git diff --name-only <base-sha>..<head-sha>)"`. `plan check` fails a box that diffs a branch name.

When the skill reports no open finding, a coder writes one line of evidence under each open Success Criteria item.

A plan written with the older four closing phases (Refactor pass, Test audit, Verify pass, Recap) runs them as written.

Nothing after this is a phase. `/adr` runs **pre-PR**, shipping in the code's PR.

## Phase Status line (copy verbatim, renumbering)

```markdown
- [ ] Phase N: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)
```
