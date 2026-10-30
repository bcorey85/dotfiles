---
type: "Change"
change_type: "fixed"
title: "test-file rules have one owner in source_paths"
description: "Every gate that asks whether a file is a test, runs alone, or is a spec file now reads the one rule in source_paths.py, so a coder's test file counts the same in the coder packet, the derived test gate and the full check's repair step."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-29T23:19:44-05:00"}
seq: 387
kind: "fix"
components: ["script/code-step", "script/review-loop-script", "script/source-paths"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_source_paths.py::TestFileRuleTableTest::test_each_test_file_rule_answers_each_path_once"
asked: ""
proof: []
unmeasured: "No intake row records which helper files a coder packet held or why a full check skipped its repair."
---

## Change

`source_paths.py` owns the test-file rules and says how they differ: `is_test_path` (the file belongs to the tests,
support files included) and `is_runnable_test_file` (a runner can take it alone). The second takes
`discovers_django_tests` for `manage.py test`, which finds only test*.py. A new `names_spec_file` tells whether a
failing check's log names a spec file. The coder packet's own regex, the derived gate's Django pattern and the full
check's `.spec.` search are deleted; each site calls source_paths. The coder packet now leaves out a helper-folder file
only when it runs alone, so `tests.py` is left out and a `test_helpers.ts` support file is kept. A non-Python
`test_*` file, such as the fixture data file `test_data.json`, is a helper and is kept; the old `^test_` regex left it
out. The `test_`, `.test.` and `.spec.` names match in any case, so `Orders.Test.ts` is left out too.

## Evidence

judgment: an architect read found five test-file rules in four files that gave different answers for the same path.
The new table test pins one row per path: each test-file rule function in source_paths answers each path once. It fails
on the base commit. A packet test checks the coder packet's helper-folder gate against the same rule.

## Result

Each test-file rule in source_paths gives one answer per path, and the coder packet reads it.

## Watch

None.

## Back-out

Revert the commit; each site keeps its own pattern again.
