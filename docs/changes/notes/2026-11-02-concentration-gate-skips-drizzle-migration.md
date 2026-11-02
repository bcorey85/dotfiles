---
type: "Change"
change_type: "fixed"
title: "concentration gate skips drizzle migration metadata"
description: "The shared generated-file rule leaves out drizzle-kit's `meta/_journal.json` and `meta/NNNN_snapshot.json`, so the concentration gate names the real largest source module; its docstring says it counts commits only."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-02T08:02:00-06:00"}
seq: 3
kind: "fix"
components: ["script/concentration", "script/source-paths", "skill/code"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_concentration.py::ConcentrationGateTest::test_drizzle_migration_metadata_does_not_count_and_the_real_largest_module_is_named"
asked: ""
proof: []
unmeasured: ""
---

## Change

- `lib/source_paths.is_uncounted_path` also leaves out `_journal.json` and `*_snapshot.json` in a `meta` folder
  (drizzle-kit's migration metadata). The concentration gate, the review-size rule and every other
  `is_counted_source` caller stop counting them.
- `concentration.py` keeps diffing `<base>...HEAD`. Its docstring and `closing-phases.md` now say that uncommitted
  and untracked work is not counted, so the finished phase is committed before the gate runs.

## Evidence

- Two /code sessions saw the gate name `drizzle/meta` (thousands of generated lines) as the largest module and
  dispatch a pointless `/refactor simplify` on it.
- Over ~/dev, 1673 of 1673 json files under a `meta/` folder are drizzle journals or snapshots, and the rule now
  excludes all of them.
- The new test fails on the old rule.

## Result

- On a branch with drizzle migrations, the gate names the real largest source module.

## Watch

—

## Back-out

Revert the commit.
