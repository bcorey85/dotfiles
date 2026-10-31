---
type: "Change"
change_type: "fixed"
title: "Shell statement reader skips heredocs with escaped or hyphenated delimiters"
description: "The heredoc opener pattern accepts a backslash-escaped delimiter and dots or hyphens in the delimiter, so the follow-mode gate no longer reads such a heredoc's file text as commands."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-26T22:44:10-05:00"}
seq: 99
kind: "fix"
components: ["script/wait-loop-gate"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_wait_loop_gate.py::WaitLoopGateTest::test_heredoc_with_an_escaped_or_hyphenated_delimiter_hides_its_follow_words"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `lib/shell_statements.py` HEREDOC: an optional `\` before the delimiter, and `.` or `-` after its first character.
  The body of `<<\EOF`, `<<'END-DATA'` or `<<-RULE.TXT` is now skipped like any other heredoc body.
- A delimiter that starts with a digit is still not read as a heredoc, so `$((x<<2))` never hides the lines after it.

## Evidence

- A fix pass on the work machine wrote rule test data holding `watch` through a heredoc, and the follow-mode gate
  denied it. The plain `<<'EOF'` form already passed; the escaped and hyphenated delimiter forms did not.
- The new test fails on the base reader and passes after; a real `watch` after such a heredoc is still denied.

## Result

- See the branch's suite run.

## Watch

—

## Back-out

Revert the commit.
