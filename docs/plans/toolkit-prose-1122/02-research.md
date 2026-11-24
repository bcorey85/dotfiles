---
date: 2026-11-22
git_commit: 9a1bef2c58d3ddb713cc4cf7caf581dfeed95794
branch: fix/toolkit-prose-nov22
topic: Toolkit prompt files (shared references, agents, core skills, eng-spec phases, vault skills, opencode ports), anchors, rule meter and prompt-reading tests
tags: [claude-toolkit, agents, skills, _shared, rule-anchors, rule-meter, opencode, tests]
status: complete
---

# Research: Toolkit prompt files, their loaders, anchors, ports, meter and tests

All paths are relative to the repo root unless they start with `~`. `C` = `claude/.claude`, `O` = `opencode/.config/opencode`. Hidden directories need `rg --hidden`.

## Findings

### Q1. `_shared/` files and their loaders

Fifteen files exist in `C/skills/_shared/`: `adr-template.md`, `closing-phases.md`, `code-vocabulary.md`, `design-decision-format.md`, `escape-ratchet.md`, `finding-log.md`, `handoff-block.md`, `jira-ticket.md`, `modifiers.md`, `nvim-jump.md`, `plan-format.md`, `plan-reading.md`, `review-fork-run.md`, `reviewer-calibration.md`, `skimmable-writing.md`.

Each file below lists its pointers with the pointer's own words.

- `review-fork-run.md` (19 lines)
  - `C/skills/review/SKILL.md:14` and `C/skills/fix/SKILL.md:14`: "Read `~/.claude/skills/_shared/review-fork-run.md` whole first and follow it. **End the run only at a STOP or at the end of the run.**"
  - `tests/scripts/test_guidance_rules.py:179` reads it as text.
- `handoff-block.md`
  - `C/skills/review/SKILL.md:23` and `C/skills/fix/SKILL.md:24`: "a `handoff:` block (schema: `~/.claude/skills/_shared/handoff-block.md`)".
  - `C/skills/code/SKILL.md:85`: "first build the handoff block per `~/.claude/skills/_shared/handoff-block.md`".
  - `docs/glossary.md:281` names it.
- `reviewer-calibration.md`
  - `C/agents/smell-reviewer.md:15` and `C/agents/complexity-reviewer.md:13`: "First action: Read `~/.claude/skills/_shared/reviewer-calibration.md` and adopt its **Calibration Anchor**, **Verify the Premise Before Flagging**, **Disposition**, and **Self-Check Before Reporting**."
  - The opencode ports `O/agents/code-reviewer.md:19`, `complexity-reviewer.md:15` and `smell-reviewer.md:17` carry the same pointer.
  - `C/agents/code-reviewer.md` has no pointer to it (no `reviewer-calibration` match in the file).
  - `C/scripts/gates/calibration_refs_guard.py` (PostToolUse hook, registered at `C/settings.json:269`) checks that each bold heading named on a line mentioning the file exists as a `##` heading in it.
  - Its own line 3 says the four `##` headings are "referenced BY NAME from every adopting agent (and their opencode ports)".
- `plan-format.md` (151 lines)
  - Pointers: `C/skills/eng-spec/templates/spec-template.md:8` ("from `plan-format.md`, which otherwise applies in full") and `:67`; `C/skills/eng-spec/phases/6-finalize.md:41`; `C/scripts/gates/spec_budget_gate.py:22`.
  - `C/skills/code/SKILL.md` has no pointer to it. `C/agents/plan-verifier.md:23` and `:33` point to `plan-reading.md`.
  - It points back to `closing-phases.md` (`plan-format.md:37`, `:92`).
- `closing-phases.md` (23 lines)
  - `C/skills/code/SKILL.md:47`: "A closing phase (`~/.claude/skills/_shared/closing-phases.md`) runs its named skill in place of steps 3 to 5: invoke that skill with the Skill tool. For the Refactor pass, run the concentration gate first, as `closing-phases.md` says."
  - Also named by `spec-template.md:33`, `:67`, `plan-format.md:37`, and `spec_budget_gate.py:22`.
- `plan-reading.md`: `C/skills/code/SKILL.md:40` ("Read it phase-scoped per ..."); `C/agents/plan-verifier.md:23`, `:33`.
- `design-decision-format.md`: `C/skills/eng-spec/phases/5-decisions.md:41` ("format: ..."); `C/scripts/gates/spec_budget_gate.py:22`.
- `escape-ratchet.md`: pointers in `C/skills/{cc:78,close-branch:68,commit:36,escape:24,fix:38,pr-comments:58,refactor:40,verify-branch:63}/SKILL.md` and `C/skills/eng-spec/phases/6b-review.md:50` ("`guard=` is the rung from ..."). Also `C/scripts/telemetry/log-escape:70,77,173,194`, `C/scripts/review/verify-log:459,475`, `C/skills/refactor/scripts/refactor_flow.py:670`.
  - `C/skills/fix/SKILL.md:38`: "Pick `guard` from `~/.claude/skills/_shared/escape-ratchet.md` without pausing."
- `finding-log.md`: `C/skills/test-audit/SKILL.md:42` ("per-finding rows per ... (read it)"); `tests/scripts/test_log_review_finding.py:23`.
- `jira-ticket.md`
  - `C/skills/pull-ticket/SKILL.md:13`: "**Resolve plus fetch** per ... (read it) — **required-ticket caller**: no key means ask; no MCP means stop."
  - `C/skills/peer-review/SKILL.md:56`: "**optional-ticket caller**: key from head branch, then title, then body; no key/MCP → note 'reviewing without ticket context' and continue."
  - `C/skills/verify-branch/SKILL.md:15` and `:28`; `C/skills/eng-spec/phases/1-ticket.md:5` ("fetch it yourself per ...").
  - `C/scripts/review/verify-prep:147`; `C/skills/adr/scripts/adr_flow.py:50` (comment).
