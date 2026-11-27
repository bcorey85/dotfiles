# Research Questions

1. Which hooks are registered under the Stop event in `claude/.claude/settings.json`, and what script does each one run? Which of them can emit a block decision?
2. What JSON does each Stop-event hook script read from stdin and write to stdout or stderr, and how does each report a block (decision, reason, exit code)? Where are captured Stop event fixtures kept, if any?
3. How does `claude/.claude/scripts/gates/staged_claim_gate.py` decide to block? Trace it from its input to its output.
4. Which shared modules under `claude/.claude/scripts/lib/` do the Stop hooks import (for example `hook_input.py`, `message_text.py`, `reply_json.py`, `api_error_stop.py`, `code_stop_record.py`, `import_guard.py`), and what does each own?
5. How does `claude/.claude/scripts/gates/format_changed.py` produce its block output, and what text does it include in it?
6. Which output fields (`systemMessage`, `reason`, `additionalContext`, others) do the hook scripts under `claude/.claude/scripts/gates/` and `lib/` emit, and where does each one go?
7. How is the last assistant reply text extracted from a transcript or hook payload, and how are multi-block messages, tool-use blocks and quoted or code text handled?
8. What test patterns exist in `tests/scripts/test_staged_claim_gate.py` and `tests/scripts/test_format_changed.py`? How do they build inputs, which cases exist per phrase form, and how do they locate the script under test via `tests/scripts/toolkit_paths.py`?
9. How are existing hook scripts timed or benchmarked, and what is `claude/.claude/scripts/tools/hook-python` doing when it starts a hook?
10. What format do change files under `docs/changes` use, and what fields (kind, date, unmeasured, and so on) does `~/agent-evals/bin/build_changes.py` require?
11. What queue items exist under `~/agent-evals/queue/` that concern Stop hooks, and what do they contain and cite?

## Exploration Map

- `claude/.claude/settings.json` — Stop hook registrations
- `claude/.claude/scripts/gates/` — Stop gate scripts (`staged_claim_gate.py`, `format_changed.py`)
- `claude/.claude/scripts/lib/` — shared modules for hook input, message text and output
- `claude/.claude/scripts/tools/hook-python` — hook launcher
- `tests/scripts/` — tests and path helpers for the gates
- `docs/changes/` — change file format
- `~/agent-evals/bin/` and `~/agent-evals/queue/` — change-file builder and queue items
