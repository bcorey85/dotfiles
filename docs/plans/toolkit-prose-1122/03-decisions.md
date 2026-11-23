# Design Decisions — toolkit-prose-1122

> Research: ./02-research.md
> Status: 14/14 resolved
>
> Criteria sign-off (agent-evals-c3, 2026-11-22): AC1-AC10 signed off. AC4 reworded to "frontmatter plus at most four behavior-changing lines" (owner: session, item is session-written). AC5 read with plan-reading.md excluded; a script or gate that reads or cites a _shared file counts as a loader, so code-vocabulary stays. AC7 gains the negative case (DL02). Change notes go in the worktree's docs/changes. The stale RF01/RF03/RF05 and L scenarios are out of scope and go in the final report as broken.
>
> Plan-review rulings (agent-evals-c3, 2026-11-22): D7 extended to every plant and detector this lane adds (DL01, DL02, PI01, BL01), all in rule_meter.py with payloads in rule_meter_checks/ and tests in bin/. A scenario whose rule_text this branch deletes (GP01, GP02, RF01B, PI01, BL01) runs both arms before the cut with the worktree root, has its counts recorded in the change note and `rule_trials.py build`, then is deleted in the same commit. PF01W/PF02W dropped; plan-format splits unmeasured. skimmable-writing folds into `_shared/adr-template.md`; AC5 is read over the ticket's three named files; adr-template gets a follow-up queue item. code-reviewer gets a `### Plan impact` output section (lane decision).

## Queue

- [x] D1. Owner of the `acceptance_criteria: none` PLAN-IMPACT rule (coder-core:97, code-reviewer:85, reviewer-calibration:92-94) — from backend-architect
- [x] D2. Which single-loader `_shared` files fold, and where — from backend-architect
- [x] D3. code-reviewer gets a reviewer-calibration pointer — from backend-architect
- [x] D4. What general-purpose's body becomes — from backend-architect
- [x] D5. Form of the item-7 rule, its meter scenario and detector — from backend-architect
- [x] D6. Phase order — from backend-architect
- [x] Q1. Item 6 premise: the ticket describes the no-file rule; the duplicated sentence is the PLAN-IMPACT rule — from backend-architect
- [x] Q2. verify-branch:44 "It is the only run site." contradicts close-branch:36; fix in item 1 or file a follow-up — from backend-architect
- [x] Q4. finding-log fold: drop its three anchor rows, or anchor every block of test-audit — from backend-architect
- [x] Q5. smell-reviewer's rg slice of code-reviewer Step 3: extract to a `_shared` file, a preloaded skill, or keep the slice — from backend-architect
- [x] Q6. Ticket says four single-loader files; three qualify — from backend-architect
- [x] Q7. Meter scenario for general-purpose, or `unmeasured` — from backend-architect (folded into D4)
- [x] Q8. Rules in `_shared` files, architects and general-purpose cannot be graded by an agent scenario — from backend-architect

## Recommendations (sent to agent-evals-c3 2026-11-22; ruled the same day, see Resolved)

🔷 **D1. Owner of the `acceptance_criteria: none` rule**
- ➡ Rec: coder-core:97 owns the coder side (how to write the line). reviewer-calibration Disposition (92-94) owns the reviewer side. Cut code-reviewer:85; code-reviewer reaches the reviewer side through the D3 pointer. Trim coder-core:43's restatement to a same-file pointer. plan-format:85 (no criteria file when the ticket has no behavioral criteria) is a different rule and stays.
- Other options: keep code-reviewer:85 and cut the calibration copy (meterable, but smell- and complexity-reviewer lose it); keep all three reworded alike (still a duplicate).
- Why: one owner per side matches the opencode code-reviewer port, which already points at calibration and lacks line 85. Meter: coder-core:97 gets a coder scenario if a detector can read the PLAN-IMPACT line; the calibration copy is `unmeasured`.

---

🔷 **D4. general-purpose body**
- ➡ Rec: keep the lines that change behavior and nothing else: report what you verified and what you did not; absolute paths; edit before create; no documentation files unless asked. About four lines. Port the same cut to the opencode file, frontmatter kept.
- Other options: empty body (the custom agent then runs with no prompt, since it replaces the built-in one and does not fall back); delete the file (loses `model: sonnet` and the Explore routing in the description).
- ⚠ Why: the Done-when says "empty or one line". Four short lines read better than one dense line with four conditions; this is a cut of an AC's wording, so it needs your yes. Meter: no scenario exists; building one needs a plant and a detector for "reports what was not verified". Rec: list as `unmeasured`.

