---
type: "Change"
title: "Let a dirty session commit docs-only changes without asking"
description: "review-commit-gate.py no longer asks the user when a dirty session commits only docs/**.md files, and it now asks for git commit forms it used to miss."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-22T08:00:03-05:00"}
seq: 3
components: ["script/review-commit-gate", "script/shell-command"]
evidence: ["work incident"]
watches: []
---

## Change

- `scripts/review-commit-gate.py`, docs-only skip: a dirty session does not ask when every path is a `docs/**.md` file. The paths are the ones already staged, plus the `git add` and `git commit` pathspecs in the same command. The gate asks as before for these:
  - a folder, `.`, a glob or a `git add` option
  - a commit that can stage more at commit time
  - a redirect to a file
  - a read-only git subcommand with `--output`
  - any command it cannot read
- Commit detection: line continuations are joined first. A text check runs on every command, and it takes a value only after git's own value options. A looser check runs when the command cannot be parsed. Every word named `git` is tried, not only the first. So `git -C $(…) commit`, `git -C \`…\` commit`, `git \` + newline + `commit`, a quoted option value, `env -u git git … commit` and `eval '… commit'` now ask while dirty.
- `scripts/shell_command.py`: a quoted word that holds only a newline is an operator, not a command break.
- Tests: `test_review_commit_gate.py` and `test_shell_command.py` under `tests/scripts/`.

## Evidence

- Work incident: a coder that only rewrote plan markdown left the session dirty, so every later commit asked the user. Six live sessions were dirty at one time, across four tickets.

## Result

Docs-only commits after a coder run no longer stop for the user. Code commits in a dirty session ask in more command forms than before. Known gap, also present before: a global option with an attached substitution that holds a space, such as `--git-dir=$(git rev-parse --git-dir)`, still commits with no ask.

## Watch

None. The intake does not count commit-gate asks.

## Back-out

Restore the previous `review-commit-gate.py` and `shell_command.py` from git.
