---
type: "Change"
change_type: "fixed"
title: "The review commit gate sees a commit behind a git option joined to a substitution"
description: "is_commit_command also reads the command with each substitution span shrunk, so `git -p\"\"$(cat <<'EOF' ...)\"\" commit` and `git -C$(echo a b) commit` count as commits and a dirty session is denied."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-28T11:00:00-05:00"}
seq: 151
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::NotesOnlyCommitTest::test_a_commit_behind_a_git_option_joined_to_a_quoted_heredoc_is_denied"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `is_commit_command` runs its readings twice: on the text as written, and on the text with each quoted heredoc,
  paren-free `$( )` and backtick span shrunk to `$S`. Either reading that finds a commit counts.

## Evidence

- `git -p""$(cat <<'EOF' ... EOF)"" commit` was allowed while a repo held unreviewed coder work. The `$(` sits outside
  quotes, so the shell splitter cut the command at `(`, and the text regex stopped at the heredoc's first space.
- An unquoted `$( )` with a space, glued to an option (`git -C$(echo a b) commit`), had the same miss.
- The new tests fail on the old script.

## Result

- Coder work does not get committed past the gate through a substitution glued to a git option.

## Watch

—

## Back-out

Revert the commit.
