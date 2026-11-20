---
type: "Change"
change_type: "changed"
title: "The review commit gate skips the heredoc text of a script-file run"
description: "`review_commit_gate.py` no longer reads a commit in the heredoc body of an interpreter running a script file, such as `python3 bin/build_queue.py new <<'EOF'`. A commit beside that run is still denied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-17T23:54:09-06:00"}
seq: 3
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["tests", "transcripts"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_a_script_file_run_with_a_commit_named_in_its_heredoc_is_not_a_commit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `lib/shell_statements.py`: `strip_stored_heredocs` also cuts an unquoted stored heredoc, keeping its `$(...)` and backtick spans because the shell runs them.
- `review/review_commit_gate.py`: only the heredoc body of a script-file run is data: a script-file run whose arguments name a commit, bare or quoted (`python3 tools/retry.py 'git commit -m x'`), is a commit, since a wrapper script may run it.
- `review/review_commit_gate.py`: its folder-changing command words come from `shell_command.DIRECTORY_MOVE_WORDS` plus `eval`, `source` and `.`, not a second list.
- `lib/git_commit_calls.py`: names the `git commit` options that take a value (`COMMIT_VALUE_OPTIONS`, `COMMIT_VALUE_LETTERS`).

## Evidence

The 2026-11-15 sighting: the gate blocked `build_queue.py` whose heredoc quoted a commit command as prose, after the earlier quoted-heredoc fix. Other non-git programs whose quoted text names a commit (`gh pr create --body`) are still denied; no session hit that form.

## Result

Eight `ReviewCommitGateTest` cases. They pass: a script-file run with a commit named in its heredoc, and a file write beside a probe that names a commit. They are denied: a script-file run with a commit in a quoted argument (also with output to /dev/null or a file), a script-file run whose arguments hold a bare `git commit`, and a real commit beside a script-file run.

Median time on matched calls, 15 runs of 4 calls: branch 53.8 ms, master 53.1 ms; bare Python start 7.7 ms.

## Watch

None: a false block that stops recurring leaves no row.

## Back-out

Revert the commit.