---

🔷 **D5. Item-7 rule form**
- ➡ Rec: one sub-bullet in code-reviewer Step 3 under the shared-decision bullet (line 51): a committed list that copies a set another source already holds (skill, agent or hook names, a directory listing, registry members) is flagged with the source to derive it from. Fix, not taste. smell-reviewer inherits it through its rg slice. Scenario: new plant with a module holding a hard-coded skill/agent name list beside a `skills/` and `agents/` tree; task and suffixes as R and S; detector `flags_derivable_list.py` passes when the reply names the drift and the source.
- Other options: a toolkit-only rule (skill and agent names only); a rule in complexity-reviewer:25's "values with more than one owner".
- Why: the general form catches the registry and enum copies the same incident describes; the toolkit names are the first example. ⚠ The ticket names only toolkit lists; widening the form is your call.

---

❓ **Q2. verify-branch:44 "It is the only run site."**
- ➡ Rec: fix in item 1 (one line: close-branch also dispatches plan-verifier) since it is the same class of contradiction item 1 covers.
- Other option: file a follow-up item.
- ⚠ Why: verify-branch is not in item 1's component list; scope growth of one line.

---

❓ **Q4. finding-log fold and its anchor rows**
- ➡ Rec: drop the three finding-log rows (179, 180, 182). test-audit has no rows today, and the anchor check requires every block of a named file to have a row.
- Other option: anchor every block of test-audit.
- ⚠ Why: anchoring all of test-audit is scope growth the ticket did not ask for. Your call since rows are cut.

---

❓ **Q5. Structure rules shared by code-reviewer and smell-reviewer**
- ➡ Rec: keep the rg slice of the stable `### Step 3: Structure` heading. Do not extract.
- Other options: a `_shared` structure-rules file (breaks live meter scenarios R, S and AE, whose `rule_source` must be the agent or a listed skill, and smell-reviewer meter runs lose the rules); a new skill preloaded by both via `skills:` with R, S and AE re-pointed in agent-evals.
- ⚠ Why: item 5's context asks for the extraction; dropping it is a cut of ticket text, so it needs your yes.


## Resolved

### D1. Owner of the `acceptance_criteria: none` rule

- Decision: coder-core:97 owns the coder side; reviewer-calibration Disposition (92-94) owns the reviewer side. Cut code-reviewer:85; code-reviewer reaches the reviewer side through the D3 pointer. Trim coder-core:43's restatement to a same-file pointer. plan-format:85 stays.
- Reasoning: one owner per side; matches the opencode code-reviewer port. Approved by agent-evals-c3, 2026-11-22, as recommended.
- Alternatives: keep code-reviewer:85 and cut the calibration copy; keep all three reworded alike.
- Consequences: coder-core:97 metered through a coder scenario where a detector can read the PLAN-IMPACT line; the calibration copy is `unmeasured`.

### D4. general-purpose body

- Decision: about four lines: report what you verified and what you did not; absolute paths; edit before create; no documentation files unless asked. Same cut in the opencode port, frontmatter kept. Meter: add one scenario that dispatches general-purpose on a small edit-and-test task, on and off arms. Only if no fixture shows the behavior does the rule go in `unmeasured`, and then it goes to agent-evals-c3 in the final report before the merge.
- Reasoning: an empty body leaves the custom agent with no prompt. Approved by agent-evals-c3, 2026-11-22, with the meter condition above; the Done-when's "empty or one line" is reworded to "about four lines" by that ruling (owner: session).
- Alternatives: empty body; delete the file; frontmatter only.
- Consequences: new general-purpose scenario and detector in ~/agent-evals/bin.

### D5. Item-7 rule form

