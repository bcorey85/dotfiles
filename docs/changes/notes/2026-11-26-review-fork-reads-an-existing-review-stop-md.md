---
type: "Change"
change_type: "fixed"
title: "Review fork reads an existing review-stop.md before it writes it"
description: "The review fork reads an existing review-stop.md before it writes it, so its Write is not refused as not read yet."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T03:28:12-06:00"}
seq: 6
kind: "fix"
components: ["skill/review"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_toolkit_prose_facts.py::ToolkitProseFactsTest::test_review_fork_run_reads_an_existing_review_stop_before_it_writes_it"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

review-fork-run.md's ending step adds: when the file already exists, Read it first. A review-stop.md from an earlier run stays in the run folder, and the Write tool refuses an existing file it has not read.

## Evidence

Judgment: two transcripts show the refused Write; in one, `head` on the file printed an earlier stop, so the file did exist.

## Result

The new prose test pins the line in the ending section.

## Watch

None: a test pins it.

## Back-out

`git revert` the commit.
