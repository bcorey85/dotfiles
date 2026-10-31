---
type: "Change"
change_type: "changed"
title: "`coder` and `architect-core` place new logic by what it knows, not by its caller count"
description: "`coder` and `architect-core` place new logic by what it knows, not by its caller count."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-10-16T00:00:00-05:00"}
seq: 1
kind: "behavior"
components: ["agent/coder", "skill/architect-core"]
evidence: ["seeded round"]
watches: []
---

## Change

`coder` and `architect-core` place new logic by what it knows, not by its caller count. A function or inline block that takes plain values or any record and reads no module table or rule goes in the repo's shared utility directory at first use, with generic types, a name for what it does, an export and a test there. A step that mixes generic work with a module rule is split, and the rule stays in the module. +86 words in each file

## Evidence

seeded round

### Anchor reasons

Anchor `agents/coder.md`, section `(preamble)` (evidence: removal round, unproven; census, judgment; model round; seeded round):

Dispatch contract: name, description, the sonnet alias, the five-tool list (Bash, Read, Edit, Write, LSP), the core-skill preload, the both-ends-of-a-wire line, and the placement rule. The placement rule puts generic logic in the shared utility directory at first use, whatever its caller count. In a seeded round on a web backend, coders without it buried the generic step in a feature module in 12 of 12 trees, and with it in 0 of 12. No tree moved a module rule into shared, and tokens stayed flat. All but the tool list was byte-identical in both arms of the removal round, so not itself varied. An opus pin once replaced the sonnet pin after two bench rounds on an older Sonnet. The sonnet alias came back when it resolved to Sonnet 5.5: behind the Opus reviewer, 0.10 hidden-test defects per run reached the branch against 0.19 for Opus, with 0 of 48 runs writing no code on either model, and each run took a median 38.5 s against 98.5 s, with 46% of the cache reads and 58% of the output tokens. Before review, Sonnet 5.5 fails more hidden tests (0.27 against 0.23 per run), so the reviewer carries the difference. The wire line had no target on a single-package phase. The tool list replaced the every-tool-but-Agent grant after a census of tool calls: the coder calls only Bash, Read, Edit, and Write, and LSP is on the list because typed code prefers it. A live check on a later harness put the cut at about 4K tokens per turn, about a tenth of a dispatch, because that harness already defers most tool definitions. A later census confirmed that the list delivers LSP: on one day after the change, 72 of 82 implementer dispatches held its schema from the first turn. The tool answers only where a plugin registers the file type and the server binary is on the path. Outside the test writer, about one dispatch in a hundred that look up a symbol in typed code calls it. A census of every file-writing implementer dispatch found none that wrote both a server-side and a client-side file, so the wire line has never been exercised. The description is a routing line: what the agent is, who dispatches it, and any rule that the dispatcher needs. A census of this machine's top-level dispatches, a guide only, found none that menu text alone picked, and no dropped dispatcher rule had the description as its only home.

Anchor `skills/architect-core/SKILL.md`, section `## Research Context` (evidence: unproven):

Flag a design against an external protocol or SDK that comes with no research, and suggest a web search. Unproven: on a ticket with a Slack webhook post and no research document, no Opus plan raised the flag, with the block or without it. Every plan wrote the one-field payload from memory. The block needs a protocol that the model does not know before it can show an effect. The block stays because the frontend architect preloads it too, and it never ran. An earlier round kept it in both texts on a ticket with no external protocol.

Anchor `skills/architect-core/SKILL.md`, section `## Placement` (evidence: seeded round):

Put logic that takes plain values or any record and reads no module table or rule in the shared utility directory at first use, and split a step that mixes it with a module rule. In a seeded round on a web backend, plans without it buried the generic step in 5 of 8, and with it in 0 of 8. No plan moved a module rule into shared. The tested text sat at the end of the backend architect file. Here it sits in the preloaded core, so both architects get it. Only the backend architect ran, so the frontend architect gets the same text untested.

## Result

Work logs: 412 duplication review findings and 65 duplication escapes, with dotfiles and agent-evals sessions filtered out. Four planted two-module tickets in a web backend, three trees per arm per ticket, with the repo line that defers sharing removed in both arms. The coder buried the generic step in the first module in 12 of 12 trees without the rule and 0 of 12 with it. Plans buried it in 5 of 8 and 0 of 8. In the second module, 7 of 12 trees copied the step without the rule and 0 of 12 with it, and 1 of 12 against 10 of 12 reused the shared code. No tree or plan moved a module rule into shared. Sonnet coder tokens per ticket, both phases, median: cache read 1.11M against 1.10M, output 25.7K against 25.0K. Lint passed in all 24 trees. One touched test failed in 8 of 12 trees without the rule and 0 of 12 with it under a loaded scorer, and all 8 passed when rerun one tree at a time, so the test guard shows no difference. Limits: two of the four tickets were not held out from the wording draft, and only the backend architect ran.

## Watch

duplication escapes per review run, down.

## Back-out

delete the paragraph from `coder.md` and the `## Placement` block from `architect-core`.