- Decision: one sub-bullet in code-reviewer Step 3 under the shared-decision bullet: a committed list that copies a set another source already holds (skill, agent or hook names, a directory listing, registry members) is flagged with the source to derive it from; fix, not taste. New plant with a hard-coded skill/agent name list beside `skills/` and `agents/` trees; task and suffixes as R and S; detector `flags_derivable_list.py`. The on arm must flag the ticket's seeded toolkit-name diff; the off arm must stay quiet. A second scenario (DL02) seeds a list with no other source in the tree: the on arm must give no finding.
- Reasoning: the general form catches registry and enum copies too. Approved by agent-evals-c3, 2026-11-22, with the arm condition; the negative case added by agent-evals-c3's criteria ruling, 2026-11-22 (a rule that flags every list is a false-alarm generator).
- Alternatives: toolkit-only rule; a complexity-reviewer rule.
- Consequences: Step 3 anchor row refreshed; smell-reviewer inherits through its rg slice.

### Q2. verify-branch:44 "It is the only run site."

- Decision: fix in item 1: say close-branch also dispatches plan-verifier. Approved by agent-evals-c3, 2026-11-22.
- Consequences: verify-branch/SKILL.md joins item 1's files.

### Q4. finding-log anchor rows

- Decision: drop the three finding-log rows when the file folds into test-audit. Approved by agent-evals-c3, 2026-11-22.
- Alternatives: anchor every block of test-audit.

### Q5. Structure rules shared by code-reviewer and smell-reviewer

- Decision: keep smell-reviewer's rg slice of the stable `### Step 3: Structure` heading; no extraction. Approved by agent-evals-c3, 2026-11-22 (drops item 5's extraction bullet; owner: session).
- Alternatives: a `_shared` structure-rules file (breaks meter scenarios R, S, AE); a preloaded skill.

### D2. Which single-loader `_shared` files fold, and where

- Decision: three folds. design-decision-format.md → eng-spec/phases/5-decisions.md step 13 (delete the file; remove it from spec_budget_gate.py SHARED_FILES and test_spec_budget_gate.py:149 in the same phase; tighten the text while folding, since the Edit-time delta is +342 words against 337 of spec-budget headroom; cut plan-format first to free room). finding-log.md → test-audit/SKILL.md (drop lines 40-43, which reach no loader; retarget test_log_review_finding.py FINDING_LOG_RULE, keeping the single `'file=<path>'` form). skimmable-writing.md → adr-template.md (merge the overlap at adr-template:42-43; the pointer at :40 goes). code-vocabulary.md does not fold: two gates print its path in deny messages and a test asserts that text; fix its false consumer list instead. plan-reading.md deferred.
- Reasoning: single loader is the test the ticket sets; the research (Q1) finds exactly these three. Ruling of agent-evals-c3, 2026-11-22: plan-reading.md is off limits (code-skill lane).
- Alternatives: fold code-vocabulary (breaks gates and test_stale_citation_gate); keep the files with stronger pointers (leaves the single-loader read on every dispatch).
- Consequences: three fewer `_shared` files; gate and test edits in the same phase; anchor rows for finding-log handled per Q4.

### D3. code-reviewer gets a reviewer-calibration pointer

- Decision: yes, one line naming the trigger and the sections by plain heading text (Disposition, Verify the Premise), no bold except real headings, so calibration_refs_guard passes. Then cut the code-reviewer lines the pointer covers (line 85 and any blocker or plan-routing restatement), each metered off through R, S, AE or a new scenario.
- Reasoning: precondition for D1's recommendation; matches the opencode port; claude-doctor needs at least one reviewer agent to cite the file, and smell/complexity already do.
- Alternatives: no pointer (code-reviewer keeps restating calibration text).
- Consequences: one more read per code-reviewer dispatch; shorter code-reviewer body.

### D6. Phase order

