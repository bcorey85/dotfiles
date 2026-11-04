---
type: "Change"
change_type: "fixed"
title: "Turn-end formatter leaves prompt markdown alone"
description: "format_files.run_formatters skips .md files a model reads as prompt text (under .claude or .config/opencode/, and CLAUDE.md, CLAUDE.local.md and AGENTS.md at any depth), so the Stop hook no longer reflows agent and skill prompts."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-04T13:50:02-06:00"}
seq: 3
kind: "fix"
components: ["script/format-changed", "script/format-files"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_format_files.py::RunFormattersTest::test_prompt_markdown_is_never_formatted_but_other_files_beside_it_are"
asked: ""
proof: []
unmeasured: ""
---

## Change

`format_files.py` gains `is_prompt_markdown(path)`: true for a `.md` file with a `.claude` folder segment, under `.config/opencode/`, or named `CLAUDE.md`, `CLAUDE.local.md` or `AGENTS.md` at any depth. `run_formatters` checks it beside the `docs/plans/` guard and skips those files. Non-markdown files in the same folders (settings JSON) still format, and so does other markdown. Docstrings in `format_files.py` and `gates/format_changed.py` name the skip. Hook timing does not change: the fix adds one string check per changed path.

## Evidence

judgment: a session saw the Stop-hook prettier pass pull a plain line after a blockquote into the quote in an agent prompt, which moved the line inside the verbatim fence every coder receives; the reflow also changed rule-anchor hashes and failed `test_rule_anchors`. The new test fails on the base commit (prettier is called on the prompt files) and passes after.

## Result

`test_format_files.py` 8 of 8 pass; lint clean.

## Watch

—

## Back-out

Revert `is_prompt_markdown`, its constants and its guard term in `format_files.py`, the docstring lines, and the test.
