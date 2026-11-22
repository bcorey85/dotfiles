---
type: "Change"
change_type: "fixed"
title: "Unpinned web-fetch calls run on haiku instead of being denied"
description: "The model guard rewrites an unpinned web-fetch call to model haiku and lets it run, so a page fetch no longer costs a denied call and a retry."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-11-22T14:45:38-06:00"}
seq: 22
kind: "fix"
components: ["script/agent-model-guard", "agent/web-fetch"]
evidence: ["judgment"]
watches: []
test: "tests/scripts/test_agent_model_guard.py::AgentModelGuardTest::test_unpinned_web_fetch_runs_pinned_to_haiku"
asked: ""
proof: []
unmeasured: ""
---

## Change

`agent-model-guard.sh` used to deny every Agent call to the harness's built-in `web-fetch` agent that set no model, because that agent has no file to carry a `model:` pin. The main session then retried with `model: "haiku"`, so each page fetch cost one wasted call. The guard now answers an unpinned `web-fetch` call with `allow` and an `updatedInput` that adds `model: "haiku"`. An explicit model on `web-fetch` passes unchanged; `opus` and `inherit` are still denied; every other unpinned agent with no file is still denied.

## Evidence

The queue item reported one denied call and one retry per first web fetch. The guard exists to stop unpinned calls running on the orchestrator's Opus model; the rewrite keeps that, since the call runs on haiku, never on the parent model.

## Result

The new test fails on the old guard and passes on the new one (20 of 20 in the file pass). Live check: an Agent call to `web-fetch` with no model ran on the first try and reported claude-haiku-5-5. Guard time on a web-fetch call: 8 ms median, next to 7 ms for a bare Python start.

## Watch

None: the intake has no count of denied Agent calls by subagent type.

## Back-out

Delete the `web-fetch` branch in `agent-model-guard.sh` and its five tests.
