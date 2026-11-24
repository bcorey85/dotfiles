# toolkit-scripts-1122: four toolkit script and prose-move items

Source: ~/agent-evals/queue/guide-skill-point-to-the-guide-binary-instead-of.md
Source: ~/agent-evals/queue/refactor-skill-have-refactor-flow-py-print-the-log.md
Source: ~/agent-evals/queue/mutation-tester-move-the-lock-backup-and-restore.md
Source: ~/agent-evals/queue/review-commit-gate-places-a-cd-to-a-literal-repo.md (dropped, D1)

## Lane brief (verbatim, /tmp/.../scratchpad/brief-toolkit-scripts.md)

# Lane: toolkit-scripts-nov22 (branch fix/toolkit-scripts-nov22)

Read `/tmp/claude-1000/-home-brandon-agent-evals/a0b58526-6a4a-4e0a-af5b-8d0985572fda/scratchpad/lane-common.md` first. It holds the lane rules; this file holds the work.

## Items (all queued on origin/bench-base of ~/agent-evals; read each with `git -C ~/agent-evals show origin/bench-base:queue/<slug>.md`)

1. `review-commit-gate-places-a-cd-to-a-literal-repo` (script fix with a test; follow git-discipline-gate's existing cd/-C target reading, one shared helper, not a second parser)
2. `guide-skill-point-to-the-guide-binary-instead-of`
3. `refactor-skill-have-refactor-flow-py-print-the-log`
4. `mutation-tester-move-the-lock-backup-and-restore`

Items 2 to 4 move text out of a skill or agent into the script or binary that owns it. Load the `toolkit-writing` skill before you touch any prose.

## Rulings already made (agent-evals-c3, 2026-11-22; record each in the plan's 03-decisions.md)

- Owners lines: none in any CLAUDE.md. A module owner goes in its module docstring.
- Scripts live under `claude/.claude/scripts/`, tests under `tests/scripts/` with paths from `tests/scripts/toolkit_paths.py`. You edit them on this branch in this worktree; the write-edit gate blocks the live `~/.claude/scripts`, never the worktree.
- Item 2: keep one worked card; rules 3-5, 7 and 8 are cut only after rule-meter on and off arms; a rule the meter cannot grade stays and is listed in `unmeasured`.
- Every cut or reworded rule gets rule-meter arms before commit. New scenarios go in `bin/rule_meter_scenarios.json`; new detectors go in `bin/rule_meter_checks/` with tests; `bin/rule_meter.py` stays untouched. Run `git -C ~/agent-evals status bin/` first and never touch another session's uncommitted file there.
- Item 4: the precondition count mismatch ("all five", four listed) is fixed by listing what the script checks; the script's `--help` is the owner of the list.
- Opencode ports: patch them where the item names them.

## Order

Triage, claim, /eng-spec one plan, /code, /verify-branch, suite under `systemd-run --user --scope --quiet -p MemoryMax=8G -p MemorySwapMax=0 bash tests/run.sh`, then commit and push the branch and send the final report to agent-evals-c3 (ListAgents name: agent-evals-c3).

## Queue item: review-commit-gate-places-a-cd-to-a-literal-repo (verbatim)

---
type: "QueueItem"
title: "review-commit-gate places a cd to a literal repo path and git command by the cd target"
description: "A reviewed commit written as cd repo && git commit gets its credit instead of a block and a retry."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T14:40:13-06:00"}
kind: "chore"
status: "running"
rank: 1011
blocked_by: []
source: "claude/.claude/scripts/gates/review-commit-gate"
components: ["script/review-commit-gate", "script/git-discipline-gate"]
---

### Context
Session a0b58526: 13 review-commit-gate blocks, every one `cd /abs/path && git commit|merge ...`. git-discipline-gate already reads the branch of the -C or cd target (change 2026-10-28); the commit gate instead names the form (change 2026-10-30), so each block cost a retry.

### Done when
- A test in ~/dotfiles/tests/scripts/ gives the gate `cd /abs/repo && git commit -m x` with /abs/repo covered by a converged review and the gate passes it; `cd $VAR && git commit` and a relative cd still earn no credit.
- bash tests/run.sh passes on the dotfiles checkout.

## Queue item: guide-skill-point-to-the-guide-binary-instead-of (verbatim)

---
type: "QueueItem"
title: "guide skill: point to the guide binary instead of copying its block formats"
description: "Cuts about 90 always-read lines from the guide skill by pointing to the format the guide binary owns."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:41:23-06:00"}
kind: "method"
status: "running"
rank: 1011
blocked_by: []
source: "claude/.claude/skills/guide/SKILL.md"
components: ["skill/guide"]
not_dup: "No prior item touches the guide skill; the 0.39 match is the code skill prompt cut."
---

### Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

guide/SKILL.md:79-198 holds about 120 lines of block and field schema tables plus three worked cards, a cache of the format `guide --format-version` owns. Rules 3-5, 7 and 8 are no-op candidates.

### Done when

The skill keeps one worked card and points to the binary for the format; the dropped rules pass rule-meter or stay; `bash tests/run.sh` passes.

## Queue item: refactor-skill-have-refactor-flow-py-print-the-log (verbatim)

---
type: "QueueItem"
title: "refactor skill: have refactor_flow.py print the log JSON template"
description: "Moves the 30-line log input template out of the refactor skill into the script that parses it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:42:05-06:00"}
kind: "method"
status: "running"
rank: 1011
blocked_by: []
source: "claude/.claude/skills/refactor/SKILL.md"
components: ["skill/refactor"]
not_dup: "The 2026-10-25 change made the skill's copy of the template parse; this makes the script the one owner so the copy cannot drift again."
---

### Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

refactor/SKILL.md:64-101 holds a 30-line `log` JSON template and field prose that `refactor_flow.py` owns.

### Done when

`refactor_flow.py` prints the template (a verb or --help); the skill keeps about 3 lines that name the trigger to run it; the refactor tests and `bash tests/run.sh` pass.

## Queue item: mutation-tester-move-the-lock-backup-and-restore (verbatim)

---
type: "QueueItem"
title: "mutation-tester: move the lock, backup and restore procedure into a script"
description: "Turns a fragile prose procedure into a script and cuts about 30 lines from each mutation dispatch."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:42:06-06:00"}
kind: "method"
status: "running"
rank: 1011
blocked_by: []
source: "claude/.claude/agents/mutation-tester.md"
components: ["agent/mutation-tester"]
not_dup: "The 2026-10-21 change moved the lock files out of the config folder; the procedure is still prose in the agent."
---

### Context

Found by the 2026-11-22 toolkit-writing audit of every skill and agent. Unmeasured: each cut of an existing rule goes through bin/rule_meter.py first.

mutation-tester.md holds the lock/backup/restore steps as prose with the `${XDG_STATE_HOME...}/claude-calibration` path repeated 8 times. It says "all five" preconditions and lists four.

### Done when

A script under claude/.claude/scripts/ does lock, backup and restore with tests under tests/scripts/; the agent calls it in one line; the precondition count is right; the opencode port is patched; `bash tests/run.sh` passes.

## Comments

none
