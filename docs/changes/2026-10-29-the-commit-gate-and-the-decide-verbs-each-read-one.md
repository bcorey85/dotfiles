---
type: "Change"
change_type: "changed"
title: "the commit gate and the decide verbs each read one shared option list"
description: "The commit gate reads git's value options only from shell_command, and both plan-impact decide verbs take their vocabulary from plan_format, so two pairs of drifting copies become one each."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T18:01:05-05:00"}
seq: 287
kind: "fix"
components: ["script/review-commit-gate", "script/review-fix", "script/code-step"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewedWorkCommitTest::test_a_bare_git_exec_path_commit_is_credited_to_the_cwd"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The review commit gate drops its own copy of git's value-option list and its hand-written option walks. It reads git's value-taking options only from `shell_command` (`git_options` and `GIT_VALUE_OPTIONS`); its flag list and the `=`-form `--exec-path` stay in the gate. The gate's copy listed `--exec-path` as taking a separate value. `--exec-path` takes a value only in its `=` form; the bare form prints git's exec path and exits. The word walk now agrees with the text regex that bare `git --exec-path commit` is a commit, and `commit_dir` now credits it to the cwd instead of refusing credit. This is harmless because the bare form only prints git's exec path and never commits. `git --exec-path <word> commit` is no longer read as a commit, because git exits before it reads `<word>`.
- The plan-impact decide vocabulary (the options, the decision words, the `--by` note, the usage stem and the `--by` user/session check) moves into `plan_format`, next to `ruling_owner` and `ruling_deviation`, the other plan-impact ruling helpers. `code_step_review.py` and `review_fix.py` both import it. Printed messages are unchanged.

## Evidence

judgment: a read-only simplify review found the two copies of each list, and that the git list had already drifted.

## Result

The gate's word walk reads both `git --exec-path commit` and `git --exec-path=/x commit` as a commit. The bare form never commits (git prints its exec path and exits), so crediting it to the cwd is harmless. The decide usage stem had two copies, `code_step_usage.DECIDE_COMMAND` (shared with `code_step_review`) and `review_fix.DECIDE_USAGE`; both now read `plan_format.DECIDE_USAGE_STEM`.

## Watch

None.

## Back-out

Revert this change's commit.
