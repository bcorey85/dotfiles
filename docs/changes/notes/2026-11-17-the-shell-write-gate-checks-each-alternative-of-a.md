---
type: "Change"
change_type: "fixed"
title: "The shell-write gate checks each alternative of a non-coder brace-list target"
description: "A non-coder redirect or tee to an unquoted brace list is denied when any alternative is a tracked file, and denied whole when the list is over 64 words or a sequence."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-17T19:33:21-06:00"}
seq: 5
kind: "fix"
components: ["script/shell-write-gate"]
evidence: ["tests"]
watches: []
test: "tests/scripts/test_shell_write_gate.py::ShellWriteGateTest::test_the_main_session_is_denied_a_brace_list_with_a_tracked_alternative"
asked: ""
proof: []
unmeasured: ""
---

## Change

`check_brace_lists` expands an unquoted comma list in a non-coder target (`shell_expansion.expand_braces`,
nested lists too) and checks each word as its own target. It reads the raw words of each step, so a target the parser
cannot read (`{';',README.md}`, `{a\;b,README.md}`) and the text of `eval '...'` or `bash -c '...'` are checked too. `echo hi > {a,README.md}` and
`echo hi > {a,README.md}(N)` are denied `[tracked_target]`. A list over 64 words or a `{1..3}` sequence is denied
whole. A coder's brace list in code-runner text (`eval 'echo x > {tracked.txt,b}'`, `bash -c '...'`, `eval 'echo x | tee {tracked.txt,b}'`)
is checked per alternative against tracked files too, as a non-coder's is
(`test_a_coder_brace_list_in_code_runner_text_checks_each_alternative`). A glob target for a non-coder is not expanded: that adds non-coder denies and needs its own replay
(queue item `shell-write-gate-main-session-expand-a-glob`).

## Evidence

Asked in this branch's verify review; accepted by the lane.

## Result

The test fails on master's gate (the write is allowed) and passes now. The replay shows no verdict change from it on a
real command. It changed three verdicts on this branch's own probe commands, where a code runner's name sits in a
`printf` argument, so the whole text is read by regex: `{a,README.md}` there is denied as `README.md` alone already
was on master, and a coder's over-64-word list there is denied whole.

## Watch

None.

## Back-out

Remove the `check_brace_lists` call in `check_redirect_targets`.