- Decision: (1) plan-format tightening, then the design-decision-format fold with gate and test edits; (2) item 1 contradictions and descriptions plus opencode ports; (3) item 3 architects (descriptions, Reuse Map dedupe, 4-explore prompt dedupe, ports' false "preloaded"); (4) item 4 general-purpose plus port; (5) item 5 folds, pointer fixes, consumer lists, cull-rule dedupe with test_guidance_rules updates; (6) item 2 remainder: review-fork-run restructure (keep the three asserted strings), coder-core paragraphs (keep asserted strings; sync meter rule_text G, H, K2, AB, AC, AD, I, J), reviewer-calibration blocker dedupe, eng-spec agents; (7) item 6 AC dedupe plus D3 pointer; (8) item 7 rule, plant, detector, tests, scenario. After every phase: `rule-anchors.sh check` and row updates, meter rule_text sync, `bash tests/run.sh`.
- Reasoning: spec-budget headroom (6 resident, 337 total) forces the plan-format cut before the fold; item 7 last because it edits Step 3, which other phases also touch.
- Alternatives: ticket order (fold first would be denied by the gate).
- Consequences: eight phases; full test runs every phase since docs/ and tests/ change.

### Q1. Item 6 premise

- Decision: the rule to dedupe is the PLAN-IMPACT `acceptance_criteria: none` rule (the line the coder writes when a change touches no AC), which has three copies: coder-core:97, code-reviewer:85, reviewer-calibration:92-94. The ticket's Context sentence describing it as "no acceptance-criteria file" is a misdescription; that rule lives once at plan-format.md:85 and is untouched.
- Reasoning: research is ground truth; the ticket's own source and component lines point at the PLAN-IMPACT copies. Corrected premise recorded here.
- Alternatives: treat plan-format:85 as the target (it has no duplicate, so the item would be a no-op).
- Consequences: none for scope.

### Q6. "Four" single-loader files

- Decision: the four are skimmable-writing, design-decision-format, finding-log and plan-reading. Three fold here; plan-reading is deferred by ruling (agent-evals-c3, 2026-11-22) and gets a follow-up queue item.
- Reasoning: code-vocabulary and adr-template fail the single-loader test (gates cite one; a script loads the other).

### Q7. general-purpose meter

- Decision: folded into D4.

### Q8. Rules the meter cannot grade

- Decision: a rule in a `_shared` file, an architect or general-purpose that no agent scenario can copy goes in the change file's `unmeasured` and is reported to agent-evals-c3 in the final report, which rules on it. Ruling of agent-evals-c3, 2026-11-22.

### D7. rule_meter.py registration for the item-7 plant and detector (architect DESIGN GAP 1)

- Decision: Option A. Add the `PLANTS["plant_derivable_skill_list"]` entry and one `grade()` branch in `~/agent-evals/bin/rule_meter.py` for the new detector. Ruling of agent-evals-c3, 2026-11-22, with three conditions: run `git -C ~/agent-evals status bin/` right before each rule_meter edit and stop if a rule_meter file is dirty; commit and push those agent-evals files from this lane; run the arms with `toolkit_root` at this worktree, then before the final commit set every new scenario's `toolkit_root` to `/home/brandon/dotfiles/claude/.claude` and say in the change file that a rerun before the merge reads master's text.
- Reasoning: the detector cannot grade without a plant and a `grade()` branch; the lane-common "rule_meter.py stays untouched" line yields to the ruling for these registration lines only.
- Alternatives rejected: a scenario with no plant (the detector would grade an empty diff: NO_TEST every run); skip the meter for item 7 (the brief requires on and off arms for the new rule).
- Trade-off accepted: two edits to a shared script another lane may also touch; the status check before each edit covers it.
- The architect's other gap, PF01/PF02 absence, was a miss: both scenarios exist with other worktrees as `toolkit_root`. The plan dry-runs both and treats a failed `rule_text` resolution as `unmeasured`; no ruling needed.

## Direction & Constraints

- Item 8 stays with bcpc-arch: note it in the queue item outcome and skip it (agent-evals-c3, 2026-11-22).
- Item 6 queue file: fix its Context text to describe the PLAN-IMPACT rule (session-written item; agent-evals-c3, 2026-11-22).

- Item 8 (retire-branch-recap) is out of this lane: claimed by bcpc-arch. Do not touch branch-recap references in todos:3, test-audit:3, code-vocabulary:44.
- Off limits: `skills/_shared/plan-reading.md`, everything under `skills/code/`, any CLAUDE.md, settings.json, orchestration.md, `bin/rule_meter.py`.
- Spec budget: 6 words resident headroom (SKILL.md + 6-finalize), 337 total. 6-finalize must not grow.
- Test-asserted strings to keep (test_guidance_rules.py: review-fork-run three strings, coder-core three strings, spec-criteria strings, test-intent-reviewer and test-reviewer cull lines; test_log_review_finding.py file= form; test_spec_agent_tools.py exclude glob; test_adr_flow.py adr-template path; test_stale_citation_gate.py code-vocabulary path).
- Headings read by code: reviewer-calibration `##` headings (Calibration Anchor, Verify the Premise, Disposition, Self-Check); code-reviewer `### Step 3: Structure`.
- Opencode ports: patch where the item names them; keep their adaptations (AGENTS.md, frontmatter, "First action: Read"); fix the false "preloaded via architect-core" in both architect ports; do not copy claude text over existing port drift.
- No rationale in agent or skill bodies. Toolkit-edit propagation sweep before done.

- Phase 1 rulings (agent-evals-c3, 2026-11-22; owner `session`):
  - (1) The `design-decision-format` ban search in Phase 1 drops `tests` from its paths; tests/scripts/test_spec_budget_gate.py:160 stays as the guard.
  - (2) The Phase 1 change note is kind `structured`: ES01W and ES02W run at 8 runs per arm on the default model, and a finding with task_class structured and runs_per_arm 8 is its proof.
  - (3) "Scope is the ticket-owner's call" leaves the note's dropped-clauses list (the sentence stays at 5-decisions.md:102): five clauses are dropped, not six.
  - (4) The removal of `_shared/design-decision-format.md` is staged with `git add`.

- Phase 2 ruling (agent-evals-c3, 2026-11-22; owner `session`): Q2 verify-branch:44 ruling changed to drop. "It is the only run site." is removed with nothing added in its place; the /close-branch pointer sentence is not added.
- Phase 2 ruling (agent-evals-c3, 2026-11-22; owner `session`): the Phase 2 change note stays kind `fix`; its `test` field names a prompt-reading test under tests/scripts (`tests/scripts/test_toolkit_prose_facts.py`) that pins facts (the false run-site sentence absent; orient and todos lines each state one fact; plan-verifier and test-intent-reviewer descriptions name close-branch; opencode test-intent-reviewer names test-audit only).
- Phase 3 ruling (agent-evals-c3, 2026-11-22; owner `session`; Phase 2 precedent for unmeasured prose fixes): the Phase 3 change note is kind `fix` with the unmeasured text kept; its `test` field names a prompt-reading test in `tests/scripts/test_toolkit_prose_facts.py` that pins facts (architect descriptions are one sentence naming /eng-spec phase 4; architect-core holds the Reuse Map rules and the exploration brief and neither architect body repeats them; the phase 4 prompt points at architect-core; each opencode architect port has a First-action line that loads architect-core).
- Phase 7 rulings (agent-evals-c3, 2026-11-22; owner `session`):
  - (1) `parse_review_texts` in `review/review_loop_findings.py` reads a `### Plan impact` section and takes its lines in as asks, like the Ask section's; a test under `tests/scripts/test_review_loop_findings.py` pins it. The script change is outside Phase 7's file list and is covered by this ruling.
  - (2) The two heading names in the code-reviewer pointer paragraph are bold so the calibration-refs guard reads them; the plan's "no bold" wording is overridden (logged under Plan Deviations).
  - (3) PI01's detector loosens to "PLAN-IMPACT: prefix present" and the arms already run are re-graded with no live rerun; the change file's Result holds both readings (strict 0/3 vs 0/3, prefix 3/3 vs 0/3). BL01 at 3/3 vs 3/3 is ALREADY: its rule line ships with the counts if it is a user rule, otherwise the line is dropped and logged ALREADY in rule_trials.
  - (4) PI01 and BL01 `toolkit_root` point at `/home/brandon/dotfiles/claude/.claude` (or the scenarios are marked retired); AE and AF join the expected plant table; the item-6 check string that dropped a space after "date;" is fixed.
  - Phase 7 ruling (agent-evals-c3, 2026-11-22; owner `session`): the Phase 7 success criterion that expected no PI01/BL01 match in rule_meter_scenarios.json accepts them marked retired (repoint to the live toolkit or mark retired); no acceptance criterion in acceptance-criteria.md changes.
  - (5) The duplicated sentence at reviewer-calibration.md line 3 is cut, and the rule-anchors row for the plan-versus-code check no longer says the coder owes a `SET BY` report line.
- Phase 8 ruling (agent-evals-c3, 2026-11-23; owner `session`; a paraphrase, not the user's words): the reviewer flags a hand-kept list without the rule in 2 of 3 framings (DL01 off arm: supportive and competing flag, neutral quiet; on arm 3 of 3), so the derivable-list rule is ALREADY and is dropped from code-reviewer. Covers Phase 8 and every acceptance criterion that names the derivable-list rule text. DL01 and DL02 stay registered as ALREADY.
