---
name: code
description: Dispatch a coder subagent for implementation, then auto-run `/review`. Use for "implement/build/add X" when the task is well-defined or a plan file exists; features needing design decisions go to /eng-spec first. When it hands back a stop, run `/code resume <the user's answer>`.
context: fork
agent: code-fork
model: sonnet
allowed-tools: [Agent, Bash, Read, Skill]
---

# Code

Dispatch coder subagent(s) to implement code directly without architectural planning.

## Modifiers

`+fast` / `+deep` per `~/.claude/skills/_shared/modifiers.md` (read it when either is present).

## Instructions

**End the run only at a STOP below.** Everywhere else, take the next reversible step that follows from the task (a dispatch, a re-run, a read, a coder edit in scope) and report it afterward. Never end the run to ask leave for such a step or only to report progress. Ask only before a step that cannot be undone or that leaves this machine, or when two paths are both defensible.

**The run folder.** `git rev-parse --path-format=absolute --git-path code-phase` from the repo root prints it; `<run folder>` below means that path. Create it with `mkdir -p` before the first write.

**You never change a tracked file.** A coder makes every code and plan edit. You write only `<run folder>/handoff.txt` and `<run folder>/stop.md`, with a Bash heredoc.

**Ending the run hands back.** Every STOP, question and "wait" below ends the run: write its text to `<run folder>/stop.md`, then make it your final reply, ending with the line `To go on: /code resume <your answer>`. Never call AskUserQuestion.

**Waiting.** An `Agent` call returns at once and names an `agentId`. Then run `python3 ~/.claude/scripts/code/code_wait.py agent <agentId>` with the Bash timeout set to 600000; it prints the agent's report. When it prints `Still working`, run it again. Never end the run while an agent you dispatched works.

**Run notes.** Text after the plan file or ticket id in the task text (other than `resume` and its answer) is the run notes. Put it, word for word, under the line `Run notes from the user. They bind this run; the plan stays the spec:` in the prompt of every coder you dispatch for the phase. The review loop's own fix coders do not get it.

**Resume.** When the task text starts with `resume`, the rest is the user's answer to the last stop. Rebuild where the run stopped from `<run folder>/stop.md`, the plan's `## Phase Status`, `git status --short`, `<run folder>/handoff.txt` and `<run folder>/review.out` (the last review packet). Apply the answer to that stop, then go on from the step that stopped.

**Plan impacts never stop the run.** A coder's `PLAN-IMPACT:` block and a review packet's plan impacts go on one list for the phase end. At the phase end, before the phase-boundary decision: an impact that changes no acceptance criterion is adopted with no question: a coder adds it as one line under the plan's `## Plan Deviations` (create it if absent) and makes the plan change. An impact that changes an acceptance criterion (a line in `acceptance-criteria.md` or a phase's Success Criteria) stays unapplied: show it in the phase-complete block under `Plan changes awaiting sign-off` (assumed → found → what changes), and the phase ends on a STOP. On resume, a coder records the user's answer, who signed off and the date, under `## Plan Deviations` and makes the change only when the user signed off.

0. **No arguments** (after stripping modifiers): run `bash ~/.claude/scripts/tools/resolve-task-dir.sh`. Exit 0 → the task directory's `spec.md` is the task input; exit 5 → the printed plan file. Say what resolved. Exit 3 → ask which (a STOP). Exit 4 → ask the user what to implement (a STOP).

1. **Modifiers**: `+deep` → dispatch `coder` as is and omit `model`. `+fast` → pass `model: "haiku"`. Strip modifiers from the prompt passed to coders.

