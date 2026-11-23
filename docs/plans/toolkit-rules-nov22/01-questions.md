# Research Questions

1. Which hook scripts under `claude/.claude/scripts/` act on the `model` field of an Agent tool call, and what exact values does each one allow, block or require? Where is each registered in settings?
2. What block messages do those model hooks print, and what do they say about call-site values versus an agent file's frontmatter?
3. How does the shell-write gate decide that a Bash command is a file write, and what does the inline-interpreter hint match? What do they print when they block?
4. What does `claude/.claude/orchestration.md` currently say about Agent launches, model selection, the auto-mode notice and Bash versus the dedicated file tools? Quote each such line with its section.
5. What does the global `claude/.claude/CLAUDE.md` say about orchestrating sessions and go-aheads, and where else in the repo does the same text appear?
6. How does the scripts `CLAUDE.md` Owners list work today: how is it structured, and what does any file or doc say about who may add or change a line in it?
7. How does the rule-anchors mechanism work? Where are its rows stored, what do `rule-anchors.sh check` and its sibling commands verify, and which rows exist for `CLAUDE.md` and `orchestration.md`?
8. How does the rule-meter harness in `~/agent-evals/bin/` work: how are scenarios defined in `rule_meter_scenarios.json`, how do detectors in `rule_meter_checks/` attach to them, what are `toolkit_root` and the on/off arms, and how are results recorded in a change file?
9. What do existing rule-meter scenarios and change files look like for a rule line that was reworded, added or deleted? Where are they and what fields do they carry?
10. What does the `toolkit-writing` skill say a rule line must satisfy, and how does the repo flag a line as a no-op or a duplicate?
11. What tests exist for the model hooks, the shell-write gate and the rule-anchors check, and where are the test files and fixtures?

## Exploration Map

- `claude/.claude/CLAUDE.md` — global rules text, including the go-ahead wording
- `claude/.claude/orchestration.md` — orchestration rules text
- `claude/.claude/scripts/gates/` and `claude/.claude/scripts/` — hook gates for model pins, shell writes and interpreter hints
- `claude/.claude/scripts/CLAUDE.md` — owners list
- `claude/.claude/skills/toolkit-writing/` — line-writing rules
- `claude/.claude/settings.json` — hook registration (read only)
- `~/agent-evals/bin/` and `~/agent-evals/queue/` — rule-meter harness, scenarios, checks, change files
- `tests/scripts/` — existing tests for gates and anchors
- `docs/` — glossary and rule-anchor storage
