---
type: "Change"
change_type: "fixed"
title: "commit gate ignores quoted text of a script run"
description: "The review commit gate drops the quoted arguments and quoted heredoc body of a script run (an interpreter given a script file, or a path to a program under ~/.claude/scripts/ or a skill's scripts folder) before it looks for a commit in the text."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-19T02:32:03-06:00"}
seq: 4
kind: "fix"
components: ["script/review-commit-gate", "script/shell-statements", "script/shell-command"]
evidence: ["review-commit-gate-heredoc-false-block-recurred"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_sighted_script_runs_that_only_mention_a_commit_are_not_a_commit"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/shell_statements.py` names a script run and strips its quoted text. A path-form program counts only under
`~/.claude/scripts/` or `~/.claude/skills/<skill>/scripts/`, or the same folders of the toolkit the gate is loaded from, such as a worktree's `claude/.claude/` (read by real path; a relative path never counts), and not
when a later word names a program of `shell_statements.NOT_SCRIPT_PROGRAMS`: a shell, launcher, git or another code runner (`~/.claude/scripts/bin/mise exec -- bash -c "git commit -am x"`), or
an interpreter. An interpreter given a script file counts anywhere, unless a later word names a program of that list or
an interpreter, or the interpreter takes inline code (`php -r '...' x`). The quoted text is emptied only when no other
step of the command runs a shell or `eval`, and a step that a `|` or `|&` follows is read as written
(`python3 x.py "git commit -am x" | fish`). A command that has a `|` and an unquoted compound opener (`{`, `(`, `do`,
`then`, `else`) is read as written, quoted text and heredoc bodies included (`{ x.py "git commit"; } | python3`).
Shells, `eval`, git, bare programs such as `gh pr create --body`, paths elsewhere (including the
macOS `/Applications/`, `/Library/`, `/System/`), and unquoted heredoc bodies still go through the text match.
A later `--test` word makes the command no script run (a test runner runs files as code).

## Evidence

Two real false blocks: `python3 bin/build_queue.py new --description "... git commit ..."` and
`~/.claude/scripts/review/verify-log review --rows - <<'JSON'` with rows that named a commit.

## Result

Both sighted commands are fixtures under `tests/scripts/fixtures/`. New tests in
`tests/scripts/test_shell_statements.py` (`ScriptRunTest`).

## Watch

None.

## Back-out

Revert the commit.
