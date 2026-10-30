---
type: "Change"
change_type: "fixed"
title: "Commit gate reads parsed commands for review credit and names a lost credit in its deny"
description: "A reviewed commit keeps its credit when a chained add or a message holds commit or cd, and a deny caused by the command form names the fix instead of asking for a second review."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T09:23:27-05:00"}
seq: 342
kind: "fix"
components: ["script/review-commit-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_message_or_a_path_holding_a_folder_word_keeps_the_credit"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `claude/.claude/scripts/review/review_commit_gate.py`: a step voids credit only when the gate's own commit check counts it as a commit, so `git -C <wt> add <file with commit in its name>` and `git log --grep commit` no longer void it. `env -C <dir> git commit` and `sh -c` forms still do.
- The folder-change check runs on parsed words and leaves out plain `git add` and `git commit`, so a message or a path may hold `cd`. A folder change in any other step, or `GIT_DIR=x git commit`, still voids credit.
- A code runner in any step other than a plain `git add` or `git commit` (`| sh`, `bash <<<`, `sh -c`), an emptied quoted-heredoc message held as a word or a redirection target by such a step, and a command the gate cannot read all void credit. A `.` after `if`, `then`, `elif`, `else`, `while`, `until` or `do` voids it, and so does `git --config-env=...`.
- `claude/.claude/scripts/lib/shell_command.py`: `GROUP_WORDS` now holds those seven keywords, so every hook that peels wrappers sees the command after them, and `is_git_word` lives here.
- A command over more than one line, once its quoted-heredoc messages are emptied, earns no credit. The parser cannot follow a comment or a continuation across lines, so the gate stops trying. A one-line `git -C <wt> commit -m "msg"`, a quoted-heredoc message and a chained add then commit on one line keep credit, and the deny says to use one line or a heredoc.
- When a command earns no credit and the session holds a review that credits a repo, the deny names that repo and `git -C <repo> commit`, and says not to run /review again. The general deny now says a commit after a `cd` earns no credit.
- A test pins that a deferred hand-back credits a `git -C <repo> commit`. The base branch already passed it, so no code changed for that case.

## Evidence

Three reports from one day: a chained add denied a reviewed commit, a worker ran a second review for a `cd` deny three times, and a commit message holding the word cd voided credit.

## Result

The named test and its neighbours fail on the old gate and pass on the new one. The gate's test file passes.

## Watch

None. No intake number reads the deny text.

## Back-out

Revert the commit. The gate returns to voiding credit on raw text.
