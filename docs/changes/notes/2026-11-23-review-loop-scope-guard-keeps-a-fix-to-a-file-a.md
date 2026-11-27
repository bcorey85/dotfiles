---
type: "Change"
change_type: "fixed"
title: "Review loop scope guard keeps a fix to a file a finding names by suffix or dot-slash"
description: "The review loop's scope guard now keeps a fix to a file that a finding names with a leading dot-slash or by the unique end of its path, so that fix is no longer put back and lost."
generated: {"by": "claude-code/claude-fable-5-2", "at": "2026-11-23T01:01:11-06:00"}
seq: 2
kind: "fix"
components: ["script/review-loop"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_review_loop_scope_guard.py::ScopeGuardTest::test_a_finding_that_names_a_tracked_file_with_a_dot_slash_or_by_a_path_suffix_keeps_its_edit"
asked: ""
proof: []
unmeasured: ""
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`lib/script_utils.py`: `texts_relative_to` cuts a leading `./` from a path in a finding's text, and the new
`texts_name_path_by_suffix` matches a trailing part of a path (`x.py` for `lib/x.py`) when it holds a dot or a slash
and no other repo file ends with it. `review/review_loop_scope_guard.py`: `PassScope.holds` uses both. The guard
lists the repo's files with one `git ls-files` call at the start of the guard, before the pass runs, so the undo reads
the pre-pass file set. A failed listing at the start of the guard raises.
`script_utils.path_has_tail` now holds the test for a path ending with a path tail, for the guard, the held-file
filter and the absent-file filter.

The `./` cut also reaches `review_loop_ruled_out.names_deletion`: a finding that asks to delete `./lib/x.py` now
counts as asking to delete `lib/x.py`.

A trailing part that two repo files end with names neither: the guard does not guess, and the fix is put back as
before. The loop stops with a blocker when the listing fails.

## Evidence

- judgment: a branch review found that a finding naming `./lib/x.py` or `x.py` did not keep `lib/x.py` in the fix
  pass's scope, so the guard undid the fix.

## Result

The named test fails without the change and passes with it. The full suite passes.

## Watch

None. No intake number counts fixes the guard put back by how the finding named the file.

## Back-out

Revert `texts_relative_to`, `texts_name_path_by_suffix` and `PassScope.holds`. A finding must name the full repo
path again, for the guard and for a deletion.
