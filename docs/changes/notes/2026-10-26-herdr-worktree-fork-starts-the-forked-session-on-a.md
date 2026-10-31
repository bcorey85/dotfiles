---
type: "Change"
change_type: "changed"
title: "herdr-worktree fork starts the forked session on a hand-over brief"
description: "herdr-worktree --fork now takes a required --prompt that the forked Claude session starts on, and the orchestration rule says to pass a brief naming the task, what is done, the next step and that the fork owns the work."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:35:04-05:00"}
seq: 75
kind: "user-rule"
components: ["rule/orchestration", "script/herdr-worktree", "script/herdr-dev"]
evidence: ["user request"]
watches: []
test: ""
asked: "2026-10-26: we need to fix the herdr-worktree fork / handoff quickly - the forker always needs to start the forked session. dont just fork and not tell it to start / pass context"
proof: []
unmeasured: ""
---

## Change

`herdr-worktree` takes `--prompt <text>`, required with `--fork`, and passes it to `herdr-dev`. `herdr-dev` launches the claude pane as `claude --resume <id> --fork-session <prompt>`, with the prompt read from a temp file so any text survives the pane shell. The orchestration rule's worktree bullet now runs `herdr-worktree --fork --prompt '<start brief>' <branch>`. It says the brief hands over the work: the task, what is done, the next step, and that the fork owns it in the new worktree.

## Evidence

user request: forked sessions opened idle, with no instruction to start and no hand-over.

## Result

Shell syntax checks and a quoting dry run of the built launch command.

## Watch

—

## Back-out

Drop `--prompt` from both scripts and restore the rule's old `herdr-worktree --fork <branch>` sentence.
