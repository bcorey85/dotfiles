---
type: "Change"
change_type: "fixed"
title: "git commit readers read stored-heredoc-cut text"
description: "A git commit line inside a stored heredoc body (cat > f <<EOF) is no longer read as a commit by the git discipline gate; bodies a shell runs (bash <<EOF, | bash) stay read."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-26T12:59:02-06:00"}
seq: 18
kind: "fix"
components: ["script/git-commit-calls", "script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_git_discipline_gate.py::SharedCloneCommitTest"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/git_commit_calls.py` `git_commit_dirs` and `gates/git_discipline_gate.py` `is_sole_git_command` now read `shell_statements.strip_stored_heredocs(command)`. A `git commit` line inside a heredoc body that only stores text (`cat > f <<EOF`) is no longer read as a commit. A body a shell runs (`bash <<EOF`, `| bash`) is still read.

## Evidence

`SharedCloneCommitTest` gains cases for a stored body (no commit), a body that runs (a commit), a body another command runs (read), and a stored body with an apostrophe (the sole-step read still works).

## Result

A command that writes commit-message text or a script with `cat > f <<EOF` no longer trips the shared-clone commit checks.

## Watch

—

## Back-out

Drop the `strip_stored_heredocs` call in `git_commit_dirs` and in `is_sole_git_command`.
