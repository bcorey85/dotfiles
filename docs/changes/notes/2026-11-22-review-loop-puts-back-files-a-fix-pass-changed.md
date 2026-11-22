---
type: "Change"
change_type: "fixed"
title: "Review loop puts back files a fix pass changed outside the review scope"
description: "After each fix pass, lint and full-check repairs included, the review loop puts back every file the pass changed that existed before it, sits outside the review scope and is named by no finding of that pass, and the packet's tool_fault lists the files it put back."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-22T13:24:50-06:00"}
seq: 21
kind: "fix"
components: ["script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_scope_guard.py::ScopeGuardLoopTest::test_a_fix_pass_edit_outside_the_review_diff_is_put_back_and_the_packet_names_it"
asked: ""
proof: []
unmeasured: ""
---

## Change

`review/review_loop_scope_guard.py` (new): `guard_pass` copies the dirty files outside a pass's scope and keeps the
commit HEAD names; `ScopeGuard.undo` copies those files back and restores every other tracked file that differs from
that commit, in the work tree and the index. `review_loop_coder.coder_call` runs it after the ruled-out guard, on a
finished and on a failed call. `review_loop_script.repair` builds the scope: the review scope, the paths of the pass's
findings, the files earlier passes touched, and the held, ruled-out and later-phase files. A path a finding's text
holds as a whole token stays, and so does a file the pass created. A decision log is guarded only on its sign-off
lines, which the loop puts back; its other lines stay as the pass left them. An approval-only file is reverted and
reported by its own guard. The loop's formatter step already reads only the review scope and the touched files.
`paths_differing_from_head` is the module's one `git diff` listing: the paths dirty before the pass and the paths
changed after it both come from it.

## Evidence

judgment: one lane's fix passes rewrote `docs/rule-anchors.md` twice, and a lint repair reformatted 44 files that no
phase touched. Only files the user ruled out were put back.

## Result

The loop test fails with the guard off and passes with it on. `test_review_loop_script.py`: 417 tests pass; one test
changed its setup so that the generated file its coder rewrites is part of the change under review.

## Watch

None: a script guard with a fixed outcome.

## Back-out

Revert the commit.
