---
type: "Change"
change_type: "added"
title: "Deny a bare git commit in a shared clone"
description: "The git discipline gate denies a git commit with no pathspec in a listed shared clone, so a session cannot commit the files its peers staged."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-24T11:46:44-06:00"}
seq: 1
kind: "fix"
components: ["script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_commit_pathspec.py::SharedClonesTest"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/commit_pathspec.py` decides whether a `git commit` is bare (no pathspec, or an option that sweeps the index).
`lib/shared_clones.py` says whether a folder is a listed shared clone. `gates/git_discipline_gate.py` rule 11 denies a
bare commit there, through `-C`, `cd`, `--git-dir`, and runner text (`eval`, `bash -c`). `lib/git_calls.py` reads the
statement before a runner word through the shell word parser, so `FOO=1 eval`, `command eval`, `time eval`, a brace
group and an `if` block deny too.

## Evidence

A commit made with no pathspec in a shared clone took the files another session had staged.

## Result

New tests in `test_commit_pathspec.py`, `test_git_discipline_gate.py` and `test_shell_statements.py` pass; the five
prefix and block eval rows failed on the earlier code. Ruff is clean on the changed files.

## Watch

None. Read the next gate denies in a shared clone for false denies.

## Back-out

Remove rule 11 from `gates/git_discipline_gate.py` and delete `lib/commit_pathspec.py`, `lib/shared_clones.py` and
their tests.
