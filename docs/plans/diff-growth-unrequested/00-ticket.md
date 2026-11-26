---
type: "QueueItem"
title: "close pass and fix add docs and tests nobody asked for, and no step flags diff growth"
description: "A reviewer finding on unrequested docs and tests keeps a branch's diff to what the ticket asked for"
generated: {"by": "claude-opus-5-5/main", "at": "2026-11-25T00:34:49-06:00"}
kind: "method"
status: "running"
rank: 985
blocked_by: []
source: "claude/.claude/agents/code-reviewer.md"
components: ["agent/code-reviewer", "skill/code"]
---

## Context
A branch grew to 84 files and about 7,000 added lines. About 3,000 were docs: a long spec plus 11 flow docs the close pass wrote. About 2,400 were tests, and a fix pass added about 230 lines nobody asked for. No reviewer flagged any of it. The user found it and later deleted 7 of the 11 docs as low value.

## Done when
The reviewer has a rule, checked by an eval case, that a new doc file or test module that no plan step, criterion or finding asks for is a fix finding to cut it, and so is a doc that repeats a sibling doc or the code. The close pass reports the added-line count split by docs, tests and code, and flags any part over a set share of the diff.