- `modifiers.md`: `C/skills/code/SKILL.md:16` ("`+fast` per ... (read it when present)"); `C/skills/cc/SKILL.md:13` ("pass through to `/fix` unchanged"); `C/skills/refactor/SKILL.md:20` ("read it when either is present").
- `nvim-jump.md`: `C/skills/drive/SKILL.md:29`, `eng-spec/phases/2-research.md:32`, `peer-review/SKILL.md:159`, `stage/SKILL.md:30`, `verify-branch/SKILL.md:66`, `walk/SKILL.md:25`.
- `code-vocabulary.md`
  - `C/agents/spec-criteria.md:58` ("never ids/paths into `tests/` or `src` (`_shared/code-vocabulary.md`)").
  - `O/agents/code-reviewer.md:57`, `O/agents/spec-criteria.md:52`.
  - `C/scripts/gates/comment_bloat_gate.py:4`, `:227`; `C/scripts/gates/stale_citation_gate.py:156`.
- `adr-template.md`: `C/skills/adr/scripts/adr_flow.py:44`; `tests/scripts/test_adr_flow.py:21,37`.
- `skimmable-writing.md`: only `C/skills/_shared/adr-template.md:40` ("Apply `~/.claude/skills/_shared/skimmable-writing.md` in full, plus:").

`C/scripts/gates/spec_budget_gate.py:22` is `SHARED_FILES = ("design-decision-format.md", "plan-format.md", "closing-phases.md")`; `tests/scripts/test_spec_budget_gate.py:136-172` exercises it.

### Q2. Agent file structure and dispatch text

All 18 files in `C/agents/` open with `---` frontmatter and a free-text body. Fields used:

- `name`, `description`, `model` in every file.
- `tools` in all but `code-fork` and `general-purpose`.
- `color` in all but `code-fork`, `general-purpose`.
- `skills:` in `coder`, `backend-architect`, `frontend-architect`.
- `maxTurns` in `spec-leak-check` (10), `spec-questions` (25), `spec-research` (80).
- `disallowedTools: Edit, NotebookEdit` only in `code-fork` (`C/agents/code-fork.md:5`).
- Descriptions are one line in quotes (except `general-purpose`, unquoted) and most end in a "Dispatched by ..." sentence.

Descriptions named in the question:

- `test-intent-reviewer` (`C/agents/test-intent-reviewer.md:3`): "Audits whether changed tests pin intent or implementation. Dispatched by /test-audit or directly; name `scope: cull` or `scope: bug-pinning`."
- `plan-verifier` (`C/agents/plan-verifier.md:3`): "Checks each plan criterion against the branch diff: done, partial or missing, with evidence. Dispatched by /verify-branch at branch end."
- `backend-architect` (`:3`): "Design and plan backend features — data models, API contracts, database schemas, service architecture. Produces implementation plans for the coder. Looking like pure configuration (adding an env var, enabling a flag) is necessary but not sufficient to skip this agent — the whole skip test is the go-lean gate in the eng-spec skill's scope phase, and every condition in it must hold. Never skipped for endpoints, services, or anything involving data flow."
- `frontend-architect` (`:3`): same structure, "(adding an import, toggling a flag)" and "Never skipped for new components, state changes, or API integration."
- `general-purpose` (`C/agents/general-purpose.md:3`): "General-purpose agent for multi-step tasks that edit files, run a build or test, or judge a design. For read-only searches and lookups, use Explore." It names no dispatcher.

Actual dispatchers found in `C/skills`, `C/scripts`, `C/README.md`, `C/orchestration.md` (no `C/commands` directory exists):

- `test-intent-reviewer`: `C/skills/test-audit/SKILL.md:15` ("Dispatch `test-intent-reviewer` (pinned; omit `model`) — **cull + weak scope**"); `C/skills/close-branch/SKILL.md:35` (item 3, `scope: cull`); `C/README.md:104` (phase gates, "when tests changed").
- `plan-verifier`: `C/skills/verify-branch/SKILL.md:44` ("It is the only run site."); `C/skills/close-branch/SKILL.md:36` (item 4, "the payload verify-prep printed, exactly"); `C/scripts/review/verify-prep:331` prints `STEP ...: dispatch Agent subagent_type=plan-verifier (omit model)`.
- `backend-architect` / `frontend-architect`: `C/skills/eng-spec/phases/4-explore.md:3-4`; `phases/6-finalize.md:3,9,11`. `C/README.md:87`.
- `general-purpose`: no skill dispatches it by name. `C/orchestration.md:6` ("Send a read-only lookup ... to `Explore` with `model: "haiku"`, not to `general-purpose`. Use `general-purpose` only when the agent must ..."). `C/scripts/telemetry/log_agent_usage.py:94` uses it as the default `subagent_type` when none is given.
- Other agents' dispatcher text: `code-fork` "Started only by those skills; never dispatch it" (`C/agents/code-fork.md:3`); `goal-blind-researcher` by /eng-spec; `spec-leak-check` by goal-blind-researcher; `spec-research` by goal-blind-researcher.

### Q3. The `acceptance_criteria none` condition

- `C/skills/coder-core/SKILL.md:81-99`: `## PLAN-IMPACT findings (structured, never prose)` holds a block with lines `assumed`, `found`, `changes`, `acceptance_criteria: <none, or the criteria this changes>` (line 90), `cause: <plan, or toolkit>`, `kind: <optional: reword, cut, or narrow>`.
  - Line 97: "Write `acceptance_criteria: none` only when every acceptance criterion holds either way. Then the plan change is adopted and logged under Plan Deviations without asking the user. Any other value asks the user."
  - Line 94: "Add `kind: reword` only when the change keeps the criterion and changes only its words. Write `cut` or `narrow` otherwise, or leave the line out."
  - Line 99: `cause: toolkit` stops the run for the main session.
