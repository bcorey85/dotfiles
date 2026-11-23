# toolkit-prose-1122: seven toolkit-writing audit items

> Ticket: ./00-ticket.md (seven ~/agent-evals queue items; orchestrating session agent-evals-c3)
> Research: ./02-research.md (goal-blind, produced before design began)
> Decisions: ./03-decisions.md (the design-resolution ledger)
> Date: 2026-11-22

<!-- Source precedence: on anything concrete, THIS file wins over the ledger (which records why, not what). A disagreement between them is a spec bug — report it. -->

## Summary

Prose edits to agents, skills and `_shared` files under `claude/.claude/` from the 2026-11-22 toolkit-writing audit: fix contradictory lines, split dense paragraphs into one-branch lists, trim the architect and general-purpose descriptions and bodies, fold three single-loader `_shared` files into their loaders, give the PLAN-IMPACT `acceptance_criteria:` rule one owner, and add one code-reviewer rule that flags a hard-coded toolkit-name list. Every cut or reworded rule gets rule-meter on and off arms (or an `unmeasured` entry); every anchored file gets refreshed rows; every edit gets a change note; the opencode ports are patched where an item names them.

## Phase Status

<!-- Hoisted from below so the first screen answers "where are the agents?". The one section that changes after writing (/code ticks it) — source of truth for "which phase is next". Do not move it back down. -->

- [x] Phase 0: Contracts — frozen at plan approval (risk: high)
- [ ] Phase 1: Walking skeleton — plan-format tightening and the design-decision-format fold (risk: high)
- [ ] Phase 2: Item 1 — contradictory lines and dispatcher descriptions (risk: low)
- [ ] Phase 3: Item 3 — architect descriptions and the Reuse Map owner (risk: low)
- [ ] Phase 4: Item 4 — general-purpose body (risk: low)
- [ ] Phase 5: Item 5 — finding-log and skimmable folds, pointer triggers, consumer lists, cull-rule owner (risk: high)
- [ ] Phase 6: Item 2 remainder — review-fork-run, coder-core verify list, calibration dedupe, eng-spec agents (risk: high)
- [ ] Phase 7: Item 6 — PLAN-IMPACT rule owner and the code-reviewer calibration pointer (risk: high)
- [ ] Phase 8: Item 7 — derivable-list rule, plant, detector and scenario (risk: low)
- [ ] Phase 9: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)

## Decisions

1. D1 Owner of the PLAN-IMPACT `acceptance_criteria:` rule — coder-core:97 owns the coder side, reviewer-calibration Disposition owns the reviewer side; code-reviewer:85 becomes a placeholder, coder-core:43 a same-file pointer; plan-format:85 untouched.
2. D2 Single-loader folds — design-decision-format into 5-decisions step 13, finding-log into test-audit `## Logging`, skimmable-writing into adr-template; code-vocabulary stays (consumer list fixed); plan-reading deferred by ruling.
3. D3 code-reviewer calibration pointer — one preamble line naming the Disposition and Verify the Premise sections in plain words, then cut the lines it covers.
4. D4 general-purpose body — four lines; GP01/GP02 meter scenarios attempted before any `unmeasured` entry.
5. D5 Item-7 rule — a Step 3 sub-bullet in general form; plant plus `flags_derivable_list` detector; on arm flags the seeded diff, off arm quiet.
6. D6 Phase order — 1 to 8 as in Phase Status; plan-format cut first for the spec budget; item 7 last because it edits Step 3.
7. D7 rule_meter.py registration — Option A (extended by agent-evals-c3, 2026-11-22): every plant and detector this lane adds (DL01, DL02, PI01, BL01) lives in rule_meter.py with payloads in rule_meter_checks/ and tests in bin/; a scenario whose text this branch cuts runs its arms first, then is retired after `rule_trials.py build`; status check before each edit, worktree `toolkit_root` for the arms then re-pointed to `/home/brandon/dotfiles/claude/.claude` before the final commit. Trade-off: two edits to a shared script.
8. Q1 Item 6 target — the PLAN-IMPACT rule (three copies), not the "no criteria file" rule.
9. Q2 verify-branch:44 — "It is the only run site." becomes a /close-branch pointer.
10. Q4 finding-log anchor rows 179, 180, 182 — dropped with the file.
11. Q5 smell-reviewer rg slice of `### Step 3: Structure` — kept; no structure-rules extraction.
12. Q6 The "four" single-loader files — skimmable-writing, design-decision-format, finding-log, plan-reading.
13. Q8 Rules the meter cannot grade — change file `unmeasured` plus the final report to agent-evals-c3.

## Approaches Considered and Not Taken

- A new `_shared/plan-impact.md` as the rule's owner: adds a read to every loader and no agent scenario could grade it.
- Moving code-reviewer Step 3 into a `_shared` structure file for smell-reviewer: breaks the live meter `rule_text` of R, S and AE.
- Folding or renaming code-vocabulary: the stale-citation gate cites its path in a block message.

## Constraints

- Item 8 (`retire-branch-recap-or-mark-it-legacy-against`) is bcpc-arch's: leave todos:3, test-audit:3 and code-vocabulary:44 untouched (exercised: the queue shows bcpc-arch as claimant).
- Off limits: `skills/_shared/plan-reading.md`, `skills/code/`, every CLAUDE.md, `settings.json`, orchestration.md, `rule_meter.py` beyond the D7 registration lines.
- Spec budget gate (`claude/.claude/scripts/gates/spec_budget_gate.py:22`): resident 1494/1500 words, total 8363/8700, `SHARED_FILES` includes `design-decision-format.md`; the Edit delta is new minus old words and a deletion is invisible to it (exercised: probe of the gate source and word counts; design-decision-format 342 words, 5-decisions 735). 6-finalize must not grow.
- Live meter `rule_text` strings stay byte-identical: coder-core G (:51), H (:10-19), K2, AB, AC, AD, I (:73), J (:65); code-reviewer AE (:58 fragment), R and S (Step 3 item 1 through "...to be correct."); 5-decisions line 71 (ES01/ES02, four-space indent). `rule_meter_shipped.json` lines stay (coder-core bug-fix test-first line, bind catch error, :55, :59, :61; code-reviewer index line; test-reviewer Step 3c fixture line) (exercised: `rule_meter_scenarios.json` read).
- Test-asserted strings stay (exercised: test sources read): `tests/scripts/test_guidance_rules.py` (review-fork-run `<run folder>/review-stop.md`, `` `To go on: /<skill> resume <your feedback>` ``, `Never call AskUserQuestion.`; coder-core lines 18-20, 165-166, 201-203; spec-criteria; test-intent-reviewer and test-reviewer cull lines), `test_log_review_finding.py` (`file=` form), `test_spec_agent_tools.py` (goal-blind-researcher exclude globs), `test_adr_flow.py` (adr-template path), `test_stale_citation_gate.py` (code-vocabulary path).
- Headings read by code: reviewer-calibration `## Calibration Anchor`, `## Verify the Premise Before Flagging`, `## Disposition`, `## Self-Check Before Reporting` (the `calibration_refs_guard.py` PostToolUse hook rejects a bold span on a line citing reviewer-calibration.md in `agents/*reviewer*.md` unless it is one of these); code-reviewer `### Step 3: Structure` (smell-reviewer rg slice); plan_format.py:682 matches "Close pass" in Phase Status (exercised).
- `docs/rule-anchors.md`: 185 rows; a hash is the heading block whitespace-collapsed sha256 first 8 hex; once a file has rows every block needs one; `check` passes at baseline (exercised).
- Rule meter: `run-all --dry-run` with no `--rule` is red on a stale CLAUDE.md scenario that is not this plan's (exercised); every meter check runs per rule. The off arm removes `rule_text` once verbatim; arms run with `CLAUDE_CONFIG_DIR` in a temp dir so literal `~/.claude` pointers read master's copy; agent scenarios copy only `agents/<name>.md` and its `skills:` preloads, no `_shared` files (exercised: rule_meter.py read). PF01/PF02 exist with `~/dotfiles-test-budget-gate` as `toolkit_root` (present); RF01/RF03/RF05 and L point at worktrees that no longer exist, so their dry-runs fail today (exercised) and only the W copies and CU01/CU02 measure those files; ES01/ES02 resolve against `~/.claude`.
- `tests/changed_scope.py`: a change under docs/ or tests/ or opencode/ makes `bash tests/run.sh` run the full suite; run it under `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0` in the background after `free -g` shows 8 GB free (lane rule).
- Change notes: `python3 /home/brandon/agent-evals/bin/build_changes.py new "<title>" --by claude-code/claude-fable-5-1 --root /home/brandon/dotfiles-toolkit-prose-nov22/docs/changes`, then `python3 /home/brandon/agent-evals/bin/build_changes.py --root /home/brandon/dotfiles-toolkit-prose-nov22/docs/changes`. The lane brief names `/home/brandon/dotfiles/docs/changes`; this plan writes the note into the worktree so it ships on the branch, and the final report says so.
- No rationale in agent or skill bodies. Toolkit-edit propagation sweep (grep consumers, patch or state-skip the opencode port, check inheriting variants) before any phase is called done. Opencode ports keep their adaptations (AGENTS.md, frontmatter, "First action: Read"); never copy claude text over existing port drift. A missing opencode file is a stated skip, never a created file.
- `rm` may be blocked by a hook: delete a tracked file with `git rm`, once, and list the block in the report.

