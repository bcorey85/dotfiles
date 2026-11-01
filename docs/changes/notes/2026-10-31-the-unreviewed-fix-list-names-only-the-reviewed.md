---
type: "Change"
change_type: "fixed"
title: "The unreviewed-fix list names only the reviewed repo's files, once each"
description: "A review packet's 'Last fix not reviewed' list resolves each fixed[] name against files_touched, so a bare file name and its full path count once and a file from another repo named in a finding's text drops out."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-31T21:35:59-05:00"}
seq: 416
kind: "fix"
components: ["script/handback"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_handback.py::FixedPathsTest::test_a_file_from_another_repo_named_in_a_finding_drops_out"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `handback.fixed_paths` resolves each path a fixed[] entry names against the packet's `files_touched`: the same
  path, else every touched path that ends with the bare or partial name, or that an absolute name ends with. A name
  no touched path matches drops out. With no `files_touched`, every named path is kept as before.
- The "Last fix not reviewed" section falls back to `files_touched` when no fixed[] name matches.
- The escape check in `review_fix.log_escapes` matches a bare or partial name against `fixed_paths`, through
  `touched_paths_named`, and stores the escape under the one full path it matches, so a bare name and its full path
  log once.

## Evidence

judgment: a dotfiles worktree review listed `backend/src/modules/timekeepers/schema.ts`, a work-repo path quoted in a
finding's text, and listed `review_fix.py` both as a full path and as a bare name. An agent-evals review listed
`gates/git_discipline_gate.py`, a file of another repo. The reader is told to check a diff that does not exist.

## Result

The named test and the bare-name dedupe test fail before (the list keeps every name) and pass after, with tests for an
absolute name, an empty `files_touched` and the fallback. `test_handback` and `test_review_fix_script`: 328 tests, 0
failed; ruff clean.

## Watch

None. The list prints in the session.

## Back-out

Revert `touched_paths_named`, the resolution in `fixed_paths`, the fallback in `unreviewed_fix_section`, the
escape check in `review_fix.log_escapes`, and `FixedPathsTest`.
