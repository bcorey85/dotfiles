---
type: "Change"
change_type: "fixed"
title: "pull_keep_index puts staged files back and rebuilds clashing built pages through the merge driver"
description: "When staged built pages clash with origin's changes, pull_keep_index puts every local change back (staged stay staged, unstaged stay unstaged, the pages rebuilt through the merge driver), in the run and through --put-back; a part that cannot apply resets the tree to the pulled HEAD and exits 1 naming the conflicted files, the ref and the command that puts the changes back."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-11-22T18:01:52-06:00"}
seq: 26
kind: "fix"
components: ["script/pull-keep-index"]
evidence: ["tests", "scratch reproduction of a pull whose staged built pages and an ordinary staged file both clash with origin's changes"]
watches: []
test: "tests/scripts/test_pull_keep_index.py::PullKeepIndexTest::test_the_incident_state_ends_with_every_local_change_back_staged_files_staged_and_the_page_rebuilt"
asked: ""
proof: []
unmeasured: "No count shows how often a pull's staged built pages and other local changes clashed together."
---

## Change

When the re-apply with the index fails with no conflicted path and the clash is on built pages, and the repo configures the built-page merge driver, the saved changes go back in six steps. The staged part, with the pages left out, goes on the index. The index is written as a tree. The unstaged part, with the pages left out, goes on the tree. The tree is read back into the index, so only the staged part is staged. Each page is rebuilt through the driver command, and the rebuilt pages are staged. This replaces the old hand repair, which handled a clash on built pages alone and stopped when an ordinary file clashed too. It runs in the pull and through `--put-back`, and every step runs from the top folder of the repo, so a run started in a subfolder puts back every path.

A part that cannot apply resets the tree to the pulled HEAD and exits 1. The message names the conflicted files, the ref of the saved changes, and the command that puts the changes back with conflict markers.

## Evidence

The incident state (staged built pages and a staged ordinary file that both clash with origin, plus an unstaged edit) ends with every change back, the staged files staged and the pages rebuilt; that test fails without the change. Other new tests cover a subfolder run, a `--put-back` run, a page missing from the base, a page named with glob characters, and the rolled-back stop.

## Result

The pull_keep_index tests pass.

## Watch

A rolled-back stop after a part conflicts, or a rebuilt page that differs from the one a git merge would have built.

## Back-out

Revert `pull_keep_index.py` to the apply with no index, which handles a clash on built pages alone.