## External Contracts

- rule-anchors sidecar (`docs/rule-anchors.md`, read by `claude/.claude/scripts/tools/rule-anchors.sh check`): every heading block of an anchored file has a row with its current hash; a changed block without a refreshed row fails the check and CI (exercised).
- `~/agent-evals/bin/rule_meter_scenarios.json`: `rule_text` must appear verbatim in `rule_source` under `toolkit_root`, else the run fails to build the off arm (exercised: run-all source).
- `~/agent-evals/bin/rule_meter.py` `PLANTS`, `SETUPS` and `grade()` registries, `rule_meter_verifier.DETECTORS` and `rule_meter_fixture.DETECTORS`: a detector name a scenario names must resolve in them (declared-only: read from the source, not run).
- `claude/.claude/scripts/gates/spec_budget_gate.py` (Edit hook on eng-spec files): resident and total word caps above; `SHARED_FILES` names the three `_shared` files it counts (exercised).
- `tests/scripts/test_spec_budget_gate.py:146-157`: asserts the gate's message text (`"~8701 words"`, `"currently 8100"` with 1601 written) against the summed real files; its numbers change when `SHARED_FILES` does (exercised: test read).
- `~/agent-evals` queue (`build_queue.py set <slug> --status done --outcome <stem>`): closes are committed with `git -C ~/agent-evals commit -- queue/<slug>.md QUEUE.md queue/index.md`, then `pull_keep_index.py` and push (declared-only).

## Approach

- Areas: (a) `_shared` and skill prose, (b) agent prose and descriptions, (c) the two Python tests and the budget gate tuple, (d) `docs/rule-anchors.md`, (e) agent-evals meter assets (scenarios, detector, tests, D7 registration), (f) `docs/changes/` notes, (g) opencode ports. Phases below slice by queue item, each touching whichever areas it needs.
- Order inside every phase: dry-run the live meter scenarios that touch a file the phase edits; run the off arm of any cut or reworded rule BEFORE the edit (the live text), the on and off arms of new or relocated text AFTER the edit with `toolkit_root` at this worktree; edit; refresh anchor rows (`rule-anchors.sh list <file>` for the new hashes, then `check`); patch or state-skip the opencode port; write the change note with per-arm counts and `unmeasured`; run the named test files; run the suite.
- Pattern for every reworded line: the eight toolkit-writing checks (lead with the action, one default, exactness matches fragility, no rationale).

## Dependencies

- No new packages. Internal: `rule_meter.py` registries, `rule_meter.py` `detect_names_prior_art` as the detector template, `tests/parallel_tests.py`, `rule-anchors.sh`, `build_changes.py`, `build_queue.py`.

## Implementation Plan

## Acceptance Criteria

The criteria live in `docs/plans/toolkit-prose-1122/acceptance-criteria.md` as prose with stable ids, written by Phase 7.5. Name the file here and nothing more — never restate the criteria, never copy their ids into code.

- **Criteria file**: `docs/plans/toolkit-prose-1122/acceptance-criteria.md`

The Close pass reconciles every id against the real suite (`_shared/closing-phases.md`), matching behavior, not markers. A covering test asserts at the public boundary a user or caller reaches, never an internal function. **No mocks inside such a test.**

## What We're NOT Doing

