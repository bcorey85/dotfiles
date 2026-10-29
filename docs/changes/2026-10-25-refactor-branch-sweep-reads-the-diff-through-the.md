---
type: "Change"
change_type: "fixed"
title: "Refactor branch sweep reads the diff through the shared parser"
description: "refactor_flow's sweep for markers and commented-out code now reads the branch diff with lib/source_text.parse_unified_diff, not its own line walker, so a line that holds a form feed or a lone carriage return is swept whole."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-25T20:30:53-05:00"}
seq: 17
kind: "fix"
components: ["skill/refactor"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_branch_prep_sweeps_a_whole_line_that_holds_a_form_feed_or_lone_carriage_return"
asked: ""
proof: []
unmeasured: ""
---

## Change

`skills/refactor/scripts/refactor_flow.py`:

- `sweep_matches` takes each added line and its new-file line number from `source_text.parse_unified_diff`. The
  sweep patterns and the (path, line, kind, text) output stay the same.
- `diff_output` passes `--no-prefix`, which the shared parser reads, in place of `--src-prefix=a/ --dst-prefix=b/`.
  Its other callers ask only for `--name-status`, `--numstat` and `--shortstat`, which carry no prefix.
- `parse_new_path`, `HUNK_HEADER` and their unit test are gone. The end-to-end tests of quoted paths, user diff
  config and header-like lines still pass.

## Evidence

Both readers were fed the same diffs with the flow's own flags and `-U0`: 800 commits from flask, requests, express
and commander.js (60,413 added lines), and 11 commits of a built repo with renames, deletes, binary files, quoted
paths (space, umlaut, tab, quote, backslash, a `b/` folder), no-newline markers, body lines that read `+++ `, `--- `,
`diff --git` and `@@`, a mode change, a symlink, an empty file and CRLF. Path, line number and text matched on every
added line, with `core.quotePath` on and off.

They disagreed on one kind of line: a line holding a form feed, a lone carriage return, U+2028 or U+0085. The old
walker split the diff with `str.splitlines`, so it kept only the text before that character and could miss a marker
after it. The shared parser splits on newlines only and is right.

The new test fails on the old walker: the marker after a form feed is not found.

## Result

The refactor_flow tests pass, 84 of 84. Ruff is clean.

## Watch

None. No intake number counts sweep matches by line content.

## Back-out

Revert the commit.
