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
commit HEAD names; `ScopeGuard.undo` copies those files back and restores every tracked file outside the scope that was
clean before the pass and whose work tree now differs from that commit, in the work tree and the index. It also records
the index entry of each dirty file outside the scope and puts back every entry the pass changed, so a `git add` of such
a file does not survive. `review_loop_coder.coder_call` runs it after the ruled-out guard, on a finished and on a failed
call. `review_loop_script.repair` builds the scope: the review scope, the paths of the pass's findings, the files
earlier passes touched, and the held, ruled-out and later-phase files. A path a finding's text holds as a whole token
stays, and so does a file the pass created. A file the sign-off snapshot holds (a root plan-folder markdown file with a
sign-off line, or a scope path that is a decision log with one) is guarded only on its sign-off lines, which the loop
puts back; its other lines stay as the pass left them. `repair` takes that snapshot before `guard_pass` and exempts
exactly those files, so a nested `docs/plans/` decision log, a non-markdown file under `docs/plans/` and a plan file
with no sign-off line are put back like any other file outside the scope. An approval-only file is reverted and
reported by its own guard. The guard does not undo a commit the coder makes during the pass: the work tree and index go
back, HEAD keeps the commit. The loop's formatter step already reads only the review scope and the touched files.
`paths_differing_from_head` is the module's one `git diff` listing: the paths dirty before the pass and the paths
changed after it both come from it.
`script_utils.texts_relative_to` is the one function that cuts a root prefix from finding texts, for this guard and the
ruled-out guard; `script_utils.texts_name_path` builds on it to say whether a finding text names a path. Before the
guard overwrites a file in the work tree, it copies that file's current bytes to
`<out>/pass-backup/<role>/put-back/<n>/<path>`, never discards that folder, and names it in the `tool_fault` note,
because the guard cannot tell who wrote the file. Each guard takes the next free `<n>`, so the second `coder-lint` pass
of a loop keeps its bytes beside the first one's, and a guard that kept nothing claims no folder. Only a folder named
in ASCII decimal digits counts as taken.
An index entry the guard replaces is not copied: the note names its blob id, which `git cat-file -p` reads until
`git gc` prunes it (two weeks by default). A file the loop could not copy (over the size cap or unreadable) is named in
a note of its own. When a put-back step fails, the pre-pass backup stays and the note names its folder for dirty files,
the commit for clean files, or the index entries as they were. A check that runs in a subfolder (`cd frontend && npm
test`) prints paths relative to that folder, which a finding text then holds without the folder; the guard matches them
as printed, so such a fix can be put back. The loop does not know which step of a check failed, so it cannot resolve the
printed paths.
`script_utils.index_entries` reads the index entries of many paths with one `git ls-files` call, and `index_entry` is a
call to it, so a pass costs two git calls for its dirty files, not two per file. The files put back before a restore
step fails are noted anyway. A guard failure after any coder call is raised as a `CoderCallError`: after a failed call
it keeps the coder's own message, after a finished call it names the undo failure, and the blocker says the pass
finished but the loop could not undo all of it. So `repair` stops the
loop with a packet blocker. `guard_pass` also fails closed before the pass: `git status` is strict, `index_entries`
raises, and `head_commit_or_unborn` tells an unreadable HEAD from an unborn one. Then `repair` keeps the findings open
and stops with a `CoderFailedError` blocker, and no coder call runs. The blocker text for all three cases comes from
`review_loop_partial_fix.coder_failure_blocker`.

`review_loop_signoffs.snapshot_signoffs` keys every scope path relative to the repo (`held_path_in_repo`), so an
absolute decision-log path in the scope gives one snapshot key and one diff for the file, not two
(`tests/scripts/test_protected_lines.py`, `test_an_absolute_scope_path_is_keyed_repo_relative_once`).

## Evidence

judgment: one lane's fix passes rewrote `docs/rule-anchors.md` twice, and a lint repair reformatted 44 files that no
phase touched. Only files the user ruled out were put back.

## Result

The loop test fails with the guard off and passes with it on. `test_review_loop_script.py`: 449 tests pass, six of them
new (the scope-guard GitCallError blocker, the absolute finding path, a plain RuntimeError passing through, an undo
failure after a finished call, a plan-folder file outside the snapshot put back, a snapshot-held decision log left to
the sign-off guard); `test_review_loop_scope_guard.py` has two more (two guards of one role keep both sets of bytes, a
guard that kept nothing claims no folder); one test changed its setup so that the generated file its coder rewrites is
part of the change under review. `test_review_loop_named_tests.py`: the three tests that delete or rename a
plan-named test now change the named test file in the work tree first, so it is under review, and the scenario gives a
third clean review; a new test shows that a pass deleting a plan-named test file outside the review scope has the file
put back and named in the packet's `tool_fault`. `tests/changed_scope.py` lists the new test file as one that names a
signal module and reads no prompt.

## Watch

None: a script guard with a fixed outcome.

## Back-out

Revert the commit.