2. **Plan file or pasted plan**: `rg -n '^## ' <plan>` lists every section; the plan is multi-phase when more than one `## Phase N:` section exists. Read it phase-scoped per `~/.claude/skills/_shared/plan-reading.md`. `lane=eng-spec` when step 0 resolved the task input, `lane=code` otherwise; pass it to `code_review_start.py`.

   Before the first phase, run `python3 ~/.claude/scripts/code/coder_gate.py clear` to drop a gate a crashed run left behind.

   Multi-phase plan:

   - The next phase is the first unchecked `- [ ]` entry under `## Phase Status`. Without that section, fall back to `git status` plus per-phase success criteria and tell the user to backfill it.
   - A closing phase (`~/.claude/skills/_shared/closing-phases.md`) runs its named skill in place of steps 3 to 5: invoke that skill with the Skill tool. For the Refactor pass, first run `python3 ~/.claude/scripts/code/concentration.py <base-sha>` and pass on the module it names, or both counts when the gate does not trigger. When the skill reports an open finding, STOP with it. Otherwise dispatch a `coder` to write one line of evidence under each open Success Criteria item of the phase, and go on to the Phase Status tick.
   - Before every phase's coder, confirm `docs/plans/<slug>/acceptance-criteria.md` exists beside the plan and is non-empty. Missing on a task with behavioral criteria → STOP, do not dispatch, report a plan defect to the user; never write the criteria and never dispatch an agent to. Missing on pure config or mechanical work → proceed. Never pass criterion ids into a dispatch prompt. Log a failed check first:

     ```bash
     bash ~/.claude/scripts/telemetry/log-scan repo=<basename> scan=acceptance-stub \
       stage=code-phase exit=0 candidates=1 confirmed=1 note="<what was missing>"
     ```

   - Dispatch the coder for that one phase only, with the phase's Automated Verification gate in its instructions. Re-read the phase's Phase Status line first: `(risk: …)` drives the boundary decision.
   - After the coder returns and you summarize, dispatch the review loop (5).
   - Before marking the phase done, check that the phase's `#### Automated Verification` commands passed: the review loop's execution gate is the full suite; run any other listed command once, after the loop returns; its `#### Manual Verification` items go on the deferred list for `/verify`. A phase with no Success Criteria is a plan defect; say so before advancing. A prohibition criterion (`git grep <pattern>` returns zero hits) is yours to run with Bash and log:

     ```bash
     bash ~/.claude/scripts/telemetry/log-scan repo=<basename> scan=prohibition \
       stage=code-phase exit=<0|1> candidates=<hits> confirmed=<real hits> \
       branch=<branch> note="<the command, and what the ban protects>"
     ```

   - After the review loop returns `converged` or `deferred` and Automated Verification is green, dispatch a `coder` to change the phase's `## Phase Status` line from `- [ ] Phase N: ...` to `- [x] Phase N: ...` and nothing else, and wait for it.
   - **Phase-boundary decision**, first match wins, then print the matching Phase-Complete Block:
     1. Last phase → STOP, block C.
     2. Phase 1, any risk tier → STOP, block B.
     3. A gate needed an exception, a `/fix` loop hit its cap, the coder flagged an ambiguity, or a plan change awaits sign-off → STOP, block B.
     4. `(risk: high)`, or no risk tag → STOP, block B.
     5. The next phase's Phase Status line carries `— gate:` → STOP, block B, naming the condition. A resume or a start for that phase whose task text already holds the release (who sent it, when, and the words verbatim from the user's or outside session's own message) is no stop: dispatch the phase in one step with `--gate-evidence` (step 3).
     6. `(risk: low)` with all machine gates green → AUTO-ADVANCE, block A, then re-enter step 2 for the next phase in-session.
   - One phase or no phase headers → a single dispatch, still after the acceptance-criteria check.

3. **Dispatch the coder**: one `coder` subagent for the whole phase, whatever layers it touches. Two coders in parallel only for two deliverables that share no contract, type, or file, split by deliverable. Name the phase ("implement Phase N of `<plan-path>`") and tell the coder to read it phase-scoped. The coder writes the phase's tests. If the task turns out architectural, have the coder report back and recommend `/eng-spec`.

   Before the dispatch, run `git rev-parse HEAD` and keep the sha as the phase base. Then, from the repo root, run `python3 ~/.claude/scripts/code/gate_commands.py <plan> <N>` (`-` as `<plan>` and `1` as `<N>` with no plan file) and set the hand-back gate with its lines: `python3 ~/.claude/scripts/code/coder_gate.py set <command>...`, each output line one quoted shell command. With no output lines, skip `set`. `set` refuses a whole-suite command; drop that command and set the rest.

   Then run `python3 ~/.claude/scripts/code/coder_packet.py <plan> <N>` and put its whole output in the coder's prompt, below the phase line. For a gated phase whose release the task text holds, add `--gate-evidence "<who>, <when>: <quoted text>"` to that command: the packet then opens with the evidence, and the coder does not ask for the release again. With no plan file (a plain task or a pasted plan), skip `coder_packet.py` and put the task text in the coder's prompt in place of the phase line. Wait for the coder.

   When the coder hands back, run `python3 ~/.claude/scripts/code/coder_gate.py clear` before anything else.

4. **After the coder completes**: put any `PLAN-IMPACT:` block in its report on the phase-end list and go on. Then summarize: what was implemented, issues flagged, follow-up items, and the coder's `WHY:` lines grouped by file as `path:start-end — <note>` (omit when every coder reported `WHY: none`).

