---
type: "Change"
change_type: "fixed"
title: "Quality-check cap skips a run a shell parse error stopped"
description: "A check command that fails on a shell parse or quoting error before any step runs is no longer counted toward the quality-check cap, so the clean rerun after the quoting fix is allowed."
generated: {"by": "claude-opus-5-5/lane-code-gates", "at": "2026-11-21T18:44:44-06:00"}
seq: 1
kind: "fix"
components: ["script/quality-check-cap", "script/check-output"]
evidence: ["queue item quality-check-cap-counts-failed-to-launch-gate: a quoting slip in a check command was counted, and the fixed rerun was capped"]
watches: []
test: "tests/scripts/test_quality_check_cap.py::QualityCheckCapTest::test_a_run_a_shell_parse_error_stopped_before_it_started_is_not_counted"
asked: ""
proof: []
unmeasured: ""
---

## Change

`check_output.shell_parse_error_line(output)` returns the shell's parse-error line when the output starts with one, after one optional `Exit code N` line. It matches `(eval):N:` on any line, and `zsh:1:` or `bash: line 1:` only on line 1, followed by `unmatched` quote, `parse error`, `unexpected EOF`, `parse error: condition expected` (the bare words `condition expected` do not match) or `syntax error near unexpected token`. `no matches found` and a runner's own `SyntaxError` are not parse errors. The PostToolUseFailure skip block in `gates/quality_check_cap.py` skips such a run.

## Evidence

Real transcripts held 20 bare `(eval):1: unmatched "` failures, 9 after `Exit code 1`, and 5 `parse error near`. `test_a_run_a_shell_parse_error_stopped_before_it_started_is_not_counted` fails without the change.

## Result

The phase gate and the full suite pass, apart from `test_rule_anchors`, which also fails on master.

## Watch

A check run that failed on real code but whose first output line looks like a shell parse error, and so went uncounted.

## Back-out

Remove the `shell_parse_error_line` call from the skip block in `quality_check_cap.py`.
