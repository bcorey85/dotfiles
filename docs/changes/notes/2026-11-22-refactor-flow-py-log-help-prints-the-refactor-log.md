---
type: "Change"
change_type: "changed"
title: "refactor_flow.py log --help prints the refactor log input template"
description: "The refactor log input grammar and its template move from refactor_flow.py and SKILL.md into refactor_log_input.py; `log --help` prints the field notes and a template that logs on the first call."
generated: {"by": "claude-code/claude-fable-5-1", "at": "2026-11-22T19:05:21-06:00"}
seq: 35
kind: "fix"
components: ["script/refactor-flow", "script/refactor-log-input", "skill/refactor"]
evidence: ["removal round", "census"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_the_log_template_in_log_help_logs_on_the_first_call"
asked: ""
proof: []
unmeasured: ""
---

## Change

`claude/.claude/skills/refactor/scripts/refactor_log_input.py` owns the `refactor_flow.py log` input grammar, the field notes and the template. `refactor_flow.py` imports it and its `log` subparser prints the notes and the template between start and end markers in `--help`. The refactor skill and close-branch point at `log --help` in place of the inline example.

## Evidence

The log input example and its format rules lived in `skills/refactor/SKILL.md` and in the script docstring, paid for on every dispatch and drifting from the grammar that read them.

## Result

`test_the_log_template_in_log_help_logs_on_the_first_call`, `test_the_log_grammar_lives_in_refactor_log_input` and `test_refactor_flow_is_at_most_1000_lines` in `tests/scripts/test_refactor_flow.py`.

## Watch

None.

## Back-out

Revert the commit.
