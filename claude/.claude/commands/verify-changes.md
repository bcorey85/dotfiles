---
description: Verify implementation against eng-plan and Jira ticket AC before PR. Final quality gate.
allowed-tools: [Bash, Read, Glob, Grep, Task, AskUserQuestion, mcp__jira__getJiraIssue]
---

# Verify Changes

Verify that the current implementation satisfies the eng-plan verification checklist and Jira ticket acceptance criteria. Run this before `/pr` to catch missed requirements.

## Instructions

### Step 1: Gather Sources of Truth

1. **Get the current branch name** to extract the Jira ticket number:
   ```bash
   git branch --show-current
   ```

2. **Find the eng-plan** — Glob `eng-plan/*.md` for a file matching the ticket number or branch description. Read it if found. Extract the `## Verification` checklist.

3. **Find the product spec** — Glob `product-specs/*.md` for files referencing the ticket. Read the relevant AC section if found.

4. **Pull Jira ticket AC** — If a Jira ticket number was extracted in step 1, fetch the ticket using `getJiraIssue` (use the Jira Cloud ID from CLAUDE.md) and extract the acceptance criteria from the description.

5. **Get the diff** — Run `git diff main...HEAD --stat` and `git diff main...HEAD` to understand what was actually changed on this branch.

6. **Run the full test suite** — This is the single most important verification step. Run ALL relevant test suites based on which packages have changes. Refer to CLAUDE.md for the project's test commands.

   Record the results. If any tests FAIL, this is an automatic blocker — do not proceed to individual checklist verification until the test suite is green. Report failures immediately.

   If the test suite passes, note the number of passing tests and suites as a baseline.

### Step 2: Build the Checklist

Compile a unified checklist from all sources:
- Eng-plan `## Verification` items (primary)
- Jira ticket AC items (if referenced in the eng-plan)
- Product spec AC items (if a different level of detail than the eng-plan)

Deduplicate items that appear in multiple sources.

**Add diff-derived items**: Compare the `git diff main...HEAD --stat` output against the compiled checklist. For each file in the diff that is NOT mentioned in any checklist item, add a new verification item: "Verify [filename] changes are correct and consistent with the ticket scope." This catches scope creep, bonus changes, and files the eng-plan forgot to mention.

### Step 3: Verify Each Item

For each checklist item, do one of (in order of preference):
- **Run a targeted test** — PREFERRED verification method. Check for passing tests that exercise this behavior. If a relevant test exists and passes, that is a strong PASS signal.
- **Check the build** — if the item relates to compilation or type safety.
- **Read the relevant file(s)** — WEAKEST verification method. Only use file reading when no test exists and the item cannot be tested. When using file reading, you MUST also perform adversarial analysis (see Step 3a).

### Step 3a: Adversarial Analysis (REQUIRED for file-read verifications)

When verifying an item by reading code (not by test), do NOT just confirm the code exists. For each item verified by reading:

1. **Check for completeness** — are ALL instances covered? (e.g., if "all N calls include X", count them explicitly and list each one)
2. **Check for correctness** — does the implementation actually satisfy the requirement, or does it just look like it does?
3. **Check for omissions** — what SHOULD be there but ISN'T? (e.g., missing error handling, missing edge case, missing test for new code)
4. **Check for regressions** — could this change break something that was working before? Check callers and consumers of modified code.

If you cannot find anything wrong after adversarial analysis, mark as PASS. But if you skipped adversarial analysis and just confirmed the code exists, mark as WEAK PASS and note "verified by file reading only — no test coverage."

Mark each item as:
- PASS — implemented correctly, verified by test or thorough adversarial analysis
- WEAK PASS — code appears correct on reading but has no test coverage (flag for follow-up)
- FAIL — missing or incorrect (explain what's wrong)
- PARTIAL — partially done (explain what's missing)
- SKIP — not verifiable without manual testing (explain why)

### Step 3b: Coverage Gap Check (REQUIRED)

After checking all items from the eng-plan/Jira AC, independently assess:

1. **Are there new code paths without tests?** — If the diff introduces new functions, branches, or handlers that have zero test coverage, flag them as WEAK PASS even if the eng-plan verification item passed by file reading.
2. **Are there modified files without corresponding test updates?** — Check whether every modified source file has a corresponding test file that was also updated (or already covers the changes).
3. **Did the eng-plan verification checklist miss anything?** — Compare the actual diff against the checklist. If the diff touches code not mentioned in any checklist item, flag it as an uncovered change.

### Step 4: Present Results

Format as a checklist:

```
## Verification Results

### Test Suite
[X] suites, [Y] tests — all passing / N failures

### From: eng-plan/TAS-X-description.md
- [x] PASS: Item description
- [~] WEAK PASS: Item description — verified by file reading only
- [ ] FAIL: Item description — what's wrong
- [~] PARTIAL: Item description — what's missing
- [-] SKIP: Item description — requires manual testing

### Coverage Gaps
- [list any uncovered changes or missing tests]

### Summary
X/Y items passed (Z verified by tests, W verified by file reading only), N issues found
```

### Step 5: Recommend Next Steps

Based on results:
- **All PASS (with tests)** → "All checks pass with test coverage. Ready for `/pr`."
- **All PASS but some WEAK PASS** → "All items appear implemented correctly, but N items lack test coverage. Consider running `/test` to add tests before `/pr`, or proceed if you accept the risk." List the weak-pass items.
- **Failures found** → List what needs fixing. Suggest `/fix` or `/code` to address them.
- **Partials found** → Ask user if the partial items are acceptable or need completion first.

**Never say "all checks pass" if any item was verified by file reading alone.** Be honest about the confidence level of each check.

## Arguments

$ARGUMENTS
