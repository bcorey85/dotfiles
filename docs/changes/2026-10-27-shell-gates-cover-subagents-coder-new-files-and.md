---
type: "Change"
title: "Shell gates cover subagents, coder new files and stdin code; quoted redirects stop counting"
description: "shell-write-gate now holds subagents and coders to the redirect and in-place rules with no skip comment, denies a coder's new file outside the temp roots, and stops reading a quoted `>` or `2>&1` as a write; the interpreter hint denies code fed on stdin; the pipe-to-shell check ignores a quoted `|` and sees through wrappers."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-27T08:33:27-05:00"}
seq: 89
kind: "fix"
components: ["script/shell-write-gate", "script/inline-interpreter-hint", "script/pipe-shell-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_inline_interpreter_hint.py::InlineInterpreterHintTest::test_inline_and_stdin_code_is_denied"
asked: ""
proof: []
unmeasured: "no intake number reads these gates' blocks: the work intake lumps them into one 'other Bash hook' row and neither gate writes the block log; a queued intake item splits them out"
---

## Change

- shell-write-gate:
  - A subagent (payload with `agent_id`) or a coder cannot disarm the gate with the skip comment.
  - A coder's redirect or `tee` onto a new file outside the temp roots is denied. `$TMPDIR` and `$HOME` are expanded
    and an unresolved `$` is denied. The rule is skipped for a relative target after a `cd`, `pushd` or `popd`.
  - Targets come from the shell parser, so a `>` inside quotes and `2>&1` are no writes. Heredoc bodies are stripped
    unless a shell reads them. `$(...)` and backtick spans are read as command text.
  - A command that names a code runner (a shell, `eval`, `su`, `script`, `flock`, `watch`, `xargs`, `find -exec`,
    docker/podman/kubectl exec, ssh) also gets the old raw-text redirect scan, with the tracked-file deny only.
  - The in-place deny names the edited file, not `2>&1`.
- inline-interpreter-hint denies code fed on stdin to a bare interpreter: `-`, a heredoc, a here-string, a pipe in,
  `/dev/stdin` and `manage.py shell`. `python3 < file` and version flags stay allowed.
- pipe-shell-check ignores a quoted `|`, strips heredocs first, sees through wrappers (`timeout`, `nice`, `env`,
  `sudo`) and runs its plain search whenever the text names a code runner.
- Shared: wrapper peeling, step splitting and heredoc stripping live in `lib/shell_command.py` and
  `lib/shell_statements.py`; the temp-root helpers live in `lib/hook_input.py`.

## Evidence

- Four queue items from this machine: subagents wrote tracked files through redirects the gate skipped, coders fed
  code on stdin past the hint, the gate denied `2>&1` and quoted `>` text, and the pipe check matched a quoted `|`.
- On the base commit, the stdin-code test (65 subtests), the quoted-`>` coder test, the quoted-`|` pipe test and the
  subagent skip-comment test fail; all pass after.
- Work hook latency puts each gate near 33 ms; the added parsing costs about 8 ms per call for the write gate and 2 ms
  for the hint on this machine.
- Not done: a relative target after `cd` still resolves against the hook's cwd, as before.

## Result

- Full suite on the rebased branch: 2976 tests in 79 files, 0 failed. Ruff passes.

## Watch

— (unmeasured; see frontmatter)

## Back-out

Revert the commit. No saved state depends on it.