5. **Dispatch review**: first build the handoff block per `~/.claude/skills/_shared/handoff-block.md`: `files` (path, one-line change, `why` from the coder's WHY lines), `tests-run` from the coder's report, `flagged` (or `none`), `plan_impact` (the block, marked `deferred to phase end`, or `none`), `iter: 0`. Never dispatch without it. Write the handoff block to `<run folder>/handoff.txt`, and from the repo root run `python3 ~/.claude/scripts/code/code_review_start.py <lane> <plan path> <N> <run folder>/handoff.txt --base <phase base> --detach`. With no plan file (a plain task or a pasted plan), pass `-` as `<plan path>` and `1` as `<N>`. Do not dispatch an agent. Then run `python3 ~/.claude/scripts/code/code_wait.py review` from the repo root with the Bash timeout set to 600000, again while it prints `Still working`. Its output holds the review packet.

   Route on the packet's `status`, first match wins:

   - `plan-impact` → put its impacts on the phase-end list. In `<run folder>/handoff.txt`, set `plan_impact` to the one line `RESOLVED: deferred to phase end by the session, <date>: <one-line impact summary>` and write no block after it. Set both counters (`iter`, `spec_iter`) and run `code_review_start.py` again the same way. When a second `plan-impact` packet names the same impact, STOP and leave that impact on the phase-end list.
   - `critical-blocker` → STOP. Present `blockers`; do not mark the phase done.
   - `cap-reached` → STOP. Report `findings_remaining`; do not mark the phase done.
   - `deferred` → render as `converged`, plus `findings_remaining` under `### Deferred to branch exit`; proceed.
   - `converged` → put any plan impacts the packet lists on the phase-end list. Then render the packet (`### Fixed` from `fixed[]`, blockers first and marked; `perf[]` under its own heading; `skipped_fp[]`, `nit[]`). `nvim-jump` `ask[]` per `~/.claude/skills/_shared/nvim-jump.md` (each at its `file_line`, `--note` = its question), then present it as a STOP; when `ask[]` is empty, proceed to the phase gates at once. On resume, dispatch a `coder` for the accepted asks and wait for it, then log one row per ask:

     ```bash
     bash "$HOME/.claude/skills/review/log-review-finding" kind=finding \
       repo="$(basename "$(git rev-parse --show-toplevel)")" branch="$(git branch --show-current)" \
       lane=<lane> scope=phase phase=<N> iter=<returned iter> \
       gate=<entry gate> disposition=ask class=<entry class> file=<path> line=<n> \
       actioned=ask ask_outcome=<accepted|rejected|modified> desc="ask resolved: <one line>"
     ```

     Then proceed to the phase gates.

6. **Multi-phase plans**: after `converged` or `deferred`, settle the phase-end plan impacts, then run the phase-boundary decision (step 2). Any other status is a STOP. On a STOP, print the block with every placeholder resolved and end the run; when the user confirms on resume, re-enter step 2 for the next phase using `## Phase Status`. On an AUTO-ADVANCE, print block A and re-enter step 2 at once for the next phase in the same run.

## Phase-Complete Block

Deliver every block through the `brief` skill's shape (`~/.claude/skills/brief/SKILL.md`).

**A — Auto-advance** (decision rule 5):

```
Phase <N> complete — machine gates green (review ✓, execution ✓, automated-verification ✓). Risk: low. Manual verification: <n> agent-verified, <m> human-only deferred to the /verify packet.
→ Auto-advancing to Phase <N+1> in-session (no /clear; interrupt anytime).
```

**B — Stop for sign-off** (decision rules 2–4):

```
Phase <N> complete. Risk: <high | low — Phase 1 calibration | low — exception>. Phase-level sign-off requested.

Behavior delta (observable change + its proof, max 3 — no internals, no paths):
- <before → after, user-visible>. See it: <test name / command / UI flow>.

Plan changes adopted (no criterion changed):
- <deviation line>

Plan changes awaiting sign-off (criterion changes, not applied):
- <assumed → found → what changes>

Read first (/stage queue, blast-radius order):
  ESCALATE:
  - <path> — <classifier reason>
  READ / SKIM:
  - <path>
Staged mechanically (<n>) — invariant-verified, skip.

Agent-verified (evidence in the plan):
- <item — one-line evidence summary>

Human-only verification remaining:
- <item>

Next:
  1. Read the queue (`]k`/`[k` in nvim); spot-check the evidence lines; run the human-only items.
  2. Stage what you've read, then run /clear and /code to start Phase <N+1> fresh. To keep this context, confirm here.

Or give feedback now for revisions to Phase <N>.
```

Omit either plan-change list when it is empty.

**C — Last phase** (decision rule 1): block B's walkthrough and verification lists, with the "Next" block replaced by:

```
All phases complete. Next: /verify (completeness + review packet; includes the remaining human-only checks), then you open the PR.
```

Verification items come from the just-finished phase's `#### Manual Verification:` section, split by the `agent-verified` / `human-only` tags. When that section is empty, omit both lists and replace step 1 with "Read the /stage queue."

Skill-invoke `/stage` to build the "Read first" queue and render it verbatim, in its order. The behavior delta comes from the coder's handoff (absent one, derive it from the diff and mark `derived from diff`).

## Task

$ARGUMENTS
