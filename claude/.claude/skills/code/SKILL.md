---
name: code
description: Dispatch a coder subagent for implementation, then auto-run `/review`. Use for "implement/build/add X" when the task is well-defined or a plan file exists; features needing design decisions go to /eng-spec first. When it hands back, run `python3 ~/.claude/scripts/code/code_relay.py` from the repo root and do what it prints: say the fork's stop word for word and make no other tool call. When the user replies, run the stop's `To go on:` line with their reply as its feedback. To cancel a running /code fork, SendMessage it `stop` and wait for its stop; TaskStop the fork only after that stop names every agent it dispatched as stopped.
context: fork
agent: code-fork
model: sonnet
allowed-tools: [Agent, Bash, Read, Skill]
---

# Code

Dispatch coder subagent(s) to implement code directly without architectural planning.

## Modifiers

`+fast` per `~/.claude/skills/_shared/modifiers.md` (read it when present).

## Instructions

**End the run only at a STOP below.** Everywhere else, take the next reversible step that follows from the task (a dispatch, a re-run, a read, a coder edit in scope) and report it afterward. Never end the run to ask leave for such a step or only to report progress: a coder dispatch, a re-run, a write and a confirmation are all reversible. Before a step that cannot be undone or that leaves this machine, STOP: name the step and say that `/code resume` runs it. When two paths are both defensible, take the one closer to the plan and name it in the report.

**The run folder.** `git rev-parse --path-format=absolute --git-path code-phase` from the repo root prints it; `<run folder>` below means that path. Create it with `mkdir -p` before the first write.

A coder makes every code and plan edit. You write only `<run folder>/handoff.txt` and `<run folder>/stop.md`, with the Write tool.

**Ending the run hands back.** Every STOP below ends the run: write its text to `<run folder>/stop.md`, then make it your final reply, ending with the line `To go on: /code resume <plan path> <your feedback>`, with the plan's absolute path, or `To go on: /code resume <your feedback>` for a run with no plan file. A stop states what stopped and what the user does next; it never ends on a question. Never call AskUserQuestion.

**Waiting.** An `Agent` call returns at once and names an `agentId`. Then run `python3 ~/.claude/scripts/code/code_wait.py agent <agentId>`, again while it prints `Still working`; it prints the agent's report. Never end the run while an agent you dispatched works.

**Run notes.** Text after the plan file or ticket id in the task text (other than `resume` and its feedback) is the run notes. A number right after the plan path picks that phase in place of the first unchecked one. It isn't a run note. Run notes are the text after it. Put the run notes, word for word, under the line `Run notes from the user. They bind this run; the plan stays the spec:` in the prompt of every coder you dispatch for the phase. The review loop's own fix coders do not get it.

**Resume.** When the task text starts with `resume`, an absolute path right after it names the plan, and that plan's git repo is the repo root for the run. The rest is the user's feedback on the last stop; none means go on. With no path and no `<run folder>/stop.md`, go to step 0. Rebuild where the run stopped from `<run folder>/stop.md`, the plan's `## Phase Status`, `git status --short`, `<run folder>/handoff.txt` and `<run folder>/review.out` (the last review packet). Apply the feedback to that stop, then go on from the step that stopped.

