---
type: "Change"
title: "The test writer's prompt is now its contract only: the role line"
description: "The test writer's prompt is now its contract only: the role line, the implementation-blindness lists with a one-sentence vocabulary rule, acceptance criteria first, red tests reported red, the three fences, and the report block."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-14T00:00:00-05:00"}
seq: 5
components: ["agent/test-writer"]
evidence: ["removal round"]
watches: []
---

## Change

The test writer's prompt is now its contract only: the role line, the implementation-blindness lists with a one-sentence vocabulary rule, acceptance criteria first, red tests reported red, the three fences, and the report block. Gone: the pointers to the shared authoring and vocabulary files, the plan-heading command, the one-test-per-behavior step, and the fixture-provenance rule. The shared authoring file is deleted, since no other agent loaded it; the coder skill's aside about it and the audit skill's diagnosis line now say what remains. The vocabulary file stays for the coders and the criteria author.

## Evidence

removal round

### Anchor reasons

Anchor `skills/_shared/code-vocabulary.md`, section `# Code Vocabulary (what may never appear in committed code)` (evidence: judgment):

The boundary between the private operator workflow and the shipped tree. Referenced by the criteria author and the code skill, and named in the messages of the two hooks that enforce it. No coder, the diff reviewer, and the test writer load it: two replicates at opus found the reviewer without it equal on recall and on false findings. Eight Sonnet runs per arm found the writer equal on kills and leak-free with a one-sentence rule in its own prompt. Eight Sonnet runs per arm found the coder equal on every test with the same one-sentence rule, where no run under the full core followed its pointer to this file and that arm leaked the one marker.

## Result

Eight Sonnet runs per arm on one frozen Go plan phase, scored against sixteen planted bugs: the contract-only writer killed the same number as the full prompt, within a fifth of a bug on average and one bug better on its worst run, at about three percent fewer tokens, with a tenth more test lines written as flat functions where the full prompt used subtests. It leaked no workflow vocabulary into test comments where the full prompt leaked three lines in one run. The loaded prompt drops from about 1,300 words across three files to about 460 in one. The blindness hook denied every Read of the package under test under either wording. The writer then printed a package file through the shell in three quarters of its runs, the vector the hook leaves open on purpose.

## Watch

—

## Back-out

—
