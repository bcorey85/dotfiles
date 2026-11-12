---
type: "Change"
change_type: "fixed"
title: "the formatter leaves the gate replay corpus layout alone"
description: "The repo-root .prettierignore lists tests/scripts/gate_replay_corpus.json, so the format-on-Edit hook no longer reflows its one-line entries."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-12T01:31:10-06:00"}
seq: 3
kind: "fix"
components: ["script/format-changed", "script/gate-replay"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_gate_replay.py::CorpusLayoutTest::test_the_formatter_ignore_file_lists_the_corpus"
asked: ""
proof: []
unmeasured: ""
---

## Change

`.prettierignore` at the repo root gains `tests/scripts/gate_replay_corpus.json`. The format-on-Edit hook runs
prettier from the repo root (`lib/format_files.py`), so prettier reads that file and skips the corpus even when the
hook names it.

## Evidence

judgment: a one-line edit to the corpus had the format hook reflow every one-line entry, churning the whole file.

## Result

`CorpusLayoutTest` fails on the old tree and passes; `test_gate_replay.py` passes (13 tests).

## Watch

None: a fixed ignore entry.

## Back-out

Revert the commit.
