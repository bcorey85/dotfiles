---
name: audit
description: Toolkit health reports in four lanes, usage, skills, review and retro.
disable-model-invocation: true
allowed-tools: [Bash, Read, Glob, Grep, Skill, mcp__ledger__search, mcp__ledger__session]
---

# Audit

One entry point for the read-side telemetry reports. Pick the lane, read only
that lane's file (same directory as this skill), and follow it. Remaining
arguments after the lane pass through to the lane (e.g. a repo filter, a date
range).

| Lane     | File        | Question it answers                                                      |
| -------- | ----------- | ------------------------------------------------------------------------ |
| `usage`  | `usage.md`  | Where are my tokens/limits going? (day × model, main vs subagent)        |
| `skills` | `skills.md` | Which skills earn their always-loaded description tax?                   |
| `review` | `review.md` | Is the review flywheel calibrated? (catches vs escapes vs specialist yield) |
| `retro`  | `retro.md`  | What in the environment made one session hard, and what fixes it?        |

Lane resolution: match the first argument or an obvious synonym (tokens/burn/limits → `usage`; flywheel/escapes/calibration → `review`; postmortem/what went wrong → `retro`). `all` runs usage, skills and review, usage first. No lane and no clear synonym → ask which lane, in one line.

## Boundaries (all lanes)

- **Report and recommend**: every change to a skill, agent or log is the user's call. The `retro` lane queues only the candidates the user picks.
- Lead with the 1–3 findings that would change behavior; hold the rest for follow-ups.
- Telemetry is per-machine and local-only — say which machine's data this is when it matters (usage lane especially).

## Arguments

$ARGUMENTS
