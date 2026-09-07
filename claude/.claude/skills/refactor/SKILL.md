---
name: refactor
description: Smart refactorer — specialist finds, coders fix, `/review` gates. Four modes. Branch audit (default, no/generic args) sweeps the branch diff via a smell-reviewer finder dispatch. Targeted ("refactor X") refactors named code. Audit (`audit <dir|module>`) sweeps PRE-EXISTING code for global DRY violations and pattern drift — mechanical clone detection + smell-reviewer judgment, report-only work list, no coders. Simplify (`simplify <dir|module>`) asks what could be DELETED if a module were shaped differently — branch thickets, one-implementation indirection, unused configurability, guards a boundary kills — via complexity-reviewer. Use for "refactor X", "clean up X", "second pass", end-of-branch cleanup, "DRY audit / debt audit of <module>", or "simplify X / this is too complex / reduce the complexity in X".
allowed-tools: [Agent, Bash, Read, Glob, Grep, Skill]
---

# Refactor

Specialist agents find (fresh eyes, out of this context); coders fix; `/review` gates. This skill never compiles its own checklist — the finder agent's scope items ARE the checklist. Two finders, two different questions:

- `smell-reviewer` — **what repeats or sits wrong** (duplication, placement, naming, dead weight, cohesion). Bound: a diff. Modes 3, 4, 6.
- `complexity-reviewer` — **what need not exist** (branching a data model collapses, indirection with one implementation, configurability nothing configures, guards a boundary kills, values with several owners). Bound: a whole module — never a diff. Mode 7.

## CRITICAL: Never modify a test to make a refactor pass

A refactor changes structure, not behavior — tests are the contract. **Never edit, weaken, or delete a test to pass.** Blocked without a test change → **stop and alert the user**. Verbatim test moves (no assertion changes) are safe.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). They apply to the finder dispatch too: `+deep` → `smell-reviewer-deep` / `complexity-reviewer-deep` (omit `model`); `+fast` → `model: "haiku"`. `+fast` for simple renames/mechanical refactors; `+deep` for multi-system refactors, tokenless semantic duplication, or multi-file simplify deletions. Never `+fast` in simplify — the oracle needs the whole module at once.

## Instructions

1. **Check for modifiers**: `+deep` → swap each agent for its `-deep` variant, omit `model`. `+fast` → `model: "haiku"`. Strip modifiers from subagent prompts.

2. **Determine the mode** — first match wins:
   - `$ARGUMENTS` starts with `simplify`, or names a target plus a complexity complaint ("this is too complex", "reduce the complexity in X", "why is this so convoluted") → **Simplify mode** (step 7). Bare `simplify` with no target: list top-level source dirs and ask — never the whole repo in one dispatch.
   - `$ARGUMENTS` starts with `audit` → **Audit mode** (step 6). Bare `audit` with no target: list top-level source dirs and ask — never the whole repo in one dispatch.
   - `$ARGUMENTS` empty or generic ("cleanup", "final pass", "second pass", "the branch") → **Branch audit mode** (step 3).
   - Otherwise → **Targeted mode** (step 4).

