---
type: "Change"
change_type: "fixed"
title: "Review loop lint and format skip files the pre-commit exclude or oxlint ignore config leaves out"
description: "The loop's lint and format file list, and the turn-end format hook's, now leave out every file the top-level exclude of the repo's pre-commit config matches, and every file a ruff hook's own exclude matches is left out of that hook's ruff run, and an oxlint whose ignore config leaves out every named file is no longer a lint problem."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T13:32:23-06:00"}
seq: 22
kind: "fix"
components: ["script/format-files", "script/format-changed", "script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_format_files.py::PreCommitExcludeTest::test_a_file_the_top_level_exclude_matches_is_neither_formatted_nor_linted"
asked: ""
proof: []
unmeasured: "The oxlint file filter reads only the .eslintignore and .oxlintrc.json at the repo root, needs git and a git work tree, and does not read an oxlint.config.ts or a nested config."
---

## Change

`lib/format_files.py`: `exclude_value` reads an `exclude:` key of a pre-commit config, as a one-line value or a `|` or
`>` block scalar; a line indented further than the block keeps its extra spaces and its line breaks, as YAML reads
it (6 of 6 shapes read the same as PyYAML). `run_formatters` and `lint_problems` read the pre-commit config once per
call and hand it to `sort_files` and `ruff_targets`, which both take it as a required argument. `sort_files` drops
each file the top-level exclude matches, for every tool. `ruff_targets` drops a Python file from `ruff format` or
`ruff check` when every ruff hook of that kind excludes it, with or without a ruff
config file. The turn-end format hook (`gates/format_changed.py`) calls the same function, so it skips those files
too. In check mode `web_lint_command` gives oxlint `--no-error-on-unmatched-pattern` when that oxlint's
`--help` lists the flag.

`web_lint_files` drops, before oxlint is called for a check or a fix, each file the repo's oxlint ignore sources
leave out: `.eslintignore` and the `ignorePatterns` of `.oxlintrc.json`, both at the repo root. With no file left,
oxlint is not called. `lib/oxlint_ignore.py` owns the match and hands the patterns to git's own gitignore matcher
(`git ls-files --ignored --exclude`), so no pattern matcher is written here. `lib/jsonc_text.py` reads the config,
which may hold comments and trailing commas. Where git cannot answer, oxlint gets every file, as before.

No change for eslint (flat config and `.eslintrc`), prettier, oxfmt and biome. Each was run on a named ignored file:
eslint 9.39 and 8.57, prettier 3, oxfmt and biome 1.9.4 all left the file alone and exited 0. The loop never runs
biome.

## Evidence

judgment: a lint repair reformatted 44 files that no phase touched, in a repo whose pre-commit config excludes them.
oxlint 1.94 skips a named file its `ignorePatterns` match, and exits 1 with "No files found to lint" when it skips
every named file, which the loop read as a lint problem.

## Result

The new reader parsed 36 of 36 pre-commit configs under `~/dev` (two shapes: no exclude, and a top-level block
scalar). `parse_jsonc` parsed 20 of 20 `.oxlintrc.json` files under `~/dev` (6 hold comments). `test_format_files.py`:
62 tests pass; `test_jsonc_text.py`: 4.

Two cases the loop now covers itself: oxlint 1.94 lints a named file under a folder pattern (`gen/`) of
`.eslintignore`, and oxlint 1.0 and older lint every named file and have no flag for it.

Not covered: an `oxlint.config.ts`, a nested config, and a repo that is not a git work tree.

## Watch

None: a file list filter with a fixed outcome.

## Back-out

Revert the commit.
