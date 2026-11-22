# Research Questions

1. How is the /code skill structured in `claude/.claude/skills/code/SKILL.md`? List its sections, the steps it runs in order, and which other files it references or defers to.
2. How does the code-fork agent definition work? Trace how it is launched and which subagents it dispatches.
3. How does the coder agent get dispatched from a code fork, and what state records exist for it?
4. What stop-event handling (hooks, scripts, settings) exists?
5. What does the code-run review start script store at phase start, and where?
6. How does the hold logic work, and where is it used?
7. How does the review scope get built from the work tree?
8. What does `claude/.claude/skills/_shared/review-fork-run.md` contain, and which files reference or include it?
9. What is the rule-meter tool and where does it store its data?
10. What test patterns and fixtures exist under `tests/scripts/` for the code-review start script, the hold logic and the review loop? Where are the test files and how do they pin file-state cases?
11. What other consumers (agents, skills, hooks, ported opencode copies) reference the /code skill's sections or the code-fork agent text?

## Exploration Map

- `claude/.claude/skills/code/SKILL.md` — the skill body and its step text
- `claude/.claude/agents/code-fork.md` — fork agent definition
- `claude/.claude/agents/` — coder and related agent definitions
- `claude/.claude/skills/_shared/` — shared review-fork-run text
- `claude/.claude/scripts/code/` — code-run helper scripts including review start
- `claude/.claude/scripts/review/` — review loop and hand-back store
- `claude/.claude/scripts/lib/` — shared modules for tree fingerprints, snapshots and notes paths
- `claude/.claude/settings.json` — hook wiring: which scripts run on which events
- `tests/scripts/` — existing script tests and fixtures
- `opencode/.config/opencode/agents/` — ported agent copies
- `~/agent-evals/` — queue item files, bin/ scripts and docs/changes conventions that the repo's docs reference
