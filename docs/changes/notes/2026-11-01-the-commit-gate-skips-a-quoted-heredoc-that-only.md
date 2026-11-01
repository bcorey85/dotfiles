---
type: "Change"
change_type: "fixed"
title: "the commit gate skips a quoted heredoc that only stores text"
description: "The review commit gate no longer reads the body of a quoted heredoc as a commit when the heredoc only stores text: cat or tee writing a file, or an interpreter given a script file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T02:20:57-06:00"}
seq: 432
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_a_quoted_heredoc_stored_in_a_file_or_fed_to_a_script_is_not_a_commit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `shell_statements.strip_stored_heredocs` cuts a heredoc body only when every heredoc on its line is quoted, the
  line parses, and each command that takes one is cat or tee writing a file, or an interpreter given a script file,
  with no later command piped from it. Every other body stays.
- `review_commit_gate.is_commit_command` reads the command with those bodies cut.
- `reads_code_from_stdin` and its constants move from `gates/inline_interpreter_hint.py` to `lib/shell_command.py`;
  the gate and `shell_statements` both use them.

## Evidence

judgment: queue item review-commit-gate-denies-a-non-commit-command. A `cat >> notes.md <<'EOF'` or a
`build_queue.py new --body - <<'EOF'` whose body named `git commit` was denied as an unreviewed commit.

## Result

The named test fails before (all 4 openers denied) and passes after. The test that a shell, a pipe, eval, xargs,
`python3 -`, an unquoted body or a commit after `;` still reads as a commit passes before and after.
`test_review_commit_gate`, `test_inline_interpreter_hint`, `test_shell_command` and `test_shell_statements`: 224
tests, 0 failed; ruff clean.

## Watch

None. Any heredoc outside the allowlist is read as before.

## Back-out

Remove the `strip_stored_heredocs` call from `is_commit_command`.
