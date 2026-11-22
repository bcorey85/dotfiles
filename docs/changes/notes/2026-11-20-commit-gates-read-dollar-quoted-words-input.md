---
type: "Change"
change_type: "fixed"
title: "Commit gates read dollar-quoted words, input duplication and a backgrounded cd chain"
description: "The review commit gate reads $'...' words as the shell runs them; the shared parsing treats <& as no background operator and reads a cd chain that a trailing & ends as conditional."
generated: {"by": "claude-sonnet-5-5/coder", "at": "2026-11-20T20:41:55-06:00"}
seq: 2
kind: "fix"
components: ["script/git-discipline-gate", "script/review-commit-gate", "script/shell-command", "script/git-calls", "script/shell-statements", "script/shell-quoting"]
evidence: ["review of the shell gates: git $'commit' read as no commit by the review commit gate, so it passed a commit the gate should hold"]
watches: []
test: "tests/scripts/test_review_commit_gate.py::ReviewCommitGateTest::test_an_ansi_c_quoted_commit_word_or_option_is_denied_as_the_discipline_gate_reads_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

Three readings change in the shared shell parsing the commit gates use.

`$'...'` words: `shell_statements.without_ansi_c_quotes` replaces each unquoted `$'...'` string by its decoded, shell-quoted text before a gate splits words, so `git $'commit' $'--amend'` reads as `git commit --amend`. A `$'` in quotes or a comment stays; two strings in one command both decode; an unterminated one stays. Only `review_commit_gate.py` calls it: the git-discipline gate already decoded `$'...'` through `shell_statements.resolved_word`, so its verdicts on these commands do not change.

A `$'...'` word in a git option or pathspec now counts toward commit credit, read as the decoded word the same way as a plain one: `git $'-C' /tmp/x commit -m y` gets credit for `/tmp/x` and `git commit -m y $'-a'` for the repo; both got none before.

`<&`: `shell_command.OPERATOR` no longer reads the `&` of `cat <&3` as a lone `&`, so the step is not sent to the background and is not split.

`cd x && y &`: `git_calls.has_conditional_cd` reads a `cd` in a list that a trailing `&` ends as conditional (the list runs in a subshell), so the git call after it reads as the main checkout's. `|&` stays inside its step.

## Evidence

The review commit gate allowed the `$'...'` commit forms before and denies or counts them as commits now (`test_an_ansi_c_quoted_commit_word_or_option_is_denied_as_the_discipline_gate_reads_it` in the review-commit-gate tests fails without the change). The discipline gate's `test_an_ansi_c_quoted_amend_already_held_before_the_change` pins a verdict that already held. The other two readings are pinned by `test_an_input_descriptor_copy_is_no_lone_ampersand` and `test_a_cd_that_may_not_run_or_runs_in_a_subshell_is_conditional`.

## Result

The 12002-command replay of real Bash commands (see the computed-target note) was run over the final tree; its verdict changes are listed there.

## Watch

A command that uses `$'...'` and is now denied by the review commit gate, and a `cd x && git ... &` chain whose git call now reads as the main checkout's, and a commit with `$'-C'` or `$'-a'` that now gets commit credit. Each one is the case to review.

## Back-out

Remove the `without_ansi_c_quotes` calls from `review_commit_gate.py`; restore `<>&` in the `OPERATOR` lookbehind; drop the background check from `has_conditional_cd`.
