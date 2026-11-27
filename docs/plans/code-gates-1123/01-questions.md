# Research Questions

1. What does the output-filter detection in `quality_check_cap.py` look like, including `OUTPUT_FILTER_START`, and how does the gate decide that a check's output was cut or seen in full, and how does it then handle a rerun that redirects output to a file?
2. What does `lib/check_scope.py` and `lib/shell_command.py` expose for splitting a piped command into its stages and naming each stage's command word, and how do existing callers use it?
3. What tests exist for `quality_check_cap.py`, how do they build events and state, and where are the test files?
4. How does the hook that denies inline interpreter code (python heredocs, `python3 -`, `python -c`) decide a target file is tracked, how does it find the files the code writes, and what message does it print on deny?
5. What tests and fixtures exist for that inline-code gate, and how do they set up a repo with tracked and untracked files and a `cd <dir> && python3 - <<'EOF'` command?
6. How does the announced-step stop gate read a transcript, find the tools launched in the final turn (including `run_in_background` Bash calls and Agent calls), and match the final text against its "started" or "running" wording?
7. What transcript fixtures and tests exist for the announced-step stop gate, and which tool-use event shapes (Bash, Agent) do they capture?
8. How does a `/code` fork run end to end, from `code_step.py` and `code_review_start.py` through the run folder, review packets, step records, and stop files, and which scripts write each of them?
9. How does the hand-back check (`review/handback.py`, `handback_store.py`) treat a code-fork hand-back today, and what does it read to decide a review ran, a reason for skipping a step was recorded, or the status is clean?
10. How do the hand-back and verify tests in `tests/scripts/` build a run folder with a phase, packets and recorded skip reasons, and where are they?
11. What shared owners in `claude/.claude/scripts/lib/` already cover the facts these gates read (run folder paths, stop file names, state file paths, session transcript reading), and who imports them?

## Exploration Map

- `claude/.claude/scripts/gates/quality_check_cap.py` — output-filter and redirect handling for check commands
- `claude/.claude/scripts/lib/check_scope.py`, `claude/.claude/scripts/lib/shell_command.py`, `claude/.claude/scripts/lib/shell_steps.py` — shell command parsing owners
- `claude/.claude/scripts/gates/` — hook gates, including the inline-code deny and the announced-step stop gate
- `claude/.claude/scripts/review/handback.py`, `claude/.claude/scripts/review/handback_store.py` — hand-back rows and clean statuses
- `claude/.claude/scripts/code/` — code step and review start scripts
- `claude/.claude/scripts/lib/` — shared modules
- `claude/.claude/settings.json` — hook registration
- `tests/scripts/` — existing tests and fixtures for gates, hand-back and the code fork
