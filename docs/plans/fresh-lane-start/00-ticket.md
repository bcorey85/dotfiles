---
type: "QueueItem"
title: "forked lane inherits the orchestrator context and compacts at once"
description: "A lane starts fresh from its brief instead of forking the orchestrator's conversation, so it skips a compaction and its re-orientation before any work."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-27T11:27:48-06:00"}
kind: "method"
status: "running"
rank: 9025
blocked_by: []
source: "scripts/.local/bin/herdr-worktree"
components: ["script/herdr-worktree", "rule/orchestration"]
not_dup: "the cron fix drops inherited timers; this drops the inherited conversation, which forced a compaction 69 s after the fork"
---

## Context
Lane session of 2026-11-26 (fix/durable-lane-plan): the fork carried 168 blocks of orchestrator history, compacted 69 s after start (block 192) before any work, then re-read the queue item it had read at block 175; a second compaction at block 730 forced about 18 re-read calls. The brief already holds what the lane needs.

## Done when
herdr-worktree starts a lane from the brief alone by default, with --fork kept as an opt-in; a test sees the lane command carry no resume of the parent session. A bench pair (fork vs fresh) on one lane item compares tokens by model and compactions.

Deletes: the inherited orchestrator context in every lane.