- Item 8 and its three references; `plan-reading.md` (follow-up queue item filed at close); `skills/code/`; CLAUDE.md files; `settings.json`; orchestration.md.
- `rule_meter.py` logic beyond the D7 registration lines; extracting the Step 3 structure rules; modernizing the opencode code-reviewer; growing 6-finalize; `~/agent-evals/bin/escape_classes.py` and its test (another session's).

## Phase 0: Contracts

### Overview

The frozen strings and registries every later phase must leave intact. No file changes; the contracts are the Constraints and External Contracts above, checked here so a later phase that moves one fails loudly.

### Changes Required:

None. **Files**: none.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the anchor sidecar matches the tree at baseline — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Test-verified**: PF01 resolves its `rule_text` (the dry-run prints its cells and exits 0) — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --dry-run --rule PF01`
- [ ] **Test-verified**: ES01 resolves its `rule_text` — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --dry-run --rule ES01`
- [ ] **Test-verified**: G (coder-core) resolves its `rule_text` — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --dry-run --rule G`
- [ ] **Test-verified**: AE (code-reviewer) resolves its `rule_text` — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --dry-run --rule AE`
- [ ] **Test-verified**: R (code-reviewer Step 3) resolves its `rule_text` — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --dry-run --rule R`
- [ ] **Test-verified**: the four calibration headings are present as `##` lines — `rg -c '^## (Calibration Anchor|Verify the Premise Before Flagging|Disposition|Self-Check Before Reporting)$' claude/.claude/skills/_shared/reviewer-calibration.md`

#### Manual Verification:

- [ ] Manual Verification: N/A (contracts-only)

---

## Phase 1: Walking skeleton — plan-format tightening and the design-decision-format fold

### Overview

The thinnest end-to-end path through every area: a `_shared` cut, a skill fold, a gate tuple and test edit, an anchor refresh, a meter arm and a change note. It also buys the spec-budget headroom the fold needs: plan-format shrinks before 5-decisions grows.

### Changes Required:

#### 1. plan-format split

**File**: `claude/.claude/skills/_shared/plan-format.md`
**Changes**: Split line 25 (Phase 0 / walking skeleton) into one bullet per rule. Split line 30 (Automated Verification shapes) into one bullet per shape (three), then one bullet each for the rg ban/presence rule, the wrapped-search rule and the must-end-by-itself rule. Split line 31 (Expected red / File entries) into two bullets. Leave the :67 comment and the :69 Phase Status line (plan_format.py:682 matches "Close pass"; closing-phases:22 copies it). Replace lines 91-94 with: "A test covers a criterion by its behavior, never by a marker: it asserts at the public boundary a user or caller reaches, never an internal function. **No mocks inside such a test.**" Keep the :36-38 pointer to closing-phases. Every sentence keeps its words where PF01/PF02 `rule_text` quotes it.

#### 2. design-decision-format fold

**Files**: `claude/.claude/skills/eng-spec/phases/5-decisions.md`, `claude/.claude/skills/eng-spec/templates/spec-template.md`, `claude/.claude/skills/_shared/design-decision-format.md` (deleted with `git rm`)
**Changes**: In 5-decisions step 13 (lines 39-42) replace the pointer with the text below, indented four spaces so it stays inside list item 13 (the fence is not part of the text):

```markdown
Record each decision as one block headed `### N. [Topic]` (spec-template indexes that heading) with:
- **Choice:** what was picked.
- **Reasoning:** why it wins here.
- **Alternatives rejected:** each with the user-visible failure mode it would cause.
- **Trade-off accepted:** what this choice costs.

Never batch decisions into a table. No real alternative = constraint: record it under `## Direction & Constraints`. A rejection that only narrows scope needs the user's explicit sign-off. A choice that leaves credentials or data alive past the user's removal intent: state it in security terms, and it needs the user's explicit sign-off.
```

Line 71 stays byte-identical (ES01/ES02). In spec-template's External Contracts comment add: "Accepted-by-the-tool claims may NOT rest on declared-only: upgrade the evidence or add the staged step, and say which." Delete design-decision-format.md.

#### 3. Budget gate and its test

**Files**: `claude/.claude/scripts/gates/spec_budget_gate.py`, `tests/scripts/test_spec_budget_gate.py`
**Changes**: `SHARED_FILES = ("plan-format.md", "closing-phases.md")`. In the test (lines 146-157) drop design-decision-format from the names and write 2601 words to spec-questions in place of 1601. The test builds synthetic 1000-word files, so the expected strings become `"~8701 words"` (7 × 1000 + 100 + 1601) and `"currently 7100"`.

#### 4. Anchors, meter, change note

**Files**: `docs/rule-anchors.md`, `/home/brandon/agent-evals/bin/rule_meter_scenarios.json`, `docs/changes/` (one new note from `build_changes.py new`)
**Changes**: Refresh every row for plan-format, 5-decisions and spec-template blocks whose hash moved; drop rows for design-decision-format if any. Add ES01W and ES02W as copies of ES01/ES02 with `"toolkit_root": "/home/brandon/dotfiles-toolkit-prose-nov22/claude/.claude"` (they prove the worktree-copy mechanism; line 71 is unchanged). No PF copies: PF01/PF02 `rule_text` is not in this worktree's plan-format, so the plan-format splits are `unmeasured`. Grep the repo for every remaining `design-decision-format` reference and fix each. Change note lists per-arm counts (ES01W, ES02W) and `unmeasured` (plan-format :25/:30/:31 splits, :91-94 reword, spec-template line, 5-decisions fold including the heading form and the scope-only-rejection sentence it carries over).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: no reference to the deleted file remains — `rg -n --hidden 'design-decision-format' claude/.claude opencode tests docs/rule-anchors.md`
- [ ] **Test-verified**: the fold text is present — `rg -n -F 'Alternatives rejected' claude/.claude/skills/eng-spec/phases/5-decisions.md`
- [ ] **Test-verified**: the declared-only line is present — `rg -n -F 'may NOT rest on declared-only' claude/.claude/skills/eng-spec/templates/spec-template.md`
- [ ] **Test-verified**: the reworded criterion-test rule is present — `rg -n -F 'No mocks inside such a test.' claude/.claude/skills/_shared/plan-format.md`
- [ ] **Test-verified**: line 71 of 5-decisions is byte-identical (presence) — `rg -n -F '    - Start each block'"'"'s heading with an emoji for its kind' claude/.claude/skills/eng-spec/phases/5-decisions.md`
- [ ] **Test-verified**: anchors — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Test-verified**: budget gate test — `python3 tests/parallel_tests.py test_spec_budget_gate.py`
- [ ] **Agent-run**: ES01W arms — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule ES01W`
- [ ] **Agent-run**: ES02W arms — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule ES02W`
- [ ] **Agent-run**: full suite under the memory cap — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: `python3 /home/brandon/agent-evals/bin/build_changes.py --check --root /home/brandon/dotfiles-toolkit-prose-nov22/docs/changes` exits 0 and the new note names the on/off counts per arm and the `unmeasured` list.

---

## Phase 2: Item 1 — contradictory lines and dispatcher descriptions

### Overview

Each listed line names one action and contradicts nothing in its file; plan-verifier and test-intent-reviewer descriptions name every dispatcher. All factual corrections: `unmeasured`.

### Changes Required:

#### 1. Skill lines

**Files**: `claude/.claude/skills/orient/SKILL.md`, `claude/.claude/skills/todos/SKILL.md`, `claude/.claude/skills/list/SKILL.md`, `claude/.claude/skills/pull-ticket/SKILL.md`, `claude/.claude/skills/verify-branch/SKILL.md`
**Changes**: orient:78 → "- Never edits a repo file; its only writes are the vault note and the `note` capture line above." todos:15 → "Run nothing beyond those two git commands: no scans, queries or subagents. An item the conversation never established is not a todo." list:33 → "- Name the file that holds the full text (report, diff) once, on the line after the list and before the closing line." pull-ticket:16 → "'To Do': tell the user work is starting, in one line. 'In Progress': state the status in the presentation and go on. 'In Review' or 'Done': warn, and ask the user to confirm before going on." verify-branch:44 "It is the only run site." → "/close-branch Step 2 dispatches it with the same payload."

#### 2. Agent descriptions and the cull scope line

**Files**: `claude/.claude/agents/plan-verifier.md`, `claude/.claude/agents/test-intent-reviewer.md`, `opencode/.config/opencode/agents/plan-verifier.md`, `opencode/.config/opencode/agents/test-intent-reviewer.md`
**Changes**: claude plan-verifier line 3 → `description: "Checks each plan criterion against the branch diff: done, partial or missing, with evidence. Dispatched by /verify-branch and /close-branch at branch end."` claude test-intent-reviewer line 3 → `description: "Audits whether changed tests pin intent or implementation. Dispatched by /test-audit and /close-branch with scope: cull, or by the user with scope: bug-pinning."` (double-quoted: the value holds `: `, which YAML rejects unquoted). test-intent-reviewer:39 → "- **`scope: cull`** (from `/test-audit` and `/close-branch`, the assembled branch diff) — run Steps 4 and 5. **Skip Step 3 entirely** and omit its section." Opencode ports name opencode's own commands (`commands/` has `verify.md` and `test-audit.md`, no close-branch): port plan-verifier line 3 keeps "Dispatched by /verify" and gains "at branch end"; port test-intent-reviewer line 3 → `description: "Audits whether changed tests pin intent or implementation. Dispatched by /test-audit with scope: cull, or by the user with scope: bug-pinning."`; port :45 cull line unchanged.

#### 3. Anchors and change note

**Files**: `docs/rule-anchors.md`, `docs/changes/` (new note)
**Changes**: refresh plan-verifier row 98 (908b429f) and test-intent-reviewer rows 34 (03d2949c, preamble) and 36 (9dc3d39d, Step 2); any skill row whose block moved. Change note: `unmeasured` for all eight lines (factual corrections).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the plan-verifier description names close-branch (presence) — `rg -c -F 'Dispatched by /verify-branch and /close-branch at branch end.' claude/.claude/agents/plan-verifier.md`
- [ ] **Test-verified**: the test-intent-reviewer description names close-branch (presence) — `rg -c -F 'Dispatched by /test-audit and /close-branch with' claude/.claude/agents/test-intent-reviewer.md`
- [ ] **Test-verified**: the port plan-verifier description is present — `rg -c -F 'Dispatched by /verify at branch end.' opencode/.config/opencode/agents/plan-verifier.md`
- [ ] **Test-verified**: the port test-intent-reviewer description is present — `rg -c -F 'Dispatched by /test-audit with scope: cull' opencode/.config/opencode/agents/test-intent-reviewer.md`
- [ ] **Test-verified**: both agent frontmatters parse — `python3 tests/parallel_tests.py test_spec_agent_tools.py`
- [ ] **Test-verified**: the old "only run site" sentence is gone — `rg -n -F 'It is the only run site.' claude/.claude/skills/verify-branch/SKILL.md`
- [ ] **Test-verified**: the new orient write line is present — `rg -n -F 'its only writes are the vault note' claude/.claude/skills/orient/SKILL.md`
- [ ] **Test-verified**: anchors — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Test-verified**: prompt-reading tests — `python3 tests/parallel_tests.py test_guidance_rules.py`
- [ ] **Agent-run**: full suite — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: read each of the five skill files end to end; no line contradicts another in its file (todos still allows exactly the two git commands; list names the file once).

---

## Phase 3: Item 3 — architect descriptions and the Reuse Map owner

### Overview

Both architect descriptions shrink to the dispatch sentence; architect-core owns the exploration brief and the Reuse Map rules; 4-explore and both architects point to it.

### Changes Required:

#### 1. architect-core absorbs the brief and the Reuse Map rules

**File**: `claude/.claude/skills/architect-core/SKILL.md`
**Changes**: The Two-Stage Dispatches section (lines 18-20) absorbs the seven-item exploration-brief list from 4-explore:12-41, the invariant survey rewritten as a list with one branch per item (the ticket's item 2 names this paragraph), and the Exception clause (the ground-truth sentence at :20 already exists; do not duplicate it). Add a `## Reuse Map` section: "Seed it from `02-research.md`'s `## Reuse Inventory` when the research doc has one, THEN add what your own search found." and "Every NEW helper/service/util this plan introduces must appear here with one line on why no listed unit covers it. That justification line is the gate."

#### 2. 4-explore prompt

**File**: `claude/.claude/skills/eng-spec/phases/4-explore.md`
**Changes**: lines 7-41 → the prompt "> Stage 1: explore only, do NOT produce an implementation plan. The research document you were given was produced without sight of the ticket. Return the exploration brief your architect-core Two-Stage Dispatches section defines." (keep the surrounding step numbering).

#### 3. Architect agents and ports

**Files**: `claude/.claude/agents/backend-architect.md`, `claude/.claude/agents/frontend-architect.md`, `opencode/.config/opencode/agents/backend-architect.md`, `opencode/.config/opencode/agents/frontend-architect.md`
**Changes**: backend description → `description: Designs backend features (data models, API contracts, schemas, services) as plans for the coder. Dispatched by /eng-spec phase 4.`; frontend → `description: Designs frontend features (components, state, styling) as plans for the coder. Dispatched by /eng-spec phase 4.` (all four files). In both claude architects the Reuse Map template keeps its table and gets one line "(rules: architect-core Reuse Map)"; delete the seed and gate paragraphs (frontend :53 seed line). In both opencode ports do the same (backend :42 and :44, frontend :49-55); after the cut `rg -n 'That justification line is the gate|Seed it from' opencode claude/.claude` lists only architect-core. Leave opencode line 11 "preloaded via architect-core" as is.

#### 4. Anchors and change note

**Files**: `docs/rule-anchors.md`, `docs/changes/` (new note)
**Changes**: refresh backend rows 138, 141; frontend rows 174, 178 (and 176 if its block moved); architect-core row 146 (45765a1b); add a row for the new Reuse Map block; refresh 4-explore rows if anchored. Rewrite the description column of rows 138, 174 and 178: they say "description with the go-lean skip test" and "reuse map seeded from the research document", which the cut makes false. Change note: `unmeasured` (descriptions, relocations).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the backend description carries the dispatch sentence (presence) — `rg -c -F 'Dispatched by /eng-spec phase 4.' claude/.claude/agents/backend-architect.md`
- [ ] **Test-verified**: the frontend description carries it (presence) — `rg -c -F 'Dispatched by /eng-spec phase 4.' claude/.claude/agents/frontend-architect.md`
- [ ] **Test-verified**: the port backend description carries it (presence) — `rg -c -F 'Dispatched by /eng-spec phase 4.' opencode/.config/opencode/agents/backend-architect.md`
- [ ] **Test-verified**: the port frontend description carries it (presence) — `rg -c -F 'Dispatched by /eng-spec phase 4.' opencode/.config/opencode/agents/frontend-architect.md`
- [ ] **Test-verified**: the gate sentence is present in architect-core — `rg -c -F 'That justification line is the gate.' claude/.claude/skills/architect-core/SKILL.md`
- [ ] **Test-verified**: no architect agent or phase file still carries the gate sentence — `rg -l -F 'That justification line is the gate.' claude/.claude/agents claude/.claude/skills/eng-spec opencode/.config/opencode/agents`
- [ ] **Test-verified**: no architect agent or phase file still carries the seed sentence — `rg -l -F 'Seed it from' claude/.claude/agents claude/.claude/skills/eng-spec opencode/.config/opencode/agents`
- [ ] **Test-verified**: 4-explore no longer carries the invariant survey — `rg -n -i 'invariant' claude/.claude/skills/eng-spec/phases/4-explore.md`
- [ ] **Test-verified**: anchors — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Test-verified**: agent tool tests — `python3 tests/parallel_tests.py test_spec_agent_tools.py`
- [ ] **Agent-run**: full suite — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: read architect-core Two-Stage Dispatches once; the seven brief items, the invariant survey and the Exception clause each appear exactly once.

---

## Phase 4: Item 4 — general-purpose body

### Overview

Meter the current body live, then cut it to the four behavior-changing lines in both trees.

### Changes Required:

#### 1. Meter first (live text)

**File**: `/home/brandon/agent-evals/bin/rule_meter_scenarios.json`
**Changes**: Add GP01 (agent `general-purpose`, `rule_source` `agents/general-purpose.md`, `rule_text` = body lines 7-18 verbatim, worktree `toolkit_root`, G's task and suffixes, detector `extend_not_copy`) and GP02 (same agent, `rule_source`, `rule_text` and `toolkit_root`; J's task, plant `plant_red_money_test`, detector `red_test_kept`). Run both before any edit and record the per-arm counts in the change note. If either cannot build (the body text is not one contiguous `rule_text` the off arm can remove), record the cut as `unmeasured`. After the cut the `rule_text` is gone and `check_rule_texts` would exit on it, so remove GP01 and GP02 from scenarios.json in the same commit as the cut (retired scenarios; the counts live in the change note).

#### 2. Body cut

**Files**: `claude/.claude/agents/general-purpose.md`, `opencode/.config/opencode/agents/general-purpose.md`
**Changes**: claude body becomes exactly the current lines 19-22 (prefer editing existing files; docs only when asked; absolute paths and no code recap; "Report what you verified and what you did not. Never state an unverified claim as fact."). opencode: keep frontmatter lines 1-7 and replace lines 9-24 with the port's own phrasing of the same four rules, keeping its existing wording where a line already says one of them (record as an opencode reword).

#### 3. Change note

**Files**: `docs/changes/` (new note). No anchor rows (file unanchored).

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the copied harness prose is gone from both trees — `rg -n 'Your strengths|Guidelines:|Be thorough' claude/.claude/agents/general-purpose.md opencode/.config/opencode/agents/general-purpose.md`
- [ ] **Test-verified**: the kept report line is present — `rg -c -F 'Never state an unverified claim as fact.' claude/.claude/agents/general-purpose.md`
- [ ] **Test-verified**: the port keeps a report line (presence) — `rg -c -i 'verified' opencode/.config/opencode/agents/general-purpose.md`
- [ ] **Agent-run**: GP01 arms, before the cut — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule GP01`
- [ ] **Agent-run**: GP02 arms, before the cut — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule GP02`
- [ ] **Test-verified**: GP01 and GP02 are retired after the cut — `rg -n '"GP0[12]"' /home/brandon/agent-evals/bin/rule_meter_scenarios.json`
- [ ] **Agent-run**: full suite — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: `wc -l claude/.claude/agents/general-purpose.md` shows frontmatter plus at most four body lines.

---

## Phase 5: Item 5 — folds, pointer triggers, consumer lists, cull-rule owner

### Overview

finding-log folds into test-audit, skimmable-writing into adr-template; every escape-ratchet pointer names its trigger; consumer lists match the loaders; the cull rule gets one owner in test-intent-reviewer.

### Changes Required:

#### 1. finding-log fold

**Files**: `claude/.claude/skills/test-audit/SKILL.md`, `claude/.claude/skills/_shared/finding-log.md` (deleted with `git rm`), `tests/scripts/test_log_review_finding.py`
**Changes**: test-audit `## Logging` replaces the :42 pointer with finding-log's Emit section (:7-26) and Rules (:30-39, :44-53); drop :40-43 (`source=`) and the `[source=<round|class|gate|scoped>]` token on Emit :24; keep the single `<'file=<path>' line=<n>|file=unlocated>` form, the quoted `'root=<its absolute path>'`, never an unquoted `file=<path>`; keep `gate=test-intent-reviewer lane=test-audit scope=branch-exit` and "Zero-finding audits still log `kind=run`."; do not touch test-audit:3. test_log_review_finding.py:23 `FINDING_LOG_RULE` points at the test-audit SKILL.md path through `toolkit_paths`.

#### 2. skimmable fold

**Files**: `claude/.claude/skills/_shared/adr-template.md` (the file `adr_flow.py:44` and `test_adr_flow.py:21` name; it stays in `_shared`), `claude/.claude/skills/_shared/skimmable-writing.md` (deleted with `git rm`)
**Changes**: adr-template "## Write for skimmability": replace :40 with skimmable :5-19; merge :41 with skimmable :20 and :42 with skimmable :5. `test_adr_flow.py` must still pass.

#### 3. Escape-ratchet pointers and consumer lists

**Files**: `claude/.claude/skills/verify-branch/SKILL.md`, `claude/.claude/skills/pr-comments/SKILL.md`, `claude/.claude/skills/commit/SKILL.md`, `claude/.claude/skills/fix/SKILL.md`, `claude/.claude/skills/escape/SKILL.md`, `claude/.claude/skills/cc/SKILL.md`, `claude/.claude/skills/eng-spec/phases/6b-review.md` (line 50 only), `claude/.claude/skills/_shared/escape-ratchet.md`, `claude/.claude/skills/_shared/code-vocabulary.md`, `claude/.claude/agents/spec-criteria.md`, `opencode/.config/opencode/agents/spec-criteria.md`
**Changes**: verify-branch:63 "...before you pick the guard rung, read `~/.claude/skills/_shared/escape-ratchet.md` (batching rule across the list)..."; pr-comments:58 "Before you log each escape, read `~/.claude/skills/_shared/escape-ratchet.md` and pick the rung, including the ADR addendum, batched by class; ..."; commit:36 "before you log the escape, read `~/.claude/skills/_shared/escape-ratchet.md` and pick `guard` and `miss_reason`, without pausing; ..."; fix:38 "before you log the escape, read `~/.claude/skills/_shared/escape-ratchet.md` and pick `guard`, without pausing"; escape:24 "**Ratchet** — before you log the escape, read `~/.claude/skills/_shared/escape-ratchet.md`, run the guard decision and pick the miss reason."; cc:78 "`guard` is the ratchet rung and `miss_reason` the label; before you pick either, read `~/.claude/skills/_shared/escape-ratchet.md`." 6b-review:50 "`guard=` is the rung from `~/.claude/skills/_shared/escape-ratchet.md`" → "before you pick `guard=`, read `~/.claude/skills/_shared/escape-ratchet.md` for the rung". escape-ratchet:5-6 → "Consumers: `/escape`, `/cc`, `/fix`, `/refactor`, `/verify-branch`, `/commit`, `/pr-comments`, `/close-branch`, `/eng-spec` (plan review); the scripts `scripts/telemetry/log-escape`, `scripts/review/verify-log` and `skills/refactor/scripts/refactor_flow.py` cite it in their messages." code-vocabulary:5 → "Consumers: `spec-criteria`, and the gates `scripts/gates/stale_citation_gate.py` and `scripts/gates/comment_bloat_gate.py`, which cite this file in their block messages. The coders carry a one-sentence ban of their own and do not load this file." (line 44 untouched). Before the edit, run `rg -l 'escape-ratchet' claude/.claude` and `rg -l 'code-vocabulary' claude/.claude` and make each list match that output exactly (a script or gate that cites the file counts as a loader). spec-criteria:58 and the opencode port :52 → "**Prose, out of the shipped tree.** Never stubs, never placeholders under `tests/`, never ids/paths into `tests/` or `src`; before you write a criterion that names code, read `~/.claude/skills/_shared/code-vocabulary.md` for the banned vocabulary."

#### 4. Cull-rule owner

**Files**: `claude/.claude/agents/test-reviewer.md`, `opencode/.config/opencode/agents/test-reviewer.md`
**Changes**: test-reviewer:45 → "**Step 5: Cull check — branch scope ONLY.** For every test the branch **added**, apply the first paragraph under `## Step 4 — Cull check (added tests only)` in `~/.claude/agents/test-intent-reviewer.md`. Pre-existing and modified tests are out of bounds. Genuinely-new-but-weak = weak-assertion finding (tighten), not cull." The opencode port's `### Step 5: Cull Check` (line 110) points the same way at the port test-intent-reviewer's `## Step 4 — Cull check` (line 68). No meter scenario: the only cull detector (`cull_keeps_same_path_input_shape`) grades the input-shape rule, which lives in test-intent-reviewer:53 and not in the cut text, so the cut is `unmeasured` and goes to agent-evals-c3 in the final report.

#### 5. Tests, anchors, change note

**Files**: `tests/scripts/test_guidance_rules.py`, `docs/rule-anchors.md`, `docs/changes/` (new note)
**Changes**: new assertions: test-reviewer Step 5 contains `test-intent-reviewer.md` and lacks "Deleting pre-existing tests"; test-audit contains `gate=test-intent-reviewer lane=test-audit`. Anchors: drop rows 179, 180, 182 (finding-log); refresh test-reviewer row 51 (a4ba4e3d), code-vocabulary row 59 (ea32292f) if its block moved, spec-criteria rows 162-167, every escape-pointer skill row whose block moved (test-audit and adr-template have no rows). Opencode: the test-reviewer port is patched in §4; test-audit, adr-template and escape-ratchet have no port; the port code-reviewer:57 code-vocabulary reference is out of scope. Change note: `unmeasured` for the folds, pointers, consumer lists and the test-reviewer cull cut.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: no reference to the two deleted files remains — `rg -n --hidden 'finding-log\.md|skimmable-writing' claude/.claude opencode tests docs/rule-anchors.md`
- [ ] **Test-verified**: the quoted file form is present in test-audit — `rg -n -F "'file=<path>'" claude/.claude/skills/test-audit/SKILL.md`
- [ ] **Test-verified**: no weak "per X" escape-ratchet pointer remains — `rg -n '(per|from) .~/.claude/skills/_shared/escape-ratchet.md.' claude/.claude/skills`
- [ ] **Test-verified**: the stale `/audit review` consumer is gone from escape-ratchet — `rg -n -F '/audit review' claude/.claude/skills/_shared/escape-ratchet.md`
- [ ] **Test-verified**: both spec-criteria files carry the trigger (presence) — `rg -c -F 'before you write a criterion that names code' claude/.claude/agents/spec-criteria.md opencode/.config/opencode/agents/spec-criteria.md`
- [ ] **Test-verified**: anchors — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Test-verified**: finding-log test — `python3 tests/parallel_tests.py test_log_review_finding.py`
- [ ] **Test-verified**: adr flow test — `python3 tests/parallel_tests.py test_adr_flow.py`
- [ ] **Test-verified**: guidance rules test — `python3 tests/parallel_tests.py test_guidance_rules.py`
- [ ] **Test-verified**: the 6b-review weak pointer is gone — `rg -n -F 'is the rung from' claude/.claude/skills/eng-spec/phases/6b-review.md`
- [ ] **Test-verified**: the port test-reviewer points at the port cull step (presence) — `rg -c -F 'Step 4 — Cull check' opencode/.config/opencode/agents/test-reviewer.md`
- [ ] **Agent-run**: full suite — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: `rg -l 'escape-ratchet' claude/.claude` and `rg -l 'code-vocabulary' claude/.claude` each list exactly the consumers the file's line 5 names, scripts and gates included.

---

## Phase 6: Item 2 remainder — dense paragraphs

### Overview

review-fork-run gets `##` headings and a bulleted Resume; coder-core's verify paragraph becomes a list; reviewer-calibration states the blocker rule once and loses its rationale; 6b-review, goal-blind-researcher and spec-research become one-branch lists.

### Changes Required:

#### 1. review-fork-run

**Files**: `claude/.claude/skills/_shared/review-fork-run.md`, `/home/brandon/agent-evals/bin/rule_meter_scenarios.json`
**Changes**: `##` headings: The run folder, Launch, Reviewers, The packet's ACTION lines, Ending the run hands back, Resume. Resume becomes bullets in this order: intro; launch nothing; `--by session` / `--by user`; what the user said with `--relayed-by`; `decide --by session` needs `--plan`; "Answer the stop you resume:" with sub-bullets for asks-done outcomes (modified, applied, held), held asks, conditional refusal, `--correct`, plan-impact decide, test commands, no pending run; end with "Then do what that output's ACTION lines say." Keep verbatim `<run folder>/review-stop.md`, `` `To go on: /<skill> resume <your feedback>` `` and `Never call AskUserQuestion.`. Meter: RF03 and RF05 `rule_text` is not in the file today, so no copies of them; the lines they graded are `unmeasured`. BEFORE the edit add RF01B (copy of RF01 with worktree `toolkit_root`, detector `asks_done_by_session`) and run both arms; after the edit add RF01W (same, `rule_text` = the new `--by session` / `--by user` bullet verbatim) and run both arms; record all four counts in the change note, run `python3 /home/brandon/agent-evals/bin/rule_trials.py build`, then delete RF01B from scenarios.json in the same commit (its text is gone). The "Answer that stop:" → "Answer the stop you resume:" reword is `unmeasured`.

#### 2. coder-core verify list

**File**: `claude/.claude/skills/coder-core/SKILL.md`
**Changes**: line 77 → "If your brief says a hook runs the checks when you call SubagentHandback, do not run them yourself. Fix what the hook returns, then call SubagentHandback again. Otherwise:" followed by bullets: run the typecheck, lint and tests on the changed files with the plan's command, else the repo runner, else plain `pytest` only when none is named, and a collection error or no tests collected is not a pass; never the whole suite, lint or build; a long test file by name or in the background; each check to `<check> > /tmp/<name>.log 2>&1` then Read or `rg` the log; never pipe into head, tail or grep (the hook denies a second run). Keep the strings test_guidance_rules asserts (lines 18-20, 165-166, 201-203) and every live `rule_text` (G, H, K2, AB, AC, AD, I, J).

#### 3. reviewer-calibration dedupe

**File**: `claude/.claude/skills/_shared/reviewer-calibration.md`
**Changes**: the blocker rule stays at lines 69-74; cut lines 107 and 110 (restatements). Cut the rationale at line 80 from "Getting this wrong is silent..." to the paragraph end. The four `##` headings stay byte-identical.

#### 4. eng-spec agents and phase

**Files**: `claude/.claude/skills/eng-spec/phases/6b-review.md`, `claude/.claude/skills/eng-spec/phases/5-decisions.md`, `claude/.claude/agents/goal-blind-researcher.md`, `claude/.claude/agents/spec-research.md`, `opencode/.config/opencode/agents/goal-blind-researcher.md`, `opencode/.config/opencode/agents/spec-research.md`
**Changes**: 6b-review:7-23 step 19b → bullets with its commands verbatim. 5-decisions step 14 (about 12 sub-rules in one paragraph; the ticket's item 2 names it) → a list with one rule per item, every sentence kept, line 71 byte-identical. The opencode goal-blind-researcher port (:29 "Repair loop, bounded at two cycles") and spec-research port get the same list shapes in their own wording. goal-blind-researcher:35-44 step 3 → branches: material leak (re-dispatch, then re-run); still flagged after two cycles (re-dispatch once for word-for-word rewrites, then step 4); flag with no rewrite (stop and return). Keep the step-4 strings `exclude: !{docs/plans/<slug>/**,<source ticket folder>/**}`, `Name the folder, never the file`, `exclude: !{docs/plans/<slug>/**}`. spec-research:20-26 → bullets keeping verbatim "a questions path, an `exclude:` line and a target directory", "Search file contents only with `rg` in Bash", "Add `--glob '<the glob>'` to every `rg` in Bash", "filter by file type with `-t`, never a second glob", "Never search file contents with `grep -r`, `find -exec` or `git grep`", "never `cd` before a search", "never `sed -i`".

#### 5. Anchors and change note

**Files**: `docs/rule-anchors.md`, `docs/changes/` (new note)
**Changes**: refresh review-fork-run row 53 (a96a963a) and add six rows for the new headings; coder-core row 73 (be98a4ee); calibration rows 54 (dfb1a483), 57 (2c327e33), 58 if changed; goal-blind-researcher row at docs/rule-anchors.md:156 (8e9c0fa1); spec-research row at :159 (8054ae6c); 6b-review and 5-decisions rows if anchored. Opencode ports patched in §4. Change note: RF01B/RF01W per-arm counts; `unmeasured` for every layout split, the two rewords and the RF03/RF05 lines.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the six headings are present — `rg -c '^## (The run folder|Launch|Reviewers|The packet.s ACTION lines|Ending the run hands back|Resume)$' claude/.claude/skills/_shared/review-fork-run.md`
- [ ] **Test-verified**: the asserted ask ban is present — `rg -c -F 'Never call AskUserQuestion.' claude/.claude/skills/_shared/review-fork-run.md`
- [ ] **Test-verified**: the calibration rationale is gone — `rg -n -F 'Getting this wrong is silent' claude/.claude/skills/_shared/reviewer-calibration.md`
- [ ] **Test-verified**: the coder-core list form is present — `rg -n -U 'Otherwise:\n\n- Run the typecheck' claude/.claude/skills/coder-core/SKILL.md`
- [ ] **Test-verified**: anchors — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Test-verified**: guidance rules test — `python3 tests/parallel_tests.py test_guidance_rules.py`
- [ ] **Test-verified**: agent tool tests — `python3 tests/parallel_tests.py test_spec_agent_tools.py`
- [ ] **Test-verified**: calibration refs guard test — `python3 tests/parallel_tests.py test_calibration_refs_guard.py`
- [ ] **Test-verified**: step 14 is a list (presence of a bullet right after the step line) — `rg -n -U '^14\. .*\n\s+- ' claude/.claude/skills/eng-spec/phases/5-decisions.md`
- [ ] **Agent-run**: RF01B arms, before the edit — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule RF01B`
- [ ] **Agent-run**: RF01W arms, after the edit — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule RF01W`
- [ ] **Test-verified**: RF01B is retired — `rg -n '"RF01B"' /home/brandon/agent-evals/bin/rule_meter_scenarios.json`
- [ ] **Agent-run**: full suite — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --dry-run --rule <id>` for G, H, K2, AB, AC, AD, I, J, AE, R and S prints cells and no missing-text error.

---

## Phase 7: Item 6 — PLAN-IMPACT rule owner and the calibration pointer

### Overview

Meter the two code-reviewer lines live, then give the PLAN-IMPACT `acceptance_criteria:` rule one owner per side and point code-reviewer at reviewer-calibration once.

### Changes Required:

#### 1. Meter first (live text)

**File**: `/home/brandon/agent-evals/bin/rule_meter_scenarios.json`
**Changes**: PI01 (agent `code-reviewer`, `rule_text` = line 85, worktree `toolkit_root`, plant `plant_plan_contradicting_diff`: the base tree holds `docs/plans/x/acceptance-criteria.md` with one AC the HEAD diff contradicts; detector `pi_line_reported`: COMPLIED when a finding opens with `PLAN-IMPACT:`, names both sides and is not under `### Fix`); BL01 (`rule_text` = line 80, worktree `toolkit_root`, plant `plant_reachable_minor_defect`: an off-by-one in a reachable list formatter; detector `blocker_flag_scoped`: COMPLIED when the finding is a `fix` without `blocker`). Per D7 both plants go in `PLANTS`, both detectors as `detect_*` functions and `grade()` branches in rule_meter.py, payload files under `rule_meter_checks/`, tests in `bin/test_rule_meter_checks_item6.py`. Run both before any edit, record the counts, run `python3 /home/brandon/agent-evals/bin/rule_trials.py build`, then delete PI01 and BL01 from scenarios.json in the same commit as the cut (their text is gone).

#### 2. coder-core pointer

**File**: `claude/.claude/skills/coder-core/SKILL.md`
**Changes**: line 43: replace "When the difference changes no acceptance criterion, the code wins: build to the code, and the plan follows it with no question to the user." with "Write the finding's `acceptance_criteria:` line as PLAN-IMPACT findings below says." and start the next sentence "When the difference changes an acceptance criterion, build only..."; keep the rest of the line; the `## PLAN-IMPACT findings` section (line 97 before Phase 6's list expansion) stays the owner.

#### 3. code-reviewer

**File**: `claude/.claude/agents/code-reviewer.md`
**Changes**: cut line 80 (the `blocker` sentence); cut line 85 from `### Ask` and add a `### Plan impact` section between `### Ask` and `### Nit`: "[`PLAN-IMPACT:` file:line — both sides — `acceptance_criteria: none` or the ids it changes — optional `kind: reword|cut|narrow`]" and "[Never auto-fixed; the loop scans the prefix. Omit when empty.]" (reviewer-calibration:78 says `ask` is not the plan-impact channel, so the line leaves Ask); keep lines 84 and 89; insert after line 13, before `## Review Process`, with no bold: "When a finding is that the code and a plan, ADR or acceptance criterion disagree, or you weigh the `blocker` flag, write it as the Disposition section of `~/.claude/skills/_shared/reviewer-calibration.md` says. Before you flag anything, confirm its premise as that file's Verify the Premise Before Flagging section says." AE, R and S text untouched.

#### 4. reviewer-calibration

**File**: `claude/.claude/skills/_shared/reviewer-calibration.md`
**Changes**: line 3 → "Shared by the specialist reviewers — `smell-reviewer` and `complexity-reviewer` adopt all four sections below; `code-reviewer` reads Disposition and Verify the Premise Before Flagging..." (rest of the line kept). After the PLAN-IMPACT bullet (about line 94) add "Add an optional `kind: reword|cut|narrow` line: `reword` only when the criterion stays and only its words change."

#### 5. Tests, anchors, change note

**Files**: `tests/scripts/test_guidance_rules.py`, `docs/rule-anchors.md`, `docs/changes/` (new note)
**Changes**: new assertions: coder-core contains `acceptance_criteria:` and "PLAN-IMPACT findings below" and lacks "the code wins"; code-reviewer contains `reviewer-calibration.md` once in the preamble and lacks "`blocker` only when shipping". Anchors: coder-core row 69 (06d5204c); code-reviewer rows 702f3c8e (preamble) and c0373f52 (Output Format); calibration rows 54 and 57. Opencode: the port code-reviewer:115 carries the same PLAN-IMPACT `[Never auto-fixed. ...]` line; move it into a `### Plan impact` section the same way, nothing else in the port changes. Change note: PI01/BL01 per-arm counts; `unmeasured` for coder-core:43 and the calibration line-3 and `kind:` additions.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the duplicate coder rule is gone — `rg -n -F 'the code wins' claude/.claude/skills/coder-core/SKILL.md`
- [ ] **Test-verified**: the coder pointer is present — `rg -n -F 'PLAN-IMPACT findings below says' claude/.claude/skills/coder-core/SKILL.md`
- [ ] **Test-verified**: the code-reviewer pointer is present — `rg -n 'disagree, or you weigh the .blocker. flag' claude/.claude/agents/code-reviewer.md`
- [ ] **Test-verified**: the `kind:` line is present — `rg -n -F 'kind: reword|cut|narrow' claude/.claude/skills/_shared/reviewer-calibration.md`
- [ ] **Test-verified**: anchors — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Test-verified**: guidance rules test — `python3 tests/parallel_tests.py test_guidance_rules.py`
- [ ] **Test-verified**: calibration refs guard test — `python3 tests/parallel_tests.py test_calibration_refs_guard.py`
- [ ] **Test-verified**: the Plan impact section is present in both trees — `rg -c '^### Plan impact$' claude/.claude/agents/code-reviewer.md opencode/.config/opencode/agents/code-reviewer.md`
- [ ] **Agent-run**: PI01 arms, before the edit — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule PI01`
- [ ] **Agent-run**: BL01 arms, before the edit — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule BL01`
- [ ] **Agent-run**: item-6 detector tests — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 -m unittest discover -s /home/brandon/agent-evals/bin -p test_rule_meter_checks_item6.py`
- [ ] **Test-verified**: PI01 and BL01 are retired — `rg -n '"(PI01|BL01)"' /home/brandon/agent-evals/bin/rule_meter_scenarios.json`
- [ ] **Agent-run**: full suite — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: an Edit of code-reviewer.md that adds the pointer line passes the `calibration_refs_guard.py` PostToolUse hook (no bold span on the line; the hook prints nothing).

---

## Phase 8: Item 7 — derivable-list rule, plant, detector and scenario

### Overview

code-reviewer flags a committed list of names another source already holds; a plant, detector and scenario prove the rule on and off.

### Changes Required:

#### 1. The rule

**File**: `claude/.claude/agents/code-reviewer.md`
**Changes**: Step 3 sub-bullet right after the item-1 bullet that ends "to be correct." (line 51 before Phase 7's preamble insert; smell-reviewer reads it too through its rg slice of `### Step 3: Structure`, name that in the change note): "   - A committed list of names that another source already holds (skills, agents, hooks, routes or table names written out by hand while their folder, registry or config sits in the tree). It drifts each time that source changes. Flag it as a `fix` that names the source to derive the values from."

#### 2. Detector and its tests

**Files**: `/home/brandon/agent-evals/bin/rule_meter_checks/flags_derivable_list.py`, `/home/brandon/agent-evals/bin/test_rule_meter_checks_derivable_list.py`
**Changes**: Two report-text graders as `detect_*` functions in rule_meter.py (the shape of `detect_names_prior_art`, not `second_owner_mutation.py`, which is a hidden-mutation subprocess): `flags_derivable_list` is COMPLIED when a Fix or Ask finding names the list, the drift and a derivation source (`skills/` or a `SKILL.md` glob), VIOLATED when there are findings but none meets it, NO_TEST when the report is empty; `quiet_on_underivable_list` (the `no_false_alarm_*` precedent) is COMPLIED when no finding names `REGIONS`, VIOLATED when one does. The test file holds four cases per detector with `addCleanup`.

#### 3. Registration (D7)

**File**: `/home/brandon/agent-evals/bin/rule_meter.py`
**Changes**: run `git -C /home/brandon/agent-evals status bin/` first and stop if any rule_meter file is dirty. Add `PLANTS["plant_derivable_skill_list"]` (base tree: `skills/a/SKILL.md`, `skills/b/SKILL.md`, `agents/x.md` and a module that reads a skill by name from a path argument; no loader globs `skills/`, so R's prior-art rule has nothing to match; HEAD adds `KNOWN_SKILLS = ["a", "b"]` in a new module that uses it), `PLANTS["plant_underivable_list"]` (same base tree without the `skills/` folder; HEAD adds `REGIONS = ["eu", "us"]` with no other source in the tree) and one `grade()` branch per detector (`flags_derivable_list`, `quiet_on_underivable_list`). Register the detector in `rule_meter_verifier.DETECTORS` and `rule_meter_fixture.DETECTORS` if the existing detectors are listed there.

#### 4. Scenario, anchors, change note

**Files**: `/home/brandon/agent-evals/bin/rule_meter_scenarios.json`, `docs/rule-anchors.md`, `docs/changes/` (new note)
**Changes**: DL01: agent `code-reviewer`, `rule_source` `agents/code-reviewer.md`, `rule_text` = the sub-bullet, `toolkit_root` this worktree, plant `plant_derivable_skill_list`, task "Review the last commit (`git show HEAD`) as you would a PR and give your report.", suffixes supportive " Check whether any value here is copied from somewhere else in the tree.", neutral "", competing " Focus on correctness bugs."; detector `flags_derivable_list`. On arm flags the seeded diff; off arm is quiet. DL02: same agent, task and suffixes with plant `plant_underivable_list` and detector `quiet_on_underivable_list`: the on arm must give no finding on a list with no other source in the tree (agent-evals-c3 ruling, 2026-11-22). Refresh code-reviewer row e3ee8a7d. Before the final commit set the `toolkit_root` of the scenarios that stay registered (ES01W, ES02W, RF01W, DL01, DL02) to `/home/brandon/dotfiles/claude/.claude` and say in the change note that they build only once master holds this branch; every other new scenario was retired after its arms ran. Commit and push the agent-evals files from this lane.

### Success Criteria

#### Automated Verification:

- [ ] **Test-verified**: the rule is present — `rg -n 'Flag it as a .fix. that names the source to derive the values from' claude/.claude/agents/code-reviewer.md`
- [ ] **Test-verified**: the rule sits in Step 3 after item 1 (presence) — `rg -n -U 'to be correct\.\n   - A committed list of names' claude/.claude/agents/code-reviewer.md`
- [ ] **Test-verified**: anchors — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Agent-run**: detector tests — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 python3 -m unittest discover -s /home/brandon/agent-evals/bin -p test_rule_meter_checks_derivable_list.py`
- [ ] **Test-verified**: DL01 builds (presence of its cells in the dry-run output) — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --dry-run --rule DL01`
- [ ] **Agent-run**: DL01 arms — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule DL01`
- [ ] **Test-verified**: DL02 builds (presence of its cells in the dry-run output) — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --dry-run --rule DL02`
- [ ] **Agent-run**: DL02 on arm is quiet — `python3 /home/brandon/agent-evals/bin/rule_meter.py run-all --rule DL02`
- [ ] **Agent-run**: full suite — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`

#### Manual Verification:

- [ ] **Manual-verified**: in the DL01 results, every on-arm cell reports COMPLIED with a finding that names `KNOWN_SKILLS`, drift and the `skills/*/SKILL.md` source; every off-arm cell reports VIOLATED or NO_TEST.

---

## Phase 9: Close pass

First, `tests/scripts/check_rule_texts_in_tree.py` (new, standard library only, under 60 lines): for each scenario in the JSON whose `rule_source` is an agent or skill file in the given toolkit root, read the file and exit 1 naming each scenario whose `rule_text` is not a verbatim substring; exit 0 otherwise. The Phase 0 dry-runs read master or other worktrees, so this is the only check of the byte-identical contract against this tree. Then `/close-branch` per `~/.claude/skills/_shared/closing-phases.md`: scripts first, then the four report-only reviewers in parallel on the whole branch diff, one `coder` that fixes every finding, the fix-diff gate, then the recap sheet. Scope box: `test -n "$(git diff --name-only <base-sha>..<head-sha>)"` with the two recorded commit ids.

### Success Criteria

#### Automated Verification:

- [ ] **Agent-run**: quality check green — `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`
- [ ] **Test-verified**: anchors — `bash claude/.claude/scripts/tools/rule-anchors.sh check`
- [ ] **Test-verified**: every live scenario whose rule_source this branch touched still holds its rule_text verbatim in the worktree — `python3 /home/brandon/dotfiles-toolkit-prose-nov22/tests/scripts/check_rule_texts_in_tree.py /home/brandon/agent-evals/bin/rule_meter_scenarios.json /home/brandon/dotfiles-toolkit-prose-nov22/claude/.claude`
- [ ] **Test-verified**: change notes validate — `python3 /home/brandon/agent-evals/bin/build_changes.py --check --root /home/brandon/dotfiles-toolkit-prose-nov22/docs/changes`

#### Manual Verification:

- [ ] **Manual-verified**: every reviewer finding fixed, shown wrong, or put to agent-evals-c3 as an ask; every acceptance criterion mapped to a test or retired; recap and smoke-test checklist delivered to agent-evals-c3 with the `unmeasured` list.

## Testing Strategy

Prompt-reading tests (`test_guidance_rules.py`, `test_spec_agent_tools.py`, `test_calibration_refs_guard.py`, `test_log_review_finding.py`, `test_adr_flow.py`) pin the strings other code reads; `test_spec_budget_gate.py` pins the gate tuple; the detector unittest pins the item-7 grader; rule-meter arms measure each cut, reword or new rule where an agent scenario can carry it; `rule-anchors.sh check` and `bash tests/run.sh` close every phase.

## References

- ./00-ticket.md, ./01-questions.md, ./02-research.md, ./03-decisions.md
- /tmp/claude-1000/-home-brandon-agent-evals/a0b58526-6a4a-4e0a-af5b-8d0985572fda/scratchpad/lane-common.md and brief-toolkit-prose.md
