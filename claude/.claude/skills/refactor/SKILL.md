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

A refactor changes structure, not behavior — so the tests are the contract. **Never edit, weaken, or delete a test to get a refactor to pass.** If you reach an issue that seems unsolvable without changing a test, **stop and alert the user** — do not work around it. Moving a test verbatim to a new file (no assertion changes) is safe.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). They apply to the finder dispatch too: `+deep` → `smell-reviewer-deep` / `complexity-reviewer-deep` (omit `model`); `+fast` → `model: "haiku"`. `+fast` for simple renames or mechanical refactors; `+deep` for refactors involving multiple interacting systems, semantic duplication that shares no tokens, or (simplify mode) a deletion spanning more than one file. Never `+fast` in simplify mode — the deletion oracle needs the whole module held at once; say so and run at the default.

## Instructions

1. **Check for modifiers**: If `+deep` is present, swap each agent for its `-deep` variant and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from prompts passed to subagents.

2. **Determine the mode** — first match wins:
   - `$ARGUMENTS` starts with `simplify`, or names a target plus a complexity complaint ("this is too complex", "reduce the complexity in X", "why is this so convoluted") → **Simplify mode** (step 7). Bare `simplify` with no target: list the repo's top-level source directories and ask which to sweep — never the whole repo in one dispatch.
   - `$ARGUMENTS` starts with `audit` → **Audit mode** (step 6). Bare `audit` with no target: list the repo's top-level source directories and ask which to audit — never sweep the whole repo in one dispatch.
   - `$ARGUMENTS` empty or generic ("cleanup", "final pass", "second pass", "the branch") → **Branch audit mode** (step 3).
   - Otherwise → **Targeted mode** (step 4).

