---
name: refactor
description: Smart refactorer — specialist finds, coders fix, `/review` gates. Four modes, by args: branch audit (default, sweeps the branch diff), targeted ("refactor X"), `audit <dir|module>` (pre-existing DRY violations and pattern drift, report-only), `simplify <dir|module>` (what a module could DELETE if reshaped, via complexity-reviewer). Use for "refactor X", "clean up X", "second pass", end-of-branch cleanup, "DRY audit of <module>", "simplify X / this is too complex".
allowed-tools: [Agent, Bash, Read, Glob, Grep, Skill]
---

# Refactor

Specialist agents find; coders fix; `/review` gates. Two finders:

- `smell-reviewer` — **what repeats or sits wrong** (duplication, placement, naming, dead weight, cohesion). Bound: a diff. Modes 3, 4, 6.
- `complexity-reviewer` — **what need not exist** (branching a data model collapses, indirection with one implementation, configurability nothing configures, guards a boundary kills, values with several owners). Bound: a whole module — never a diff. Mode 7.

## CRITICAL: Never modify a test to make a refactor pass

**Never edit, weaken, or delete a test to pass.** Blocked without a test change → **stop and alert the user**. Verbatim test moves (no assertion changes) are safe.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). `+fast` applies to the finder dispatch too (`model: "haiku"`). Never `+fast` in simplify.

## Script

`python3 ~/.claude/skills/refactor/scripts/refactor_flow.py <verb>`. Each verb prints its report and ends with a `NEXT:` line (what you still do) or a `STOP:` line (say why and stop; a repository with no commits ends in `STOP:` too). Exit 1 = bad input: fix the input and re-run; nothing was written.

## Instructions

1. **Check for modifiers**: `+fast` → `model: "haiku"`. Strip modifiers from subagent prompts.

2. **Determine the mode** — first match wins:
   - `$ARGUMENTS` starts with `simplify`, or names a target plus a complexity complaint ("this is too complex", "reduce the complexity in X", "why is this so convoluted") → **Simplify mode** (step 7). Bare `simplify` with no target: list top-level source dirs and ask — never the whole repo in one dispatch.
   - `$ARGUMENTS` starts with `audit` → **Audit mode** (step 6). Bare `audit` with no target: list top-level source dirs and ask — never the whole repo in one dispatch.
   - `$ARGUMENTS` empty or generic ("cleanup", "final pass", "second pass", "the branch") → **Branch audit mode** (step 3).
   - Otherwise → **Targeted mode** (step 4).

3. **Branch audit (default)**: target = entire branch diff. Do NOT ask focus, do NOT read changed files.

   a. Run `python3 ~/.claude/skills/refactor/scripts/refactor_flow.py branch-prep` and read `~/.claude/skills/_shared/escape-ratchet.md` in the same response. It prints the base it chose (the `branch-base` helper picks it; pass `--base REF` to override), the mechanical-sweep matches, and the finder prompt with the changed-file list (deleted, renamed and binary files marked). `STOP:` on an empty diff, a base with no shared history, or no base found.

   b. **Finder dispatch**: ONE `smell-reviewer` (pinned; omit `model` unless `+fast`) with the prompt the script printed. Every finding must carry `file:line` (and the sibling/prior-art `file:line` for duplication).

   c. **Work list** = finder findings + the sweep matches; present as a statement, not a question. `[design-decision]` → user, never coder list. Nothing found → say so, run step 5's `log` (empty-handed), and stop.

4. **Targeted mode** — when `$ARGUMENTS` names specific code or a specific goal:
   - Read the referenced files; name the goal (structure, readability, perf, maintainability, pattern alignment)
   - **Ask the deletion question before the extraction question**: a different data model, moved decision, or stronger invariant making the complexity unnecessary (boundary checks, unrepresentable illegal states, one canonical owner).
   - **Every change must earn its keep**: state what it deletes or what bug class it kills. Shape-only moves aren't worth the diff — drop them. Redesign (not refactor) → `/eng-spec`.

