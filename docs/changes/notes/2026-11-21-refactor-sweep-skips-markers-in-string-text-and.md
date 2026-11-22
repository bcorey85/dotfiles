---
type: "Change"
change_type: "fixed"
title: "refactor sweep skips markers in string text and prints in CLI scripts"
description: "The /refactor branch-prep sweep no longer lists a marker inside a single-line string literal or a multi-line string held as data, or a print( in a .py or .pyi file with a command-line entry point, as a debug leftover."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-21T20:36:55-06:00"}
seq: 5
kind: "fix"
components: ["skill/refactor"]
evidence: ["refactor-sweep-flags-print-inside-a-string-literal", "refactor-sweep-flags-every-print-call-in-a-cli"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_branch_prep_sweep_skips_print_in_a_cli_script_but_keeps_todo_and_library_prints"
asked: ""
proof: []
unmeasured: ""
---

## Change

- The sweep moved from `skills/refactor/scripts/refactor_flow.py` into the new `skills/refactor/scripts/sweep_markers.py`.
- The sweep reads each changed file's post-image (the work-tree file, or `git show <head>:<path>` with `--head`) and masks single-line string literals and multi-line strings held as data through `lib/source_text.py` before it matches a marker. A marker in a comment or a docstring is still a hit, and so is one in a file of an unknown suffix (Markdown, plain text), which is never masked. YAML has the hash style, so an apostrophe pair in a plain scalar is still masked.
- In a .py or .pyi file with a command-line entry point, a `print(` or `pprint(` is no hit. TODO-class markers there, and a `print(` in library code, are still hits.
- branch-prep stops when the post-image it reads does not hold the diff's added line.

## Evidence

Queue item `refactor-sweep-flags-print-inside-a-string-literal`: a `print(` inside a test fixture string was put on the work list. Queue item `refactor-sweep-flags-every-print-call-in-a-cli`: on the near-clones branch, both listed lines were a CLI script's real report output.

## Result

`test_branch_prep_sweep_ignores_a_marker_inside_a_string_and_keeps_a_bare_statement` and the named test fail on the old sweep and pass with the change.

## Watch

None. No intake number reads this.

## Back-out

Revert the commit.
