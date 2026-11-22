---
type: "Change"
change_type: "fixed"
title: "Review loop lint and format skip files the pre-commit exclude or oxlint ignore config leaves out"
description: "The loop's lint and format file list now leaves out every file the top-level exclude of the repo's pre-commit config matches and every file a ruff hook's own exclude matches, and an oxlint whose ignore config leaves out every named file is no longer a lint problem."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T13:32:23-06:00"}
seq: 22
kind: "fix"
components: ["script/format-files", "script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_format_files.py::PreCommitExcludeTest::test_a_file_the_top_level_exclude_matches_is_neither_formatted_nor_linted"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/format_files.py`: `exclude_value` reads an `exclude:` key of a pre-commit config, as a one-line value or a `|` or
`>` block scalar. `sort_files` drops each file the top-level exclude matches, for every tool. `ruff_targets` drops a
Python file from `ruff format` or `ruff check` when every ruff hook of that kind excludes it, with or without a ruff
config file. In check mode `web_lint_command` gives oxlint `--no-error-on-unmatched-pattern` when that oxlint's
`--help` lists the flag.

No change for eslint (flat config and `.eslintrc`), prettier, oxfmt and biome. Each was run on a named ignored file:
eslint 9.39 and 8.57, prettier 3, oxfmt and biome 1.9.4 all left the file alone and exited 0. The loop never runs
biome.

## Evidence

judgment: a lint repair reformatted 44 files that no phase touched, in a repo whose pre-commit config excludes them.
oxlint 1.94 skips a named file its `ignorePatterns` match, and exits 1 with "No files found to lint" when it skips
every named file, which the loop read as a lint problem.

## Result

The new reader parsed 36 of 36 pre-commit configs under `~/dev` (two shapes: no exclude, and a top-level block
scalar). `test_format_files.py`: 58 tests pass.

Not covered: oxlint 1.94 lints a named file under a folder pattern (`gen/`) of `.eslintignore`, though it skips the
same file for `gen/**` and for either form in `ignorePatterns`. oxlint 1.0 and older lint every named file and have
no flag for it.

## Watch

None: a file list filter with a fixed outcome.

## Back-out

Revert the commit.
