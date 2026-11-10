---
type: "Change"
change_type: "fixed"
title: "code-fork writes its run folder files with the Write tool, held to the run folder by a hook"
description: "The /code, /review and /fix fork writes stop.md, handoff and findings files with the Write tool, which a new Write hook holds to the run folder, so a stop whose text names an interpreter flag no longer loses its stop file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T07:12:28-06:00"}
seq: 1
kind: "fix"
components: ["agent/code-fork", "skill/code", "shared/review-fork-run"]
evidence: ["hook block log", "headless probe"]
watches: []
test: "tests/scripts/test_fork_write_scope.py::ForkHasWriteTest::test_code_fork_may_use_write"
asked: ""
proof: []
unmeasured: "The two skill lines change call syntax only (Write tool in place of a Bash heredoc for the same files); they add no behavior rule, so no rule-meter run."
---

## Change

- `agents/code-fork.md`: `disallowedTools` drops `Write` (keeps `Edit`, `NotebookEdit`).
- New `scripts/gates/fork_write_scope.py`, a PreToolUse hook on `Write` only: when the payload's `agent_type` is `code-fork`, it denies a Write outside a run folder (a `code-phase` directory whose parent holds a git `HEAD` file, which covers linked worktrees). Every other caller passes. Fail-closed on the code-fork path; it loads `hook_input` only on that path.
- `settings.json`: registers the hook under its own `Write` matcher. No existing hook fits: the `Write|Edit|MultiEdit|NotebookEdit` group holds the generated safety gate, the eng-spec budget gate and a telemetry hook, none of which judges who writes.
- `/code` SKILL.md and `_shared/review-fork-run.md`: the fork writes its run folder files with the Write tool, not a Bash heredoc.

## Evidence

The bash safety gate greps the whole command, heredoc body included. A stop text that names an interpreter flag (here "inline python3 -I -" in its hook-block list) matched `interpreter_stdin`, and code-fork had no other way to write: no Write tool, and a script cannot take the text without it passing through the command. The block log holds that stop.md write on 2026-11-10 and two earlier stop.md writes blocked by other gate rules on 2026-11-09.

A headless probe on Claude Code 2.1.322 showed a forked skill's `PreToolUse` payload carries the fork agent's name in `agent_type`, and that a `hooks:` block in the agent's frontmatter does not fire under a skill fork, so the hook must sit in `settings.json`.

Hook time, median of 15 through `hook-python`: 22 ms on a non-fork Write, 36 ms on a code-fork Write, against 17 ms for `hook-python` on an empty script (16 ms bare `python3`).

## Result

`test_fork_write_scope.py`: 8 tests. Before the change the frontmatter and registration tests fail; after, all pass. `tests/duplicate_code.py` passes: the gate's reason function is `out_of_folder_reason`, since `deny_reason` already names a function in `wait_loop_gate.py`.

## Watch

None: a stop file that is now written leaves no intake count to read.

## Back-out

Put `Write` back in code-fork's `disallowedTools`, remove the `Write` matcher group from `settings.json`, delete the gate and its test, and restore "with a Bash heredoc" in the two skill lines.