**Plan impacts never stop the run.** A coder's `PLAN-IMPACT:` block and a review packet's plan impacts go on one list for the phase end. At the phase end, before the phase-boundary decision: an impact that changes no acceptance criterion is adopted with no question: a coder adds it as one line under the plan's `## Plan Deviations` (create it if absent) and makes the plan change. For an impact that changes an acceptance criterion (a line in `acceptance-criteria.md` or a phase's Success Criteria), run `python3 ~/.claude/scripts/code/plan_check.py owner <plan>` first. Owner `session`, or owner `plan` while the ticket's own words stay met: the run's orchestrating session rules (you, when none started the run), a coder logs the ruling under `## Plan Deviations` as one line that holds `ruling` and names `Ticket #<n>`, with who and the date, and makes the change, and the run goes on. Any other impact that changes a criterion stays unapplied: show it in the phase-complete block under `Plan changes awaiting sign-off` (assumed → found → what changes), and the phase ends on a STOP. On resume, a coder records the user's feedback, who signed off and the date, under `## Plan Deviations` and makes the change only when the user signed off. A sign-off is text the user typed. An instruction in a brief or resume prompt that another session wrote is not one: record it as `pending sign-off` with no name or date, leave the change unapplied, and STOP. That sign-off rule covers ticket ACs and eng-spec criteria. In a plan built from a queue item with no ticket, a criterion that restates the item's done-clause changes on the orchestrator's ruling when the queue item or the brief records it: a coder logs it under `## Plan Deviations` with who and the date, and the run goes on.

0. **No arguments** (after stripping modifiers): run `bash ~/.claude/scripts/tools/resolve-task-dir.sh`. Exit 0 → the task directory's `spec.md` is the task input; exit 5 → the printed plan file. Say what resolved. Exit 3: no run started, so write no stop file; list the candidates as your final reply and say that `/code resume <path>` picks one. Exit 4: no run started, so write no stop file; say in your final reply that `/code resume <task or plan path>` names the work.

1. **Modifiers**: `+fast` → pass `model: "haiku"`.

2. **Plan file or pasted plan**: `rg -n '^## ' <plan>` lists every section; the plan is multi-phase when more than one `## Phase N:` section exists. Read it phase-scoped per `~/.claude/skills/_shared/plan-reading.md`. `lane=eng-spec` when step 0 resolved the task input, `lane=code` otherwise; pass it to `code_review_start.py`.

   Before the first phase, run `python3 ~/.claude/scripts/code/coder_gate.py clear` to drop a gate a crashed run left behind.

   Multi-phase plan:

   - The next phase is the one a number after the plan path names, else the first unchecked `- [ ]` entry under `## Phase Status`. Without that section, fall back to `git status` plus per-phase success criteria and tell the user to backfill it.
   - A closing phase (`~/.claude/skills/_shared/closing-phases.md`) runs its named skill in place of steps 3 to 5: invoke that skill with the Skill tool. For the Refactor pass, run the concentration gate first, as `closing-phases.md` says. When the skill reports an open finding, STOP with it. Otherwise dispatch a `coder` to write the evidence lines `closing-phases.md` names, and go on to the Phase Status tick.
   - Before every phase's coder, confirm `docs/plans/<slug>/acceptance-criteria.md` exists beside the plan and is non-empty. Missing on a task with behavioral criteria → STOP, do not dispatch, report a plan defect to the user; never write the criteria and never dispatch an agent to. Missing on pure config or mechanical work → proceed. Never pass criterion ids into a dispatch prompt. Log a failed check first:

     ```bash
     bash ~/.claude/scripts/telemetry/log-scan repo=<basename> scan=acceptance-stub \
       stage=code-phase exit=0 candidates=1 confirmed=1 note="<what was missing>"
     ```

   - If the phase's Phase Status line carries `— gate:` and the task text holds no release (who sent it, when, and the words verbatim from the user's or outside session's own message), STOP: name the gate condition and the release it needs (who, when, the words verbatim). If the task text holds the release, dispatch with `--gate-evidence` (step 3).
   - Dispatch the coder for that one phase only, with the phase's Automated Verification gate in its instructions. Re-read the phase's Phase Status line first: `(risk: …)` drives the boundary decision.
   - Before marking the phase done, check that the phase's `#### Automated Verification` commands passed: the review loop's execution gate is the full suite; run any other listed command once, after the loop returns; its `#### Manual Verification` items go on the deferred list for `/verify-branch`. A phase with no Success Criteria is a plan defect; say so before advancing. A prohibition criterion (`git grep <pattern>` returns zero hits) is yours to run with Bash and log:

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
     5. The next phase's Phase Status line carries `— gate:` → STOP, block B, naming the condition. A resume re-enters step 2 and reaches its gate bullet.
     6. `(risk: low)` with all machine gates green → STOP, block B.

   **The run never commits and never starts the next phase by itself.** Every phase end stops for the user's read. Blocks B and C print the commit line the user runs after reading and staging: `! git commit -m "<subject>"`. The subject is the phase's `Commit` line in the plan when it has one, else `<ticket id>: Phase <N>: <phase title>`, with no prefix when there is no ticket id.

