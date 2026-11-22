---
type: "Change"
change_type: "fixed"
title: "Commit gate passes session scratch repos and quoted commit words piped to text tools"
description: "The review commit gate lets a session commit in a throwaway repo under its own scratchpad, and no longer reads commit words quoted in a script's argument as a commit when the script's output goes to a text tool."
generated: {"by": "claude-opus-5-5/lane-code-gates", "at": "2026-11-21T18:44:44-06:00"}
seq: 2
kind: "fix"
components: ["script/review-commit-gate", "script/commit-gate-dirty", "script/shell-statements", "script/shell-command", "script/hook-input"]
evidence: ["queue item review-commit-gate-blocks-scratch-repo-saves-again: a scratchpad repo commit and a build_queue call whose --body quoted git commit, piped to tail -5, were both denied"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_commit_in_a_repo_under_the_sessions_scratchpad_passes_a_dirty_session"
asked: ""
proof: []
unmeasured: ""
---

## Change

The dirty tracking moves with no behavior change from `review/review_commit_gate.py` (now 923 lines) into `review/commit_gate_dirty.py`.

`is_clear` passes a repo whose top and git common dir lie under `<temp root>/<project slug>/<session>/`, when no coder dispatch's edits name it, every coder's edits were readable with an agent id, and it is not the reviewed repo. A reviewed scratch repo is still judged by its review.

`shell_command.DIRECTORY_FREE_CONFIG` adds `user.name` and `user.email`, so `git -c user.name=b commit` still places the commit in its repo.

`shell_statements.blank_script_run_quotes` blanks a script step that a `|` follows when no later step of that pipeline names a code runner, a shell, `source` or `.`. A pipe into a shell or an unparsable step stays as written.

## Evidence

Both denied commands are captured as fixtures. `test_a_commit_in_a_repo_under_the_sessions_scratchpad_passes_a_dirty_session` and `test_a_script_run_piped_into_a_text_tool_that_quotes_commit_words_is_not_a_commit` fail without the change.

## Result

The phase gate and the full suite pass, apart from `test_rule_anchors`, which also fails on master.

## Watch

A commit under a session scratchpad that should have needed review, and a piped script step whose quoted text did feed a shell.

## Back-out

Drop the scratch-repo branch from `is_clear`, the two `DIRECTORY_FREE_CONFIG` entries, and the pipeline check in `blank_script_run_quotes`.
