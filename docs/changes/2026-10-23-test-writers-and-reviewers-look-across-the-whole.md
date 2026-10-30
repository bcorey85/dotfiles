---
type: "Change"
change_type: "changed"
title: "Test writers and reviewers look across the whole suite for a test that already catches the bug"
description: "The coder, both test reviewers and the plan format treat any test in the suite, at any layer, as a sibling. A rule's case table is tested at one layer, with one wiring test per other entry point."
generated: {"by": "claude-code/claude-opus-5-5", "at": "2026-10-23T08:16:59-05:00"}
seq: 3
kind: "behavior"
components: ["skill/coder-core", "agent/test-reviewer", "agent/test-intent-reviewer", "skill/plan-format"]
evidence: ["census"]
watches: ["test-sibling-whole-suite"]
---

## Change

- `skills/coder-core/SKILL.md`, Tests are yours: before the coder writes a test, it searches the suite for tests of the same function at every layer. It deletes a test that another test in the suite already covers, or that asserts a value copied from a registry or a constant that no acceptance criterion names. A rule already tested at one layer gets one wiring test per other entry point. Inputs that take the same branch go in one table-driven test.
- `agents/test-reviewer.md` Step 5 and `agents/test-intent-reviewer.md` Step 4: a sibling is any test in the suite, at any layer, that calls the same unit. The reviewer greps the suite for them, not only the diff. An assert copied from a registry or a constant is a cull shape, unless an acceptance criterion names the value.
- `skills/_shared/plan-format.md`: a plan lists a rule's case table at one layer only. Each other entry point gets one wiring test.
- Unchanged: the cull applies only to tests that the branch added. No existing test is removed.

## Evidence

- Census: a read-only audit of one repo on this machine read about 950 of its 1958 Rust tests. It put 200 to 280 tests (10 to 14%) at low value. An estimated 120 to 160 of them test one rule again at each layer that calls it. The cull rule already asked for "no sibling", but the reviewers compared a new test only with the diff. The plans listed test names for every layer.
- This is one repo, so it guides the rule but does not size a gain.

## Result

Not measured yet. Expected: fewer tests added per phase, with no rise in test-gap findings.

## Watch

`test-sibling-whole-suite`: review findings of class test-gap and weak-assertion per review run stay flat. The intake does not count tests added per phase yet, so the gain itself has no watch.

Reading, 2026-10-27 intake: the coder output cost guard is closed as not tracked. Work subagent transcripts before Claude Code 2.1.308 carry output on about 5% of requests, so its before window cannot be compared. The findings watch is held: from 2026-10-27 the scripted review loop's finding rows are wrong until its logger is fixed.

Reading, 2026-10-28 intake: NO CHANGE (0.35 per run against a 0.38 median), still held. The after window includes rows from the scripted loop's broken logger. The logger fix is on master; read the watch on rows written after the work machine installs it.

Reading, 2026-10-29 intake: NO CHANGE (0.38 → 0.28 per run), still held. The after window still holds rows from the scripted loop's logger before its fix.

## Back-out

Restore the four files from git.