3. **Branch audit mode (the default)** — the target is the entire branch diff. Do NOT ask what to focus on, and do NOT read the changed files yourself — the finder reads; this context stays lean.

   a. **Scope**: `git diff --name-only main...HEAD` (fall back to `master` if no `main`). Empty diff → say so and stop.

   b. **Mechanical sweep (deterministic, zero agent cost)** — comment rot and scaffolding are regexable; catch them without a dispatch:

   ```bash
   git diff main...HEAD -U0 | rg '^\+' | rg -n 'TODO|FIXME|XXX|HACK|console\.(log|debug)|debugger\b|binding\.pry|print\('
   git diff main...HEAD -U0 | rg -n '^\+\s*(//|#)\s*(if |for |while |return |const |let |var |def |function |import )'
   ```

   First = leftover debug/TODO litter; second = commented-out code. Matches go straight onto the work list (adapt patterns to the repo's language). Most were already caught per-phase by `[comment-noise]` — expect this to be small or empty.

   c. **Finder dispatch**: ONE `smell-reviewer` (pinned; omit `model`; variants per step 1) with:
   - the changed-file list from (a) — never let it rediscover scope
   - the bound: "Your review bound for this run is the whole branch diff (`git diff main...HEAD`), not a phase diff."
   - the priority: "Prioritize cross-phase smells — duplication grown in two places by separate tasks, naming that drifted as the branch evolved, dead code orphaned by iteration, and changed code that diverges in idiom from its unchanged sibling files. Within-phase smells were already gated per phase; findings here should be things no single-phase view could see."
   - Every finding must carry `file:line` (and the sibling/prior-art `file:line` for duplication).

   d. **Compile the work list** = finder findings + mechanical matches. Present it as a statement of what you're fixing, not a question. `[design-decision]`-tagged findings go to the user, never onto the coder list. Genuinely nothing found → say so and stop.

4. **Targeted mode** — when `$ARGUMENTS` names specific code or a specific goal:
   - Read the referenced files to understand the current code
   - Identify the refactoring goal: structure, readability, performance, maintainability, pattern alignment
   - **Ask the deletion question before the extraction question.** Extracting a block into a helper RELOCATES complexity — the branching still exists, now behind a name. First ask whether a different data model, a different placement of the decision, or a stronger invariant makes the complexity unnecessary: push a check to a boundary so downstream code cannot be wrong, make an illegal state unrepresentable so its guard is dead, give a value one canonical owner so the code reconciling three copies gets deleted.
   - **Every proposed change must earn its keep**: state what it deletes or what class of bug it makes impossible. A change that only moves code to a new shape is not a refactor worth the diff — say so and drop it. If the answer is a redesign rather than a refactor, stop and recommend `/eng-spec` (step 5 covers the same exit from the coder side).

5. **Dispatch the appropriate coder(s)** (branch-audit and targeted modes only — audit mode never dispatches coders):

   Determine if the work is **frontend** (components, pages, stores, styles), **backend** (models, controllers/views, services, middleware, migrations), or **both**.

   **Frontend only** → `frontend-coder` · **Backend only** → `backend-coder` · **Both** → both in parallel, single message · **Neither** (non-web repo) → `coder`

   For each coder:
   - Pass the work list (with file paths per finding) or the targeted refactoring description, plus any context you gathered
   - **Pass the CRITICAL test rule above verbatim**: never modify/weaken/delete a test to make the refactor pass; if blocked, stop and report back rather than touching a test (moving a test verbatim to a new file is fine)
   - If the refactor turns out to need architectural redesign, have it report back and recommend `/eng-spec` instead

   **After coder(s) complete**, summarize: what was refactored and why, what changed structurally, any concerns or follow-ups.

   **Log escapes** (branch-audit mode): if the target is code produced by this branch's coding loop (`/code` + `/review` already blessed it), every finder finding fixed is by definition a cross-phase miss by the quality layer — derive the log lines from the finder's findings list, one per distinct smell (not per file), `class` straight off the finding (`duplication` for scope-item-1 findings, `smell` otherwise):

   ```bash
   bash ~/.claude/scripts/log-escape repo="$(basename "$(git rev-parse --show-toplevel)")" stage_found=refactor gate_missed=review class=<smell|duplication> severity=medium lane=<eng-spec|code|other> desc="<one line>" file=<representative path>
   ```

   `lane` is the planning lane that produced the branch's work — infer from the conversation or planning artifacts. Skip logging for mechanical-sweep matches (regex hits, not reviewer misses) and when the target is legacy code that never went through the loop — old debt is not an escape.

   **Test audit (conditional)**: dispatch a `test-reviewer` subagent (`model: "sonnet"`) when the refactor could have changed what the tests guarantee — logic moved/split/merged across units, a behavior-adjacent path changed, any test file touched, or a coder flagged uncertainty. SKIP it (and say so) for purely mechanical refactors with green quality checks. When it runs: pass the refactor scope and the changed-file list; surface its findings in the summary. If it flags weakened assertions or tests altered to accommodate the refactor, treat that as a violation of the CRITICAL rule — stop and alert the user.

   **Auto-dispatch peer review**: tell the user "Auto-dispatching `/review` to check the refactored code before committing." Build a handoff block from the coder output (schema: `~/.claude/skills/_shared/handoff-block.md` — `files` with per-file change lines, `tests-run`, `flagged`, `plan_impact`, `iter: 1`) and invoke the `/review` skill via the Skill tool with it as args, prepending any `+fast`/`+deep` modifier. Runs AFTER all coders complete and the summary is presented.

6. **Audit mode — global DRY / pattern sweep of pre-existing code. Report-only: no coders, no `/review`, no code changes.**

   This is the one lane that deliberately looks at UNCHANGED code. Natural trigger: `/audit review` showing recurring `class=duplication` escapes in a module.

   a. **Mechanical clone detection first** (detector finds, agent judges — neither does the other's job). If node is available, verify syntax then run jscpd via npx (no global install — keeps the cross-platform rule):

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

   a. **Resolve the bound**: the named module, feature directory, or file set. Expand it to a concrete file list (`git ls-files <target>`) and pass that list — the finder must not rediscover scope. A bound bigger than roughly 25 source files: split it and say which slice you're running.

   b. **Do NOT read the files yourself.** The finder holds the module; this context holds the decision. Reading it here defeats the fresh-eyes split and burns the context you need for the walkthrough.

   c. **Finder dispatch**: ONE `complexity-reviewer` (pinned; omit `model`; `-deep` variant per step 1) with:
   - the file list from (a) and the bound: "Simplify mode: your bound is the whole existing code of `<target>`. Pre-existing shape IS the target."
   - the ask, verbatim from its scope: branching a data model collapses, indirection with one implementation, configurability nothing configures, guards a stronger invariant kills, values with more than one owner.
   - the reminder that its deletion oracle and magnitude floor are hard gates: every finding names what disappears (quantified), the enabling change, why the removed code becomes unreachable, and what the change makes harder.
   - any project constraint you already know that makes a shape mandatory (a required layer, a framework seam, a public contract).

   d. **Triage the findings yourself before offering any of them.** Drop findings that fail the oracle, sit under the magnitude floor, or propose collapsing irreducible domain complexity into something unreadable. `[design-decision]` findings — public contracts, cross-module moves, migrations, anything needing a test assertion changed — go to the user via AskUserQuestion and never onto a coder list.

   e. **Present the surviving list and let the user choose which to take.** Each entry: the sites, what disappears (quantified), the enabling change, and the cost clause. This is the one mode that asks rather than states — a simplification is a behavior-adjacent restructure, and which risk is worth taking is the user's call. Nothing found → say the module is already as simple as its problem and stop.

   f. **Dispatch the chosen findings** through step 5 with two changes: the test audit is **mandatory, not conditional** (every finding here is behavior-adjacent by construction), and escape logging uses `class=complexity` — and only for code this branch's `/code` loop produced. Pre-existing debt is not an escape.

## Code to refactor

$ARGUMENTS
