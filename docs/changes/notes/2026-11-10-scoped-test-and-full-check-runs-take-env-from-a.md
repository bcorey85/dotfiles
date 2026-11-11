---
type: "Change"
change_type: "fixed"
title: "Scoped test and full-check runs take env from a personal per-repo file"
description: "The review loop's gate env now merges the NAME=value assignments listed under the repo's origin name in ~/.claude/gate-env.json, so a repo whose CI sets a test env var that no plan names gets scoped and full-check runs with it; a plan's assignment wins and a malformed file fails naming the file."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-10T18:58:47-06:00"}
seq: 5
kind: "fix"
components: ["skill/review", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_plan_format.py::RepoGateEnvTest::test_the_personal_file_gives_the_assignments_listed_under_the_repo_name"
asked: ""
proof: []
unmeasured: ""
---

## Change

`lib/plan_format.py` `repo_gate_env` merges the assignments of the personal file `~/.claude/gate-env.json` (path overridable with `CLAUDE_GATE_ENV_FILE`), shape `{"<repo name>": ["NAME=value"]}`. The repo name is the origin URL's last part without `.git`, else the main worktree folder name. A plan's assignment wins for the same name; a missing file adds nothing; a file that is not that shape, or holds a word that is not a literal `NAME=value`, raises `ValueError` naming the file. The scoped-tests `critical-blocker` text in `review/review_loop_script.py` names the repo key and the file to edit. The file lives in the home folder, so the toolkit adds nothing to a company repo.

## Evidence

judgment: a /code run's scoped test gate ran without an env var the repo's CI sets, and the loop stopped on test errors that were not the change's. The key test fails on the old code (`['PLUGINS=1'] != []`) and passes after.

## Result

The loop's full check on the final tree passed: 3373 tests, 0 failed.

## Watch

—

## Back-out

Revert the personal-file merge in `lib/plan_format.py`, the hint line in `review/review_loop_script.py`, and their tests.
