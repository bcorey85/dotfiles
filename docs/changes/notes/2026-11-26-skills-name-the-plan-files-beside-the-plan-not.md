---
type: "Change"
change_type: "changed"
title: "skills name the plan files beside the plan, not under docs/plans"
description: "eng-spec phases 6 and 7 write and check the spec in the task directory phase 1 opened, eng-spec phase 1 also finds an existing git-dir task directory by ticket key, and /code, coder-core and the plan format name the criteria file as the one beside the plan."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T04:50:27-06:00"}
seq: 10
kind: "fix"
components: ["skill/eng-spec", "skill/code", "skill/coder-core", "skill/plan-format"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_resolve_task_dir.py::ResolveTaskDirTest::test_home_prints_the_git_dir_path_without_docs_plans"
asked: ""
proof: []
unmeasured: "No rule-meter fixture shows where a session writes a spec or reads the criteria file; the lines swap a fixed docs/plans path for the task directory the resolver names. Shipped unmeasured on agent-evals-74's ruling (2026-11-26); the user rules before the weekend merge."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`skills/eng-spec/phases/6-finalize.md` and `7-handoff.md`: every `docs/plans/<slug>/` path is now `<task dir>/`, the folder phase 1 step 3 opened, and the handoff names the absolute spec path. `skills/eng-spec/phases/1-ticket.md` step 2: with a ticket key, also run `resolve-task-dir.sh <KEY>`; a folder it prints is the existing task directory. `skills/code/SKILL.md`, `skills/coder-core/SKILL.md` and `skills/_shared/plan-format.md` name `acceptance-criteria.md` beside the plan.

## Evidence

The branch review of the git-dir plan root found that eng-spec phase 1 opened a git-dir folder but phases 6 and 7 still wrote `docs/plans/<slug>/spec.md`, and /code checked a criteria file under `docs/plans` that a git-dir plan does not have.

## Result

Rule anchors updated for coder-core and code. No measured effect.

## Watch

None.

## Back-out

Revert the commit; a repo with no docs/plans then gets its spec written to a docs/plans folder again.
