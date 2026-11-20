---
type: "Change"
change_type: "added"
title: "A fail-closed gate that crashes on import blocks the call and names itself"
description: "`lib/import_guard.py` makes `review_commit_gate.py`, `quality_check_cap.py`, `git_discipline_gate.py`, `shell_write_gate.py`, `fork_write_scope.py` and `coder_gate.py` exit 2 with the gate's name and the recovery step when an import crashes, where the call ran before. The omp bridge denies on a PreToolUse gate crash."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-17T23:54:09-06:00"}
seq: 2
kind: "fix"
components: ["script/review-commit-gate", "script/quality-check-cap", "script/git-discipline-gate", "script/shell-write-gate", "script/fork-write-scope", "script/coder-gate", "script/handback"]
evidence: ["tests", "transcripts"]
watches: []
test: "tests/scripts/test_import_guard.py::ImportGuardTest::test_a_syntax_error_in_a_lib_module_blocks_each_gate_and_names_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

- New `lib/import_guard.py`: `guard("<gate-name>", __name__)` sets an excepthook, only when the gate runs as the hook, before the gate's other imports; an uncaught crash after it prints the gate's name and the recovery step on stderr and exits 2. A `SystemExit` keeps its own code.
- Four gates (`review_commit_gate.py`, `quality_check_cap.py`, `git_discipline_gate.py`, `shell_write_gate.py`) call `guard(name, __name__)` right after they put `lib` on `sys.path`; `guard` acts only when the gate runs as `__main__`, so a test that imports a gate as a library keeps its own excepthook. `code/coder_gate.py` calls it the same way, and its `hook` and `bash-hook` verbs run inside `hook_input.run_gate`, so any runtime crash in them, not only an import crash, exits 2; for `hook` that blocks the coder's SubagentHandback, where it used to fail open with exit 1. The `set`, `summary` and `clear` verbs release the guard and keep their traceback. `fork_write_scope.py` does not call `guard`: it loads `hook_input` and its name modules only for a code-fork call, so it imports `hook_input` inside its own try/except in `main()`, which writes `crash_line` to stderr and exits 2 on any crash on the code-fork path (the late `hook_input` import, the scope check, the deny output). A crash before the code-fork check (unreadable stdin) stays fail-open.
- `review/handback.py` (the successor of `code_step.py dispatch-hook`): its header says it fails open on purpose.
- `omp/.omp/agent/hooks/pre/claude-security-bridge.ts`: a gate that exits other than 0 or 2, or times out, denies the call. A `.py` gate runs through `sh tools/hook-python <script>`, as `settings.json` runs it, so an old `python3` cannot crash every gate into a deny. The header says the gates deny through the JSON `permissionDecision` line and use exit 2 with stderr only when they crash.

## Evidence

11 PreToolUse rows on 6 calls ran past a crashed gate on this machine: 2026-11-12 (`import reviewed_tree` SyntaxError mid-pull, 5 calls with both commit gates off), 2026-10-30 (`dispatch-hook` ImportError) and 2026-10-24 (missing gate files). Claude Code runs the call on exit 1.

## Result

`test_import_guard.py` plants a syntax error in a scratch copy of `lib/shell_command.py` and asserts each of four gates exits 2 and names itself. `test_a_crash_in_hook_input_blocks_fork_write_scope` does the same for fork_write_scope through a planted `lib/hook_input.py` error, and `test_a_syntax_error_in_a_lib_module_blocks_the_coder_gate_bash_hook` does it for coder_gate, so all six guarded gates are covered; `test_a_runtime_crash_in_the_coder_gate_hook_blocks_and_names_the_gate` covers a crash after the imports in `hook` (exit 2, "while judging"), and `test_the_coder_gate_cli_verbs_keep_their_traceback_after_the_guard_is_released` pins the guard release; a missing-name import does the same. `spec_budget_gate.py` stays fail-open on an import crash: it is a size budget, and a block would deny every Edit, the route that repairs the broken module (`test_a_crash_in_hook_input_leaves_spec_budget_gate_open`). `hook_input.run_gate` writes its crash line through `import_guard.crash_line`, so every gate crash reads the same.

Median time on matched calls of the first four gates (the two hook_input gates are unmeasured), 15 runs of 4 calls, branch vs master: review_commit_gate 53.8 vs 53.1 ms, quality_check_cap 45.9 vs 46.0 ms, git_discipline_gate 34.0 vs 34.0 ms, shell_write_gate 34.7 vs 35.6 ms; bare Python start 7.7 ms.

## Watch

None: the effect shows only on a crash.

## Back-out

Revert the commit.
