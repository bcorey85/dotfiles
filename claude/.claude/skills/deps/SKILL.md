---
name: deps
description: Upgrade a dependency safely — mandatory breaking-change research first, then plan, apply via coder dispatch, and verify. Use for "upgrade X", "bump X to v9", "update dependencies", or any library version migration.
---

# Deps

The global WebSearch-before-config rule applies in full here — this skill is its workflow.

## Process

### 1. Establish versions (one lookup, trust it)

Current from lockfile/manifest; target from request or registry. One lookup, trust it.

### 2. MANDATORY research — before touching anything

For every major-version step between current and target:

1. Official changelog / release notes / migration guide.
2. GitHub issues for known breakage with the project's stack.

Then grep the codebase per breaking API — zero-file hits are footnotes, not blockers.

### 3. Plan

Present version path, applicable breaks (plus files), code changes, rollback (manifest plus lockfile revert). Applicable break means wait for go-ahead; clean patch or minor means proceed.

### 4. Apply

Bump manifest plus install together (never hand-edit lockfile). Code changes via coder dispatch with migration notes: migration-required only, no opportunistic refactoring.

### 5. Verify

Quality checks (2-run cap). Clean install plus green means done; no ad-hoc spot checks.

### 6. Report

Old → new, code changed (files), anything intentionally deferred, residual risks (e.g. deprecations slated for removal in the next major).

## Rules

- One upgrade per task — never batch unrelated bumps into one diff.
- System-level deps: apt, brew, or pacman only, added to install/deps for all platforms.
- If research surfaces an unresolved blocker (open regression, missing peer support), report it and stop — don't upgrade into a known hole.

## Arguments

$ARGUMENTS
