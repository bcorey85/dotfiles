---
type: "Change"
change_type: "fixed"
title: "format_files reads ruff and ruff-format from a pre-commit-only repo"
description: "The review loop's format step now runs ruff in a repo whose only ruff setup is a ruff, ruff-check or ruff-format hook in its pre-commit config, and the lint pass now runs `ruff check` on the Python files the ruff hooks' `files:` regexes match."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-13T09:30:00-06:00"}
seq: 2
kind: "fix"
components: ["script/format-files", "script/review-loop-script", "script/full-check"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_format_files.py::RunFormattersTest::test_ruff_runs_in_a_repo_whose_only_ruff_setup_is_pre_commit_hooks"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/format_files.py`: `repo_configures_ruff` is also true when `.pre-commit-config.yaml` has a hook with id `ruff`,
`ruff-check` or `ruff-format`, and `repo_formats_with_ruff` is also true for the id `ruff-format`. The hooks are read
line by line, because the toolkit has no YAML parser. The review loop's lint pass (`lint_problems`) now runs
`ruff check` on the Python files the ruff hooks' `files:` regexes match, so a violation there triggers a `coder-lint`
repair and can stop the loop as `critical-blocker`.

When ruff is enabled only through those hooks (no `ruff.toml`, `.ruff.toml` or `[tool.ruff]`), ruff runs on the Python
files the hooks' `files:` regexes match (`exclude:` is not read): each hook's `files:` regex is kept next to its id,
`ruff format` runs on the files a `ruff-format` hook matches, `ruff check` (fix and lint pass) on the files a `ruff` or
`ruff-check` hook matches, and a hook with no `files:` matches every file. A ruff command with no hook of its kind runs
on no files. A quoted `files:` value loses one matching pair of quotes, and a single-quoted `''` becomes `'`;
a double-quoted value with a backslash (YAML escapes are not decoded) means every file; a block-scalar or other value
the line match cannot read means every file. A regex that does not compile means every file. With a ruff config file, every file is
still handed to ruff.

## Evidence

judgment: a repo that runs ruff only through `astral-sh/ruff-pre-commit` got no ruff run, so the loop handed back
files that the pre-commit `ruff-format` hook rewrites. Both pre-commit configs on the dev machine have this shape.

## Result

The new test fails on the old tree (no formatting happens) and passes. A repo with neither a config nor a ruff hook
still runs no ruff.

## Watch

None: a fixed rule.

## Back-out

Revert the commit.
