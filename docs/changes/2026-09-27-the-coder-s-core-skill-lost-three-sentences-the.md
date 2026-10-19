---
type: "Change"
title: "The coder's core skill lost three sentences: the ban on dispatching or spawning a reviewer"
description: "The coder's core skill lost three sentences: the ban on dispatching or spawning a reviewer, the explicit ban on writing tests and fixtures, and the targeted-tests line in its verify step."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-27T00:00:00-05:00"}
seq: 15
components: ["skill/coder-core"]
evidence: ["removal round"]
watches: []
---

## Change

The coder's core skill lost three sentences: the ban on dispatching or spawning a reviewer, the explicit ban on writing tests and fixtures, and the targeted-tests line in its verify step. It keeps who writes tests, the compile-fix and red-test reporting, and the command-with-exit-code report.

## Evidence

removal round

## Result

Run as the coder on a plan phase whose plan names a new test file and whose verification lists a long gate, on a clean plan and on one that contradicts the code. Without the three sentences, the coder wrote no test and hit no test-ownership block, the same as with them, and it made no dispatch or review call. Both versions flagged the false plan. The cut version reported the command-with-exit-code line in both runs, the full one in one. Held-out tests passed in both cut runs and in one full run. The other full run's held-out tests failed to build. The cut version ran the full suite once more on the false plan. The dispatch ban was already pinned by the agent's tool list, the test ban by the ownership hook, and the targeted-tests rule by the global CLAUDE.md. About 150 fewer tokens a coder request, about 2.1M a week. One run per task.

## Watch

—

## Back-out

restore the sentences from git.
