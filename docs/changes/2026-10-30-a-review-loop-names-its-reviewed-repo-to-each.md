---
type: "Change"
change_type: "fixed"
title: "a review loop names its reviewed repo to each reviewer it dispatches"
description: "The review-loop gate refuses a reviewer dispatch that leaves out the loop's sibling repo, and the reviewers run their commands in a named `Repo root`."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-30T05:08:41-05:00"}
seq: 393
kind: "fix"
components: ["script/review-loop-gate", "script/loop-transcript", "agent/code-reviewer", "agent/test-reviewer", "agent/smell-reviewer"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_gate.py::ReviewerRepoDispatchTest::test_a_reviewer_brief_without_the_sibling_repo_is_refused_with_that_repo"
asked: ""
proof: []
unmeasured: "One session saw it first-hand; no intake row counts reviewers that read the wrong repo."
---

## Change

`review_loop_gate.py` checks each Agent dispatch that a review-loop makes to a `*-reviewer` or `*-reviewer-deep` agent. When the loop's reviewed repo (`LoopTranscript.reviewed_repo`: the ROOT= that review-scope printed, else the `repo:` line, else the first path, else cwd) is not the work tree of the loop's cwd, the dispatch is refused unless its prompt has a `Repo root: <path>` line whose work tree is that repo. The `Repo root` path and the `repo:` path resolve through one helper, `loop_transcript.prompt_path_work_tree`. The reason names the line to add. A loop on its cwd's repo dispatches as before. The gate fails open on a transcript it cannot read.

`code-reviewer`, `test-reviewer` and `smell-reviewer` (and their opencode ports) now run every git and shell command as `cd <path> && <command>` when the prompt names `Repo root: <path>`, and read files under that path. Before, none of them read the line, so a reviewer's `git diff` ran in the session's cwd.

## Evidence

A run dispatched with a `repo:` line naming a sibling worktree sent its test-reviewer to the session's cwd repo. review-loop.md Step 0 already told the loop to put `Repo root: <ROOT>` in every reviewer prompt; nothing checked that it did, and the reviewers ignored the line when it was there.

## Result

The new test dispatches `code-reviewer`, `smell-reviewer`, `test-reviewer` and `test-reviewer-deep` from a loop whose `repo:` line names a sibling repo: each brief without `Repo root` is refused with that repo named, each brief naming it passes, a brief naming the cwd repo is refused, and a loop on the cwd repo needs no line. It fails against the previous gate.

## Watch

None: no intake number reads which repo a reviewer ran its commands in.

## Back-out

Remove `reviewer_repo_deny_reason` and `REVIEWER_REPO_REASON` from `review_loop_gate.py` and its call in `check_dispatch`, `PROMPT_REPO_ROOT` from `loop_transcript.py`, the `Repo root` line from the three reviewer agents and their opencode ports, and `ReviewerRepoDispatchTest`.
