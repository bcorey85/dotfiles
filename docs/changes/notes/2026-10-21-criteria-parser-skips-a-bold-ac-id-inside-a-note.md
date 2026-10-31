---
type: "Change"
change_type: "fixed"
title: "Criteria parser skips a bold AC id inside a note but still refuses a miswritten criterion line"
description: "verify_common.criteria_file no longer refuses an acceptance-criteria file because a note line has an unclosed bold **ACn's ... mid-line. A line that starts with a bold id, or holds a closed bold id span anywhere, and does not match `- **ACn** — text` still fails."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-21T16:38:14-05:00"}
seq: 20
kind: "fix"
components: ["script/verify-common", "skill/verify-branch"]
evidence: ["work incident", "tests"]
watches: []
---

## Change

- `scripts/verify_common.py`:
  - `ID_START` matches a bold `**ACn` only at the start of a line, after an optional indent, list marker and checkbox.
  - New `ID_SPAN` matches a closed bold id span, such as `**AC5**` or `**AC5, AC6**`, anywhere in a line.
  - `criteria_file` raises Fail when a line does not match `- **ACn** — text` and either guard matches. Any other line is skipped.
- `tests/scripts/test_verify_branch_script.py`: three new tests. One checks that a note with `**AC4's ...**` is skipped. One checks that each miswritten criterion line still fails: a table row, a leading word, a quote, a prefix, a strikethrough, no space after the dash, and the old forms. One checks that indented and starred criterion lines still parse.

## Evidence

Work incident: a plan's acceptance-criteria file had an indented status note under a criterion with `**AC4's main-skill part is OPEN ...**`. The parser refused the whole file, so verify-prep and `/verify-branch` failed on that branch. The real-plans test in the full suite failed on the same file.

A code review of the first staged fix found that anchoring the guard at line start let six miswritten criterion forms drop out of the parsed list without an error. The gate then checks fewer criteria. The closed-span guard was added before install. Across 76 real plan folders, the parsed criterion count is the same on the installed and staged parsers. The one exception is the plan that failed, which now parses all 23 criteria.

## Result

Staged 2026-10-21 in the fifth script fix batch. 92 tests pass on the staged copies, including the real-plans tests. On the installed script, the new note test and the two real-plans tests fail. Installed 2026-10-21.

## Watch

None. No intake metric counts verify-prep parse failures.

## Back-out

Restore the previous `verify_common.py` and `test_verify_branch_script.py` from the dotfiles history.
