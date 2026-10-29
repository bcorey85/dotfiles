---
type: "Change"
title: "Callers read the review store from handback_store, not through handback"
description: "handback.py drops its re-export block; every caller imports the hand-back store names from handback_store and the finding-id constants from loop_transcript."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T14:49:53-05:00"}
seq: 273
kind: "fix"
components: ["script/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::NoStoreReExportTest::test_every_script_reads_only_names_handback_defines"
asked: ""
proof: []
unmeasured: ""
---

## Change

`was_recorded` moves from `handback.py` into `handback_store.py`, and `open_child_gate.py` calls it there.
`handback.py` imports from `handback_store` and `loop_transcript` only the names it uses itself, with no
`noqa: F401` re-exports. `review_loop_packet.py`, `saved_handback.py`, `open_child_gate.py`,
`review_commit_gate.py`, `review_loop_gate.py` and `code_step_review.py` call `handback_store.record`, `latest`, `hand_back_gap`,
`unreviewed_streak`, `ended_on_unreviewed_fix` and the gap constants directly. `review_loop_script.py` reads
`FINDING_ID_HEX_LEN` and `PRINTED_FINDING_ID` from `loop_transcript`. The tests that read store names through
`handback` now read them from `handback_store`.

## Evidence

A mechanical sweep: the re-export block hid which module owns the store. A new test scans every script for
attributes read on `handback`, on the `load_handback()` module or on a code-step `module` parameter, and fails
when one is not a name `handback.py` defines itself.

## Result

The new test fails before the sweep, when the callers read the re-exported names, and passes after it. The review and code-step suites pass with no change in
what any script prints.

## Watch

None; no behavior change.

## Back-out

Revert the import edits in `handback.py` and the seven callers, the `was_recorded` move into `handback_store.py`, the
docstring edits in `handback_store.py` and `saved_handback.py`, the `handback_store.` references in
`test_handback.py`, `test_review_loop_script.py` and `test_code_step_review_script.py`, and the new test.
