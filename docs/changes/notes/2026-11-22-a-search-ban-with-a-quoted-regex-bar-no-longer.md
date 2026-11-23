---
type: "Change"
change_type: "fixed"
title: "A search ban with a quoted regex bar no longer reads GREEN on a hit"
description: "The criteria dry run tells a real pipe from a regex bar inside quotes, so a ban such as rg -q 'a|b' f that exits 0 reads RED."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T20:38:59-06:00"}
seq: 37
kind: "fix"
components: ["script/criteria-dry-run"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_criteria_verdict.py::ItemVerdictTest::test_a_quoted_regex_bar_ban_that_exits_zero_reads_red_with_the_hit_count"
asked: ""
proof: []
unmeasured: "A bar-in-quotes ban is not logged as its own number."
---

## Change

`criteria_verdict.py` picks the pipe form of a search ban with `has_pipe`, which reads only an unquoted `|` through `split_command_steps`. A bar inside quotes is a regex alternation, so the ban is judged by exit code.

## Evidence

judgment: a quiet search such as `rg -q 'a|b' f` printed nothing and exited 0, which the old `"|" in command` test read as a pipe with empty output, so a broken ban read GREEN. The test fails on the base logic and passes now.

## Result

Targeted tests pass (38).

## Watch

None: no intake number reads this fix.

## Back-out

Revert the commit; the old substring test returns.

