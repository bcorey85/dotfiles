# Acceptance Criteria — toolkit-rules-nov22

> Written before implementation. The closing Verify phase reconciles these
> against the test suite.

## Item 1 — go-ahead covers a scripts owner line

- **AC1** — The global go-ahead rule says an owner line in the scripts CLAUDE.md is covered by the orchestrating session's ruling.
  - Walk ruling W1 in `03-decisions.md`: the rule covers adding or updating an owner line, and nothing else in that file.
- **AC2** — Rule-meter on and off arms have run for the reworded rule, with counts in the change file.
- **AC3** — A lane that has the orchestrating session's go-ahead to add an owner line for a new module adds it to the scripts CLAUDE.md by a direct edit, without asking the user in its own pane.
  - Narrowed per W8 in `03-decisions.md`.
- **AC4** — The go-ahead still does not cover master, `settings.json`, any other CLAUDE.md file, or a step a hook denied.

## Item 2 — auto-mode Bash line on file edits

- **AC5** — rule_meter scenario for the line, on and off arms run; the change file records the per-arm counts.
- **AC6** — If the off arm shows no more gate blocks than the on arm, the line is deleted with a change file and its rule-anchors row removed.
  - Walk rulings W2 and W3 in `03-decisions.md`: equal counts delete, no margin; an errored or NO_TEST cell is re-run once within the budget, then the line is kept if still inconclusive.
  - Reworded per ruling 8 in `03-decisions.md`. "Gate blocks" becomes Bash file writes plus inline interpreter calls, counted against Edit/Write calls per arm, with the auto-mode notice's words in the scenario task text. The line is deleted only if the off arm shows no more Bash writes than the on arm; otherwise it stays and the item closes with the counts.
- **AC7** — When the line is deleted, the scenario is deleted in the same agent-evals commit, and both arms ran before the cut against a tree that still carried the line, with per-arm counts in the change note.
- **AC8** — The old scenario A, whose rule text was already gone from the live global, is removed after its past results are kept in the trial record, and the item 2 change file names the removal (Q7 in `03-decisions.md`).
- **AC9** — When the line is kept, the orchestration line and its rule-anchors row are unchanged and the item closes with the counts.

## Item 3 — Agent model rule

- **AC10** — orchestration.md has one line: omit `model` on an Agent call or set sonnet or haiku; opus goes only in the agent file's frontmatter. A headless run that launches a general-purpose agent sends no opus pin.
  - Walk ruling W4 in `03-decisions.md`: the no-opus-pin check covers every Agent call, not only general-purpose.
  - Line not shipped (W6); the headless-run sentence is FAILING per the W6 correction in `03-decisions.md`.
- **AC11** — The Agent model line states exactly what the model hooks under the scripts folder enforce, and no more.
- **AC12** — Rule-meter on and off arms have run for the Agent model line, with per-arm counts of opus or inherit pins in a finding.

## Batch-wide

- **AC13** — Every new or reworded line passed the toolkit-writing check: none is flagged as a no-op or a duplicate of another line.
- **AC14** — The rule-anchors rows for `CLAUDE.md` and `orchestration.md` are updated and `rule-anchors.sh check` passes from the lane's worktree.
- **AC15** — No CLAUDE.md gains an owner line, and the only CLAUDE.md wording change is item 1's.
- **AC16** — `settings.json` and the live `~/dotfiles` checkout are untouched; on the lane branch the only prompt-file edits are `claude/.claude/CLAUDE.md` and `claude/.claude/orchestration.md`, and the only other dotfiles edits are `docs/rule-anchors.md`, `docs/changes/`, `docs/plans/toolkit-rules-nov22/` and the opencode port `opencode/.config/opencode/AGENTS.md`.
  - Reworded on plan-review finding (the old text contradicted AC14 and AC21): R4 in `03-decisions.md`.
- **AC17** — Each new scenario's `toolkit_root` is `/home/brandon/dotfiles/claude/.claude` in the final agent-evals commit, except a scenario for a line being deleted, which is removed.
- **AC18** — The agent-evals changes are on branch `toolkit-rules-nov22` and pushed, not committed to its default branch (D8).
- **AC19** — Any line the meter cannot grade is listed under `unmeasured` in its change file and named in the lane's final report.
- **AC20** — The opus run count stays within 24 per item.
  - AC20 is met at 20 Opus runs for item 3; the 6 sonnet AM02 runs fall outside the Opus count (W7 in `03-decisions.md`).
- **AC21** — The ported copy under `opencode/.config/opencode/` is patched, or the report states it is knowingly skipped, for any line that has a port.

## Manual only

- **AC22** — The user installs by merging the branch and the live global reads the new item 1 sentence afterward; no automated test covers the merge or the post-merge read.
