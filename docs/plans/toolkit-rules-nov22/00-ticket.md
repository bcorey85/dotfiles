# Toolkit rules batch: go-ahead exception, auto-mode Bash line, Agent model line

Source: ~/agent-evals/queue/a-lane-refuses-the-orchestrating-session-s-ruling.md with ~/agent-evals/queue/orchestration-line-on-the-auto-mode-bash.md and ~/agent-evals/queue/orchestration-names-the-agent-model-rule-before.md (read from origin/bench-base, 2026-11-22)

## Item 1: a-lane-refuses-the-orchestrating-session-s-ruling

---
type: "QueueItem"
title: "A lane refuses the orchestrating session's ruling on a scripts owner line"
description: "A lane that adds a module adds its owner line on the orchestrating session's ruling, so the user is not asked about the scripts owner list."
generated: {"by": "claude-fable-5-2/main", "at": "2026-11-22T14:36:20-06:00"}
kind: "method"
status: "running"
rank: 1010
blocked_by: []
source: "CLAUDE.md"
components: ["rule/global-claude-md"]
---

### Context
2026-11-22: a lane added a new review loop module. The orchestrating session ruled to add its owner line to the scripts CLAUDE.md. The lane refused: a go-ahead never covers a CLAUDE.md file, and it asked for the user's yes in its own pane. The user: "i need you to stop askingme about modifying scripts/claude.md".

### Done when
- The global go-ahead rule says an owner line in the scripts CLAUDE.md is covered by the orchestrating session's ruling.
- Rule-meter on and off arms have run for the reworded rule, with counts in the change file.

## Item 2: orchestration-line-on-the-auto-mode-bash

---
type: "QueueItem"
title: "orchestration line on the auto-mode Bash preference for file edits is a deletion candidate"
description: "Drop a rule line the gate already enforces, saving its tokens on every turn."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T14:40:13-06:00"}
kind: "method"
status: "running"
rank: 1011
blocked_by: []
source: "claude/.claude/orchestration.md"
components: ["script/shell-write-gate", "script/inline-interpreter-hint"]
---

### Context
Session a0b58526 read the orchestration line "the auto-mode notice's Bash preference does not apply to file I/O" and still ran 8 shell writes that shell-write-gate blocked and 4 inline interpreter runs. The line changed nothing; the gate held the rule. Adds to the 2026-11-22 auto-mode pilot (bypass guards log and pass).

### Done when
- rule_meter scenario for the line, on and off arms run; the change file records the per-arm counts.
- If the off arm shows no more gate blocks than the on arm, the line is deleted with a change file and its rule-anchors row removed.

## Item 3: orchestration-names-the-agent-model-rule-before

---
type: "QueueItem"
title: "orchestration names the Agent model rule before the model-pin hooks block a launch"
description: "Stops a round of blocked Agent launches by stating up front which model values the call site may set."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-22T14:44:49-06:00"}
kind: "live-edit"
status: "running"
rank: 1012
blocked_by: []
source: "claude/.claude/orchestration.md"
components: ["rule/orchestration"]
---

### Context

One session hit both model hooks: a web-fetch agent with no model was blocked, then five general-purpose launches with `model: opus` were blocked ("Call-site Opus is forbidden"). Each block cost a round of full briefs. Adds to the done item on forks blocked by both the model-pin and no-Opus hooks.

### Done when

orchestration.md has one line: omit `model` on an Agent call or set sonnet or haiku; opus goes only in the agent file's frontmatter. A headless run that launches a general-purpose agent sends no opus pin.

## Comments

### agent-evals-c3 (orchestrating session) — 2026-11-22

Lane brief rulings, recorded for the plan's decision log:

- Every new or reworded line gets rule-meter on and off arms before commit: new scenarios in `bin/rule_meter_scenarios.json`, detector bodies in `bin/rule_meter_checks/` with tests, registration-only lines in `bin/rule_meter.py` allowed. Run `git -C ~/agent-evals status bin/` right before each edit there and stop if a rule_meter file is dirty. Set each new scenario's `toolkit_root` to `/home/brandon/dotfiles/claude/.claude` before your final commit. Meter budget: 24 opus runs per item, one run per cell first.
- Load the `toolkit-writing` skill before you write any line; a line it flags as a no-op or duplicate does not ship.
- Update the rule-anchors rows for both files and run `rule-anchors.sh check` from this worktree.
- A line the meter cannot grade is listed in the change file's `unmeasured` and named in your final report; I take it to the user.
- Owners lines: none in any CLAUDE.md beyond item 1's wording change.
- This lane edits `claude/.claude/CLAUDE.md` and `claude/.claude/orchestration.md` on its branch; the user installs by merging the branch. Never touch `settings.json`; never edit the live `~/dotfiles` checkout.
- Item 3: check the model hooks under `claude/.claude/scripts/` first so the line states exactly what they enforce.