3. **Branch audit (default)**: target = entire branch diff. Do NOT ask focus, do NOT read changed files — the finder reads; this context stays lean.

   a. **Scope**: `git diff --name-only main...HEAD` (fall back to `master` if no `main`). Empty diff → say so and stop.

   b. **Mechanical sweep (deterministic, zero agent cost)**:

   ```bash
   git diff main...HEAD -U0 | rg '^\+' | rg -n 'TODO|FIXME|XXX|HACK|console\.(log|debug)|debugger\b|binding\.pry|print\('
   git diff main...HEAD -U0 | rg -n '^\+\s*(//|#)\s*(if |for |while |return |const |let |var |def |function |import )'
   ```

   First = leftover debug/TODO litter; second = commented-out code. Matches go straight onto the work list (adapt patterns to the repo's language).

   c. **Finder dispatch**: ONE `smell-reviewer` (pinned; omit `model`; variants per step 1) with:
   - the changed-file list from (a) — never let it rediscover scope
   - the bound: "Your review bound for this run is the whole branch diff (`git diff main...HEAD`), not a phase diff."
   - the priority: "Prioritize cross-phase smells — things no single-phase view could see (multi-task duplication, drifted naming, orphaned dead code, idiom divergence from unchanged siblings)."
   - Every finding must carry `file:line` (and the sibling/prior-art `file:line` for duplication).

   d. **Work list** = finder findings + mechanical matches; present as a statement, not a question. `[design-decision]` → user, never coder list. Nothing found → say so and stop.

4. **Targeted mode** — when `$ARGUMENTS` names specific code or a specific goal:
   - Read the referenced files; name the goal (structure, readability, perf, maintainability, pattern alignment)
   - **Ask the deletion question before the extraction question**: a different data model, moved decision, or stronger invariant making the complexity unnecessary (boundary checks, unrepresentable illegal states, one canonical owner).
   - **Every change must earn its keep**: state what it deletes or what bug class it kills. Shape-only moves aren't worth the diff — drop them. Redesign (not refactor) → `/eng-spec`.

5. **Dispatch the coder** (branch-audit and targeted modes only — audit mode never dispatches coders):

   Launch a single `coder` for the whole work list, whatever layers it spans — never split it by layer.

   For the coder:
   - Pass the work list (with file paths per finding) or the targeted refactoring description, plus any context you gathered
   - **Pass the CRITICAL test rule verbatim** (never modify/weaken/delete a test; blocked → stop and report; verbatim moves fine)
   - Needs redesign → report back, recommend `/eng-spec`

   **After coders complete**, summarize: what, why, structural changes, concerns.

   **Log escapes** (branch-audit mode, branch-loop code only): one line per distinct smell (not per file), `class` off the finding (`duplication` for scope-item-1, `smell` otherwise):

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=refactor gate_missed=review class=<smell|duplication> severity=medium lane=<eng-spec|code|other> guard=<...> desc="<one line>" file=<representative path>
   ```

   `guard` comes from the ratchet — run it per `~/.claude/skills/_shared/escape-ratchet.md`, using its batching rule (one guard per `class` group, not per row).

   `lane` from conversation/planning artifacts. Skip mechanical-sweep matches and legacy targets — old debt is not an escape.

   **Log the finder** (every mode, even empty-handed) per `~/.claude/skills/_shared/finding-log.md` (read it): `gate=` the dispatched finder, `scope=branch-exit` (branch-audit) or `standalone`. Fires on pre-existing code too. Non-blocking.

   **Test audit (conditional)**: dispatch `test-reviewer` (`model: "sonnet"`) when the refactor could change test guarantees (moved/split/merged logic, behavior-adjacent paths, touched test files, coder uncertainty). SKIP for purely mechanical refactors with green checks. Weakened/altered tests flagged → CRITICAL-rule violation: stop, alert the user.

   **Auto-dispatch review**: tell the user you're auto-dispatching `/review`. Build a handoff block (`~/.claude/skills/_shared/handoff-block.md`: `files`, `tests-run`, `flagged`, `plan_impact`, `iter: 1`) and Skill-invoke `/review` with it + any modifier.

6. **Audit mode — global DRY / pattern sweep of pre-existing code. Report-only: no coders, no `/review`, no code changes.**

   This is the one lane that deliberately looks at UNCHANGED code. Natural trigger: `/audit review` showing recurring `class=duplication` escapes in a module.

   a. **Mechanical clone detection first** (detector finds, agent judges — neither does the other's job). If node is available, verify syntax then run jscpd via npx:

   ```bash
   npx --yes jscpd --help >/dev/null 2>&1 && npx --yes jscpd <target-dir> --min-tokens 70 --reporters consoleFull > /tmp/jscpd.log; # then read the log
   ```

   No node / detector fails → skip it, note "no mechanical detection — agent prior-art search only" in the report, and rely on (b).

   b. **Judgment dispatch**: ONE `smell-reviewer` (variants per step 1) with:
   - the bound: "Audit mode: your bound is the existing code of `<target>` — pre-existing smells ARE the target this run, per your audit-bound clause."
   - the candidate clone pairs from (a), if any: "Judge each candidate against the anti-churn line — must-stay-in-sync (flag, name the extraction) vs looks-a-bit-similar (suppress)."
   - the ask: duplication across files, pattern/idiom drift between sibling modules, wrong-altitude code — each finding with both `file:line` sites and the consolidation it proposes. Cross-module consolidations or anything moving a public contract → `[design-decision]`.

   c. **Report the work list — the product is the list, not fixes.** For each surviving finding: the sites, the proposed consolidation, and its route — small single-module extraction → a follow-up **targeted `/refactor`** invocation; `[design-decision]` / cross-module / public-contract → **`/eng-spec`**.

   d. **No escape logging** — old debt is not an escape (same rule as `/escape`).

7. **Simplify mode — what could be DELETED if this module were shaped differently.** The one lane whose question is subtraction rather than consolidation. Fixes are opt-in per finding, never wholesale.

   a. **Resolve the bound**: the named module, directory, or file set. Expand to a concrete file list (`git ls-files <target>`) — no scope rediscovery. Over ~25 source files: split, say which slice runs.

   b. **Do NOT read the files yourself.** The finder holds the module; this context holds the decision.

   c. **Finder dispatch**: ONE `complexity-reviewer` (pinned; omit `model`; `-deep` variant per step 1) with:
   - the file list from (a) and the bound: "Simplify mode: your bound is the whole existing code of `<target>`. Pre-existing shape IS the target."
   - the ask, verbatim from its scope: branching a data model collapses, indirection with one implementation, configurability nothing configures, guards a stronger invariant kills, values with more than one owner.
   - its oracle + magnitude floor are hard gates (quantified disappearance, enabling change, unreachability proof, cost clause).
   - any project constraint you already know that makes a shape mandatory (a required layer, a framework seam, a public contract).

   d. **Triage before offering**: drop oracle-failures, under-floor, and irreducible-complexity collapses. `[design-decision]` (contracts, cross-module, migrations, test-assertion changes) → user via AskUserQuestion, never a coder list.

   e. **Present survivors for the user to choose** (sites, quantified disappearance, enabling change, cost). Nothing found → say so and stop.

   f. **Dispatch chosen findings** via step 5 with two changes: test audit **mandatory** (every finding is behavior-adjacent), escape `class=complexity` for branch-loop code only.

## Code to refactor

$ARGUMENTS
