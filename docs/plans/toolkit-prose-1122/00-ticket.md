# toolkit-prose-1122: seven toolkit-writing audit items

Source: ~/agent-evals/queue/fix-contradictory-lines-in-orient-todos-and-two.md (first of seven items, each listed below with its own Source line; orchestrating session agent-evals-c3; lane brief /tmp/claude-1000/-home-brandon-agent-evals/a0b58526-6a4a-4e0a-af5b-8d0985572fda/scratchpad/brief-toolkit-prose.md)

## Item: fix-contradictory-lines-in-orient-todos-and-two

Source: ~/agent-evals/queue/fix-contradictory-lines-in-orient-todos-and-two.md

description: "Fixes lines an agent cannot follow because they contradict another line or name no action."
source: "claude/.claude/skills/orient/SKILL.md"
components: ["skill/orient", "skill/todos", "skill/list", "skill/pull-ticket", "agent/test-intent-reviewer", "agent/plan-verifier"]

### Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

- orient:78 says it never edits, but it writes to the vault.
- todos:13-15 allows `git status` but says "do not go looking".
- list:33/37 puts the file name under the list but says nothing after the closing line.
- pull-ticket:15-16 "'To Do' means note work starting" names no action.
- test-intent-reviewer and plan-verifier descriptions name only /test-audit and /verify-branch as dispatchers; close-branch dispatches both.

### Done when

Each line names one action and no line contradicts another in its file; the agent descriptions name every dispatcher; opencode ports are patched.

## Item: split-dense-paragraphs-in-review-fork-run-coder

Source: ~/agent-evals/queue/split-dense-paragraphs-in-review-fork-run-coder.md

description: "Splits the longest multi-branch paragraphs in the toolkit into one-branch lists."
source: "claude/.claude/skills/_shared/review-fork-run.md"
components: ["shared/review-fork-run", "shared/plan-format", "shared/reviewer-calibration", "skill/coder-core", "skill/eng-spec"]

### Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

- _shared/review-fork-run.md:19 (also :13, :17): about 420 words, 10+ branches.
- coder-core/SKILL.md:77 "Verify before you report": about 230 words; :14 test-first overlaps :43 "Tests are yours".
- _shared/plan-format.md:25, :30, :31; :30 is about 330 words; the Close pass is described four times.
- eng-spec: 4-explore.md invariant survey, 5-decisions.md step 14 (about 12 sub-rules), 6b-review.md shard procedure; goal-blind-researcher repair loop; spec-research rg rules.
- reviewer-calibration.md:58-98 states plan-routing and blocker rules 3-4 times.

coder-core is anchored: update the anchor rows.

### Done when

Each listed paragraph is a list with one branch per item and each duplicate has one owner; rule-meter arms run on removed text; `bash tests/run.sh` passes.

## Item: architect-agents-descriptions-name-the-dispatch

Source: ~/agent-evals/queue/architect-agents-descriptions-name-the-dispatch.md

description: "Cuts about 45 always-loaded words from each architect description and one copy of the reuse-map block."
source: "claude/.claude/agents/backend-architect.md"
components: ["agent/backend-architect", "agent/frontend-architect", "skill/architect-core"]

### Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

- backend-architect.md:3 and frontend-architect.md:3: about 45 words each argue the go-lean gate in the always-loaded description.
- The Reuse Map block is in both architects; the two-stage and "research is ground truth" text is in both architect-core and eng-spec/phases/4-explore.md.

Architects are anchored: update the anchor rows.

### Done when

Each description reads "Designs backend/frontend features ... Dispatched by /eng-spec phase 4."; each duplicate has one owner in architect-core; rule-meter arms run; the opencode ports are patched.

## Item: general-purpose-agent-cut-the-body-that-copies-the

Source: ~/agent-evals/queue/general-purpose-agent-cut-the-body-that-copies-the.md

description: "Cuts about 16 lines from every general-purpose dispatch by keeping only the frontmatter that changes behavior."
source: "claude/.claude/agents/general-purpose.md"
components: ["agent/general-purpose"]

### Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

agents/general-purpose.md:7-22 copies the harness's built-in general-purpose prompt. Only the frontmatter (model, description) changes behavior.

### Done when

The body is empty or one line; a rule-meter arm shows no loss; the opencode port is patched or knowingly skipped.

## Item: shared-fold-single-loader-files-into-their-loader

Source: ~/agent-evals/queue/shared-fold-single-loader-files-into-their-loader.md