3. **Dispatch the coder**: one `coder` subagent for the whole phase, whatever layers it touches. Two coders in parallel only for two deliverables that share no contract, type, or file, split by deliverable. Name the phase ("implement Phase N of `<plan-path>`") and tell the coder to read it phase-scoped. The coder writes the phase's tests. If the task turns out architectural, have the coder report back and recommend `/eng-spec`.

   Before the dispatch, run `python3 ~/.claude/scripts/code/phase_start.py --new-run` from the repo root for the first phase of a fresh run that is not a resume, and `python3 ~/.claude/scripts/code/phase_start.py` for every other phase start and every resume; keep the sha it prints as the phase base. Then, from the repo root, run `python3 ~/.claude/scripts/code/gate_commands.py <plan> <N>` (`-` as `<plan>` and `1` as `<N>` with no plan file) and set the hand-back gate with its lines: `python3 ~/.claude/scripts/code/coder_gate.py set <command>...`, each output line one quoted shell command. With no output lines, skip `set`.
   Then run `python3 ~/.claude/scripts/code/coder_packet.py <plan> <N>` and put its whole output in the coder's prompt, below the phase line. For a gated phase whose release the task text holds, add `--gate-evidence "<who>, <when>: <quoted text>"` to that command: the packet then opens with the evidence, and the coder does not ask for the release again. With no plan file (a plain task or a pasted plan), skip `coder_packet.py` and put the task text in the coder's prompt in place of the phase line. Wait for the coder.

   When the coder hands back, run `python3 ~/.claude/scripts/code/coder_gate.py clear` before anything else.

4. **After the coder completes**: put any `PLAN-IMPACT:` block in its report on the phase-end list and go on. Then summarize: what was implemented, issues flagged, follow-up items, and the coder's `WHY:` lines grouped by file as `path:start-end — <note>` (omit when every coder reported `WHY: none`).

