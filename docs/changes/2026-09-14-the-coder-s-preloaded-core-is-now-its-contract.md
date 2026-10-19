---
type: "Change"
title: "The coder's preloaded core is now its contract only: the role line, the terminal-implementer fence"
description: "The coder's preloaded core is now its contract only: the role line, the terminal-implementer fence, phase-scoped plan reading, the no-tests rule with a one-sentence vocabulary ban, one sentence to run the quality checks, the stop-and-ask list, the plan-impact block, and the handoff lines."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-14T00:00:00-05:00"}
seq: 6
components: ["shared/plan-reading", "skill/coder-core"]
evidence: ["removal round"]
watches: []
---

## Change

The coder's preloaded core is now its contract only: the role line, the terminal-implementer fence, phase-scoped plan reading, the no-tests rule with a one-sentence vocabulary ban, one sentence to run the quality checks, the stop-and-ask list, the plan-impact block, and the handoff lines. Gone: the code-style block, performance defaults, the plan-read mechanics, reuse-before-you-write, fixture provenance, the pre-submission checklist, the HTTP and UI conditionals, both sides of one wire, the handoff calibration prose, and the pointer to the vocabulary file. The hooks that hold the comment ceiling and the marker ban are unchanged. The vocabulary file's consumer line now says the coders do not load it. The comment hook's header still credits the cap to the coder core, because the hook scripts are write-protected. The code skill's quote of the no-tests heading follows the heading's new case.

## Evidence

removal round

### Anchor reasons

Anchor `skills/coder-core/SKILL.md`, section `(preamble)` (evidence: removal round):

Frontmatter: the name the coder preloads by, and the description. Byte-identical in both arms of the removal round, apart from the deep coder's name, which left the description when that agent was deleted.

Anchor `skills/coder-core/SKILL.md`, section `# Coder Core Directives` (evidence: removal round):

The role line: implement the plan, decide no architecture, report and stop on an open design question. Kept in the contract-only text that matched the full core on every held-out and downstream test in eight Sonnet runs per arm at 18% fewer tokens. The sentence about the agent file's scope fence is gone with the fences it described.

## Result

Eight Sonnet runs per arm on one frozen Go plan phase, scored by the substrate's own held-out tests and its downstream packages: the contract-only coder passed every test in every run, as did the full text, at eighteen percent fewer tokens, with comment density a third of a point lower and no fence broken. The saving came from reading, not prompt size: the dropped read mechanics had the coder opening the plan twice as often. No run under the full text ever opened the vocabulary file it was told to read, and the one marker leak came from that arm. The loaded prompt drops from about 2,400 words to about 630. Both arms sat at ceiling, so the result is no worse, not better.

## Watch

—

## Back-out

—
