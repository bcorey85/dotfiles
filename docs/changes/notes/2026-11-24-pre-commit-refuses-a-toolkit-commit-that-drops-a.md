---
type: "Change"
change_type: "fixed"
title: "Pre-commit refuses a toolkit commit that drops a metered rule text or breaks the skill list"
description: "The dotfiles pre-commit hook checks the staged claude/.claude against agent-evals' rule-meter scenarios and skill-list test, so a commit that removes a metered rule fragment or a tracked skill fails before it lands."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-24T04:21:18-06:00"}
seq: 1
kind: "fix"
components: ["script/pre-commit-hook", "script/toolkit-drift", "script/index-export"]
evidence: ["work incident"]
watches: []
test: "tests/scripts/test_toolkit_drift.py::ToolkitDriftTests::test_a_staged_deletion_of_a_metered_rule_line_fails_and_names_it"
asked: ""
proof: []
unmeasured: "a commit-time check; no intake number reads it"
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`.githooks/pre-commit` runs `tests/toolkit_drift.py` when the staged set touches any path under `claude/.claude/` other than `scripts/` (a `CLAUDE.md` under `scripts/` counts). It runs before the `build_changes.py` early exit.

- **Rule texts:** `rule_meter.check_rule_texts` reads the toolkit from the home folder, not from a staged tree. So the step exports the staged `claude/.claude` from the index into a `tempfile.TemporaryDirectory()`, using the new `lib/index_export.py`, which honors `GIT_INDEX_FILE`. It then points each live scenario at that export: one with no `toolkit_root`, or a root that resolves to `~/.claude` or `~/dotfiles/claude/.claude`. It checks only scenarios whose rule source or `rule_file` is a staged path. It runs one scenario at a time, so every removed fragment is named.
- **Skill list:** agent-evals' `bin/test_skill_names.py` runs unchanged whenever a skill path is staged, with `GIT_DIR` and `GIT_INDEX_FILE` set so that its `git -C ~/dotfiles ls-files` reads the staged index.
- **When it skips:** with a one-line note when `$AGENT_EVALS_DIR` (default `~/agent-evals`) or either script is missing, and with a "skill list was not checked" note when the skill test skips itself (for example no `~/dotfiles`). It fails closed when `rule_meter` cannot be imported. It edits nothing in agent-evals and writes no bytecode there.

## Evidence

Work incident: toolkit commits 3360701a2 and a315d97f5 removed four rules, and 412a679c3 and e7951de09 changed the skill set. The agent-evals suite then failed 10 tests, and another session found them hours later. Queue item `a-toolkit-commit-that-deletes-rule-text-or-a-skill`.

## Result

`test_a_staged_deletion_of_a_metered_rule_line_fails_and_names_it` fails without the step and passes with it. The skip, pass and skill-list cases are in `tests/scripts/test_toolkit_drift.py`, and the hook-level case is `test_the_drift_step_runs_and_its_failure_refuses_the_commit`.

Real run, against the live agent-evals with a temp index:

- Cutting scenario AB's fragment from the staged `skills/coder-core/SKILL.md` failed the check, naming `'A comprehension has one loop.'`.
- A commit that touches `skills/code/SKILL.md` took 101–119 ms over 5 runs, with a median of 105 ms.

The export uses one resolved destination path. The staged path list is read through `script_utils.git_output`, so a non-ASCII path is not quoted.

## Watch

None.

## Back-out

Revert the commit.
