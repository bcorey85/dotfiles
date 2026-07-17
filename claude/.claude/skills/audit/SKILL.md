---
name: audit
description: Entry point for toolkit health and telemetry reports — lanes; usage (token burn by day × model from local transcripts), skills (skill toolkit vs usage telemetry), review (review flywheel — catches, escapes, specialist yield, calibration). Use for "/audit", "where are my tokens going", "token burn", "usage breakdown", "am I burning limits", "audit my skills", "which skills am I not using", "review stats", "review flywheel", "how is the review loop calibrated".
allowed-tools: [Bash, Read, Glob, Grep]
---

# Audit

One entry point for the read-side telemetry reports. Pick the lane, read ONLY
that lane's file (same directory as this skill), and follow it. Remaining
arguments after the lane pass through to the lane (e.g. a repo filter, a date
range).

| Lane     | File        | Question it answers                                                      |
| -------- | ----------- | ------------------------------------------------------------------------ |
| `usage`  | `usage.md`  | Where are my tokens/limits going? (day × model, main vs subagent)        |
| `skills` | `skills.md` | Which skills earn their always-loaded description tax?                   |
| `review` | `review.md` | Is the review flywheel calibrated? (catches vs escapes vs specialist yield) |

Lane resolution: match the first argument or an obvious synonym (tokens/burn/limits → `usage`; flywheel/escapes/calibration → `review`). `all` runs all three, usage first. No lane and no clear synonym → ask which lane, one line, don't guess.

## Boundaries (all lanes)

- **Read-only** — never delete or edit a skill, agent, or log during an audit; recommend, the user decides.
- Report per the global style: lead with the 1–3 findings that would change behavior; hold the rest for follow-ups.
- Telemetry is per-machine and local-only — say which machine's data this is when it matters (usage lane especially).

## Arguments

$ARGUMENTS
