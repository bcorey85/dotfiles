---
type: "Change"
change_type: "changed"
title: "The review metrics logger, the per-finding logger and the escape logger now stamp every row with the session"
description: "The review metrics logger, the per-finding logger and the escape logger now stamp every row with the session id and the current git branch."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-20T00:00:00-05:00"}
seq: 19
kind: "behavior"
components: ["script/log-review-metrics", "script/log-review-finding", "script/log-escape"]
evidence: ["judgment"]
watches: []
---

## Change

The review metrics logger, the per-finding logger and the escape logger now stamp every row with the session id and the current git branch. Both are read inside the script, so no agent or skill text changed. A branch the caller passes still wins.

## Evidence

judgment

## Result

Instrumentation, no speed or quality gain claimed. Before this, an aggregate review row carried no branch and no row carried a session, so a loop run could not be joined to its own findings, or an escaped defect to the run that passed it. Each of the three scripts was tested on scratch files in three cases: a normal call, a caller-supplied branch, and a call with no session outside a git tree. Effect unmeasured. The earliest data that can show the join working is review rows written on the work machine after this change is pulled there, read at the first intake after that date.

## Watch

—

## Back-out

—