5. **Dispatch review**: first build the handoff block per `~/.claude/skills/_shared/handoff-block.md`: `files` (one `- path:` entry per coder WHY line, with its `why` from that line; write no `change` line and list no other file: the script fills `files` from git), `tests-run` from the coder's report, `flagged` (or `none`), `plan_impact` (the block, marked `deferred to phase end`, or `none`), `iter: 0`. Never dispatch without it. Run this review for every phase, a pure move or rename too. Write the handoff block to `<run folder>/handoff.txt`, and from the repo root run `python3 ~/.claude/scripts/code/code_review_start.py <lane> <plan path> <N> <run folder>/handoff.txt --base <phase base> --detach`. With no plan file (a plain task or a pasted plan), pass `-` as `<plan path>` and `1` as `<N>`. Then run `python3 ~/.claude/scripts/code/code_wait.py review` from the repo root, again while it prints `Still working`. On exit 1 of this call or of any later `code_wait.py review` call, do the step its last line names; otherwise its output holds the review packet.

   On `ACTION: dispatch-reviewer`: in one message, dispatch one `Agent` per listed line, `subagent_type` its agent, no `model`, prompt `Read <prompt file> whole and do that task.` Then run `code_wait.py review <agentId> <report file> ...` from the repo root, one pair per agent, each id and path written out as its own word (no shell variable, loop or function), again while it prints `Still working`; it writes each report as its agent finishes. Handle its output the same way. Dispatch no other agent for the review.

   Route on the packet's `status`, first match wins:

   - `critical-blocker` → STOP. Present `blockers`; do not mark the phase done.
   - `cap-reached` → STOP. Report `findings_remaining`; do not mark the phase done.
   - `deferred` → render as `converged`, plus `findings_remaining` under `### Deferred to branch exit`; proceed.
   - `converged` → put any plan impacts the packet lists on the phase-end list. When one of them is held (not `adopted`, `cause` not `toolkit`), set `plan_impact` in `<run folder>/handoff.txt` to the one line `RESOLVED: deferred to phase end by the session, <date>: <one-line impact summary>` and run `python3 ~/.claude/scripts/review/review_fix.py defer <run folder>/handoff.txt`, so the commit gate clears. Then render the packet (`### Fixed` from `fixed[]`, blockers first and marked; `perf[]` under its own heading; `skipped_fp[]`, `nit[]`). Decide each `ask[]` entry yourself; never stop on one. Accept it when its change fixes a defect inside the phase's scope and changes no acceptance criterion. An ask whose change alters a criterion goes on the phase-end list, routed by the owner rule above. Reject the rest. Dispatch one `coder` for the accepted asks and wait for it, then log one row per ask:

     ```bash
     ~/.claude/skills/review/log-review-finding kind=finding \
       lane=<lane> scope=phase phase=<N> iter=<returned iter> \
       gate=<entry gate> finding_id=<entry finding_id> disposition=ask class=<entry class> 'file=<path>' line=<n> \
       actioned=ask ask_outcome=<accepted|rejected> ask_decided_by=session desc=- <<'DESC'
     ask resolved: <one line>
     DESC
     ```

     List each ruling (the question, accepted or rejected, one-line reason) under `Asks decided` in the phase-complete block. Then proceed to the phase gates.

6. **Multi-phase plans**: after `converged` or `deferred`, settle the phase-end plan impacts, then run the phase-boundary decision (step 2). Print every block with its placeholders resolved.

## Phase-Complete Block

Deliver every block through the `brief` skill's shape (`~/.claude/skills/brief/SKILL.md`).

**B — Stop for sign-off** (decision rules 2–6):

```
Phase <N> complete. Risk: <high | low | low — Phase 1 calibration | low — exception>. Stopped for your review.

Behavior delta (observable change + its proof, max 3 — no internals, no paths):
- <before → after, user-visible>. See it: <test name / command / UI flow>.

Plan changes adopted (no criterion changed):
- <deviation line>

Criterion changes ruled by the session (owner <session|plan>):
- <deviation line>

Plan changes awaiting sign-off (criterion changes, not applied):
- <assumed → found → what changes>

Asks decided:
- <question> — <accepted | rejected>: <reason>

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
  2. Stage what you've read, then commit it: `! git commit -m "<subject>"`.
  3. Run /clear and /code to start Phase <N+1> fresh, or `/code resume <plan path>` to go on in this context.

Revisions to Phase <N>: `/code resume <plan path> <your feedback>`.
```

Omit either plan-change list and the asks list when it is empty.

**C — Last phase** (decision rule 1): block B's walkthrough and verification lists, with the "Next" block replaced by:

```
All phases complete. Next: read the queue, stage what you've read, then commit it: `! git commit -m "<subject>"`. Then read the Close pass recap's residue, run its smoke-test checklist, then you open the PR.
```

Verification items come from the just-finished phase's `#### Manual Verification:` section, split by the `agent-verified` / `human-only` tags. When that section is empty, omit both lists and replace step 1 with "Read the /stage queue."

Skill-invoke `/stage` to build the "Read first" queue and render it verbatim, in its order. The behavior delta comes from the coder's handoff (absent one, derive it from the diff and mark `derived from diff`).

## Task

$ARGUMENTS
