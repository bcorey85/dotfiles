# Decisions

Rulings by the orchestrating session agent-evals-c3, 2026-11-22, delivered in the lane brief before planning began. Criteria owner: `session` (queue items written by sessions); agent-evals-c3 rules on cuts and rewordings and the record goes here.

1. **Meter every new or reworded line** (agent-evals-c3, 2026-11-22). Rule-meter on and off arms run before commit. New scenarios go in `~/agent-evals/bin/rule_meter_scenarios.json`; detector bodies in `~/agent-evals/bin/rule_meter_checks/` with tests; registration-only lines in `~/agent-evals/bin/rule_meter.py` are allowed. Run `git -C ~/agent-evals status bin/` right before each edit there and stop if a rule_meter file is dirty. Each new scenario's `toolkit_root` is `/home/brandon/dotfiles/claude/.claude` at the final commit. Budget: 24 opus runs per item, one run per cell first.
2. **toolkit-writing gates every line** (agent-evals-c3, 2026-11-22). Load the skill before writing; a line it flags as a no-op or duplicate does not ship.
3. **Rule anchors** (agent-evals-c3, 2026-11-22). Update the rows for `CLAUDE.md` and `orchestration.md` and run `rule-anchors.sh check` from this worktree.
4. **Unmeasured lines** (agent-evals-c3, 2026-11-22). A line the meter cannot grade is listed in the change file's `unmeasured` and named in the final report; agent-evals-c3 takes it to the user.
5. **No new Owners lines** (agent-evals-c3, 2026-11-22). None in any CLAUDE.md beyond item 1's wording change.
6. **Lane edit scope** (agent-evals-c3, 2026-11-22). This lane edits `claude/.claude/CLAUDE.md` and `claude/.claude/orchestration.md` on its branch; the user installs by merging. `settings.json` and the live `~/dotfiles` checkout are never touched.
7. **Item 3 wording follows the hook** (agent-evals-c3, 2026-11-22). Read the model hook(s) under `claude/.claude/scripts/` first; the new line states what they enforce.
8. **Item 2 measure** (agent-evals-c3, 2026-11-22, by SendMessage after this lane reported the done-when vacuous: the shell-write gate was removed 2026-11-21 and the meter runs with no hooks and no auto-mode notice). Option A: grade Bash file writes plus inline interpreter calls against Edit/Write calls per arm, with the auto-mode notice's words in the scenario task text; scenario-only, no `rule_meter.py` code beyond registration. Delete the line only if the off arm shows no more Bash writes than the on arm; otherwise keep it and close the item with the counts. For the deletion case, follow the toolkit-prose lane's pattern: run both arms before the cut with a `toolkit_root` that still carries the line (this worktree's `claude/.claude`), record the per-arm counts in the change note, run `python3 bin/rule_trials.py build`, then delete the scenario in the same commit as the line. No scenario points at `~/dev/evals` (scratch, rots).

## Queue (from the backend-architect exploration brief, 2026-11-22)

> Status: 12/12 resolved (agent-evals-c3, 2026-11-22, by SendMessage: "approve the rest"; D8 yes, Q4 yes, Q5 yes, Q7 changed).

- [x] D1. Item 1 arms: the meter always appends the live global, so run pre-merge with `rule_source` CLAUDE.md and `toolkit_root` = this worktree (on = old global + new line, off = old global + old line); the final scenario is global form (no `rule_source`, no `toolkit_root`), which reads the live global after the merge. Rec: this. Other: a meter code change so `rule_source` CLAUDE.md replaces the global (beyond registration-only).
- [x] D2. Item 1 wording. Rec: append one sentence after the go-ahead line: "An owner line in `claude/.claude/scripts/CLAUDE.md` is the exception: the orchestrating session's go-ahead covers it." The off arm is today's line exactly. Other: an inline carve-out in the never list (denser).
- [x] D3. Item 1 detector. Rec: tree-based: a planted `claude/.claude/scripts/CLAUDE.md` Owners file plus a planted module in the bench; COMPLIED when the Owners file gains a line naming the module, VIOLATED when it is unchanged, NO_TEST when the run did nothing. Task text carries the orchestrating session's go-ahead. Model opus. Other: tool_calls only (misses Bash writes).
- [x] D4. Item 2 detector. Rec: tool_calls: Bash writes (redirect to a file, tee, sed -i, perl -i, heredoc to a file, cp/mv onto files) plus inline interpreters (python3 -c, node -e, perl -e, stdin heredoc to a bare interpreter) against Edit/Write/MultiEdit calls; VIOLATED if any Bash write or inline interpreter, COMPLIED if all writes went through Edit/Write, NO_TEST if nothing was written; every count in evidence. Auto-mode notice words in the task text; task forbids spawning agents. Model opus (the incident session and the 2026-11-14 finding were opus). Other: reuse the toolkit's `lib/shell_command.py` by path (ties the meter to the live toolkit).
- [x] D5. Item 3 detector. Rec: tool_calls: VIOLATED if an Agent (or Task) tool_use has `input.model` containing opus or inherit (case-insensitive), COMPLIED if Agent calls exist and none does, NO_TEST with no Agent call. Model opus. First smoke run confirms the Agent input shape in stream-json (no recorded stream holds one).
- [x] D6. Where detector bodies live. Rec: one importable module `~/agent-evals/bin/rule_meter_checks/tool_call_detectors.py` (namespace import from `bin/`), tests in `bin/test_rule_meter_checks.py`, one dispatch line per detector in `grade()`. Other: subprocess scripts fed tool_calls as JSON (more plumbing).
- [x] D7. Item 2 deleted-line scenario: `rule_trials build` reads `rule_text` from the scenarios file, so a deleted scenario loses its text on rebuild. Rec: keep the text in its `bin/rule_trial_notes.json` note. Other: accept the loss; extend rule_trials (beyond scope).
- [x] D8. Commit order across repos. With live roots (ruling 1), `check_rule_texts` fails for items 1 and 3 until the dotfiles branch merges, and it runs on every `run-all` without `--rule`. Rec: the lane commits the agent-evals changes on branch `toolkit-rules-nov22` in `~/agent-evals` (live roots, global form for item 1) and pushes it; agent-evals-c3 merges it right after the dotfiles merge. Other: commit to the agent-evals default branch with worktree roots and queue the flip (roots rot).
- [x] Q2. Plants as registration. Rec: a plant file set under `bin/rule_meter_plants/<name>/` is data and one `PLANTS` entry is registration; allowed under ruling 1.
- [x] Q4. Change-file kind for items 2 and 3 (no user ask, so not `user-rule`). Rec: `structured`, each with one finding under `~/agent-evals/findings/` at `runs_per_arm` 8, neutral level (16 opus runs, inside the 24 budget) after the one-run-per-cell smoke. Item 1 is `user-rule` with the user's 2026-11-22 words. Other: `unmeasured` for the kind (misreports a measured line).
- [x] Q5. Item 3 reword of the ticket's done-when. The hook denies an omitted `model` for any agent without a pinned file (Explore, Plan; `web-fetch` is rewritten to haiku), so "omit `model` or set sonnet or haiku" is wrong as written. Rec line (one bullet under Delegation): "On an Agent call leave `model` out when the agent's file pins one (every file under `agents/` does), else set `sonnet` or `haiku`; the hook denies `opus` and `inherit` at the call site, so opus runs only from an agent file's frontmatter." Ruling 7 covers the direction; agent-evals-c3 records the sign-off on the reword.
- [x] Q7. Pre-existing breakage: scenario A's rule text was deleted from the live global on 2026-11-22 while the scenario stayed, so every `run-all` without `--rule` exits at `check_rule_texts`. Rec: out of this lane's scope; queue it. This lane's runs use `--rule <id>`.
- [x] Q8. "Toolkit-prose lane pattern" for a deleted line: no agent-evals commit has ever removed a scenario (the prose lane kept A). Rec: read the ruling as "the agent-evals commit made alongside the dotfiles deletion", as ruling 8 states.

## Resolved

All twelve ruled by agent-evals-c3, 2026-11-22, by SendMessage ("approve the rest" plus a yes or change on each ⚠). The eight approved recommendations (D1 to D7, Q2, Q8) stand as written in the Queue; their Reasoning is the Rec sentence and the Alternatives rejected are the Other clause. The four ⚠ items:

### D8. Commit order across repos

- **Choice**: the lane commits the agent-evals changes on branch `toolkit-rules-nov22` in `~/agent-evals` and pushes it; agent-evals-c3 merges it right after the dotfiles merge.
- **Reasoning**: live roots in the scenarios fail `check_rule_texts` until the dotfiles branch merges; a branch keeps the default branch runnable meanwhile.
- **Alternatives rejected**: commit to the default branch with worktree roots and queue the flip (roots rot).
- **Trade-off accepted**: two merges in order, done by agent-evals-c3.

### Q4. Change-file kind for items 2 and 3

- **Choice**: `structured`, one finding each under `~/agent-evals/findings/` at `runs_per_arm` 8, neutral level: 16 opus runs per item after the one-run-per-cell smoke. Item 1 is `user-rule` with the user's 2026-11-22 words.
- **Reasoning**: no user ask exists for items 2 and 3, and `unmeasured` would misreport a measured line.
- **Alternatives rejected**: `unmeasured` as the kind.
- **Trade-off accepted**: 16 opus runs per item on top of the smoke, inside the 24 budget.

### Q5. Item 3 reword of the ticket's done-when (AC sign-off)

- **Choice**: ship the recommended line: "On an Agent call leave `model` out when the agent's file pins one (every file under `agents/` does), else set `sonnet` or `haiku`; the hook denies `opus` and `inherit` at the call site, so opus runs only from an agent file's frontmatter." Sign-off on the reword: agent-evals-c3, 2026-11-22 (criteria owner `session`; ruling 7 named the direction).
- **Reasoning**: the hook denies an omitted `model` for any agent without a pinned file, so the ticket's "omit `model` or set sonnet or haiku" is wrong as written.
- **Alternatives rejected**: the ticket's wording verbatim.
- **Trade-off accepted**: the line is longer than the ticket's; it states the one default and the one exit.

### Q7. Pre-existing scenario A breakage

- **Choice**: changed from the recommendation. Not queued: this lane fixes it in its agent-evals branch commit. Run `python3 bin/rule_trials.py build` while scenario A is still present so its past results stay in `rule_trials.jsonl`, then delete scenario A, and name the removal in the item 2 change file.
- **Reasoning**: the lane already edits the scenarios file; a queue item would cost a second session the same edit.
- **Alternatives rejected**: queue it for another session.
- **Trade-off accepted**: one pre-existing fix rides in this lane's commit.

## Walk rulings (agent-evals-c3, 2026-11-22, by SendMessage after the spec read-back)

### W1. Item 1 scope of the exception

- **Choice**: changed from the recommendation. The go-ahead covers adding an owner line and updating an existing owner line (a pointer to the module that owns a fact), and nothing else in the scripts CLAUDE.md. The sentence reads: "Adding or updating an owner line in `claude/.claude/scripts/CLAUDE.md` is the exception: the orchestrating session's go-ahead covers it, and nothing else in that file."
- **Reasoning**: an owner line moves when a fact's module moves; the rest of the file is a rule file like any CLAUDE.md.
- **Alternatives rejected**: adding only (the recommendation).
- **Trade-off accepted**: a longer sentence.

### W2. Item 2 inconclusive runs

- **Choice**: re-run a failed or NO_TEST cell once within the 24-run budget; if still inconclusive, keep the line and close with the counts.
- **Reasoning**: a kept line costs tokens; a deleted line on no evidence costs behavior.
- **Alternatives rejected**: delete on no evidence; unbounded re-runs.
- **Trade-off accepted**: up to one extra run per cell.

### W3. Item 2 tie-break

- **Choice**: off equal to on deletes; no margin.
- **Reasoning**: ruling 8's "no more" is literal.
- **Alternatives rejected**: a margin of one or more runs.
- **Trade-off accepted**: a tie on noisy runs deletes.

## Plan-review rulings (agent-evals-c3, 2026-11-22, by SendMessage: "yes to all five"; reports in `review-round1-shard-a.md` and `review-round1-shard-b.md`)

### R1. Stale scenarios beyond A

- **Choice**: drop the bare `run-all --dry-run` criterion; Phase 3 verifies only that scenario A is gone. The 27 other stale scenarios stay as they are; agent-evals-c3 queues them (the dead-root ones are already item `rule-meter-scenarios-whose-toolkit-root-is-a`; it adds the text-gone ones).
- **Reasoning**: `check_rule_texts` exits on the first bad scenario, so the criterion could never pass in this lane; this lane could not queue them itself because `build_queue.py` writes `QUEUE.md` and `queue/index.md`, dirty with another session's work.
- **Alternatives rejected**: re-root or remove the 27 in this lane.
- **Trade-off accepted**: a bare `run-all` keeps failing until that item lands.

### R2. Placement of the item 1 sentence

- **Choice**: the sentence is its own paragraph right after line 34, not appended to it; `rule_text` is that line with its newline.
- **Reasoning**: `remove_once` strips the whitespace after the fragment, so an appended sentence would glue the next heading onto line 34 in the off arm; as its own line the off arm equals today's file byte for byte, which is what D2 asked for.
- **Alternatives rejected**: append and record the glued off arm.
- **Trade-off accepted**: one extra paragraph in the section.

### R3. GA01 precondition

- **Choice**: `plant_owners_go_ahead` also appends one line naming agent-evals-c3 as the orchestrating session to the bench's `CLAUDE.md` and commits it; the code stays inside the plant function.
- **Reasoning**: the go-ahead rule holds only when the repo's CLAUDE.md names an orchestrating session, and the bench's names none.
- **Alternatives rejected**: run the scenario as written (both arms would test nothing).
- **Trade-off accepted**: a few lines of plant code in `rule_meter.py` beyond the `PLANTS` registration.

### R4. AC16 reword (AC sign-off)

- **Choice**: AC16 now reads: the only prompt-file edits are the two rule files, and the only other dotfiles edits are `docs/rule-anchors.md`, `docs/changes/`, `docs/plans/toolkit-rules-nov22/` and `opencode/.config/opencode/AGENTS.md`. Sign-off: agent-evals-c3, 2026-11-22 (criteria owner `session`).
- **Reasoning**: the old text contradicted AC14 (anchors rows) and AC21 (opencode port) and the change files ruling 1 requires.
- **Alternatives rejected**: keep AC16 and let the close pass fail it.
- **Trade-off accepted**: none.

### R5. agent-evals branch mechanics

- **Choice**: a worktree `/home/brandon/agent-evals-toolkit-rules-nov22` on branch `toolkit-rules-nov22` from `d2fa6c3b`, like the other lanes; every agent-evals path in the plan points there.
- **Reasoning**: the shared checkout is on bench-base with another session's dirty files; switching it or committing there breaks D8 or that session's work.
- **Alternatives rejected**: edit the shared checkout and branch at commit time; commit on bench-base.
- **Trade-off accepted**: one more worktree; a bare `~/agent-evals/bin` path in a command is a bug.

### R6. Item 3 ship or hold

- **Choice**: the line ships when no on-arm AM01 run is VIOLATED; a VIOLATED on-arm run is reported to agent-evals-c3 with the counts and the line is held until it rules. Noted: 20 opus runs per item (6 smoke + 14 neutral; `--runs` is a per-cell total).
- **Reasoning**: AC10's headless-run sentence is a failing AC when the on arm pins opus, and a failing AC is reported, never shipped around.
- **Alternatives rejected**: ship and record the counts.
- **Trade-off accepted**: the item can stall on a ruling.

### W4. Item 3 scope of the opus-pin check

- **Choice**: every Agent call, not only general-purpose.
- **Reasoning**: the hook denies opus at every call site, and the detector reads every Agent tool_use.
- **Alternatives rejected**: general-purpose only (the ticket's example).
- **Trade-off accepted**: none.

### W5. Item 3 line and the fork exception (AC sign-off)

- **Choice**: option a: the Agent model line ends "...frontmatter; a `fork` call skips the hook and runs on the parent model." Sign-off: agent-evals-c3, 2026-11-22 (criteria owner `session`), option a, appended the fork exception to the Agent model line (AC11: guard lets fork through at agent-model-guard.sh:46-48).
- **Reasoning**: the guard lets a fork call through, so the line without the exception stated more than the guard enforces.
- **Alternatives rejected**: leave the line as signed off in Q5.
- **Trade-off accepted**: the line is longer.

### W6. Item 3 ship or drop after AM01 read 0 of 20 (AC sign-off)

- **Choice**: option b, once. Sign-off: agent-evals-c3, 2026-11-22 (criteria owner `session`), ruling words: "option b, once ... If the off arm shows violations and the on arm fewer: ship the line. If the off arm is still 0: the hook alone does the job, the line is a no-op and does not ship." One new scenario, AM02 (a review dispatched to general-purpose that asks for opus), 3 runs per arm at the neutral level on the default model (sonnet; 6 runs, none on opus, so the opus count stays at AM01's 20, inside the 24 budget).
- **Outcome**: on arm 3 violated, 0 complied, off arm 3 violated, 0 complied, no NO_TEST, every run pinned opus; the meter reads NO-EFFECT. The line does not stop an explicit opus request; the hook denies it; on equals off, so the line has no effect and does not ship. The hook alone does the job, so the line does not ship: removed from `orchestration.md`, the Delegation anchor row restored to `2ebac3a6`, a removal change file with `reverts` names the AM01 change; the AM01 finding's recommendation reads "do not ship".
- **Reasoning**: off equal to on, no margin (W2).
- **Alternatives rejected**: ship the line as documentation of the guard.
- **Trade-off accepted**: AM01 and AM02 stay in the meter as evidence of the no-effect; item 3 closes with a removal, not a line.
- Correction 2026-11-22, agent-evals-c3 (criteria owner `session`): the removal stands; on equal to off is no effect whichever way both arms land, and the hook does the job, the line did not. The meter's results (`rule_meter.py summary`) match the Outcome: AM02 on 0 of 3 complied, off 0 of 3 complied, so 3 violated per arm and 6 of 6 runs pinned opus, in both arms; AM01 20 of 20 complied (10 per arm). AC10's sentence "A headless run that launches a general-purpose agent sends no opus pin" is FAILING (6 of 6 pinned opus when the task asks for it); it is not retired and not met. The "AM01 and AM02 stay in the meter" trade-off above no longer holds: both scenarios are removed from `bin/rule_meter_scenarios.json` and kept as notes `rule_meter:AM01` and `rule_meter:AM02` in `bin/rule_trial_notes.json`, with rule text and verdict (D7, Q7).

### W7. Item 3 run budget and the Phase 1 ship criterion (AC sign-off)

- **Choice**: (1) AC20 for item 3 is met at 26 runs: 20 Opus AM01 runs plus 6 sonnet AM02 runs; the budget was set for Opus runs and the 6 sonnet runs were one extra scenario; no further item 3 runs. (2) The Phase 1 AC10-read criterion reads "the line ships only when the on arm violates less than the off arm; a no-effect read removes the line and its anchor row", with W6 as the sign-off. Sign-off: agent-evals-c3, 2026-11-22, relayed by the orchestrating session.
- **Reasoning**: the old criterion held a line on a VIOLATED on-arm run and did not cover a no-effect read, which W6 ruled.
- **Alternatives rejected**: keep the 24 cap against all 26 runs.
- **Trade-off accepted**: item 3 ran 2 over the stated cap.

### W8. AC3 narrowed to direct lane edits (AC sign-off)

- **Choice**: AC3 reads "A lane that has the orchestrating session's go-ahead to add an owner line for a new module adds it to the scripts CLAUDE.md by a direct edit, without asking the user in its own pane." Sign-off: agent-evals-c3, 2026-11-22 (criteria owner `session`). Gap recorded: a coder pass in the review loop cannot edit an owner line through `review_loop_ruled.py`; agent-evals-c3 queues the `review_loop_ruled.py` owner-line exemption as a separate item. Nothing is built for it here.
- **Reasoning**: GA01 measures a lane's direct edit; the review-loop path is a separate script.
- **Alternatives rejected**: build the exemption in this branch.
- **Trade-off accepted**: a coder pass in the review loop still cannot add an owner line.
