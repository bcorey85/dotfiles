# Decisions — fresh-lane-start

- The queue item's bench pair (fork vs fresh, tokens by model and compactions) is left out of this plan's criteria: the orchestrator runs it after the branch lands. Ruled by agent-evals-c3-owner, 2026-11-27.
- This lane edits `claude/.claude/orchestration.md:35` and `claude/.claude/skills/_shared/lane-brief.md:3`, a one-time exception to lane-brief.md's ban on lane edits of orchestration.md, for the user's ask to fix the fork issue. Ruled by agent-evals-c3-owner, 2026-11-27.
- The fresh lane keeps every step a forked lane has (headless, cron off, lane entry, push, watcher) and keeps base HEAD, so a lane still starts from the caller's branch.
