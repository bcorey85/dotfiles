---
type: "Change"
change_type: "fixed"
title: "the discovered full check skips doc paths when it picks parts"
description: "A plan doc beside frontend files no longer starts every part of the discovered full check; a docs-only diff still runs every part."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-25T19:23:48-06:00"}
seq: 4
kind: "fix"
components: ["script/check-discovery"]
evidence: ["tests/scripts/test_check_discovery.py"]
watches: []
test: "tests/scripts/test_check_discovery.py::ChangedPathPartsTest::test_doc_paths_beside_frontend_files_do_not_widen_the_check_to_every_part"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`check_discovery.parts_to_run` skips each `source_paths.is_doc_path` path after the shared, package and Python kind checks, so a code file under a docs folder keeps its kind.

## Evidence

The new test fails on the old tree (every part selected) and passes on the new one. The full check passed on the final tree (6728 tests, 0 failed).

## Result

Before, a frontend diff with a plan doc ran the backend suite too; now it runs only the package part.

## Watch

—

## Back-out

Revert the commit.
