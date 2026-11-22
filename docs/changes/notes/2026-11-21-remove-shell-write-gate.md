---
type: "Change"
change_type: "removed"
title: "Remove shell-write-gate"
description: "The PreToolUse(Bash) shell-write-gate is deleted with the five libs only it used. bash-safety-gate still blocks in-place edits, inline interpreter writes and redirects into the protected toolkit paths."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-21T22:02:53-06:00"}
seq: 6
kind: "user-rule"
components: ["script/shell-write-gate"]
evidence: ["user rule", "census"]
watches: ["remove-shell-write-gate", "remove-shell-write-gate-all-blocks"]
test: "tests/scripts/test_hook_if_filters.py::HookIfFiltersTest::test_scripts_that_fire_per_command"
asked: "2026-11-21: asked by the user"
proof: []
unmeasured: "No bench run ever measured a benefit from the gate; the watches read its cost, not what it caught."
---

## Change

- Deleted `gates/shell_write_gate.py` and `lib/shell_write_denial.py`, `lib/shell_write_paths.py`, `lib/interpreter_writes.py`, `lib/inplace_edit.py`, `lib/shell_variables.py`, with their four test files.
- Removed its rows from `gate_replay.py`, `gate_replay_corpus.json`, `test_review_fixes.py`, `test_import_guard.py`, `test_hook_if_filters.py`, `claude-doctor.sh`, the omp bridge and the lib lists in `docs/toolkit-script-rules.md`.
- The `settings.json` hook entry is removed by hand: the Edit tool may not write project settings.
- `commit_gate_dirty.edited_repos` keeps reading only the edit tools; its docstring now says a coder shell write is not counted.

## Evidence

User rule, 2026-11-21: the user asked to delete it. Census of the work hook log: 1,311 of 6,755 hook blocks were shell-write-gate, the top rule (150 in main sessions, 1,161 in subagents), and the gate took 48 patch queue items.

## Result

The suite passes with the gate gone; the replay corpus holds no shell-write-gate rows.

## Watch

`remove-shell-write-gate` reads its blocks per coder run; `remove-shell-write-gate-all-blocks` reads every rule's blocks per coder run, to show no other gate takes up the blocks.

## Back-out

Restore the six deleted scripts, the four test files and the hook entry from the commit before this change.