5. **Dispatch the coder** (branch-audit and targeted modes only — audit mode never dispatches coders):

   Launch a single `coder` for the whole work list — never split it by layer.

   For the coder:
   - Pass the work list (with file paths per finding) or the targeted refactoring description, plus any context you gathered
   - **Pass the CRITICAL test rule verbatim** (never modify/weaken/delete a test; blocked → stop and report; verbatim moves fine)
   - Needs redesign → report back, recommend `/eng-spec`

   **After coders complete**, summarize: what, why, structural changes, concerns.

   **Test audit (conditional)**: dispatch `test-reviewer` (pinned; omit `model`) when the refactor could change test guarantees (moved/split/merged logic, behavior-adjacent paths, touched test files, coder uncertainty). SKIP for purely mechanical refactors with green checks. Weakened/altered tests flagged → CRITICAL-rule violation: stop, alert the user.

   **Log and hand off — one call.** Write the JSON file at the path the prep script's `NEXT:` line named (a fresh path for each invocation), and run `python3 ~/.claude/skills/refactor/scripts/refactor_flow.py log --mode <branch|targeted|simplify> --input <file> [--base REF]`. Use one input file per /refactor invocation; re-run `log` on that file (the script skips rows already written for it). In branch mode pass `--base` with the base `branch-prep` printed in its `NEXT:` line. It writes the escape rows, the finder rows and prints the `/review` handoff block. You supply:
   - `finder` (the dispatched agent; omit in targeted mode), `lane` (required whenever there is a finder; from conversation/planning artifacts), `result` (optional).
   - `findings`: one entry per finder finding, each `{class, disposition, actioned, file, line, desc}` (`line` 0 when none; `desc` one line). Add `escape: true` plus `severity` for each distinct smell in branch-loop code (branch-audit: `duplication` for scope-item-1, `smell` otherwise; simplify: `complexity`). One entry per smell, not per file. Never `escape` mechanical-sweep matches or legacy targets — old debt is not an escape.
   - `guards`: an object, `{"<class>": "<guard>"}`, one guard per escape `class` group, from the ratchet (`escape-ratchet.md`, read in step 3a; read it now in simplify mode). The script refuses an escape class with no guard.
   - `handoff`: `files` (`{path, change}`, one line each), `tests_run` (exact command + exit code, or `none`), `flagged` (one line, `none` when nothing is flagged), optional `plan_impact` (may span lines). Add `modifier` if one was given.

   ```json
   {
     "finder": "smell-reviewer",
     "lane": "code",
     "result": "NEEDS CHANGES",
     "findings": [
       {
         "class": "duplication",
         "disposition": "fix",
         "actioned": "fixed",
         "file": "src/orders.py",
         "line": 3,
         "desc": "the same parse in two handlers",
         "severity": "medium",
         "escape": true
       }
     ],
     "guards": { "duplication": "convention" },
     "handoff": {
       "files": [
         {
           "path": "src/orders.py",
           "change": "one parse helper for both handlers"
         }
       ],
       "tests_run": "pytest tests/test_orders.py -> exit 0",
       "flagged": "none",
       "plan_impact": "none"
     }
   }
   ```

   If it prints no handoff and code changed, add `handoff` to the file and run `python3 ~/.claude/skills/refactor/scripts/refactor_flow.py handoff --input <file>`; that prints the block and writes nothing. If `log` exits 2 (a writer refused a row), still follow its `NEXT:` and tell the user which row failed.

   **Auto-dispatch review**: tell the user you're auto-dispatching `/review`, then Skill-invoke `/review` with the handoff block the script printed + any modifier.

6. **Audit mode — global DRY / pattern sweep of pre-existing code. Report-only: no coders, no `/review`, no code changes.**

   a. Run `python3 ~/.claude/skills/refactor/scripts/refactor_flow.py audit-prep <target-dir>`. It runs jscpd (or prints "no mechanical detection — agent prior-art search only") and prints the finder prompt, with the candidate clone pairs when there are any.

   b. **Judgment dispatch**: ONE `smell-reviewer` (omit `model` unless `+fast`) with the printed prompt.

   c. **Report the work list.** For each surviving finding: the sites, the proposed consolidation, and its route — small single-module extraction → a follow-up **targeted `/refactor`** invocation; `[design-decision]` / cross-module / public-contract → **`/eng-spec`**.

   d. **No escape logging.** Log the finder with `log --mode audit` (JSON as in step 5, with `target`: `["<target-dir>"]`, no `escape`, no `handoff`).

7. **Simplify mode — what could be DELETED if this module were shaped differently.** Fixes are opt-in per finding, never wholesale.

   a. Run `python3 ~/.claude/skills/refactor/scripts/refactor_flow.py simplify-prep <target...>`. It expands the target with `git ls-files`; over 25 files it splits and runs slice 1 — tell the user which slice runs (`--slice N` for the others).

   b. **Do NOT read the files yourself.**

   c. **Finder dispatch**: ONE `complexity-reviewer` (pinned; omit `model`) with the printed prompt. Add any project constraint you already know that makes a shape mandatory (a required layer, a framework seam, a public contract).

   d. **Triage before offering**: drop oracle-failures, under-floor, and irreducible-complexity collapses. `[design-decision]` (contracts, cross-module, migrations, test-assertion changes) → user via AskUserQuestion, never a coder list.

   e. **Present survivors for the user to choose** (sites, quantified disappearance, enabling change, cost). Nothing found → say so, run `log --mode simplify` (empty-handed, with `target`), and stop. The user picks none → log every finder finding anyway (declined survivors `actioned=none`, triage drops `actioned=skipped_fp`) with `target`, and stop. Empty-handed means the finder returned nothing.

   f. **Dispatch chosen findings** via step 5 with two changes: test audit **mandatory**, escape `class=complexity` for branch-loop code only. The `log` call in step 5 carries `--mode simplify` and `target` = the files listed in the printed prompt (the slice that ran).

## Code to refactor

$ARGUMENTS
