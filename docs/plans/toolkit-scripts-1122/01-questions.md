# Research Questions

1. How does `claude/.claude/scripts/gates/review-commit-gate` decide whether a git commit or merge command is covered by a converged review? Trace the flow from the hook's stdin event to its allow or deny output, including how it determines which repo folder a command lands in.
2. How does `claude/.claude/scripts/gates/git-discipline-gate` read the target of a `-C` option or a `cd` before a git call, and which shared helpers in `claude/.claude/scripts/lib/` (for example `git_commit_calls.py`, `shell_command.py`, `shell_directory.py`) does it use?
3. What do existing tests under `tests/scripts/` for the review-commit-gate and git-discipline-gate cover, how do they build fixtures (repos, review records, hook events), and where do they get paths from `tests/scripts/toolkit_paths.py`?
4. What does `claude/.claude/skills/guide/SKILL.md` contain, section by section, and what block and field formats does the `guide` binary report through `--format-version`? Where is that binary or its source defined?
5. How does `claude/.claude/skills/refactor/SKILL.md` describe the `log` input, and how does `refactor_flow.py` parse that input, define its verbs and `--help` output, and report parse errors? Which tests cover it?
6. What steps does `claude/.claude/agents/mutation-tester.md` describe for locking, backing up and restoring files, where do the lock and backup files live, and what preconditions does it list?
7. What existing scripts under `claude/.claude/scripts/` handle locks, backups or restores of files (for example `lib/file_lock.py`, `lib/script_utils.py`), and how do their `--help` outputs, argument conventions and tests under `tests/scripts/` look?
8. Which ported copies of agents and skills exist under `opencode/.config/opencode/` (for example the mutation-tester, guide and refactor ports), and how do they differ from the claude originals?
9. What other files (skills, agents, hooks, `settings.json`, other scripts, docs) reference the guide skill, the refactor skill's log template, or the mutation-tester procedure, and how do tests check skill and agent prose (for example prompt-reading tests)?
10. What does `tests/run.sh` run, how do `tests/lint.sh` and `tests/parallel_tests.py` fit in, and what conventions in `docs/toolkit-script-rules.md` and `claude/.claude/scripts/CLAUDE.md` apply to a script?
11. How is rule-meter structured in `~/agent-evals/bin/` (`rule_meter.py`, `rule_meter_scenarios.json`, `rule_meter_checks/`), how are scenarios and detectors defined, and where are its tests?

## Exploration Map

- `claude/.claude/scripts/gates/` — hook gates for commit review and git discipline
- `claude/.claude/scripts/lib/` — shared shell, git-call and lock modules
- `claude/.claude/scripts/telemetry/` and `claude/.claude/scripts/tools/` — neighboring script conventions
- `claude/.claude/skills/guide/` — guide skill prose
- `claude/.claude/skills/refactor/` — refactor skill prose and `refactor_flow.py`
- `claude/.claude/agents/mutation-tester.md` — mutation agent procedure
- `opencode/.config/opencode/agents/` — ported agent copies
- `tests/scripts/` and `tests/run.sh` — test patterns and suite runner
- `docs/toolkit-script-rules.md` — script rules
- `~/agent-evals/bin/` — rule-meter tooling and scenarios
