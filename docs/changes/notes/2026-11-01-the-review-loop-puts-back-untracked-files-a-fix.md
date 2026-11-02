---
type: "Change"
change_type: "fixed"
title: "The review loop puts back untracked files a fix coder deleted"
description: "A fix coder can no longer lose an untracked file: the loop saves untracked files before each fix call, writes back any that vanish, and names them in the packet."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-01T19:36:55-06:00"}
seq: 458
kind: "fix"
components: ["agent/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_script.py::ReviewLoopScriptTest::test_a_fix_coder_that_deletes_an_untracked_file_it_did_not_make_finds_it_restored_and_noted"
asked: ""
proof: []
unmeasured: ""
---

## Change

`coder_call` in `review_loop_script.py` saves every untracked file in scope before a fix call, using the new `lib/file_backup.py`. After the call, on success or failure, it writes back any file that vanished, before the changed-file diffs, so a restored file never counts as removed code. A file the coder edited stays edited. Files over 256 KB, or past 4 MB in total, are not saved; if one goes, the packet reports it lost. Each case adds a note to `tool_fault`.

## Evidence

A /code run lost three untracked scratch SQL files to the loop, which counted them as removed code and stopped without converging. The review gate's clear instructions were checked and are correct: the wrong path in that run came from the runner, not from a file.

## Result

The new loop test errors on the old code and passes on the new. See the branch report for the suite count.

## Watch

None. A fix coder that means to delete a redundant new file now sees it restored and noted. That costs one note and loses nothing.

## Back-out

Revert the branch merge.
