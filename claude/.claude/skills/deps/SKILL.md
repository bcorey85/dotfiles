---
name: deps
description: Upgrade a dependency safely — mandatory breaking-change research first, then plan, apply via coder dispatch, and verify. Use for "upgrade X", "bump X to v9", "update dependencies", or any library version migration.
---

# Deps

Version migrations are the highest-risk config-adjacent change: failures surface at build/run time, sometimes only in CI. The global WebSearch-before-config rule applies in full here — this skill is its workflow.

## Process

### 1. Establish versions (one lookup, trust it)

Current version from the lockfile/manifest. Target from the request, or the registry (`npm view <pkg> version` or ecosystem equivalent) if "latest".

### 2. MANDATORY research — before touching anything

For every major-version step between current and target:

1. Official changelog / release notes / migration guide.
2. GitHub issues for known breakage with the project's stack.

Then grep the codebase for each documented breaking API to determine which actually apply here. A breaking change that touches zero files is a footnote, not a blocker.

### 3. Plan

Present: version path, breaking changes that apply (with the files they touch), code changes needed, and rollback (revert manifest + lockfile). If any breaking change applies → wait for the user's go-ahead. Patch/minor with nothing applicable → proceed.

### 4. Apply

Bump the manifest and install (manifest and lockfile change together; never hand-edit the lockfile). Required code changes go through a coder dispatch per the delegation rule — pass the migration notes as context and instruct: only changes the migration requires, no opportunistic refactoring.

### 5. Verify

Run the project's quality checks (global 2-run cap applies). A clean install plus green checks is the done signal — do not add ad-hoc spot checks on top.

### 6. Report

Old → new, code changed (files), anything intentionally deferred, residual risks (e.g. deprecations slated for removal in the next major).

## Rules

- One upgrade per task — never batch unrelated bumps into one diff.
- System-level deps (CLI tools, runtimes) follow the platform rule: apt / brew / pacman only, added to `install/deps` for all platforms in dotfiles-managed environments.
- If research surfaces an unresolved blocker (open regression, missing peer support), report it and stop — don't upgrade into a known hole.

## Arguments

$ARGUMENTS
