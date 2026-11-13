---
type: "Change"
change_type: "fixed"
title: "simplify-prep counts source files only and slices along module folders"
description: "refactor_flow simplify-prep drops test, index, style and generated files and packs whole module folders into its 25-file slices instead of cutting the file list alphabetically."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-13T12:30:00-06:00"}
seq: 2
kind: "fix"
components: ["skill/refactor", "script/refactor-flow", "script/source-paths"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_refactor_flow.py::RefactorFlowTest::test_simplify_prep_slices_along_module_folders_and_drops_test_index_and_style_files"
asked: ""
proof: []
unmeasured: ""
---

## Change

New `skills/refactor/scripts/simplify_slices.py`, called by `simplify_prep`: it drops test
(`source_paths.is_test_path`), index and style files (`source_paths.is_index_file`, `is_style_file`, new) and
generated (lockfile, dist, snapshot, minified, migration metadata) files (`source_paths.is_uncounted_path`),
prints how many of each it dropped, and packs whole module folders (the first path part below the target) into
slices of at most 25 files. A folder over the limit splits by its subfolders, then into sorted chunks. A target
with no source file left STOPs. The refactor SKILL.md step 7a says what the prep now does.

## Evidence

judgment: a session's simplify run split one feature folder into 17 alphabetical slices with tests and index files
counted, cutting modules apart, and the session hand-wrote finder prompts instead.

## Result

The new tests fail on the old tree and pass; the full suite passed (3777 tests, 0 failed).

## Watch

None: a fixed slicing rule.

## Back-out

Revert the commit.
