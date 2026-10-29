---
type: "Change"
change_type: "changed"
title: "Every block of the diff reviewer's prompt now has a recorded content hash, evidence kind and reason"
description: "Every heading block of the diff reviewer's prompt, and of the two shared files it loads, now has a content hash in a sidecar table under `docs/`, each with the kind of evidence behind the block and a one-line reason."
generated: {"by": "claude-code/claude-sonnet-5-5", "at": "2026-09-14T00:00:00-05:00"}
seq: 2
kind: "behavior"
components: ["agent/code-reviewer"]
evidence: ["census"]
watches: []
---

## Change

Every heading block of the diff reviewer's prompt, and of the two shared files it loads, now has a content hash in a sidecar table under `docs/`, each with the kind of evidence behind the block and a one-line reason. The config doctor recomputes the hashes and fails on a block with no row and on a row whose block is gone. The prompt files themselves carry nothing.

## Evidence

census

### Anchor reasons

Anchor `rules/vue.md`, section `# Vue` (evidence: unproven):

29 words. Script setup, computed for derived state, and typed props and emits. Loads when a `.vue` file is read, which is rare in work branches.

## Result

An earlier pass tagged each rule with its evidence by reading, and a second pass over the same files did not reproduce the tags, so the anchor has to be mechanical and prospective: the hash is computed, not judged, and a changed block cannot keep an old reason without the doctor saying so. Whitespace does not move a hash, so a formatter's padding does not fire it. Twenty blocks anchored at the start, most of them as unmeasured judgment, which is the honest baseline that later removal rounds write over.

## Watch

—

## Back-out

—
