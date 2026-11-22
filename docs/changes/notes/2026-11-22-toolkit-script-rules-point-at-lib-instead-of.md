---
type: "Change"
change_type: "fixed"
title: "Toolkit script rules point at lib/ instead of listing its modules"
description: "The script rules drop two hand-kept lists of lib/ modules that had fallen 14 modules behind, so a search-before-you-write check looks at the whole folder."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T10:50:52-06:00"}
seq: 8
kind: "user-rule"
components: ["rule/toolkit-script-rules"]
evidence: ["user request", "prompt audit"]
watches: []
test: ""
asked: "2026-11-22: asked by the user"
proof: []
unmeasured: "A fact correction: the rule (search lib/ before writing a helper) is unchanged; only the stale list goes. No intake number reads it."
---

## Change

`docs/toolkit-script-rules.md`: the folder line keeps "`lib/` (shared modules)" with no list. The helper rule reads
"search `lib/` (list it; every file there is a shared module) and the other scripts".

## Evidence

prompt audit: both lists named 54 modules; `lib/` holds 68. Missing: code_context, code_text, diff_ranges, expected_red,
file_backup, full_check_receipt, git_calls, handoff_files, local_check, notes_paths, numstat, pytest_config,
source_paths, user_prompts. The two lists also disagreed in order.

## Result

Applied. No run: fact correction.

## Watch

None: see `unmeasured`.

## Back-out

Restore the two lists from git.
