---
name: refactor
description: Smart refactorer — smell-reviewer finds, coders fix, `/review` gates. Three modes. Branch audit (default, no/generic args) sweeps the branch diff via a smell-reviewer finder dispatch. Targeted ("refactor X") refactors named code. Audit (`audit <dir|module>`) sweeps PRE-EXISTING code for global DRY violations and pattern drift — mechanical clone detection + smell-reviewer judgment, report-only work list, no coders. Use for "refactor X", "clean up X", "second pass", end-of-branch cleanup, or "DRY audit / debt audit of <module>".
allowed-tools: [Agent, Bash, Read, Glob, Grep, Skill]
---

# Refactor

One source of smell truth: the `smell-reviewer` agent finds (fresh eyes, out of this context); coders fix; `/review` gates. This skill never compiles its own smell checklist — the agent's five scope items ARE the checklist.

## CRITICAL: Never modify a test to make a refactor pass

A refactor changes structure, not behavior — so the tests are the contract. **Never edit, weaken, or delete a test to get a refactor to pass.** Tests pin current behavior; modifying them mid-refactor masks the exact regressions a refactor is most likely to introduce. If you reach an issue that seems unsolvable without changing a test, **stop and alert the user** — do not work around it. Moving a test verbatim to a new file (no assertion changes) is safe.

## Modifiers

- `+fast` / `+deep` — semantics defined in `~/.claude/skills/_shared/modifiers.md` (read it when either is present). They apply to the finder dispatch too: `+deep` → `smell-reviewer-deep` (omit `model`); `+fast` → `model: "haiku"`. `+fast` for simple renames or mechanical refactors; `+deep` for refactors involving multiple interacting systems or semantic duplication that shares no tokens.

## Instructions

1. **Check for modifiers**: If `+deep` is present, swap each agent for its `-deep` variant and omit `model`. If `+fast` is present, pass `model: "haiku"`. Strip modifiers from prompts passed to subagents.

2. **Determine the mode** — first match wins:
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

5. **Dispatch the appropriate coder(s)** (branch-audit and targeted modes only — audit mode never dispatches coders):

   Determine if the work is **frontend** (components, pages, stores, styles), **backend** (models, controllers/views, services, middleware, migrations), or **both**.

   **Frontend only** → `frontend-coder` · **Backend only** → `backend-coder` · **Both** → both in parallel, single message · **Neither** (non-web repo) → `coder`

   For each coder:
   - Pass the work list (with file paths per finding) or the targeted refactoring description, plus any context you gathered
   - Instruct it to: read and understand the existing code, implement the refactoring step by step, and ensure no functionality is broken
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

   This is the one lane that deliberately looks at UNCHANGED code — the gates are diff-bounded on purpose, so repo debt (three old copies of a guard, two modules mapping the same shape differently) is invisible to them. Natural trigger: `/audit review` showing recurring `class=duplication` escapes in a module.

   a. **Mechanical clone detection first** (detector finds, agent judges — neither does the other's job). If node is available, verify syntax then run jscpd via npx (no global install — keeps the cross-platform rule):

   ```bash
   npx --yes jscpd --help >/dev/null 2>&1 && npx --yes jscpd <target-dir> --min-tokens 70 --reporters consoleFull > /tmp/jscpd.log; # then read the log
   ```

   No node / detector fails → skip it, note "no mechanical detection — agent prior-art search only" in the report, and rely on (b).

   b. **Judgment dispatch**: ONE `smell-reviewer` (variants per step 1) with:
   - the bound: "Audit mode: your bound is the existing code of `<target>` — pre-existing smells ARE the target this run, per your audit-bound clause."
   - the candidate clone pairs from (a), if any: "Judge each candidate against the anti-churn line — must-stay-in-sync (flag, name the extraction) vs looks-a-bit-similar (suppress)."
   - the ask: duplication across files, pattern/idiom drift between sibling modules, wrong-altitude code — each finding with both `file:line` sites and the consolidation it proposes. Cross-module consolidations or anything moving a public contract → `[design-decision]`.

   c. **Report the work list — the product is the list, not fixes.** For each surviving finding: the sites, the proposed consolidation, and its route — small single-module extraction → a follow-up **targeted `/refactor`** invocation; `[design-decision]` / cross-module / public-contract → **`/eng-spec`**. Consolidating old shared code is design-shaped and may sit on untested paths; a sweep that rewrites it unsupervised is the risk, not the debt.

   d. **No escape logging** — old debt is not an escape (same rule as `/escape`).

## Code to refactor

$ARGUMENTS
