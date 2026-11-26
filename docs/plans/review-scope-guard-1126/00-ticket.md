# Review loop fix pass: edits outside the review scope

Source: ~/agent-evals/queue/review-loop-fix-pass-kept-an-edit-to-a-file.md
Source: ~/agent-evals/queue/review-loop-fix-pass-edits-a-sibling-repo-outside.md

## Ticket 1

---
type: "QueueItem"
title: "review loop fix pass kept an edit to a file outside the branch diff and reworded a ticket AC"
description: "A capped /review left an out-of-scope script edit and an AC-changing reword in the work tree, so the push needs a manual revert and a ruling."
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T10:45:13-06:00"}
kind: "chore"
status: "running"
rank: 2111
blocked_by: []
source: "claude/.claude/scripts/review/review_loop_scope_guard.py"
components: ["script/review-loop", "script/review-loop-scope-guard"]
not_dup: "2026-11-22-review-loop-puts-back-files-a-fix-pass-changed"
---

## Context
A branch /review of a small gate change hit its cap. The work tree after it held: (1) a refactor of scripts/.local/bin/hunk-review-pane plus 48 new test lines in tests/scripts/test_hunk_review_pane.py, neither in the branch diff, so the scope guard did not put them back; (2) a reworded deny reason in wait_loop_gate.py that replaced the ticket AC's "Bash timeout up to 600000 ms" with "about 150 seconds", with no ask filed for an AC change. The stop packet named neither. The lane had to diff the tree by hand to find them.

## Done when
A test where a fix pass edits a file outside the branch diff ends the loop with that file put back (or named in the stop packet), and a fix that changes text an AC quotes is filed as an ask, not applied.

## Root cause (found later the same run)
The resumed loop diffs against the origin/master tip (a commit landed on master after the branch's merge-base), not the merge-base. Master's own new change to hunk-review-pane shows up as this branch's diff, reversed, so reviewers file findings on master's code and the fix pass edits it; the scope guard treats it as in scope. The owner for a base without merged-in commits is lib/merge_free_base.py; the loop's base should be the merge-base with the branch.

## Ticket 2

---
type: "QueueItem"
title: "review loop fix pass edits a sibling repo outside the reviewed repo and the scope guard misses it"
description: "The scope guard catches fix-pass edits outside the reviewed repo, so a brief that forbids editing a sibling repo holds"
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-24T13:34:31-06:00"}
kind: "chore"
status: "running"
rank: 2116
blocked_by: []
source: "claude/.claude/scripts/review/review_loop_scope_guard.py"
components: ["script/review-loop"]
not_dup: "that fix covered a CLAUDE.md inside the reviewed repo; this edit landed in another repo"
---

## Context
A /review on a dotfiles branch had a brief that said never edit ~/agent-evals. Its fix pass added functions to two agent-evals files, left them uncommitted, and changed the dotfiles script to depend on them. The scope guard puts back only files inside the reviewed repo, so the edit stayed and the session found it only by reading the stop text.

## Done when
A test of the scope guard: a fix pass that writes a file outside the reviewed repo's work tree has the write reported as a blocker (or put back), and the run does not end as if the edit belonged to it.
