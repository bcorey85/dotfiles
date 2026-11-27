---
type: "Change"
change_type: "changed"
title: "eng-spec opens the task directory the resolver names"
description: "eng-spec phase 1 opens the task directory that resolve-task-dir.sh --home prints, so a repo with no docs/plans gets a plan folder in its git dir."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-26T04:41:29-06:00"}
seq: 8
kind: "fix"
components: ["skill/eng-spec"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_resolve_task_dir.py::ResolveTaskDirTest::test_home_prints_the_git_dir_path_without_docs_plans"
asked: ""
proof: []
unmeasured: "No rule-meter fixture shows where a session writes a plan folder or a fetched ticket; the line swaps a fixed path for a script-printed one. Shipped unmeasured on agent-evals-74's ruling (2026-11-26); the user rules before the weekend merge."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

`claude/.claude/skills/eng-spec/phases/1-ticket.md` step 3: "Open the task directory `docs/plans/<slug>/`" became "Open the task directory that `bash ~/.claude/scripts/tools/resolve-task-dir.sh --home <slug>` prints". The slug rules are unchanged.

## Evidence

Queue item `a-lane-plan-and-its-criteria-in-the-tmpfs`: a lane in a repo with no docs/plans put its plan in the tmpfs scratchpad and a reboot lost it. The script names a git-dir folder for such a repo and docs/plans otherwise, so the path no longer depends on the session's choice.

## Result

Unmeasured. `bash claude/.claude/scripts/tools/rule-anchors.sh check` passes.

## Watch

None.

## Back-out

Revert this commit alone; the script change stays.
