---
name: skill-audit
description: Audit the skill toolkit against usage telemetry — reports untriggered skills, overlap candidates, and always-loaded context cost. Run monthly. Triggers on "/skill-audit", "audit my skills", "which skills am I not using", "skill usage".
allowed-tools: [Bash, Read, Glob, Grep]
---

# Skill Audit

Data-driven monthly audit of `~/.claude/skills/`. The guidance this implements: every skill's description is always-loaded context tax; skills that never trigger should be merged, trimmed, or deleted.

## Inputs

1. **Telemetry**: `${SKILL_USAGE_FILE:-$HOME/.claude/skill-usage.jsonl}` — written by the `log-skill-use.sh` hooks (`{ts, skill, via, repo}`; `via` is `user` for typed slash commands, `model` for Skill-tool invocations). If the file is missing or empty, say the telemetry hooks haven't fired yet (check they're registered in settings.json), and still run the static checks below.
2. **Inventory**: every `~/.claude/skills/*/SKILL.md` — name, description, body line count.

## Exempt list (never flag)

- `coder-core` — preloaded via agent `skills:` frontmatter; it can never appear in telemetry.
- `_shared/` files — not skills.
- Pipeline-internal skills reachable only via chaining (`fix`, `review` when invoked by `/code`) DO log via the model path — they are not exempt, but weight their counts accordingly.

## Process (single pass, jq/awk — don't re-read the log per skill)

1. Build the inventory table: skill | description length | body lines.
2. From telemetry: invocation counts per skill for the last 30 and 90 days, split user/model. Drop log entries that don't match any skill directory (built-in commands like `/clear`, `/model` land in the log too).
3. Flag, with thresholds:
   - **Untriggered ≥ 30 days** (with ≥ 30 days of telemetry history) → retire/merge candidate.
   - **Description > ~4 lines or body > 150 lines** on a low-use skill → trim candidate.
   - **Overlapping trigger domains** — two descriptions a reasonable router could confuse → merge or sharpen-description candidate.
   - **Built-in shadowing** — a custom skill whose job a harness built-in now covers; check against the "Built-in vs Custom Skills" routing table in `~/.claude/CLAUDE.md` before flagging.
4. Report (cap ~60 lines): usage table, then flags, each with a one-line recommended action (delete / merge into X / trim to Y / sharpen description). If telemetry history is thin (< 30 days), say so and mark usage-based flags provisional.

## Boundaries

- **Read-only** — never delete or edit a skill during the audit; the user decides.
- Do not flag skills purely for being niche — a skill used twice a year that saves an hour each time earns its ~100-token description. Judge cost vs. value, not raw counts.

## Arguments

$ARGUMENTS
