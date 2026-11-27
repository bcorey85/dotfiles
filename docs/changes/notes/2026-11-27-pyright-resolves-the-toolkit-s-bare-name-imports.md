---
type: "Change"
change_type: "fixed"
title: "pyright resolves the toolkit's bare-name imports"
description: "A root pyrightconfig.json lists the toolkit script folders as extraPaths, so an editor's pyright resolves a script's bare-name sibling imports instead of flagging them."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-27T17:23:51-06:00"}
seq: 5
kind: "fix"
components: ["script/pyrightconfig"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_pyright_config.py::PyrightConfigTest::test_every_script_folder_is_an_extra_path"
asked: ""
proof: []
unmeasured: "Editor diagnostics only; no intake number counts unresolved-import reports."
impact: {"metric": "", "before": "", "after": "", "unit": "", "finding": ""}
---

## Change

New `pyrightconfig.json` at the dotfiles root. Its `extraPaths` name `claude/.claude/scripts/{code,gates,lib,review,telemetry,tools}`, the `adr`, `close-branch` and `refactor` skill script folders, and `tests/scripts`, which are the folders the scripts add to `sys.path` at run time.

## Evidence

judgment: the scripts import siblings by bare module name through `sys.path` lines, which pyright cannot follow, so every such import showed as unresolved in the editor after the scripts moved into per-concern folders.

## Result

`tests/scripts/test_pyright_config.py` fails with no config and passes with it: every script folder is listed and every entry exists. pyright 1.1.414, given the same extraPaths as absolute paths: `gates/inline_interpreter_hint.py` and `tests/scripts/test_memory_cap_scope.py` report no unresolved import, and a file that imports a module that does not exist still reports `reportMissingImports`. The pyright CLI auto-excludes `**/.*` whatever the config says, so a CLI run on a file under `claude/.claude` from the repo root checks nothing. The editor's language server checks the open file, so the config takes effect there.

## Watch

None: see unmeasured.

## Back-out

Delete `pyrightconfig.json`.
