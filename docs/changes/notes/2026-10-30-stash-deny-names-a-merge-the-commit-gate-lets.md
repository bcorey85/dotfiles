---
type: "Change"
change_type: "fixed"
title: "Stash deny names a merge the commit gate lets through"
description: "The stash and autostash denies now name `git merge <base>` with the work uncommitted in place of a WIP commit the review commit gate refused, and that gate judges a commit against the repos a coder edited, and every repo when the coder's edits cannot be read or a dirty mark is set."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T09:46:18-05:00"}
seq: 360
kind: "fix"
components: ["script/review-commit-gate", "script/git-discipline-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_coder_work_in_one_repo_denies_a_commit_there_and_lets_one_in_another_repo_through"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The git stash and autostash denies no longer say to set work aside with a temporary WIP commit. They name
  `git merge <base>` with the work uncommitted: git stops and changes nothing when the merge touches an edited file,
  and if it stops, the work is committed after /review hands back converged or deferred, then merged.
- A conflicted merge's `git commit` already passes the review commit gate, because MERGE_HEAD exists. A test now pins
  that.
- The review commit gate reads each coder dispatch's subagent transcript and marks dirty only the repos its
  file-edit tool calls (the gate's EDIT_TOOL_PATH_KEYS) touched. A commit in another repo passes. A dispatch whose
  edits cannot be read, or that edited nothing inside a repo, and every `dirty` mark, still make every repo dirty.
- Known gap: a file a coder edits only through the shell is not seen as an edit. When that coder also edited
  through a tool, the repo the shell file lives in is judged clean unless the tool edits were there too.

## Evidence

- Mid-lane, a session needed a base merged into unfinished coder work. The stash deny sent it to a WIP commit, and the
  review commit gate refused that commit for unreviewed coder work, so no path the gates named worked.
- A coder's work in one worktree also made the gate refuse an unrelated commit in another repo of the same session.

## Result

Against the gate before this change, the per-repo test fails: the commit in the other repo is denied. After it,
`test_review_commit_gate.py` and `test_git_discipline_gate.py` pass (124 tests) and ruff passes.

## Watch

None; a fix with no intake number.

## Back-out

Revert the commit. The stash deny then names a WIP commit the review commit gate refuses, and one coder's work again
blocks commits in every repo of the session.