- `C/agents/code-reviewer.md:85` (`### Ask` template): "When the code and the plan or ticket disagree and the plan is the side in doubt, open the line with `PLAN-IMPACT:`, name both sides, and end it with `acceptance_criteria: none` when every acceptance criterion holds either way, else `acceptance_criteria: <the criteria it changes>`. Add an optional `kind: reword|cut|narrow` line: `reword` only when the criterion stays and only its words change."
- `C/skills/_shared/plan-format.md`: no `acceptance_criteria` string. Its `## Acceptance Criteria` section (`:83-94`) says "Omit when the ticket has no behavioral criteria" (`:85`) and names `docs/plans/<slug>/acceptance-criteria.md` (`:87`, `:89`).
- `C/skills/_shared/closing-phases.md:9` says "(an ask that changes a ticket AC) put to the user".
- Scripts:
  - `C/scripts/lib/plan_format.py:72` `AC_CHANGE_LINE = re.compile(r"acceptance[_ ]criteria[*`_]*:[ \t*`_]*([^;\n]*)", re.I)`; `:87` `AC_CHANGE_CLAUSE`.
  - `plan_format.py:782` `changes_acceptance_criteria(impact)`: False only when each PLAN-IMPACT answers `none`; a PLAN-IMPACT with no such line counts as an AC change.
  - `plan_format.py:791` `criteria_ids(text, answers_only=False)`; `:805` `plan_impact_cause(block, missing=PLAN_CAUSE)`; `:76` `PLAN_IMPACT_CAUSE`; `:80` `PLAN_IMPACT_CAUSES`; `:871` `PLAN_IMPACT_OPTIONS = ["Adopt plan change", "Keep plan as written", "Discuss"]`.
  - Callers of `changes_acceptance_criteria`: `C/scripts/review/review_loop_ruled.py:317`, `:358`.
  - `C/scripts/review/review_loop_findings.py:429-475` reads `acceptance_criteria:` lines for ids.
  - `C/scripts/review/review_fix_asks.py:257,271,277,382` writes ` acceptance_criteria: <ids>` onto an ask.
  - `C/scripts/lib/standing_rulings.py:68` (a standing ruling covers a reword impact naming a criterion id).
  - `C/scripts/code/coder_report.py:35` `PLAN_IMPACT_KEY` regex lists the keys `assumed|found|changes|acceptance_criteria|cause` (no `kind`).
  - `C/scripts/code/plan_check.py:48` calls `standing_rulings.reword_ruling`.
  - `review_fix_plan_impacts.py:201-233` handles reword impacts.

### Q4. Layout of the core skills and reviewer agents

- `C/skills/coder-core/SKILL.md` (111 lines), `##` sections in order: Readability comes first (10), You are the terminal implementer (22), Shell commands the hooks block (26), Read the plan phase-scoped (37), Check the plan against the code it names (41), Copy import paths, never guess them (45), Extend, never copy (49), Async actions in a view (53), Fixing a review finding (57), Tests are yours (63), Verify before you report (75), PLAN-IMPACT findings (81), Review handoff (101).
  - Line 8: "You implement the plan; you make no architectural decisions."
  - Line 67 (under `## Tests are yours`) holds the cull rule: "Before you write a test, search the suite for tests that call the same function, at every layer. Before you keep a test, name the bug that it alone would catch."
  - Line 71 reads the acceptance criteria as spec.
  - Line 111: `RECOMMEND: eng-spec`.
- `C/skills/architect-core/SKILL.md` (48 lines): Research Context (12), Two-Stage Dispatches (16), Placement (24), Output Format (28), Out of Scope (37), Refactor Candidates (41), Success Criteria (45).
  - `C/agents/backend-architect.md` and `frontend-architect.md` preload it through `skills:`; their bodies say (`O` copies line 11) "adopt them in full. Everything below is ... specific and layers on top".
- `C/agents/code-reviewer.md` (97 lines): preamble (lines 1-13: "You own every lens on the diff: correctness, security, query and I/O cost, prose claims (Step 2), and structure (Step 3). Leave low-value-test culling to the branch-exit test audit."); `## Review Process` (15) with `### Step 1: Determine Scope` (17), `### Step 2: Read the Changes` (31), `### Step 3: Structure` (43-64, six numbered lenses: Duplication in three forms, Layer placement, Naming, Dead weight, Cohesion, Helper placement); `## Output Format` (66) with Prior Issues Verified (74), Fix (77), Ask (82), Nit (87); `## Reviewer-Specific Tool Use` (94).
- `C/agents/smell-reviewer.md` (52 lines): `## Inherit the calibration verbatim` (13; line 15 reads `reviewer-calibration.md`), `## Your scope — the structure rules, ONLY inside your dispatched bound` (17), `## Explicitly NOT your scope` (23; line 29 "Narration comments — `code-reviewer`; test fluff — `test-intent-reviewer`'s cull."), `## Output Format` (33) with Fix, Ask, Nit.
  - Line 19: "Second action: find the `### Step 3: Structure` heading in `~/.claude/agents/code-reviewer.md` (`rg -n '^### Step 3: Structure' ...`)".
- `C/agents/test-reviewer.md` (92 lines): `## Calibration — restraint over thoroughness` (17), `## Target Scope` (21), `## Review Process` (31) with Steps 1, 2, 3, 3b, 3c, 4, 5; `## Output Format` (47) with eight `###` report sections. Step 5 (line 45): "Cull check — branch scope ONLY ... **name a concrete bug this test — and no sibling — would catch.**"
- `C/agents/test-intent-reviewer.md` (104 lines): Steps 1-5 (15, 32, 43, 51, 57) and `## Output Format` (65). Step 4 (line 51) is "Cull check (added tests only)"; line 53 uses the same "no sibling" wording; line 34 names `test-reviewer` as the whole-suite reviewer.
- Cross-references among them:
  - smell-reviewer -> code-reviewer Step 3 (smell line 19) and reviewer-calibration.
  - code-reviewer line 8 -> branch-exit test audit.
  - Cull wording appears in coder-core:67, test-reviewer Step 5, test-intent-reviewer Step 4.
  - `C/agents/test-reviewer.md:17` has its own `## Calibration` section and no `reviewer-calibration.md` pointer.
- Parts repeated across code-reviewer and calibration: `blocker` rule at `code-reviewer.md:80` ("`blocker` only when shipping the item means data loss, a security breach, or a production outage in normal use") and `reviewer-calibration.md:69,74`; `fix`/`ask`/`nit` template in both `code-reviewer.md:77-89` and `smell-reviewer.md:41-48`.

### Q5. review-fork-run, plan-format, reviewer-calibration

- `review-fork-run.md` (19 lines, no headings; bold lead-ins): The run folder (3), Launch (5), Reviewers (7), The packet's ACTION lines (9; bullets 11-15: STOP readings, `--detach` launch, `show-plan-impacts` / Plan Deviations coder dispatch, `redispatch` / `launch-fix-run`, "An ask you may decide yourself: ... asks-done with `--by session`"), Ending the run hands back (17: writes `<run folder>/review-stop.md`), Resume (19).
- `plan-format.md` (151 lines): `## Risk tiers` (5), `## Format rules (hard)` (12), `## Reading a plan` (40), `## Template` (44) containing Phase Status (59), Acceptance Criteria (83), Phase sections (100-138), Testing Strategy (140), Plan Deviations (144), References (148).
  - Rules: Phase Status mandatory (14), `(risk: low|high)` tag (15), `— gate:` suffix (16), `Expected red:` line (31), plan ends with the Close pass (36).
- `reviewer-calibration.md` (112 lines): `## Calibration Anchor` (5), `## Verify the Premise Before Flagging` (35), `## Disposition` (46; `blocker` at 69, "blocker needs real-world likelihood" at 74, "The disposition is a claim, not a lever" at 76, "make the routing mechanical" at 82), `## Self-Check Before Reporting` (102).
- Same rule at more than one place:
  - Close pass Phase Status line: `closing-phases.md:22` and `plan-format.md:69` carry the same text "- [ ] Phase N: Close pass — /close-branch parallel review, one fix, fix-diff gate, recap (risk: high)".
  - Close pass described in `closing-phases.md:7`, `plan-format.md:36-38`, `plan-format.md:91`, `C/skills/close-branch/SKILL.md:3`, `:94`.
  - Plan routing / Plan Deviations / PLAN-IMPACT: `review-fork-run.md:13`, `coder-core:81-99`, `code-reviewer.md:85`, `C/skills/code/SKILL.md:94`.
  - Blocker rule: `reviewer-calibration.md:7,69,74,107`; `code-reviewer.md:78-80`; `C/skills/_shared/finding-log.md:22,39` (`blocker=yes`); `C/agents/plan-reviewer.md:65,83,89-90` (a separate `BLOCKER` meaning for plans).

### Q6. eng-spec phase structure and the goal-blind files

- `C/skills/eng-spec/SKILL.md:25-33`: phase files `phases/1-ticket · 2-research · 3-scope · 4-explore · 5-decisions · 6-finalize · 6b-review · 7-handoff` ("Read each phase file on entry, not ahead"); "All agent dispatches are pinned — omit `model`." Template: `templates/spec-template.md`.
- Step numbers run continuously across phase files (9-10 in `4-explore.md`, 11-14 in `5-decisions.md`, 15+ in `6-finalize.md`, 19-21 in `6b-review.md`).
- `phases/4-explore.md` (45 lines): step 9 launches `backend-architect` / `frontend-architect` (both in parallel for fullstack), gives each the ticket and `02-research.md` and a quoted prompt asking for an exploration brief of seven numbered items (Current state, Invariant survey, Patterns, Constraints, Counter-priming, Decision points, Open questions). Step 10 (line 43): if every architect returns a full plan with zero decision points and zero open questions, skip Phase 5 and step 15; enter Phase 6 at step 16.
- `phases/5-decisions.md` (97 lines): step 11 writes `03-decisions.md` (queue lines D#/Q#, `## Resolved`, `## Direction & Constraints`; items are ADD-ONLY). Step 12 presents understanding. Step 13 writes each answer down as a four-field block (`_shared/design-decision-format.md`, line 41) before the next question. Step 14 recommends the whole queue in one message and never uses `AskUserQuestion`; "approve the rest" covers every non-warning line; a scope gate (line 93) marks migration/index/table/endpoint/dependency decisions with a warning. Line 97: no spec until every queue line is ticked.
- `phases/6b-review.md` (79 lines): step 19 dispatches `plan-reviewer` with paths only; 19b shards above 400 lines (`plan_review_shards.py cut` / `clean`, `plan_review_reports.py check`); step 20 "Review rounds: STANDARD max 1, DEEP max 2", only BLOCKER and GAP re-dispatch, ALT goes to the user once; 20b logs via `log-escape` (`guard=` from `_shared/escape-ratchet.md`, line 50); step 21 logs via `log-spec-run` (line 59); then Phase 7.
- `C/agents/goal-blind-researcher.md`:
  - Rule (line 13): "You do not read the ticket." Line 15: never writes or edits `01-questions.md`; "Repair is a re-dispatch."
  - Steps (lines 30-60): 1 `spec-questions`; 2 `spec-leak-check` with the questions path and nothing else; 3 "Repair loop, bounded at two cycles" — a material leak re-dispatches `spec-questions` with the questions path, findings and ticket path; after two cycles it dispatches once more to replace each flagged question word for word with the leak-check's rewrite; a flag with no rewrite -> "stop and return survivors + verdicts"; 4 `spec-research` with the questions path and one line `exclude: !{docs/plans/<slug>/**,<source ticket folder>/**}` (or `exclude: !{docs/plans/<slug>/**}` with no source file, line 60).
  - Return block (lines 62-76) lists Questions, Leak check, Research; "Never summarize `02-research.md`".
- `C/agents/spec-research.md`:
  - "The one rule" (lines 12-30): read only the questions file; the `exclude:` glob goes on every `rg`; use `rg` for content search, `rg --files` for listing; never `grep -r`, `find -exec`, `git grep`, `cd` before a search, `ls`, `tree`; write files only with Edit or Write.
  - Steps 1-9 (lines 34-52) and the document format (lines 54-64) are as this file follows. Tools: `Bash, Read, LSP, Write, Edit`; `maxTurns: 80`.
- `tests/scripts/test_spec_agent_tools.py:21-56` asserts the Edit tool on spec agents that write, the exclude glob in goal-blind-researcher and spec-research, and `eng-spec` forwarding the source ticket file.

### Q7. orient, todos, list, pull-ticket

- `C/skills/orient/SKILL.md` (80 lines): explains how the change fits unchanged code; "On-demand, never a phase — no gate runs it" (8). Git actions: `BASE=$(git merge-base HEAD origin/master 2>/dev/null || git merge-base HEAD origin/main)`, `git diff --stat "$BASE"` / `git diff "$BASE"` (26-27), default branch vs HEAD. Report sections Where it sits, Wiring, Reused vs. new, Structural risks, Attention map (39-69). Vault (71-74): persists to `<vault>/orientations/<yyyy-mm-dd>-<repo>-<branch-or-scope>.md` (`$VAULT_DIR` else `~/vault`), plus a capture line `~/.local/bin/note "orientation: <repo>/<branch> — [[<note filename without .md>]]"`; same-day re-orient overwrites; `+ephemeral` skips. Line 78: read-only, vault persist writes vault-only.
- `C/skills/todos/SKILL.md` (49 lines): `allowed-tools: [Bash, Read, Grep, Glob]`. Sources are the conversation only; `git status` / `git log --oneline -5` only when session state is stale (13). Groups NOW / BLOCKED / THEIRS (21-30), cap 12 items (41). No vault or ticket-state action.
- `C/skills/list/SKILL.md` (37 lines): numbered list of changes already proposed in the conversation; order tiers (16-19); format `<path:line> — <change>. Gate: <direct | meter | user>.` (26); closing line "Reply with numbers to apply" (37). No vault, git or ticket action.
- `C/skills/pull-ticket/SKILL.md` (26 lines): `allowed-tools` includes `mcp__jira__getJiraIssue`. Step 1 fetch per `_shared/jira-ticket.md` (required-ticket caller). Step 2 ticket status: "'To Do' means note work starting; 'In Progress' means note only; 'In Review' or 'Done' means warn and confirm" (15-16). Step 3 presents key, summary, status, acceptance criteria, suggested approach. Line 22: "Devs pull from Jira only (Notion is the PM domain)." It writes no ticket state itself (only the instruction text "note work starting").

### Q8. Anchor rows

- Stored in `docs/rule-anchors.md` (211 lines; table header line 25 `| hash | file | section | evidence | reason |`). Preamble lines 1-24 explain the procedure and the evidence kinds: `gate ranking`, `census`, `removal round`, `seeded round`, `controlled replay`, `rule meter`, `judgment`, `unproven`.
- A row is `| <8-hex sha256 prefix> | <path relative to C/> | <heading line or (preamble)> | <evidence kinds> | <reason with [change](changes/notes/...) links> |`. Example: `docs/rule-anchors.md:63` (`d939d255 | skills/coder-core/SKILL.md | (preamble) | removal round`).
- Rows per file (computed): coder-core 15; architect-core 6; code-reviewer 7; smell-reviewer 5; test-reviewer 5; test-intent-reviewer 7; plan-verifier 12; complexity-reviewer 12; mutation-tester 9; plan-reviewer 7; spec-criteria 6; spec-questions 6; goal-blind-researcher 5; spec-research 4; spec-leak-check 4; backend-architect 5; frontend-architect 5; coder 1; `CLAUDE.md` 8; `orchestration.md` 6; five `rules/*.md` 2 each; `skills/code` 6; `fix` 4; `refactor` 7; `review` 4; `_shared/code-vocabulary.md` 4, `finding-log.md` 3, `handoff-block.md` 6, `reviewer-calibration.md` 5, `review-fork-run.md` 1. Files with no rows: `general-purpose.md`, `code-fork.md`, the other `_shared` files, `orient`, `todos`, `list`, `pull-ticket`, `eng-spec`.
- Hash (`C/scripts/tools/rule-anchors.sh:15-24`): a block is a heading line plus text to the next heading outside a code fence; whitespace runs collapse to one space; `sha256sum | cut -c1-8`.
- Commands: `rule-anchors.sh list <file>...` (hash, file, heading per block); `rule-anchors.sh check` (every file the sidecar names against the sidecar; sidecar path from `RULE_ANCHORS` or `C/../../docs/rule-anchors.md`, line 13).
- Readers: `C/scripts/tools/claude-doctor.sh:13,229-233` (check 4e); `tests/scripts/test_rule_anchors.py:1-11` (env `RULE_ANCHORS_SCRIPT`); `tests/changed_scope.py:22` and `tests/scripts/test_prompt_reader_list.py:13` list `test_rule_anchors.py` as a prompt reader read through awk; `tests/scripts/test_toolkit_self_location.py:80` covers the script's path handling; `.prettierignore:2` excludes the file.

### Q9. opencode ports

- `O/agents/` holds 17 files: every `C/agents/*.md` except `code-fork.md` (no port).
- Per-file differing lines (`diff` count of `<`/`>`): backend-architect 18, code-reviewer 109, coder 14, complexity-reviewer 42, frontend-architect 14, general-purpose 12, goal-blind-researcher 32, mutation-tester 77, plan-reviewer 8, plan-verifier 61, smell-reviewer 46, spec-criteria 12, spec-leak-check 12, spec-questions 14, spec-research 35, test-intent-reviewer 62, test-reviewer 160.
- Frontmatter differences (`O/agents/code-reviewer.md:3-8`): `model: opencode-go/mimo-v2.6-flash` (claude: `opus`), `mode: subagent`, `permission: edit: deny`, `color: "#06b6d4"` (hex, not a name); no `tools:` line. `coder.md:4-5` same `model`/`mode`/hex color.
- Body differences seen:
  - `O/agents/coder.md:9`: "**First action**: Read `~/.claude/skills/coder-core/SKILL.md` and adopt it in full — opencode does not preload skills. While reading it, substitute: project `CLAUDE.md` -> `AGENTS.md` ...". Architect ports say "preloaded via `architect-core`" (`O/agents/backend-architect.md:11`, `frontend-architect.md:11`).
  - `O/agents/plan-verifier.md:3`: "Dispatched by /verify at branch end" (claude: /verify-branch). `O/agents/code-reviewer.md:3`: "...bugs, anti-patterns, architectural violations and security issues. Dispatched by the review loop, /peer-review and /calibrate."
  - `O/agents/code-reviewer.md` has a `## Calibration (shared)` pointer (line 17-19) and a `## Do NOT Flag` section, a `### Step 3: Categorize Findings` (94) and an `### Ask` line with `PLAN-IMPACT:` (115); it has no `### Step 3: Structure` heading.
  - `O/agents/code-reviewer.md:13` hook-block line says "never run that command in another form (split strings, swapped words, encoding)", where `C/agents/code-reviewer.md:11` does not.
- Other `O/` content: `commands/` (59 files, e.g. `adr.md`, `code.md`, `review.md`, `verify.md`), `skills/{rebase,open-pr,merge}/SKILL.md`, `plugins/` (security-gate, herdr-agent-state, tuios-agent-state), `opencode.jsonc`, `tui.json`. `C/skills/` is auto-loaded by opencode (`CLAUDE.md` "opencode" notes), so `_shared` files are read from `~/.claude/skills/_shared/` by the ports.
- `C/scripts/tools/claude-doctor.sh:15,21` has check 6 "opencode sync: agent filename diff, CLAUDE.md vs AGENTS.md mtime drift".

### Q10. `~/agent-evals` rule meter and `unmeasured`

- `bin/rule_meter.py` (2723 lines). Docstring (lines 2-48): one cell is a rule x prompt level (`LEVELS = ("supportive","neutral","competing")`, line 87) x arm (`ARMS = ("on","off")`, line 88). A cell builds a bench tree from the ticketsim fixture, appends the global CLAUDE.md to the project CLAUDE.md (arm off: minus the rule's text), runs `claude -p` on the rule's task, grades tool calls and tree with a script. Outcomes COMPLIED, VIOLATED, NO_TEST, NO_CHANGE, ERROR.
- Commands (docstring 22-28): `run --rule A --level competing --arm on [--run 1] [--dry-run]`, `run-all [--runs N] [--level L] [--dry-run]`, `summary`. Entry points: `main` (2671), `run_cell` (2488), `grade` (1435), `load_scenarios` (1578; reads `SCENARIOS = HERE / "rule_meter_scenarios.json"` at line 83, then `rule_meter_families.check_splits`).
- `rule_source_for_arm` (1590s): arm `on` returns the source whole; arm `off` removes `scenario["rule_text"]` once (`remove_once`), loud when not found. A scenario may name an `agent` and `rule_source` (toolkit file relative to `~/.claude`); the session then runs as that agent with the agent file and skills copied into the tree's `.claude/`.
- `bin/rule_meter_scenarios.json` (1747 lines): a dict of 105 scenarios keyed by id (`A`, `AE`, `TR01`, `NC01`, `PV01`, ...). Keys: `name`, `rule_text`, `setup`, `detector`, `task`, `suffix` ({supportive, neutral, competing} strings), `rule_source`, `toolkit_root`; optional `agent`, `model`, `plant`, `note`, `family`, `split`. Counts by `agent`: coder 61, none 21, code-reviewer 10, test-reviewer 8, smell-reviewer 3, test-intent-reviewer 1, plan-verifier 1.
  - Reviewer scenarios: code-reviewer AE (`flags_readability_smell`), AF (`no_wording_only_docs_findings`), AG-AJ (unindexed filter/sort), R (`flags_reimplemented_helper`), S (`flags_inline_prorate`), T (`reachable_defect_is_a_fix`), U (`sibling_sweep`); test-reviewer TR01-TR04 and TR01Q-TR04Q; test-intent-reviewer L (`cull_keeps_same_path_input_shape`); smell-reviewer NC01-NC03; plan-verifier PV01 (`late_fee_verdicts`).
- Detectors: named by `scenario["detector"]`; dispatched in `grade` (1435) to `grade_stacks` (1423, `STACK_DETECTORS` 147, `STACK_RED_DETECTORS` 153), `grade_coder5` (1365), `RECORD_DETECTORS` (1361), and inline cases (`no_unstage`, `changed_tests_only`, ...). Rules F, R, S read the final reply.
- Hidden checks `bin/rule_meter_checks/` (12 files): `async_panel_states.mts`, `async_view_states.mts`, `branch_has_failing_test.py`, `incidental_owner_filters.py`, `keep_behavior.mts`, `keep_date.mts`, `keep_quantity.mts`, `second_owner_mutation.py`, `stale_docs.mts`, `sweep_defaults.mts`, `sweep_owner_check.mts`, `weak_fix_test.mts`.
- Plants: `bin/rule_meter_plants/` (25 folders, `PLANT_SOURCES` at `rule_meter.py:126`); also `rule_sweep_plants` (127) and `rule_stack_plants` (140). Run output under `~/dev/evals/rulemeter1/`.
- Other modules: `rule_meter_{coder5,config,families,fixture,index,plans,regress,stacks,verifier}.py`, `rule_meter_shipped.json`, `test_rule_meter*.py` (8).
- `unmeasured` (change files): `bin/build_changes.py:170` lists it in `OPTIONAL_FIELDS`; docstring `:59-60`: "unmeasured, a non-empty reason that no intake metric can read it; those changes are listed in the changelog under 'Unmeasured behavior changes'." `:398-400`: a behavior change needs a non-empty `watches` list or `unmeasured`. `:470` stored per change; `:690` `unmeasured_changes`, `:703` `unmeasured_reason`, `:734-738` render the changelog entries. `~/agent-evals/CLAUDE.md:471`: "A rule the meter cannot grade (no fixture shows the behavior) says so in `unmeasured` and goes to the user before it ships."; `:485` lists stacks in `unmeasured`.

### Q11. `tests/run.sh` and prompt-reading tests

- `tests/run.sh` (header lines 2-7): runs, in order, `tests/lint.sh`; `tests/duplicate_code.py`; `tests/review_gate_unchanged.py snapshot`; `tests/changed_scope.py scope`; `tests/parallel_tests.py` (every `test_*.py` under `tests/`, one process per file, `nproc` at a time); `review_gate_unchanged.py compare`. A failed step (`lint`, `duplicate-check`, `tests`, `review-gate-state`) is named on the last line with exit 1. A missing `ruff` (lint status 2) stops the run. `CLAUDE_SKIP_HOOKS` is unset. `REAL_PLANS=1` adds a parse of real plans.
- Markdown-only scope (`tests/changed_scope.py`): `PROMPT_MARKDOWN = ^claude/\.claude/(skills|agents)/.+\.md$` (line 21). When every change since the merge base with `origin/master` (committed, staged, unstaged, untracked) matches it, `run.sh` runs only `PROMPT_READING_TESTS` (printed by `changed_scope.py kept`); lint and duplicate-check still run. Any unreadable state answers `full`.
- `PROMPT_READING_TESTS` (`changed_scope.py:27-44`, 16 files): `test_adr_flow`, `test_code_skill_text`, `test_docs_kind`, `test_fork_write_scope`, `test_guidance_rules`, `test_log_escape`, `test_log_review_finding`, `test_refactor_flow`, `test_review_loop_coder`, `test_review_loop_named_tests`, `test_review_loop_round_two_fixes`, `test_review_loop_ruled`, `test_review_loop_script`, `test_rule_anchors`, `test_spec_agent_tools`, `test_telemetry_switch` (all `.py`).
- `SIGNAL_BUT_NO_PROMPT_READ` (`changed_scope.py:55-72`): 16 files that show the signal regex but read no markdown. `tests/scripts/test_prompt_reader_list.py` checks both lists against the signal regex and `LISTED_WITHOUT_SIGNAL = {"test_rule_anchors.py": ...}` (line 13). `tests/scripts/test_changed_scope.py` tests the scope script.
- Tests asserting content of skill or agent markdown:
  - `tests/scripts/test_guidance_rules.py`: `guidance_text("<path under C>")` reads `orchestration.md`, `CLAUDE.md`, `agents/{code-fork,test-intent-reviewer,test-reviewer,spec-research,spec-criteria}.md`, `skills/{code,close-branch,pr-comments,branch-recap,coder-core,eng-spec/phases/2-research,eng-spec/phases/7-handoff,_shared/review-fork-run}`, `rules/frontend-style.md` (lines 25-206).
  - `tests/scripts/test_code_skill_text.py`: `/code` and code-fork give the user no git command.
  - `tests/scripts/test_spec_agent_tools.py` (spec agents' tools and the exclude glob).
  - `tests/scripts/test_rule_anchors.py` (anchors; drift between prompt blocks and `docs/rule-anchors.md`).
  - Tests that run `C/scripts/gates/*` against fixtures: `test_calibration_refs_guard.py` (heading match between reviewer agents and `reviewer-calibration.md`), `test_spec_budget_gate.py` (word budget over `SHARED_FILES`, lines 136-172), `test_agent_model_guard.py` (model pin from agent frontmatter), `test_dead_prose_gate.py`, `test_comment_bloat_gate.py`, `test_stale_citation_gate.py`.
- Descriptions: no test in `tests/scripts` asserts agent `description` text (`rg description` over `test_guidance_rules.py`, `test_rule_anchors.py`, `test_spec_agent_tools.py` found none). Pointers: `test_calibration_refs_guard.py` (calibration pointers), `test_guidance_rules.py:179`. `_shared` loaders: `test_spec_budget_gate.py`, `test_adr_flow.py:21,37` (adr-template), `test_log_escape.py:325,341` (escape-ratchet), `test_log_review_finding.py:23` (finding-log).

### Q12. `code-reviewer.md` rules and finding format; hard-coded lists and duplicated values

- Format (`C/agents/code-reviewer.md:66-90`): `## Code Review Summary`, `Files Reviewed`, `Overall Assessment: [PASS / PASS WITH WARNINGS / NEEDS CHANGES]`, optional `### Prior Issues Verified`, then `### Fix` (`[blocker] file:line — issue — fix`; "an item with no fix is an `ask`"; `blocker` only for data loss, security breach or production outage), `### Ask` (`file:line — issue — the question the human has to answer — change: the one edit an accepted answer makes`; two cases only; PLAN-IMPACT form, line 85), `### Nit` (one combined line). Line 90: no "Positive Observations" or "Recommendations".
- Review steps: Step 1 scope (17), Step 2 reads (31), Step 3 structure (43). Structure findings are prefixed `[smell]` (58); disposition by consequence (58); anti-churn paragraph (60); `[smell] [design-decision]` for restructuring beyond the diff (62); "Never audit pre-existing smells" (64). Tool use limits at 94-97.
- Rules on duplicated values and hard-coded copies in the file (all inside `### Step 3: Structure`):
  - Line 51: "**A shared decision copied at any size.** When two or more sites encode ONE decision that must produce identical output — a derived formula, a magic value or sentinel, a user-visible string, a guard threshold, a format/rounding choice — flag at two sites when the copies are already inconsistent, at three or more regardless. State the decision, every site, and whether they currently agree."
  - Lines 47-50: duplication in three forms (same logic twice in the diff; re-implementing an existing helper/util/hook/component with the candidate named by `file:line`; a block of ~8+ lines copied from a sibling).
  - Line 58: "a hand-written copy of a helper the file already has" is a `fix`.
  - Line 60: Anti-churn — three similar lines or incidental similarity are suppressed.
  - Line 54: dead weight; dead exports need an LSP/`rg` reference count.
  - No rule in the file names a "hard-coded list" as such.
- Related rules elsewhere: `C/agents/complexity-reviewer.md:25` ("**Values with more than one owner.** The same fact stored, cached, or recomputed in several places ... Give it one canonical owner"); `C/agents/plan-reviewer.md:29` ("A class scoped as a list"), `:43` ("Count classes, never sample them"); `C/skills/_shared/reviewer-calibration.md:28` (magic numbers in test fixture data are not flagged); `C/scripts/CLAUDE.md` "Owners" section (one owner per fact, "Never add a second copy of the fact"); meter scenarios `R`, `S` (`flags_reimplemented_helper`, `flags_inline_prorate`) and `NC01-NC03`.

## Dormant scaffolding

- `C/agents/code-reviewer.md` carries no pointer to `reviewer-calibration.md`, while `reviewer-calibration.md:3` says it is shared by `smell-reviewer` and `complexity-reviewer` and that its headings are referenced by every adopting agent and its opencode ports; `O/agents/code-reviewer.md:19` does point to it.
- `kind: reword|cut|narrow` is on the PLAN-IMPACT block (`coder-core:92`, `code-reviewer.md:85`); `C/scripts/code/coder_report.py:35` `PLAN_IMPACT_KEY` does not list `kind`. `kind: reword` is read as the `reword` flag in `review_fix_plan_impacts.py:229`.
- `plan_format.PLAN_IMPACT_OPTIONS` (871) and `DECISION_WORDS` (875) are defined beside each other; not traced further.
- `C/skills/_shared/plan-format.md` is not named by `C/skills/code/SKILL.md` or the architect agents; its pointers are in eng-spec files and `spec_budget_gate.py`.
- `skimmable-writing.md` has exactly one pointer (`adr-template.md:40`).
- `C/agents/general-purpose.md`: no skill, script or README names it as a dispatch target (see Q2).
- No rows in `docs/rule-anchors.md` for `general-purpose.md`, `code-fork.md`, `orient`, `todos`, `list`, `pull-ticket` or `eng-spec` (see Q8).
- `O/agents/code-fork.md` does not exist (no port of `code-fork`).
- `C/commands/` does not exist; `O/commands/` has 59 files.
- `tests/changed_scope.py` `SIGNAL_BUT_NO_PROMPT_READ` holds 16 entries, each a test that matches the signal and reads no prompt markdown.

## Code References

- `C/skills/_shared/review-fork-run.md:3-19` — fork run procedure, ACTION lines, stop file
- `C/skills/_shared/reviewer-calibration.md:5,35,46,102` — the four load-bearing headings
- `C/skills/_shared/plan-format.md:5-148` — risk tiers, format rules, template; Phase Status at 59; Close pass line at 69; Acceptance Criteria at 83
- `C/skills/_shared/closing-phases.md:7,22` — Close pass description and Phase Status line
- `C/skills/coder-core/SKILL.md:81-99` — PLAN-IMPACT block, `acceptance_criteria` rule
- `C/agents/code-reviewer.md:43-64,66-90` — Step 3 structure, output format
- `C/agents/smell-reviewer.md:15,19` — calibration pointer, Step 3 pointer
- `C/agents/goal-blind-researcher.md:30-60` — chain and repair loop
- `C/agents/spec-research.md:12-52` — one rule and steps
- `C/skills/eng-spec/phases/{4-explore,5-decisions,6b-review}.md` — phases 4, 5, 6.5
- `C/scripts/lib/plan_format.py:72,87,782,791,805` — AC regexes and readers
- `C/scripts/tools/rule-anchors.sh:13-24` — sidecar path, block hashing
- `docs/rule-anchors.md:25-211` — anchor table
- `tests/changed_scope.py:21-72` — markdown-only scope and prompt-reader lists
- `tests/run.sh:1-70` — runner steps
- `~/agent-evals/bin/rule_meter.py:83-88,1435,1578,2488,2671` — meter core
- `~/agent-evals/bin/build_changes.py:59,170,398,470,690-738` — `unmeasured`

## Patterns Found

- Skills point to `_shared` files by the absolute-style path `~/.claude/skills/_shared/<name>.md`, often with "(read it)" or "whole first"; agents point to `reviewer-calibration.md` with "First action: Read ... and adopt its **Heading**".
- Agent descriptions end in a "Dispatched by ..." sentence; dispatchers pin the model by omitting `model`.
- Pointers by heading name are guarded by hooks and tests (`calibration_refs_guard.py`, `rule-anchors.sh check`).
- Each anchored block has a content hash; evidence kinds are listed in the table's fourth column.
- The opencode port copies each agent with frontmatter rewritten (`model`, `mode`, `permission`, hex color) and a "First action: Read" line where claude uses `skills:` preloading.
- Step numbers in eng-spec phase files continue across files (9 to 21).
- Prompt-reading tests are listed by hand in `changed_scope.py`, checked by `test_prompt_reader_list.py`.
- Meter scenarios hold the verbatim `rule_text`, a three-level `suffix`, a `detector` name, optional `plant`.

## Reuse Inventory

- `changes_acceptance_criteria(impact) → bool` — `C/scripts/lib/plan_format.py:782` — False only when every PLAN-IMPACT answers `none`.
- `criteria_ids(text, answers_only=False) → set` — `plan_format.py:791` — AC ids named by a text.
- `plan_impact_cause(block, missing=PLAN_CAUSE) → str` — `plan_format.py:805` — the `cause:` value.
- `AC_CHANGE_LINE`, `AC_CHANGE_CLAUSE`, `PLAN_IMPACT_CAUSE`, `PLAN_IMPACT_CAUSES`, `PLAN_IMPACT_OPTIONS` — `plan_format.py:72,87,76,80,871` — PLAN-IMPACT grammar constants.
- `rule-anchors.sh list <file>... / check` — `C/scripts/tools/rule-anchors.sh:5-6` — block hashes and sidecar check.
- `claude-doctor.sh` check 4e — `C/scripts/tools/claude-doctor.sh:229-233` — runs the anchor check.
- `calibration_refs_guard.py` — `C/scripts/gates/calibration_refs_guard.py` — PostToolUse heading-reference check (env `CALIB_FILE`, `CALIB_AGENTS_DIR`).
- `spec_budget_gate.SHARED_FILES` — `C/scripts/gates/spec_budget_gate.py:22` — guarded shared files.
- `plan_review_shards.py cut|clean`, `plan_review_reports.py check` — `C/scripts/tools/` — used by `6b-review.md:7-21`.
- `log-escape`, `log-spec-run` — `C/scripts/telemetry/` — used by `6b-review.md:50-59`.
- `changed_scope.py scope|kept` — `tests/changed_scope.py:85-100` — markdown-only scope and kept test list.
- `guidance_text(path)` — used in `tests/scripts/test_guidance_rules.py` — reads a toolkit prompt file's text.
- `toolkit_paths` — `tests/scripts/toolkit_paths.py` — path constants (`TOOLS_DIR` etc.) shared by tests.
- `tests/parallel_tests.py <test file>` — runs named tests with the worker cap.
- `rule_meter.py run | run-all | summary` — `~/agent-evals/bin/rule_meter.py:22-28` — meter commands.
- `load_scenarios() → dict` — `rule_meter.py:1578`; `rule_source_for_arm(source_text, scenario, arm, source_path)` — `:1590`; `grade(scenario, tool_calls, tree, base_sha, result_text=None)` — `:1435`.
- `bin/rule_meter_checks/*`, `bin/rule_meter_plants/*` — hidden checks and plants (lists in Q10).
- `build_changes.py` — `unmeasured_changes(changes)` `:690`, `unmeasured_reason(change)` `:703`.
