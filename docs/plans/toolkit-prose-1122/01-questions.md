# Research Questions

1. Which files under `claude/.claude/skills/_shared/` exist, and for each one, which skills, agents, commands and scripts load or point to it, and what does each pointer say about when to read it?
2. How are the files in `claude/.claude/agents/` structured (frontmatter fields, description text, body), and what do the descriptions of `test-intent-reviewer`, `plan-verifier`, `backend-architect`, `frontend-architect` and `general-purpose` say about who dispatches them? Which skills and commands actually dispatch each of these?
3. How is the `acceptance_criteria none` condition described across `skills/coder-core/SKILL.md`, `agents/code-reviewer.md` and the plan-format shared file, and where is it read or written by scripts?
4. How are `skills/coder-core/SKILL.md`, `skills/architect-core/`, `agents/code-reviewer.md`, `agents/smell-reviewer.md`, `agents/test-reviewer.md` and `agents/test-intent-reviewer.md` laid out, and which parts of them repeat or reference each other?
5. How do `_shared/review-fork-run.md`, `_shared/plan-format.md` and `_shared/reviewer-calibration.md` describe their procedures, and where do the same rules (plan routing, blocker rules, the Close pass) appear in more than one place?
6. How does the eng-spec skill's phase structure work (`4-explore.md`, `5-decisions.md`, `6b-review.md`), and what do the goal-blind-researcher and spec-research files say about their repair loop and search rules?
7. What do `skills/orient/SKILL.md`, `skills/todos/SKILL.md`, `skills/list/SKILL.md` and `skills/pull-ticket/SKILL.md` instruct, and which vault, git and ticket-state actions does each one name?
8. What are the "anchor rows" for agents and skills such as coder-core and the architects, where are they stored, what format do they use, and which tests or scripts read them?
9. How do the opencode ports in `opencode/.config/opencode/agents/` correspond to the files in `claude/.claude/agents/` and skills, and which adaptations differ between the two copies?
10. How does `bin/rule_meter.py` in `~/agent-evals` work, where do `rule_meter_scenarios.json` and `bin/rule_meter_checks/` live, what shape do scenarios and detectors take, and what does a change file's `unmeasured` field record?
11. What does `bash tests/run.sh` run, which tests read skill and agent markdown content, and which of them check descriptions, pointers, `_shared` loaders or anchors?
12. How does `agents/code-reviewer.md` define its review rules and finding format, and what existing rules concern hard-coded lists or duplicated values?

## Exploration Map

- `claude/.claude/skills/_shared/` — shared reference files and their loaders
- `claude/.claude/agents/` — agent definitions, descriptions and dispatch text
- `claude/.claude/skills/coder-core/`, `claude/.claude/skills/architect-core/` — preloaded core skills
- `claude/.claude/skills/eng-spec/` — phase files, researcher and spec-research text
- `claude/.claude/skills/orient/`, `todos/`, `list/`, `pull-ticket/` — vault and ticket skills
- `opencode/.config/opencode/agents/` — ported agent copies
- `~/agent-evals/bin/` — rule meter, scenarios, checks
- `tests/` — test runner and content tests
