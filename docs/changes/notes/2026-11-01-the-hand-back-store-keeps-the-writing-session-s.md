---
type: "Change"
change_type: "fixed"
title: "The hand-back store keeps the writing session's own file"
description: "Recording a hand-back row no longer deletes the writing session's own store file when it is more than 7 days old, so a long session keeps its dispatch and hand-back rows."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T02:01:21-06:00"}
seq: 431
kind: "fix"
components: ["script/handback-store"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::StoreTest::test_a_record_keeps_the_writing_session_s_own_stale_file"
asked: ""
proof: []
unmeasured: "A fix with a failing-before test; no intake number counts sessions whose store file was pruned mid-run."
---

## Change

`handback_store.prune_stale` takes `keep`, the file `record` is about to append to, and skips it. Other sessions' files older than `STALE_STORE_SECONDS` are still deleted.

## Evidence

judgment: a bug hunt showed `record` prune every `*.jsonl` older than 7 days before appending, its own file included. A session resumed after a week lost its dispatch and hand-back rows on its next write, such as `record_asks_logged`.

## Result

The resumed session's file keeps its dispatch and hand-back rows and gains the new row.

## Watch

—

## Back-out

Revert the commit.
