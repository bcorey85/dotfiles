---
type: "Change"
change_type: "fixed"
title: "Dotfiles tests and scripts find toolkit code in their own checkout"
description: "The test suite and ten scripts found toolkit code through ~/.claude, so a suite run in a dotfiles worktree tested the live scripts instead of the edited ones. They now find it from their own file location, and a script change can be edited and fully tested in a worktree before the user merges it."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T15:25:01-05:00"}
seq: 3
kind: "fix"
components: ["script/code-step", "script/review-fix", "script/review-loop-gate", "script/verify-common", "script/adr-flow", "script/refactor-flow", "script/review-scope", "skill/stage"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_paths.py::ToolkitPathsTest::test_the_default_is_the_toolkit_folder_of_the_tree_the_tests_sit_in"
asked: ""
proof: []
unmeasured: ""
---

## Change

`tests/scripts/toolkit_paths.py` defaults `CLAUDE_DIR` to `claude/.claude` of the tree that it sits in, not to `~/.claude`. `TOOLKIT_CLAUDE_DIR` still points the tests at another folder.

These scripts find sibling code through their own file location (`Path(__file__).resolve()`, `${BASH_SOURCE[0]}`, `import.meta.url`), not through the home folder:

- `code/code_step_core.py`, `review/review_fix.py`, `review/review_loop_gate.py` and `review/verify_common.py`
- `skills/adr/scripts/adr_flow.py`, `skills/refactor/scripts/refactor_flow.py`, `skills/review/review-scope` and `skills/stage/scripts/stage.mjs`

Each env override (`CODE_STEP_CLAUDE_DIR`, `REVIEW_FIX_CLAUDE_DIR`, `REVIEW_LOOP_GATE_CLAUDE_DIR` and the others) still wins. State, logs, locks and ledgers stay under the home folder. `verify_common.py` renames `CLAUDE_HOME` to `STATE_ROOT`, because it now holds only state.

`tests/scripts/test_toolkit_self_location.py` fails when a script, hook or skill script finds toolkit code through the home folder. Printed text and the live checks on purpose are in an allowlist with a reason each. An allowlist entry that matches nothing also fails the test.

The comments and `docs/toolkit-script-rules.md` no longer say that the tests use the installed copy.

## Evidence

Judgment from a code read. A lane bundle (a hand-built copy tree, a manifest writer, a test runner pointed at the copy through env vars, and an install script that the user runs) existed only because a worktree suite run tested `~/.claude`. Each lane under `~/dev/evals/fixbatch-*` built these tools again by hand.

## Result

The default-path test failed before the change, because the default was `/home/brandon/.claude`, and it passes after it. The self-location test failed before the change with 11 offenders, and it passes after it. Live runs behave the same, because `~/.claude` is a symlink to `~/dotfiles/claude/.claude`, the tree that these scripts now find through their own location. The full suite passed from the worktree.

## Watch

None. No intake number reads the place where a test finds its code. The self-location test keeps the rule.

## Back-out

Revert the branch `fix/tree-local-tests`. A suite run in a worktree then tests the live scripts again.