description: "Folds four single-loader reference files into their loader and makes every pointer to a shared file name when to read it."
source: "claude/.claude/skills/_shared/escape-ratchet.md"
components: ["shared/escape-ratchet", "shared/skimmable-writing", "shared/design-decision-format", "shared/finding-log", "shared/code-vocabulary", "shared/plan-reading", "skill/test-audit", "agent/smell-reviewer"]

### Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

- Single loader: skimmable-writing.md (only via adr-template.md, which only adr_flow.py loads), design-decision-format.md (only eng-spec 5-decisions), finding-log.md (only test-audit, yet claims every gate; its review-loop lines 39-43 reach no loader).
- code-vocabulary.md and plan-reading.md list consumers that do not load them.
- escape-ratchet.md has 6 weak "per X" pointers (verify-branch, cc, commit, escape, pr-comments, fix); agents/spec-criteria.md:58 is a bare pointer.
- Also in this sweep: test-reviewer.md:45 and test-intent-reviewer.md:53 carry the same cull rule; smell-reviewer.md:19 reads a slice of code-reviewer.md by rg (extract to one shared structure-rules file).

### Done when

No _shared file has a single loader; every pointer names its trigger; each consumer list matches the loaders rg finds; `bash tests/run.sh` passes.

## Item: dedupe-the-acceptance-criteria-none-rule-across

Source: ~/agent-evals/queue/dedupe-the-acceptance-criteria-none-rule-across.md

description: "States the acceptance_criteria-none rule once so coder-core and code-reviewer stop carrying the same sentence."
source: "claude/.claude/skills/coder-core/SKILL.md"
components: ["skill/coder-core", "agent/code-reviewer"]

### Context

Bullet 4 of queue item code-skill-dedupe-the-stop-rule-and-move-the-phase: the rule that a plan with no behavioral criteria has no acceptance-criteria file (acceptance_criteria none) is stated in both `skills/coder-core/SKILL.md` and `agents/code-reviewer.md:85`. The 2026-11-22 code-skill lane left it out because those files sit outside the /code skill. Each cut of an existing rule goes through rule-meter on/off runs first.

### Done when

One owner for the rule; the other file points to it or drops the sentence; rule-meter arms recorded in the change file; anchor rows updated; `bash tests/run.sh` passes.

## Item: reviewer-flags-a-hard-coded-list-of-toolkit-names

Source: ~/agent-evals/queue/reviewer-flags-a-hard-coded-list-of-toolkit-names.md

description: "A review catches a committed list of skill or agent names that drifts each time the toolkit changes, before the user has to."
source: "claude/.claude/agents/code-reviewer.md"
components: ["agent/code-reviewer"]

### Context
A retro on a ledger doctor session: ledger kept a committed known list of skill names, and three new skills lost their names. The main session first offered to add the names, then a design that still checked installed skills; the user corrected it twice ("lists of stuff drift"). The fix derives the label from the source path each skill call records.

### Done when
A seeded diff that adds a hard-coded toolkit-name list (skills, agents, hooks) to an app gets a reviewer finding that names the drift and the source the value can be derived from; the same diff without the rule gets none.

## Rulings from the orchestrating session (agent-evals-c3, 2026-11-22)


- Item 8: retire. close-branch is the single closing phase. Cut the branch-recap template and the "fourth"/"third closing phase" lines; keep `skills/branch-recap/SKILL.md` as a three-line alias that says to run close-branch's recap step, so the slash name still works. Do not ask the user.
- Item 5: do not edit `skills/_shared/plan-reading.md` or anything under `skills/code/`; the code-skill lane owns them on fix/code-skill-nov22. Record that bullet as deferred in the queue item's outcome and leave it for a follow-up item (`build_queue.py new`).
- Item 2: the coder-core and reviewer-calibration paragraphs are in scope. `skills/code/SKILL.md` is not.
- Owners lines: none in any CLAUDE.md. A module owner goes in its module docstring.
- Every rule you cut, merge or reword gets rule-meter on and off arms before commit. New scenarios go in `bin/rule_meter_scenarios.json`; new detectors go in `bin/rule_meter_checks/` with tests; `bin/rule_meter.py` stays untouched. Run `git -C ~/agent-evals status bin/` first and never touch another session's uncommitted file there. A rule the meter cannot grade is listed in the change file's `unmeasured` and reported to agent-evals-c3, which rules on it.
- Item 7 is a new code-reviewer rule: its meter scenario is the seeded diff in the item's Done-when (a hard-coded skill or agent name list), on and off arms.
- Opencode ports: patch them where the item names them.

- Item 8 (retire-branch-recap) is out of this lane: claimed by session bcpc-arch before this lane could claim it.

## Comments

none
